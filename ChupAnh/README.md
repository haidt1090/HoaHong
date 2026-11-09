# ChupAnh — Telegram Photo Print 1.2 cho Windows

Nhận ảnh bằng Bot hoặc tài khoản Telegram qua API, không auto click.
Hiển thị ảnh thu nhỏ, chọn nhiều ảnh để in hàng loạt, tự động in ảnh mới,
lưu kết nối và cài đặt in. Giấy A4/A5/A6, ảnh 3×4 hoặc 4×6 cm,
1–999 bản mỗi ảnh, chọn máy in Windows, xem trước và xuất PDF.

## Cài đặt / nâng cấp
1. Cài Python 3.11+ từ python.org, chọn Add Python to PATH.
2. Thoát hẳn bản cũ; chỉ chạy một ứng dụng nhận cùng một bot.
3. Giải nén toàn bộ gói mới vào thư mục có quyền ghi.
4. Chạy `CAI_DAT.bat` một lần, kể cả khi nâng cấp (bản mới dùng thêm keyring).
5. Chạy `MO_UNG_DUNG.bat`. Tiêu đề phải có số **1.2**.
6. Cài driver máy in thật trên Windows trước khi in ra giấy. OneNote và các máy in PDF
   là máy in ảo, có thể mở hộp thoại riêng của driver.

## Kết nối Bot
1. Tạo bot ở @BotFather, lấy token và nhập vào ứng dụng. Không gửi token vào chat hỗ trợ.
2. Thêm bot vào nhóm. Để nhận ảnh thường do thành viên gửi, cấp quyền quản trị phù hợp
   hoặc tắt Group Privacy qua `/setprivacy` ở @BotFather. Sau khi đổi privacy, có thể cần gỡ và thêm lại bot.
3. Bấm **Kết nối Telegram → Bot Telegram**, nhập token, bấm **Kết nối**.
4. Gửi một tin nhắn trong nhóm để nhóm xuất hiện; chọn đúng tên và ID rồi bấm **Nhận ảnh từ nhóm**.
5. Bật **Tự kết nối khi mở phần mềm**, bấm **Lưu kết nối**.
6. Đóng cửa sổ cấu hình bằng X: bot vẫn tiếp tục nhận ảnh trong ứng dụng chính.
   **Ngắt kết nối** hoặc thoát hẳn ứng dụng mới dừng nhận.

Bot API không có lệnh liệt kê toàn bộ nhóm: danh sách được phát hiện từ cập nhật.
Bot không nhận tin nhắn từ bot khác. Bản này không lấy lịch sử toàn nhóm.
Nhớ vị trí cập nhật của bot để khi mở lại nhận các cập nhật còn được Telegram giữ lại,
thường tối đa 24 giờ. Nếu đã lưu tự động in, những ảnh nhận bù đó cũng được tự gửi in.
Không chạy hai chương trình getUpdates cho cùng token và không dùng webhook đồng thời.
Ứng dụng báo rõ lỗi token, quyền truy cập và xung đột; không tự xóa webhook của dịch vụ khác.
Bot tải ảnh và tệp JPEG/PNG/WebP/BMP tối đa 20 MB theo giới hạn Bot API tiêu chuẩn.

## Kết nối tài khoản
1. Lấy API ID và API Hash tại https://my.telegram.org → API development tools.
2. Chọn **Tài khoản Telegram**, nhập ID/Hash rồi **Kết nối**.
3. Nhập số điện thoại quốc tế (+84…, bỏ số 0 đầu), mã Telegram gửi và mật khẩu hai bước nếu có.
4. Chọn nhóm đang tham gia, bấm **Nhận ảnh từ nhóm** rồi **Lưu kết nối**.

Phiên đăng nhập được giữ trên máy. Nhận ảnh mới sau khi chọn nhóm; chưa có nút tải lịch sử
hoặc bù ảnh tài khoản bị lỡ lúc ứng dụng tắt. Hỗ trợ ảnh/tệp JPEG/PNG/WebP/BMP tối đa 50 MB.
Một nguồn Telegram kết nối tại một thời điểm; ngắt trước khi đổi nguồn.
Ứng dụng đọc và tải ảnh, không gửi tin nhắn vào nhóm.

## Chọn ảnh, xem trước và in hàng loạt
- Mỗi ảnh hiển thị thành một ô thu nhỏ; rê chuột để xem đường dẫn đầy đủ.
- Tích ô các ảnh cần in. Có **Chọn tất cả**, **Bỏ chọn** và bộ đếm ảnh đã chọn.
- Nếu chưa tích ô nào, có thể dùng Ctrl/Shift để chọn nhiều ảnh. Khi có ảnh tích ô,
  danh sách tích ô được dùng để in, ưu tiên hơn vùng bôi chọn.
