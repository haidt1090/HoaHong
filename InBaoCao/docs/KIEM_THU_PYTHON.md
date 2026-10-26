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


## Sửa tham số COM — bản 2.0.1, 27/10/2026

- Hai lần sửa trước chưa đủ: `_FlagAsMethod` nhận đúng phương thức nhưng pywin32 tạo `def FilePrintSetup(self, *args)`, không có `**kwargs`. Test trước dùng mock nhận `**kwargs`, nên bỏ sót lỗi thực tế.
- Đọc trực tiếp `win32com/client/dynamic.py` (`_FlagAsMethod`, `_make_method_`) và `build.py` (`MakeVarArgsFuncMethod`) trong wheel pywin32 312 đang ghim. Tái hiện lỗi keyword bằng chính hàm sinh mã trích nguyên từ wheel, không sửa mã thư viện. Tài liệu web Microsoft không truy cập được trong môi trường này.
- Đổi lời gọi WordBasic sang tham số vị trí `FilePrintSetup(printer, 0, 0, 1)` (Printer, Options, Network, DoNotSetAsSysDefault). Không chuyển sang thay máy in mặc định toàn hệ thống.
- Rà và chuyển các lời gọi Open, PrintOut, Close, Quit sang tham số vị trí để tránh phụ thuộc tên tham số/type metadata. Giữ ReadOnly, bỏ recent files, in đồng bộ một bản, không lưu thay đổi.
- Test workflow chỉ nhận tham số vị trí. Bổ sung `test_com_contract.py` dùng generator thực của pywin32, kiểm tra chuỗi chọn máy in/mở/in/đóng tài liệu/thoát và tái hiện lỗi keyword cũ. CI Windows sẽ chạy bài này với pywin32 đã cài, không cần Word/máy in.
- Tại Linux: chạy riêng bài contract bằng hàm generator trích từ wheel: 1/1 đạt. Bộ kiểm tra thường: 14 đạt, 5 bỏ qua (4 GUI và 1 pywin32 Windows). Chưa xác minh Microsoft Word hoặc máy in thực trên Windows; không coi mô phỏng COM là kết quả in thực tế.
- Tiêu đề cửa sổ hiển thị phiên bản 2.0.1 để nhận biết bản đang chạy.
