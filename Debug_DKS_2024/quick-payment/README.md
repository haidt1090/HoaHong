# Thanh toán nhanh và in hai máy — bản thử

## Sửa lỗi đọc báo cáo

Đã sửa lỗi `Property Get method was not found` ở In bệnh án và luồng in kèm Giấy Khám SK: thuộc tính `MyReport` của form gốc chỉ có setter; adapter đọc trường `reportMain` mà setter đó lưu vào. Cả hai đường in dùng chung bộ đọc này. Thêm 3 trường hợp kiểm tra: báo cáo đã gán, lớp kế thừa và báo cáo chưa có.

## Rà soát Báo cáo – Thống kê

Xem `AUDIT-REPORTS.md`: đã đối chiếu tất cả 10 mục (8 hiển thị, 2 ẩn), sửa lỗi có thể để sót trạng thái giao dịch khi giải phóng SQL transaction thất bại, và chặn loại phiếu thu khám bệnh không khớp mã báo cáo. Chưa đối chiếu số liệu trên SQL Server thực tế.

## Nhớ các mẫu khám sức khỏe đã tích chọn

Các dấu tích được lưu ngay theo mã mẫu, khôi phục khi mở lại cửa sổ hoặc khởi động lại phần mềm. Chỉ thay đổi khi bạn tích/bỏ tích; có thể nhớ nhiều mẫu cùng lúc, và bỏ hết cũng được lưu. Đổi máy in không xóa dấu tích. Dùng chung file cấu hình máy in tại LocalAppData; không sửa database. Cấu hình cũ chỉ có hai máy in vẫn đọc được. Xem `REPORT-CHECKLIST.md` để xem chi tiết rà soát từng mục báo cáo và phần đối soát thực tế còn thiếu.

## A3 ngang, hai mặt và in khi chưa có thủ thuật

Mẫu giấy khám sức khỏe được đặt **A3 ngang** cho mọi section trước khi in, máy thứ nhất dùng **hai mặt lật cạnh ngắn** (`Duplex.Horizontal`). Chỗ chỉnh layout là `source/HealthPageLayout.cs`; chỗ gắn cấu hình máy in là `PrepareHealthPrint` trong `source/Printing.cs`. Bệnh án qua máy thứ hai giữ thiết lập/bố cục riêng, không bị ép sang A3 hoặc hai mặt bởi thay đổi này.

Máy thứ nhất phải có A3 và hỗ trợ duplex tự động. Nếu driver không hỗ trợ A3/duplex thì báo rõ thay vì tự in một mặt hoặc đổi khổ. Riêng **Microsoft Print to PDF** tạo file A3 ngang, không yêu cầu duplex vật lý; chọn hai mặt khi in file PDF ra máy in thật. Driver PDF vẫn có thể hỏi tên file theo cơ chế Windows.

Mẫu KSK chỉ cần có bệnh nhân đã chọn, không cần thêm thủ thuật, thanh toán hay lần khám giả. Nếu có lần khám thì vẫn thử dựng bệnh án bằng hàm gốc để in kèm; nếu chưa có lần khám hoặc không dựng được bệnh án khi chưa có thủ thuật, vẫn in các mẫu KSK và ghi trạng thái không có bệnh án kèm. Với lần khám đã có thủ thuật, lỗi dựng bệnh án vẫn được báo trước khi gửi bất kỳ tài liệu nào.

7 tình huống layout A3 ngang và chính sách duplex đã qua bằng mô hình giả lập; tổng 41 tình huống đơn vị/giả lập đã qua. Chưa chạy trên máy in vật lý hoặc driver Windows của người dùng; cần thử một bệnh nhân chưa có thủ thuật và một bản hai mặt để xác nhận mặt sau đúng chiều.

## Số lượng bản in

Hai dòng máy in có ô **Số lượng** riêng, sửa được từ 1 đến 99. Mỗi mẫu KSK được tích sẽ in theo số lượng dòng thứ nhất; bệnh án theo số lượng dòng thứ hai. Ví dụ KSK=3, bệnh án=1 thì mỗi mẫu KSK in 3 bộ và bệnh án 1 bản. Đây là số bộ đầy đủ, không phải số trang. Mỗi lần mở cửa sổ số lượng mặc định về 1, không lưu theo bệnh nhân trước; máy in và dấu tích mẫu vẫn nhớ như cũ.

