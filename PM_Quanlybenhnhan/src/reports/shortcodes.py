"""
Documented shortcode/variable surface for report templates (Sprint 9a).

Consumed by:
  * the admin variable picker (``reports/static/reports/template_editor.js``)
  * ``GET /api/report-templates/variables/`` for the frontend editor
  * the admin guide page (``admin:reports_template_guide``)
"""

from __future__ import annotations

from typing import Any

#: Variables available in ``body_html`` and in every department body template.
#: Excel letterhead (``header_xlsx`` / ``footer_xlsx``) is static and does not
#: use these tokens.
REPORT_VARIABLES: list[dict[str, Any]] = [
    {
        "group": "Phòng khám",
        "variables": [
            {"token": "{{ clinic_name }}", "label": "Tên phòng khám"},
            {"token": "{{ clinic_address }}", "label": "Địa chỉ phòng khám"},
            {"token": "{{ clinic_phone }}", "label": "Số điện thoại"},
            {"token": "{{ clinic_email }}", "label": "Email"},
            {"token": "{{ clinic_website }}", "label": "Website"},
            {
                "token": '<img src="{{ logo_url }}" style="height:20mm">',
                "label": "Logo (từ ReportTemplate.logo)",
            },
        ],
    },
    {
        "group": "Công ty",
        "variables": [
            {"token": "{{ company.name }}", "label": "Tên công ty"},
            {"token": "{{ company.code }}", "label": "Mã công ty"},
            {"token": "{{ company.address }}", "label": "Địa chỉ công ty"},
            {"token": "{{ company.tax_code }}", "label": "Mã số thuế"},
            {"token": "{{ company.contact_person }}", "label": "Người liên hệ"},
            {"token": "{{ company.contact_phone }}", "label": "SĐT liên hệ"},
        ],
    },
    {
        "group": "Đợt khám",
        "variables": [
            {"token": "{{ exam_package_name }}", "label": "Tên gói khám"},
            {"token": "{{ exam_type }}", "label": "Loại khám"},
            {"token": "{{ exam_date }}", "label": "Ngày khám"},
            {"token": "{{ report_date }}", "label": "Ngày tạo báo cáo"},
            {"token": "{{ total_employees }}", "label": "Tổng số nhân viên"},
            {"token": "{{ day }}", "label": "Ngày (số)"},
            {"token": "{{ month }}", "label": "Tháng (số)"},
            {"token": "{{ year }}", "label": "Năm (số)"},
        ],
    },
    {
        "group": "Nhân viên (trong template khoa)",
        "variables": [
            {"token": "{{ patient.stt }}", "label": "STT"},
            {"token": "{{ patient.so_ho_so }}", "label": "Số hồ sơ"},
            {"token": "{{ patient.ma_nv }}", "label": "Mã nhân viên"},
            {"token": "{{ patient.ho_ten }}", "label": "Họ và tên"},
            {"token": "{{ patient.ngay_sinh }}", "label": "Ngày sinh"},
            {"token": "{{ patient.tuoi }}", "label": "Tuổi"},
            {"token": "{{ patient.gioi_tinh_display }}", "label": "Giới tính"},
            {"token": "{{ patient.bo_phan }}", "label": "Bộ phận"},
            {"token": "{{ patient.cccd }}", "label": "CCCD"},
            {"token": "{{ patient.noi_o }}", "label": "Nơi ở hiện tại"},
            {"token": "{{ patient.ngay_vao }}", "label": "Ngày vào làm"},
            {"token": "{{ patient.exam_date }}", "label": "Ngày khám của NV"},
            {"token": "{{ patient.phan_loai }}", "label": "Phân loại sức khỏe"},
            {"token": "{{ patient.benh_mac }}", "label": "Bệnh mắc"},
            {"token": "{{ patient.tu_van }}", "label": "Tư vấn"},
            {"token": "{{ patient.ket_luan }}", "label": "Kết luận"},
            {"token": "{{ patient.doctor_name }}", "label": "Bác sĩ khám"},
            {"token": "{{ patient.abnormal_count }}", "label": "Số chỉ số bất thường"},
            {
                "token": "{{ result_table|safe }}",
                "label": "Bảng kết quả chi tiết của NV",
            },
        ],
    },
    {
        "group": "Khoa (trong template khoa)",
        "variables": [
            {"token": "{{ department.name }}", "label": "Tên khoa"},
            {"token": "{{ department.code }}", "label": "Mã khoa"},
            {"token": "{{ department.template_name }}", "label": "Tên template khoa"},
            {"token": "{{ department.parent_name }}", "label": "Tên khoa cha"},
            {"token": "{{ has_abnormal }}", "label": "Khoa có chỉ số bất thường?"},
            {
                "token": "{{ group_index }}",
                "label": "STT khoa trong báo cáo tổng hợp (1, 2, 3…)",
                "help": "Chỉ có khi template khoa dùng iterate_departments / per_department.",
                "scope": "department",
            },
        ],
    },
    {
        "group": "Chỉ số",
        "variables": [
            {
                "token": (
                    "{% for field in fields %}\n"
                    "  <tr>\n"
                    "    <td>{{ field.label }}</td>\n"
                    "    <td>{{ field.value }}</td>\n"
                    "    <td>{{ field.unit }}</td>\n"
                    "    <td>{{ field.normal_range }}</td>\n"
                    "  </tr>\n"
                    "{% endfor %}"
                ),
                "label": "Vòng lặp tất cả chỉ số",
            },
            {"token": "{{ field.key }}", "label": "Mã chỉ số"},
            {"token": "{{ field.label }}", "label": "Tên chỉ số"},
            {"token": "{{ field.value }}", "label": "Giá trị"},
            {"token": "{{ field.display }}", "label": "Giá trị + đơn vị"},
            {"token": "{{ field.unit }}", "label": "Đơn vị"},
            {"token": "{{ field.normal_range }}", "label": "Khoảng bình thường"},
            {"token": "{{ field.is_abnormal }}", "label": "Có bất thường?"},
            {
                "token": "{{ field.abnormal_direction }}",
                "label": "Hướng lệch (low/high)",
            },
            {
                "token": '{% if field.is_abnormal %}<span class="abnormal">{{ field.value }}</span>{% else %}{{ field.value }}{% endif %}',
                "label": "Tô đỏ giá trị bất thường",
            },
            {
                "token": "{% for field in abnormal_fields %}{{ field.label }}: {{ field.display }}{% if not forloop.last %}, {% endif %}{% endfor %}",
                "label": "Liệt kê chỉ số bất thường",
            },
            {
                "token": "{{ field.abnormal_label }}",
                "label": "Tên bệnh (từ định nghĩa bất thường)",
                "help": "Nhãn bệnh khi chỉ số lệch (DepartmentFieldAbnormal). Trống nếu bình thường.",
                "scope": "department",
            },
        ],
    },
    {
        "group": "Thống kê công ty",
        "variables": [
            {
                "token": "{{ stats.total }}",
                "label": "Tổng số CBNV đã khám",
                "scope": "report",
            },
            {"token": "{{ stats.male }}", "label": "Số nam", "scope": "report"},
            {"token": "{{ stats.female }}", "label": "Số nữ", "scope": "report"},
            {
                "token": "{{ stats.male_pct }}",
                "label": "% nam",
                "scope": "report",
            },
            {
                "token": "{{ stats.female_pct }}",
                "label": "% nữ",
                "scope": "report",
            },
        ],
    },
    {
        "group": "Cấu trúc",
        "variables": [
            {
                "token": "{% for patient in patients %}\n  {{ patient.ho_ten }}\n{% endfor %}",
                "label": "Vòng lặp nhân viên",
            },
            {"token": "{% if %}{% else %}{% endif %}", "label": "Điều kiện"},
            {"token": "{{ forloop.counter }}", "label": "Số thứ tự vòng lặp"},
            {"token": '<div class="page-break"></div>', "label": "Ngắt trang"},
            {
                "token": (
                    '<div class="report-row">\n'
                    '  <div class="report-grid-item" data-column="4" data-width="8">\n'
                    "    {% classification_table %}\n"
                    "  </div>\n"
                    '  <div class="report-grid-item" data-column="12" data-width="4">\n'
                    "    {% classification_chart %}\n"
                    "  </div>\n"
                    "</div>"
                ),
                "label": "Bảng và biểu đồ cùng hàng (lưới Excel 15 cột)",
                "help": (
                    "data-column là cột bắt đầu; data-width là số cột chiếm. "
                    "Các khối phải nằm trong cột 1-15 và không chồng nhau."
                ),
            },
            {
                "token": (
                    '<tr style="height:28pt">\n'
                    "  <th>Phân loại</th><th>Tổng</th>\n"
                    "</tr>\n"
                    '<tr data-row-height="36">\n'
                    "  <td>Loại I</td><td>10</td>\n"
                    "</tr>"
                ),
                "label": "Chiều cao hàng Excel (style / data-row-height)",
                "help": (
                    "Đặt trên <tr>, <p> hoặc <div>. Ưu tiên data-row-height. "
                    "Đơn vị khuyến nghị: pt. px được quy đổi ×0.75."
                ),
            },
            {"token": "{{ config.ten_tham_so }}", "label": "Tham số từ JSON config"},
        ],
    },
    {
        "group": "Mã gọi hàm (template tags)",
        "variables": [],  # filled after TAG_VARIABLES is defined
    },
]


