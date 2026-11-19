"""
Department-driven template models — Phase 2, Sprint 4.

Replaces the old fixed-section ExamTemplate with a dynamic, department-driven
system. Each :class:`Department` owns its own tabular field definitions via
:class:`DepartmentTemplate`. Each field is a :class:`DepartmentField` row
(indexed, searchable) rather than a JSON array. Departments are grouped into
:class:`ExamPackage` (gói khám) for company registration through
:class:`ExamPackageDepartment`, which freezes the template version.
"""

from __future__ import annotations

import json
import math
import random
import re
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from core.models import BaseModel, VersionedModel
from examinations.field_scope import (
    APPLIES_TO_ALL,
    APPLIES_TO_CHOICES,
    field_applies_to_gender,
    should_seed_field,
)
from examinations.input_formats import (
    INPUT_FORMAT_BP_SLASH,
    INPUT_FORMAT_CHOICES,
    apply_formats_to_data,
    apply_input_format,
)

# Department categories drive the department-level RBAC in core.permissions.
DEPARTMENT_CATEGORY_CLINICAL = "clinical"
DEPARTMENT_CATEGORY_PARACLINICAL = "para_clinical"

DEPARTMENT_CATEGORY_CHOICES = [
    (DEPARTMENT_CATEGORY_CLINICAL, "Lâm sàng"),
    (DEPARTMENT_CATEGORY_PARACLINICAL, "Cận lâm sàng"),
]


class Department(BaseModel):
    """
    A medical department a patient can be examined in.

    Examples: "Khám lâm sàng", "Xét nghiệm máu", "X-Quang", "Siêu âm".
    Supports hierarchical structure via ``parent`` FK. Templates, exam
    packages, results, and RBAC bind to leaf departments only.

    The ``category`` field feeds department-level role locking: nurses edit
    clinical departments, lab technicians edit para-clinical ones.
    """

    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
        help_text="Parent department for hierarchical grouping.",
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    category = models.CharField(
        max_length=20,
        choices=DEPARTMENT_CATEGORY_CHOICES,
        default=DEPARTMENT_CATEGORY_CLINICAL,
        help_text="Nhóm khoa: quyết định quyền chỉnh sửa theo vai trò",
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"

    @classmethod
    def build_tree(cls, queryset=None):
        """Build a nested tree from a flat department queryset."""
        if queryset is None:
            queryset = cls.objects.filter(is_active=True).order_by("name")
        all_deps = {
            d.pk: {
                "id": str(d.pk),
                "name": d.name,
                "code": d.code,
                "category": d.category,
                "parent_id": str(d.parent_id) if d.parent_id else None,
                "children": [],
            }
            for d in queryset
        }
        roots = []
        for d in queryset:
            node = all_deps[d.pk]
            if d.parent_id and d.parent_id in all_deps:
                all_deps[d.parent_id]["children"].append(node)
            else:
                roots.append(node)
        return roots

    def get_descendants(self, include_self=False):
        """Return a QuerySet of all descendant departments using recursive CTE."""
        from django.db.models.expressions import RawSQL

        return Department.objects.raw(
            """
            WITH RECURSIVE tree AS (
                SELECT id FROM examinations_department WHERE id = %s
                UNION ALL
                SELECT d.id FROM examinations_department d
                INNER JOIN tree t ON d.parent_id = t.id
            )
            SELECT * FROM examinations_department WHERE id IN (
                SELECT id FROM tree
                UNION ALL SELECT %s WHERE %s
            )
            """,
            [self.pk, self.pk, include_self],
        )

    def get_ancestors(self, include_self=False):
        """Return a list of ancestor departments from nearest to root."""
        ancestors = []
        current = self.parent if not include_self else self
        while current is not None:
            ancestors.append(current)
            current = current.parent
        return ancestors


class DepartmentTemplate(BaseModel):
    """
    A tabular form definition for a department.

    ``version`` is incremented on every content update so that existing
    packages can keep referencing an older, frozen version. Individual field
    definitions are stored as :class:`DepartmentField` rows (searchable,
    indexed) rather than a JSON array. The ``fields_config`` property
    re-serializes those rows into the legacy JSON shape for the render API
    and ``DepartmentResult.template_snapshot``.
    """

    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="templates",
    )
    name = models.CharField(max_length=255)
    version = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_department_templates",
    )

    class Meta:
        ordering = ["department__name", "name"]

    def __str__(self) -> str:
        return f"{self.name} v{self.version}"

    @property
    def fields_config(self) -> list[dict[str, Any]]:
        """Serialize related :class:`DepartmentField` rows into the legacy
        ``fields_config`` JSON array shape used by the render API and
        ``DepartmentResult.template_snapshot``."""
        return [f.as_config() for f in self.fields.all()]


