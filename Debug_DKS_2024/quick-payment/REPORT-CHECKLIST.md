# Chi tiết kiểm tra từng mục Báo cáo – Thống kê

## Cách đọc kết quả

**Đã kiểm tra:** so sánh mã IL, handler menu, form, bộ lọc, đường dựng/in/xuất và tài nguyên nhúng của EXE với bản gốc. Kết quả đối chiếu máy nằm trong `audit/results.json`, kết luận tổng thể trong `AUDIT-REPORTS.md`.

**Chưa thực hiện:** chạy từng báo cáo trên Windows/SQL Server của người dùng, đối chiếu các stored procedure đang cài, số liệu lịch sử và driver máy in. Các bước đối soát dưới đây là kiểm tra cần làm trên database thử, không phải kết quả đã chạy thực tế.

## 1. Danh sách bệnh nhân khám bệnh

- Handler `barButtonItem1_ItemClick`, form `UC_DS_BENHNHAN_KHAMBENH`: 32 phương thức giữ nguyên.
- Đã đối chiếu bộ lọc ngày, phòng chỉ định, đối tượng; đường chọn lần khám và lấy chi tiết qua `LUAN_CHITIET_BENHNHAN_KHAMBENH_By_IdKhambenh`; dựng mẫu và xuất PDF.
- Cần đối soát: cùng khoảng ngày/phòng/đối tượng trên bản gốc và bản mới, so sánh danh sách mã bệnh nhân/lần khám, số dòng, chi tiết thủ thuật, tổng tiền và file xuất.
- Thanh toán nhanh không tạo thêm bệnh nhân/lần khám/thủ thuật. Chỉ số tiền đã trả/còn nợ liên quan có thể thay đổi sau thu tiền. Bộ lọc trạng thái có thể làm danh sách hiển thị thay đổi theo dữ liệu mới.

## 2. Tổng hợp thủ thuật theo bác sĩ

- Handler `barButtonItem2_ItemClick`, form `frm_BAOCAO_THUTHUAT_THEO_BACSI`: 13 phương thức giữ nguyên.
- Đã đối chiếu chọn tất cả/một bác sĩ, lọc ngày và đối tượng, đường gọi `LUAN_tblCTKhambenh_BAOCAO_THUTHUAT_THEO_TATCA_BACSI` / `LUAN_tblCTKhambenh_BAOCAO_THUTHUAT_THEOBACSI`, dựng/in/xuất báo cáo.
- Cần đối soát: số lượng từng thủ thuật, bác sĩ thực hiện, số tiền/tổng theo bác sĩ và tổng cuối; thử cả tất cả bác sĩ và một bác sĩ.
- Không sửa bác sĩ hoặc chi tiết thủ thuật trong luồng thanh toán nhanh. Chưa xác nhận cách các stored procedure thực tế xử lý trạng thái đã thu tiền.

## 3. Danh sách bệnh nhân nợ tiền

- Handler `barButtonItem3_ItemClick`, form `frm_DS_BENHNHAN_NOTIEN`: 11 phương thức giữ nguyên.
- Đã đối chiếu lọc ngày/đối tượng và các đường tính `LUAN_tblCTKhambenh_TINHTIEN_By_idkhambenh`, `LUAN_tblPhieuthu_TINHTIEN_By_thanhtoancholankham`; mẫu và xuất PDF giữ nguyên.
- Cần đối soát trước/sau: số phải trả, đã trả, còn nợ theo từng lần khám và toàn bệnh nhân. Sau thu đủ, lần khám thử không còn nợ; bệnh nhân vẫn có thể xuất hiện nếu còn nợ lần khám khác.
- Thử trường hợp đã trả một phần, giảm giá, phần được chi trả, bấm lại khi đủ và thanh toán lỗi. Không được mất nợ hoặc tăng phiếu thu khi giao dịch đã rollback.

## 4. Tổng hợp thu chi

- Handler `bntBaocaotonghopthuchi_ItemClick`, form `uc_TONGHOPTHUCHI`: 9 phương thức giữ nguyên.
- Đã đối chiếu lấy phiếu thu/chi theo ngày và đối tượng, tách nhóm, cộng tổng và đường in.
- Mã phân nhóm trong code gốc: thu khám `101120140000`, thu khác `101120140001`, thu thuốc `101120140002`; tạm ứng có đường lấy dữ liệu riêng. Adapter hiện kiểm tra đúng mã thu khám trước khi ghi; thuốc dùng hàm lưu gốc với mã thu thuốc.
- Cần đối soát: từng phiếu mới thuộc đúng nhóm; tổng tăng đúng số thực thu, không cộng tiền thuốc hai lần vào thu khám. Phần chi không được tự phát sinh từ việc bấm Thanh toán. Đối chiếu riêng nhóm tạm ứng và các khoản lịch sử.
- Thanh toán nhanh mặc định tiền mặt, không dùng tạm ứng/ghi nợ; ca theo mặc định form gốc là ca1.

## 5. Danh sách thu tiền khám bệnh

- Handler `bntBaoCaoThuTienKhamBenh_ItemClick`, form `uc_DS_THUTIEN_KHAMBENH`: 11 phương thức giữ nguyên.
- Đã đối chiếu lọc ngày/đối tượng, lấy nội dung thủ thuật, tính tiền khám và phiếu thu bằng `LUAN_tblPhieuthu_TINHTIEN_By_thanhtoancholankham_tungay_denngay`; đường in/xuất giữ nguyên.
- Cần đối soát: bệnh nhân, lần khám, ngày thu, số thu đúng phần khám/thủ thuật; tiền thuốc không lọt vào nhóm này. Thử lần khám và ngày thu nằm ở hai ngày khác nhau với đúng bộ lọc của bản gốc.
- Chưa có định nghĩa stored procedure thực tế để xác nhận mọi quy tắc lọc ngày và khoản thu trong database đang dùng.

