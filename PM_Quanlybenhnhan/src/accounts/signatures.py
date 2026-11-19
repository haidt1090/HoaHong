"""Doctor signature storage for the national checkup sync.

A doctor keeps either a PNG file or a base64 string. Sync always sends
base64 in ``CKS_NGUOI_KET_LUAN``; a stored PNG is encoded at push time.
"""

from __future__ import annotations

import base64
import io
import logging
from typing import Any

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)

MAX_SIGNATURE_BYTES = 2 * 1024 * 1024


def normalize_signature_base64(value: str) -> str:
    """Return a padded base64 string, or raise ``ValidationError``."""
    text = (value or "").strip()
    if text.lower().startswith("data:"):
        _, _, text = text.partition(",")
    text = "".join(text.split())
    if not text:
        raise ValidationError("Chuỗi base64 trống.")
    try:
        raw = base64.b64decode(text, validate=True)
    except Exception as exc:
        raise ValidationError("Chuỗi base64 không hợp lệ.") from exc
    if not raw:
        raise ValidationError("Chuỗi base64 trống.")
    if len(raw) > MAX_SIGNATURE_BYTES:
        raise ValidationError("Chữ ký vượt quá 2 MB.")
    return base64.b64encode(raw).decode("ascii")


def assert_png(data: bytes) -> None:
    """Reject anything that is not a PNG within the size limit."""
    if not data:
        raise ValidationError("File ảnh trống.")
    if len(data) > MAX_SIGNATURE_BYTES:
        raise ValidationError("Ảnh chữ ký tối đa 2 MB.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format != "PNG":
                raise ValidationError("Chỉ nhận file ảnh PNG.")
            image.verify()
    except ValidationError:
        raise
    except (UnidentifiedImageError, OSError) as exc:
        raise ValidationError("File PNG không hợp lệ.") from exc


def signature_kind(user: Any) -> str:
    """``image``, ``base64``, or ``""`` when the doctor has no signature."""
    image = getattr(user, "signature_image", None)
    if image is not None and getattr(image, "name", ""):
        return "image"
    if (getattr(user, "signature_base64", "") or "").strip():
        return "base64"
    return ""


def signature_base64_for_sync(user: Any) -> str:
    """Base64 placed in the checkup XML. A readable PNG wins over stored text.

    A missing PNG (the database still names the file) does not abort the sync.
    The stored base64 string is used instead, or ``""`` when there is none.
    """
    if user is None:
        return ""
    image = getattr(user, "signature_image", None)
    if image is not None and getattr(image, "name", ""):
        try:
            with image.open("rb") as handle:
                raw = handle.read()
        except FileNotFoundError:
            logger.warning(
                "Signature file missing for %s: %s",
                getattr(user, "pk", ""),
                image.name,
            )
        else:
            if raw:
                return base64.b64encode(raw).decode("ascii")
    text = (getattr(user, "signature_base64", "") or "").strip()
    if not text:
        return ""
    # Tolerate a data-URI prefix left from paste/import.
    if text.lower().startswith("data:"):
        _, _, text = text.partition(",")
        text = "".join(text.split())
    return text


def store_signature_image(user: Any, data: bytes, *, filename: str = "") -> None:
    """Replace the stored signature with PNG bytes."""
    assert_png(data)
    if user.signature_image:
        user.signature_image.delete(save=False)
    user.signature_base64 = ""
    user.signature_image.save(
        filename or f"{user.pk}.png", ContentFile(data), save=False
    )
    user.save(update_fields=["signature_image", "signature_base64"])


def store_signature_base64(user: Any, value: str) -> None:
    """Replace the doctor's signature with a base64 string and drop any PNG."""
    text = normalize_signature_base64(value)
    if user.signature_image:
        user.signature_image.delete(save=False)
    user.signature_base64 = text
    user.save(update_fields=["signature_image", "signature_base64"])


def clear_signature(user: Any) -> None:
    """Remove both the PNG and the stored base64 string."""
    if user.signature_image:
        user.signature_image.delete(save=False)
    user.signature_base64 = ""
    user.save(update_fields=["signature_image", "signature_base64"])
