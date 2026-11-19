# Software Requirements Specification (SRS)

## 1. Giới thiệu

### Mục tiêu

Hệ thống hỗ trợ quản lý khám sức khỏe doanh nghiệp cho Phòng khám Đa
khoa Y Cao Hoa Hồng, hỗ trợ làm việc online/offline, nhập liệu đa nguồn,
tổng hợp kết quả, in sổ khám, trả kết quả trực tuyến và báo cáo.

## 2. Phạm vi

-   Quản lý công ty và đợt khám
-   Quản lý nhân viên
-   Quản lý hồ sơ khám
-   Nhập dữ liệu từ nhiều phòng
-   Tổng hợp kết quả
-   Sinh kết luận theo Rule Engine
-   In biểu mẫu
-   QR Code
-   Tra cứu kết quả
-   Báo cáo

## 3. Kiến trúc

-   Frontend: Next.js (PWA)
-   Backend: Django REST Framework
-   Database: PostgreSQL
-   Cache: Redis
-   Queue: Celery
-   Storage: MinIO

# 4. Core Modules

## 4.1 Authentication & RBAC

-   Đăng nhập JWT
-   Phân quyền: Admin, Lễ tân, Điều dưỡng, Bác sĩ, KTV, Doanh nghiệp,
    Người lao động
-   Audit Log

## 4.2 Company & Campaign

### Chức năng

-   Quản lý công ty
-   Quản lý đợt khám
-   Cấu hình danh mục khám
-   Import danh sách nhân viên

## 4.3 Employee

### Thông tin

-   Mã nhân viên
-   Họ tên
-   Ngày sinh
-   Giới tính
-   Công ty
-   Phòng ban
-   Chức danh
-   Nghề nghiệp

## 4.4 Medical Record

Một hồ sơ khám thuộc một nhân viên trong một đợt khám. Trạng thái: -
Draft - In Progress - Completed - Reviewed - Locked

## 4.5 Clinical Examination

-   Sinh hiệu
-   Nội khoa
-   Ngoại khoa
-   Mắt
-   Tai mũi họng
-   Răng hàm mặt
-   Da liễu
-   Phân loại sức khỏe

## 4.6 Laboratory

-   Huyết học
-   Sinh hóa
-   Nước tiểu
-   Các xét nghiệm khác
-   Import Excel
-   Nhập QR

## 4.7 Imaging

### X-Quang

-   Kết luận
-   File đính kèm

### Siêu âm

-   Kết luận
-   File đính kèm

## 4.8 Rule Engine

Mục tiêu: - Sinh kết luận tự động - Sinh tư vấn - Phân loại sức khỏe

Rule gồm: - Điều kiện - Toán tử AND/OR - Kết quả - Độ ưu tiên

## 4.9 QR Module

-   Sinh QR
-   In QR
-   Quét QR mở hồ sơ
-   In QR lên ống xét nghiệm

## 4.10 Import/Export

Import: - Excel - QR - Nhập tay

Export: - Excel - PDF - CSV

## 4.11 Report

-   Báo cáo theo công ty
-   Báo cáo đợt khám
-   Báo cáo xét nghiệm
-   Báo cáo bệnh nghề nghiệp
-   Báo cáo chi phí
-   Dashboard

## 4.12 Online Result Portal

Đăng nhập bằng: - Mã công ty - Mã nhân viên - Ngày sinh

Chức năng: - Xem kết quả - Tải PDF - Đổi mật khẩu

# 5. Business Rules

-   Một nhân viên chỉ có một hồ sơ trong một đợt khám.
-   Hồ sơ đã khóa không được sửa.
-   Chỉ bác sĩ được sửa kết luận.
-   QR là duy nhất.
-   Import có kiểm tra trùng dữ liệu.
-   Mọi thao tác ghi Audit Log.

# 6. Non-functional

-   Hỗ trợ online/offline.
-   Đồng bộ dữ liệu khi có mạng.
-   API \< 500ms với CRUD.
-   Import 10.000 dòng theo background job.
-   Backup hằng ngày.
-   HTTPS và RBAC.

# 7. Roadmap

1.  Authentication
2.  Company/Campaign
3.  Employee
4.  Medical Record
5.  Clinical
6.  Laboratory
7.  Imaging
8.  Rule Engine
9.  QR
10. Reports
11. Online Portal
12. CMS
