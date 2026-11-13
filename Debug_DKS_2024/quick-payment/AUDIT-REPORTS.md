# Kiểm tra toàn bộ Báo cáo – Thống kê

## Kết luận và phạm vi

Đã so sánh EXE đang dùng với EXE gốc trong repo bằng IL/metadata, đồng thời đọc lại các form báo cáo, đường lấy dữ liệu, phân loại phiếu thu và bộ in của adapter. Không tìm thấy thay đổi trực tiếp vào mã của các mục báo cáo, các nút mở báo cáo, mẫu in nhúng hoặc các file SQL có sẵn. Chưa có kết nối tới SQL Server/Windows của người dùng nên chưa thể xác nhận số liệu thực tế trước/sau thanh toán hay việc in/xuất thực tế.

## Từng mục trong menu

| Mục | Kết quả đối chiếu mã |
|---|---|
| Danh sách bệnh nhân khám bệnh | Hàm mở, toàn bộ 32 phương thức của màn hình, lọc và in/xuất giữ nguyên |
| Tổng hợp thủ thuật theo bác sĩ | Hàm mở, toàn bộ 13 phương thức, lọc bác sĩ/ngày, dựng báo cáo và in/xuất giữ nguyên |
| Danh sách bệnh nhân nợ tiền | Hàm mở, toàn bộ 11 phương thức, đọc tiền khám/phiếu thu và in/xuất giữ nguyên |
| Tổng hợp thu chi | Hàm mở, toàn bộ 9 phương thức, nhóm thu khám/thu thuốc/thu khác và in giữ nguyên |
| Danh sách thu tiền khám bệnh | Hàm mở, toàn bộ 11 phương thức, lọc và đọc phiếu thu theo thời gian giữ nguyên |
| Tổng hợp khám | Hàm mở và 15 phương thức của form tổng hợp giữ nguyên; giữ chế độ BAOCAOTONGHOPKHAMBENH2 |
| Chăm sóc khách hàng | Hàm mở, toàn bộ 9 phương thức, lấy dữ liệu và xuất Excel giữ nguyên |
| Tổng hợp khám bệnh | Hàm mở và 15 phương thức của form tổng hợp giữ nguyên; giữ chế độ BAOCAOTONGHOPKHAMBENH |
| Hoa hồng chi tiết (đang ẩn) | Hàm mở và toàn bộ 10 phương thức của form giữ nguyên |
| Công nợ khách cơ quan (đang ẩn) | Hàm mở và toàn bộ 13 phương thức của form giữ nguyên |

Hai mục tổng hợp dùng chung một form nhưng truyền hai chế độ khác nhau; cả hai đường gọi và hai nhánh xử lý đã được đối chiếu.

## Bằng chứng tự động

- So sánh 15.324 phương thức; chỉ có 8 phương thức EXE đã biết bị vá: 5 hàm truy cập dữ liệu SQL có guard và 3 hàm trong màn hình Khám bệnh – Điều trị (Thanh toán, In bệnh án, Giấy Khám SK).
- 3.478 phương thức trong 213 lớp/nhóm có tên báo cáo hoặc XtraReport giữ nguyên. Đây là tập được nhận diện theo tên, không phải 213 màn hình riêng biệt.
- 213 tài nguyên nhúng có nội dung byte giống bản gốc.
- Cả 10 handler menu và 9 form duy nhất bên trên giữ nguyên; hai chế độ tổng hợp dùng chung form.
- Đối chiếu Git từ trước khi vá: không sửa script SQL có sẵn, DLL DevExpress hoặc mẫu gốc.
- Hook in chỉ áp dụng lệnh xem trước bệnh án của `uc_Nghiepvu.btnInhoso_Click`; không thay `Form.ShowDialog` hoặc hệ thống in toàn cục. Hai máy in đã lưu không đổi máy in mặc định của Windows hay ép các báo cáo trong menu sang máy đó.
- Các wrapper SQL chỉ chạy adapter khi `Database.IsActive()` trên thread hiện tại; ngoài thanh toán nhanh quay lại thân hàm gốc.

## Rủi ro đã tái hiện và sửa trong lần rà soát

Bản adapter trước có thể để sót trạng thái giao dịch nếu chính `transaction.Dispose()` ném lỗi. Truy vấn báo cáo chạy sau đó trên cùng thread có thể đi nhầm vào giao dịch không còn hiệu lực. Test giả lập đã tái hiện lỗi trước khi sửa. Đã chuyển việc xóa trạng thái sang `finally` riêng để luôn chạy, kể cả khi giải phóng giao dịch thất bại. Test hiện đã qua. Không có bằng chứng lỗi này đã xảy ra với dữ liệu của người dùng.

Đã bổ sung kiểm tra loại khoản thu khám bệnh phải là `101120140000`, vì báo cáo tổng hợp thu chi và script `F_TIENTHANHTOAN_BYIDKHAMBENH` trong repo dùng mã này. Thuốc vẫn dùng mã `101120140002` theo hàm lưu gốc. Nếu danh mục không khớp, dừng thu thay vì ghi phiếu vào nhóm khác. Không tự sửa danh mục hoặc phiếu thu cũ.

## Những số liệu có thể thay đổi đúng theo chức năng mới

Thanh toán nhanh tạo phiếu thu thật, thu hết phần còn nợ và có thể xuất thuốc chưa xuất. Vì vậy báo cáo thu chi/thu tiền tăng, công nợ giảm và báo cáo kho cập nhật là kết quả dự kiến. Tiền thu nhanh mặc định tiền mặt, không dùng tạm ứng/ghi nợ; ca giữ mặc định của form gốc (ca1). Nếu trước đây người dùng chọn chuyển khoản, ngày thu khác hoặc ca2 bằng tay, báo cáo chia theo các tiêu chí đó sẽ khác. Các lựa chọn này hiện không được hỏi lại trong thanh toán nhanh.

Bản vá gọi lại hàm tạo phiếu thu/xuất thuốc/ghi nhật ký gốc; không chỉ sửa nhãn hiển thị. Công nợ được đọc và đối chiếu sau ghi. Tuy nhiên code/stored procedure thực tế trong database chưa được truy cập để kiểm chứng toàn bộ nghiệp vụ.

## Kiểm tra đã chạy và phần còn thiếu

28 tình huống giả lập/đơn vị đã qua: 12 công nợ, 8 giao dịch cục bộ (có lỗi giải phóng giao dịch), 2 lưu máy in, 3 đọc báo cáo setter-only, 3 phân loại phiếu thu. Build adapter .NET Framework 4.0 không lỗi/cảnh báo. Không dùng các test này để khẳng định SQL Server/driver máy in thực tế đã qua.

Để xác nhận số liệu, cần đối chiếu trên database thử: dùng cùng bộ lọc ngày/đối tượng/bác sĩ trước và sau một giao dịch gồm tiền khám + tiền thuốc; kiểm tra tổng thu, nhóm thu, công nợ, số lượt, nhật ký và tồn kho. Kiểm tra thêm giao dịch lỗi/thiếu tồn không để lại phiếu dang dở và bấm lại không thu trùng. Dữ liệu lịch sử đã thu trước đây chưa được kiểm tra hoặc thay đổi trong lần rà soát này.

Có thể chạy lại công cụ trong thư mục `audit` với ba đối số: EXE gốc, EXE đã vá và đường dẫn JSON kết quả. `results.json` ghi đối chiếu EXE; các sửa phòng lỗi trong lần này nằm ở DLL adapter, không sửa thêm EXE/báo cáo.
