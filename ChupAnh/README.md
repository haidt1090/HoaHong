# Telegram Photo Print — Windows, Python 3.11+

Chọn nguồn Bot hoặc Tài khoản Telegram, chọn nhóm và nhận ảnh mới bằng API.
Chạy nền khi ứng dụng mở, không auto click, không cần mở Telegram Desktop.
In tay/tự động, máy in Windows, giấy A4/A5/A6, ảnh 3×4 hoặc 4×6 cm,
số lượng mỗi tệp 1–999, xem trước, xuất PDF, tự chia trang.

## Cài đặt
1. Cài Python 3.11+ từ python.org, chọn Add Python to PATH.
2. Giải nén toàn bộ vào một thư mục có quyền ghi.
3. Chạy `CAI_DAT.bat` một lần (cần Internet).
4. Chạy `MO_UNG_DUNG.bat`.
5. Cài driver máy in Windows, chọn máy in và các thông số.
6. Bấm **Kết nối Telegram**, chọn một trong hai chế độ dưới đây.

## Bot
1. Tạo bot ở @BotFather, lấy token và nhập vào ứng dụng. Không gửi token vào chat hỗ trợ.
2. Thêm bot vào nhóm. Để nhận ảnh thông thường của thành viên, cấp quyền quản trị phù hợp
   hoặc dùng /setprivacy trong @BotFather để tắt Group Privacy (có thể cần thêm lại bot sau khi đổi).
3. Bấm Kết nối. Gửi một tin nhắn mới vào nhóm để nhóm xuất hiện trong danh sách.
4. Chọn đúng tên và ID nhóm, bấm **Nhận ảnh từ nhóm**. Gửi ảnh mới để thử.

Bot API không có lệnh liệt kê toàn bộ nhóm bot đang tham gia: danh sách được phát hiện từ cập nhật nhận được.
Bot không đọc lịch sử trước khi tham gia, không nhận ảnh do bot khác gửi.
Không chạy hai bộ nhận getUpdates cho cùng một token hoặc dùng webhook đồng thời.
Ứng dụng không tự xóa webhook; nếu bot đang dùng dịch vụ khác, tạo bot riêng.
Giới hạn tải mặc định Bot API: 20 MB mỗi tệp. Nhận ảnh và tệp đính kèm JPEG/PNG/WebP/BMP.

## Tài khoản Telegram
1. Vào https://my.telegram.org, mục API development tools để lấy API ID và API Hash.
2. Chọn Tài khoản Telegram, nhập API ID và Hash, bấm Kết nối.
3. Nhập số điện thoại quốc tế, ví dụ +84… (bỏ số 0 đầu), bấm Gửi số điện thoại.
4. Nhập mã Telegram gửi cho bạn, bấm Xác nhận mã. Telegram có thể gửi mã trong ứng dụng thay vì SMS.
5. Nếu có xác thực hai bước, nhập mật khẩu theo yêu cầu.
6. Chọn nhóm trong danh sách nhóm bạn đang tham gia, bấm Nhận ảnh từ nhóm.

Phiên đăng nhập được giữ trên máy để lần sau không cần nhập mã.
Bản này nhận ảnh mới sau khi chọn nhóm, CHƯA có nút tải lịch sử.
Nhận ảnh và tệp JPEG/PNG/WebP/BMP tối đa 50 MB. Kết nối chỉ đọc và tải ảnh; không gửi tin nhắn.
Chỉ có một kết nối nguồn Telegram tại một thời điểm. Ngắt kết nối để đổi bot/tài khoản.

## In
- Ảnh xuất hiện trong danh sách. Chọn một dòng, xem trước/xuất PDF hoặc In ảnh đã chọn.
- Thử in một ảnh và đo bằng thước trước khi bật tự động.
- Mặc định tự động tắt. Bật sau khi kiểm tra đúng nhóm và cấu hình máy in.
- Khi chọn nhóm hoặc kết nối/ngắt nguồn, tự động in tắt; kiểm tra rồi bật lại nếu cần.
- Số lượng là số bản của MỖI ảnh, không phải số tờ giấy.
- Lề 7 mm, khoảng cách 3 mm; giữ toàn bộ ảnh, không cắt, có viền trắng nếu khác tỷ lệ khung.
- Chống tải trùng theo tài khoản/nhóm/tin nhắn; chống tự in trùng theo SHA-256 của nội dung ảnh.
- Đã gửi máy in chưa có nghĩa giấy đã ra. Tác vụ lỗi/không rõ kết quả không tự in lại.
  Kiểm tra hàng đợi Windows trước khi in lại bằng tay. Tắt tự động không hủy lệnh đã gửi.
- Thư mục ảnh bổ sung vẫn được theo dõi riêng. Chọn thư mục trống nếu chỉ muốn dùng Telegram.

## Dữ liệu và phiên đăng nhập
Dữ liệu ở `%LOCALAPPDATA%\TelegramPhotoPrint`:
- `telegram-images`: ảnh theo chế độ, tài khoản, nhóm.
- `telegram-account.session`: phiên tài khoản, cần giữ riêng như thông tin đăng nhập.
- `telegram.sqlite`: lịch sử tải; `history.sqlite`: lịch sử gửi in.
- Token, API Hash, mã và mật khẩu không được ghi trong cấu hình của ứng dụng.
Không chia sẻ thư mục dữ liệu. Để đổi tài khoản: ngắt và đóng ứng dụng, xóa phiên
`telegram-account.session` cùng tệp phụ nếu có, sau đó mở lại và đăng nhập tài khoản khác.
Có thể thu hồi phiên từ Telegram → Settings → Devices.

Đóng cửa sổ kết nối khi đang chạy sẽ ngắt rồi tự đóng sau khi kết nối dừng.
Khi mất mạng bot tự thử lại; tài khoản phụ thuộc khả năng kết nối lại của Telethon.
Bản này chưa có cơ chế tự bù mọi ảnh bị lỡ khi ứng dụng tắt hoặc tải lỗi.

## Kiểm tra và giới hạn
Kiểm tra tự động: lọc ảnh/tệp, chỉ tải nhóm đã chọn, chống trùng,
đọc thư mục, bố trí đúng kích thước và chia trang. Có kiểm tra GUI và xuất PDF không cần máy in.
Chưa xác minh bằng bot, tài khoản Telegram và máy in Windows thật trong môi trường phát triển.
Chạy `.venv\Scripts\python -m unittest discover -v` để chạy kiểm tra.
Đây là gói mã nguồn Python, chưa phải bộ cài .exe.