# Gender codes accepted in ``DepartmentField.gender_overrides``. Mirrors
# ``patients.models.Patient.GENDER_CHOICES``, kept literal to avoid a circular
# import between the examinations and patients apps.
GENDER_OVERRIDE_KEYS = ("M", "F")
#: Default discrete step when a gender override has min/max but omits ``step``.
DEFAULT_GENDER_OVERRIDE_STEP = 0.1


def _parse_bound(raw: Any, gender: str, bound: str) -> float:
    """Parse one gender-override bound into a float.

    The admin editor collects bounds from text inputs, so ``"1.5"`` is the
    normal case: the dot is the decimal separator.

    A comma is accepted as the decimal separator (``"1,5"`` → 1.5) only where
    it cannot be mistaken for digit grouping. ``"1,500.5"`` is unambiguous —
    the dot marks the decimals, so the comma groups thousands → 1500.5. But
    ``"2,000"`` alone could mean either 2 or 2000, and guessing would quietly
    store a wrong reference range, so it is rejected instead.
    """
    if isinstance(raw, bool):
        raise ValidationError(f"{bound} ({gender}) không phải là số.")
    if isinstance(raw, (int, float)):
        value = float(raw)
    else:
        text = str(raw).strip().replace(" ", "")
        if "." in text and "," in text:
            text = text.replace(",", "")
        elif "," in text:
            if text.count(",") > 1 or re.fullmatch(r"[+-]?\d+,\d{3}", text):
                raise ValidationError(
                    f'Giá trị "{raw}" của {bound} ({gender}) không rõ ràng — '
                    "dùng dấu chấm cho phần thập phân (ví dụ 1.5)."
                )
            text = text.replace(",", ".")
        try:
            value = float(text)
        except ValueError:
            raise ValidationError(
                f'Giá trị "{raw}" của {bound} ({gender}) không phải là số.'
            ) from None
    if not math.isfinite(value):
        raise ValidationError(f"{bound} ({gender}) phải là số hữu hạn.")
    return value


def build_step_grid(lo: float, hi: float, step: float) -> list[float]:
    """Return ``[lo, lo+step, …]`` up to ``hi`` (inclusive when it lands on the grid).

    Uses :class:`~decimal.Decimal` so values like ``0.2`` do not drift off the
    intended sequence (``3.5, 3.7, …, 7.5``).
    """
    if step <= 0 or hi < lo:
        return []
    start = Decimal(str(lo))
    end = Decimal(str(hi))
    delta = Decimal(str(step))
    values: list[float] = []
    current = start
    # Hard cap prevents runaway loops on tiny steps.
    for _ in range(100_001):
        if current > end:
            break
        values.append(float(current))
        current += delta
    return values


def random_in_range(
    lo: float, hi: float, step: float | None = None
) -> float:
    """Pick a number in ``[lo, hi]``; with ``step > 0`` choose from the discrete grid."""
    if step is not None and step > 0:
        grid = build_step_grid(lo, hi, step)
        if grid:
            return random.choice(grid)
    return round(random.uniform(float(lo), float(hi)), 2)


_BLANK_STRINGS = frozenset(
    {
        "",
        "null",
        "none",
        "nil",
        "n/a",
        "na",
        "#n/a",
        "#null!",
        "-",
        "–",
        "—",
    }
)


def is_blank_value(value: Any) -> bool:
    """True for empty import/API values that should be seeded or skipped.

    Treats ``None``, whitespace, ``NaN``, and common Excel placeholders
    (``null``, ``N/A``, ``-``) as blank. Numeric ``0`` is a real value.
    """
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str):
        return value.strip().lower() in _BLANK_STRINGS
    return False


