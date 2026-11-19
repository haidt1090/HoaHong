from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from accounts.models import CompanyExamPackage
from examinations.models import Examination


def _classification_number(matches: list[dict[str, Any]]) -> int:
    """Most severe classification: 5 (Loại V) > 4 > 3 > 2 > 1; default 1 (Loại I)."""
    if not matches:
        return 1
    classifications = {m["classification"] for m in matches}
    for level in (5, 4, 3, 2, 1):
        if level in classifications:
            return level
    return 1


def _resolve_diagnosis(exam: Examination) -> tuple[int, str, str, str]:
    """
    Return ``(classification, work_fitness, benh_mac, tu_van)``.

    ``classification`` is the health classification number (1-5, Loại I-V);
    ``work_fitness`` is ``fit``/``unfit``.  Stored values (written by the scan
    task or the doctor) win; otherwise they are derived from the diagnosis
    engine on the fly without persisting.
    """
    classification = exam.classification
    matches: list[dict[str, Any]] = []

    if classification is None:
        # Not concluded by the scan yet — derive classification on the fly.
        from diagnosis.services import aggregate_findings, match_diagnosis

        findings = aggregate_findings(exam, skip_known_keywords=False)
        matches = match_diagnosis(findings) if findings.strip() else []
        classification = _classification_number(matches)

    # Bệnh mắc: stored disease text wins, else matched disease names.
    if exam.disease.strip():
        benh_mac = exam.disease
    else:
        seen: list[str] = []
        for m in matches:
            name = m["disease_name"]
            if name and name not in seen:
                seen.append(name)
        benh_mac = ", ".join(seen)

    # Tư vấn: stored consultation wins, else matched templates (comma-joined).
    tu_van = exam.consultation or ", ".join(
        m["conclusion_template"].strip()
        for m in matches
        if m.get("conclusion_template", "").strip()
    )

    # Đủ/không đủ: stored work_fitness wins, else derived from classification.
    if exam.work_fitness != "pending":
        work_fitness = exam.work_fitness
    else:
        work_fitness = "unfit" if (classification is not None and classification >= 4) else "fit"

    return (classification, work_fitness, benh_mac, tu_van)


_WORK_FITNESS_DISPLAY = {
    "pending": "",
    "fit": "Đủ điều kiện lao động",
    "unfit": "Không đủ điều kiện lao động",
}


@dataclass
class FieldColumn:
    field_key: str
    label: str
    unit: str
    normal_range: str
    order: int
    department_name: str
    department_id: str
    template_name: str
    template_id: str
    parent_id: str | None
    parent_name: str | None
    # Raw bounds kept alongside the pre-formatted ``normal_range`` string so
    # the template engine can compute ``is_abnormal`` (Sprint 9a).
    normal_min: float | None = None
    normal_max: float | None = None
    gender_overrides: dict = field(default_factory=dict)
    field_type: str = "text"
    test_category: str = ""
    abnormal_definitions: list[dict[str, str]] = field(default_factory=list)
    # ``order`` is the field's own order within its template; ``binding_order``
    # is the ExamPackageDepartment.order of the slot it came from. Both are
    # needed because one department may be bound twice with different
    # templates (Sprint 4a).
    binding_order: int = 0


@dataclass
class ReportColumn:
    field: FieldColumn | None  # None for personal-info / conclusion columns
    header_personal: str | None  # label for fixed columns (STT, Mã NV, ...)
    merge_parent: bool = False  # R7 merge start
    merge_child: bool = False  # R8 merge start
    parent_span: int = 1  # how many cols this parent spans (R7)
    child_span: int = 1  # how many cols this child spans (R8)


@dataclass
class ReportHeader:
    columns: list[ReportColumn] = field(default_factory=list)


@dataclass
class ReportData:
    headers: ReportHeader
    rows: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Sprint 9a — nested dataset for the dynamic template engine
#
# ``ReportData`` above keeps a *flat* ``{field_key: value}`` row namespace,
# which collides when two departments reuse the same field key (keys are only
# unique per template). The template engine needs per-department nesting plus
# abnormal-value detection, so it consumes ``ReportDataset`` instead.
# ---------------------------------------------------------------------------


