# Thanh toán nhanh và in hai máy — bản thử

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
- 12 tình huống công nợ, 7 tình huống giao dịch cục bộ bằng ADO.NET fake (commit, rollback, lỗi bị bắt mất, khóa, cô lập theo thread), 2 tình huống lưu/đọc/cập nhật lựa chọn máy in: qua.
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
