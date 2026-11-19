"""
KHAMSUCKHOE XML builder — Phase 8, Sprint 16.

Turns one or more :class:`~examinations.models.Examination` into a single
``KHAMSUCKHOE`` XML document (one ``HOSO`` per examination, each with the 7
``FILEHOSO`` blocks: XML1, XML2, XML7, XML9, XML10, XML11, XML12).

Empty leaf elements (no text / whitespace-only, no children) are stripped
recursively before serialization so the national push payload does not
include tags without information. Signing happens on that cleaned XML.

Field mapping is intentionally data-driven:

* XML1 / XML2 / XML12 map directly from ``Patient`` / ``Examination``.
* XML7 (khám lâm sàng), XML9 (tiền sử) and XML10 (thể lực) read the
  ``DepartmentResult.data`` of clinical departments and map known field keys
  to the fixed Ministry schema element names (see the ``*_FIELD_MAP`` tables).
* XML11 (cận lâm sàng) emits one ``CHI_TIET_CLS`` per para-clinical field.

The mapping tables are the single place to extend when the clinic adds new
department fields; unmapped fields are ignored rather than guessed.
"""

from __future__ import annotations

import unicodedata
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from datetime import date
from typing import Any

from accounts.signatures import signature_base64_for_sync
from examinations.models import DepartmentResult, Examination
from nationalsync.mapping import SyncMappings, value_for_mapping
from nationalsync.models import FacilitySignature, SyncConfig, SyncFieldMapping
from nationalsync.provinces import resolve_patient_admin_codes

# ---------------------------------------------------------------------------
# Department classification helpers
# ---------------------------------------------------------------------------

HISTORY_DEPT_KEYWORDS = ("tien su", "benh tat", "history", "tien_su")
PHYSICAL_DEPT_KEYWORDS = (
    "the luc",
    "the_luc",
    "the chat",
    "thechat",
    "sinh hieu",
    "vital",
)

# XML7 (KHAM_LAM_SANG) element name → candidate DepartmentField keys.
XML7_FIELD_MAP: dict[str, tuple[str, ...]] = {
    # Mắt
    "KHONG_KINH_MAT_PHAI": (
        "khong_kinh_mat_phai",
        "thi_luc_khong_kinh_phai",
        "mat_phai",
    ),
    "KHONG_KINH_MAT_TRAI": (
        "khong_kinh_mat_trai",
        "thi_luc_khong_kinh_trai",
        "mat_trai",
    ),
    "CO_KINH_MAT_PHAI": ("co_kinh_mat_phai", "thi_luc_co_kinh_phai"),
    "CO_KINH_MAT_TRAI": ("co_kinh_mat_trai", "thi_luc_co_kinh_trai"),
    "BENH_KHAC_MAT": ("benh_khac_mat", "benh_mat"),
    # Tai mũi họng
    "TAI_TRAI_NOI_THUONG": ("tai_trai_noi_thuong", "tai_trai"),
    "TAI_TRAI_NOI_THAM": ("tai_trai_noi_tham",),
    "TAI_PHAI_NOI_THUONG": ("tai_phai_noi_thuong", "tai_phai"),
    "TAI_PHAI_NOI_THAM": ("tai_phai_noi_tham",),
    "BENH_TAI_MUI_HONG": ("benh_tai_mui_hong",),
    "BENH_KHAC_TAI_MUI_HONG": ("benh_khac_tai_mui_hong",),
    # Răng hàm mặt
    "HAM_TREN": ("ham_tren", "rang_ham_tren"),
    "HAM_DUOI": ("ham_duoi", "rang_ham_duoi"),
    "BENH_RANG_HAM_MAT": ("benh_rang_ham_mat",),
    "BENH_KHAC_RANG_HAM_MAT": ("benh_khac_rang_ham_mat",),
    # Nội khoa
    "NOI_KHOA_TUAN_HOAN": ("noi_khoa_tuan_hoan", "tuan_hoan"),
    "NOI_KHOA_HO_HAP": ("noi_khoa_ho_hap", "ho_hap"),
    "NOI_KHOA_TIEU_HOA": ("noi_khoa_tieu_hoa", "tieu_hoa"),
    "NOI_KHOA_THAN_TN_SD": ("noi_khoa_than_tn_sd", "than_tiet_nieu"),
    "NOI_KHOA_NOI_TIET": ("noi_khoa_noi_tiet", "noi_tiet"),
    "NOI_KHOA_CO_XUONG_KHOP": ("noi_khoa_co_xuong_khop", "co_xuong_khop"),
    "NOI_KHOA_THAN_KINH": ("noi_khoa_than_kinh", "than_kinh"),
    "NOI_KHOA_TAM_THAN": ("noi_khoa_tam_than", "tam_than"),
    # Ngoại khoa / da liễu / sản phụ khoa
    "KET_QUA_KHAM_NGOAI_KHOA": ("ket_qua_kham_ngoai_khoa", "ngoai_khoa"),
    "KET_QUA_KHAM_DA_LIEU": ("ket_qua_kham_da_lieu", "da_lieu"),
    "KET_QUA_KHAM_SAN_PHU_KHOA": ("ket_qua_kham_san_phu_khoa", "san_phu_khoa"),
}

