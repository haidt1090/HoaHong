# Thanh toán nhanh toàn bộ — BẢN THỬ, CHƯA KIỂM THỬ WINDOWS/SQL SERVER

Bấm **Thanh toán** trong màn hình Khám bệnh – Điều trị sẽ gọi bộ xử lý mới thay vì mở Mẫu phiếu thu số 2. Bộ xử lý dự kiến thu đủ phần còn nợ của tiền khám/thủ thuật và tất cả đơn thuốc của lần khám, mặc định tiền mặt, không ghi nợ, không dùng tạm ứng và không tự in. Vẫn hiện thông báo kết quả hoặc lỗi.

## Cách thử

1. Sao lưu database, phục hồi thành database thử riêng và sao chép toàn bộ thư mục chương trình sang thư mục thử.
2. Cấu hình chương trình thử kết nối **database thử** trước khi chạy. Chỉ sao chép thư mục EXE không tách database: ứng dụng đọc chuỗi kết nối trong registry người dùng tại `SOFTWARE\DakhoasoSoft2024dot8\ConnectionSQL\StringSQL`. Cấu hình này có thể dùng chung với chương trình đang chạy.
3. Đóng chương trình thử. Giữ lại EXE gốc; chép **cả hai file** `DakhoasoSoft.exe` và `DKS.QuickPay.dll` trong gói vào thư mục thử có các DLL DevExpress gốc.
4. Chạy thử các trường hợp dưới đây. Chưa thay EXE của máy đang thu tiền thực tế.

## Cơ chế và giới hạn

- Bản vá chỉ dành cho EXE gốc có SHA256 `5abb1bc6e4be8659bce4544a42b39e1f989a98d72219c589ef89b3e562bc7a59`.
- Thay đúng một lệnh gọi `Form.ShowDialog()` ở `uc_Nghiepvu.btnThanhtoan_Click` bằng adapter. Các hàm thu tiền, tạo phiếu và xuất thuốc gốc được gọi lại qua reflection.
- Tính phần còn nợ từ dữ liệu hiện tại; không chỉ đổi nhãn Đã thanh toán. Không thu thêm nếu phần nợ bằng 0; kiểm tra lại công nợ sau khi lưu.
- Lặp qua tất cả đơn thuốc. Tái sử dụng phiếu xuất có sẵn, chỉ thêm số lượng chưa xuất, kiểm tra kho và đối chiếu số lượng sau khi xuất. Dừng nếu thiếu tồn kho, mã trống/trùng, nhiều phiếu xuất cho một đơn hoặc số lượng xuất không khớp.
- Dùng `TransactionScope` Serializable và khóa ứng dụng SQL giữa các giao dịch thanh toán nhanh. Do lớp truy cập dữ liệu gốc mở nhiều connection, hệ thống **có thể cần MSDTC**. Nếu không hỗ trợ transaction hoặc có lỗi thì không được coi là đã thu thành công.
- Tính nguyên khối của toàn bộ stored procedure, ghi nhật ký, kho và dữ liệu thực tế **chưa được chứng minh**. Cần kiểm tra rollback trên database thử. Khóa chỉ phối hợp các phiên dùng adapter, không khóa mọi màn hình/phần mềm khác.
- Từ chối khoản tiền còn nợ có phần lẻ để tránh hàm gốc loại dấu thập phân làm sai tiền. Công thức giữ theo hàm gốc; mẫu SQL và schema thực tế chưa có để đối chiếu.
- EXE ClickOnce/manifest và file PDB gốc không còn khớp EXE đã sửa. Gói dành cho chạy thử trực tiếp; chưa đóng gói lại bản triển khai ClickOnce.

## Kiểm tra bắt buộc trên database thử

- Lần khám chỉ có 140.000đ tiền thủ thuật: thu 140.000đ, đúng thu ngân, còn nợ 0, không mở form.
- Đã trả một phần: chỉ thu số còn nợ; kiểm tra giảm giá và phần được chi trả.
- Không có thuốc; một đơn; nhiều đơn; thuốc đã xuất đủ; xuất một phần; thuốc đã trả một phần.
- Thiếu thuốc hoặc lỗi SQL giữa chừng: không phát sinh phiếu/tiền/kho dang dở; đối chiếu trước/sau.
- Bấm lại và bấm từ hai máy: không thu trùng, không xuất trùng; đối chiếu sổ quỹ, tồn kho, báo cáo và nhật ký.
- Thuốc thuộc kho khác kho đầu tiên; khoản có phần lẻ; kết nối đứt lúc ghi; MSDTC tắt.

## Các kiểm tra đã chạy tại môi trường phân tích

- Build adapter .NET Framework 4.0 và công cụ vá: không lỗi/cảnh báo.
- 12 tình huống tính công nợ: qua.
- Kiểm tra các tên lớp, trường và hàm của adapter tồn tại trong EXE gốc: qua.
- So sánh 15.324 phương thức: đúng một lệnh được thay; giữ tên tài nguyên và kiểu biến cục bộ.
- Chưa chạy giao diện Windows, SQL Server, stored procedure thực tế hoặc kiểm tra rollback/MSDTC.

## Hoàn tác

Đóng chương trình, phục hồi EXE gốc và bỏ `DKS.QuickPay.dll`. Hoàn tác file chương trình không xóa các giao dịch đã ghi vào database.

## Build lại

SDK .NET 8 build `source/QuickPay.csproj` (target .NET Framework 4.0) và `patcher/Patcher.csproj`. Công cụ vá nhận ba tham số: đường dẫn EXE gốc, adapter DLL, EXE đầu ra. Công cụ từ chối EXE gốc khác hash.
