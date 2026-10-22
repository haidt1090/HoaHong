# Kết quả kiểm thử — 22/10/2026

- `npm test`: 3/3 bài đạt; nhận diện đủ 12 trường, không phân biệt dấu/hoa thường, trường thiếu để trống, giá trị chung, ngày Excel và rich text.
- `npm run test:e2e`: 2/2 luồng đạt trên Chromium, chạy bản production đã build. Kiểm tra Excel → liên kết tự động/thủ công → chọn người → xuất PDF A3; dữ liệu thay đổi hủy PDF cũ; mẫu lưu qua tải lại; giao diện di động không tràn ngang. Luồng thứ hai nhập PDF hai trang, đặt vị trí, xuất hai người thành bốn trang A3 ngang.
- `npm run build`: đạt. Bundle của các thư viện Excel/PDF khá lớn; có cảnh báo kích thước bundle, không ảnh hưởng kết quả build.
- `npm audit`: không có lỗ hổng được báo cáo tại thời điểm kiểm tra. Đã dùng PDF.js bản vá và override uuid tương thích cho ExcelJS.
- Hai file Excel tham khảo: nhận diện đúng dòng tiêu đề 3 và 4; lần lượt đọc 10 và 4 dòng dữ liệu không trống. File thứ hai nhận diện đúng các cột có `(*)`.
- Hai file Word tham khảo: API chuyển thành PDF thành công; nhập qua giao diện thành công. Cả hai mẫu đều xuất 10 người × 2 trang thành 20 trang A3 ngang, kiểm tra bằng bản production. Không đưa tệp kết quả hoặc dữ liệu người khám vào Git.
- Danh sách thứ nhất xuất qua mẫu minh họa thành 10 trang A3 dọc. Dùng `pdfinfo` xác nhận kích thước trang; dùng `pdftotext` đối chiếu nội bộ xác nhận tên tiếng Việt giữ nguyên.

Chưa kiểm tra máy in vật lý, chiều lật giấy hai mặt, đăng nhập/đồng bộ đa thiết bị, hoặc tự sinh mã vạch. Mẫu có dữ liệu người cũ cần được làm sạch tại nguồn trước khi sử dụng chính thức.

## Bản desktop 1.1.0

- Chạy trực tiếp các bài kiểm thử module: 3 bài xử lý dữ liệu + 2 bài kiểm tra đường dẫn tài nguyên desktop/ghi đè đường dẫn LibreOffice đều đạt.
- Hai luồng end-to-end web vẫn đạt sau khi tách bộ chuyển Word dùng chung.
- Chạy cửa sổ Electron thật trên Linux/Xvfb: tải ứng dụng qua giao thức nội bộ, PDF worker, font tiếng Việt cục bộ, nhập Excel, mẫu PDF hai trang, xuất hai người thành bốn trang A3, giữ IndexedDB sau tải lại đều đạt. Lệnh kiểm thử: `npm run test:desktop` (Linux cần màn hình hoặc Xvfb).
- Nhập mẫu Word tham khảo qua API nội bộ của Electron và hiển thị mẫu nhiều trang: đạt. Không lưu tài liệu thực vào repo.
- Đóng gói Windows x64 portable thành công bằng electron-builder. Cấu hình và workflow có cả target bộ cài NSIS và portable; bộ cài tùy chỉnh tạo uninstaller lúc cài đặt, giữ AppData và không dừng ép ứng dụng đang chạy.
- Chưa chạy/cài trên Windows thật; chưa xác minh hộp thoại máy in và in A3 vật lý. File chưa được ký số nhà phát hành.