# XML9 (TIEN_SU_BENH_TAT) element name → candidate keys.
XML9_FIELD_MAP: dict[str, tuple[str, ...]] = {
    "TSGD_MAC_BENH": ("tsgd_mac_benh", "tien_su_gia_dinh_mac_benh"),
    "TSGD_MA_BENH": ("tsgd_ma_benh", "tien_su_gia_dinh_ma_benh"),
    "TSBT_MAC_BENH": ("tsbt_mac_benh", "tien_su_ban_than_mac_benh"),
    "TSBT_MA_BENH": ("tsbt_ma_benh", "tien_su_ban_than_ma_benh"),
    "TSBT_DANG_DIEU_TRI_BENH": ("tsbt_dang_dieu_tri_benh",),
    "BENH_DANG_DIEU_TRI": ("benh_dang_dieu_tri",),
    "TSBT_BENH_TRONG_5_NAM_QUA": ("tsbt_benh_trong_5_nam_qua",),
    "TSBT_BENH_THAN_KINH": ("tsbt_benh_than_kinh",),
    "TSBT_BENH_MAT": ("tsbt_benh_mat",),
    "TSBT_BENH_TAI": ("tsbt_benh_tai",),
    "TSBT_BENH_TIM": ("tsbt_benh_tim",),
    "TSBT_PHAU_THUAT_TIM": ("tsbt_phau_thuat_tim",),
    "TSBT_TANG_HUYET_AP": ("tsbt_tang_huyet_ap",),
    "TSBT_KHO_THO": ("tsbt_kho_tho",),
    "TSBT_BENH_PHOI": ("tsbt_benh_phoi",),
    "TSBT_BENH_THAN": ("tsbt_benh_than",),
    "TSBT_NGHIEN_RUOU": ("tsbt_nghien_ruou",),
    "TSBT_DAI_THAO_DUONG": ("tsbt_dai_thao_duong",),
    "TSBT_BENH_TAM_THAN": ("tsbt_benh_tam_than",),
    "TSBT_BENH_TIEU_HOA": ("tsbt_benh_tieu_hoa",),
    "TSBT_ROI_LOAN_GIAC_NGU": ("tsbt_roi_loan_giac_ngu",),
    "TSBT_TAI_BIEN": ("tsbt_tai_bien",),
    "TSBT_BENH_COT_SONG": ("tsbt_benh_cot_song",),
    "TSBT_BENH_KHAC": ("tsbt_benh_khac",),
    "TSBT_MA_BENH_KHAC": ("tsbt_ma_benh_khac",),
    "TSBT_TEN_THUOC_LIEU_LUONG": ("tsbt_ten_thuoc_lieu_luong",),
}