@dataclass
class RenderedField:
    """One field of one department for one patient."""

    key: str
    label: str
    value: str
    raw_value: Any
    unit: str
    normal_range: str
    normal_min: float | None
    normal_max: float | None
    field_type: str
    test_category: str
    order: int
    is_abnormal: bool = False
    abnormal_direction: str = ""  # "low" | "high" | ""
    abnormal_label: str = ""
    is_empty: bool = True

    @property
    def display(self) -> str:
        """Value with unit appended, for one-shot template output."""
        if not self.value:
            return ""
        return f"{self.value} {self.unit}".strip()


@dataclass
class RenderedDepartment:
    """One department's results for one patient."""

    id: str
    name: str
    code: str
    category: str
    template_id: str
    template_name: str
    parent_id: str | None
    parent_name: str | None
    order: int
    fields: list[RenderedField] = field(default_factory=list)
    completed_at: Any = None

    @property
    def abnormal_fields(self) -> list[RenderedField]:
        return [f for f in self.fields if f.is_abnormal]

    @property
    def has_abnormal(self) -> bool:
        return any(f.is_abnormal for f in self.fields)

    @property
    def filled_fields(self) -> list[RenderedField]:
        return [f for f in self.fields if not f.is_empty]

    def field(self, key: str) -> RenderedField | None:
        for f in self.fields:
            if f.key == key:
                return f
        return None


@dataclass
class PatientRecord:
    """One examined employee: personal info + per-department results."""

    stt: int
    examination_id: str
    patient_id: str
    so_ho_so: str
    ma_nv: str
    ho_ten: str
    ngay_sinh: str
    tuoi: int | None
    gioi_tinh: str
    gioi_tinh_display: str
    bo_phan: str
    cccd: str
    noi_o: str
    phone: str
    ngay_vao: str
    exam_date: str
    phan_loai: str
    benh_mac: str
    tu_van: str
    ket_luan: str
    doctor_name: str
    status: str
    departments: list[RenderedDepartment] = field(default_factory=list)

    def department(self, department_id: str) -> RenderedDepartment | None:
        for d in self.departments:
            if d.id == str(department_id):
                return d
        return None

    def departments_for(self, department_id: str) -> list[RenderedDepartment]:
        """All results for a department (a department may repeat per Sprint 4a)."""
        return [d for d in self.departments if d.id == str(department_id)]

    @property
    def abnormal_count(self) -> int:
        return sum(len(d.abnormal_fields) for d in self.departments)

    def flat_values(self) -> dict[str, str]:
        """Flat ``{field_key: value}`` map (last writer wins) for table bodies."""
        out: dict[str, str] = {}
        for d in self.departments:
            for f in d.fields:
                if f.value or f.key not in out:
                    out[f.key] = f.value
        return out


@dataclass
class DepartmentSpec:
    """A department slot in the exam package (independent of any patient)."""

    id: str
    name: str
    code: str
    category: str
    template_id: str
    template_name: str
    parent_id: str | None
    parent_name: str | None
    order: int
    fields: list[FieldColumn] = field(default_factory=list)


@dataclass
class ReportDataset:
    """Full payload handed to the template engine."""

    company: Any
    exam_package: Any
    company_exam_package: Any
    departments: list[DepartmentSpec] = field(default_factory=list)
    patients: list[PatientRecord] = field(default_factory=list)
    exam_date: str = ""
    # Legacy flat structure, kept so coded body functions can reuse the
    # existing column-grouping/merge logic.
    table: ReportData | None = None

    @property
    def total_employees(self) -> int:
        return len(self.patients)

    def department_spec(self, department_id: str) -> DepartmentSpec | None:
        for d in self.departments:
            if d.id == str(department_id):
                return d
        return None


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _format_number(value: Decimal | float) -> str:
    """Render a numeric value without scientific notation or trailing zeros."""
    d = Decimal(str(value))
    if d == d.to_integral_value():
        return str(int(d))
    s = format(d, "f")
    return s.rstrip("0").rstrip(".")


def _evaluate_abnormal(
    raw: Any, minimum: float | None, maximum: float | None
) -> tuple[bool, str]:
    """Return ``(is_abnormal, direction)`` for a value against its normal range."""
    number = _to_float(raw)
    if number is None:
        return False, ""
    if minimum is not None and number < minimum:
        return True, "low"
    if maximum is not None and number > maximum:
        return True, "high"
    return False, ""