def normalize_gender_overrides(value: Any) -> dict[str, dict[str, Any]]:
    """Coerce a ``gender_overrides`` payload into numeric ``min`` / ``max`` / ``step``.

    Bounds entered in the admin arrive as strings. Stored raw they force every
    consumer to coerce before comparing or computing — and in JavaScript
    ``"4.5" + 1`` concatenates instead of adding.

    Legacy ``default`` keys are dropped (fixed seeds use field-level
    ``default_value``; random seeds use ``step``, defaulting to
    :data:`DEFAULT_GENDER_OVERRIDE_STEP` when omitted at runtime).
    """
    if not value:
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            raise ValidationError("Gender overrides phải là JSON hợp lệ.") from None
    if not isinstance(value, dict):
        raise ValidationError("Gender overrides phải là một object JSON.")

    cleaned: dict[str, dict[str, Any]] = {}
    for gender, override in value.items():
        if gender not in GENDER_OVERRIDE_KEYS:
            raise ValidationError(
                f'Giới tính "{gender}" không hợp lệ '
                f'(chỉ nhận {" / ".join(GENDER_OVERRIDE_KEYS)}).'
            )
        if not isinstance(override, dict):
            raise ValidationError(f"Cấu hình cho {gender} phải là một object JSON.")

        entry: dict[str, Any] = {}
        for bound in ("min", "max"):
            raw = override.get(bound)
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                continue
            entry[bound] = _parse_bound(raw, gender, bound)

        step_raw = override.get("step")
        if step_raw is not None and not (
            isinstance(step_raw, str) and not step_raw.strip()
        ):
            step = _parse_bound(step_raw, gender, "step")
            if step <= 0:
                raise ValidationError(f"step ({gender}) phải lớn hơn 0.")
            entry["step"] = step

        if "min" in entry and "max" in entry and entry["min"] > entry["max"]:
            raise ValidationError(
                f"Khoảng của {gender} không hợp lệ: min ({entry['min']}) "
                f"lớn hơn max ({entry['max']})."
            )
        if entry:
            cleaned[gender] = entry
    return cleaned


