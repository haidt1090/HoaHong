# KySoPython

## Chế độ kiểm tra hiện tại: đọc thử 5 hồ sơ từ Phiếu khám

Theo màn hình thực tế, luồng cần đối chiếu là **Phiếu khám → Hành động → Ký nhiều file**. Nút **Quét thử 5 hồ sơ** mở **Hành động → Ký nhiều file** nếu cần, rồi đọc tối đa 5 dòng có checkbox khả dụng và trạng thái **Chưa ký số** trên trang hiện tại của cửa sổ chọn phiếu. Không gọi API cũ, không chuyển trang, không mở trang chi tiết và không gửi lệnh ký. Chọn đúng tab Phiếu khám trong Chrome trước khi quét. Nếu không có bảng phù hợp, tool báo lỗi thay vì dùng API thay thế. Dùng STT và thông tin hiển thị để đối chiếu, không suy đoán mã hồ sơ từ STT hoặc số định danh đã che.

Trạng thái các dòng đọc thử lấy từ cột **Trạng thái** của cửa sổ; đây chưa phải xác minh chữ ký. Chưa tự tích checkbox, bấm **Chọn phiếu**, **Ký số** hoặc đặt chữ ký trên PDF. Nút ký cho các dòng đọc thử và ký liên tục 100 tạm dừng trong giao diện trong lúc đối chiếu luồng thực tế. Phần hướng dẫn ký dưới đây mô tả luồng cũ, chưa xác minh phù hợp với màn hình mới.

**Cảnh báo phân phối:** ZIP tại commit `499470d` bị Windows Defender phát hiện `Trojan:Script/Sabsik.FL.A!ml`. Chưa có kết luận phân tích độc lập. Thay đổi bước quét không giải quyết cảnh báo này; không tắt Defender hoặc khôi phục file bị chặn để thử bản sửa. Chưa tạo ZIP thay thế hoặc xác nhận bản mới sạch.

Ứng dụng desktop Python/Tkinter hỗ trợ ký hồ sơ trên **https://admin.csdlksk.vn** theo thứ tự thao tác của tool gốc: mở hồ sơ → mở PDF → chọn chữ ký → tạo chữ ký mới → Save signature → Sign with USB Token → xử lý chứng thư/PIN → chờ Complete → gửi Complete.

Bản này có mã nguồn, bộ chạy và cấu hình đóng gói EXE. Phần ký trên website thật, hộp thoại USB Token và EXE **chưa được kiểm chứng trên máy Windows có USB ký số**. Selector của website hoặc hộp thoại nhà cung cấp có thể cần điều chỉnh sau lần thử thực tế. Chỉ dùng hồ sơ đã kiểm tra và bạn có quyền ký; nên thử một hồ sơ trước khi chạy một danh sách.

## Cài và mở trên Windows

Cần Windows 10/11, Google Chrome, Python **64-bit 3.10–3.15 có Tcl/Tk**, driver USB Token và chứng thư còn hiệu lực. Máy ký phải đăng nhập được hệ thống bằng tài khoản có quyền ký. USB phải đang cắm và chứng thư có private key phải xuất hiện trong kho chứng thư Windows.

1. Giải nén toàn bộ mã nguồn vào một thư mục mới.
2. Chạy `CaiDat.cmd` một lần để tạo `.venv` và cài dependency.
3. Chạy `CHAY_PHAN_MEM.bat` để mở giao diện.

Bộ chạy tự tìm Python đang hoạt động và dùng `.venv` riêng; môi trường cũ không hợp lệ được đổi tên thành `.venv-backup-...`. Nếu cửa sổ lệnh đóng khi có lỗi, mở Terminal trong thư mục rồi chạy lại lệnh để xem thông báo. Không cần gỡ Python hiện có.

