# ChupAnh 1.6 — Telegram Photo Print

Bản công khai không chứa token bot. Nhập token trong Kết nối Telegram và lưu trên máy.
Bot mặc định @pkhoahongbot; nhóm ChupAnh, ID -5313722195.

## Chạy
1. Dùng Windows 10/11 x64 và Python 3.12 x64.
2. Thoát bản cũ. Giải nén toàn bộ, chạy CAI_DAT.bat rồi MO_UNG_DUNG.bat.
3. Mở Kết nối Telegram, nhập token rồi chọn nhóm ChupAnh hoặc nhập ID -5313722195. Lưu kết nối để tự khôi phục lần sau.
4. Cài đặt trước đây ở LOCALAPPDATA vẫn được giữ. Các thay đổi kết nối được lưu trên máy.

## Chỉnh bot và nhóm
Bấm Kết nối Telegram → Sửa kết nối. Sửa token/username, Kết nối lại;
chọn nhóm đã phát hiện hoặc nhập ID nhóm (số âm), tên nhóm → Nhận ảnh từ nhóm.
Bấm Lưu kết nối hoặc Lưu cài đặt khi nguồn đã sẵn sàng. Token lưu trong Windows Credential Manager.
Tên nhóm chỉ để hiển thị; ID nhóm xác định nơi nhận ảnh. Token được kiểm tra với username bot đang chọn.
Tài khoản cá nhân vẫn kiểm tra quyền bằng dấu kiểm tra một chiều, không ghi số gốc trong source.

## Tự động in và Lưu cài đặt
Chọn máy in, giấy, ảnh, số bản; bật Tự động in nếu muốn, bấm Lưu cài đặt.
Lần mở lại khôi phục trạng thái đó cùng máy in, mẫu bố trí và bot/nhóm đã lưu.
Đổi nhóm không tự bỏ dấu tự động. Kiểm tra đúng nhóm trước khi gửi ảnh cần in.
Ngắt kết nối chủ động tắt tự động; Sửa kết nối giữ lại lựa chọn để bạn tiếp tục sau khi đổi.

## Chỉnh khoảng cách, chồng ảnh và lưu format
Chọn ảnh → Xem trước ảnh đã chọn. Có thể sửa giấy, kích thước, số bản, lề,
khoảng cách ngang/dọc (mm). Dương là xa nhau, 0 là sát, âm là chồng ảnh.
Xem trang bằng ô Trang; đặt tên rồi Lưu mẫu. Áp dụng và lưu cài đặt dùng mẫu cho in tay,
tự động và PDF. Có thể in ngay từ trình chỉnh mẫu. Các tác vụ đã xếp hàng giữ mẫu lúc tạo.
Mẫu lưu tại `%LOCALAPPDATA%\TelegramPhotoPrint\print-formats.json`.

## Tổng hợp và sửa ghi chú yêu cầu
Bấm ? / F1 → tab Yêu cầu. Nội dung ban đầu từ YEU_CAU.md trong gói source.
Có thể sửa và Lưu nội dung yêu cầu; bản sửa riêng lưu tại LOCALAPPDATA.
Nội dung ghi chú không tự làm thay đổi chức năng phần mềm.

## Các chức năng đã có
Ảnh mới ở đầu, tối đa 100 lượt ảnh; nhận lại cùng ảnh bằng tin nhắn mới vẫn thêm lượt.
Alt+1…9 in theo vị trí; Alt+A chỉ ảnh chưa gửi in. In tay không hỏi Yes/No.
Chọn nhiều ảnh; xem trước/PDF; giấy A4/A5/A6; ảnh 3×4/4×6 cm; 1–999 bản mỗi ảnh.
Thanh kéo giữa hai khung; xóa ảnh không xóa file. Tiến độ theo Windows, Offline chưa hoàn tất.
Pause/resume/cancel đúng mã lệnh; xóa tiến độ chỉ xóa lịch sử kết thúc.
Bản này nhận ảnh mới, chưa có nút lấy toàn bộ lịch sử Telegram.

## Đóng gói thủ công
Khi test xong mới tự chạy DONG_GOI.bat. Cấu hình mặc định trong private_defaults.py không chứa token;
Nuitka làm khó trích mã hơn, không bảo vệ tuyệt đối.
Không tự tạo EXE khi chạy/cài. Quy trình đóng gói được chạy thủ công.

## Kiểm tra offline
Trong CMD: `set CHUPANH_OFFLINE_TEST=1`, sau đó `.venv\Scripts\python -m unittest discover -v`.
Cờ này ngăn kết nối bot thật khi kiểm tra. Không đặt cờ này khi chạy để nhận ảnh thực tế.
