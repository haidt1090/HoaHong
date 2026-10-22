# InBaoCao

Ứng dụng tiếng Việt nhập danh sách Excel, liên kết dữ liệu với nhiều mẫu sổ khám sức khỏe và xuất PDF A3 hàng loạt. Yêu cầu gốc và phạm vi triển khai: [docs/YEU_CAU.md](docs/YEU_CAU.md).

## Bản Windows EXE

Xem [hướng dẫn dùng, chuyển máy và đóng gói Windows](docs/UNG_DUNG_WINDOWS.md). Có bộ cài và bản portable; máy sử dụng không cần Node.js. Chỉnh mã nguồn rồi chạy `DongGoiWindows.cmd` để tạo phiên bản mới.

## Chạy ứng dụng

Yêu cầu Node.js 22.13+ hoặc 24, npm. LibreOffice (`soffice` trong PATH) cần cho nhập `.docx`; có thể đặt `SOFFICE_BIN` là đường dẫn executable. Không cần cơ sở dữ liệu hoặc API key. Mặc định cổng 5173; đổi bằng `PORT`.

```sh
cd InBaoCao
npm ci
npm run dev
```

Bản production:

```sh
npm run build
npm start
```

Máy chủ cung cấp cả giao diện và API chuyển Word. Không dùng riêng `vite preview` nếu cần nhập Word. Với máy chưa có LibreOffice, xuất Word thành PDF bằng Microsoft Word rồi nhập PDF. Cài LibreOffice từ nguồn chính thức/hệ điều hành nếu muốn chuyển trực tiếp.

## Sử dụng

1. Nhập `.xlsx` tại **In sổ sức khỏe**; kiểm tra sheet, dòng tiêu đề và danh sách. Excel có các cột mã số nên định dạng **Text** để giữ số 0 đầu; ứng dụng không thể khôi phục số 0 Excel đã làm mất.
2. Chọn **Thêm mẫu mới**, nhập Word/PDF/ảnh tối đa 25 MB. Dùng mẫu trắng. Word đi qua LibreOffice nên cần so sánh bố cục với file gốc; xuất PDF từ Word khi cần giữ bố cục chính xác.
3. Trong **Kho mẫu in**, đặt tên. Chọn trường, bấm vị trí trên trang, điều chỉnh tọa độ/cỡ chữ/chiều rộng. Chuyển trang để đặt tiếp; có thể đặt Họ và tên ở nhiều vị trí. Không cần sửa chính file mẫu bằng placeholder.
4. Trở lại màn hình in, chọn mẫu và mở **Thiết lập** để tự liên kết cột hoặc nhập giá trị chung (ví dụ Nơi công tác). Ô không có dữ liệu để trống.
5. Chọn người cần in. Xuất thử một người rồi **Tạo PDF hàng loạt**. Tất cả người được chọn đều xuất, kể cả khi bảng chỉ hiển thị 300 kết quả đầu hoặc đang tìm kiếm.
6. Mở/tải PDF, dùng hộp thoại in: A3, tỷ lệ thực 100%, thiết lập in hai mặt phù hợp với máy. Ứng dụng không xác minh được chất lượng hay chiều lật giấy trên máy in vật lý.
7. Sao lưu kho mẫu JSON trước khi xóa dữ liệu trình duyệt hoặc chuyển máy. Danh sách Excel không được giữ sau khi tải lại trang.

## Dữ liệu và giới hạn

Excel xử lý trong trình duyệt. Kho mẫu (gồm nội dung tài liệu) lưu trong IndexedDB của trình duyệt hiện tại, không đồng bộ lên tài khoản. Word được gửi cùng nguồn đến máy chủ, lưu thư mục tạm riêng, chuyển PDF bằng LibreOffice với thời hạn 90 giây, xóa sau xử lý; tối đa một tác vụ chuyển Word tại một thời điểm. PDF/ảnh không gửi lên máy chủ. Font tiếng Việt được đóng gói cục bộ.

Bản này dành cho máy cá nhân/mạng nội bộ tin cậy. Chưa có xác thực người dùng; cần bổ sung xác thực, HTTPS và giới hạn truy cập trước khi công khai máy chủ chuyển Word ra Internet. Không mở tài liệu không tin cậy trên máy chứa dữ liệu nhạy cảm.

Mẫu Word/PDF có sẵn thông tin người cũ phải được làm sạch trước khi nhập. Tùy chọn nền trắng chỉ che vùng hiển thị, không xóa nội dung nền khỏi cấu trúc PDF. Mã vạch của mẫu không tự cập nhật. Địa chỉ thường trú và bộ phận không tự gán cho nơi ở hiện tại/nghề nghiệp để tránh thay đổi nghĩa dữ liệu.

PDF nguồn được giữ dưới dạng vector khi xuất; ảnh dùng độ phân giải gốc. Font dữ liệu xuất PDF là DejaVu Sans có giấy phép đi kèm tại `public/fonts`.

## Kiểm thử

```sh
npm test
npm run test:e2e
npm run build
```

Kiểm thử trình duyệt dùng Chromium có sẵn (`CHROMIUM_PATH=/usr/bin/chromium`) hoặc `npx playwright install chromium` nếu máy chưa có trình duyệt. File thử được sinh tự động, không chứa dữ liệu thật.
