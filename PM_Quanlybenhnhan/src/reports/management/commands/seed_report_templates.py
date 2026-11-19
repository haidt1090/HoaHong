"""
Seed the default report templates (Sprint 9a, task 9).

Idempotent: templates are matched by name and updated in place unless
``--no-overwrite`` is passed. Department templates are attached to a matching
``examinations.Department`` by code when one exists, otherwise created as
global (department=None) templates that an admin can bind later.

Usage::

    python manage.py seed_report_templates
    python manage.py seed_report_templates --no-overwrite
    python manage.py seed_report_templates --list
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from examinations.models import Department
from reports.models import (
    DepartmentReportTemplate,
    ReportTemplate,
    ReportTemplateItem,
)

# ---------------------------------------------------------------------------
# Header / footer
#
# Letterhead is an uploaded .xlsx (ReportTemplate.header_xlsx / footer_xlsx).
# Seeded composites leave those empty for the admin to upload.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Department body templates
# ---------------------------------------------------------------------------

BODY_BLOOD_VERTICAL = """\
<h3 style="font-size:10pt; margin-top:3mm;">{{ department.name }}</h3>
<table class="report-table">
  <thead>
    <tr>
      <th style="width:8%;">STT</th>
      <th style="width:42%; text-align:left;">Chỉ số</th>
      <th style="width:16%;">Kết quả</th>
      <th style="width:14%;">Đơn vị</th>
      <th style="width:20%;">Trị số bình thường</th>
    </tr>
  </thead>
  <tbody>
    {% for field in fields %}
    <tr>
      <td>{{ forloop.counter }}</td>
      <td style="text-align:left;">{{ field.label }}</td>
      <td{% if field.is_abnormal %} class="abnormal"{% endif %}>{{ field.value }}</td>
      <td>{{ field.unit }}</td>
      <td>{{ field.normal_range }}</td>
    </tr>
    {% empty %}
    <tr><td colspan="5"><i>Không có dữ liệu.</i></td></tr>
    {% endfor %}
  </tbody>
</table>
{% if has_abnormal %}
<p style="font-size:8.5pt; margin-top:1mm;">
  <b>Chỉ số bất thường:</b>
  {% for field in abnormal_fields %}{{ field.label }} ({{ field.display }}){% if not forloop.last %}, {% endif %}{% endfor %}
</p>
{% endif %}
"""

BODY_URINE = """\
<h3 style="font-size:10pt; margin-top:3mm;">{{ department.name }}</h3>
<table class="report-table">
  <thead>
    <tr>
      {% for field in fields %}<th>{{ field.label }}</th>{% endfor %}
    </tr>
    <tr class="normal-range-row">
      {% for field in fields %}<th>{{ field.normal_range }}</th>{% endfor %}
    </tr>
  </thead>
  <tbody>
    <tr>
      {% for field in fields %}
      <td{% if field.is_abnormal %} class="abnormal"{% endif %}>{{ field.value }}</td>
      {% endfor %}
    </tr>
  </tbody>
</table>
"""

BODY_CLINICAL = """\
<h3 style="font-size:10pt; margin-top:3mm;">{{ department.name }}</h3>
<table class="report-table">
  <tbody>
    {% for field in fields %}
    <tr>
      <th style="width:35%; text-align:left;">{{ field.label }}</th>
      <td style="text-align:left;"{% if field.is_abnormal %} class="abnormal"{% endif %}>
        {{ field.display }}
        {% if field.normal_range %}<span style="color:#888; font-size:7.5pt;">(BT: {{ field.normal_range }})</span>{% endif %}
      </td>
    </tr>
    {% empty %}
    <tr><td><i>Chưa khám.</i></td></tr>
    {% endfor %}
  </tbody>
</table>
"""

BODY_EYE = """\
<h3 style="font-size:10pt; margin-top:3mm;">{{ department.name }}</h3>
<table class="report-table">
  <tbody>
    {% for field in fields %}
    <tr>
      <th style="width:40%; text-align:left;">{{ field.label }}</th>
      <td style="text-align:left;"{% if field.is_abnormal %} class="abnormal"{% endif %}>{{ field.display }}</td>
    </tr>
    {% empty %}
    <tr><td><i>Chưa khám mắt.</i></td></tr>
    {% endfor %}
  </tbody>
