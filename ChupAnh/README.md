# ChupAnh — Telegram Photo Print 1.5.1 cho Windows

Nhận ảnh bằng Bot hoặc tài khoản Telegram qua API, không auto click.
Hiển thị ảnh thu nhỏ, chọn nhiều ảnh để in hàng loạt, tự động in ảnh mới,
lưu kết nối và cài đặt in. Giấy A4/A5/A6, ảnh 3×4 hoặc 4×6 cm,
1–999 bản mỗi ảnh, chọn máy in Windows, xem trước và xuất PDF.

## Bản 1.5.1: sửa cài đặt và giới hạn Telegram

- Chỉ bot **@pkhoahongbot** được kết nối; xác minh username từ Telegram `getMe`, không dựa vào token bạn tự đặt tên.
- Chỉ tài khoản được cấp phép được dùng; số gốc không ghi trong source, chỉ giữ dấu scrypt một chiều kèm salt ngẫu nhiên. Kiểm tra số nhập trước khi xin mã và kiểm tra lại số Telegram trả về
  sau đăng nhập/khôi phục phiên. Phiên của số khác bị từ chối trước khi đọc nhóm hoặc tải ảnh.
- `CAI_DAT.bat` và `DONG_GOI.bat` dùng cùng Python **3.12 x64** và cài **đầy đủ requirements.txt**,
  không bỏ thư viện đóng gói. `zstandard==0.25.0` có wheel cp312-cp312-win_amd64;
  pip được yêu cầu dùng wheel, không tự biên dịch zstandard bằng Visual C++.
- Nếu môi trường `.venv` cũ khác Python/bitness, đổi tên giữ lại `.venv-old-...` rồi tạo môi trường đúng;
  không xóa ảnh, token hoặc dữ liệu ứng dụng trong LOCALAPPDATA.
- Nếu chưa có Python 3.12 x64, cài bản Windows 64-bit tại python.org trước. Không dùng bản 3.14/3.15 cho bộ cài này.
- Việc giới hạn danh tính nằm trong chương trình; source repo công khai vẫn có thể bị sửa bởi người có source.

## Bản 1.5: thông tin nhà phát triển và phím tắt

PHÒNG KHÁM ĐA KHOA Y CAO HOA HỒNG  
CÔNG TY TNHH DỊCH VỤ VÀ Y TẾ HUỆ LINH

Hai dòng trên hiển thị trên cùng cửa sổ chính. Bấm nút **?** trên thanh trên cùng hoặc **F1** để xem hướng dẫn.

| Phím | Thao tác |
|---|---|
| Alt+1 … Alt+9 | In ngay ảnh ở vị trí 1 … 9 tính từ ảnh mới nhất, từ trái qua phải rồi xuống hàng |
| Alt+A | In tất cả ảnh mới **chưa gửi in**, bỏ qua ảnh đã gửi, đang chờ/in, đã xuất PDF hoặc cần kiểm tra |
| F1 | Mở hướng dẫn phím tắt |

Phím tắt chỉ có tác dụng khi cửa sổ chính đang được sử dụng; không đổi các ảnh đang tích chọn.
Dùng cấu hình máy in, khổ giấy, kích thước và số bản hiện tại. Nếu chọn PDF vẫn hỏi nơi lưu.
Ảnh có tác vụ chưa rõ kết quả cần xác nhận trước khi in lại bằng Alt+số.

Mỗi tin nhắn ảnh mới từ Telegram là một lượt riêng: copy/gửi lại ảnh cũ sẽ thêm ô ảnh mới
và có thể tự in tiếp. Cùng một tin nhắn được Telegram gửi lại khi kết nối lại không bị thêm/in trùng.
Thư viện vẫn giữ tối đa 100 lượt ảnh; có thể có nhiều ô cùng nội dung từ các tin nhắn khác nhau.

Đã bỏ nhãn trạng thái và thanh tiến độ lớn phía trên bảng; theo dõi trực tiếp trong các cột.
**Xóa tất cả tiến độ** xóa toàn bộ lịch sử đã kết thúc, kể cả dòng cũ không còn hiện trong bảng.
Nút này giữ nguyên các lệnh đang chờ/in trong phần mềm và Windows, file ảnh và chống in trùng.

## Khung ảnh và thư viện

- Kéo thanh phân cách ngang giữa khung ảnh và tiến độ để thay đổi chiều cao hai khung.
  Tiến độ mặc định nhỏ hơn; bấm **Lưu cài đặt** để nhớ tỷ lệ khung.
