"""Attach to the running Chrome version, without proxying local WebDriver traffic."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.request import ProxyHandler, build_opener


class ConnectionSetupError(RuntimeError):
    pass


def safe_error(exc):
    text = str(getattr(exc, 'msg', exc)).split('Stacktrace:')[0].strip()
    text = re.sub(r'(https?://)[^\s/]+@', r'\1[hidden]@', text)
    text = re.sub(r'(?i)(token|password|api_key|authorization)([=:]\s*)[^\s&]+', r'\1\2[hidden]', text)
    return f'{type(exc).__name__}: {text[:1200]}'


def chrome_version(address):
    try:
        with build_opener(ProxyHandler({})).open(f'http://{address}/json/version', timeout=5) as response:
            data = json.loads(response.read(65537))
        version = str(data.get('Browser', '')).split('/', 1)
        if len(version) != 2 or version[0] not in ('Chrome', 'HeadlessChrome') or not re.fullmatch(r'\d+(?:\.\d+){3}', version[1]):
            raise ValueError('Endpoint không trả về phiên bản Chrome hợp lệ')
        return version[1]
    except Exception as exc:
        raise ConnectionSetupError('Không đọc được Chrome Debug tại '+address+'. '+safe_error(exc)) from exc


def driver_version(path):
    try:
        result = subprocess.run([str(path), '--version'], capture_output=True,
                                text=True, timeout=10, check=True,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        match = re.search(r'ChromeDriver (\d+(?:\.\d+){3})', result.stdout)
        return match.group(1) if match else None
    except (OSError, subprocess.SubprocessError):
        return None


def resolve_driver(version, log):
    # A compatible installed driver also works without a download. Never use a
    # stale PATH driver merely because it is first on PATH.
    local = Path(__file__).resolve().parents[1] / 'drivers' / ('chromedriver.exe' if os.name == 'nt' else 'chromedriver')
    candidates = [str(local)] if local.is_file() else []
    on_path = shutil.which('chromedriver')
    if on_path:
        candidates.append(on_path)
    for path in candidates:
        actual = driver_version(path)
        if actual and actual.split('.')[0] == version.split('.')[0]:
            log(f'Dùng ChromeDriver {actual} với Chrome {version}.')
            return path
        log(f'Bỏ qua ChromeDriver không tương thích (phiên bản {actual or "không đọc được"}).')
    try:
        from selenium.webdriver.common.selenium_manager import SeleniumManager
        result = SeleniumManager().binary_paths([
            '--browser', 'chrome', '--browser-version', version,
            '--skip-driver-in-path', '--avoid-browser-download', '--avoid-stats', '--timeout', '30',
        ])
        path = result.get('driver_path')
        actual = driver_version(path) if path else None
        if not actual or actual.split('.')[0] != version.split('.')[0]:
            raise ValueError('Driver tải về không khớp phiên bản Chrome đang mở')
        log(f'Đã chọn ChromeDriver {actual} cho Chrome {version}.')
        return path
    except Exception as exc:
        raise ConnectionSetupError(
            f'Không chuẩn bị được ChromeDriver cho Chrome {version}. '
            'Cần truy cập googlechromelabs.github.io và storage.googleapis.com để tải driver, '
            'hoặc đặt ChromeDriver phù hợp vào thư mục drivers cạnh app.py. '+safe_error(exc)) from exc


def attach(address, log):
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    version = chrome_version(address)
    log(f'Chrome Debug đang mở: phiên bản {version}, địa chỉ {address}.')
    path = resolve_driver(version, log)
    options = webdriver.ChromeOptions()
    options.debugger_address = address
    # debuggerAddress attaches to an existing browser. ChromeDriver rejects
    # launch-only options such as detach in this mode. disconnect() stops only
    # driver transport/service and never issues a browser quit command.
    # Selenium 4.38 Chrome() does not expose ClientConfig. This supported Options
    # API changes only driver HTTP transport, preserving proxies for downloads
    # and the website. Do not unset the process's HTTP_PROXY/HTTPS_PROXY.
    options.ignore_local_proxy_environment_variables()
    service = Service(executable_path=path)
    try:
        return webdriver.Chrome(service=service, options=options)
    except Exception as exc:
        try:
            service.stop()
        except Exception:
            pass
        raise ConnectionSetupError(
            f'Không tạo được phiên điều khiển Chrome {version} tại {address}. '+safe_error(exc)) from exc


def save_failure(detail):
    """Persist only connection diagnostics, never browser cookies or token PINs."""
    import tempfile
    folder = Path(os.environ.get('LOCALAPPDATA', tempfile.gettempdir())) / 'KySoPython' / 'diagnostics'
    try:
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / 'last-connection.log'
        target.write_text(detail + '\n', encoding='utf-8')
        return target
    except OSError:
        return None
