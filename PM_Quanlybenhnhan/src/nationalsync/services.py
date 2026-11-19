"""
EMRHUB API client — login, header building, RSA-SHA256 signing, data push.

The signing scheme mirrors the Ministry of Health's official Postman
pre-request script (see documents/checkup.api.facility.sandbox.*.postman):

    headerSha = SHA256(JSON.stringify(header)).toUpperCase()
    dataSha   = SHA256(data.trim()).toUpperCase()
    compare   = headerSha + "." + dataSha
    signature = Base64(RSA_SHA256_Sign(compare, privateKey))

The header JSON must be serialized with the *exact* field order used in the
request body, compact (no whitespace), and without ASCII-escaping non-ASCII
chars — all of which ``json.dumps(..., separators=(",", ":"))`` reproduces.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import time
import uuid
from typing import Any

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from django.core.cache import cache

from nationalsync.models import SyncConfig

logger = logging.getLogger(__name__)

SERVICE_TYPE = "100"  # Đồng bộ dữ liệu từ HIS/EMR lên Trục
LOGIN_PATH = "/api/auth/login"
PUSH_PATH = "/api/platform/data-sync/push"

TOKEN_CACHE_KEY = "nationalsync:token:{config_id}"
TOKEN_CACHE_TTL = 30 * 60  # re-login at most every 30 minutes

REQUEST_TIMEOUT = (10, 60)  # (connect, read) seconds — login
PUSH_TIMEOUT = (10, 300)  # push can wait on a large checkup payload


# ---------------------------------------------------------------------------
# Header building
# ---------------------------------------------------------------------------


def build_msg_id(sender_id: str, now: time.struct_time | None = None) -> str:
    """Return ``sender_id + YY + MM + DD + UUID4`` (no dashes)."""
    now = now or time.localtime()
    return (
        f"{sender_id}{now.tm_year % 100:02d}{now.tm_mon:02d}{now.tm_mday:02d}"
        f"{uuid.uuid4().hex}"
    )


def build_header(config: SyncConfig) -> dict[str, Any]:
    """Build the request header dict in the exact field order EMRHUB expects."""
    return {
        "version": config.version,
        "sender_id": config.sender_id,
        "receiver_id": config.receiver_id,
        "txn_type": "sync_checkup",
        "msg_type": "101",
        "data_type": "xml/base64",
        "send_datetime": int(time.time() * 1000),
        "msg_id": build_msg_id(config.sender_id),
    }


def _serialize_header(header: dict[str, Any]) -> str:
    """Serialize the header the same way JS ``JSON.stringify`` does."""
    return json.dumps(header, separators=(",", ":"), ensure_ascii=False)


# ---------------------------------------------------------------------------
# RSA-SHA256 signing
# ---------------------------------------------------------------------------


def normalize_pem(pem: str) -> str:
    """Normalize a PEM string so cryptography can load it.

    Handles the common mistake of pasting a Postman/JSON value where
    newlines are stored as the two characters ``\\n``.
    """
    text = (pem or "").strip()
    if "\\n" in text and "\n" not in text:
        text = text.replace("\\n", "\n")
    return text.strip() + "\n"


def sign_payload(header: dict[str, Any], data: str, private_key_pem: str) -> str:
    """Produce the Base64 RSA-SHA256 signature over ``header`` + ``data``.

    ``data`` is the raw XML string; it is trimmed before hashing to match the
    reference implementation.
    """
    header_sha = (
        hashlib.sha256(_serialize_header(header).encode("utf-8")).hexdigest().upper()
    )
    data_sha = hashlib.sha256(data.strip().encode("utf-8")).hexdigest().upper()
    compare_data = f"{header_sha}.{data_sha}"

    private_key = serialization.load_pem_private_key(
        normalize_pem(private_key_pem).encode("utf-8"), password=None
    )
    signature = private_key.sign(
        compare_data.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("ascii")


# ---------------------------------------------------------------------------
# Login + push
# ---------------------------------------------------------------------------


class EmrHubError(RuntimeError):
    """Raised when the EMRHUB API returns an error response."""


def login(config: SyncConfig, *, force: bool = False) -> str:
    """Log in to the EMRHUB API and return a bearer token (cached)."""
    cache_key = TOKEN_CACHE_KEY.format(config_id=config.pk or "default")
    if not force:
        cached = cache.get(cache_key)
        if cached:
            return cached

    url = f"{config.effective_api_base_url.rstrip('/')}{LOGIN_PATH}"
    try:
        response = requests.post(
            url,
            json={"username": config.username, "password": config.password},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise EmrHubError(f"Login request failed: {exc}") from exc

    if response.status_code == 401:
        raise EmrHubError("Login failed: sai thông tin tài khoản (401).")

    if response.status_code != 200:
        raise EmrHubError(
            f"Login failed: HTTP {response.status_code} — {response.text[:200]}"
        )

    try:
        token = response.json()["data"]["token"]
    except (ValueError, KeyError, TypeError) as exc:
        raise EmrHubError("Login failed: unexpected response shape.") from exc

    cache.set(cache_key, token, TOKEN_CACHE_TTL)
    return token


def push_data(
    config: SyncConfig,
    token: str,
    header: dict[str, Any],
    data_b64: str,
    signature: str,
    *,
    patient_type: str | None = None,
) -> dict[str, Any]:
    """Push the signed payload to the EMRHUB push endpoint.

    ``patient_type`` is the QĐ 2062 age-group form type required by EMRHUB:
    ``Adult`` / ``ChildUnder`` / ``Minor``.
    """
    url = f"{config.effective_api_base_url.rstrip('/')}{PUSH_PATH}"
    headers = {
        "service-type": SERVICE_TYPE,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "header": header,
        "data": data_b64,
        "signature": signature,
    }
    if patient_type:
        # EMRHUB validates this required enum on the push DTO (QĐ 2062).
        body["TYPE"] = patient_type

    try:
        response = requests.post(
            url, json=body, headers=headers, timeout=PUSH_TIMEOUT
        )
    except requests.RequestException as exc:
        raise EmrHubError(f"Push request failed: {exc}") from exc

    if response.status_code in (400, 401):
        raise EmrHubError(
            f"Push rejected: HTTP {response.status_code} — {response.text[:300]}"
        )

    if response.status_code != 200:
        raise EmrHubError(
            f"Push failed: HTTP {response.status_code} — {response.text[:300]}"
        )

    try:
        return response.json()
    except ValueError as exc:
        raise EmrHubError("Push failed: non-JSON success response.") from exc