#: Builtin tags — no ``{% load %}`` needed. ``scope`` is report | department.
TAG_VARIABLES: list[dict[str, Any]] = [
    {
        "token": "{% result_table %}",
        "label": "Bảng kết quả chi tiết của nhân viên",
        "help": "Bảng từng chỉ số của nhân viên đang render. Dùng trong template khoa (1 người).",
        "scope": "department",
    },
    {
        "token": "{% company_summary_table %}",
        "label": "Bảng tổng hợp công ty (1 dòng/NV)",
        "help": "Bảng phẳng toàn công ty. Chỉ in 1 lần mỗi báo cáo — an toàn nếu nằm trong vòng lặp nhân viên.",
        "scope": "report",
        "params": [
            {"name": "show_normal_range", "default": "True"},
            {"name": "highlight_abnormal", "default": "True"},
        ],
        "example": "{% company_summary_table show_normal_range=True %}",
    },
    {
        "token": "{% clinical_detail_table %}",
        "label": "Bảng chi tiết ngang (header 4 tầng)",
        "help": "Bảng ngang 1 dòng/NV, header merge R7–R10. Chỉ in 1 lần/báo cáo.",
        "scope": "report",
        "params": [
            {"name": "highlight_abnormal", "default": "True"},
            {"name": "show_normal_range", "default": "True"},
        ],
    },
    {
        "token": "{% cost_table %}",
        "label": "Bảng chi phí theo nhân viên",
        "help": "Chi phí theo chỉ số hoặc trọn gói. Chỉ in 1 lần/báo cáo.",
        "scope": "report",
    },
    {
        "token": "{% gender_table %}",
        "label": "Bảng 1.1 tổng / nam / nữ",
        "help": "Số CBNV đăng ký khám: tổng, nam, nữ và %. Dùng ở phần I báo cáo tổng hợp.",
        "scope": "report",
    },
    {
        "token": "{% classification_table %}",
        "label": "Bảng 2.1 phân loại sức khỏe × nam/nữ",
        "help": "Phân loại I–V (QĐ 1613) theo giới tính. Loại 0 được gom vào loại I.",
        "scope": "report",
    },
    {
        "token": "{% classification_chart %}",
        "label": "Biểu đồ phân loại sức khỏe",
        "help": "Biểu đồ tròn SVG theo tỷ lệ loại I–V.",
        "scope": "report",
    },
    {
        "token": "{% group_overview_table %}",
        "label": "Bảng 3.0 tỷ lệ BT/bất thường theo khoa",
        "help": "Mỗi dòng = 1 slot trong gói khám (khoa + template nhập liệu).",
        "scope": "report",
    },
    {
        "token": "{% group_overview_chart %}",
        "label": "Biểu đồ % bất thường theo khoa",
        "help": "Cột ngang % bất thường của từng khoa trong gói.",
        "scope": "report",
    },
    {
        "token": "{% dept_summary %}",
        "label": "Mini-bảng BT/bất thường của khoa hiện tại",
        "help": "Số đã khám / bình thường / bất thường của khoa đang render. Cần template có iterate_departments.",
        "scope": "department",
    },
    {
        "token": "{% dept_disease_table %}",
        "label": "Bảng bệnh trong khoa hiện tại",
        "help": "Danh sách bệnh (từ tên bất thường). Không in gì nếu khoa không có bệnh.",
        "scope": "department",
    },
    {
        "token": '{% dept_chart type="pie" %}',
        "label": "Biểu đồ bệnh của khoa hiện tại",
        "help": "Biểu đồ bệnh trong khoa. type=pie (tròn) hoặc bar (cột).",
        "scope": "department",
        "params": [
            {
                "name": "type",
                "default": "pie",
                "choices": ["pie", "bar"],
            },
        ],
        "example": '{% dept_chart type="bar" %}',
    },
    {
        "token": "{% narrative_bullets %}",
        "label": "Đoạn nhận xét (phân loại + từng khoa)",
        "help": "Sinh gạch đầu dòng: tổng số khám, từng loại SK, rồi từng khoa. Chỉ in 1 lần/báo cáo.",
        "scope": "report",
    },
]