# XML10 (KHAM_THE_LUC) element name → candidate keys.
XML10_FIELD_MAP: dict[str, tuple[str, ...]] = {
    "CHIEU_CAO": ("chieu_cao", "height", "chieucao"),
    "CAN_NANG": ("can_nang", "weight", "cannang"),
    "CHI_SO_BMI": ("chi_so_bmi", "bmi", "chisobmi"),
    "MACH": ("mach", "nhip_tim", "pulse"),
    "HUYET_AP": ("huyet_ap", "blood_pressure", "ha"),
}

# exam_type → DOI_TUONG code (XML2).
DOI_TUONG_MAP: dict[str, str] = {
    "periodic": "1",
    "occupational": "2",
    "job_placement": "3",
    "labor_under18": "4",
    "labor_over18": "5",
}

# exam_type → LY_DO_VV (XML1). EMRHUB rejects empty LY_DO_VV for Adult.
LY_DO_VV_MAP: dict[str, str] = {
    "periodic": "Khám sức khỏe định kỳ",
    "occupational": "Khám sức khỏe nghề nghiệp",
    "job_placement": "Khám sức khỏe bố trí nghề nghiệp",
    "labor_under18": "Khám sức khỏe lao động dưới 18 tuổi",
    "labor_over18": "Khám sức khỏe lao động trên 18 tuổi",
}

# QĐ 2062/QĐ-BYT age-group form types (EMRHUB required ``TYPE`` field).
TYPE_CHILD_UNDER = "ChildUnder"  # dưới 06 tuổi
TYPE_MINOR = "Minor"  # đủ 06 đến dưới 18 tuổi
TYPE_ADULT = "Adult"  # đủ 18 tuổi trở lên
EMRHUB_TYPES = (TYPE_CHILD_UNDER, TYPE_MINOR, TYPE_ADULT)


# ---------------------------------------------------------------------------
# Normalization + data lookups
# ---------------------------------------------------------------------------