- Ảnh mới và dòng tiến độ mới hiển thị trên cùng. Thứ tự xử lý lệnh in vẫn theo hàng chờ.
- Nút **In ảnh đã chọn** to và đậm hơn.
- Thư viện hiển thị và nhớ tối đa **100 ảnh mới nhất**. Ảnh cũ hơn được bỏ khỏi khung,
  giữ nguyên file trên đĩa và lịch sử chống in trùng.
- **Xóa ảnh đã chọn** bỏ các ảnh được tích; **Làm trống khung ảnh** dọn toàn bộ khung.
  Hai nút không xóa file, không hủy lệnh in và không xóa bảng tiến độ.
  Ảnh đã dọn không tự xuất hiện lại; dùng **Thêm ảnh** để đưa chúng vào khung lại nếu cần.

## Đóng gói thủ công sau khi test source
Bản cập nhật này chỉ có source; không tự tạo EXE và không tự đăng bản build lên Releases.
Các bản EXE 1.4 cũ không có chức năng mới của source 1.5.

Sau khi test đạt, tự chạy **DONG_GOI.bat**. Cần Windows 10/11 x64, Python **3.12 x64**
và Internet. Script tạo `.build-venv` riêng, cài đầy đủ requirements qua cùng bộ cài môi trường, biên dịch bằng **Nuitka + MinGW64**,
bỏ docstring/assert trong bản native, kiểm tra ứng dụng và tạo **dist/ChupAnh-Windows.zip**.
Lần đầu có thể tải compiler và mất nhiều thời gian hơn PyInstaller.
Máy nhận ZIP không cần Python; cần giải nén cả thư mục, không chép riêng EXE.
Bộ đóng gói không đưa token, ảnh hoặc dữ liệu `%LOCALAPPDATA%` vào ZIP.

Nuitka biên dịch mã thành native để khó trích lại mã Python hơn; không phải mã hóa hay
chống đảo ngược tuyệt đối. Repo GitHub hiện công khai nên source vẫn xem được trên GitHub.
Không thay đổi quyền riêng tư repo trong cập nhật này.

GitHub chỉ build nếu bạn chủ động **Run workflow** tại `ChupAnh - Manual Windows Build`.
Push source không tạo EXE; nếu bật kiểm tra source thì chỉ chạy kiểm tra, không đóng gói.
Môi trường, phiên bản thư viện, compiler và yêu cầu ngoài pip đều ghi trong **requirements.txt**;
`requirements-build.txt` chỉ trỏ về file đó để tương thích bộ hướng dẫn cũ.

## Các chức năng in và hàng đợi Windows: in tay, PDF và hàng đợi Windows

- Tắt tự động vẫn chọn ảnh đã in để in lại bằng tay được; lịch sử không khóa in tay.
- Chọn **Microsoft Print to PDF** hoặc **Xuất PDF trực tiếp**, bấm **In ảnh đã chọn**:
  chọn nơi lưu bằng hộp thoại của phần mềm, không gọi hộp thoại Save Print Output As của driver.
- Hủy hộp thoại lưu PDF không tạo lệnh in hoặc khóa ảnh. PDF lỗi/hủy giữ nguyên tệp đích cũ.
- Nút **Xuất PDF ảnh đã chọn** dùng cùng cơ chế xuất trực tiếp. Tự động PDF lưu vào
  **Thư mục PDF tự động**, không hỏi tên tệp từng ảnh.
- Bảng tiến độ cho từng lượt: tên ảnh đang xử lý, số bản đã xử lý, trạng thái và đích in/PDF.
- **Tạm dừng / Tiếp tục** áp dụng cho hàng đợi phần mềm và gửi PAUSE/RESUME đến các lệnh
  Windows đã nhận diện của ứng dụng.
- Chọn một dòng, bấm **Hủy lệnh đã chọn**: hủy tác vụ chưa gửi, dừng PDF đang tạo,
  hoặc gửi `SetJob(JOB_CONTROL_DELETE)` tới đúng mã lệnh trong Windows Print Spooler.
  Không dùng PurgePrinter và không xóa tác vụ của chương trình khác.
- **Mở hàng đợi Windows** mở cửa sổ queue của máy in ở dòng đang chọn.
- **Xóa tất cả tiến độ** chỉ xóa dòng lịch sử đã kết thúc; không xóa ảnh,
  không xóa lịch sử chống in trùng và không giấu tác vụ còn treo trong Windows.