for _group in REPORT_VARIABLES:
    if _group["group"] == "Mã gọi hàm (template tags)":
        _group["variables"] = TAG_VARIABLES
        break


DEPARTMENT_TAG_NAMES = frozenset(
    {"result_table", "dept_summary", "dept_disease_table", "dept_chart"}
)
DEPARTMENT_VARIABLE_GROUP_NAMES = frozenset(
    {
        "Phòng khám",
        "Công ty",
        "Đợt khám",
        "Nhân viên (trong template khoa)",
        "Khoa (trong template khoa)",
        "Chỉ số",
        "Cấu trúc",
        "Mã gọi hàm (template tags)",
    }
)

HTML_TAG_GUIDE: list[dict[str, str]] = [
    {
        "tag": "<h1>…</h1> đến <h4>…</h4>",
        "purpose": "Tiêu đề từ cấp 1 đến cấp 4.",
        "attributes": "class, style",
        "excel": "Mỗi tiêu đề thành một hàng. Excel đọc font-size, font-weight và text-align viết trực tiếp trong style.",
    },
    {
        "tag": "<p>…</p>, <div>…</div>",
        "purpose": "Đoạn văn hoặc khối nội dung.",
        "attributes": "class, style, data-row-height, data-excel-header-gap, data-excel-gap",
        "excel": "Mỗi khối văn bản thành một hàng; <br> bên trong tạo xuống dòng trong ô. data-excel-gap chèn hàng trống trước khối (trong body). data-excel-header-gap chỉ cách letterhead.",
    },
    {
        "tag": "<br>",
        "purpose": "Xuống dòng trong đoạn văn hoặc ô bảng.",
        "attributes": "Không có",
        "excel": "Chuyển thành ký tự xuống dòng trong cùng ô.",
    },
    {
        "tag": "<b>, <strong>, <i>, <em>, <span>",
        "purpose": "Định dạng nội tuyến cho nội dung HTML.",
        "attributes": "class, style",
        "excel": "Hiển thị trong HTML; Excel chủ yếu giữ nội dung chữ. Muốn chữ đậm/cỡ chữ trong Excel, đặt style trên td, th, p hoặc div.",
    },
    {
        "tag": "<table>…</table>",
        "purpose": "Tạo bảng dữ liệu.",
        "attributes": "class, style",
        "excel": "Tạo vùng ô Excel. Không đặt một table bên trong table khác.",
    },
    {
        "tag": "<thead>, <tbody>",
        "purpose": "Nhóm phần đầu và phần dữ liệu của bảng.",
        "attributes": "class",
        "excel": "Excel bỏ qua thẻ nhóm nhưng vẫn đọc các hàng tr bên trong.",
    },
    {
        "tag": "<tr>…</tr>",
        "purpose": "Tạo một hàng trong bảng.",
        "attributes": "class, style, data-row-height",
        "excel": "Tạo một hàng Excel. Đọc chiều cao từ style height/min-height hoặc data-row-height.",
    },
    {
        "tag": "<th>…</th>",
        "purpose": "Ô tiêu đề bảng.",
        "attributes": "class, style, colspan, rowspan",
        "excel": "Chữ đậm, căn giữa và có nền tiêu đề mặc định.",
    },
    {
        "tag": "<td>…</td>",
        "purpose": "Ô dữ liệu của bảng.",
        "attributes": "class, style, colspan, rowspan",
        "excel": "Tạo ô dữ liệu; class abnormal tô đỏ và in đậm.",
    },
    {
        "tag": '<img src="…">',
        "purpose": "Chèn logo hoặc hình ảnh.",
        "attributes": "src, class, style",
        "excel": "Đọc file://, đường dẫn file và ảnh trong MEDIA_ROOT; không tải ảnh http/https khi xuất Excel.",
    },
    {
        "tag": '<div class="page-break"></div>',
        "purpose": "Bắt đầu trang mới khi in HTML/PDF.",
        "attributes": "class",
        "excel": "Không tạo ngắt trang Excel.",
    },
    {
        "tag": '<div class="report-row">…</div>',
        "purpose": "Tạo một hàng bố cục trên lưới 15 cột.",
        "attributes": "class",
        "excel": "Các report-grid-item bên trong được đặt cùng hàng.",
    },
    {
        "tag": '<div class="report-grid-item">…</div>',
        "purpose": "Đặt một bảng, biểu đồ, ảnh hoặc khối chữ vào lưới.",
        "attributes": "class, data-column, data-width",
        "excel": "data-column là cột bắt đầu; data-width là số cột chiếm.",
    },
]