Bộ in đặt `Copies` và `Collate` theo driver để in từng bộ đầy đủ; nếu driver giới hạn số bản mỗi lệnh, tách đủ số bộ thành nhiều lệnh. Driver Microsoft Print to PDF có thể hỏi tên file cho từng lệnh và không có cơ chế in hai mặt trên giấy. Chưa kiểm thử phần cứng thực tế.

8 tình huống lập số lượng đã qua; cùng các kiểm tra trước có tổng 49 tình huống đơn vị/giả lập. EXE, thanh toán, database và mã báo cáo không thay đổi trong lần bổ sung ô số lượng này.

## Cập nhật chương trình

Tắt hoàn toàn DakhoasoSoft, pull repo hoặc chép **cả `DakhoasoSoft.exe` và `DKS.QuickPay.dll`** vào cùng thư mục đang có các DLL DevExpress 12.2. Chạy trực tiếp EXE, không dùng gói ClickOnce/manifest cũ. Không cần sửa chuỗi kết nối Registry, sửa schema/stored procedure database hay bật MSDTC. Bản sửa vẫn ghi giao dịch thu tiền và xuất thuốc vào database như các thao tác tương ứng.

## Thanh toán

Bấm Thanh toán ở màn hình Khám bệnh – Điều trị: thu phần còn nợ của tiền khám/thủ thuật và tất cả đơn thuốc của lần khám, mặc định tiền mặt, không ghi nợ, không dùng tạm ứng, không mở form phiếu thu và không tự in. Hiện thông báo kết quả hoặc lỗi.

- Bỏ `TransactionScope` từng gây lỗi MSDTC. Chỉ mở một `SqlConnection`, đọc thông tin kết nối bằng hàm gốc từ Registry.
- Dùng `SqlTransaction` cục bộ mức Serializable, khóa ứng dụng SQL theo transaction. Các hàm `KetNoiCSDL_Data.taobang`, `LayDuLieu`, `update` dùng chung kết nối/giao dịch trong thời gian thanh toán nhanh; ngoài luồng này giữ đường chạy gốc.
- Thu tiền, xuất thuốc và nhật ký qua lớp dữ liệu này nằm trong cùng giao dịch. Lỗi SQL được ghi nhận kể cả khi code gốc bắt và bỏ qua exception; không commit giao dịch đã lỗi.
- Tái sử dụng phiếu xuất đã có, chỉ bổ sung lượng chưa xuất, kiểm tra tồn kho và đối chiếu số lượng/công nợ sau khi ghi. Không thu thêm khi phần nợ bằng 0.
- Dừng khi thiếu tồn, dữ liệu không khớp, có nhiều phiếu xuất cho một đơn hoặc số tiền có phần lẻ. Không tạo hay thay đổi stored procedure/schema.
- Cần kiểm tra với database thực tế để xác nhận stored procedure và các trigger tương thích giao dịch cục bộ. Nếu stored procedure/trigger tự truy cập linked server thì đó là phụ thuộc riêng chưa kiểm chứng.

## Giấy Khám SK và in bệnh án

1. Bấm **Giấy Khám SK**.
2. Tích chọn một hoặc nhiều mẫu trong danh sách.
3. Dòng **Máy in giấy khám SK** dùng cho các mẫu được tích chọn.
4. Dòng **Máy in bệnh án** dùng cho bệnh án của bệnh nhân đang chọn.
5. Bấm **Print**: gửi từng mẫu tới máy thứ nhất, sau đó gửi bệnh án tới máy thứ hai; không mở cửa sổ xem trước hoặc hỏi lại máy in. Kết quả hiển thị ngay trong cửa sổ.