</table>
"""

BODY_ENT_DENTAL = """\
<h3 style="font-size:10pt; margin-top:3mm;">{{ department.name }}</h3>
<table class="report-table">
  <tbody>
    {% for field in fields %}
    <tr>
      <th style="width:35%; text-align:left;">{{ field.label }}</th>
      <td style="text-align:left;"{% if field.is_abnormal %} class="abnormal"{% endif %}>{{ field.display }}</td>
    </tr>
    {% empty %}
    <tr><td><i>Chưa khám.</i></td></tr>
    {% endfor %}
  </tbody>
</table>
"""

BODY_PATIENT_HEADER = """\
<div style="border:0.5pt solid #444; padding:2mm; margin-top:4mm;">
  <table style="width:100%; border:0; font-size:9pt;">
    <tr>
      <td style="border:0;"><b>{{ patient.stt }}. {{ patient.ho_ten }}</b></td>
      <td style="border:0;">Mã NV: <b>{{ patient.ma_nv }}</b></td>
      <td style="border:0;">Ngày sinh: {{ patient.ngay_sinh }}</td>
      <td style="border:0;">Giới: {{ patient.gioi_tinh_display }}</td>
    </tr>
    <tr>
      <td style="border:0;">Bộ phận: {{ patient.bo_phan }}</td>
      <td style="border:0;" colspan="2">CCCD: {{ patient.cccd }}</td>
      <td style="border:0;">Ngày khám: {{ patient.exam_date }}</td>
    </tr>
  </table>
</div>
"""

BODY_CONCLUSION = """\
<table class="report-table" style="margin-top:2mm;">
  <tbody>
    <tr><th style="width:22%; text-align:left;">Phân loại sức khoẻ</th>
        <td style="text-align:left;">{{ patient.phan_loai }}</td></tr>
    <tr><th style="text-align:left;">Bệnh mắc</th>
        <td style="text-align:left;">{{ patient.benh_mac }}</td></tr>
    <tr><th style="text-align:left;">Tư vấn</th>
        <td style="text-align:left;">{{ patient.tu_van|linebreaksbr }}</td></tr>
    <tr><th style="text-align:left;">Kết luận</th>
        <td style="text-align:left;">{{ patient.ket_luan|linebreaksbr }}</td></tr>
  </tbody>
</table>
"""

BODY_PROGRESS = """\
<h3 style="font-size:10pt; margin-top:3mm;">{{ department.name }}</h3>
<table class="report-table">
  <thead>
    <tr>
      <th style="width:8%;">STT</th>
      <th style="width:42%; text-align:left;">Chỉ số</th>
      <th style="width:16%;">Kết quả</th>
      <th style="width:14%;">Đơn vị</th>
      <th style="width:20%;">Trị số bình thường</th>
    </tr>
  </thead>
  <tbody>
    {% for field in fields %}
    <tr>
      <td>{{ forloop.counter }}</td>
      <td style="text-align:left;">{{ field.label }}</td>
      <td{% if field.is_abnormal %} class="abnormal"{% endif %}>{% if field.value %}{{ field.value }}{% else %}<span style="color:#999;">--</span>{% endif %}</td>
      <td>{{ field.unit }}</td>
      <td>{{ field.normal_range }}</td>
    </tr>
    {% empty %}
    <tr><td colspan="5"><i>Không có dữ liệu.</i></td></tr>
    {% endfor %}
  </tbody>
</table>
{% if has_abnormal %}
<p style="font-size:8.5pt; margin-top:1mm;">
  <b>Chỉ số bất thường:</b>
  {% for field in abnormal_fields %}{{ field.label }} ({{ field.display }}){% if not forloop.last %}, {% endif %}{% endfor %}
