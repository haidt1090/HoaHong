"""Windows Chrome, certificate metadata and deliberately narrow USB-token UI helpers.

No private keys are read. PINs live only in the caller's memory and are never logged.
Manual mode is the default: vendor middleware and secure-desktop prompts vary.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import time
from typing import Callable
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener


class TokenError(RuntimeError):
    """An actionable Windows integration error; callers should stop the batch."""


@dataclass(frozen=True)
class Certificate:
    thumbprint: str
    subject: str
    label: str


def _require_windows() -> None:
    if os.name != "nt":
        raise TokenError("Chức năng này cần Windows, Chrome và driver USB Token đã cài.")


def _parse_certificates(output: str) -> list[Certificate]:
    try:
        rows = json.loads(output.lstrip("\ufeff").strip() or "[]")
    except (ValueError, TypeError) as exc:
        raise TokenError("Không đọc được danh sách chứng thư từ Windows.") from exc
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        raise TokenError("Danh sách chứng thư Windows có định dạng không hợp lệ.")
    result: dict[str, Certificate] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TokenError("Dữ liệu chứng thư Windows không hợp lệ.")
        thumbprint = str(row.get("thumbprint", "")).replace(" ", "").upper()
        subject = str(row.get("subject", "")).strip()
        label = str(row.get("label", "")).strip()
        if not re.fullmatch(r"[0-9A-F]{40,128}", thumbprint) or not subject:
            raise TokenError("Windows trả về chứng thư thiếu mã nhận diện hoặc chủ thể.")
        result[thumbprint] = Certificate(thumbprint, subject, label or subject)
    return sorted(result.values(), key=lambda cert: (cert.label.casefold(), cert.thumbprint))


def list_certificates() -> list[Certificate]:
    """List certificate metadata with a private-key binding; never export keys."""
    _require_windows()
    # The script is constant: no caller input is interpolated into PowerShell.
    script = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$items = @(Get-ChildItem -Path Cert:\CurrentUser\My,Cert:\LocalMachine\My |
    Where-Object { $_.HasPrivateKey } |
    ForEach-Object {
        [pscustomobject]@{
            thumbprint = $_.Thumbprint
            subject = $_.Subject
            label = ($_.GetNameInfo([System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false) + ' | ' + $_.NotAfter.ToString('yyyy-MM-dd') + ' | ' + $_.Thumbprint)
        }
    })
ConvertTo-Json -InputObject $items -Compress
"""
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, timeout=25, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise TokenError("Không thể đọc chứng thư Windows. Kiểm tra PowerShell và driver Token.") from exc
    if proc.returncode:
        # Do not surface raw process output, which can contain customer details.
        raise TokenError("Windows không cho đọc danh sách chứng thư. Kiểm tra quyền và driver USB Token.")
    return _parse_certificates(proc.stdout.decode("utf-8-sig", errors="replace"))


def _debugger_state(port: int) -> str:
    """Return free/chrome/occupied; never use an outbound proxy for loopback."""
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            pass
    except ConnectionRefusedError:
        return "free"
    except OSError as exc:
        raise TokenError("Không kiểm tra được cổng Chrome Debug trên máy này.") from exc
    try:
        opener = build_opener(ProxyHandler({}))
        with opener.open(f"http://127.0.0.1:{port}/json/version", timeout=1.5) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            return "occupied"
        data = json.loads(raw)
        browser = data.get("Browser", "")
        websocket = urlsplit(data.get("webSocketDebuggerUrl", ""))
        if (
            browser.startswith(("Chrome/", "HeadlessChrome/"))
            and websocket.scheme == "ws"
            and websocket.hostname in {"127.0.0.1", "localhost", "::1"}
            and websocket.port == port
            and websocket.path.startswith("/devtools/browser/")
        ):
            return "chrome"
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return "occupied"