def _norm(value: str) -> str:
    """Lowercase and strip Vietnamese diacritics for key matching."""
    value = unicodedata.normalize("NFD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return value.lower().replace("-", "_").replace(" ", "_")


def _pick(data: dict[str, Any], keys: Iterable[str]) -> Any:
    """Return the first non-empty value from ``data`` for any of ``keys``."""
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _text(value: Any) -> str:
    """Coerce a value to a string for XML text (empty for None/'')."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)


def _element_has_content(el: ET.Element) -> bool:
    """True when the element has non-whitespace text or any child elements."""
    if len(el) > 0:
        return True
    return bool((el.text or "").strip())


#: Tags that must remain even when empty (schema / sample ``KHAMSUCKHOE_sample.xml``).
#: Stripping these has caused EMRHUB ``ERROR_99`` / "Unknown error" on push.
PRESERVE_EMPTY_TAGS = frozenset(
    {
        # Unit signature placeholders (always present in the official sample).
        "CHUKYDONVI",
        "CKS_NGUOI_KET_LUAN",
        "CKS_BENH_VIEN",
        # Structural wrappers — keep so FILEHOSO / blocks stay well-formed.
        "THONGTINDONVI",
        "THONGTINHOSO",
        "DANHSACHHOSO",
        "HOSO",
        "FILEHOSO",
        "LOAIHOSO",
        "NOIDUNGFILE",
        "THONG_TIN_HANH_CHINH",
        "THONG_TIN_CHUNG_VE_LAN_KHAM",
        "KHAM_LAM_SANG",
        "TIEN_SU_BENH_TAT",
        "KHAM_THE_LUC",
        "KHAM_CAN_LAM_SANG",
        "DANH_SACH_CLS",
        "KET_LUAN",
    }
)


def strip_empty_elements(el: ET.Element) -> None:
    """Remove empty data leaves; keep signature + structural schema tags.

    Walks depth-first. Empty optional field tags (no text, no children) are
    dropped. Tags in :data:`PRESERVE_EMPTY_TAGS` are never removed — matching
    the Ministry sample and avoiding EMRHUB ``ERROR_99`` validation failures.
    """
    for child in list(el):
        strip_empty_elements(child)
        if child.tag in PRESERVE_EMPTY_TAGS:
            continue
        if not _element_has_content(child):
            el.remove(child)


def _date_compact(value: Any, with_time: bool = False) -> str:
    """Format a date as ``YYYYMMDD`` (or ``YYYYMMDDHHMM``)."""
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return ""
        compact = value.replace("-", "").replace("/", "")[:8]
        if with_time:
            return compact + "0000"
        return compact
    return value.strftime("%Y%m%d%H%M") if with_time else value.strftime("%Y%m%d")


def _age_years(dob: date, on_date: date) -> int:
    """Completed years of age on ``on_date``."""
    return on_date.year - dob.year - (
        (on_date.month, on_date.day) < (dob.month, dob.day)
    )


def resolve_emrhub_type(
    patient: Any,
    *,
    on_date: date | None = None,
) -> str:
    """Return EMRHUB ``TYPE`` for a patient (QĐ 2062/QĐ-BYT age groups).

    - ``ChildUnder``: dưới 06 tuổi
    - ``Minor``: đủ 06 đến dưới 18 tuổi
    - ``Adult``: đủ 18 tuổi trở lên

    When DOB is missing, defaults to ``Adult`` (typical occupational exams).
    """
    on_date = on_date or date.today()
    dob = getattr(patient, "dob", None)
    if not dob:
        return TYPE_ADULT
    age = _age_years(dob, on_date)
    if age < 6:
        return TYPE_CHILD_UNDER
    if age < 18:
        return TYPE_MINOR
    return TYPE_ADULT


def _ma_lk(examination: Examination) -> str:
    """Derive a stable 12-digit MA_LK from the examination UUID."""
    return str(examination.id.int % 10**12).zfill(12)


def _classify_department(result: DepartmentResult) -> str:
    """Classify a DepartmentResult into clinical/history/physical/paraclinical."""
    department = result.department
    code = _norm(department.code)
    name = _norm(department.name)
    label = f"{code}_{name}"

    if any(k in label for k in HISTORY_DEPT_KEYWORDS):
        return "history"
    if any(k in label for k in PHYSICAL_DEPT_KEYWORDS):
        return "physical"
    if department.category == "para_clinical":
        return "paraclinical"
    return "clinical"


# ---------------------------------------------------------------------------
# Per-block builders
# ---------------------------------------------------------------------------


# Danh mục dân tộc BYT: 01 = Kinh. CSDLKSK rejects Adult records when this is empty.
DEFAULT_MA_DAN_TOC = "01"


def _resolve_ma_dan_toc(patient: Any) -> str:
    """Return ethnicity code for XML1 ``MA_DAN_TOC``.

    Uses a patient override when present. Otherwise ``01`` (Kinh), because
    the portal rejects an empty tag and the patient record has no ethnicity.
    """
    raw = getattr(patient, "ethnicity_code", None) or getattr(
        patient, "ma_dan_toc", None
    )
    if raw is not None and str(raw).strip():
        return str(raw).strip()
    return DEFAULT_MA_DAN_TOC


def _resolve_ma_nghe_nghiep(patient: Any) -> str:
    """Return occupation code for XML1 ``MA_NGHE_NGHIEP``, or empty when unset.

    Do not invent sample defaults (e.g. ``04`` from KHAMSUCKHOE_sample.xml).
    Empty tags are stripped before push.
    """
    raw = getattr(patient, "occupation_code", None) or getattr(
        patient, "ma_nghe_nghiep", None
    )
    if raw is not None and str(raw).strip():
        return str(raw).strip()
    return ""


def _resolve_ly_do_vv(exam_type: str | None) -> str:
    """Return visit reason for XML1 ``LY_DO_VV`` from ``exam_type`` only."""
    if exam_type and exam_type in LY_DO_VV_MAP:
        return LY_DO_VV_MAP[exam_type]
    return ""


def _build_xml1(
    patient: Any, *, exam_type: str | None = None
) -> ET.Element:
    root = ET.Element("THONG_TIN_HANH_CHINH")
    gender = "1" if patient.gender == "M" else "2" if patient.gender == "F" else ""
    company_name = patient.company.name if patient.company_id else ""
    matinh, maxa = resolve_patient_admin_codes(patient)

    # Only real patient / exam data — no sample XML filler (TUAN_THAI=0,
    # MA_NGHE_NGHIEP=04, …). MA_DAN_TOC is required by CSDLKSK for Adult.
    # Empty leaves are stripped later.
    fields: list[tuple[str, str]] = [
        ("HO_TEN", patient.full_name or ""),
        ("GIOI_TINH", gender),
        ("NGAY_SINH", _date_compact(patient.dob, with_time=True)),
        ("MA_DAN_TOC", _resolve_ma_dan_toc(patient)),
        ("SO_CCCD", patient.cccd or ""),
        ("NGAYCAP_CCCD", _date_compact(patient.cccd_issued_date)),
        ("NOICAP_CCCD", patient.cccd_issued_place or ""),
        ("DIA_CHI", patient.address or ""),
        ("MATINH_CU_TRU", matinh),
        ("MAXA_CU_TRU", maxa),
        ("DIEN_THOAI", patient.phone or ""),
        ("MA_NGHE_NGHIEP", _resolve_ma_nghe_nghiep(patient)),
        ("NOI_LAM_VIEC_HOC_TAP", company_name),
        ("LY_DO_VV", _resolve_ly_do_vv(exam_type)),
    ]
    for tag, value in fields:
        child = ET.SubElement(root, tag)
        child.text = value
    return root


def _build_xml2(examination: Examination, config: SyncConfig) -> ET.Element:
    root = ET.Element("THONG_TIN_CHUNG_VE_LAN_KHAM")
    patient_type = resolve_emrhub_type(
        examination.patient, on_date=examination.exam_date or date.today()
    )
    fields: list[tuple[str, str]] = [
        ("MA_LK", _ma_lk(examination)),
        ("MA_CSKCB", config.facility_code or ""),
        ("MA_GTIN_CSKCB", config.sender_id or ""),
        ("DOI_TUONG", DOI_TUONG_MAP.get(examination.exam_type, "")),
        ("TYPE", patient_type),
        ("NGAY_VAO", _date_compact(examination.exam_date, with_time=True)),
    ]
    for tag, value in fields:
        child = ET.SubElement(root, tag)
        child.text = value
    return root


def _tag_value(
    tag: str,
    *,
    block: str,
    fallback_data: dict[str, Any],
    fallback_keys: tuple[str, ...],
    results: list[DepartmentResult],
    mappings: SyncMappings,
) -> Any:
    """Mapped column when an admin row exists; otherwise the built-in key list."""
    row = mappings.by_tag.get(tag)
    if row is not None and row.block == block:
        value, _result, _key = value_for_mapping(results, row)
        return value
    return _pick(fallback_data, fallback_keys)


def _tags_for(
    block: str,
    fallback: dict[str, tuple[str, ...]],
    mappings: SyncMappings,
) -> list[str]:
    tags = list(fallback)
    for tag, row in mappings.by_tag.items():
        if row.block == block and tag not in fallback:
            tags.append(tag)
    return tags


def _build_xml7(
    data: dict[str, Any],
    results: list[DepartmentResult],
    mappings: SyncMappings,
) -> ET.Element:
    root = ET.Element("KHAM_LAM_SANG")
    for tag in _tags_for(SyncFieldMapping.BLOCK_XML7, XML7_FIELD_MAP, mappings):
        value = _tag_value(
            tag,
            block=SyncFieldMapping.BLOCK_XML7,
            fallback_data=data,
            fallback_keys=XML7_FIELD_MAP.get(tag, ()),
            results=results,
            mappings=mappings,
        )
        if value is None:
            continue
        child = ET.SubElement(root, tag)
        child.text = _text(value)
    return root


def _build_xml9(
    data: dict[str, Any],
    results: list[DepartmentResult],
    mappings: SyncMappings,
) -> ET.Element:
    root = ET.Element("TIEN_SU_BENH_TAT")
    for tag in _tags_for(SyncFieldMapping.BLOCK_XML9, XML9_FIELD_MAP, mappings):
        value = _tag_value(
            tag,
            block=SyncFieldMapping.BLOCK_XML9,
            fallback_data=data,
            fallback_keys=XML9_FIELD_MAP.get(tag, ()),
            results=results,
            mappings=mappings,
        )
        if value is None:
            continue
        child = ET.SubElement(root, tag)
        child.text = _text(value)
    return root


def _build_xml10(
    data: dict[str, Any],
    results: list[DepartmentResult],
    mappings: SyncMappings,
) -> ET.Element:
    root = ET.Element("KHAM_THE_LUC")
    for tag in _tags_for(SyncFieldMapping.BLOCK_XML10, XML10_FIELD_MAP, mappings):
        value = _tag_value(
            tag,
            block=SyncFieldMapping.BLOCK_XML10,
            fallback_data=data,
            fallback_keys=XML10_FIELD_MAP.get(tag, ()),
            results=results,
            mappings=mappings,
        )
        if value is None:
            continue
        child = ET.SubElement(root, tag)
        child.text = _text(value)
    return root


def _append_cls_row(
    danh_sach: ET.Element,
    *,
    ma_dich_vu: str,
    ma_chi_so: str,
    ten_chi_so: str,
    gia_tri: str,
    don_vi_do: str,
) -> None:
    chi_tiet = ET.SubElement(danh_sach, "CHI_TIET_CLS")
    for tag, content in (
        ("MA_DICH_VU", ma_dich_vu),
        ("MA_CHI_SO", ma_chi_so),
        ("TEN_CHI_SO", ten_chi_so),
        ("GIA_TRI", gia_tri),
        ("DON_VI_DO", don_vi_do),
        ("MO_TA", ""),
        ("KET_LUAN", ""),
    ):
        child = ET.SubElement(chi_tiet, tag)
        child.text = content


def _snapshot_field(result: DepartmentResult, key: str) -> dict[str, Any]:
    for field in result.template_snapshot or []:
        if field.get("key") == key:
            return field
    return {}


def _build_xml11(
    paraclinical_results: Iterable[DepartmentResult],
    results: list[DepartmentResult],
    mappings: SyncMappings,
) -> ET.Element:
    root = ET.Element("KHAM_CAN_LAM_SANG")
    danh_sach = ET.SubElement(root, "DANH_SACH_CLS")

    if mappings.lab:
        for row in mappings.lab:
            value, result, key = value_for_mapping(results, row)
            if value is None or result is None:
                continue
            field = _snapshot_field(result, key)
            _append_cls_row(
                danh_sach,
                ma_dich_vu=row.ma_dich_vu,
                ma_chi_so=row.ma_chi_so or key,
                ten_chi_so=str(field.get("label") or key),
                gia_tri=_text(value),
                don_vi_do=str(field.get("unit") or ""),
            )
        return root

    for result in paraclinical_results:
        snapshot = {f["key"]: f for f in (result.template_snapshot or [])}
        for key, value in result.data.items():
            field = snapshot.get(key, {})
            chi_tiet = ET.SubElement(danh_sach, "CHI_TIET_CLS")
            label = field.get("label", key)
            unit = field.get("unit", "")

            for tag, content in (
                ("MA_DICH_VU", ""),
                ("MA_CHI_SO", key),
                ("TEN_CHI_SO", label),
                ("GIA_TRI", _text(value)),
                ("DON_VI_DO", unit),
                ("MO_TA", ""),
                ("KET_LUAN", ""),
            ):
                child = ET.SubElement(chi_tiet, tag)
                child.text = content
    return root


def _build_xml12(examination: Examination) -> ET.Element:
    root = ET.Element("KET_LUAN")
    classification = _text(
        examination.classification if examination.classification is not None else ""
    )

    fields: list[tuple[str, str]] = [
        ("PHAN_LOAI_SK", classification),
        ("KET_LUAN_BENH", ""),
        ("CAC_VAN_DE_SUC_KHOE", examination.conclusion or ""),
        ("CAC_BENH_TAT_NEU_CO", examination.disease or ""),
    ]
    for tag, value in fields:
        child = ET.SubElement(root, tag)
        child.text = value
    return root


# ---------------------------------------------------------------------------
# Top-level builder
# ---------------------------------------------------------------------------


def _build_hoso(
    examination: Examination,
    config: SyncConfig,
    mappings: SyncMappings | None = None,
) -> ET.Element:
    hoso = ET.Element("HOSO")
    if mappings is None:
        mappings = SyncMappings.load()

    # Merge clinical data by department category for XML7/9/10.
    clinical_data: dict[str, Any] = {}
    history_data: dict[str, Any] = {}
    physical_data: dict[str, Any] = {}
    paraclinical: list[DepartmentResult] = []
    results = list(
        examination.department_results.select_related("department").all()
    )

    for result in results:
        kind = _classify_department(result)
        if kind == "paraclinical":
            paraclinical.append(result)
        elif kind == "history":
            history_data.update(result.data)
        elif kind == "physical":
            physical_data.update(result.data)
        else:
            clinical_data.update(result.data)

    hoso.append(
        _file_hoso(
            "XML1",
            _build_xml1(examination.patient, exam_type=examination.exam_type),
        )
    )
    hoso.append(_file_hoso("XML2", _build_xml2(examination, config)))
    hoso.append(_file_hoso("XML7", _build_xml7(clinical_data, results, mappings)))
    hoso.append(_file_hoso("XML9", _build_xml9(history_data, results, mappings)))
    hoso.append(_file_hoso("XML10", _build_xml10(physical_data, results, mappings)))
    hoso.append(
        _file_hoso("XML11", _build_xml11(paraclinical, results, mappings))
    )
    hoso.append(_file_hoso("XML12", _build_xml12(examination)))

    return hoso


def _file_hoso(loai_hoso: str, content: ET.Element) -> ET.Element:
    file_hoso = ET.Element("FILEHOSO")
    loai = ET.SubElement(file_hoso, "LOAIHOSO")
    loai.text = loai_hoso
    noi_dung = ET.SubElement(file_hoso, "NOIDUNGFILE")
    noi_dung.append(content)
    return file_hoso


def concluding_doctor_signature(examinations: Iterable[Examination]) -> str:
    """Base64 for ``CKS_NGUOI_KET_LUAN`` when every exam shares one doctor.

    A file has a single signature block. Mixed or missing doctors leave it
    empty rather than attaching the wrong signature. Callers that group by
    doctor (the sync task) always hit the single-doctor case.
    """
    exams = list(examinations)
    if not exams:
        return ""
    doctor_ids = {exam.doctor_id for exam in exams}
    if len(doctor_ids) != 1 or None in doctor_ids:
        return ""
    return signature_base64_for_sync(exams[0].doctor)


def facility_signature_base64() -> str:
    """Base64 for ``CKS_BENH_VIEN``, or ``""`` when the admin has not set one."""
    facility = FacilitySignature.objects.filter(pk=1).first()
    if facility is None:
        return ""
    return signature_base64_for_sync(facility)


def require_chuky_signatures(
    examinations: Iterable[Examination],
    *,
    doctor_signature: str | None = None,
) -> None:
    """``CKS_NGUOI_KET_LUAN`` may be empty.

    The doctor signs the record later on admin.csdlksk.vn. The USB token on
    this PC is the facility certificate and is written to ``CKS_BENH_VIEN``.
    """
    del examinations, doctor_signature


def build_kham_suc_khoe_xml(
    examinations: Iterable[Examination],
    config: SyncConfig,
    *,
    ngay_lap: date | None = None,
    facility_signature: str | None = None,
) -> str:
    """Build the full KHAMSUCKHOE XML document as a UTF-8 string.

    ``CKS_NGUOI_KET_LUAN`` is left empty. ``facility_signature`` overrides the
    stored facility image in ``CKS_BENH_VIEN``; pass ``""`` to keep that tag
    empty while the USB token signs the document.
    """
    exams = list(examinations)

    root = ET.Element("KHAMSUCKHOE")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root.set("xmlns:xsd", "http://www.w3.org/2001/XMLSchema")

    thong_tin_don_vi = ET.SubElement(root, "THONGTINDONVI")
    ma_cskcb = ET.SubElement(thong_tin_don_vi, "MACSKCB")
    ma_cskcb.text = config.sender_id or ""

    thong_tin_ho_so = ET.SubElement(root, "THONGTINHOSO")
    ngay_lap_el = ET.SubElement(thong_tin_ho_so, "NGAYLAP")
    ngay_lap_el.text = _date_compact(ngay_lap or date.today())
    so_luong = ET.SubElement(thong_tin_ho_so, "SOLUONGHOSO")
    so_luong.text = str(len(exams))

    danh_sach = ET.SubElement(thong_tin_ho_so, "DANHSACHHOSO")
    mappings = SyncMappings.load()
    for examination in exams:
        danh_sach.append(_build_hoso(examination, config, mappings))

    chu_ky = ET.SubElement(root, "CHUKYDONVI")
    cks_bac_si = ET.SubElement(chu_ky, "CKS_NGUOI_KET_LUAN")
    cks_bac_si.text = ""
    cks_benh_vien = ET.SubElement(chu_ky, "CKS_BENH_VIEN")
    cks_benh_vien.text = (
        facility_signature_base64()
        if facility_signature is None
        else facility_signature
    )

    # National API rejects / ignores empty leaf tags — drop them before encode.
    strip_empty_elements(root)

    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")


def embed_facility_signature(xml: str, signature_b64: str) -> str:
    """Put Base64(XMLDSig) into the empty ``CKS_BENH_VIEN`` tag.

    The facility USB token signs the document while that tag is empty.
    ``CKS_NGUOI_KET_LUAN`` stays empty for the doctor to sign on the portal.
    """
    filled = f"<CKS_BENH_VIEN>{signature_b64}</CKS_BENH_VIEN>"
    for empty in (
        "<CKS_BENH_VIEN />",
        "<CKS_BENH_VIEN/>",
        "<CKS_BENH_VIEN></CKS_BENH_VIEN>",
    ):
        if empty in xml:
            return xml.replace(empty, filled, 1)
    raise ValueError("XML không có thẻ CKS_BENH_VIEN trống để gắn chữ ký.")


def build_data_b64(
    examinations: Iterable[Examination],
    config: SyncConfig,
    *,
    facility_signature: str | None = None,
    ngay_lap: date | None = None,
) -> str:
    """Return the base64-encoded XML string used as the push ``data`` field.

    ``facility_signature`` is Base64 of the facility XML Signature. The token
    signs the document with an empty ``CKS_BENH_VIEN``; that value is then
    written into the tag. ``CKS_NGUOI_KET_LUAN`` stays empty.
    """
    import base64

    exams = list(examinations)
    if facility_signature:
        xml_str = build_kham_suc_khoe_xml(
            exams, config, ngay_lap=ngay_lap, facility_signature=""
        )
        xml_str = embed_facility_signature(xml_str, facility_signature.strip())
    else:
        xml_str = build_kham_suc_khoe_xml(exams, config, ngay_lap=ngay_lap)
    return base64.b64encode(xml_str.encode("utf-8")).decode("ascii")


# Keep a stable public reference to the id helper used by tests.
__all__ = [
    "TYPE_ADULT",
    "TYPE_CHILD_UNDER",
    "TYPE_MINOR",
    "_ma_lk",
    "build_data_b64",
    "build_kham_suc_khoe_xml",
    "embed_facility_signature",
    "concluding_doctor_signature",
    "facility_signature_base64",
    "require_chuky_signatures",
    "resolve_emrhub_type",
    "strip_empty_elements",
]
