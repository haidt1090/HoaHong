"""
Template preview support (Sprint 9a).

Renders a ReportTemplate / DepartmentReportTemplate against either a real
CompanyExamPackage (truncated to a handful of employees) or a synthetic
sample dataset, so authors can iterate without generating a full report.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from accounts.models import Company, CompanyExamPackage
from reports.report_builder import (
    DepartmentSpec,
    FieldColumn,
    PatientRecord,
    RenderedDepartment,
    RenderedField,
    ReportData,
    ReportDataset,
    ReportHeader,
    build_report_dataset,
)


class PreviewDataUnavailable(RuntimeError):
    """Raised when a preview was requested for data that does not exist."""


def _sample_field(
    key: str,
    label: str,
    value: str,
    unit: str = "",
    nmin: float | None = None,
    nmax: float | None = None,
    order: int = 0,
) -> RenderedField:
    from reports.report_builder import _evaluate_abnormal

    abnormal, direction = _evaluate_abnormal(value, nmin, nmax)
    nrange = " - ".join(str(x) for x in (nmin, nmax) if x is not None)
    return RenderedField(
        key=key,
        label=label,
        value=value,
        raw_value=value,
        unit=unit,
        normal_range=nrange,
        normal_min=nmin,
        normal_max=nmax,
        field_type="number" if nmin is not None or nmax is not None else "text",
        test_category="",
        order=order,
        is_abnormal=abnormal,
        abnormal_direction=direction,
        is_empty=value == "",
    )


SAMPLE_DEPARTMENTS: list[dict[str, Any]] = [
    {
        "code": "XN_MAU",
        "name": "Xét nghiệm máu",
        "parent": "Cận lâm sàng",
        "fields": [
            ("hbg", "Hemoglobin", "13.5", "g/dL", 12.0, 16.0),
            ("wbc", "Bạch cầu", "11.2", "10^9/L", 4.0, 10.0),
            ("rbc", "Hồng cầu", "4.7", "10^12/L", 4.2, 5.8),
            ("plt", "Tiểu cầu", "250", "10^9/L", 150.0, 400.0),
            ("glu", "Đường huyết", "5.4", "mmol/L", 3.9, 6.4),
        ],
    },
    {
        "code": "XN_NT",
        "name": "Xét nghiệm nước tiểu",
        "parent": "Cận lâm sàng",
        "fields": [
            ("nt_pro", "Protein", "Âm tính", "", None, None),
            ("nt_glu", "Glucose", "Âm tính", "", None, None),
            ("nt_ph", "pH", "6.0", "", 5.0, 8.0),
        ],
    },
    {
        "code": "LS_TQ",
        "name": "Khám nội tổng quát",
        "parent": "Lâm sàng",
        "fields": [
            ("chieu_cao", "Chiều cao", "168", "cm", None, None),
            ("can_nang", "Cân nặng", "72", "kg", None, None),
            ("bmi", "BMI", "25.5", "", 18.5, 24.9),
            ("huyet_ap", "Huyết áp", "120/80", "mmHg", None, None),
            ("mach", "Mạch", "78", "lần/phút", 60.0, 100.0),
        ],
    },
    {
        "code": "LS_MAT",
        "name": "Khám mắt",
        "parent": "Lâm sàng",
        "fields": [
            ("mat_phai", "Thị lực mắt phải", "10/10", "", None, None),
            ("mat_trai", "Thị lực mắt trái", "8/10", "", None, None),
            ("benh_mat", "Bệnh về mắt", "Không", "", None, None),
        ],
    },
]

SAMPLE_PATIENTS = [
    ("NV001", "Nguyễn Văn An", "15/03/1985", "M", "Sản xuất"),
    ("NV002", "Trần Thị Bình", "22/07/1990", "F", "Kế toán"),
    ("NV003", "Lê Hoàng Cường", "08/11/1982", "M", "Kỹ thuật"),
]


def build_sample_dataset(limit: int = 3) -> ReportDataset:
    """A synthetic dataset for previewing templates without real data."""

    specs: list[DepartmentSpec] = []
    for order, d in enumerate(SAMPLE_DEPARTMENTS):
        dept_id = f"sample-{d['code']}"
        cols = [
            FieldColumn(
                field_key=key,
                label=label,
                unit=unit,
                normal_range=" - ".join(str(x) for x in (nmin, nmax) if x is not None),
                order=i,
                department_name=d["name"],
                department_id=dept_id,
                template_name=f"Mẫu {d['name']}",
                template_id=f"tpl-{d['code']}",
                parent_id=f"parent-{d['parent']}",
                parent_name=d["parent"],
                normal_min=nmin,
                normal_max=nmax,
                field_type="number" if nmin is not None else "text",
                binding_order=order,
            )
            for i, (key, label, _v, unit, nmin, nmax) in enumerate(d["fields"])
        ]
        specs.append(
            DepartmentSpec(
                id=dept_id,
                name=d["name"],
                code=d["code"],
                category=(
                    "para_clinical" if d["parent"] == "Cận lâm sàng" else "clinical"
                ),
                template_id=f"tpl-{d['code']}",
                template_name=f"Mẫu {d['name']}",
                parent_id=f"parent-{d['parent']}",
                parent_name=d["parent"],
                order=order,
                fields=cols,
            )
        )

    patients: list[PatientRecord] = []
    for idx, (code, name, dob, gender, unit_name) in enumerate(
        SAMPLE_PATIENTS[:limit], 1
    ):
        rendered: list[RenderedDepartment] = []
        for order, d in enumerate(SAMPLE_DEPARTMENTS):
            rendered.append(
                RenderedDepartment(
                    id=f"sample-{d['code']}",
                    name=d["name"],
                    code=d["code"],
                    category=(
                        "para_clinical" if d["parent"] == "Cận lâm sàng" else "clinical"
                    ),
                    template_id=f"tpl-{d['code']}",
                    template_name=f"Mẫu {d['name']}",
                    parent_id=f"parent-{d['parent']}",
                    parent_name=d["parent"],
                    order=order,
                    fields=[
                        _sample_field(key, label, value, unit, nmin, nmax, i)
                        for i, (key, label, value, unit, nmin, nmax) in enumerate(
                            d["fields"]
                        )
                    ],
                )
            )
        patients.append(
            PatientRecord(
                stt=idx,
                examination_id=f"sample-exam-{idx}",
                patient_id=f"sample-patient-{idx}",
                so_ho_so=f"MAU{idx:03d}",
                ma_nv=code,
                ho_ten=name,
                ngay_sinh=dob,
                tuoi=date.today().year - int(dob.split("/")[-1]),
                gioi_tinh=gender,
                gioi_tinh_display="Nam" if gender == "M" else "Nữ",
                bo_phan=unit_name,
                cccd=f"0790000000{idx:02d}",
                noi_o="123 Đường Mẫu, Phường 1, TP. HCM",
                phone="0900000000",
                ngay_vao="01/01/2020",
                exam_date=date.today().strftime("%d/%m/%Y"),
                phan_loai="2" if idx == 1 else "",
                benh_mac="Thiếu máu nhẹ" if idx == 1 else "",
                tu_van="Bổ sung sắt, tái khám sau 3 tháng" if idx == 1 else "",
                ket_luan="Đủ điều kiện lao động",
                doctor_name="BS. Nguyễn Thị Mẫu",
                status="completed",
                departments=rendered,
            )
        )

    sample_company = Company(
        name="CÔNG TY MẪU ABC",
        code="MAU",
        address="456 Đường Demo, Quận 1, TP. HCM",
        tax_code="0123456789",
        contact_person="Phòng Nhân sự",
        contact_phone="0281234567",
    )

    from examinations.models import ExamPackage

    sample_package = ExamPackage(
        name="Khám sức khoẻ định kỳ 2026",
        exam_type="periodic",
    )

    dataset = ReportDataset(
        company=sample_company,
        exam_package=sample_package,
        company_exam_package=None,
        departments=specs,
        patients=patients,
        exam_date=date.today().strftime("%d/%m/%Y"),
        table=_sample_table(specs, patients),
    )
    return dataset


def _sample_table(
    specs: list[DepartmentSpec], patients: list[PatientRecord]
) -> ReportData:
    """Build the flat legacy table for sample data so table bodies work."""
    from reports.report_builder import ReportColumn

    columns: list[ReportColumn] = []
    personal = [
        "STT",
        "Số hồ sơ",
        "Mã NV",
        "Họ và tên",
        "Ngày sinh",
        "Giới tính",
        "Bộ phận",
        "CCCD",
        "Nơi ở hiện tại",
        "Ngày bắt đầu làm việc",
    ]
    for h in personal:
        columns.append(ReportColumn(field=None, header_personal=h))

    # Group by parent so the merged header rows mirror a real report.
    grouped: dict[str, list[DepartmentSpec]] = {}
    for s in specs:
        grouped.setdefault(s.parent_id or s.id, []).append(s)

    for group in grouped.values():
        parent_span = sum(len(s.fields) for s in group)
        first_of_parent = True
        for spec in group:
            for i, col in enumerate(spec.fields):
                c = ReportColumn(field=col, header_personal=None)
                c.parent_span = parent_span
                c.child_span = len(spec.fields)
                c.merge_parent = first_of_parent and i == 0
                c.merge_child = i == 0
                columns.append(c)
            first_of_parent = False

    for h in ["Phân loại sức khỏe", "Bệnh mắc", "Tư vấn", "Kết luận"]:
        columns.append(ReportColumn(field=None, header_personal=h))

    rows: list[dict[str, Any]] = []
    for p in patients:
        row: dict[str, Any] = {
            "stt": p.stt,
            "so_ho_so": p.so_ho_so,
            "ma_nv": p.ma_nv,
            "ho_ten": p.ho_ten,
            "ngay_sinh": p.ngay_sinh,
            "gioi_tinh": p.gioi_tinh_display,
            "bo_phan": p.bo_phan,
            "cccd": p.cccd,
            "noi_o": p.noi_o,
            "ngay_vao": p.ngay_vao,
            "phan_loai": p.phan_loai,
            "benh_mac": p.benh_mac,
            "tu_van": p.tu_van,
            "ket_luan": p.ket_luan,
        }
        row.update(p.flat_values())
        rows.append(row)

    return ReportData(headers=ReportHeader(columns=columns), rows=rows)


def build_preview_dataset(
    company_id: Any = None,
    exam_package_id: Any = None,
    exam_date: Any = None,
    limit: int = 3,
) -> ReportDataset:
    """
    Real data when a company+package is given, otherwise the sample dataset.

    The patient list is truncated to ``limit`` so previews stay fast.
    """
    if not (company_id and exam_package_id):
        return build_sample_dataset(limit=limit)

    try:
        cep = CompanyExamPackage.objects.select_related("company", "exam_package").get(
            company_id=company_id, exam_package_id=exam_package_id
        )
    except CompanyExamPackage.DoesNotExist:
        raise PreviewDataUnavailable("Công ty chưa được gán gói khám này.") from None

    dataset = build_report_dataset(cep, exam_date=str(exam_date) if exam_date else None)
    if not dataset.patients:
        raise PreviewDataUnavailable("Chưa có dữ liệu khám cho công ty/gói khám này.")
    dataset.patients = dataset.patients[:limit]
    if dataset.table is not None:
        dataset.table.rows = dataset.table.rows[:limit]
    return dataset