</p>
{% endif %}
"""

# ---------------------------------------------------------------------------
# body_html defaults for the four coded body types
# ---------------------------------------------------------------------------

BODY_HORIZONTAL_TABLE = """\
<table class="report-table clinical-detail">
  <thead>
    <tr>{% for cell in d_header.r1 %}<th colspan="{{ cell.span }}" rowspan="{{ cell.rowspan }}">{{ cell.label }}</th>{% endfor %}</tr>
    <tr>{% for cell in d_header.r2 %}<th colspan="{{ cell.span }}" rowspan="{{ cell.rowspan }}">{{ cell.label }}</th>{% endfor %}</tr>
    <tr>{% for cell in d_header.r3 %}<th>{{ cell.label }}</th>{% endfor %}</tr>
    {% if d_show_range %}<tr class="normal-range-row">{% for cell in d_header.r4 %}<th>{{ cell.label }}</th>{% endfor %}</tr>{% endif %}
  </thead>
  <tbody>
    {% for row in d_rows %}
    <tr>{% for cell in row.cells %}<td{% if cell.abnormal %} class="abnormal"{% endif %}>{{ cell.text }}</td>{% endfor %}</tr>
    {% endfor %}
  </tbody>
</table>
"""

BODY_BLOOD_HORIZONTAL = """\
<table class="report-table blood-test">
  <thead>
    <tr>
      <th rowspan="{% if d_show_range %}2{% else %}1{% endif %}">STT</th>
      <th rowspan="{% if d_show_range %}2{% else %}1{% endif %}">Mã NV</th>
      <th rowspan="{% if d_show_range %}2{% else %}1{% endif %}">Họ và tên</th>
      <th rowspan="{% if d_show_range %}2{% else %}1{% endif %}">Năm sinh</th>
      <th rowspan="{% if d_show_range %}2{% else %}1{% endif %}">Giới</th>
      {% for col in d_columns %}<th>{{ col.label }}{% if col.unit %}<br><span class="unit">({{ col.unit }})</span>{% endif %}</th>{% endfor %}
    </tr>
    {% if d_show_range %}<tr class="normal-range-row">
      {% for col in d_columns %}<th>{{ col.normal_range }}</th>{% endfor %}
    </tr>{% endif %}
  </thead>
  <tbody>
    {% for row in d_rows %}
    <tr>
      <td>{{ row.stt }}</td>
      <td>{{ row.ma_nv }}</td>
      <td class="name">{{ row.ho_ten }}</td>
      <td>{{ row.ngay_sinh }}</td>
      <td>{{ row.gioi_tinh }}</td>
      {% for cell in row.cells %}<td{% if cell.abnormal %} class="abnormal"{% endif %}>{{ cell.text }}</td>{% endfor %}
    </tr>
    {% endfor %}
  </tbody>
</table>
"""

BODY_SUMMARY = """\
<div class="summary-stats">

<table class="report-table stats-overview"><tbody>
<tr><th>Tổng số nhân viên</th><td>{{ s_total }}</td><td></td></tr>
<tr><th>Nam</th><td>{{ s_male }}</td><td>{{ s_male_pct }}</td></tr>
<tr><th>Nữ</th><td>{{ s_female }}</td><td>{{ s_female_pct }}</td></tr>
</tbody></table>

<h3>Phân loại sức khỏe</h3>
<table class="report-table stats-classification">
<thead><tr><th>Phân loại</th><th>Số lượng</th><th>Tỷ lệ</th></tr></thead>
<tbody>
{% for c in s_classifications %}
<tr><td>{{ c.label }}</td><td>{{ c.count }}</td><td>{{ c.pct }}</td></tr>
{% endfor %}
</tbody></table>

{% if s_diseases %}
<h3>Bệnh thường gặp</h3>
<table class="report-table stats-diseases">
<thead><tr><th>STT</th><th>Tên bệnh</th><th>Số ca</th><th>Tỷ lệ</th></tr></thead>
<tbody>
{% for d in s_diseases %}
<tr><td>{{ forloop.counter }}</td><td>{{ d.name }}</td><td>{{ d.count }}</td><td>{{ d.pct }}</td></tr>
{% endfor %}
</tbody></table>
{% endif %}