HTML_ATTRIBUTE_GUIDE: list[dict[str, str]] = [
    {
        "attribute": "class",
        "values": "report-table, abnormal, page-break, report-row, report-grid-item",
        "html": "Áp dụng CSS có sẵn của báo cáo.",
        "excel": "Excel nhận abnormal và các class bố cục report-row/report-grid-item.",
    },
    {
        "attribute": "colspan",
        "values": 'colspan="2"',
        "html": "Gộp ô theo chiều ngang.",
        "excel": "Merge số cột tương ứng; trong lưới co giãn, phạm vi được phân bổ lại theo data-width.",
    },
    {
        "attribute": "rowspan",
        "values": 'rowspan="2"',
        "html": "Gộp ô theo chiều dọc.",
        "excel": "Merge số hàng tương ứng.",
    },
    {
        "attribute": "style",
        "values": "text-align, font-size (pt), font-weight, height / min-height (pt|px)",
        "html": "Trình duyệt áp dụng toàn bộ CSS hợp lệ.",
        "excel": "Chuyển text-align, font-size (pt), font-weight: bold và height/min-height thành chiều cao hàng Excel.",
    },
    {
        "attribute": "data-row-height",
        "values": 'data-row-height="30" hoặc data-row-height="30pt"',
        "html": "Gợi ý chiều cao hàng (không bắt buộc cho trình duyệt).",
        "excel": "Đặt chiều cao hàng Excel theo điểm (pt). Ưu tiên hơn style height trên cùng thẻ.",
    },
    {
        "attribute": "data-excel-header-gap",
        "values": 'data-excel-header-gap="9"',
        "html": "Không ảnh hưởng bố cục HTML/PDF (metadata xuất Excel).",
        "excel": "Số hàng trống giữa letterhead Excel và nội dung body. Mặc định 1 nếu bỏ qua. Đặt trên bất kỳ thẻ nào trong HTML đã render.",
    },
    {
        "attribute": "data-excel-gap",
        "values": 'data-excel-gap="1"',
        "html": "Không ảnh hưởng bố cục HTML/PDF (metadata xuất Excel).",
        "excel": "Chèn N hàng trống ngay trước thẻ này trong body Excel. Dùng giữa các mục, không phải dưới letterhead.",
    },
    {
        "attribute": "data-column",
        "values": 'data-column="1" … "15"',
        "html": "Chọn cột bắt đầu trong CSS Grid 15 cột.",
        "excel": "Chọn cột Excel bắt đầu: 1=A, 4=D, 12=L, 15=O.",
    },
    {
        "attribute": "data-width",
        "values": 'data-width="1" … "15"',
        "html": "Số cột của CSS Grid mà khối chiếm.",
        "excel": "Số cột Excel mà khối chiếm; column + width - 1 không được vượt 15.",
    },
    {
        "attribute": "src",
        "values": 'src="{{ logo_url }}"',
        "html": "Đường dẫn ảnh.",
        "excel": "Nên dùng logo_url hoặc file trong MEDIA_ROOT; URL ngoài không được tải.",
    },
]

