"""
Vietnam province and commune codes for EMRHUB address fields.

``src/vietnam_province_codes.json`` lists each xã/phường/đặc khu after the
2025 rearrangement:

* ``ma_tinh`` → ``MATINH_CU_TRU`` (2 digits)
* ``ma_so`` → ``MAXA_CU_TRU`` (5 digits)

Free-text ``Patient.address`` is matched against province and unit names.
Commune names repeat across provinces, so ``MAXA_CU_TRU`` is filled only when
the unit is unique inside the resolved province, or nationally unique when
the province is missing. Tone pairs such as Thành/Thạnh stay distinct.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PROVINCE_JSON = Path(__file__).resolve().parent.parent / "vietnam_province_codes.json"

# Extra aliases (folded, underscore-separated) → province code.
# Short codes (hn, hcm) are only matched as whole address segments.
_ALIASES: dict[str, str] = {
    # Hà Nội
    "thanh_pho_ha_noi": "01",
    "tp_ha_noi": "01",
    "hn": "01",
    # TP.HCM (+ một số tên cũ thường gặp trong địa chỉ)
    "thanh_pho_ho_chi_minh": "79",
    "tp_ho_chi_minh": "79",
    "tp_hcm": "79",
    "tphcm": "79",
    "hcm": "79",
    "sai_gon": "79",
    "saigon": "79",
    "binh_duong": "79",
    "ba_ria_vung_tau": "79",
    "vung_tau": "79",
    # Huế (cũ: Thừa Thiên Huế)
    "thua_thien_hue": "46",
    "thanh_pho_hue": "46",
    "tp_hue": "46",
    # Đà Nẵng / Hải Phòng / Cần Thơ
    "thanh_pho_da_nang": "48",
    "tp_da_nang": "48",
    "thanh_pho_hai_phong": "31",
    "tp_hai_phong": "31",
    "thanh_pho_can_tho": "92",
    "tp_can_tho": "92",
    # Đắk Lắk biến thể viết
    "daklak": "66",
    "dak_lak": "66",
    "dac_lac": "66",
}

_SHORT_ALIASES = frozenset({"hn", "hcm", "tphcm", "tp_hcm"})

_FOLD_PREFIX_RE = re.compile(
    r"^(tinh|thanh_pho|thanhpho|tp|tx|thi_xa|thi_tran|quan|huyen|xa|phuong|dac_khu)_+"
)
_SOFT_PREFIX_RE = re.compile(
    r"^(tỉnh|thành_phố|thanh_pho|thànhphố|tp|thị_xã|thị_trấn|quận|huyện|xã|phường|đặc_khu)_+"
)
_UNIT_HINT_RE = re.compile(r"(xã|phường|đặc\s*khu|thị\s*trấn)", re.IGNORECASE)


def _fold(value: str) -> str:
    """Lowercase, strip diacritics, collapse separators to underscores."""
    value = (value or "").replace("đ", "d").replace("Đ", "D")
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def _soft(value: str) -> str:
    """Lowercase, keep Vietnamese diacritics, collapse separators."""
    value = (value or "").lower()
    value = re.sub(r"[^\w]+", "_", value, flags=re.UNICODE)
    return value.strip("_")


def _strip_fold_prefix(token: str) -> str:
    prev = None
    while prev != token:
        prev = token
        token = _FOLD_PREFIX_RE.sub("", token)
    return token


def _strip_soft_prefix(token: str) -> str:
    prev = None
    while prev != token:
        prev = token
        token = _SOFT_PREFIX_RE.sub("", token)
    return token


def _put_unique(mapping: dict[str, str], key: str, code: str) -> None:
    if not key:
        return
    current = mapping.get(key)
    if current is None:
        mapping[key] = code
    elif current != code:
        mapping[key] = ""


@dataclass(frozen=True)
class _Catalog:
    province_soft: dict[str, str]
    province_fold: dict[str, str]
    province_fold_keys: tuple[str, ...]
    commune_soft: dict[str, dict[str, str]]
    commune_fold_unique: dict[str, dict[str, str]]
    national_soft: dict[str, tuple[str, str]]
    national_fold: dict[str, tuple[str, str]]


def _index_names(
    raw_name: str,
    code: str,
    soft_map: dict[str, str],
    fold_map: dict[str, str],
) -> tuple[str, str]:
    soft_full = _soft(raw_name)
    fold_full = _fold(raw_name)
    soft_key = _strip_soft_prefix(soft_full)
    fold_key = _strip_fold_prefix(fold_full)
    _put_unique(soft_map, soft_key, code)
    _put_unique(soft_map, soft_full, code)
    _put_unique(fold_map, fold_key, code)
    _put_unique(fold_map, fold_full, code)
    return soft_key, fold_key


@lru_cache(maxsize=1)
def _catalog() -> _Catalog:
    province_soft: dict[str, str] = {}
    province_fold: dict[str, str] = {}
    commune_soft: dict[str, dict[str, str]] = {}
    commune_fold: dict[str, dict[str, set[str]]] = {}
    national_soft_sets: dict[str, set[tuple[str, str]]] = {}
    national_fold_sets: dict[str, set[tuple[str, str]]] = {}

    try:
        raw = json.loads(_PROVINCE_JSON.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Cannot load admin codes from %s: %s", _PROVINCE_JSON, exc)
        raw = []

    if isinstance(raw, dict):
        # Legacy {code: province name} file — province only.
        for code, name in raw.items():
            _index_names(str(name), str(code).zfill(2), province_soft, province_fold)
    elif isinstance(raw, list):
        for row in raw:
            if not isinstance(row, dict):
                continue
            ma_tinh = str(row.get("ma_tinh") or "").zfill(2)
            ma_so = str(row.get("ma_so") or "").strip()
            if ma_tinh == "00" or not ma_so:
                continue
            ma_so = ma_so.zfill(5)
            _index_names(
                str(row.get("tinh_thanh_pho") or ""),
                ma_tinh,
                province_soft,
                province_fold,
            )
            soft_units: dict[str, str] = {}
            fold_units: dict[str, str] = {}
            soft_key, fold_key = _index_names(
                str(row.get("ten_don_vi") or ""),
                ma_so,
                soft_units,
                fold_units,
            )
            commune_soft.setdefault(ma_tinh, {}).update(
                {k: v for k, v in soft_units.items() if v}
            )
            bucket = commune_fold.setdefault(ma_tinh, {})
            for key, unit_code in fold_units.items():
                if key and unit_code:
                    bucket.setdefault(key, set()).add(unit_code)
            if soft_key:
                national_soft_sets.setdefault(soft_key, set()).add((ma_tinh, ma_so))
            if fold_key:
                national_fold_sets.setdefault(fold_key, set()).add((ma_tinh, ma_so))
    else:
        logger.error("Unexpected admin-code JSON type: %s", type(raw).__name__)

    for alias, code in _ALIASES.items():
        _put_unique(province_fold, _fold(alias), code)

    province_soft = {k: v for k, v in province_soft.items() if v}
    province_fold = {k: v for k, v in province_fold.items() if v}

    commune_fold_unique: dict[str, dict[str, str]] = {}
    for ma_tinh, names in commune_fold.items():
        commune_fold_unique[ma_tinh] = {
            key: next(iter(codes)) for key, codes in names.items() if len(codes) == 1
        }

    national_soft = {
        key: next(iter(pairs))
        for key, pairs in national_soft_sets.items()
        if len(pairs) == 1
    }
    national_fold = {
        key: next(iter(pairs))
        for key, pairs in national_fold_sets.items()
        if len(pairs) == 1
    }

    fold_keys = tuple(
        sorted(
            (k for k in province_fold if k not in _SHORT_ALIASES),
            key=len,
            reverse=True,
        )
    )
    return _Catalog(
        province_soft=province_soft,
        province_fold=province_fold,
        province_fold_keys=fold_keys,
        commune_soft=commune_soft,
        commune_fold_unique=commune_fold_unique,
        national_soft=national_soft,
        national_fold=national_fold,
    )


def _lookup(
    soft_key: str, fold_key: str, soft_map: dict[str, str], fold_map: dict[str, str]
) -> str:
    if soft_key and soft_key in soft_map:
        return soft_map[soft_key]
    if fold_key and fold_key in fold_map:
        return fold_map[fold_key]
    return ""


def _windows(token: str, *, minimum: int) -> list[str]:
    parts = [p for p in token.split("_") if p]
    found: list[str] = []
    if len(parts) < minimum:
        return found
    for size in range(len(parts), minimum - 1, -1):
        for start in range(0, len(parts) - size + 1):
            found.append("_".join(parts[start : start + size]))
    return found


def _trailing(token: str, size: int) -> str:
    parts = [part for part in token.split("_") if part]
    if size <= 0 or len(parts) < size:
        return ""
    return "_".join(parts[-size:])


def _match_province(address: str, catalog: _Catalog) -> str:
    raw_parts = re.split(r"[,;/|]+", address)
    for raw in reversed(raw_parts):
        soft = _strip_soft_prefix(_soft(raw))
        fold = _strip_fold_prefix(_fold(raw))
        hit = _lookup(soft, fold, catalog.province_soft, catalog.province_fold)
        if hit:
            return hit
        soft_parts = [part for part in soft.split("_") if part]
        fold_parts = [part for part in fold.split("_") if part]
        for size in range(min(4, max(len(soft_parts), len(fold_parts))), 0, -1):
            hit = _lookup(
                _strip_soft_prefix(_trailing(soft, size)),
                _strip_fold_prefix(_trailing(fold, size)),
                catalog.province_soft,
                catalog.province_fold,
            )
            if hit:
                return hit

    padded = f"_{_fold(address)}_"
    for key in catalog.province_fold_keys:
        if f"_{key}_" in padded:
            return catalog.province_fold[key]
    return ""


def _match_in_maps(
    raw: str,
    soft_map: dict[str, str],
    fold_map: dict[str, str],
) -> str:
    soft = _strip_soft_prefix(_soft(raw))
    fold = _strip_fold_prefix(_fold(raw))
    hit = _lookup(soft, fold, soft_map, fold_map)
    if hit:
        return hit
    for soft_cand in _windows(soft, minimum=2):
        hit = soft_map.get(_strip_soft_prefix(soft_cand), "")
        if hit:
            return hit
    for fold_cand in _windows(fold, minimum=2):
        hit = fold_map.get(_strip_fold_prefix(fold_cand), "")
        if hit:
            return hit
    return ""


def _match_commune(address: str, ma_tinh: str, catalog: _Catalog) -> str:
    soft_map = catalog.commune_soft.get(ma_tinh, {})
    fold_map = catalog.commune_fold_unique.get(ma_tinh, {})
    if not soft_map:
        return ""
    parts = [p for p in re.split(r"[,;/|]+", address) if p.strip()]
    hinted = [p for p in parts if _UNIT_HINT_RE.search(p)]
    for raw in reversed(hinted or parts):
        hit = _match_in_maps(raw, soft_map, fold_map)
        if hit:
            return hit
    if hinted:
        return ""
    padded = f"_{_soft(address)}_"
    for key in sorted(soft_map, key=len, reverse=True):
        if len(key) < 4:
            continue
        if f"_{key}_" in padded:
            return soft_map[key]
    return ""


def _match_unique_commune(address: str, catalog: _Catalog) -> tuple[str, str]:
    """Infer province from a commune name that exists in only one province."""
    parts = [p for p in re.split(r"[,;/|]+", address) if p.strip()]
    hinted = [p for p in parts if _UNIT_HINT_RE.search(p)]
    for raw in reversed(hinted or parts):
        soft = _strip_soft_prefix(_soft(raw))
        fold = _strip_fold_prefix(_fold(raw))
        pair = catalog.national_soft.get(soft) or catalog.national_fold.get(fold)
        if pair:
            return pair
        for cand in _windows(soft, minimum=2):
            pair = catalog.national_soft.get(_strip_soft_prefix(cand))
            if pair:
                return pair
        for cand in _windows(fold, minimum=2):
            pair = catalog.national_fold.get(_strip_fold_prefix(cand))
            if pair:
                return pair
    return "", ""


def resolve_admin_codes(address: str | None) -> tuple[str, str]:
    """Return ``(MATINH_CU_TRU, MAXA_CU_TRU)`` parsed from a free-text address.

    Either value is ``""`` when it cannot be resolved safely.
    """
    if not address or not str(address).strip():
        return "", ""
    catalog = _catalog()
    ma_tinh = _match_province(address, catalog)
    if ma_tinh:
        return ma_tinh, _match_commune(address, ma_tinh, catalog)
    return _match_unique_commune(address, catalog)


def resolve_province_code(address: str | None) -> str:
    """Extract ``MATINH_CU_TRU`` (2-digit) from a free-text address."""
    return resolve_admin_codes(address)[0]


def resolve_patient_admin_codes(patient: Any) -> tuple[str, str]:
    """Resolve province and commune from the patient address, then company address."""
    ma_tinh, ma_xa = resolve_admin_codes(getattr(patient, "address", None))
    if ma_tinh or ma_xa:
        return ma_tinh, ma_xa
    company = getattr(patient, "company", None)
    if company is not None:
        return resolve_admin_codes(getattr(company, "address", None))
    return "", ""


def resolve_patient_province_code(patient: Any) -> str:
    """Resolve ``MATINH_CU_TRU`` from patient address, falling back to company address."""
    return resolve_patient_admin_codes(patient)[0]