def _resolve_gender_range(
    minimum: float | None,
    maximum: float | None,
    overrides: dict,
    gender: str | None,
) -> tuple[float | None, float | None]:
    """Resolve normal-range bounds for a gender, using gender_overrides when set."""
    if gender and overrides and overrides.get(gender):
        o = overrides[gender]
        lo = o.get("min")
        hi = o.get("max")
        if lo is not None or hi is not None:
            return (
                _to_float(lo) if lo not in (None, "") else None,
                _to_float(hi) if hi not in (None, "") else None,
            )
    return minimum, maximum


def _build_department_specs(package) -> list[DepartmentSpec]:
    """Collect the department slots + their field metadata for a package."""
    bindings = list(
        package.package_departments.select_related(
            "department", "department__parent", "template"
        )
        .prefetch_related("template__fields__abnormal_definitions")
        .order_by("order")
    )

    specs: list[DepartmentSpec] = []
    for b in bindings:
        dept = b.department
        parent = dept.parent
        tpl = b.template
        cols: list[FieldColumn] = []
        for f in sorted(tpl.fields.all(), key=lambda x: x.order) if tpl else []:
            cols.append(
                FieldColumn(
                    field_key=f.key,
                    label=f.label,
                    unit=f.unit or "",
                    normal_range=_format_normal_range(
                        f.normal_range_min, f.normal_range_max
                    ),
                    order=f.order,
                    department_name=dept.name,
                    department_id=str(dept.id),
                    template_name=tpl.name,
                    template_id=str(tpl.id),
                    parent_id=str(parent.id) if parent else None,
                    parent_name=parent.name if parent else None,
                    normal_min=_to_float(f.normal_range_min),
                    normal_max=_to_float(f.normal_range_max),
                    gender_overrides=f.gender_overrides or {},
                    field_type=f.field_type,
                    test_category=f.test_category or "",
                    abnormal_definitions=[
                        {"direction": ad.direction, "label": ad.label}
                        for ad in f.abnormal_definitions.all()
                    ],
                )
            )
        specs.append(
            DepartmentSpec(
                id=str(dept.id),
                name=dept.name,
                code=dept.code,
                category=dept.category,
                template_id=str(tpl.id) if tpl else "",
                template_name=tpl.name if tpl else dept.name,
                parent_id=str(parent.id) if parent else None,
                parent_name=parent.name if parent else None,
                order=b.order,
                fields=cols,
            )
        )
    return specs


def _format_normal_range(minimum: Any, maximum: Any) -> str:
    parts = []
    if minimum is not None:
        parts.append(_format_number(minimum))
    if maximum is not None:
        parts.append(_format_number(maximum))
    return " - ".join(parts)