{% if s_departments %}
<h3>Thống kê theo khoa</h3>
<table class="report-table stats-departments">
<thead><tr><th>Khoa</th><th>Đã khám</th><th>Chỉ số bất thường</th></tr></thead>
<tbody>
{% for d in s_departments %}
<tr><td>{{ d.name }}</td><td>{{ d.examined }}</td><td>{{ d.abnormal }}</td></tr>
{% endfor %}
</tbody></table>
{% endif %}

</div>
"""

BODY_COST = """\
<div class="cost-breakdown">

{% if c_mode == "package_total" %}
<table class="report-table cost-summary"><tbody>
<tr><th>Gói khám</th><td>{{ c_package_name }}</td></tr>
<tr><th>Đơn giá trọn gói</th><td>{{ c_unit_price }} đ</td></tr>
<tr><th>Số nhân viên</th><td>{{ c_total_employees }}</td></tr>
<tr class="total"><th>Tổng cộng</th><td>{{ c_total }} đ</td></tr>
</tbody></table>
{% else %}
<table class="report-table cost-detail">
<thead><tr><th>STT</th><th>Khoa</th><th>Chỉ số</th><th>Đơn giá</th><th>Số lượt</th><th>Thành tiền</th></tr></thead>
<tbody>
{% for line in c_lines %}
<tr><td>{{ forloop.counter }}</td><td>{{ line.dept }}</td><td>{{ line.field }}</td>
    <td>{{ line.unit_price }}</td><td>{{ line.count }}</td><td>{{ line.line_total }}</td></tr>
{% endfor %}
<tr class="total"><td colspan="5">TỔNG CỘNG</td><td>{{ c_grand_total }} đ</td></tr>
</tbody></table>
{% endif %}

{% if c_per_patient %}
<h3>Chi phí theo nhân viên</h3>
<table class="report-table cost-per-patient">
<thead><tr><th>STT</th><th>Họ và tên</th><th>Thành tiền</th></tr></thead>
<tbody>
{% for p in c_per_patient %}
<tr><td>{{ forloop.counter }}</td><td>{{ p.name }}</td><td>{{ p.amount }}</td></tr>
{% endfor %}
</tbody></table>
{% endif %}

</div>
"""

#: name → (department code candidates, body_html, config)
#: ``codes`` are matched case-insensitively against ``Department.code``; the
#: first hit wins. Codes that match nothing leave the template global
#: (department=None) for an admin to bind manually.
BODY_SUMMARY_COVER = """\
<div class="summary-letter">
  <div class="title">BÁO CÁO TỔNG HỢP KẾT QUẢ KHÁM SỨC KHỎE</div>
  <div class="company">{{ company.name }}</div>
  <p>Kính gửi: <b>{{ company.name }}</b></p>
  {% if company.address %}<p>Địa chỉ: {{ company.address }}</p>{% endif %}
  <p>Kính thưa Quý công ty,</p>
  <p>{{ clinic_name }} trân trọng thông báo đợt {{ exam_type|lower }} dành cho cán bộ công nhân viên của Quý công ty đã hoàn tất.</p>
  <p>Thời gian khám: <b>{% if exam_date %}{{ exam_date }}{% else %}Theo kế hoạch của công ty{% endif %}</b>.</p>
  <p>Tổng số cán bộ công nhân viên thực tế tham gia khám: <b>{{ stats.total }}</b> người.</p>
  <p>Báo cáo này tổng hợp tình hình sức khỏe chung, kết quả phân loại sức khỏe và tình hình bệnh tật ghi nhận trong đợt khám.</p>
</div>

<h2>I. TÌNH HÌNH SỨC KHỎE CHUNG</h2>
<p><b>1. Tổng hợp số lượng cán bộ công nhân viên tham gia khám:</b></p>
<ul>
  <li>Tổng số CBNV đến khám: <b>{{ stats.total }}</b> người.</li>
  <li>Nam: <b>{{ stats.male }}</b> người ({{ stats.male_pct }}%).</li>
  <li>Nữ: <b>{{ stats.female }}</b> người ({{ stats.female_pct }}%).</li>