class DepartmentField(BaseModel):
    """One column (field) in a department's tabular form.

    Stored as a table row — not buried in a JSON array — so that each field
    can be indexed, queried, and searched efficiently (e.g. "all templates
    with a hemoglobin field", "fields where test_category = 'blood'").

    The ``as_config()`` method exports the field in the same dict shape
    previously used by ``fields_config``, keeping the render API and
    ``template_snapshot`` output identical.
    """

    FIELD_TYPES = [
        ("text", "Text"),
        ("number", "Number"),
        ("select", "Select"),
        ("multi_select", "Multi-select"),
        ("boolean", "Boolean"),
        ("date", "Date"),
        ("textarea", "Textarea"),
        ("computed", "Computed"),
    ]

    template = models.ForeignKey(
        DepartmentTemplate,
        on_delete=models.CASCADE,
        related_name="fields",
    )
    key = models.CharField(max_length=100)
    label = models.CharField(max_length=255)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES, default="text")
    unit = models.CharField(max_length=50, blank=True)
    required = models.BooleanField(default=False)
    order = models.IntegerField(default=0)
    normal_range_min = models.DecimalField(
        max_digits=15, decimal_places=4, null=True, blank=True
    )
    normal_range_max = models.DecimalField(
        max_digits=15, decimal_places=4, null=True, blank=True
    )
    default_value = models.CharField(max_length=55, blank=True, default="")
    gender_overrides = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Khoảng theo giới tính: {\"M\": {\"min\": 3.5, \"max\": 7.5, "
            "\"step\": 0.2}, \"F\": {...}}. Khi random seed, chọn trên lưới "
            "min + n×step (mặc định step=0.1 nếu bỏ trống). Seed cố định dùng "
            "default_value của trường."
        ),
    )
    default_price = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    test_category = models.CharField(max_length=50, blank=True)
    options = models.JSONField(default=list, blank=True)
    placeholder = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Gợi ý hiển thị khi ô trống (ví dụ: '110/70' cho huyết áp).",
    )
    formula = models.TextField(
        blank=True,
        default="",
        help_text="Expression using {field_key} references. Example: {weight} / (({height} / 100) ^ 2). "
        "Supports IF(condition, true_val, false_val).",
    )
    input_format = models.CharField(
        max_length=32,
        blank=True,
        default="",
        choices=INPUT_FORMAT_CHOICES,
        help_text=(
            "Định dạng nhập liệu (không phụ thuộc key). "
            "bp_slash: số nguyên 4–5 chữ số → chèn / trước 2 số cuối "
            "(11280 → 112/80). Áp dụng khi rời ô và khi import Excel."
        ),
    )
    applies_to = models.CharField(
        max_length=8,
        choices=APPLIES_TO_CHOICES,
        default=APPLIES_TO_ALL,
        help_text=(
            "Giới tính được áp dụng. 'Nữ' = không seed/không bắt buộc "
            "với nam (ví dụ siêu âm bụng). 'Nam' tương tự cho nữ."
        ),
    )

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "key"],
                name="unique_field_key_per_template",
            )
        ]
        indexes = [
            models.Index(fields=["key"]),
            models.Index(fields=["template", "order"]),
        ]

    def __str__(self) -> str:
        return f"{self.template.name} / {self.key}"

    def clean(self) -> None:
        super().clean()
        try:
            self.gender_overrides = normalize_gender_overrides(self.gender_overrides)
        except ValidationError as exc:
            raise ValidationError({"gender_overrides": exc.messages}) from exc
        if self.input_format == INPUT_FORMAT_BP_SLASH and self.field_type not in (
            "text",
            "textarea",
        ):
            raise ValidationError(
                {
                    "input_format": (
                        "Định dạng huyết áp (bp_slash) chỉ dùng cho trường text/textarea."
                    )
                }
            )

    def save(self, *args: Any, **kwargs: Any) -> None:
        # clean() only runs for admin/model forms; normalise here so the API,
        # fixtures and shell writes cannot store string bounds either.
        self.gender_overrides = normalize_gender_overrides(self.gender_overrides)
        super().save(*args, **kwargs)

    def as_config(self) -> dict[str, Any]:
        """Return this field as a ``fields_config``-style dict entry."""
        cfg: dict[str, Any] = {
            "key": self.key,
            "label": self.label,
            "type": self.field_type,
            "order": self.order,
            "required": self.required,
        }
        if self.unit:
            cfg["unit"] = self.unit
        if self.normal_range_min is not None or self.normal_range_max is not None:
            nr: dict[str, Any] = {}
            if self.normal_range_min is not None:
                nr["min"] = float(self.normal_range_min)
            if self.normal_range_max is not None:
                nr["max"] = float(self.normal_range_max)
            cfg["normal_range"] = nr
        if self.default_value:
            cfg["default_value"] = self.default_value
        if self.default_price:
            cfg["default_price"] = int(self.default_price)
        if self.test_category:
            cfg["test_category"] = self.test_category
        if self.options:
            cfg["options"] = self.options
        if self.placeholder:
            cfg["placeholder"] = self.placeholder
        if self.abnormal_definitions.exists():
            cfg["abnormal_definitions"] = [
                {"direction": ad.direction, "label": ad.label}
                for ad in self.abnormal_definitions.all()
            ]
        if self.formula:
            cfg["formula"] = self.formula
        if self.input_format:
            cfg["input_format"] = self.input_format
        if self.applies_to and self.applies_to != APPLIES_TO_ALL:
            cfg["applies_to"] = self.applies_to
        if self.gender_overrides:
            cfg["gender_overrides"] = self.gender_overrides
        return cfg

    def resolve_normal_range(self, gender: str | None):
        """Return ``(min, max)`` for the given gender, falling back to the
        field's base normal range when no gender-specific override exists."""
        if gender:
            override = (self.gender_overrides or {}).get(gender)
            if override:
                lo = override.get("min")
                hi = override.get("max")
                if lo is not None or hi is not None:
                    return (
                        float(lo) if lo not in (None, "") else None,
                        float(hi) if hi not in (None, "") else None,
                    )
        lo = self.normal_range_min
        hi = self.normal_range_max
        return (
            float(lo) if lo is not None else None,
            float(hi) if hi is not None else None,
        )

    def resolve_default_value(self, gender: str | None = None) -> str:
        """Return the field-level ``default_value`` (gender overrides use ``step`` for random)."""
        return self.default_value or ""


