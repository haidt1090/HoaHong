"""Company-summary statistics for the official aggregate report.

Counts people (not fields) per exam-package slot, so a department bound
twice with different templates (Sprint 4a) becomes two independent groups.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable

from reports.report_builder import (
    DepartmentSpec,
    PatientRecord,
    RenderedDepartment,
    RenderedField,
    ReportDataset,
)

CLASS_LABELS: dict[int, str] = {
    1: "Sức khỏe loại I",
    2: "Sức khỏe loại II",
    3: "Sức khỏe loại III",
    4: "Sức khỏe loại IV",
    5: "Sức khỏe loại V",
}

_POSITIVE_VALUES = frozenset(
    {
        "duong tinh",
        "dương tính",
        "positive",
        "pos",
        "reactive",
        "+",
        "1",
        "true",
        "yes",
        "co",
        "có",
    }
)


@dataclass
class DiseaseStat:
    name: str
    count: int
    pct: float


@dataclass
class GroupStat:
    """One exam-package slot (department + data-entry template)."""

    key: str
    name: str
    kind: str  # "range" | "serology"
    examined: int
    normal: int
    abnormal: int
    pct_normal: float
    pct_abnormal: float
    diseases: list[DiseaseStat] = field(default_factory=list)
    advice: str = ""

    @property
    def normal_caption(self) -> str:
        return "âm tính" if self.kind == "serology" else "bình thường"

    @property
    def abnormal_caption(self) -> str:
        return "dương tính" if self.kind == "serology" else "bất thường"


@dataclass
class ClassificationStat:
    level: int
    label: str
    male: int
    female: int
    count: int
    pct: float


@dataclass
class CompanyStats:
    total: int
    male: int
    female: int
    male_pct: float
    female_pct: float
    classifications: list[ClassificationStat] = field(default_factory=list)
    groups: list[GroupStat] = field(default_factory=list)

    def group_for(self, spec: DepartmentSpec) -> GroupStat | None:
        key = _group_key(spec)
        for group in self.groups:
            if group.key == key:
                return group
        return None


def build_company_stats(
    dataset: ReportDataset, config: dict[str, Any] | None = None
) -> CompanyStats:
    """Aggregate demographics, health class, and per-slot disease counts."""
    config = config or {}
    advice_map = config.get("advice") or {}
    patients = dataset.patients
    total = len(patients)
    male = sum(1 for p in patients if p.gioi_tinh == "M")
    female = sum(1 for p in patients if p.gioi_tinh == "F")

    return CompanyStats(
        total=total,
        male=male,
        female=female,
        male_pct=_pct(male, total),
        female_pct=_pct(female, total),
        classifications=_classification_rows(patients, total),
        groups=[
            _group_stat(spec, patients, advice_map) for spec in dataset.departments
        ],
    )


def _group_key(spec: DepartmentSpec) -> str:
    return f"{spec.id}:{spec.template_id}"


def _pct(count: int, total: int) -> float:
    if not total:
        return 0.0
    return round(count / total * 100, 2)


def _parse_class_level(raw: str) -> int | None:
    """Map ``phan_loai`` to 1–5. ``0`` is treated as loại I (healthy)."""
    text = (raw or "").strip()
    if not text:
        return None
    if text.isdigit():
        level = int(text)
        if level == 0:
            return 1
        if 1 <= level <= 5:
            return level
        return None
    roman = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5}
    lowered = text.lower().replace("loại", "").replace("loai", "").strip()
    if lowered in roman:
        return roman[lowered]
    return None


def _classification_rows(
    patients: list[PatientRecord], total: int
) -> list[ClassificationStat]:
    buckets: dict[int, list[int]] = {level: [0, 0, 0] for level in range(1, 6)}
    # [male, female, total]
    for patient in patients:
        level = _parse_class_level(patient.phan_loai)
        if level is None:
            continue
        buckets[level][2] += 1
        if patient.gioi_tinh == "M":
            buckets[level][0] += 1
        elif patient.gioi_tinh == "F":
            buckets[level][1] += 1

    rows: list[ClassificationStat] = []
    for level in range(1, 6):
        male_n, female_n, count = buckets[level]
        if count == 0:
            continue
        rows.append(
            ClassificationStat(
                level=level,
                label=CLASS_LABELS[level],
                male=male_n,
                female=female_n,
                count=count,
                pct=_pct(count, total),
            )
        )
    return rows


def _group_kind(spec: DepartmentSpec) -> str:
    if any(f.normal_min is not None or f.normal_max is not None for f in spec.fields):
        return "range"
    return "serology"


def _is_positive_value(raw: Any) -> bool:
    if raw is None or raw == "":
        return False
    if isinstance(raw, bool):
        return raw
    text = str(raw).strip().lower()
    return text in _POSITIVE_VALUES


def _field_is_abnormal(field: RenderedField) -> bool:
    if field.is_empty:
        return False
    if field.is_abnormal:
        return True
    if field.normal_min is None and field.normal_max is None:
        return _is_positive_value(field.raw_value if field.raw_value not in (None, "") else field.value)
    return False


def _disease_name(field: RenderedField) -> str:
    if getattr(field, "abnormal_label", ""):
        return field.abnormal_label
    if field.abnormal_direction == "low":
        return f"{field.label} thấp"
    if field.abnormal_direction == "high":
        return f"{field.label} cao"
    return field.label


def _match_result(patient: PatientRecord, spec: DepartmentSpec) -> RenderedDepartment | None:
    matches = [
        dept
        for dept in patient.departments
        if dept.id == spec.id and dept.template_id == spec.template_id
    ]
    return matches[0] if matches else None


def _resolve_advice(spec: DepartmentSpec, advice_map: dict[str, str]) -> str:
    if not advice_map:
        return ""
    for key in (spec.template_id, spec.code, spec.name, spec.id):
        if key in advice_map:
            return str(advice_map[key])
    return ""


def _group_stat(
    spec: DepartmentSpec,
    patients: Iterable[PatientRecord],
    advice_map: dict[str, str],
) -> GroupStat:
    kind = _group_kind(spec)
    examined = 0
    abnormal_people = 0
    disease_counts: Counter[str] = Counter()

    for patient in patients:
        result = _match_result(patient, spec)
        if result is None or not result.filled_fields:
            continue
        examined += 1
        person_diseases: set[str] = set()
        for fld in result.fields:
            if not _field_is_abnormal(fld):
                continue
            name = _disease_name(fld)
            if name:
                person_diseases.add(name)
        if person_diseases:
            abnormal_people += 1
            for name in person_diseases:
                disease_counts[name] += 1

    normal = examined - abnormal_people
    diseases = [
        DiseaseStat(name=name, count=count, pct=_pct(count, abnormal_people))
        for name, count in disease_counts.most_common()
    ]
    return GroupStat(
        key=_group_key(spec),
        name=spec.template_name or spec.name,
        kind=kind,
        examined=examined,
        normal=normal,
        abnormal=abnormal_people,
        pct_normal=_pct(normal, examined),
        pct_abnormal=_pct(abnormal_people, examined),
        diseases=diseases,
        advice=_resolve_advice(spec, advice_map),
    )
