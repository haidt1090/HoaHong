# InBaoCao cho Windows

## Dùng trên máy của bạn

Hỗ trợ Windows 10/11 64-bit. Không cần cài Node.js, không cần mở Terminal khi dùng bản EXE.

- **InBaoCao-1.1.0-x64-Setup.exe**: bộ cài, cho phép chọn thư mục cài và tạo lối tắt trên Desktop/Start menu.
- **InBaoCao-1.1.0-x64-Portable.exe**: bấm đúp để chạy, không cần cài đặt. Có thể chép qua USB. Bản portable vẫn lưu cấu hình và kho mẫu vào tài khoản Windows trên từng máy, không lưu hồ sơ cạnh EXE trên USB.

PDF/Excel/font được đóng gói trong ứng dụng, dùng được ngoại tuyến. Muốn nhập trực tiếp Word cần cài thêm LibreOffice trên mỗi máy; ứng dụng tự tìm trong Program Files. Có thể xuất Word thành PDF trước để không phải cài LibreOffice. Ứng dụng không tự cài hoặc đóng gói LibreOffice.

## Chỉnh mẫu và mang sang máy khác

1. Mở EXE, vào **Kho mẫu in**, nhập mẫu, đặt tên và chỉnh vị trí các trường dữ liệu.
2. Bấm **Sao lưu kho mẫu** để lấy file `InBaoCao-kho-mau.json`.
3. Chép EXE portable (hoặc bộ cài) cùng file JSON sang máy mới.
4. Mở InBaoCao trên máy mới, chọn **Khôi phục mẫu**, chọn file JSON.
5. Chọn Excel danh sách của đợt khám và in. Không cần đóng gói lại mã nguồn chỉ để thay đổi mẫu.

Mẫu trong trình duyệt web cũ và mẫu trong EXE là hai kho riêng. Muốn chuyển từ bản web sang bản EXE cũng dùng Sao lưu/Khôi phục. Không xóa dữ liệu ứng dụng trước khi sao lưu. Danh sách Excel chỉ giữ trong phiên đang mở.

Dữ liệu desktop lưu ở `%APPDATA%\InBaoCao`. Cài phiên bản mới hoặc đổi thư mục đặt EXE giữ cùng kho mẫu; trình gỡ cài đặt không chủ động xóa kho mẫu. Không mở đồng thời nhiều phiên độc lập: ứng dụng sẽ đưa cửa sổ đang mở lên trước.

## Chỉnh mã nguồn và đóng gói phiên bản mới

Máy **phát triển/đóng gói** cần Node.js 24 LTS, npm và Internet để tải Electron/công cụ build. Máy **sử dụng** chỉ cần file EXE.

Tải repo HoaHong, vào thư mục InBaoCao, bấm đúp `DongGoiWindows.cmd`. Script cài đúng phụ thuộc từ lockfile rồi build. Hoặc chạy:

```sh
npm ci
npm run desktop
```

Chỉnh giao diện trong `src`, vỏ ứng dụng trong `desktop`, chuyển Word trong `word-converter.js`. Sau khi sửa:

```sh
npm test
npm run test:e2e
npm run pack:win
```

Có thể chạy `npm run test:desktop` để kiểm thử cửa sổ Electron bằng dữ liệu giả. Linux cần màn hình/Xvfb. File `build/installer.nsi` điều khiển bộ cài và giữ nguyên dữ liệu AppData khi gỡ ứng dụng; hãy đóng InBaoCao trước khi cài phiên bản mới.

Kết quả nằm trong `release/`: bộ cài và bản portable. Tăng `version` trong `package.json` bằng `npm version patch --no-git-tag-version` trước khi phát hành phiên bản mới để đồng bộ lockfile. Không chép `node_modules` hoặc dữ liệu người khám vào repo.

## Lấy bản đóng gói từ GitHub

Repo có workflow **InBaoCao - Build Windows EXE**. Mỗi lần cập nhật InBaoCao trên main, GitHub Actions sẽ build bằng Windows. Có thể chạy lại trong tab **Actions → InBaoCao - Build Windows EXE → Run workflow**. Khi workflow thành công, tải artifact **InBaoCao-Windows-x64**, giải nén lấy EXE. Artifact được giữ 30 ngày; đây không phải bản GitHub Release vĩnh viễn.

## Lưu ý phát hành

Bộ cài hiện chưa có chữ ký số nhà phát hành. Windows có thể hiển thị cảnh báo ứng dụng chưa được nhận diện; xác minh nguồn file trước khi mở. Không tắt Windows Defender hoặc chính sách bảo vệ của máy. Muốn phát hành rộng rãi nên ký số bằng chứng thư của đơn vị.

Việc build EXE trên Linux không xác minh được cài đặt/in thực tế trên Windows. Cần kiểm tra một lượt trên Windows 10/11: mở app, nhập Excel/mẫu, xuất thử PDF, đóng/mở lại để kiểm tra lưu mẫu và in thử trên máy in A3.