class DepartmentFieldAbnormal(BaseModel):
    """
    Defines what an out-of-range numeric value means, linking a field to a
    human-readable label and optionally a DiagnosisKeyword.

    Each field can have at most one ``low`` and one ``high`` definition.
    """

    DIRECTION_CHOICES = [("low", "Dưới ngưỡng"), ("high", "Trên ngưỡng")]

    field = models.ForeignKey(
        DepartmentField,
        on_delete=models.CASCADE,
        related_name="abnormal_definitions",
    )
    direction = models.CharField(max_length=5, choices=DIRECTION_CHOICES)
    label = models.CharField(
        max_length=255, help_text="Ví dụ: 'Nhịp tim chậm', 'Tăng men gan'"
    )
    keyword = models.ForeignKey(
        "diagnosis.DiagnosisKeyword",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="abnormal_definitions",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["field", "direction"],
                name="unique_abnormal_per_field",
            )
        ]

    def __str__(self) -> str:
        return f"{self.field.key}: {self.get_direction_display()} → {self.label}"


class ExamPackage(BaseModel):
    """A named group of departments (gói khám) offered for an exam type."""

    EXAM_TYPES = [
        ("periodic", "Khám định kỳ"),
        ("occupational", "Khám nghề nghiệp"),
        ("job_placement", "Khám bố trí nghề nghiệp"),
        ("labor_under18", "Khám lao động dưới 18"),
        ("labor_over18", "Khám lao động trên 18"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    exam_type = models.CharField(max_length=50, choices=EXAM_TYPES)
    departments = models.ManyToManyField(
        Department,
        through="ExamPackageDepartment",
        related_name="exam_packages",
    )
    default_package_price = models.DecimalField(
        max_digits=12, decimal_places=0, null=True, blank=True
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ExamPackageDepartment(BaseModel):
    """
    Through model binding a department (and a frozen template version) to a
    package, with an explicit display ``order``.
    """

    exam_package = models.ForeignKey(
        ExamPackage,
        on_delete=models.CASCADE,
        related_name="package_departments",
    )
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    template = models.ForeignKey(DepartmentTemplate, on_delete=models.PROTECT)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["exam_package", "department", "template"],
                name="unique_department_per_package",
            )
        ]

    def __str__(self) -> str:
        return f"{self.exam_package.name} → {self.department.name}"


# ---------------------------------------------------------------------------
# Examination entry — Phase 2, Sprint 5
# ---------------------------------------------------------------------------


class Examination(VersionedModel):
    """
    A single health examination for a patient.

    An examination groups one :class:`DepartmentResult` per department in the
    chosen package. Exam-level fields (conclusion, disease, doctor, status) are
    edited by the doctor; per-department data is edited by the assigned staff.

    ``version`` (from :class:`VersionedModel`) auto-increments on save for
    offline sync conflict resolution.
    """

    STATUS_DRAFT = "draft"
    STATUS_COMPLETED = "completed"
    STATUS_CONFIRMED = "confirmed"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Nháp"),
        (STATUS_COMPLETED, "Hoàn thành"),
        (STATUS_CONFIRMED, "Xác nhận"),
    ]

    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.CASCADE,
        related_name="examinations",
    )
    # Set when the company (and its priced package) is known — Sprint 6a.
    company_exam_package = models.ForeignKey(
        "accounts.CompanyExamPackage",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="examinations",
    )
    # Snapshot of which package's departments spawned this exam's results.
    exam_package = models.ForeignKey(
        ExamPackage,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="examinations",
    )
    exam_type = models.CharField(max_length=50, choices=ExamPackage.EXAM_TYPES)
    exam_date = models.DateField(default=timezone.localdate)
    consultation = models.TextField(blank=True, help_text="Tư vấn từ kết quả chẩn đoán")
    conclusion = models.TextField(blank=True, help_text="Kết luận tự do của bác sĩ")
    work_fitness = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Chưa kết luận"),
            ("fit", "Đủ điều kiện lao động"),
            ("unfit", "Không đủ điều kiện lao động"),
        ],
        default="pending",
        help_text="Kết luận đáp ứng điều kiện lao động; tự động mặc định "
        "'unfit' khi phân loại bệnh mắc = 1",
    )
    disease = models.TextField(
        blank=True,
        help_text="Bệnh mắc — danh sách tên bệnh, tự động từ chẩn đoán (không còn M2M)",
    )
    classification = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Phân loại sức khỏe 1-5 (Loại I→V). Tự động từ chẩn đoán hoặc bác sĩ cập nhật.",
    )
    auto_diagnosed = models.BooleanField(
        default=False,
        help_text=(
            "Đánh dấu kết luận (work_fitness/disease/consultation) được sinh tự "
            "động bởi scan chẩn đoán, chưa có bác sĩ duyệt."
        ),
    )
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="examinations",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
    )
    # ``embedding`` VectorField (384d) is added in Phase 3 (Sprint 8).

    class Meta:
        ordering = ["-exam_date", "-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["exam_date"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["patient", "exam_package"],
                name="unique_patient_exam_package",
            )
        ]

    def __str__(self) -> str:
        return f"{self.patient.full_name} — {self.exam_date} ({self.status})"

    def all_departments_filled(self) -> bool:
        """Return True when every DepartmentResult has data for every field
        in its template_snapshot that applies to the patient."""
        dept_results = list(self.department_results.all())
        if not dept_results:
            return False
        gender = None
        try:
            if self.patient_id:
                gender = self.patient.gender
        except AttributeError:
            gender = None
        for dr in dept_results:
            snapshot = dr.template_snapshot or []
            data = dr.data or {}
            for col in snapshot:
                key = col.get("key")
                if not key:
                    continue
                if not field_applies_to_gender(col, gender):
                    continue
                value = data.get(key)
                if value is None or value == "":
                    return False
        return True

    def recompute_status(self) -> str | None:
        """Auto-update status based on department completeness.

        - confirmed: stay confirmed (locked)
        - all departments filled → completed
        - otherwise → draft
        Returns the new status, or None if unchanged.
        """
        if self.status == self.STATUS_CONFIRMED:
            return None
        target = (
            self.STATUS_COMPLETED
            if self.all_departments_filled()
            else self.STATUS_DRAFT
        )
        if self.status == target:
            return None
        self.status = target
        self.save(update_fields=["status", "version", "updated_at"])
        return target

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk is None:
            super().save(*args, **kwargs)
            return
        super().save(*args, **kwargs)