</ul>
<h3>Bảng 1.1: Số CBNV đăng ký khám</h3>
<div class="report-row">
  <div class="report-grid-item" data-column="4" data-width="9">
    {% gender_table %}
  </div>
</div>

<h2>II. BẢNG PHÂN LOẠI SỨC KHỎE</h2>
<p><b>1. Phân loại sức khỏe:</b></p>
<p>(Theo tiêu chuẩn phân loại ban hành tại Quyết định số 1613 BYT/QĐ ngày 15/08/1997 của Bộ Y tế)</p>
<h3>Bảng 2.1: Bảng phân loại sức khỏe của CBNV</h3>
<div class="report-row">
  <div class="report-grid-item" data-column="4" data-width="8">
    {% classification_table %}
  </div>
  <div class="report-grid-item" data-column="12" data-width="4">
    {% classification_chart %}
  </div>
</div>

<h2>III. TÌNH HÌNH BỆNH TẬT</h2>
<h3>Bảng 3.0: Tỷ lệ bình thường và bất thường theo từng nhóm khám</h3>
<div class="report-row">
  <div class="report-grid-item" data-column="1" data-width="10">
    {% group_overview_table %}
  </div>
  <div class="report-grid-item" data-column="11" data-width="5">
    {% group_overview_chart %}
  </div>
</div>
"""

BODY_DEPT_SUMMARY = """\
<h3>3.{{ group_index }}. {{ department.template_name }}</h3>
<div class="report-row">
  <div class="report-grid-item" data-column="4" data-width="9">
    {% dept_summary %}
  </div>
</div>
{% if group.diseases %}
<h3>Bảng 3.{{ group_index }}: Phân loại bệnh lý {{ department.template_name }}</h3>
<div class="report-row">
  <div class="report-grid-item" data-column="1" data-width="9">
    {% dept_disease_table %}
  </div>
  <div class="report-grid-item" data-column="10" data-width="6">
    {% dept_chart type="pie" %}
  </div>
</div>
{% endif %}
"""

BODY_SUMMARY_NARRATIVE = """\
<h2>IV. NHẬN XÉT VÀ ĐỀ NGHỊ</h2>
{% narrative_bullets %}
<h3>Kiến nghị và đề xuất</h3>
<ul>
  <li>Đơn vị đã hỗ trợ và duy trì tốt công tác chăm sóc sức khỏe ban đầu.</li>
  <li>Đoàn khám sức khỏe đã tiến hành khám đảm bảo các quy định về chuyên môn kỹ thuật và quy trình khám sức khỏe theo đúng quy định của Bộ Y tế.</li>
  <li>Kết quả khám đã được phân tích, đánh giá, phân loại sức khỏe cho người lao động.</li>
  <li>Khám sức khỏe định kỳ cho CBCNV theo quy định hiện hành.</li>
  <li>Căn cứ vào kết quả khám sức khỏe định kỳ bố trí công việc phù hợp cho CBCNV.</li>
  <li>Tổ chức cho CBNV có bệnh lý hoặc chỉ số bất thường đi khám chuyên khoa, điều trị và theo dõi theo tư vấn của bác sĩ.</li>
