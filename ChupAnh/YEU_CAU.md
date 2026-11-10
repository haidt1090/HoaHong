# TỔNG HỢP YÊU CẦU — CHUPANH 1.6 RIÊNG

## Thông tin nhà phát triển
PHÒNG KHÁM ĐA KHOA Y CAO HOA HỒNG
CÔNG TY TNHH DỊCH VỤ VÀ Y TẾ HUỆ LINH

## 1. Nguồn nhận ảnh
- Chuyển từ phương án Zalo sang Telegram qua API, không dùng auto click.
- Có chế độ bot và tài khoản Telegram cá nhân được cấp phép.
- Bản riêng có sẵn token bot và nhóm ChupAnh trong private_defaults.py.
- Token mặc định đã được kiểm tra với Telegram, bot đọc được nhóm ChupAnh.
- Token, username bot, tên nhóm và ID nhóm có thể sửa trong cửa sổ Kết nối Telegram.
- Sửa kết nối sẽ ngắt nguồn hiện tại rồi cho sửa; kết nối lại và lưu.
- Cấu hình riêng áp dụng một lần khi mở phiên bản này; các chỉnh sửa lưu sau đó được ưu tiên.
- Thông tin nhạy cảm lưu trong Windows Credential Manager; bản source riêng vẫn chứa token theo yêu cầu chủ sở hữu.
- Không đưa bản source riêng hay token lên GitHub. Không tự build EXE.
- Mỗi tin nhắn Telegram mới là một lượt: gửi lại cùng ảnh vẫn thêm ảnh/lệnh mới.
- Cùng một tin nhắn nhận lại do kết nối lại không tạo trùng.

## 2. Giao diện và thư viện ảnh
- Thông tin đơn vị và nút ? cùng một hàng trên cùng, tiết kiệm chiều cao.
- Có thanh kéo đổi kích thước khung ảnh và tiến độ, lưu tỷ lệ bằng Lưu cài đặt.
- Hiển thị ảnh thu nhỏ; ảnh mới ở đầu. Giữ tối đa 100 lượt ảnh trong khung.
- Chọn nhiều ảnh, chọn tất cả, bỏ chọn; xóa ảnh đã chọn hoặc làm trống khung.
- Xóa khỏi khung không xóa file ảnh và không hủy lệnh in.

## 3. In và lưu cài đặt
- Chọn máy in Windows; giấy A4/A5/A6; ảnh 3×4 hoặc 4×6 cm; 1–999 bản mỗi ảnh.
- In nhiều ảnh chung giấy, tự chia trang.
- In tay và hotkey gửi in ngay, không hỏi Yes/No; PDF vẫn chọn nơi lưu.
- Tự động in ảnh mới không cần bấm nút In ảnh đã chọn.
- Lưu cài đặt nhớ trạng thái Tự động in, máy in, giấy, kích thước, số bản,
  thư mục, bố trí/khoảng cách, mẫu đang dùng và tỷ lệ hai khung.
- Nếu kết nối đã sẵn sàng, Lưu cài đặt cũng lưu bot và nhóm hiện tại.
- Chọn lại nhóm/kết nối không tự bỏ dấu Tự động in; Ngắt kết nối chủ động có thể tắt in tự động.
- Ảnh cũ trong thư viện không tự in lại chỉ vì mở lại ứng dụng.

## 4. Xem trước và format in
- Nút Xem trước ảnh đã chọn mở trình chỉnh mẫu.
- Sửa khổ giấy, kích thước, số bản, lề, khoảng cách ngang và dọc (mm).
- Khoảng cách dương = xa nhau; 0 = sát; âm = chồng ảnh.
- Thấy ngay ảnh và số trang thay đổi; cách xếp dùng chung với in thật và PDF.
- Đặt tên và Lưu mẫu; chọn lại mẫu đã lưu để chỉnh tiếp.
- Áp dụng và lưu cài đặt để dùng mẫu cho in tay, tự động và PDF.
- Có thể in ngay từ cửa sổ chỉnh mẫu.

## 5. Tiến độ và điều khiển hàng đợi
- Bỏ vùng thông báo/tiến độ lớn phía trên bảng, giữ thông tin ở các cột.
- Dòng mới ở đầu; hiển thị tên ảnh, số bản xử lý, trạng thái và đích.
- Tạm dừng/tiếp tục; hủy đúng lệnh trong Windows Print Spooler, không auto click.
- Máy Offline hoặc lệnh còn trong queue = chưa hoàn tất.
- Không coi lỗi đọc queue là đã in xong. Windows không luôn xác nhận được giấy thực sự ra.
- Xóa tất cả tiến độ chỉ xóa lịch sử đã kết thúc; giữ lệnh đang chờ/in và dữ liệu chống trùng.

## 6. Hotkey
- Alt+1 … Alt+9: ảnh mới nhất theo vị trí 1 … 9.
- Alt+A: chỉ các ảnh mới chưa gửi in.
- F1 / ?: hướng dẫn; thêm tab Yêu cầu có thể sửa và lưu ghi chú trên máy.
- Phím tắt hoạt động ở cửa sổ chính; không đổi các ảnh đang tích.

## 7. Môi trường và đóng gói
- Windows 10/11 x64, Python 3.12 x64; toàn bộ thư viện trong requirements.txt.
- CAI_DAT.bat và DONG_GOI.bat cùng cài đầy đủ thư viện chạy và build.
- Dùng wheel zstandard để không tự biên dịch thư viện này bằng Visual C++.
- Khi test xong, chủ sở hữu tự chạy DONG_GOI.bat để biên dịch native bằng Nuitka.
- Bảo vệ cơ bản, không chống đảo ngược tuyệt đối. Bản đóng gói riêng chứa thông tin bot mặc định.

## Ghi chú bổ sung của người dùng
Bạn có thể sửa nội dung này trong tab Yêu cầu rồi bấm Lưu nội dung yêu cầu.
Ghi chú không tự sửa chức năng hoặc mã nguồn; các yêu cầu mới vẫn cần được triển khai.