def build_report_dataset(
    company_exam_package: CompanyExamPackage,
    exam_date: str | None = None,
) -> ReportDataset:
    """
    Build the nested dataset consumed by the dynamic report template engine.

    ``exam_date`` optionally filters examinations to a single date (the legacy
    ``build_clinical_detail_report`` ignores it).
    """
    package = company_exam_package.exam_package
    specs = _build_department_specs(package)
    # Field metadata indexed by (department_id, template_id) so repeated
    # departments with different templates resolve independently.
    spec_by_slot = {(s.id, s.template_id): s for s in specs}
    spec_by_dept: dict[str, DepartmentSpec] = {}
    for s in specs:
        spec_by_dept.setdefault(s.id, s)

    examinations = (
        Examination.objects.filter(company_exam_package=company_exam_package)
        .select_related("patient__company", "doctor")
        .prefetch_related(
            "department_results__values",
            "department_results__department__parent",
            "department_results__template",
        )
        .order_by("patient__full_name")
    )
    # ``exam_date`` is a display label only — it does NOT filter examinations,
    # matching ``build_clinical_detail_report`` so the nested ``dataset.patients``
    # and the flat ``dataset.table`` stay consistent.

    patients: list[PatientRecord] = []
    for idx, exam in enumerate(examinations, 1):
        patient = exam.patient
        company_code = patient.company.code if patient.company else ""

        rendered_depts: list[RenderedDepartment] = []
        for dr in exam.department_results.all():
            dept = dr.department
            dept_id = str(dept.id)
            template_id = str(dr.template_id) if dr.template_id else ""
            spec = spec_by_slot.get((dept_id, template_id)) or spec_by_dept.get(dept_id)

            values = {v.field_key: v for v in dr.values.all()}
            fields: list[RenderedField] = []

            # Prefer the package spec for field metadata; fall back to the
            # result's own frozen ``template_snapshot`` for departments that
            # are not part of the current package binding.
            metadata = (
                [
                    (
                        c.field_key,
                        c.label,
                        c.unit,
                        c.normal_range,
                        c.normal_min,
                        c.normal_max,
                        c.gender_overrides,
                        c.field_type,
                        c.test_category,
                        c.order,
                        c.abnormal_definitions,
                    )
                    for c in spec.fields
                ]
                if spec and spec.fields
                else _metadata_from_snapshot(dr.template_snapshot)
            )

            gender = patient.gender or None

            for (
                key,
                label,
                unit,
                nrange,
                nmin,
                nmax,
                goverrides,
                ftype,
                tcategory,
                forder,
                adefs,
            ) in metadata:
                nmin, nmax = _resolve_gender_range(nmin, nmax, goverrides, gender)
                if goverrides:
                    nrange = _format_normal_range(nmin, nmax)
                v = values.get(key)
                if v is None:
                    raw: Any = None
                    text = ""
                elif v.value_number is not None:
                    raw = v.value_number
                    text = _format_number(v.value_number)
                else:
                    raw = v.value_text or ""
                    text = v.value_text or ""

                abnormal, direction = _evaluate_abnormal(raw, nmin, nmax)
                abnormal_label = ""
                if abnormal:
                    for ad in adefs or []:
                        if ad.get("direction") == direction and ad.get("label"):
                            abnormal_label = ad["label"]
                            break
                    if not abnormal_label:
                        abnormal_label = label
                fields.append(
                    RenderedField(
                        key=key,
                        label=label,
                        value=text,
                        raw_value=raw,
                        unit=unit,
                        normal_range=nrange,
                        normal_min=nmin,
                        normal_max=nmax,
                        field_type=ftype,
                        test_category=tcategory,
                        order=forder,
                        is_abnormal=abnormal,
                        abnormal_direction=direction,
                        abnormal_label=abnormal_label,
                        is_empty=text == "",
                    )
                )

            rendered_depts.append(
                RenderedDepartment(
                    id=dept_id,
                    name=dept.name,
                    code=dept.code,
                    category=dept.category,
                    template_id=template_id,
                    template_name=dr.template.name if dr.template else dept.name,
                    parent_id=str(dept.parent_id) if dept.parent_id else None,
                    parent_name=dept.parent.name if dept.parent_id else None,
                    order=spec.order if spec else 0,
                    fields=fields,
                    completed_at=dr.completed_at,
                )
            )

        rendered_depts.sort(key=lambda d: (d.order, d.name))

        classification, wf, benh_mac, tu_van = _resolve_diagnosis(exam)

        patients.append(
            PatientRecord(
                stt=idx,
                examination_id=str(exam.id),
                patient_id=str(patient.id),
                so_ho_so=f"{company_code}{idx:03d}",
                ma_nv=patient.employee_code or "",
                ho_ten=patient.full_name,
                ngay_sinh=patient.dob.strftime("%d/%m/%Y") if patient.dob else "",
                tuoi=_age_at(patient.dob, exam.exam_date),
                gioi_tinh=patient.gender or "",
                gioi_tinh_display=(
                    patient.get_gender_display() if patient.gender else ""
                ),
                bo_phan=patient.department or "",
                cccd=patient.cccd or "",
                noi_o=patient.address or "",
                phone=patient.phone or "",
                ngay_vao=(
                    patient.start_date.strftime("%d/%m/%Y")
                    if patient.start_date
                    else ""
                ),
                exam_date=exam.exam_date.strftime("%d/%m/%Y") if exam.exam_date else "",
                phan_loai=str(classification),
                benh_mac=benh_mac,
                tu_van=tu_van,
                ket_luan=_WORK_FITNESS_DISPLAY.get(wf, ""),
                doctor_name=exam.doctor.display_name if exam.doctor else "",
                status=exam.status,
                departments=rendered_depts,
            )
        )

    return ReportDataset(
        company=company_exam_package.company,
        exam_package=package,
        company_exam_package=company_exam_package,
        departments=specs,
        patients=patients,
        exam_date=exam_date or "",
        table=build_clinical_detail_report(company_exam_package),
    )


