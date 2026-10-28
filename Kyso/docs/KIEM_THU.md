# Kiểm thử bản 0.1.0

Ngày kiểm tra: 28/10/2026. Mã nguồn được kiểm tra trong môi trường Linux, Python 3.12.14.

**69 kiểm thử đã chạy và đạt, không bỏ qua trong lần kiểm tra đầy đủ.**

- 30 kiểm thử bộ điều khiển browser: API/phân trang, phiên đăng nhập, origin, redirect, nút trùng, timeout, giữ tab và ngắt driver.
- 8 kiểm thử giao diện Tkinter thật trên Xvfb: nút nằm trong cửa sổ tối thiểu, chọn hồ sơ, hủy xác nhận, lưu cài đặt, xóa PIN/danh sách sau lô và đóng giao diện.
- 7 kiểm thử lưu cấu hình: ghi nguyên tử, dữ liệu lỗi, trường không được hỗ trợ, không lưu PIN.
- 14 kiểm thử Windows dùng bộ giả lập: kho chứng thư, Chrome, nhận diện hộp thoại, gửi PIN đúng một lần, dừng khi không rõ trạng thái.
- 9 kiểm thử workflow: đúng thứ tự nút, chỉ xử lý danh sách chọn, dừng giữa hồ sơ, không thử lại khi lỗi, không khẳng định đã ký thành công.
- 1 smoke test dùng Chromium/ChromeDriver 156 thật và HTTP server loopback chứa dữ liệu giả. Test quét hai trang, thực hiện đầy đủ chuỗi nút trên hai hồ sơ giả, xác minh server giả nhận hai yêu cầu Complete và các tab được giữ mở. Chỉ trong bài test này, kiểm tra origin được thay bằng bộ kiểm tra HTTP đúng cổng loopback của fixture; ứng dụng thật vẫn yêu cầu HTTPS.

`pip check` đạt. Đã mở/chụp giao diện minh họa tiếng Việt bằng Tk 8.6; bộ kiểm thử GUI chạy bằng Tk 9.0 của runtime.

## Chạy lại

Bộ test thông thường:

```sh
python -m unittest discover -s tests -v
```

Mặc định bỏ qua 8 test GUI nếu chưa bật `KYSO_GUI_TESTS=1`, và bỏ qua smoke test browser nếu chưa bật `KYSO_BROWSER_SMOKE=1`. Đây là test tùy chọn có yêu cầu runtime, không phải kết quả đạt khi bị bỏ qua.

Bật GUI trên Windows desktop bằng PowerShell:

```powershell
$env:KYSO_GUI_TESTS = '1'
.venv\Scripts\python -m unittest discover -s tests -v
```

Smoke test browser chạy trên Linux có Chromium/ChromeDriver cùng phiên bản; đặt `KYSO_BROWSER_SMOKE=1`, `KYSO_CHROMIUM_BINARY` và `KYSO_CHROMEDRIVER` trỏ đến các binary cục bộ, rồi chạy `test_local_smoke.py`. Test này không truy cập website thật.

## Chưa kiểm chứng

Chưa đăng nhập hoặc gọi API của admin.csdlksk.vn, chưa thao tác USB Token thật, chưa chạy UI Automation Windows thật, chưa build/chạy EXE Windows. Không có tài khoản, PIN hoặc hồ sơ thật được dùng để kiểm tra. Selector và API dựa vào bản EXE người dùng cung cấp, có thể khác phiên bản website hiện tại.

Để nghiệm thu trên máy ký: cài driver USB, mở Chrome/đăng nhập, quét danh sách, thử một hồ sơ bằng chế độ PIN thủ công, kiểm tra chữ ký và trạng thái trên website. Sau đó mới thử chế độ tự nhập PIN nếu hộp thoại tương thích. Khi gặp lỗi, giữ nguyên tab và kiểm tra trạng thái trước khi thử lại; không tự động ký lại hồ sơ chưa rõ kết quả.
