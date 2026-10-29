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

## Kiểm tra lại bộ chạy — 29/10/2026

Sửa nhận Python 3.15 và `py -3`; giữ cửa sổ lỗi, lưu stdout/stderr của tiến trình con vào log khởi động và giữ đúng mã lỗi. Kiểm tra thư viện mở giao diện không còn bắt import pywinauto trước khi dùng chế độ PIN tự động. Thêm `app.py --smoke-test` để mở/đóng giao diện mà không truy cập Chrome hoặc USB.

Đã chạy **75 test, tất cả đạt, không skip**, gồm GUI thật trên Xvfb, browser localhost và 6 test bộ chạy/log. Đã chạy riêng `app.py --smoke-test` thành công. Đã tải/phân giải wheel Windows CPython 3.15 cho Selenium, pywinauto, PyInstaller và riêng pywin32 312, comtypes 1.4.17, pefile. Pip trên Linux dùng marker của máy chạy nên kiểm tra các dependency Windows được làm riêng; điều này không xác nhận chúng đã chạy trên Windows.

Workflow Windows đã bổ sung việc gọi trực tiếp `CaiDat.cmd` và `CHAY_PHAN_MEM.bat --smoke-test` cho Python 3.12/3.15. Chưa có kết quả workflow này trong phiên sửa. Chưa xác định nguyên nhân cụ thể trên máy người dùng khi chưa nhận được lỗi/phiên bản Python; việc bản cũ từ chối Python 3.15 chỉ gây lỗi nếu máy dùng phiên bản đó.

## Sửa kiểm tra cổng Chrome — 29/10/2026

Ảnh lỗi người dùng xác nhận giao diện mở được nhưng thất bại ở socket probe trước khi mở Chrome. Bản cũ chỉ coi ConnectionRefusedError là cổng trống; TimeoutError/WinError 10060 bị báo lỗi chung. Bản sửa kiểm tra quyền sở hữu cổng bằng exclusive bind trên Windows khi probe timeout; chỉ mở Chrome nếu cổng trống. Cổng bị chiếm không được coi là trống. Nếu bị chặn hoặc dành riêng, thông báo giữ mã Windows (ví dụ 10013) để chẩn đoán. Endpoint HTTP đang khởi động được chờ thay vì kết luận nhầm ứng dụng khác.

82 test đã chạy, tất cả đạt, không skip: thêm các trường hợp timeout, Winsock 10060/10013/10048, endpoint HTTP chưa sẵn sàng, socket trống thật và HTTP localhost thật. Chưa tái hiện trên Windows của người dùng; cần thử lại bản sửa để xác nhận timeout hay quyền truy cập là nguyên nhân cụ thể. Không thay cấu hình tường lửa và không chiếm cổng đang có dịch vụ.

## Sửa nút Kết nối Chrome — 29/10/2026

Đã tái hiện bằng ChromeDriver 156: `InvalidArgumentException: cannot parse capability: goog:chromeOptions / unrecognized chrome option: detach` khi gửi cả debuggerAddress và detach như bản cũ. Bỏ detach khỏi chế độ attach.

Bộ smoke test trước dùng driver truyền sẵn nên đã bỏ qua nhánh tạo driver trong ứng dụng và không phát hiện lỗi này. Smoke test hiện đi qua chính ChromeSession.connect() và factory của ứng dụng, đọc endpoint phiên bản Chrome thật, chọn driver cục bộ, kết nối vào Chrome đang chạy, quét fixture và thực hiện đủ chuỗi nút. Chạy cả với HTTP_PROXY/HTTPS_PROXY cố tình trỏ tới proxy localhost không hoạt động: kết nối WebDriver vẫn đạt và biến môi trường vẫn nguyên. Đã xác minh disconnect giữ Chrome và cả ba tab qua phiên driver bên ngoài.

90 test chạy đầy đủ, tất cả đạt, không skip. Thêm 8 test chọn driver, giữ lỗi gốc, bỏ detach và xử lý proxy cục bộ. Đã chạy lại riêng smoke test sau khi thêm kiểm tra Chrome vẫn mở sau disconnect. Bản sửa chưa chạy trên máy Windows người dùng; việc ký thật/API thật/USB vẫn chưa kiểm chứng.