## 6. Báo cáo tổng hợp khám

- Handler `bntTongHopKhamBenh_ItemClick`, form `frm_BAOCAO_TONGHOP_KHAMBENH`: 15 phương thức giữ nguyên.
- Chế độ riêng được giữ nguyên: `BAOCAOTONGHOPKHAMBENH2`. Không ghép nhầm với mục tổng hợp khám bệnh bên dưới.
- Đã đối chiếu nhánh `huynv_tblCTKhambenh_BAOCAO_THUTHUAT_THEO_TATCA_NHOMTHUTHUAT` / `huynv_tblCTKhambenh_BAOCAO_THUTHUAT_THEO_NHOMTHUTHUAT`, chọn nhóm và dựng mẫu tương ứng.
- Cần đối soát: từng nhóm thủ thuật, số lượng, đơn giá/thành tiền và tổng; thử một nhóm và tất cả nhóm, đối tượng cụ thể và tất cả.

## 7. Báo cáo chăm sóc khách hàng

- Handler `barButtonItem10_ItemClick`, form `UCBaoCaoChamSocKhachHang`: 9 phương thức giữ nguyên.
- Đã đối chiếu kiểm tra quyền, chọn nhân viên chăm sóc, tìm kiếm và xuất XLS/XLSX.
- Cần đối soát: cùng ngày/nhân viên/bộ lọc phải ra cùng mã khách hàng, lịch sử chăm sóc và số dòng; xuất Excel không thiếu dữ liệu.
- Adapter thanh toán/in không sửa lịch sử chăm sóc hay nhân viên phụ trách. Không đưa máy in đã chọn cho giấy khám vào đường xuất Excel này.

## 8. Báo cáo tổng hợp khám bệnh

- Handler `barButtonItem12_ItemClick`, dùng chung form tổng hợp nhưng giữ chế độ `BAOCAOTONGHOPKHAMBENH`.
- Đã đối chiếu nhánh `CHUONGBUI_tblCTKhambenh_BAOCAO_THUTHUAT_THEO_TATCA_NHOMTHUTHUAT` / `CHUONGBUI_tblCTKhambenh_BAOCAO_THUTHUAT_THEO_NHOMTHUTHUAT`, đường lấy tổng tiền nhóm và mẫu riêng.
- Cần đối soát: cùng nhóm/ngày/đối tượng trên hai phiên bản, số lượng và tổng từng nhóm, tổng cuối; kiểm tra không dùng nhầm chế độ/mẫu của mục số 6.

## 9. Hoa hồng chi tiết — mục đang ẩn

- Handler `barButtonItem8_ItemClick`, form `frm_tinhhoahong`: 10 phương thức giữ nguyên.
- Đã đối chiếu chọn nhóm/ngày, gọi `CHUONGBUI_tblCTKhambenh_BAOCAO_cacMau_NHOMTT`, dựng báo cáo hoa hồng và xem trước.
- Cần đối soát: đối tác/bác sĩ, tỷ lệ/căn cứ tính, số tiền từng dòng và tổng; không tự kết luận hoa hồng không đổi nếu database có quy tắc dựa trên số đã thu.
- Không thay tỷ lệ, mã đối tác hay công thức báo cáo trong bản vá.

## 10. Công nợ khách cơ quan — mục đang ẩn

- Handler `btnBaocaocongno_ItemClick`, form `Uc_Congnokhachcoquan`: 13 phương thức giữ nguyên.
- Đã đối chiếu chọn cơ quan/ngày, lấy dữ liệu bằng `Select_DS_KHACHCOQUAN`, dựng/in/xuất PDF.
- Cần đối soát: đúng cơ quan, từng bệnh nhân/lần khám, tổng phát sinh/đã thu/còn nợ và tổng cơ quan. Thử đúng đối tượng cơ quan trước/sau thu tiền; không đánh đồng người nộp với cơ quan chịu chi trả.

## Một kịch bản đối soát chung

Trên database thử, chọn một lần khám giả định có tiền khám 140.000đ và thuốc 60.000đ; đã trả tiền khám 40.000đ, thuốc 20.000đ, không giảm giá/chi trả khác. Các số này chỉ là dữ liệu kiểm tra đề xuất.

Sau thanh toán nhanh, số thu thêm dự kiến là 100.000đ tiền khám và 40.000đ tiền thuốc, tổng 140.000đ. Đối chiếu đồng thời phiếu thu, báo cáo tổng hợp thu chi, thu tiền khám, công nợ và kho. Bấm lại không được tạo thêm phiếu hoặc xuất thêm thuốc. Mở/in giấy khám không được tự tạo phiếu thu. Nếu test thiếu tồn/lỗi SQL thì không được lưu giao dịch dang dở.

Cùng một snapshot database và bộ lọc, kết quả bản gốc/bản mới cần khớp trước khi thực hiện nghiệp vụ mới. Chênh lệch sau thanh toán phải giải thích được bằng đúng các phiếu và xuất kho vừa ghi. Sau lỗi giao dịch phải mở lại báo cáo để kiểm tra không còn trạng thái giao dịch sót; lỗi dọn transaction đã có regression test giả lập.
