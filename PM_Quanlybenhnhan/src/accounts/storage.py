"""Signature files live outside the public media directory."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateSignatureStorage(FileSystemStorage):
    """PNG signatures are served only through the authenticated API."""

    def __init__(self) -> None:
        location = Path(settings.BASE_DIR) / "private_media" / "doctor_signatures"
        super().__init__(location=str(location), base_url=None)

    def deconstruct(self) -> tuple[str, list, dict]:
        return ("accounts.storage.PrivateSignatureStorage", [], {})