HTML_GUIDE_NOTES: list[str] = [
    "Template được autoescape: dữ liệu từ biến được escape trước khi đưa vào HTML.",
    "Không dùng script, iframe, include, extends, load, debug hoặc ssi trong template báo cáo.",
    "CSS trong thẻ style: Excel chỉ chuyển text-align, font-size (pt), font-weight: bold và height/min-height (pt|px). width, margin, padding, border, color chỉ chắc chắn có hiệu lực ở HTML/PDF.",
    'Chiều cao hàng Excel: đặt trên <tr>, <p> hoặc <div> bằng style="height:28pt" hoặc data-row-height="28". Số không đơn vị được hiểu là pt; px được quy đổi ×0.75.',
    'Khoảng cách dưới letterhead Excel: đặt data-excel-header-gap="N" (N ≥ 0) trên bất kỳ thẻ nào. Mặc định 1 hàng trống. Không dùng bảng <tr> rỗng để đẩy nội dung xuống dưới header.',
    'Cách dòng trong body Excel: đặt data-excel-gap="N" trên <div>, <p> hoặc <h2>… — N hàng trống được chèn ngay trước thẻ đó. Ví dụ <h2 data-excel-gap="1">II. …</h2>.',
    "Không lồng table trong table. Để đặt hai bảng cạnh nhau, dùng report-row và hai report-grid-item.",
    "Mỗi report-grid-item nên chứa một khối chính: một shortcode bảng, một shortcode biểu đồ, một ảnh hoặc một đoạn chữ.",
]