def launch_chrome(base_url: str = "https://admin.csdlksk.vn", port: int = 9222) -> None:
    """Launch a dedicated Chrome profile, exposing debugging on loopback only."""
    _require_windows()
    target = urlsplit(base_url)
    if target.scheme != "https" or not target.hostname or target.username or target.password:
        raise TokenError("Địa chỉ hệ thống phải là HTTPS và không chứa thông tin đăng nhập.")
    if not isinstance(port, int) or not 1024 <= port <= 65535:
        raise TokenError("Cổng Chrome Debug phải nằm trong khoảng 1024–65535.")
    state = _debugger_state(port)
    if state == "chrome":
        return
    if state != "free":
        raise TokenError(f"Cổng {port} đang được ứng dụng khác sử dụng; hãy đóng ứng dụng đó.")
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise TokenError("Không xác định được thư mục LOCALAPPDATA của Windows.")
    candidates = [Path(local) / "Google/Chrome/Application/chrome.exe"]
    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        if os.environ.get(variable):
            candidates.append(Path(os.environ[variable]) / "Google/Chrome/Application/chrome.exe")
    executable = next((p for p in candidates if p.is_file()), None)
    if executable is None:
        raise TokenError("Không tìm thấy Google Chrome. Hãy cài Chrome trên Windows rồi thử lại.")
    profile = Path(local) / "KySoPython" / "ChromeProfile"
    profile.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.Popen(
            [str(executable), "--remote-debugging-address=127.0.0.1", f"--remote-debugging-port={port}",
             f"--user-data-dir={profile}", "--no-first-run", base_url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as exc:
        raise TokenError("Không khởi động được Google Chrome.") from exc
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        state = _debugger_state(port)
        if state == "chrome":
            return
        if state == "occupied":
            raise TokenError("Cổng Debug đã mở nhưng không phải endpoint Chrome hợp lệ.")
        time.sleep(0.3)
    raise TokenError("Chrome chưa mở cổng Debug sau 20 giây. Đóng cửa sổ Chrome của tool rồi thử lại.")


def _noop(_message: str) -> None:
    pass


def _check_stop(stop_event) -> None:
    if stop_event is not None and stop_event.is_set():
        raise TokenError("Đã dừng xử lý USB Token theo yêu cầu.")


class ManualTokenPrompt:
    """Leave certificate selection and PIN entry to the Windows user."""

    def __init__(self, log: Callable[[str], None] = _noop):
        self.log = log

    def handle(self, certificate: Certificate | None, pin: str, stop_event) -> None:
        _check_stop(stop_event)
        self.log("Chọn đúng chứng thư và nhập PIN trong hộp thoại USB Token; tool đang chờ nút Complete.")


_SECURITY_TITLES = {"windows security", "bảo mật windows", "bao mat windows"}
_PIN_TITLES = {"verify user pin", "kiểm tra mã pin", "kiem tra ma pin"}
_MORE_BUTTONS = {"more choices", "thêm lựa chọn", "them lua chon", "more options"}
_CONFIRM_BUTTONS = {"ok", "continue", "tiếp tục", "tiep tuc"}
_LOGIN_BUTTONS = {"login", "đăng nhập", "dang nhap", "ok"}


def _normalized(text: str) -> str:
    return " ".join(str(text).split()).casefold()


def _dialog_kind(title: str) -> str | None:
    text = _normalized(title)
    if text in _SECURITY_TITLES:
        return "security"
    if text in _PIN_TITLES:
        return "pin"
    return None


def _name(control) -> str:
    return str(control.window_text()).strip()


def _visible_enabled(control) -> bool:
    return bool(control.is_visible() and control.is_enabled())


def _button(window, names: set[str]):
    matches = [item for item in window.descendants(control_type="Button")
               if _visible_enabled(item) and _normalized(_name(item)) in names]
    if len(matches) > 1:
        raise TokenError("Có nhiều nút xác nhận giống nhau; hãy chuyển sang chế độ nhập PIN thủ công.")
    return matches[0] if matches else None


def _certificate_names(certificate: Certificate) -> set[str]:
    names = {_normalized(certificate.subject)}
    # Windows certificate pickers normally show CN, not the entire X.500 name.
    match = re.search(r'(?:^|,)\s*CN\s*=\s*("(?:[^"]|"")*"|[^,]+)', certificate.subject, re.IGNORECASE)
    if match:
        names.add(_normalized(match.group(1).strip('"').replace('""', '"')))
    return {name for name in names if name}


def _certificate_choice(window, certificate: Certificate):
    names = _certificate_names(certificate)
    matches = []
    # Restrict selection to actual list items. Matching arbitrary desktop text
    # would risk picking an unrelated certificate or clicking a heading.
    for item in window.descendants(control_type="ListItem"):
        if not _visible_enabled(item):
            continue
        labels = [_name(item)] + [_name(child) for child in item.descendants(control_type="Text")]
        if any(_normalized(label) in names for label in labels):
            matches.append(item)
    if len(matches) > 1:
        raise TokenError("Nhiều chứng thư có cùng tên; chọn chứng thư thủ công để tránh ký nhầm.")
    return matches[0] if matches else None


def _password_edit(window):
    edits = []
    for item in window.descendants(control_type="Edit"):
        try:
            masked = bool(item.element_info.element.CurrentIsPassword)
        except (AttributeError, RuntimeError):
            masked = False
        if _visible_enabled(item) and masked:
            edits.append(item)
    if len(edits) > 1:
        raise TokenError("Hộp thoại có nhiều ô mật khẩu; hãy nhập PIN thủ công.")
    return edits[0] if edits else None


class AutomatedTokenPrompt:
    """One PIN submission to an explicitly recognized dialog, with no retries.

    Some middleware/secure-desktop prompts cannot be automated through UIA.
    Those cases fail closed and must be handled in manual mode. A listed
    certificate means Windows has a private-key binding; it does not prove the
    currently inserted USB device or a successful digital signature.
    """

    def __init__(self, log: Callable[[str], None] = _noop, timeout: float = 60):
        self.log = log
        self.timeout = timeout

    def handle(self, certificate: Certificate | None, pin: str, stop_event) -> None:
        _require_windows()
        if certificate is None or not pin:
            raise TokenError("Chế độ tự động cần chọn chứng thư và nhập PIN USB Token.")
        _check_stop(stop_event)
        try:
            from pywinauto import Desktop
        except ImportError as exc:
            raise TokenError("Thiếu pywinauto; chạy CaiDat.cmd hoặc chọn nhập PIN thủ công.") from exc
        try:
            desktop = Desktop(backend="uia")
            self._handle_desktop(desktop, certificate, pin, stop_event)
        except TokenError:
            raise
        except Exception as exc:
            # Do not forward vendor UI exception text or entered values.
            raise TokenError("Không điều khiển được hộp thoại Token; dừng lô và thử chế độ PIN thủ công.") from exc

    def _handle_desktop(self, desktop, certificate: Certificate, pin: str, stop_event) -> None:
        deadline = time.monotonic() + self.timeout
        selected = False
        expanded = False
        confirmed = False
        while time.monotonic() < deadline:
            _check_stop(stop_event)
            windows = [window for window in desktop.windows(control_type="Window")
                       if _visible_enabled(window) and _dialog_kind(_name(window))]
            if len(windows) > 1:
                raise TokenError("Có nhiều hộp thoại bảo mật; hãy đóng các yêu cầu khác và chọn nhập PIN thủ công.")
            if not windows:
                time.sleep(0.2)
                continue
            window = windows[0]
            kind = _dialog_kind(_name(window))
            edit = _password_edit(window)
            if edit is not None:
                if kind == "security" and not selected:
                    raise TokenError("Windows đang hỏi PIN nhưng chưa xác nhận được chứng thư; hãy dùng chế độ thủ công.")
                button = _button(window, _LOGIN_BUTTONS)
                if button is None:
                    raise TokenError("Không xác định được nút đăng nhập PIN; hãy nhập thủ công.")
                _check_stop(stop_event)
                edit.set_edit_text(pin)
                try:
                    _check_stop(stop_event)
                except TokenError:
                    edit.set_edit_text("")
                    raise
                # Never retry this invocation; a wrong PIN can lock a token.
                button.invoke()
                self.log("Đã gửi PIN một lần; chờ hộp thoại Token đóng.")
                close_deadline = time.monotonic() + min(10.0, max(0.1, deadline - time.monotonic()))
                while time.monotonic() < close_deadline:
                    _check_stop(stop_event)
                    try:
                        still_visible = window.is_visible()
                    except Exception:
                        still_visible = False
                    if not still_visible:
                        self.log("Hộp thoại Token đã đóng; tiếp tục kiểm tra nút Complete trên website.")
                        return
                    time.sleep(0.2)
                raise TokenError("Hộp thoại PIN chưa đóng sau một lần gửi; lô đã dừng. Kiểm tra PIN trên Windows, không thử lặp lại.")
            if kind == "pin":
                # Recognized title alone is insufficient to type a secret.
                raise TokenError("Không tìm thấy ô PIN được Windows đánh dấu là mật khẩu; hãy nhập thủ công.")
            if not selected:
                if not expanded:
                    more = _button(window, _MORE_BUTTONS)
                    expanded = True
                    if more is not None:
                        _check_stop(stop_event)
                        more.invoke()
                        time.sleep(0.2)
                        continue
                choice = _certificate_choice(window, certificate)
                if choice is not None:
                    _check_stop(stop_event)
                    choice.select()
                    selected = True
                    self.log("Đã chọn chứng thư theo tên trong hộp thoại Windows Security.")
            if selected and not confirmed:
                button = _button(window, _CONFIRM_BUTTONS)
                if button is not None:
                    _check_stop(stop_event)
                    button.invoke()
                    confirmed = True
            time.sleep(0.2)
        raise TokenError("Không xác định được hộp thoại USB Token trong thời gian chờ; hãy chuyển sang nhập PIN thủ công.")