- Nhớ mã lệnh và tên tài liệu riêng để mở lại vẫn theo dõi/hủy được tác vụ của bản này.

### Hiểu đúng trạng thái

**Đã xử lý ảnh** là tiến độ ghép ảnh và gửi dữ liệu. Nếu lệnh vẫn xuất hiện trong Windows,
phần mềm tiếp tục báo **chưa hoàn tất**, kể cả máy in Offline, hết giấy hoặc lỗi.
Chỉ khi truy vấn thành công và không còn lệnh tương ứng mới báo **Không còn trong hàng đợi Windows**.
Nếu truy vấn hoặc quyền điều khiển thất bại, báo lỗi và giữ trạng thái chưa xác minh.
Windows không luôn xác nhận được giấy đã ra; dữ liệu đã nằm trong bộ nhớ máy in
có thể vẫn ra giấy sau yêu cầu hủy. Theo dõi số trang Windows báo nếu driver hỗ trợ.

Tạm dừng/hủy diễn ra giữa các ảnh; nếu driver đang mở hộp thoại riêng, có thể cần đóng hộp thoại đó.
Lệnh cũ từ bản 1.2 chưa có mã theo dõi không tự được nhập vào bảng: dùng hàng đợi Windows để kiểm tra/hủy chúng.

Bộ điều khiển Windows cần `pywin32`: **phải chạy lại CAI_DAT.bat khi nâng cấp**.
Nếu thiếu thư viện hoặc chưa xác minh được queue, phần mềm không báo đã in hoàn tất.
Các thao tác Windows cần quyền truy cập lệnh in tương ứng; lỗi quyền được hiển thị.

## Cài đặt / nâng cấp bản source Python
1. Cài Python 3.12 x64 từ python.org, chọn Add Python to PATH (môi trường khuyến nghị đã ghi trong requirements).
2. Thoát hẳn bản cũ; chỉ chạy một ứng dụng nhận cùng một bot.
3. Giải nén toàn bộ gói mới vào thư mục có quyền ghi.
4. Chạy `CAI_DAT.bat` một lần, kể cả khi nâng cấp (bản mới dùng thêm keyring).
5. Chạy `MO_UNG_DUNG.bat`. Tiêu đề phải có số **1.5.1**.
6. Cài driver máy in thật trên Windows trước khi in ra giấy. OneNote và các máy in PDF
   là máy in ảo. Với Microsoft Print to PDF, phần mềm chuyển sang xuất PDF trực tiếp để tránh hộp thoại driver bị treo.

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
Tắt tự động sẽ bỏ các tác vụ tự động chưa bắt đầu. Tác vụ đã gửi Windows có thể hủy bằng nút Hủy lệnh đã chọn hoặc ở hàng đợi Windows.
Nếu máy in đã lưu không còn khả dụng, chọn lại máy in trước khi bật tự động.

Lề 7 mm, khoảng cách 3 mm. Giữ toàn bộ ảnh, không cắt; có thể có viền trắng nếu khác tỷ lệ khung.
Driver có thể co giãn hoặc thay khổ; kiểm tra bằng thước trên bản in thử.
Chống tải/in trùng cho cùng tin nhắn Telegram; tin nhắn mới gửi lại cùng nội dung vẫn được nhận và in tiếp.
Nguồn thư mục/nhập tay vẫn nhận diện trùng theo SHA-256 nội dung.
In tay vẫn có thể in lại theo hộp xác nhận. Gửi máy in chưa có nghĩa giấy đã ra.
Lỗi in sẽ dừng tự động, đánh dấu cần kiểm tra và không tự in lại để tránh ra giấy hai lần.
Trạng thái chờ bị sót sau gián đoạn được đưa về cần kiểm tra, không khóa in tay vĩnh viễn.

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
bố trí kích thước và kết xuất PDF bằng luồng in thực. Có kiểm tra toàn luồng nút In ảnh đã chọn
→ xuất PDF, hủy lưu rồi thử lại, in tay lại ảnh cũ, pause/resume/cancel, và mô phỏng Windows
Offline, SetJob, lỗi quyền, lỗi đọc queue, khôi phục mã lệnh sau khởi động lại.
Chưa kiểm chứng bằng bot/tài khoản và máy in Windows thật trong môi trường phát triển.
Đây là mã nguồn Python kèm tệp .bat, chưa phải bộ cài .exe.