Hai lựa chọn được lưu riêng trên từng máy/tài khoản Windows tại `%LOCALAPPDATA%\DakhoasoSoft\printer-settings.xml`, tự khôi phục khi mở lại. Không đổi máy in mặc định của Windows. Khi đã lưu máy thứ hai, nút **In bệnh án** trên màn hình chính cũng gửi trực tiếp tới máy đó. Nếu chưa cấu hình lần nào thì nút này giữ xem trước như bản gốc.

Bộ in dùng nội dung mẫu trong database và logic thay thông tin bệnh nhân của form gốc; giữ bố cục của mẫu. Luồng bệnh án dùng hàm dựng báo cáo gốc. Chuẩn bị các tài liệu và kiểm tra tên máy in trước khi gửi; không tự chuyển sang máy in khác nếu máy đã lưu không còn hợp lệ.

Nếu lỗi giữa chừng, có thể một số tài liệu đã vào hàng đợi. Thông báo cho biết số lần gửi đã hoàn tất; phải kiểm tra hàng đợi trước khi bấm lại để tránh in trùng. Máy in ngoại tuyến/driver có thể nhận lệnh nhưng không in ra giấy ngay; thông báo gửi lệnh không xác nhận giấy đã in thành công. Một số driver PDF hoặc driver đặc thù có thể tự hiện hộp thoại riêng.

## Kiểm tra đã chạy

- Build adapter .NET Framework 4.0 và công cụ vá: qua, không lỗi/cảnh báo.
- 12 tình huống công nợ, 8 tình huống giao dịch cục bộ bằng ADO.NET fake (commit, rollback, lỗi bị bắt mất, khóa, cô lập theo thread), 2 tình huống lưu/đọc/cập nhật lựa chọn máy in: qua.
- Công cụ vá đối chiếu 15.324 phương thức: đúng 8 điểm được sửa; IL các phương thức còn lại và byte tài nguyên nhúng giữ nguyên.
- Kiểm tra tên lớp/trường/hàm của adapter và API in trong DLL DevExpress 12.2 có trong repo.
- **Chưa chạy Windows/SQL Server hoặc máy in vật lý.** Các test fake không chứng minh các stored procedure thực tế hay driver máy in hoạt động đúng.

## Cách thử

Dùng database thử được phục hồi từ bản sao lưu. Chỉ sao chép thư mục EXE không tách database: chương trình đọc chuỗi kết nối trong Registry tại `SOFTWARE\DakhoasoSoft2024dot8\ConnectionSQL\StringSQL`.

Kiểm tra lần lượt: tiền khám đơn thuần; đã trả một phần; giảm giá/phần được chi trả; nhiều đơn thuốc; thuốc đã xuất đủ hoặc một phần; thiếu tồn; lỗi SQL giữa chừng; bấm lại sau khi đã thu đủ; giao dịch từ hai máy. Đối chiếu phiếu thu, kho và nhật ký sau thành công/lỗi. Thử với MSDTC tắt để xác nhận đường chạy mới.

Với in: chọn đúng bệnh nhân và mẫu, chọn hai máy khác nhau, Print; kiểm tra đúng máy, đủ trang, đúng bố cục và thông tin bệnh nhân. Đóng/mở lại phần mềm để kiểm tra lưu lựa chọn; thử nhiều mẫu cùng lúc và nút In bệnh án riêng. Thử máy in không còn khả dụng để xác nhận không chuyển máy âm thầm.

## Hoàn tác và build

Đóng chương trình, phục hồi EXE gốc và bỏ adapter DLL. Hoàn tác file không xóa các giao dịch đã ghi vào database hay lệnh đã gửi tới hàng đợi in.

Công cụ `patcher` chỉ chấp nhận EXE gốc SHA256 `5abb1bc6e4be8659bce4544a42b39e1f989a98d72219c589ef89b3e562bc7a59`. Build `source/QuickPay.csproj` bằng SDK .NET 8 (target .NET Framework 4.0), build `patcher/Patcher.csproj`, chạy patcher với ba đường dẫn: EXE gốc, DLL mới, EXE đầu ra. Bản EXE gốc còn trong lịch sử Git trước commit thanh toán nhanh. File PDB/ClickOnce manifest gốc không còn khớp EXE đã sửa.
