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
