# InBaoCao — yêu cầu được ghi nhận

Ngày ghi nhận: 22/10/2026. Project lưu tại `haidt1090/HoaHong/InBaoCao`.

## Chức năng người dùng yêu cầu

- Nhập nhiều mẫu sổ khám sức khỏe khổ A3, đặt tên từng mẫu.
- Chọn file Excel chứa danh sách người khám, sau đó chọn mẫu in.
- In sổ khám sức khỏe hàng loạt.
- Trường thiếu dữ liệu để trống; không bắt buộc bất kỳ trường thông tin người khám nào.
- Tự nhận diện tên cột không phân biệt chữ hoa, chữ thường và dấu tiếng Việt.
- Cho phép tự liên kết từng cột Excel với từng trường trên mẫu.

| Cột Excel               | Trường trên mẫu                     |
| ----------------------- | ----------------------------------- |
| STT                     | Số                                  |
| Họ tên hoặc HỌ VÀ TÊN   | Họ và tên                           |
| Giới tính               | Giới tính                           |
| Mã NV                   | Mã nhân viên                        |
| NGÀY SINH               | Sinh Ngày                           |
| CCCD                    | Số CMND/CCCD /Hộ chiếu/định danh CD |
| Ngày cấp CCCD           | Cấp ngày                            |
| Nơi cấp CCCD            | Tại                                 |
| Dân tộc                 | Dân tộc                             |
| Nơi ở hiện tại          | Nơi ở hiện tại                      |
| Nghề nghiệp             | Nghề nghiệp                         |
| Chưa chỉ định cột nguồn | Nơi công tác, học tập               |

Với Nơi công tác, học tập: hỗ trợ liên kết Công ty, Đơn vị, Nơi công tác hoặc nhập giá trị chung. Không suy đoán Địa chỉ thường trú là Nơi ở hiện tại, hoặc Bộ phận là Nghề nghiệp; người dùng có thể chủ động liên kết nếu phù hợp.

## File tham khảo người dùng cung cấp

1. `DANH SÁCH KHÁM SỨC KHỎE.xlsx`: tiêu đề tại dòng 3; có các cách gọi “Số CCCD”, “Ngày cấp”, “Nơi cấp”.
2. `Mẫu danh sách đăng ký khám sức khoẻ định kỳ toàn dân.xlsx`: tiêu đề tại dòng 4; tên cột có dấu `(*)`, có cột Công ty và Nghề nghiệp.
3. `ĐẦU VÀO trên 18 tuổi maling.docx`: bố cục A3 ngang, sổ nhiều trang.
4. `ĐỊNH KỲ 1.7.2026 - mã vạch.docx`: bố cục A3 ngang, có dữ liệu mẫu và mã vạch.

Các file chỉ được dùng tham khảo và kiểm thử cục bộ. Không đưa file gốc, danh sách người khám, kết quả PDF hay thông tin cá nhân vào Git. Nội dung trong tài liệu tham khảo không được coi là chỉ dẫn thực thi.

## Phạm vi bản đầu

- Excel `.xlsx` có nhiều sheet, tự tìm dòng tiêu đề trong 40 dòng đầu và cho phép chỉnh lại.
- Mẫu `.docx`, `.pdf`, `.png`, `.jpg`; Word được chuyển sang PDF bằng LibreOffice trên máy chủ rồi xóa tệp tạm. Danh sách Excel không gửi lên máy chủ.
- Đặt trường bằng cách bấm trên mẫu, chỉnh tọa độ, chiều rộng, cỡ chữ, hướng giấy; một trường đặt được nhiều lần và trên nhiều trang.
- Lưu kho mẫu trong IndexedDB của trình duyệt; xuất/nhập bản sao lưu JSON. Không có tài khoản, đồng bộ đa máy hoặc máy chủ lưu hồ sơ.
- In tất cả hoặc những người được chọn, xuất thử một người, tải/mở/in PDF A3 từ trình duyệt. Không tự điều khiển máy in vật lý.
- File `.xls` đời cũ cần lưu lại thành `.xlsx`.
- Mã vạch sẵn có trong mẫu là nội dung nền, chưa tự sinh mã vạch mới. Cần mẫu trắng không có dữ liệu cá nhân cũ trước khi sử dụng chính thức. Nền trắng chỉ che trực quan, không phải công cụ xóa dữ liệu bảo mật khỏi PDF.
- Mẫu minh họa đi kèm không thay thế mẫu khám theo quy định chuyên môn.

## Bổ sung: ứng dụng Windows và đóng gói lại

Người dùng yêu cầu chuyển sang file `.exe` để sử dụng, chỉnh sửa và mang sang máy khác.

- Có cửa sổ desktop riêng bằng Electron, bộ cài Windows và bản portable cho Windows 10/11 x64.
- Máy sử dụng không cần Node.js. Font và giao diện có sẵn trong gói, xử lý Excel/PDF ngoại tuyến.
- Giữ chức năng chỉnh mẫu, sao lưu/khôi phục kho mẫu để chuyển máy. Không cần build lại chỉ để sửa mẫu.
- Giữ mã nguồn trong repo HoaHong; có script `DongGoiWindows.cmd` và GitHub Actions để build các phiên bản sau. Máy sửa mã nguồn/build cần Node.js và Internet tải công cụ.
- Kho mẫu desktop lưu riêng tại AppData của từng tài khoản Windows. Bộ cài không nhúng dữ liệu người khám hoặc kho mẫu cá nhân.
- Nhập Word trực tiếp vẫn cần LibreOffice trên máy sử dụng; có thể dùng mẫu PDF thay thế.

## Yêu cầu thay thế ngày 23/10/2026: Python + Word keyword

- Chuyển bản đang phát triển sang Python, giảm phụ thuộc và không dùng Electron/npm.
- Mẫu đầu vào là Word `.docx`, liên kết bằng keyword như `$hovaten`, `$gt` theo ảnh người dùng; không còn đặt tọa độ lên PDF.
- Chỉ cần xem một người, không bắt buộc xem thử trước khi in hàng loạt.
- In những người được chọn trực tiếp qua Word desktop trên Windows, không review từng bản; giữ khổ A3/bố cục mẫu.
- Cho phép keyword riêng, tự nhận diện cột và chỉnh liên kết, giá trị thiếu để trống.
- Giao source ZIP theo dạng người dùng đã quen: app.py, .spec, CHAY_PHAN_MEM.bat, DONG_GOI_EXE.bat, requirements.txt, HUONG_DAN.txt, Excel mẫu; bổ sung Word mẫu keyword và modules Python.
- Không gửi dữ liệu người khám trong ZIP. Bản Electron cũ đã được xóa theo yêu cầu dọn sạch của người dùng. Bản Python được phép đẩy lên GitHub để tải source mới.

## Tương thích Python hiện có — 26/10/2026

Người dùng đã có Python 3.15 64-bit. Bộ cài/chạy/build phải tự nhận runtime hiện có, không ép cài thêm 3.12; cập nhật pywin32/PyInstaller tương thích. Không xóa mẫu riêng hoặc gỡ Python hệ thống khi sửa môi trường.
