# InBaoCao — Python 2.0

Ứng dụng desktop nhẹ với **Tkinter**, nhập **mẫu Word có keyword**, ghép danh sách Excel, xem một người trong Word và in hàng loạt không cần review. Không có Electron, npm, trình duyệt nhúng hoặc bước chuyển PDF.

Đọc [HUONG_DAN.txt](HUONG_DAN.txt). Mẫu thử an toàn: `MAU_WORD_KEYWORD.docx`, `DANH_SACH_MAU.xlsx` (dữ liệu giả).

## Chạy và đóng gói trên Windows

Cài Python **3.12 64-bit** kèm Tcl/Tk và pip. Chạy `CaiDat.cmd` một lần rồi `CHAY_PHAN_MEM.bat`. Để tạo EXE, chạy `DONG_GOI_EXE.bat`, kết quả **`dist/InBaoCao.exe`**. Máy nhận EXE không cần Python. Chưa đo kích thước/tốc độ build Windows thực tế, không cam kết số MB hoặc thời gian cụ thể.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python app.py
# Đóng gói:
.venv\Scripts\python -m pip install -r requirements-build.txt
.venv\Scripts\python -m PyInstaller --noconfirm --clean InBaoCao.spec
```

**Xem thử** tạo một DOCX đã điền và mở bằng ứng dụng mặc định. **In trực tiếp** cần Windows, Microsoft Word desktop đã cài/hoạt động và driver máy in; Word Online không đủ. Không cần LibreOffice. Có thể **Xuất Word đã chọn** khi chưa có Word hoặc máy in.

## Mẫu Word và liên kết

Trong mẫu, chèn `$hovaten`, `$gt`, `$ngaysinh`, `$cccd`, `$so`… ở vị trí muốn điền. Có thể lặp cùng keyword nhiều lần, trong bảng/đầu trang/cuối trang/hộp văn bản thông thường. Dùng `$keywordrieng` hoặc `${Tên cột bất kỳ}` để tự liên kết cột. Keyword plain text được xử lý kể cả khi Word chia thành nhiều run khác định dạng. Không dùng trường mail-merge của Word thay cho keyword.

Nhập mẫu → chọn Excel → kiểm tra dòng tiêu đề → chỉnh liên kết nếu cần. Trường thiếu để trống; giá trị chung chỉ được dùng khi không chọn cột. Không sửa ảnh, chữ ký, mã vạch hoặc dữ liệu cố định trong mẫu. Giữ sẵn khổ A3/hướng giấy trong Word. Chuỗi dài có thể làm Word dàn lại trang, nên xem thử một trường hợp có dữ liệu dài trước khi in thật.

In hàng loạt gửi một lệnh cho mỗi người được chọn, không mở cửa sổ review. Nút dừng có hiệu lực giữa hai người; lệnh đã gửi tới máy in không tự hủy được. Số lượng báo cáo là số lệnh gửi thành công, không xác nhận giấy đã in.

## Dữ liệu và chuyển máy

Kho mẫu/keyword/liên kết lưu tại `%APPDATA%/InBaoCaoPython`, ghi file nguyên tử và đọc lại sau khi mở app. File Excel chỉ ở bộ nhớ, không đưa vào bản sao lưu. Nút sao lưu ZIP chứa mẫu Word và liên kết; khôi phục sẽ thêm mẫu mới, không thay mẫu đang có. Dùng ZIP này để chuyển máy. Nên dùng mẫu trắng; file mẫu/giá trị chung vẫn có thể chứa thông tin người dùng đã nhập.

Bản Electron, thư viện Node và các đầu ra build cũ đã được xóa khỏi phiên bản này. Kho PDF/tọa độ của bản cũ không tự biến thành keyword Word; cần sửa file Word gốc.

## Kiểm thử và cấu trúc

```sh
python -m unittest discover -s tests -v
```

`app.py` mở app; `inbaocao/gui.py` là giao diện; `core.py` xử lý DOCX/Excel; `printing.py` làm việc với Word; `storage.py` quản lý kho mẫu. Chỉ cần openpyxl và pywin32 trên Windows; việc sửa/trộn DOCX dùng thư viện chuẩn Python, không cần python-docx hoặc bộ dựng PDF.

Xem [kết quả kiểm thử Python](docs/KIEM_THU_PYTHON.md). Chưa xác minh Microsoft Word/driver máy in trên Windows thật. Workflow Windows dùng Python/PyInstaller; kết quả build thực tế xem trong GitHub Actions.