class DepartmentResult(VersionedModel):
    """
    One department's tabular result within an examination.

    Created automatically (one per package department) when the examination is
    created. ``template_snapshot`` freezes the department template's
    ``fields_config`` at creation time so the form layout never shifts if the
    template is later edited. Individual field values are stored as
    :class:`DepartmentResultValue` rows (indexed, searchable) rather than a
    JSON dict. The ``data`` property re-serializes them into the legacy
    ``{field_key: value}`` shape for backward compatibility.
    """

    examination = models.ForeignKey(
        Examination,
        on_delete=models.CASCADE,
        related_name="department_results",
    )
    department = models.ForeignKey(Department, on_delete=models.PROTECT)
    template = models.ForeignKey(
        DepartmentTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="department_results",
    )
    template_snapshot = models.JSONField(default=list)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_department_results",
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["examination", "department__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["examination", "department", "template"],
                name="unique_department_per_examination",
            )
        ]

    def __str__(self) -> str:
        return f"{self.examination_id} / {self.department.name}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        super().save(*args, **kwargs)
        if self.examination_id:
            try:
                self.examination.recompute_status()
            except Examination.DoesNotExist:
                pass

    @property
    def data(self) -> dict[str, Any]:
        """Serialize :class:`DepartmentResultValue` rows back into the legacy
        ``{field_key: value}`` dict shape."""
        result: dict[str, Any] = {}
        for val in self.values.all():
            if val.value_number is not None:
                result[val.field_key] = float(val.value_number)
            else:
                result[val.field_key] = val.value_text
        return result

    def _sync_values(self, data: dict[str, Any], randomize: bool = True) -> None:
        """Replace all values with entries from *data*, resolving types
        against ``template_snapshot``.

        Fields that are missing (or empty) in *data* fall back to their
        template ``default_value``. When no default exists, empty numeric
        fields with a normal range are filled with a random value within
        ``[min, max]`` (``randomize=True``, the default). Gender overrides
        use a discrete ``step`` (default ``0.1`` when omitted): ``min + n×step``.
        """
        snap = {f["key"]: f for f in self.template_snapshot or []}
        merged: dict[str, Any] = {}

        gender = None
        try:
            if self.examination_id and self.examination.patient_id:
                gender = self.examination.patient.gender
        except (AttributeError, Examination.DoesNotExist):
            gender = None

        def _resolve_default(field_def: dict[str, Any]) -> Any:
            return field_def.get("default_value")

        def _resolve_range(field_def: dict[str, Any]) -> tuple[Any, Any]:
            if gender:
                override = (field_def.get("gender_overrides") or {}).get(gender)
                if override:
                    lo = override.get("min")
                    hi = override.get("max")
                    if lo is not None or hi is not None:
                        return lo, hi
            nr = field_def.get("normal_range") or {}
            return nr.get("min"), nr.get("max")

        def _resolve_step(field_def: dict[str, Any]) -> float | None:
            """Return step for gender-override ranges; ``None`` → continuous base range."""
            if not gender:
                return None
            override = (field_def.get("gender_overrides") or {}).get(gender) or {}
            if override.get("min") is None and override.get("max") is None:
                return None
            step = override.get("step")
            if step is None or step == "":
                return DEFAULT_GENDER_OVERRIDE_STEP
            try:
                value = float(step)
            except (TypeError, ValueError):
                return DEFAULT_GENDER_OVERRIDE_STEP
            return value if value > 0 else DEFAULT_GENDER_OVERRIDE_STEP

        def _resolve_seed(field_def: dict[str, Any]) -> Any:
            if not should_seed_field(field_def, gender):
                return None
            if field_def.get("formula"):
                return None
            default = _resolve_default(field_def)
            if not is_blank_value(default):
                return default
            if randomize and field_def.get("type") == "number":
                lo, hi = _resolve_range(field_def)
                if lo is not None and hi is not None:
                    return random_in_range(float(lo), float(hi), _resolve_step(field_def))
            return None

        for key, field_def in snap.items():
            value = data.get(key)
            if is_blank_value(value):
                value = _resolve_seed(field_def)
            if not is_blank_value(value):
                merged[key] = apply_input_format(value, field_def)

        # Preserve any extra keys not present in the snapshot (legacy/import).
        for key, value in data.items():
            if key not in merged and not is_blank_value(value):
                merged[key] = value

        self.values.all().delete()
        DepartmentResultValue.objects.bulk_create(
            [
                DepartmentResultValue(
                    result=self,
                    field_key=key,
                    value_number=_to_decimal(value, snap.get(key, {}).get("type")),
                    value_text=_value_as_text(value, snap.get(key, {}).get("type")),
                )
                for key, value in merged.items()
            ]
        )

    def apply_imported_values(
        self, imported_data: dict[str, Any], fields_config: list[dict[str, Any]] | None = None
    ) -> None:
        """Merge imported cells, randomize blanks, then evaluate formulas.

        Formula fields must run *after* empty numeric cells are seeded,
        otherwise BMI/IF expressions see 0 instead of the random in-range value.
        """
        from examinations.formula_evaluator import evaluate_computed_fields

        config = fields_config or self.template_snapshot or []
        imported_data = apply_formats_to_data(imported_data, config)
        merged = {**(self.data or {}), **imported_data}
        merged = {k: v for k, v in merged.items() if not is_blank_value(v)}
        self._sync_values(merged, randomize=True)
        gender = None
        try:
            if self.examination_id and self.examination.patient_id:
                gender = self.examination.patient.gender
        except (AttributeError, Examination.DoesNotExist):
            gender = None
        computed = evaluate_computed_fields(config, self.data, gender=gender)
        self._sync_values(computed, randomize=False)