TEMPLATE_CONCEPTS: list[dict[str, Any]] = [
    {
        "id": "syntax",
        "title": "Hai loại mã",
        "paragraphs": [
            "Biến {{ tên }} in ra một giá trị. Mã gọi hàm {% ten_ham %} dựng cả bảng hoặc biểu đồ — không cần viết {% load %}.",
            "Header/footer Excel là file tĩnh: không dùng các mã này. Chỉ phần thân HTML (template khoa hoặc body_html) mới đọc mã.",
        ],
        "examples": [
            {"code": "{{ company.name }}", "note": "In tên công ty"},
            {"code": "{% gender_table %}", "note": "Gọi hàm dựng bảng 1.1"},
        ],
    },
    {
        "id": "where",
        "title": "Đặt mã ở đâu?",
        "paragraphs": [
            "Template khoa (Department report template): dùng biến nhân viên, khoa, chỉ số và các hàm phạm vi “khoa”.",
            "Thân báo cáo (body_html) hoặc template khoa gắn vào báo cáo tổng hợp: dùng biến công ty/đợt khám, {{ stats.* }} và các hàm phạm vi “báo cáo”.",
            "Hàm phạm vi “báo cáo” chỉ in một lần dù nằm trong vòng lặp nhân viên — tránh bảng bị nhân đôi.",
        ],
    },
    {
        "id": "composite",
        "title": "Báo cáo ghép theo khoa",
        "paragraphs": [
            "Chọn kiểu thân “Ghép template theo khoa”, rồi gắn từng template khoa ở mục Report template items.",
            "body_config.per_patient=true: lặp cả danh sách khoa cho từng nhân viên (sổ khám cá nhân).",
            "body_config.per_patient=false và per_department=true: phần thống kê in một lần; template có iterate_departments lặp theo từng khoa trong gói (báo cáo tổng hợp công ty).",
            'config của template khoa: {"iterate_departments": true} để khối đó chạy một lần cho mỗi slot khoa.',
            'body_config.advice: map mã/tên khoa → câu kiến nghị riêng, ví dụ {"XN": "Theo dõi công thức máu 3 tháng/lần"}.',
        ],
        "examples": [
            {
                "code": '{"per_patient": false, "per_department": true, "skip_empty": true}',
                "note": "body_config mẫu — báo cáo tổng hợp",
            },
            {
                "code": '{"iterate_departments": true}',
                "note": "config của template “Tổng hợp 1 khoa”",
            },
        ],
    },
    {
        "id": "excel-grid",
        "title": "Bố cục Excel 15 cột",
        "paragraphs": [
            "Dùng report-row để đặt nhiều bảng hoặc biểu đồ trên cùng một hàng khi xuất HTML và Excel.",
            "Mỗi report-grid-item khai báo data-column (cột bắt đầu 1-15) và data-width (số cột chiếm). Tổng phạm vi không được vượt cột 15 hoặc chồng lên khối khác.",
        ],
        "examples": [
            {
                "code": (
                    '<div class="report-row">\n'
                    '  <div class="report-grid-item" data-column="4" data-width="8">\n'
                    "    {% classification_table %}\n"
                    "  </div>\n"
                    '  <div class="report-grid-item" data-column="12" data-width="4">\n'
                    "    {% classification_chart %}\n"
                    "  </div>\n"
                    "</div>"
                ),
                "note": "Chừa 3 cột trái; bảng ở D-K và biểu đồ ở L-O.",
            }
        ],
    },
    {
        "id": "row-height",
        "title": "Chiều cao hàng Excel",
        "paragraphs": [
            "Khi xuất Excel, có thể cố định chiều cao hàng bằng style height/min-height hoặc thuộc tính data-row-height.",
            "Đặt trên thẻ <tr> (hàng bảng) hoặc trên <p>/<div>/<h1>–<h4> (khối chữ). data-row-height được ưu tiên hơn style trên cùng thẻ.",
            "Đơn vị khuyến nghị là pt (điểm Excel). px được quy đổi ×0.75. Số không có đơn vị được hiểu là pt. Giá trị ≤ 0 bị bỏ qua.",
        ],
        "examples": [
            {
                "code": '<tr style="height:28pt"><th>Phân loại</th><th>Tổng</th></tr>',
                "note": "Hàng tiêu đề cao 28pt",
            },
            {
                "code": '<tr data-row-height="36"><td>Loại I</td><td>10</td></tr>',
                "note": "Hàng dữ liệu cao 36pt",
            },
            {
                "code": '<p style="height:18pt">Tiêu đề phụ</p>',
                "note": "Khối chữ ngoài bảng cũng đặt được chiều cao hàng",
            },
            {
                "code": '<tr style="min-height:22pt; height:30pt"><td>…</td></tr>',
                "note": "Có cả height và min-height: Excel lấy height trước",
            },
        ],
    },
    {
        "id": "header-gap",
        "title": "Khoảng cách dưới letterhead Excel",
        "paragraphs": [
            "Khi template có file header.xlsx, body HTML được ghép ngay dưới letterhead. Mặc định chừa 1 hàng trống.",
            "Nếu logo/khung trong header kéo dài thấp hơn hàng ô cuối cùng, tăng khoảng trống bằng data-excel-header-gap để tránh đè nội dung.",
            "Thuộc tính chỉ dùng khi xuất Excel; HTML/PDF bỏ qua. Đặt trên bất kỳ thẻ nào trong body (thường là thẻ đầu).",
        ],
        "examples": [
            {
                "code": '<div data-excel-header-gap="9"></div>\n<p>Nội dung bắt đầu sau 9 hàng trống dưới header…</p>',
                "note": "9 hàng trống giữa letterhead và body",
            },
            {
                "code": '<div data-excel-header-gap="0"></div>',
                "note": "Dán body sát ngay hàng ô cuối của header (không chừa trống)",
            },
        ],
    },
    {
        "id": "body-gap",
        "title": "Cách dòng trong body Excel",
        "paragraphs": [
            "data-excel-header-gap chỉ chèn hàng trống dưới letterhead, một lần cho cả báo cáo.",
            "Để cách 1–N dòng giữa các mục trong body, đặt data-excel-gap trên thẻ bắt đầu mục tiếp theo (hoặc một <div> trống).",
            "Thuộc tính chỉ dùng khi xuất Excel; HTML/PDF bỏ qua.",
        ],
        "examples": [
            {
                "code": '<h2 data-excel-gap="1">II. BẢNG PHÂN LOẠI SỨC KHỎE</h2>',
                "note": "1 hàng trống rồi mới tới tiêu đề mục II",
            },
            {
                "code": '<div data-excel-gap="2"></div>',
                "note": "2 hàng trống tại vị trí thẻ này",
            },
        ],
    },
]


def variable_groups_for(*, department: bool) -> list[dict[str, Any]]:
    """Picker groups: department editors only see khoa-scoped tags."""
    if not department:
        return REPORT_VARIABLES
    groups: list[dict[str, Any]] = []
    for group in REPORT_VARIABLES:
        if group["group"] not in DEPARTMENT_VARIABLE_GROUP_NAMES:
            continue
        if group["group"] == "Mã gọi hàm (template tags)":
            groups.append(
                {
                    "group": group["group"],
                    "variables": [
                        item
                        for item in group["variables"]
                        if any(name in item["token"] for name in DEPARTMENT_TAG_NAMES)
                    ],
                }
            )
        else:
            groups.append(group)
    return groups


def flat_tokens() -> list[str]:
    """Every documented token, flattened — used by tests and validation."""
    return [v["token"] for g in REPORT_VARIABLES for v in g["variables"]]


def tag_catalog() -> list[dict[str, Any]]:
    """Tags with help text — used by the admin guide page."""
    return TAG_VARIABLES
