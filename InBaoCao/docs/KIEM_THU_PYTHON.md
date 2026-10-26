# Kiểm thử Python 2.0 — 23/10/2026

- 6/6 unittest đạt: keyword chia run; bảng/header/footer; namespace Word mc:Ignorable; giữ định dạng, ảnh và A3; Unicode/escape XML; ngày/CCCD giữ 0; tự ghép cột và giá trị chung; lưu/đọc kho mẫu; ZIP backup/restore; chống đường dẫn ZIP; in từng người, hủy giữa hai lệnh và đóng Word khi lỗi.
- GUI Tkinter chạy thật trên màn hình ảo Linux: nhập mẫu 19 keyword, nhận hai người trong Excel mẫu, chọn một người xem thử, luồng nút in gửi hai lệnh không mở review. Word và máy in được mô phỏng, không in giấy.
- Hai Excel người dùng gửi vẫn nhận đúng dòng tiêu đề 3/4 và lần lượt đọc 10/4 người. Không chép các file này vào source ZIP.
- Mẫu DOCX đã ghép được kiểm tra độc lập bằng LibreOffice ở máy phát triển: mở được, giữ một trang A3 ngang, tên tiếng Việt đúng và không còn keyword. LibreOffice không phải phụ thuộc của ứng dụng.
- Chưa chạy Word COM thật, máy in A3 thật hoặc PyInstaller Windows. Python/PyInstaller trên Linux không tạo được Windows EXE; chỉ giao source và script build Windows, không tuyên bố đã tạo EXE Python.
- Chưa đo dung lượng EXE Python trên Windows. Không nhúng Electron/Chromium/LibreOffice hoặc dữ liệu người khám.

## Sửa bộ cài nhận Python hiện có

- Bộ cài nhận Python 64-bit 3.10–3.15 thay vì bắt buộc 3.12. Thông báo lỗi môi trường/thư viện/Tcl-Tk tách biệt.
- Nâng pywin32 lên 312 và PyInstaller lên 6.22.3. Đã kiểm tra tải được wheel Windows x64 cho CPython 3.15 từ PyPI; đây không phải xác nhận đã chạy ứng dụng hoặc in Word trên Windows 3.15 thật.
- 6/6 kiểm thử logic vẫn đạt sau thay đổi phụ thuộc/bộ cài.

## Hoàn thiện tương thích — 26/10/2026

- Tổng 13/13 bài kiểm thử: 6 luồng Word/Excel/in và 7 luồng chọn Python, nhận `.venv315`, bảo toàn môi trường lỗi, dùng đúng interpreter và giữ mã lỗi pip/build.
- Không báo build thành công nếu không có EXE đầu ra. Đã cấu hình CI Windows matrix 3.12/3.15; chưa chạy CI bản sửa, chưa xác minh Word COM trên máy Windows 3.15 thật.

## Hiển thị điều khiển in — 26/10/2026

- Vùng in cố định ngoài vùng nội dung co giãn; bảng lớn không đẩy hàng nút khỏi cửa sổ. Hàng nút tự xuống hai dòng khi tổng chiều rộng yêu cầu vượt phần hiển thị.
- 4 kiểm thử GUI thực trên Linux/Xvfb: 9 tổ hợp kích thước/DPI, vùng nhập liệu cao bất thường, nút quá rộng và trạng thái chọn người/tiến độ/dừng/hoàn tất. Không gửi lệnh tới máy in thật.
- Chạy cùng 13 bài logic bằng `INBAOCAO_GUI_TESTS=1`: tổng 17 bài. Nếu không bật biến này, 4 bài GUI được bỏ qua có chủ ý. Chưa xác minh bố cục bản sửa trên Windows thật.


Sửa lỗi kết nối Word: bỏ qua wrapper COM sinh sẵn, báo rõ bước lỗi và giữ nguyên lỗi gốc nếu đóng Word thất bại. Đếm sổ ngay sau PrintOut thành công để tránh in trùng khi đóng tài liệu lỗi. Kiểm tra tự động: 14 bài đạt, 4 bài GUI bỏ qua; chưa xác minh in thực tế trên Windows.

Sửa bước chọn máy in: đánh dấu FilePrintSetup là phương thức COM bằng _FlagAsMethod trước khi gọi, vì WordBasic thiếu metadata có thể khiến pywin32 đọc thành thuộc tính None. Bài kiểm tra mô phỏng FilePrintSetup ban đầu là None và chỉ gọi được sau khi đánh dấu; 14 bài đạt, 4 bài GUI bỏ qua. Cần xác minh tiếp trên Word Windows thực tế.