class DepartmentResultValue(BaseModel):
    """One field-value pair within a department result.

    Stored as a table row — not buried in a JSON dict — so that each value
    can be indexed and searched efficiently:
    - ``value_number``: indexed for numeric range queries (e.g. hemoglobin > 16)
    - ``value_text``: GIN-trgm indexed for text search (e.g. note ILIKE '%bất thường%')
    """

    result = models.ForeignKey(
        DepartmentResult,
        on_delete=models.CASCADE,
        related_name="values",
    )
    field_key = models.CharField(max_length=100)
    value_number = models.DecimalField(
        max_digits=15, decimal_places=4, null=True, blank=True
    )
    value_text = models.TextField(blank=True)

    class Meta:
        ordering = ["field_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["result", "field_key"],
                name="unique_value_per_result",
            )
        ]
        indexes = [
            models.Index(fields=["field_key", "value_number"]),
            models.Index(fields=["field_key"]),
        ]

    def __str__(self) -> str:
        return f"{self.result_id} / {self.field_key} = {self.value_number or self.value_text}"


# ---------------------------------------------------------------------------
# Value converters — map Python values to typed store columns
# ---------------------------------------------------------------------------


def _to_decimal(value, field_type):
    if value in (None, "") or isinstance(value, bool):
        return None
    # Computed formulas often return numbers; store them in value_number
    # so reports/range checks see a float instead of the string "24.22".
    if field_type not in ("number", "computed"):
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _value_as_text(value, field_type):
    if value is None or value == "":
        return ""
    if isinstance(value, str):
        return value
    return str(value)


