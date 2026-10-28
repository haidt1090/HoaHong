"""Non-secret, per-user settings. PINs and browser session data are never saved."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import json
import os
from pathlib import Path
import re
import tempfile


class SettingsError(ValueError):
    pass


@dataclass(frozen=True)
class AppSettings:
    debugger_address: str = "127.0.0.1:9222"
    base_url: str = "https://admin.csdlksk.vn"
    certificate_thumbprint: str = ""
    automatic_pin: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.debugger_address, str):
            raise SettingsError("Địa chỉ Chrome phải là địa chỉ loopback.")
        match = re.fullmatch(r"127\.0\.0\.1:([0-9]{1,5})", self.debugger_address)
        if match is None or not 1 <= int(match.group(1)) <= 65535:
            raise SettingsError("Địa chỉ Chrome phải có dạng 127.0.0.1:9222.")
        if self.base_url != "https://admin.csdlksk.vn":
            raise SettingsError("Bản này chỉ dùng HTTPS tại admin.csdlksk.vn.")
        if not isinstance(self.certificate_thumbprint, str):
            raise SettingsError("Mã chứng thư phải là chuỗi.")
        if self.certificate_thumbprint and not re.fullmatch(
                r"[0-9A-Fa-f]{40}", self.certificate_thumbprint):
            raise SettingsError("Mã chứng thư phải là SHA-1 thumbprint 40 ký tự hex.")
        if type(self.automatic_pin) is not bool:
            raise SettingsError("automatic_pin phải là true hoặc false.")


def settings_path() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "KySoPython" / "settings.json"


def load_settings(path: str | Path | None = None) -> AppSettings:
    target = Path(path) if path is not None else settings_path()
    try:
        text = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return AppSettings()
    except (OSError, UnicodeError) as exc:
        raise SettingsError("Không đọc được file cấu hình.") from exc
    try:
        data = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise SettingsError("File cấu hình không phải JSON hợp lệ.") from exc
    if not isinstance(data, dict):
        raise SettingsError("Cấu hình phải là một JSON object.")
    supported = {f.name for f in fields(AppSettings)}
    if set(data) - supported:
        raise SettingsError(
            "Cấu hình có trường không được hỗ trợ; không nhập PIN hoặc mật khẩu vào file này.")
    return AppSettings(**data)


def save_settings(settings: AppSettings, path: str | Path | None = None) -> None:
    if not isinstance(settings, AppSettings):
        raise SettingsError("Chỉ lưu được AppSettings đã kiểm tra.")
    # Revalidate even if the caller circumvented the frozen dataclass.
    settings = AppSettings(**asdict(settings))
    target = Path(path) if path is not None else settings_path()
    temporary: str | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".settings-", suffix=".tmp", dir=target.parent)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(asdict(settings), stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        temporary = None
    except (OSError, UnicodeError) as exc:
        raise SettingsError("Không lưu được file cấu hình.") from exc
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass
