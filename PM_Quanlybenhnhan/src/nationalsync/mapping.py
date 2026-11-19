"""Resolve admin XML mappings onto one examination's department results.

A mapping stores a department plus a column key. Sync prefers that
department's result. When the exam package did not include the department,
the same key is read from any other result on that examination.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, BinaryIO

from examinations.models import DepartmentResult

# block, tag, Vietnamese label. XML11 rows have no fixed tag.
XML_TAG_CATALOG: tuple[tuple[str, str, str], ...] = (
    ("xml7", "KHONG_KINH_MAT_PHAI", "Thị lực không kính mắt phải"),
    ("xml7", "KHONG_KINH_MAT_TRAI", "Thị lực không kính mắt trái"),
    ("xml7", "CO_KINH_MAT_PHAI", "Thị lực có kính mắt phải"),
    ("xml7", "CO_KINH_MAT_TRAI", "Thị lực có kính mắt trái"),
    ("xml7", "BENH_KHAC_MAT", "Bệnh khác về mắt"),
    ("xml7", "KHAM_MAT_PL", "Phân loại khám mắt"),
    ("xml7", "TAI_TRAI_NOI_THUONG", "Tai trái nói thường"),
    ("xml7", "TAI_TRAI_NOI_THAM", "Tai trái nói thầm"),
    ("xml7", "TAI_PHAI_NOI_THUONG", "Tai phải nói thường"),
    ("xml7", "TAI_PHAI_NOI_THAM", "Tai phải nói thầm"),
    ("xml7", "BENH_TAI_MUI_HONG", "Bệnh tai mũi họng"),
    ("xml7", "BENH_KHAC_TAI_MUI_HONG", "Bệnh khác tai mũi họng"),
    ("xml7", "KHAM_TAI_MUI_HONG_PL", "Phân loại tai mũi họng"),
    ("xml7", "HAM_TREN", "Hàm trên"),
    ("xml7", "HAM_DUOI", "Hàm dưới"),
    ("xml7", "BENH_RANG_HAM_MAT", "Bệnh răng hàm mặt"),
    ("xml7", "BENH_KHAC_RANG_HAM_MAT", "Bệnh khác răng hàm mặt"),
    ("xml7", "KHAM_RANG_HAM_MAT_PL", "Phân loại răng hàm mặt"),
    ("xml7", "NOI_KHOA_TUAN_HOAN", "Nội khoa tuần hoàn"),
    ("xml7", "NOI_KHOA_TUAN_HOAN_PL", "Phân loại tuần hoàn"),
    ("xml7", "NOI_KHOA_HO_HAP", "Nội khoa hô hấp"),
    ("xml7", "NOI_KHOA_HO_HAP_PL", "Phân loại hô hấp"),
    ("xml7", "NOI_KHOA_TIEU_HOA", "Nội khoa tiêu hóa"),
    ("xml7", "NOI_KHOA_TIEU_HOA_PL", "Phân loại tiêu hóa"),
    ("xml7", "NOI_KHOA_THAN_TN_SD", "Nội khoa thận tiết niệu"),
    ("xml7", "NOI_KHOA_THAN_TN_SD_PL", "Phân loại thận tiết niệu"),
    ("xml7", "NOI_KHOA_NOI_TIET", "Nội khoa nội tiết"),
    ("xml7", "NOI_KHOA_NOI_TIET_PL", "Phân loại nội tiết"),
    ("xml7", "NOI_KHOA_CO_XUONG_KHOP", "Nội khoa cơ xương khớp"),
    ("xml7", "NOI_KHOA_CO_XUONG_KHOP_PL", "Phân loại cơ xương khớp"),
    ("xml7", "NOI_KHOA_THAN_KINH", "Nội khoa thần kinh"),
    ("xml7", "NOI_KHOA_THAN_KINH_PL", "Phân loại thần kinh"),
    ("xml7", "NOI_KHOA_TAM_THAN", "Nội khoa tâm thần"),
    ("xml7", "NOI_KHOA_TAM_THAN_PL", "Phân loại tâm thần"),
    ("xml7", "KET_QUA_KHAM_NGOAI_KHOA", "Ngoại khoa"),
    ("xml7", "KHAM_NGOAI_KHOA_PL", "Phân loại ngoại khoa"),
    ("xml7", "KET_QUA_KHAM_DA_LIEU", "Da liễu"),
    ("xml7", "KHAM_DA_LIEU_PL", "Phân loại da liễu"),
    ("xml7", "KET_QUA_KHAM_SAN_PHU_KHOA", "Sản phụ khoa"),
    ("xml7", "KHAM_SAN_PHU_KHOA_PL", "Phân loại sản phụ khoa"),
    ("xml9", "TSGD_MAC_BENH", "Tiền sử gia đình có bệnh"),
    ("xml9", "TSGD_MA_BENH", "Mã bệnh tiền sử gia đình"),
    ("xml9", "TSBT_MAC_BENH", "Tiền sử bản thân có bệnh"),
    ("xml9", "TSBT_MA_BENH", "Mã bệnh tiền sử bản thân"),
    ("xml9", "TSBT_DANG_DIEU_TRI_BENH", "Đang điều trị bệnh"),
    ("xml9", "BENH_DANG_DIEU_TRI", "Bệnh đang điều trị"),
    ("xml9", "TSBT_BENH_TRONG_5_NAM_QUA", "Bệnh trong 5 năm qua"),
    ("xml9", "TSBT_BENH_THAN_KINH", "Tiền sử bệnh thần kinh"),
    ("xml9", "TSBT_BENH_MAT", "Tiền sử bệnh mắt"),
    ("xml9", "TSBT_BENH_TAI", "Tiền sử bệnh tai"),
    ("xml9", "TSBT_BENH_TIM", "Tiền sử bệnh tim"),
    ("xml9", "TSBT_PHAU_THUAT_TIM", "Tiền sử phẫu thuật tim"),
    ("xml9", "TSBT_TANG_HUYET_AP", "Tiền sử tăng huyết áp"),
    ("xml9", "TSBT_KHO_THO", "Tiền sử khó thở"),
    ("xml9", "TSBT_BENH_PHOI", "Tiền sử bệnh phổi"),
    ("xml9", "TSBT_BENH_THAN", "Tiền sử bệnh thận"),
    ("xml9", "TSBT_NGHIEN_RUOU", "Tiền sử nghiện rượu"),
    ("xml9", "TSBT_DAI_THAO_DUONG", "Tiền sử đái tháo đường"),
    ("xml9", "TSBT_BENH_TAM_THAN", "Tiền sử bệnh tâm thần"),
    ("xml9", "TSBT_BENH_TIEU_HOA", "Tiền sử bệnh tiêu hóa"),
    ("xml9", "TSBT_ROI_LOAN_GIAC_NGU", "Tiền sử rối loạn giấc ngủ"),
    ("xml9", "TSBT_TAI_BIEN", "Tiền sử tai biến"),
    ("xml9", "TSBT_BENH_COT_SONG", "Tiền sử bệnh cột sống"),
    ("xml9", "TSBT_BENH_KHAC", "Tiền sử bệnh khác"),
    ("xml9", "TSBT_MA_BENH_KHAC", "Mô tả bệnh khác"),
    ("xml9", "TSBT_TEN_THUOC_LIEU_LUONG", "Thuốc và liều đang dùng"),
    ("xml10", "CHIEU_CAO", "Chiều cao"),
    ("xml10", "CAN_NANG", "Cân nặng"),
    ("xml10", "CHI_SO_BMI", "BMI"),
    ("xml10", "MACH", "Mạch"),
    ("xml10", "HUYET_AP", "Huyết áp"),
    ("xml10", "KHAM_THE_LUC_PL", "Phân loại thể lực"),
)


TAG_LABELS: dict[str, str] = {tag: label for _block, tag, label in XML_TAG_CATALOG}

_BLOCK_BY_ROOT = {
    "KHAM_LAM_SANG": "xml7",
    "TIEN_SU_BENH_TAT": "xml9",
    "KHAM_THE_LUC": "xml10",
}
_CLS_KEYS = ("MA_DICH_VU", "MA_CHI_SO", "TEN_CHI_SO")


def label_for_tag(tag: str) -> str:
    """Vietnamese label when the tag is in the adult catalog, otherwise the tag."""
    return TAG_LABELS.get(tag, tag)


def _local_name(tag: str) -> str:
    if tag.startswith("{"):
        return tag.rsplit("}", 1)[-1]
    return tag


def extract_mapping_fields(source: BinaryIO) -> list[dict[str, str]]:
    """Read mappable result tags from a KHAMSUCKHOE document.

    XML7/XML9/XML10 contribute one entry per leaf tag. Signature images
    (``CKDT_*``) are skipped. XML11 contributes one entry per ``CHI_TIET_CLS``
    row that has ``MA_CHI_SO``. ``MA_DICH_VU`` may be empty.
    """
    stack: list[str] = []
    cls_row: dict[str, str] = {}
    fields: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    for event, elem in ET.iterparse(source, events=("start", "end")):
        tag = _local_name(elem.tag)
        if event == "start":
            stack.append(tag)
            if tag == "CHI_TIET_CLS":
                cls_row = {}
            continue

        parent = stack[-2] if len(stack) >= 2 else ""
        if parent == "CHI_TIET_CLS" and tag in _CLS_KEYS:
            cls_row[tag] = (elem.text or "").strip()
        elif tag == "CHI_TIET_CLS":
            ma_dich_vu = cls_row.get("MA_DICH_VU", "")
            ma_chi_so = cls_row.get("MA_CHI_SO", "")
            key = ("xml11", ma_dich_vu, ma_chi_so)
            if ma_chi_so and key not in seen:
                seen.add(key)
                fields.append(
                    {
                        "block": "xml11",
                        "tag": "",
                        "label": cls_row.get("TEN_CHI_SO") or ma_chi_so,
                        "ma_dich_vu": ma_dich_vu,
                        "ma_chi_so": ma_chi_so,
                    }
                )
            cls_row = {}
            elem.clear()
        elif not tag.startswith("CKDT_") and not list(elem):
            block = ""
            for ancestor in reversed(stack[:-1]):
                if ancestor in _BLOCK_BY_ROOT:
                    block = _BLOCK_BY_ROOT[ancestor]
                    break
            key = (block, tag, "")
            if block and key not in seen:
                seen.add(key)
                fields.append(
                    {
                        "block": block,
                        "tag": tag,
                        "label": label_for_tag(tag),
                        "ma_dich_vu": "",
                        "ma_chi_so": "",
                    }
                )
        if tag.startswith("CKDT_"):
            elem.text = None
            elem.clear()
        if stack:
            stack.pop()

    if not fields:
        raise ValueError(
            "File XML không có thẻ kết quả khám (XML7, XML9, XML10, XML11)."
        )
    return fields


def copy_matching_mappings(source: Any, target: Any) -> int:
    """Copy mappings whose tag or lab code still exists on ``target``."""
    from nationalsync.models import SyncFieldMapping

    tags = {
        (item.get("block"), item.get("tag"))
        for item in target.extracted_fields
        if item.get("tag")
    }
    labs = {
        (item.get("ma_dich_vu"), item.get("ma_chi_so"))
        for item in target.extracted_fields
        if item.get("block") == SyncFieldMapping.BLOCK_XML11
    }
    copied = 0
    for row in source.mappings.all():
        if row.block == SyncFieldMapping.BLOCK_XML11:
            if (row.ma_dich_vu, row.ma_chi_so) not in labs:
                continue
        elif (row.block, row.xml_tag) not in tags:
            continue
        SyncFieldMapping.objects.create(
            version=target,
            block=row.block,
            xml_tag=row.xml_tag,
            department=row.department,
            field_key=row.field_key,
            alias_keys=list(row.alias_keys or []),
            ma_dich_vu=row.ma_dich_vu,
            ma_chi_so=row.ma_chi_so,
        )
        copied += 1
    return copied


@dataclass
class SyncMappings:
    """Mappings loaded once per XML document."""

    by_tag: dict[str, Any]
    lab: list[Any]

    @classmethod
    def load(cls) -> SyncMappings:
        from nationalsync.models import SyncFieldMapping, SyncMappingVersion

        version = SyncMappingVersion.objects.filter(is_default=True).first()
        if version is None:
            return cls(by_tag={}, lab=[])
        rows = list(version.mappings.all())
        return cls(
            by_tag={row.xml_tag: row for row in rows if row.xml_tag},
            lab=[row for row in rows if row.block == SyncFieldMapping.BLOCK_XML11],
        )


def mapping_keys(row: Any) -> list[str]:
    """Primary key, then aliases, without duplicates."""
    keys: list[str] = []
    for key in [row.field_key, *(row.alias_keys or [])]:
        text = str(key or "").strip()
        if text and text not in keys:
            keys.append(text)
    return keys


def value_for_mapping(
    results: list[DepartmentResult],
    row: Any,
) -> tuple[Any, DepartmentResult | None, str]:
    """Return ``(value, result, key)`` for one mapping.

    When the configured department has a result on this exam, only that
    result is read. Otherwise the same keys are searched on the other
    departments of this exam.
    """
    keys = mapping_keys(row)
    preferred = [
        result
        for result in results
        if row.department_id and result.department_id == row.department_id
    ]
    search = preferred if preferred else list(results)
    for result in search:
        data = result.data or {}
        for key in keys:
            value = data.get(key)
            if value not in (None, ""):
                return value, result, key
    return None, None, ""