def _metadata_from_snapshot(snapshot: Any) -> list[tuple]:
    """Derive field metadata from a ``DepartmentResult.template_snapshot``."""
    out: list[tuple] = []
    if not isinstance(snapshot, list):
        return out
    for i, item in enumerate(snapshot):
        if not isinstance(item, dict):
            continue
        nr = item.get("normal_range") or {}
        nmin = _to_float(nr.get("min")) if isinstance(nr, dict) else None
        nmax = _to_float(nr.get("max")) if isinstance(nr, dict) else None
        out.append(
            (
                item.get("key", ""),
                item.get("label", item.get("key", "")),
                item.get("unit", "") or "",
                _format_normal_range(nmin, nmax),
                nmin,
                nmax,
                item.get("gender_overrides", {}) or {},
                item.get("type", "text"),
                item.get("test_category", "") or "",
                item.get("order", i),
                item.get("abnormal_definitions") or [],
            )
        )
    return out


def _age_at(dob: Any, on_date: Any) -> int | None:
    if not dob or not on_date:
        return None
    years = on_date.year - dob.year
    if (on_date.month, on_date.day) < (dob.month, dob.day):
        years -= 1
    return years


def build_clinical_detail_report(
    company_exam_package: CompanyExamPackage,
) -> ReportData:
    package = company_exam_package.exam_package
    bindings = list(
        package.package_departments.select_related(
            "department", "department__parent", "template"
        )
        .prefetch_related("template__fields")
        .order_by("order")
    )

    # ── Step 1: collect flat columns with department hierarchy info ──
    flat_cols: list[FieldColumn] = []
    for b in bindings:
        # Uses the ``template__fields`` prefetch above (previously an N+1 query).
        fields = (
            sorted(b.template.fields.all(), key=lambda x: x.order) if b.template else []
        )
        dept = b.department
        parent = dept.parent
        tpl_name = b.template.name if b.template else dept.name
        tpl_id = str(b.template.id) if b.template else str(dept.id)
        if not fields:
            flat_cols.append(
                FieldColumn(
                    field_key=dept.code,
                    label=dept.name,
                    unit="",
                    normal_range="",
                    order=b.order,
                    department_name=dept.name,
                    department_id=str(dept.id),
                    template_name=tpl_name,
                    template_id=tpl_id,
                    parent_id=str(parent.id) if parent else None,
                    parent_name=parent.name if parent else None,
                    binding_order=b.order,
                )
            )
        else:
            for f in fields:
                flat_cols.append(
                    FieldColumn(
                        field_key=f.key,
                        label=f.label,
                        unit=f.unit or "",
                        normal_range=_format_normal_range(
                            f.normal_range_min, f.normal_range_max
                        ),
                        order=f.order,
                        department_name=dept.name,
                        department_id=str(dept.id),
                        template_name=tpl_name,
                        template_id=tpl_id,
                        parent_id=str(parent.id) if parent else None,
                        parent_name=parent.name if parent else None,
                        normal_min=_to_float(f.normal_range_min),
                        normal_max=_to_float(f.normal_range_max),
                        field_type=f.field_type,
                        test_category=f.test_category or "",
                        binding_order=b.order,
                    )
                )

    # ── Step 2: sort + group by parent (R7) and department (R8) ──
    # Group siblings (same R7 key) together while preserving each group's first
    # appearance position from the package order.
    def _r7_key(c: FieldColumn) -> str:
        return c.parent_id or c.department_id

    r7_first_pos: dict[str, int] = {}
    for pos, c in enumerate(flat_cols):
        key = _r7_key(c)
        if key not in r7_first_pos:
            r7_first_pos[key] = pos

    dept_first_pos: dict[str, int] = {}
    for pos, c in enumerate(flat_cols):
        if c.department_id not in dept_first_pos:
            dept_first_pos[c.department_id] = pos

    flat_cols.sort(
        key=lambda c: (
            r7_first_pos[_r7_key(c)],  # keep R7 group at its first position
            dept_first_pos[c.department_id],  # order departments within the group
            c.binding_order,  # then by package binding (Sprint 4a duplicates)
            c.order,  # then by field order within the template
        )
    )
    # R7 (parent row) groups consecutive columns by parent_id (fallback: department_id).
    # R8 (child row)  groups consecutive columns within each R7 span by department_id.
    # R7 label = parent_name (or department_name if no parent).
    # R8 label = department_name.
    columns: list[ReportColumn] = []

    personal_headers = [
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
    for h in personal_headers:
        columns.append(ReportColumn(field=None, header_personal=h))

    i = 0
    while i < len(flat_cols):
        # R7 group: same parent (or department if no parent)
        r7_key = _r7_key(flat_cols[i])
        parent_start = i
        while i < len(flat_cols) and _r7_key(flat_cols[i]) == r7_key:
            i += 1
        parent_end = i
        parent_span = parent_end - parent_start

        # R8 sub-groups within this parent: same department_id
        k = parent_start
        while k < parent_end:
            r8_key = flat_cols[k].department_id
            child_start = k
            while k < parent_end and flat_cols[k].department_id == r8_key:
                k += 1
            child_end = k
            child_span = child_end - child_start

            for idx in range(child_start, child_end):
                col = ReportColumn(field=flat_cols[idx], header_personal=None)
                col.parent_span = parent_span
                col.child_span = child_span
                col.merge_parent = idx == parent_start
                col.merge_child = idx == child_start
                columns.append(col)

    # Fixed conclusion columns
    conclusion_headers = ["Phân loại sức khỏe", "Bệnh mắc", "Tư vấn", "Kết luận"]
    for h in conclusion_headers:
        columns.append(ReportColumn(field=None, header_personal=h))

    header = ReportHeader(columns=columns)

    # ── Step 3: build data rows ──
    examinations = (
        Examination.objects.filter(
            company_exam_package=company_exam_package,
        )
        .select_related("patient__company")
        .prefetch_related(
            "department_results__values",
            "department_results__department",
        )
        .order_by("patient__full_name")
    )

    rows: list[dict[str, Any]] = []
    for idx, exam in enumerate(examinations, 1):
        patient = exam.patient
        row: dict[str, Any] = {}

        # Look up department result data by field key
        dept_data: dict[str, str] = {}
        for dr in exam.department_results.all():
            for v in dr.values.all():
                if v.value_number is not None:
                    dept_data[v.field_key] = str(float(v.value_number))
                else:
                    dept_data[v.field_key] = v.value_text or ""

        # Personal info
        company_code = patient.company.code if patient.company else ""
        row["stt"] = idx
        row["so_ho_so"] = f"{company_code}{idx:03d}"
        row["ma_nv"] = patient.employee_code
        row["ho_ten"] = patient.full_name
        row["ngay_sinh"] = patient.dob.strftime("%d/%m/%Y") if patient.dob else ""
        row["gioi_tinh"] = patient.get_gender_display() if patient.gender else ""
        row["bo_phan"] = patient.department or ""
        row["cccd"] = patient.cccd
        row["noi_o"] = patient.address or ""
        row["ngay_vao"] = (
            patient.start_date.strftime("%d/%m/%Y") if patient.start_date else ""
        )

        classification, wf, benh_mac, tu_van = _resolve_diagnosis(exam)

        # Department field values
        for col in columns:
            if col.field:
                row[col.field.field_key] = dept_data.get(col.field.field_key, "")
            elif col.header_personal == "Phân loại sức khỏe":
                row["phan_loai"] = str(classification)
            elif col.header_personal == "Bệnh mắc":
                row["benh_mac"] = benh_mac
            elif col.header_personal == "Tư vấn":
                row["tu_van"] = tu_van
            elif col.header_personal == "Kết luận":
                row["ket_luan"] = _WORK_FITNESS_DISPLAY.get(wf, "")

        rows.append(row)

    return ReportData(headers=header, rows=rows)
