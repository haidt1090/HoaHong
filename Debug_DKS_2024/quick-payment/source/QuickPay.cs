using System;
using System.Collections.Generic;
using System.Data;
using System.Data.SqlClient;
using System.Globalization;
using System.Reflection;
using System.Transactions;
using System.Windows.Forms;

namespace DKS.QuickPay
{
    // Adapter for the exact DakhoasoSoft.exe recorded in the patch manifest.
    public static class Payment
    {
        static readonly object Gate = new object();
        const BindingFlags Flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance;
        static object Field(object o, string n) { return o.GetType().GetField(n, Flags).GetValue(o); }
        static void Field(object o, string n, object v) { o.GetType().GetField(n, Flags).SetValue(o, v); }
        static object Call(object o, string n, params object[] args)
        {
            try { return o.GetType().InvokeMember(n, Flags | BindingFlags.InvokeMethod, null, o, args); }
            catch (TargetInvocationException e) { throw e.InnerException ?? e; }
        }
        static object New(object form, string name) { return Activator.CreateInstance(form.GetType().Assembly.GetType(name, true)); }
        static DataTable Table(object o, string method, params object[] args)
        {
            DataTable dt = Call(o, method, args) as DataTable;
            if (dt == null) throw new InvalidOperationException("Không đọc được dữ liệu: " + method);
            return dt;
        }
        static string Text(object f, string n) { return ((Control)Field(f, n)).Text; }
        static void Text(object f, string n, string v) { ((Control)Field(f, n)).Text = v; }
        static void Check(object f, string n, bool v) { Field(f, n).GetType().GetProperty("Checked").SetValue(Field(f, n), v, null); }
        static void Source(object f, string n, object v)
        {
            object grid = Field(f, n);
            ((Control)grid).BindingContext = new BindingContext();
            grid.GetType().GetProperty("DataSource").SetValue(grid, v, null);
            Call(grid, "ForceInitialize");
        }
        static decimal Money(object value)
        {
            if (value == null || value == DBNull.Value) throw new InvalidOperationException("Thiếu số tiền; chưa thu tiền.");
            return Convert.ToDecimal(value, CultureInfo.CurrentCulture);
        }
        static string Amount(decimal v)
        {
            if (v < 0 || decimal.Truncate(v) != v) throw new InvalidOperationException("Số tiền không hợp lệ hoặc có phần lẻ. Cần kiểm tra trước khi thu.");
            return v.ToString("0", CultureInfo.InvariantCulture);
        }
        static string Column(DataTable dt, params string[] names)
        {
            foreach (string n in names) foreach (DataColumn c in dt.Columns)
                if (string.Equals(c.ColumnName, n, StringComparison.OrdinalIgnoreCase)) return c.ColumnName;
            throw new InvalidOperationException("Thiếu cột dữ liệu: " + string.Join("/", names));
        }
        static Dictionary<string, int> Quantities(DataTable dt)
        {
            var totals = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
            if (dt.Rows.Count == 0) return totals;
            string id = Column(dt, "idThuoc"), qty = Column(dt, "Soluong");
            foreach (DataRow r in dt.Rows)
            {
                string key = Convert.ToString(r[id]);
                decimal q = Money(r[qty]);
                if (string.IsNullOrEmpty(key) || q <= 0 || q != decimal.Truncate(q) || q > int.MaxValue)
                    throw new InvalidOperationException("Số lượng thuốc không hợp lệ.");
                int old; totals.TryGetValue(key, out old); totals[key] = checked(old + (int)q);
            }
            return totals;
        }
        static decimal ExamDebt(object f)
        {
            string visit = (string)Field(f, "_StrIDLankham");
            DataTable cost = Table(New(f, "_247Dental.Data.CTKhambenh_Data"), "TinhTienChoAnhEmOi", visit);
            DataTable paid = Table(New(f, "_247Dental.Data.Phieuthu_Data"), "TienAnhDaTra", visit);
            DataTable exam = Table(New(f, "_247Dental.Data.Khambenh_Data"), "SelectByID", visit);
            if (cost.Rows.Count != 1 || exam.Rows.Count != 1 || paid.Rows.Count > 1)
                throw new InvalidOperationException("Không xác định được công nợ lần khám.");
            decimal gross = Money(cost.Rows[0]["Tongphaithanhtoan"]);
            decimal discount = Money(cost.Rows[0]["Tonggoamgia"]);
            decimal coverage = Money(exam.Rows[0]["phantramduocchitra"]);
            decimal settled = paid.Rows.Count == 0 || paid.Rows[0]["TongDaThanhToan"] == DBNull.Value ? 0 : Money(paid.Rows[0]["TongDaThanhToan"]);
            if (gross < 0 || discount < 0 || coverage < 0 || coverage > 100 || settled < 0)
                throw new InvalidOperationException("Dữ liệu công nợ không hợp lệ.");
            return Rules.ExamDebt(gross, discount, settled, coverage);
        }
        static decimal DrugDebt(object f, string export)
        {
            DataTable dt = Table(New(f, "_247Dental.Data.XuatThuoc_Data"), "TongTienDaTraByID", export);
            if (dt.Rows.Count != 1) throw new InvalidOperationException("Không đọc được công nợ phiếu xuất thuốc.");
            return Math.Max(0, Money(dt.Rows[0]["conno"]));
        }
        static decimal PayPrescription(object f, string prescription)
        {
            object exports = New(f, "_247Dental.Data.XuatThuoc_Data");
            object details = New(f, "_247Dental.Data.ChiTietXuatThuoc_Data");
            DataTable ordered = Table(New(f, "_247Dental.Data.TranAnh_CTDonthuoc_Data"), "SelectAll", prescription, 2);
            var wanted = Quantities(ordered);
            if (wanted.Count == 0) return 0;
            DataTable existing = Table(exports, "SelectIdDonThuoc", prescription);
            if (existing.Rows.Count > 1) throw new InvalidOperationException("Đơn thuốc có nhiều phiếu xuất. Cần kiểm tra thủ công.");
            Field(f, "Iddonthuoc", prescription);
            // Avoid checkbox events: CheckData is called explicitly after loading this prescription.
            Field(f, "is_thu", 3);
            Call(f, "CheckData");
            string export = Convert.ToString(Field(f, "valIdXuatThuoc"));
            if (string.IsNullOrEmpty(export)) throw new InvalidOperationException("Chưa tạo được phiếu xuất thuốc.");
            Text(f, "txtMaPhieuXuat", export);
            DataTable exportHeader = Table(exports, "SelectByID", export);
            if (exportHeader.Rows.Count != 1) throw new InvalidOperationException("Không đọc được kho của phiếu xuất.");
            ((ListControl)Field(f, "cbKhoThuoc")).SelectedValue = exportHeader.Rows[0]["idkho"];
            if (((ListControl)Field(f, "cbKhoThuoc")).SelectedValue == null) throw new InvalidOperationException("Kho của phiếu xuất không còn khả dụng.");
            DataTable issued = Table(details, "SelectByID", export);
            var already = Quantities(issued);
            foreach (var p in already)
            {
                int quantity;
                if (!wanted.TryGetValue(p.Key, out quantity) || p.Value > quantity)
                    throw new InvalidOperationException("Phiếu xuất khác đơn thuốc. Cần kiểm tra thủ công.");
            }
            DataTable missing = ordered.Clone();
            string idColumn = Column(ordered, "idThuoc"), quantityColumn = Column(ordered, "Soluong");
            var added = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (DataRow r in ordered.Rows)
            {
                string id = Convert.ToString(r[idColumn]);
                if (!added.Add(id)) continue;
                int done; already.TryGetValue(id, out done);
                int remaining = wanted[id] - done;
                if (remaining == 0) continue;
                string warehouse = Convert.ToString(((ListControl)Field(f, "cbKhoThuoc")).SelectedValue);
                if (string.IsNullOrEmpty(warehouse)) throw new InvalidOperationException("Chưa xác định kho thuốc.");
                DataTable stock = Table(details, "HUY_NV_Check_SL_TONTHUOC_BYIDNHAPTHUOC", id, warehouse);
                decimal available = 0;
                foreach (DataRow lot in stock.Rows) available += Money(lot["soluong_toncuoiki"]);
                if (available < remaining) throw new InvalidOperationException("Không đủ tồn kho cho thuốc " + id + ". Chưa hoàn tất thanh toán.");
                DataRow next = missing.NewRow(); next.ItemArray = (object[])r.ItemArray.Clone(); next[quantityColumn] = remaining; missing.Rows.Add(next);
            }
            if (missing.Rows.Count > 0)
            {
                Source(f, "GC_donthuoc", missing);
                Call(f, "bntXuatTatCaDonThuoc_Click", f, EventArgs.Empty);
            }
            var actual = Quantities(Table(details, "SelectByID", export));
            if (actual.Count != wanted.Count) throw new InvalidOperationException("Xuất thuốc chưa đầy đủ.");
            foreach (var p in wanted)
            {
                int q; if (!actual.TryGetValue(p.Key, out q) || q != p.Value) throw new InvalidOperationException("Số lượng xuất thuốc không khớp đơn.");
            }
            decimal debt = DrugDebt(f, export);
            if (debt > 0)
            {
                Text(f, "txtConNo", Amount(debt));
                Call(f, "thanhtoanthuoc");
                if (DrugDebt(f, export) != 0) throw new InvalidOperationException("Chưa lưu đủ tiền thuốc.");
            }
            Call(exports, "LUAN_Update_tblXuatThuoc_isxuat", export, 1);
            return debt;
        }
        // Same stack return type as the replaced ShowDialog call; the form is never shown.
        public static int Run(object receipt)
        {
            lock (Gate)
            {
                Form form = (Form)receipt;
                try
                {
                    if (Convert.ToString(Field(receipt, "_LayTuForm")) != "Nghiệp vụ") throw new InvalidOperationException("Sai ngữ cảnh thanh toán.");
                    var dbType = receipt.GetType().Assembly.GetType("_247Dental.Data.KetNoiCSDL_Data", true);
                    using (var connection = (SqlConnection)dbType.GetMethod("GetSQLConnection").Invoke(null, null))
                    {
                        // Capture before Open: SqlConnection removes credentials afterwards unless Persist Security Info is enabled.
                        string transactionConnectionString = connection.ConnectionString;
                        if (!new SqlConnectionStringBuilder(transactionConnectionString).Enlist)
                            throw new InvalidOperationException("Kết nối SQL phải bật Enlist để thanh toán nguyên khối.");
                        connection.Open();
                        using (var command = connection.CreateCommand())
                        {
                            command.CommandText = "DECLARE @r int; EXEC @r=sys.sp_getapplock @Resource=N'DKS.QuickPay.All', @LockMode='Exclusive', @LockOwner='Session', @LockTimeout=0; SELECT @r;";
                            if (Convert.ToInt32(command.ExecuteScalar()) < 0) throw new InvalidOperationException("Đang có giao dịch thanh toán khác. Vui lòng thử lại.");
                        }
                        try
                        {
                            decimal total = 0;
                            var options = new TransactionOptions { IsolationLevel = System.Transactions.IsolationLevel.Serializable, Timeout = TimeSpan.FromMinutes(2) };
                            using (var transaction = new TransactionScope(TransactionScopeOption.RequiresNew, options))
                            {
                                // Original data access opens multiple connections. Require successful enlistment
                                // before invoking any methods that may write; SQL/MSDTC failures abort this flow.
                                using (var probe = new SqlConnection(transactionConnectionString)) { probe.Open(); }
                                Call(receipt, "frm_PhieuThu2_Load", receipt, EventArgs.Empty);
                                if (((ListControl)Field(receipt, "cbNguoithu")).SelectedValue == null ||
                                    ((ListControl)Field(receipt, "cbLoaikhoanthu")).SelectedValue == null ||
                                    string.IsNullOrWhiteSpace(Text(receipt, "txtNguoinop")))
                                    throw new InvalidOperationException("Thiếu thông tin người nộp, thu ngân hoặc loại khoản thu.");
                                Check(receipt, "chkGhino", false); Check(receipt, "chkTamung", false);
                                Check(receipt, "rbtTienMat", true); Check(receipt, "rbtChuyenKhoan", false);
                                string visit = Convert.ToString(Field(receipt, "_StrIDLankham"));
                                DataTable prescriptions = Table(New(receipt, "_247Dental.Data.TranAnh_Donthuoc_Data"), "SelectByidkhambenh", visit);
                                var processed = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                                foreach (DataRow row in prescriptions.Rows)
                                {
                                    string id = Convert.ToString(row["idDonThuoc"]);
                                    if (string.IsNullOrEmpty(id) || !processed.Add(id)) throw new InvalidOperationException("Mã đơn thuốc trống hoặc trùng.");
                                    total += PayPrescription(receipt, id);
                                }
                                decimal exam = ExamDebt(receipt);
                                if (exam > 0)
                                {
                                    Text(receipt, "txtSotien", Amount(exam));
                                    Call(receipt, "thanhtoanthuthuat");
                                    if (ExamDebt(receipt) != 0) throw new InvalidOperationException("Chưa lưu đủ tiền khám/thủ thuật.");
                                    total += exam;
                                }
                                transaction.Complete();
                            }
                            MessageBox.Show(total > 0 ? "Đã thanh toán " + total.ToString("N0") + " đồng bằng tiền mặt." : "Lần khám này đã thanh toán đủ.", "Thanh toán", MessageBoxButtons.OK, MessageBoxIcon.Information);
                        }
                        finally
                        {
                            using (var command = connection.CreateCommand())
                            {
                                command.CommandText = "EXEC sys.sp_releaseapplock @Resource=N'DKS.QuickPay.All', @LockOwner='Session';";
                                command.ExecuteNonQuery();
                            }
                        }
                    }
                    return (int)DialogResult.OK;
                }
                catch (Exception ex)
                {
                    MessageBox.Show("Không hoàn tất thanh toán.\n" + ex.Message + "\nKiểm tra lại công nợ trước khi thao tác tiếp.", "Thanh toán", MessageBoxButtons.OK, MessageBoxIcon.Error);
                    return (int)DialogResult.Cancel;
                }
                finally { form.Dispose(); }
            }
        }
    }
}
