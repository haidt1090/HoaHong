using System;
using System.Collections.Generic;
using System.Data;
using System.Drawing;
using System.Drawing.Printing;
using System.IO;
using System.Reflection;
using System.Windows.Forms;
using System.Xml.Serialization;

namespace DKS.QuickPay
{
    public static class Printing
    {
        const BindingFlags Flags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
        [ThreadStatic] static bool capturing;
        [ThreadStatic] static object capturedReport;
        [ThreadStatic] static Form capturedPreview;
        static object Field(object o, string name) { return o.GetType().GetField(name, Flags).GetValue(o); }
        static object Property(object o, string name)
        {
            for (Type t = o.GetType(); t != null; t = t.BaseType)
            { var p = t.GetProperty(name, Flags | BindingFlags.DeclaredOnly); if (p != null) return p.GetValue(o, null); }
            throw new MissingMemberException(o.GetType().FullName, name);
        }
        static void Set(object o, string name, object value)
        {
            var f = o.GetType().GetField(name, Flags);
            if (f != null) { f.SetValue(o, value); return; }
            o.GetType().GetProperty(name, Flags).SetValue(o, value, null);
        }
        static object Call(object o, string name, params object[] args)
        {
            try { return o.GetType().InvokeMember(name, Flags | BindingFlags.InvokeMethod, null, o, args); }
            catch (TargetInvocationException e) { throw e.InnerException ?? e; }
        }
        static void DisposeObject(object o) { var d = o as IDisposable; if (d != null) d.Dispose(); }
        static void ValidatePrinter(string name)
        {
            if (string.IsNullOrWhiteSpace(name) || !new PrinterSettings { PrinterName = name }.IsValid)
                throw new InvalidOperationException("Máy in không khả dụng: " + name + ". Hãy chọn lại máy in.");
        }
        static object NativePrinter(object rich) { return Property(rich, "Printer"); }
        static void PrintRich(object rich, string name)
        {
            // Same native ComponentPrinter path as RichEditControl.Print(), with an explicit printer.
            object printer = NativePrinter(rich);
            Call(printer, "InvokeLinkMethod", "Print", new object[] { name });
        }
        static void PrintReport(object report, string name)
        {
            Call(report, "CreateDocument");
            var printing = Assembly.LoadFrom(Path.Combine(Application.StartupPath, "DevExpress.XtraPrinting.v12.2.dll"));
            object system = Property(report, "PrintingSystem");
            object tool = Activator.CreateInstance(printing.GetType("DevExpress.XtraPrinting.PrintTool", true), new object[] { system });
            try { Call(tool, "Print", name); }
            finally { DisposeObject(tool); }
        }
        // Intercepts only the patient-record preview from uc_Nghiepvu.btnInhoso_Click.
        public static int ReportPreview(object preview)
        {
            if (capturing)
            {
                capturedReport = ReportAccess.FromPreview(preview);
                capturedPreview = (Form)preview;
                return (int)DialogResult.OK;
            }
            var settings = PrinterOptions.Read();
            if (string.IsNullOrEmpty(settings.RecordPrinter)) return (int)((Form)preview).ShowDialog();
            try
            {
                ValidatePrinter(settings.RecordPrinter);
                PrintReport(ReportAccess.FromPreview(preview), settings.RecordPrinter);
                return (int)DialogResult.OK;
            }
            catch (Exception e) { MessageBox.Show("Không in được bệnh án: " + e.Message, "In bệnh án", MessageBoxButtons.OK, MessageBoxIcon.Error); return (int)DialogResult.Cancel; }
            finally { ((Form)preview).Dispose(); }
        }
        public static int ShowMenu(object chooser, object host)
        {
            try { return ShowMenuCore(chooser, host); }
            catch (Exception ex) { MessageBox.Show("Không mở được cấu hình in: " + ex.Message, "In giấy khám sức khỏe", MessageBoxButtons.OK, MessageBoxIcon.Error); ((Form)chooser).Dispose(); return (int)DialogResult.Cancel; }
        }
        static int ShowMenuCore(object chooser, object host)
        {
            var menu = (Form)chooser;
            var settings = PrinterOptions.Read();
            var health = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Dock = DockStyle.Fill };
            var record = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Dock = DockStyle.Fill };
            foreach (string name in PrinterSettings.InstalledPrinters) { health.Items.Add(name); record.Items.Add(name); }
            Restore(health, settings.HealthPrinter); Restore(record, settings.RecordPrinter);
            var templates = new CheckedListBox { Dock = DockStyle.Fill, CheckOnClick = true, IntegralHeight = false };
            var status = new Label { AutoSize = true, Text = "Tích chọn các mẫu cần in; bệnh án sẽ được in kèm.", Dock = DockStyle.Top, Height = 26 };
            var print = new Button { Text = "Print", AutoSize = true };
            var close = (Control)Field(chooser, "btnThoat");
            close.Dock = DockStyle.None; close.Size = new Size(90, 30);
            var buttons = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.RightToLeft, WrapContents = false };
            buttons.Controls.Add(close); buttons.Controls.Add(print);
            var footer = new TableLayoutPanel { Dock = DockStyle.Bottom, Height = 114, ColumnCount = 2, RowCount = 3, Padding = new Padding(8) };
            footer.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 165)); footer.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            footer.RowStyles.Add(new RowStyle(SizeType.Absolute, 30)); footer.RowStyles.Add(new RowStyle(SizeType.Absolute, 30)); footer.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            footer.Controls.Add(new Label { Text = "Máy in giấy khám SK", AutoSize = true, Anchor = AnchorStyles.Left }, 0, 0); footer.Controls.Add(health, 1, 0);
            footer.Controls.Add(new Label { Text = "Máy in bệnh án", AutoSize = true, Anchor = AnchorStyles.Left }, 0, 1); footer.Controls.Add(record, 1, 1);
            footer.Controls.Add(buttons, 0, 2); footer.SetColumnSpan(buttons, 2);
            var grid = (Control)Field(chooser, "gridControl2"); grid.Visible = false;
            var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 3 };
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 28)); layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100)); layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 114));
            footer.Dock = DockStyle.Fill;
            layout.Controls.Add(status, 0, 0); layout.Controls.Add(templates, 0, 1); layout.Controls.Add(footer, 0, 2);
            menu.Controls.Add(layout); layout.BringToFront();
            menu.ClientSize = new Size(640, 440);
            EventHandler save = delegate
            {
                try { Save(health, record); status.Text = "Đã lưu máy in cho lần sau."; }
                catch (Exception ex) { status.Text = "Không lưu được máy in: " + ex.Message; }
            };
            health.SelectedIndexChanged += save; record.SelectedIndexChanged += save;
            menu.Shown += delegate
            {
                try
                {
                    DataTable table = Property(grid, "DataSource") as DataTable;
                    if (table == null || table.Rows.Count == 0) throw new InvalidOperationException("Chưa có mẫu khám sức khỏe.");
                    foreach (DataRow row in table.Rows) templates.Items.Add(new Template { Id = Convert.ToString(row["idthuthuat"]), Name = Convert.ToString(row["tenthuthuat"]) });
                }
                catch (Exception ex) { status.Text = ex.Message; print.Enabled = false; }
            };
            print.Click += delegate
            {
                print.Enabled = false;
                var documents = new List<Form>();
                Form preview = null;
                object report = null;
                int submitted = 0;
                try
                {
                    menu.Cursor = Cursors.WaitCursor;
                    string healthPrinter = Convert.ToString(health.SelectedItem), recordPrinter = Convert.ToString(record.SelectedItem);
                    ValidatePrinter(healthPrinter); ValidatePrinter(recordPrinter);
                    if (templates.CheckedItems.Count == 0) throw new InvalidOperationException("Hãy tích chọn ít nhất một mẫu khám sức khỏe.");
                    Save(health, record);
                    string patient = ((Control)Field(host, "txtidbenhnhan")).Text;
                    if (string.IsNullOrWhiteSpace(patient)) throw new InvalidOperationException("Chưa chọn bệnh nhân.");
                    var asm = chooser.GetType().Assembly;
                    Type parameters = asm.GetType("_247Dental.Common.Class.clsThamSo", true);
                    Type editorType = asm.GetType("_247Dental.Design.Mau_Sieu_Am.frmMauKetQuaChanDoanHinhAnh", true);
                    editorType.GetField("fmr", BindingFlags.Public | BindingFlags.Static).SetValue(null, "Note");
                    foreach (Template template in templates.CheckedItems)
                    {
                        object args = Activator.CreateInstance(parameters);
                        Set(args, "_StrIDBenhNhan", patient); Set(args, "_StrID_chidinhCLS", ""); Set(args, "_StrIDBacsi", ""); Set(args, "_StrIDThuThuat", template.Id); Set(args, "_chandoan", "");
                        var editor = (Form)Activator.CreateInstance(editorType, new object[] { args }); documents.Add(editor);
                        object rich = Field(editor, "txtNoidungmauketqua");
                        ((Control)rich).CreateControl();
                        string text = Convert.ToString(Property(Property(rich, "Document"), "Text"));
                        if (string.IsNullOrWhiteSpace(text)) throw new InvalidOperationException("Mẫu không có nội dung: " + template.Name);
                        NativePrinter(rich); // Verify native printing support before submitting any document.
                    }
                    capturedReport = null; capturedPreview = null; capturing = true;
                    try { Call(host, "btnInhoso_Click", host, EventArgs.Empty); report = capturedReport; preview = capturedPreview; }
                    finally { capturing = false; capturedReport = null; capturedPreview = null; }
                    if (report == null) throw new InvalidOperationException("Không tạo được bệnh án; chưa gửi lệnh in.");
                    Call(report, "CreateDocument");
                    foreach (Form editor in documents) { PrintRich(Field(editor, "txtNoidungmauketqua"), healthPrinter); submitted++; }
                    PrintReport(report, recordPrinter); submitted++;
                    status.Text = "Đã gửi " + submitted + " tài liệu tới máy in.";
                }
                catch (Exception ex)
                {
                    MessageBox.Show("Không hoàn tất in. Đã gửi " + submitted + " tài liệu.\n" + ex.Message + "\nKiểm tra hàng đợi in trước khi bấm Print lại.", "In giấy khám sức khỏe", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
                finally
                {
                    foreach (Form editor in documents) editor.Dispose();
                    if (preview != null) preview.Dispose(); DisposeObject(report);
                    menu.Cursor = Cursors.Default; print.Enabled = true;
                }
            };
            try { return (int)menu.ShowDialog(((Control)host).FindForm()); }
            finally { menu.Dispose(); }
        }
        static void Restore(ComboBox combo, string saved)
        {
            string name = string.IsNullOrEmpty(saved) ? new PrinterSettings().PrinterName : saved;
            if (!string.IsNullOrEmpty(name)) { if (!combo.Items.Contains(name)) combo.Items.Add(name); combo.SelectedItem = name; }
        }
        static void Save(ComboBox health, ComboBox record)
        { new PrinterOptions { HealthPrinter = Convert.ToString(health.SelectedItem), RecordPrinter = Convert.ToString(record.SelectedItem) }.Save(); }
        sealed class Template { public string Id; public string Name; public override string ToString() { return Name; } }
    }
}