Cài/chạy bằng Terminal cũng được:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install --no-input -r requirements.txt
.venv\Scripts\python app.py
```

## Quy trình ký

1. Chọn **Mở Chrome**. Tool mở Chrome với profile riêng trong `%LOCALAPPDATA%\KySoPython\ChromeProfile`, chỉ bật cổng điều khiển tại `127.0.0.1:9222`.
2. Đăng nhập `admin.csdlksk.vn` thủ công trong cửa sổ Chrome đó và mở trang danh sách hồ sơ.
3. Kết nối Chrome, lấy danh sách chứng thư nếu cần, rồi **Quét hồ sơ**. Tool đọc API bằng phiên đăng nhập sẵn có trong Chrome, lấy tối đa 100 hồ sơ trạng thái `init` theo thứ tự API thành một danh sách cố định trước khi ký.
4. Chọn các hồ sơ cần ký. Giữ chế độ nhập PIN thủ công cho lần thử đầu. Khi có cửa sổ bảo mật, chọn đúng chứng thư và nhập PIN trên cửa sổ của USB Token; tool đợi nút Complete sẵn sàng.
5. Kiểm tra số hồ sơ, xác nhận bắt đầu ký. Nếu bật tự nhập PIN, chọn đúng chứng thư và nhập PIN vào ô trong tool trước khi bắt đầu.
6. Kiểm tra lại trạng thái hồ sơ trên hệ thống khi kết thúc. **Đã hoàn tất thao tác** chỉ xác nhận đã gửi click Complete, chưa xác nhận chữ ký đã được máy chủ ghi nhận.

### Ký liên tục từng đợt 100

Bấm **Ký liên tục từng đợt 100** và xác nhận để tự quét tối đa 100 hồ sơ chưa ký, ký lần lượt từng hồ sơ, rồi quét đợt tiếp theo. Nút này tự quét danh sách mới, không dùng lựa chọn đang hiển thị. Đợt cuối có thể ít hơn 100 hồ sơ. Đây là xử lý tuần tự, không mở 100 giao dịch USB Token đồng thời.

Mỗi lần quét lại bắt đầu từ trang 1 vì danh sách chưa ký thay đổi sau mỗi đợt. Trong cùng lần chạy liên tục, các mã đã thao tác được loại khỏi các lần quét sau, kể cả khi API vẫn trả trạng thái `init`. Tool dừng khi hết hồ sơ mới, gặp lỗi, phiên đăng nhập hết hạn hoặc bạn bấm **Dừng sau hồ sơ này**. Nó không tự thử lại hồ sơ gặp lỗi. PIN chỉ giữ trong bộ nhớ suốt lần chạy và được xóa khi kết thúc. Chế độ nhập PIN thủ công vẫn cần bạn xử lý hộp thoại của từng hồ sơ.

Thứ tự hiện theo API; chưa xác minh API sắp mới nhất trước và chưa có hợp đồng trường ngày tạo/tham số sắp xếp trong repository. Chỉ có thể coi đây là 100 hồ sơ mới nhất nếu API trả danh sách theo thứ tự đó. Luồng chia đợt đã được kiểm thử bằng dữ liệu giả 100 + 100 + 5 hồ sơ, chưa thử ký thật trên Windows/USB Token.

**Dừng** có hiệu lực trước hồ sơ kế tiếp. Hồ sơ đang ở bước ký có thể tiếp tục để tránh bỏ dở. Khi lỗi hoặc trạng thái không rõ, danh sách dừng để bạn kiểm tra; tool không tự gửi lại lệnh ký hoặc thử lại PIN.

Các tab hồ sơ được giữ mở để yêu cầu lưu/ký của website có thời gian hoàn tất và để bạn kiểm tra kết quả. Tool không tự đóng tab ngay sau khi gửi Complete; chạy nhiều đợt có thể giữ nhiều tab và tốn bộ nhớ Chrome. Với chế độ ký hồ sơ đã chọn, danh sách đã chọn bị xóa sau khi kết thúc; quét lại trước đợt tiếp theo. Với chế độ liên tục, tool tự quét giữa các đợt và xóa danh sách hiển thị khi lần chạy kết thúc. Không xử lý cùng các hồ sơ bằng tool khác trong lúc chạy.

Chế độ tự nhập PIN chỉ hỗ trợ các cửa sổ bảo mật/PIN đã nhận diện và chọn chứng thư khớp duy nhất. Nó gửi PIN một lần. Nếu nhà cung cấp USB dùng hộp thoại khác, hãy chuyển về nhập PIN thủ công; không tăng số lần thử vì USB có thể khóa sau nhiều lần nhập sai.

## Dữ liệu và kết nối

Cấu hình nằm tại `%LOCALAPPDATA%\KySoPython\settings.json`. Chỉ lưu địa chỉ Chrome, hệ thống và chứng thư/chế độ đã chọn; **PIN không được lưu vào cấu hình hoặc log**. PIN tự động chỉ giữ trong bộ nhớ khi chạy. Profile Chrome riêng có thể lưu phiên đăng nhập như Chrome thông thường; đăng xuất trên website khi cần xóa phiên.

Tool không lấy private key ra khỏi USB, không yêu cầu mật khẩu riêng để mở ứng dụng và không dùng dịch vụ cấp phép Firebase của bản gốc. Giao diện và bộ điều khiển Chrome cần chạy trong cùng phiên desktop Windows của người dùng. Không bật cổng Chrome ra mạng ngoài.

Cài dependency cần truy cập PyPI. Khi kết nối Chrome lần đầu, Selenium Manager có thể tải ChromeDriver tương thích từ nguồn chính thức của Google. Nếu mạng giới hạn, cho phép các đích Google được thông báo trong lỗi (thường `googlechromelabs.github.io`, `storage.googleapis.com`) hoặc cài ChromeDriver tương thích sẵn trên PATH. Giữ xác minh TLS; không dùng tham số bỏ kiểm tra chứng chỉ.

## Đóng gói EXE

Trên Windows, chạy `DONG_GOI_EXE.bat`. Script cài dependency build, chạy unit test rồi gọi PyInstaller. Kết quả dự kiến: `dist\KySoPython.exe`; máy nhận EXE vẫn cần Chrome và driver USB Token, không cần Python.

```powershell
.venv\Scripts\python -m pip install --no-input -r requirements-build.txt
.venv\Scripts\python -m unittest discover -s tests -v
.venv\Scripts\python -m PyInstaller --noconfirm --clean KySoPython.spec
```

Workflow `.github/workflows/kyso-windows.yml` có thể chạy thủ công trên GitHub Actions sau khi đẩy mã nguồn, tạo artifact `KySoPython-Windows`. Việc có file workflow chưa có nghĩa bản EXE đã được build hoặc đã được kiểm thử ký thật.

## Kiểm thử và cấu trúc

```sh
python -m unittest discover -s tests -v
```

Trên Windows có desktop, chạy thêm kiểm thử giao diện bằng PowerShell:

```powershell
$env:KYSO_GUI_TESTS = '1'
.venv\Scripts\python -m unittest discover -s tests -v
```

Kiểm thử GUI mở Tkinter thật với dữ liệu giả, kiểm tra các nút hiển thị, xác nhận lựa chọn, lưu cài đặt và xóa PIN sau phiên ký. Nó không tự ký hồ sơ thật.

Các test dùng bộ giả lập browser/hộp thoại để kiểm tra phân trang, danh sách cố định, quyền sở hữu tab, dừng khi lỗi, một lần nhập PIN và lưu cấu hình không chứa PIN. Chúng không truy cập hệ thống thật và không thay thế lần thử USB Token trên Windows.

- `app.py`, `kyso/gui.py`: giao diện Tkinter.
- `kyso/browser.py`: kết nối Chrome, API và thao tác website.
- `kyso/windows.py`: Chrome, kho chứng thư và UI Automation Windows.
- `kyso/workflow.py`: trình tự ký, dừng và thống kê.
- `kyso/settings.py`: cấu hình cục bộ.
- `scripts/windows_env.py`: cài, chạy và build trong môi trường Python riêng.

## Mở hồ sơ nhưng dừng ở form trống hoặc trước màn hình PDF

Tool chờ ô họ tên trên trang chi tiết có dữ liệu khớp tên lúc quét, sau đó bấm đúng **Ký phiếu khám**. Không dùng nút `submit` chung vì có thể bấm nhầm **Lưu thông tin** và kích hoạt lỗi bắt buộc nhập trên form. Nếu trang trống, sai người hoặc không có ô họ tên nhận diện được sau 30 giây, tool dừng trước khi mở ký. Kiểm tra đường dẫn hồ sơ, phiên đăng nhập và dữ liệu tải từ cổng; không nhập hoặc lưu dữ liệu giả để vượt qua lỗi.

## Nếu cài xong nhưng không mở được

Bản sửa bộ chạy nhận cả Python 3.15. Khi bị lỗi, cửa sổ lệnh được giữ mở và log nằm tại `%LOCALAPPDATA%\KySoPython\diagnostics\last-launch.log`. Gửi thông báo lỗi hoặc file log này để xác định nguyên nhân trên máy của bạn. Bộ chạy không lưu PIN trong log.

Tải ZIP mới và giải nén sang thư mục mới, chạy `CaiDat.cmd`, sau đó `CHAY_PHAN_MEM.bat`. Có thể kiểm tra riêng khả năng mở GUI bằng Terminal: `CHAY_PHAN_MEM.bat --smoke-test`; chế độ này tự đóng sau khi mở giao diện, không truy cập Chrome hoặc USB Token. Python cần bản 64-bit có Tcl/Tk; bộ chạy không ép gỡ Python đang dùng.

## Chrome mở được nhưng nút Kết nối báo lỗi

Bản sửa bỏ tùy chọn `detach` khi dùng `debuggerAddress`: ChromeDriver từ chối tùy chọn mở trình duyệt này trong chế độ kết nối vào Chrome đã chạy. Lỗi đã được tái hiện bằng Chromium/ChromeDriver 156 trước khi sửa.

Tool đọc phiên bản từ Chrome đang mở để chọn ChromeDriver, bỏ qua driver cũ khác major trên PATH. Kết nối điều khiển localhost đi trực tiếp; proxy của quá trình tải driver vẫn được giữ. Nếu mạng không tải được driver, thông báo nêu lỗi gốc và các đích Google cần truy cập. Có thể đặt ChromeDriver tương thích vào thư mục `drivers` cạnh `app.py` để dùng cục bộ.

Lỗi kết nối được hiện chi tiết và lưu tại `%LOCALAPPDATA%\KySoPython\diagnostics\last-connection.log`. Log này chỉ phục vụ bước kết nối, không đọc PIN hoặc cookie. Nếu vẫn lỗi, gửi thông báo mới hoặc log kết nối này.