- Chọn **Số bản / mỗi ảnh**: ví dụ chọn 3 ảnh và số bản 4 là in tổng cộng 12 ảnh.
- **Xem trước ảnh đã chọn**, **In ảnh đã chọn**, **Xuất PDF ảnh đã chọn** đều áp dụng cho lô đã chọn.
- Các ảnh được ghép liên tiếp trên cùng khổ giấy để dùng hết chỗ; tự chia trang khi đầy.
- Ảnh mới đến không làm thay đổi lô bạn đang chọn thủ công.
- Thư viện ghi nhớ các ảnh đã nhận; mở lại vẫn hiển thị ảnh nếu tệp gốc còn trên máy.

## Tự động in và lưu cài đặt
1. Chọn máy in thật, khổ giấy, kích thước và số bản mỗi ảnh; in thử để kiểm tra.
2. Bật **Tự động in ảnh MỚI**. Ảnh mới từ Telegram, thư mục theo dõi hoặc nút **Thêm ảnh**
   sẽ được gửi vào hàng đợi in ngay, không cần bấm In ảnh đã chọn hay xác nhận từng ảnh.
3. Bấm **Lưu cài đặt** ở cửa sổ chính để nhớ máy in, khổ giấy, kích thước, số bản,
   thư mục, đọc thư mục con và trạng thái tự động in cho lần mở tiếp theo.
4. **Lưu kết nối** trong cửa sổ Telegram là nút riêng, nhớ bot/tài khoản và nhóm.
   Muốn mở lại tự nhận và tự in, cần lưu cả hai loại cài đặt.

Bật tự động không in lại thư viện cũ hoặc ảnh đã có sẵn trong thư mục.
Thay đổi thông số chỉ tác động đến tác vụ tiếp theo; tác vụ đã xếp hàng giữ cấu hình lúc nhận.
Tắt tự động sẽ bỏ các tác vụ tự động chưa bắt đầu; tác vụ đã gửi máy in phải hủy ở hàng đợi Windows.
Nếu máy in đã lưu không còn khả dụng, chọn lại máy in trước khi bật tự động.

Lề 7 mm, khoảng cách 3 mm. Giữ toàn bộ ảnh, không cắt; có thể có viền trắng nếu khác tỷ lệ khung.
Driver có thể co giãn hoặc thay khổ; kiểm tra bằng thước trên bản in thử.
Chống tải trùng theo tài khoản/nhóm/tin nhắn, chống tự in trùng theo SHA-256 của nội dung.
In tay vẫn có thể in lại theo hộp xác nhận. Gửi máy in chưa có nghĩa giấy đã ra.
Lỗi in sẽ dừng tự động, đánh dấu cần kiểm tra và không tự in lại để tránh ra giấy hai lần.

## Thư mục ảnh bổ sung
Chọn thư mục ảnh thường trên Windows, tùy chọn đọc thư mục con.
Chờ tệp ổn định trước khi nhận, bỏ qua tệp tải dở; ảnh có sẵn chỉ vào thư viện.
Có thể để thư mục mặc định trống nếu chỉ dùng Telegram.

## Dữ liệu và bảo mật
Dữ liệu ở `%LOCALAPPDATA%\TelegramPhotoPrint`:
- `telegram-images`: ảnh tải theo chế độ, tài khoản, nhóm.
- `telegram-account.session`: phiên tài khoản; cần giữ riêng như thông tin đăng nhập.
- `telegram.sqlite`: lịch sử tải và vị trí cập nhật bot.
- `history.sqlite`: thư viện và lịch sử gửi in.
- `settings.json`: cài đặt in; `telegram-connection.json`: lựa chọn nhóm và tham chiếu thông tin đăng nhập.

Token/API Hash lưu trong Windows Credential Manager qua keyring khi bấm Lưu kết nối,
không ghi dạng văn bản trong cấu hình. Không lưu mã đăng nhập hoặc mật khẩu hai bước.
Dùng **Quên kết nối** để xóa thông tin đã lưu, **Ngắt kết nối** để dừng nguồn hiện tại.
Đổi tài khoản cá nhân: ngắt, thoát ứng dụng, xóa `telegram-account.session` và tệp phụ nếu có,
sau đó đăng nhập lại. Có thể thu hồi phiên tại Telegram → Settings → Devices.

Ứng dụng cần mở và có mạng để nhận trực tiếp; không chạy ngầm sau khi thoát hẳn.
Bot tự thử lại lỗi mạng; tài khoản dùng khả năng kết nối lại của Telethon.

## Kiểm tra
Chạy `.venv\Scripts\python -m unittest discover -v`.
Có kiểm tra tự động cho lưu/khôi phục kết nối, đóng cửa sổ vẫn nhận ảnh, lọc nhóm,
chống trùng, tự in không hỏi xác nhận, in nhiều ảnh, lưu cài đặt, thư viện,
bố trí kích thước và kết xuất PDF bằng luồng in thực.
Chưa kiểm chứng bằng bot/tài khoản và máy in Windows thật trong môi trường phát triển.
Đây là mã nguồn Python kèm tệp .bat, chưa phải bộ cài .exe.