# ---------------------------------------------------------------------------
# Excel import — Phase 2, Sprint 6
# ---------------------------------------------------------------------------


class ImportJob(BaseModel):
    """
    Tracks an Excel import job for per-department data upload.

    Each import targets a single department. The file is parsed row-by-row,
    matching patients by ``employee_code`` and updating the corresponding
    :class:`DepartmentResult` for that patient's examination on the given date.
    """

    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Chờ xử lý"),
        (STATUS_PROCESSING, "Đang xử lý"),
        (STATUS_COMPLETED, "Hoàn thành"),
        (STATUS_FAILED, "Thất bại"),
    ]

    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="import_jobs",
    )
    exam_date = models.DateField(
        help_text="Ngày khám áp dụng cho tất cả bệnh nhân trong file"
    )
    file = models.FileField(upload_to="imports/%Y/%m/%d/")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    total_rows = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    errors = models.JSONField(
        default=list,
        help_text="List of error dicts: {row, employee_code, message}",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="import_jobs",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["department", "exam_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.department.name} — {self.exam_date} ({self.status})"


class ExportJob(BaseModel):
    """
    Tracks an Excel export job for pre-populated department results.

    Saves the generated file to ``MEDIA_ROOT/exports/`` under a job status flow.
    """

    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Chờ xử lý"),
        (STATUS_PROCESSING, "Đang xử lý"),
        (STATUS_COMPLETED, "Hoàn thành"),
        (STATUS_FAILED, "Thất bại"),
    ]

    company = models.ForeignKey(
        "accounts.Company",
        on_delete=models.CASCADE,
        related_name="export_jobs",
    )
    exam_package = models.ForeignKey(
        ExamPackage,
        on_delete=models.CASCADE,
        related_name="export_jobs",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="export_jobs",
    )
    exam_date = models.DateField(
        null=True,
        blank=True,
        help_text="Lọc kết quả khám theo ngày khám cụ thể (nếu có)",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    file = models.FileField(upload_to="exports/%Y/%m/%d/", null=True, blank=True)
    error_message = models.TextField(blank=True)
    current_progress = models.PositiveIntegerField(default=0)
    total_progress = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="export_jobs",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
        ]

    def __str__(self) -> str:
        return f"Export {self.company.code} — {self.department.name} ({self.status})"