</ul>
"""

DEPARTMENT_TEMPLATES: list[dict[str, Any]] = [
    {
        "name": "Thông tin nhân viên",
        "codes": [],
        "body_html": BODY_PATIENT_HEADER,
        "config": {},
    },
    {
        "name": "Bảng XN máu dọc",
        "codes": ["xet_nghiem", "XN_MAU", "XNMAU", "HUYETHOC"],
        "body_html": BODY_BLOOD_VERTICAL,
        "config": {},
    },
    {
        "name": "Bảng XN nước tiểu",
        "codes": ["xet_nghiem", "XN_NT", "XNNT", "NUOCTIEU"],
        "body_html": BODY_URINE,
        "config": {},
    },
    {
        "name": "Bảng Lâm sàng",
        "codes": ["kham_lam_sang", "LS_TQ", "NOI_TQ", "LAMSANG"],
        "body_html": BODY_CLINICAL,
        "config": {},
    },
    {
        "name": "Bảng Mắt",
        "codes": ["mat", "MAT", "LS_MAT", "KHAM_MAT"],
        "body_html": BODY_EYE,
        "config": {},
    },
    {
        "name": "Bảng TMH-RHM",
        "codes": ["tmh", "rhm", "TMH_RHM", "LS_TMH"],
        "body_html": BODY_ENT_DENTAL,
        "config": {},
    },
    {
        "name": "Bảng chẩn đoán hình ảnh",
        "codes": ["x_quang", "sieu_am", "CDHA"],
        "body_html": BODY_CLINICAL,
        "config": {},
    },
    {
        "name": "Bảng tiền sử bệnh",
        "codes": ["medical_history", "TIEN_SU"],
        "body_html": BODY_CLINICAL,
        "config": {},
    },
    {
        "name": "Kết luận & tư vấn",
        "codes": [],
        "body_html": BODY_CONCLUSION,
        "config": {},
    },
    {
        "name": "Tóm tắt khoa",
        "codes": [],
        "body_html": BODY_PROGRESS,
        "config": {"iterate_departments": True},
    },
    {
        "name": "Bìa + thống kê chung",
        "codes": [],
        "body_html": BODY_SUMMARY_COVER,
        "config": {},
    },
    {
        "name": "Tổng hợp 1 khoa",
        "codes": [],
        "body_html": BODY_DEPT_SUMMARY,
        "config": {"iterate_departments": True},
    },
    {
        "name": "Nhận xét và kiến nghị",
        "codes": [],
        "body_html": BODY_SUMMARY_NARRATIVE,
        "config": {},
    },
]

#: Report-template name → hints used to pin ``ReportTemplateItem.exam_template``
#: when the bound department has more than one data-entry template in play
#: (e.g. "xet_nghiem" hosting both "XN máu" and "XN nước tiểu").
EXAM_TEMPLATE_HINTS: dict[str, list[str]] = {
    "Bảng XN máu dọc": ["máu", "mau", "huyết học", "huyet hoc", "blood"],
    "Bảng XN nước tiểu": ["nước tiểu", "nuoc tieu", "urine"],
}

COMPOSITE_TEMPLATES: list[dict[str, Any]] = [
    {
        "name": "Tổng hợp KSK YCHH",
        "description": "Sổ khám theo từng nhân viên: header + các khoa + kết luận.",
        "report_type": "clinical_detail",
        "body_type": ReportTemplate.BODY_DEPARTMENT_TEMPLATES,
        "body_config": {
            "per_patient": True,
            "page_break_between_patients": True,
            "skip_empty": False,
        },
        "page_size": ReportTemplate.PAGE_A4_PORTRAIT,
        "is_default": False,
        "items": [
            "Thông tin nhân viên",
            "Bảng tiền sử bệnh",
            "Bảng Lâm sàng",
            "Bảng Mắt",
            "Bảng TMH-RHM",
            "Bảng chẩn đoán hình ảnh",
            "Bảng XN máu dọc",
            "Bảng XN nước tiểu",
            "Kết luận & tư vấn",
        ],
    },
    {
        "name": "Bảng chi tiết ngang YCHH",
        "description": "Bảng tổng hợp ngang, 1 dòng/nhân viên — bản HTML của file Excel cũ.",
        "report_type": "clinical_detail",
        "body_type": ReportTemplate.BODY_CLINICAL_DETAIL_TABLE,
        "body_config": {"highlight_abnormal": True, "show_normal_range": True},
        "body_html": BODY_HORIZONTAL_TABLE,
        "page_size": ReportTemplate.PAGE_A3_LANDSCAPE,
        "is_default": True,
        "items": [],
    },
    {
        "name": "Bảng xét nghiệm máu dọc",
        "description": "Mỗi hàng 1 nhân viên, mỗi cột 1 chỉ số xét nghiệm máu.",
        "report_type": "clinical_detail",
        "body_type": ReportTemplate.BODY_CLINICAL_DETAIL_BLOOD_TEST,
        "body_config": {
            "columns": [],
            "highlight_abnormal": True,
            "show_normal_range": True,
            "show_unit": True,
        },
        "body_html": BODY_BLOOD_HORIZONTAL,
        "page_size": ReportTemplate.PAGE_A4_LANDSCAPE,
        "is_default": False,
        "items": [],
    },
    {
        "name": "Thống kê tổng hợp công ty",
        "description": "Số liệu tổng hợp: giới tính, phân loại sức khoẻ, bệnh thường gặp.",
        "report_type": "company_summary",
        "body_type": ReportTemplate.BODY_SUMMARY_STATS,
        "body_config": {"top_diseases": 10, "show_departments": True},
        "body_html": BODY_SUMMARY,
        "page_size": ReportTemplate.PAGE_A4_PORTRAIT,
        "is_default": False,
        "items": [],
    },
    {
        "name": "Báo cáo tổng hợp công ty (chính thức)",
        "description": "Công văn + thống kê I–III theo từng khoa trong gói khám, có biểu đồ.",
        "report_type": "company_summary",
        "body_type": ReportTemplate.BODY_DEPARTMENT_TEMPLATES,
        "body_config": {
            "per_patient": False,
            "per_department": True,
            "skip_empty": True,
        },
        "page_size": ReportTemplate.PAGE_A4_PORTRAIT,
        "is_default": True,
        "items": [
            "Bìa + thống kê chung",
            "Tổng hợp 1 khoa",
            "Nhận xét và kiến nghị",
        ],
    },
    {
        "name": "Bảng chi phí khám",
        "description": "Chi phí theo từng chỉ số hoặc trọn gói.",
        "report_type": "cost",
        "body_type": ReportTemplate.BODY_COST_BREAKDOWN,
        "body_config": {"show_per_patient": False},
        "body_html": BODY_COST,
        "page_size": ReportTemplate.PAGE_A4_PORTRAIT,
        "is_default": True,
        "items": [],
    },
    {
        "name": "Employee Exam Report",
        "description": "Kết quả khám cá nhân: thông tin NV + tiến độ từng khoa.",
        "report_type": "clinical_detail",
        "body_type": ReportTemplate.BODY_DEPARTMENT_TEMPLATES,
        "body_config": {
            "per_patient": True,
            "page_break_between_patients": False,
            "skip_empty": True,
        },
        "page_size": ReportTemplate.PAGE_A4_PORTRAIT,
        "is_default": False,
        "items": [
            "Thông tin nhân viên",
            "Tóm tắt khoa",
            "Kết luận & tư vấn",
        ],
    },
]


class Command(BaseCommand):
    help = "Seed default report templates (header, footer, per-department, composites)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--no-overwrite",
            action="store_true",
            help="Bỏ qua các template đã tồn tại thay vì cập nhật.",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="Chỉ liệt kê template sẽ được tạo, không ghi vào DB.",
        )

    def handle(self, *args, **options) -> None:
        if options["list"]:
            self.stdout.write(self.style.MIGRATE_HEADING("Template khoa:"))
            for d in DEPARTMENT_TEMPLATES:
                codes = ", ".join(d["codes"]) or "(dùng chung)"
                self.stdout.write(f"  • {d['name']}  →  {codes}")
            self.stdout.write(self.style.MIGRATE_HEADING("Template tổng hợp:"))
            for c in COMPOSITE_TEMPLATES:
                self.stdout.write(f"  • {c['name']}  [{c['body_type']}]")
            return

        overwrite = not options["no_overwrite"]
        with transaction.atomic():
            dept_templates = self._seed_department_templates(overwrite)
            self._seed_composites(dept_templates, overwrite)

        self.stdout.write(self.style.SUCCESS("Seed template báo cáo hoàn tất."))

    # -- department templates -------------------------------------------------

    def _seed_department_templates(
        self, overwrite: bool
    ) -> dict[str, DepartmentReportTemplate]:
        created = updated = skipped = 0
        result: dict[str, DepartmentReportTemplate] = {}

        for spec in DEPARTMENT_TEMPLATES:
            department = self._match_department(spec["codes"])
            existing = DepartmentReportTemplate.objects.filter(
                name=spec["name"]
            ).first()

            if existing and not overwrite:
                result[spec["name"]] = existing
                skipped += 1
                continue

            if existing:
                existing.body_html = spec["body_html"]
                existing.config = spec["config"]
                if department and existing.department_id is None:
                    existing.department = department
                existing.save()
                result[spec["name"]] = existing
                updated += 1
            else:
                result[spec["name"]] = DepartmentReportTemplate.objects.create(
                    name=spec["name"],
                    department=department,
                    body_html=spec["body_html"],
                    config=spec["config"],
                )
                created += 1

            bound = result[spec["name"]].department
            self.stdout.write(
                f"  · {spec['name']} → {bound.name if bound else 'dùng chung'}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Template khoa: {created} mới, {updated} cập nhật, {skipped} bỏ qua."
            )
        )
        return result

    def _match_department(self, codes: list[str]) -> Department | None:
        for code in codes:
            dept = Department.objects.filter(code__iexact=code, is_active=True).first()
            if dept:
                return dept
        return None

    def _match_exam_template(
        self, item_name: str, dept_template: DepartmentReportTemplate
    ):
        """
        Pin the data-entry template when a department hosts several of them.

        Returns None when the department has 0 or 1 template (no ambiguity) or
        when no hint matches — in which case every result for the department is
        rendered through this block.
        """
        from examinations.models import DepartmentTemplate

        department = dept_template.department
        if department is None:
            return None

        candidates = list(
            DepartmentTemplate.objects.filter(department=department, is_active=True)
        )
        if len(candidates) < 2:
            return None

        hints = EXAM_TEMPLATE_HINTS.get(item_name, [])
        for hint in hints:
            for candidate in candidates:
                if hint.lower() in candidate.name.lower():
                    self.stdout.write(f"      ↳ ghim mẫu nhập liệu: {candidate.name}")
                    return candidate
        return None

    # -- composite templates --------------------------------------------------

    def _seed_composites(
        self, dept_templates: dict[str, DepartmentReportTemplate], overwrite: bool
    ) -> None:
        created = updated = skipped = 0

        for spec in COMPOSITE_TEMPLATES:
            existing = ReportTemplate.objects.filter(name=spec["name"]).first()
            if existing and not overwrite:
                skipped += 1
                continue

            defaults = {
                "description": spec["description"],
                "report_type": spec["report_type"],
                "body_type": spec["body_type"],
                "body_config": spec["body_config"],
                "body_html": spec.get("body_html", ""),
                "page_size": spec["page_size"],
                "is_default": spec["is_default"],
                "is_active": True,
            }

            if existing:
                for key, value in defaults.items():
                    setattr(existing, key, value)
                existing.save()
                template = existing
                template.items.all().delete()
                updated += 1
            else:
                template = ReportTemplate.objects.create(name=spec["name"], **defaults)
                created += 1

            for order, item_name in enumerate(spec["items"]):
                dept_template = dept_templates.get(item_name)
                if dept_template is None:
                    self.stdout.write(
                        self.style.WARNING(
                            f"    ! Bỏ qua '{item_name}' — chưa có template khoa."
                        )
                    )
                    continue
                ReportTemplateItem.objects.create(
                    report_template=template,
                    department_template=dept_template,
                    department=dept_template.department,
                    exam_template=self._match_exam_template(item_name, dept_template),
                    order=order,
                    page_break_before=False,
                )

            self.stdout.write(f"  · {spec['name']} ({len(spec['items'])} khoa)")

        self.stdout.write(
            self.style.SUCCESS(
                f"Template tổng hợp: {created} mới, {updated} cập nhật, {skipped} bỏ qua."
            )
        )
