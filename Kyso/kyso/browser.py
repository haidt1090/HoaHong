"""Chrome automation for the existing CSDLKSK signing workflow.

This module never logs in, exports cookies, or starts a signing operation by
itself. The browser must already contain an authenticated tab. Selenium is
loaded lazily so parsing and unit tests also run without a Windows desktop.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
import time
from typing import Callable, Iterator
from urllib.parse import quote, urlencode, urlsplit


class BrowserError(RuntimeError):
    """An actionable browser or API failure."""


class BrowserCancelled(BrowserError):
    """The user requested a stop before the next operation."""


@dataclass(frozen=True)
class Record:
    check_up_id: str
    full_name: str = ""
    status: str = "init"


@dataclass(frozen=True)
class BulkRecord:
    """A displayed bulk-sign row, not an API record or a guessed document ID."""
    row_number: str
    full_name: str
    masked_identifier: str
    status: str


def xpath_literal(value: str) -> str:
    """Quote arbitrary text as an XPath 1.0 string literal."""
    if "'" not in value:
        return "'" + value + "'"
    if '"' not in value:
        return '"' + value + '"'
    return "concat(" + ', "\'", '.join("'" + part + "'" for part in value.split("'")) + ")"


def _origin(value: str) -> tuple[str, str, int]:
    try:
        parsed = urlsplit(value)
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("userinfo")
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("https required")
        return parsed.scheme, parsed.hostname.lower(), parsed.port or 443
    except ValueError as exc:
        raise BrowserError("Địa chỉ hệ thống phải là URL HTTPS hợp lệ, không chứa tài khoản.") from exc


def _cancelled(stop_event) -> None:
    if stop_event is not None and stop_event.is_set():
        raise BrowserCancelled("Đã dừng theo yêu cầu.")


_FETCH_SCRIPT = """
const done = arguments[arguments.length - 1];
const controller = new AbortController();
const timer = setTimeout(() => controller.abort(), 20000);
fetch(arguments[0], {method: 'GET', credentials: 'include',
    redirect: 'error', signal: controller.signal,
    headers: {'Accept': 'application/json'}})
.then(async r => done(JSON.stringify({httpStatus:r.status,body:await r.text()})))
.catch(() => done(JSON.stringify({error:'Không gọi được API; kiểm tra phiên đăng nhập và kết nối.'})))
.finally(() => clearTimeout(timer));
"""


_VISIBLE_RECORDS_SCRIPT = """
// Read only the bulk-selection table: no checkbox click, request or submission.
const visible = element => element.getClientRects().length > 0;
const normalize = text => text.trim().replace(/\\s+/g, ' ').toLocaleLowerCase('vi');
const tables = [...document.querySelectorAll('table')].filter(table => {
    const headers = [...table.querySelectorAll('thead th')].map(th => normalize(th.textContent));
    return visible(table) && ['stt', 'họ và tên', 'trạng thái'].every(h => headers.includes(h))
        && [...table.querySelectorAll('tbody input[type="checkbox"], tbody [role="checkbox"]')].some(visible);
});
if (tables.length !== 1) return null;
const table = tables[0];
const headers = [...table.querySelectorAll('thead th')].map(th => normalize(th.textContent));
return [...table.querySelectorAll('tbody tr')].filter(visible).map(row => {
    const cells = [...row.querySelectorAll('td')];
    const read = heading => cells[headers.indexOf(heading)]?.textContent.trim() || '';
    const checks = [...row.querySelectorAll('input[type="checkbox"], [role="checkbox"]')].filter(visible);
    return {
        row_number: read('stt'), name: read('họ và tên'),
        masked_identifier: read('số định danh cá nhân'), status: read('trạng thái'),
        selectable: checks.length === 1 && !checks[0].disabled && checks[0].getAttribute('aria-disabled') !== 'true'
    };
});
"""

class ChromeSession:
    MAX_PAGES = 1000
    MAX_RECORDS = 10000
    PAGE_SIZE = 100

    def __init__(
        self,
        debugger_address: str = "127.0.0.1:9222",
        base_url: str = "https://admin.csdlksk.vn",
        log: Callable[[str], None] | None = None,
        *,
        driver=None,
        keep_completed_tabs: bool = False,
    ) -> None:
        try:
            debug = urlsplit("http://" + debugger_address)
            if (debug.hostname != "127.0.0.1" or debug.port is None
                    or not 1 <= debug.port <= 65535 or debug.username is not None
                    or debug.password is not None or debug.path or debug.query or debug.fragment):
                raise ValueError("local endpoint required")
        except ValueError as exc:
            raise BrowserError("Cổng Chrome phải có dạng 127.0.0.1:9222 (chỉ trên máy này).") from exc
        self.origin = _origin(base_url)
        base = urlsplit(base_url)
        if base.path not in ("", "/") or base.query or base.fragment:
            raise BrowserError("Địa chỉ hệ thống chỉ gồm https://tên-miền, không gồm đường dẫn.")
        self.base_url = base_url.rstrip("/")
        self.debugger_address = debugger_address
        self.log = log or (lambda message: None)
        self.driver = driver
        self.keep_completed_tabs = keep_completed_tabs
        self._base_handle: str | None = None
        self._connected = False

    def connect(self) -> None:
        created = self.driver is None
        if created:
            try:
                from .connection import attach
                self.driver = attach(self.debugger_address, self.log)
            except ImportError as exc:
                raise BrowserError("Chưa cài Selenium. Chạy CaiDat.cmd trước.") from exc
            except Exception as exc:
                from .connection import safe_error, save_failure
                detail = safe_error(exc)
                self.log(detail)
                saved = save_failure(detail)
                if saved:
                    self.log(f"Chi tiết kết nối đã lưu tại {saved}")
                raise BrowserError(detail) from exc
        try:
            name = str(self.driver.capabilities.get("browserName", "")).lower()
            if name not in ("chrome", "chromium"):
                raise BrowserError("Kết nối này cần Chrome hoặc Chromium.")
            self.driver.set_script_timeout(30)
            self.driver.set_page_load_timeout(45)
            original = self.driver.current_window_handle
            for handle in list(self.driver.window_handles):
                self.driver.switch_to.window(handle)
                try:
                    same_origin = _origin(self.driver.current_url) == self.origin
                except BrowserError:
                    continue
                path = urlsplit(self.driver.current_url).path.lower()
                if same_origin and not any(part in ("login", "signin", "sign-in") for part in path.split("/")):
                    self._base_handle = handle
                    self._connected = True
                    self.log("Đã kết nối Chrome. Quét hồ sơ để kiểm tra phiên đăng nhập.")
                    return
            if original in self.driver.window_handles:
                self.driver.switch_to.window(original)
            raise BrowserError("Hãy mở tab hệ thống và đăng nhập trước khi kết nối Chrome.")
        except BrowserError:
            if created:
                self.disconnect()
            raise
        except Exception as exc:
            if created:
                self.disconnect()
            raise BrowserError("Không đọc được các tab Chrome. Hãy mở lại kết nối.") from exc

    def disconnect(self) -> None:
        """Close driver transport/service only; never quit the attached browser."""
        driver, self.driver = self.driver, None
        self._connected = False
        self._base_handle = None
        if driver is None:
            return
        try:
            executor = getattr(driver, "command_executor", None)
            if executor is not None and hasattr(executor, "close"):
                executor.close()
        except Exception:
            self.log("Không đóng được kết nối driver; Chrome vẫn được giữ nguyên.")
        try:
            service = getattr(driver, "service", None)
            if service is not None:
                service.stop()
        except Exception:
            self.log("Không dừng được dịch vụ driver; Chrome vẫn được giữ nguyên.")

    def _require_connected(self):
        if not self._connected or self.driver is None:
            raise BrowserError("Chưa kết nối Chrome.")
        return self.driver

    def _ensure_site(self) -> None:
        driver = self._require_connected()
        try:
            actual = _origin(driver.current_url)
        except BrowserError as exc:
            raise BrowserError("Tab đã chuyển khỏi hệ thống; dừng thao tác.") from exc
        if actual != self.origin:
            raise BrowserError("Tab đã chuyển khỏi hệ thống; dừng thao tác.")

    def _select_base(self) -> None:
        driver = self._require_connected()
        if self._base_handle not in driver.window_handles:
            raise BrowserError("Tab hệ thống ban đầu đã đóng. Hãy kết nối lại Chrome.")
        driver.switch_to.window(self._base_handle)
        self._ensure_site()

    def _fetch_page(self, page: int) -> tuple[int, list[dict]]:
        self._ensure_site()
        query = urlencode({"page_number": page, "page_size": self.PAGE_SIZE, "status": "init"})
        path = "/api/checkup/health-examinations/all?" + query
        try:
            result = self.driver.execute_async_script(_FETCH_SCRIPT, path)
            envelope = json.loads(result) if isinstance(result, str) else result
            if not isinstance(envelope, dict):
                raise ValueError("envelope")
            if envelope.get("error"):
                raise BrowserError("Không gọi được API. Kiểm tra kết nối và đăng nhập lại.")
            http_status = envelope.get("httpStatus")
            if type(http_status) is not int:
                raise ValueError("status")
            if http_status != 200:
                raise BrowserError(f"API HTTP {http_status}. Kiểm tra phiên đăng nhập hoặc quyền truy cập.")
            body = envelope.get("body")
            body = json.loads(body) if isinstance(body, str) else body
            if not isinstance(body, dict):
                raise ValueError("body")
            header = body.get("header")
            if not isinstance(header, dict):
                raise ValueError("header")
            if header.get("success") is not True:
                raise BrowserError("API không chấp nhận yêu cầu. Kiểm tra phiên đăng nhập và quyền xem hồ sơ.")
            data = body.get("data")
            if not isinstance(data, dict):
                raise ValueError("data")
            total_pages = data.get("total_pages")
            if isinstance(total_pages, str) and total_pages.isascii() and total_pages.isdigit():
                total_pages = int(total_pages)
            if type(total_pages) is not int or total_pages < 0:
                raise ValueError("total_pages")
            if total_pages > self.MAX_PAGES:
                raise BrowserError(f"Có hơn {self.MAX_PAGES} trang. Hãy thu hẹp danh sách trước khi quét.")
            rows = data.get("data")
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise ValueError("rows")
            if total_pages == 0 and rows:
                raise ValueError("inconsistent pages")
            return total_pages, rows
        except BrowserError:
            raise
        except Exception as exc:
            raise BrowserError("Không đọc được danh sách API đúng định dạng. Hãy kiểm tra phiên đăng nhập hoặc cập nhật bộ kết nối.") from exc

    def scan_pending(self, stop_event=None, *, limit: int | None = None,
                     exclude_ids=()) -> list[Record]:
        """Read a bounded, deduplicated pending snapshot before any signing."""
        if limit is not None and (type(limit) is not int or limit < 1):
            raise ValueError("Giới hạn hồ sơ phải là số nguyên dương.")
        self._select_base()
        result: list[Record] = []
        excluded = set(exclude_ids)
        seen: set[str] = set()
        expected_pages = None
        page = 1
        while True:
            _cancelled(stop_event)
            pages, rows = self._fetch_page(page)
            if expected_pages is None:
                expected_pages = pages
            elif pages != expected_pages:
                raise BrowserError("Danh sách thay đổi trong lúc quét. Hãy quét lại trước khi ký.")
            for row in rows:
                _cancelled(stop_event)
                status = row.get("status")
                if not isinstance(status, str):
                    raise BrowserError("Hồ sơ thiếu trạng thái hợp lệ. Dừng quét để tránh chọn nhầm.")
                if status != "init":
                    continue
                identifier = row.get("check_up_id")
                if type(identifier) not in (str, int) or not str(identifier).strip():
                    raise BrowserError("Hồ sơ thiếu mã định danh hợp lệ. Dừng quét.")
                identifier = str(identifier)
                if len(identifier) > 256:
                    raise BrowserError("Mã hồ sơ không hợp lệ.")
                full_name = row.get("full_name", "")
                if not isinstance(full_name, str):
                    raise BrowserError("Tên hồ sơ không đúng định dạng.")
                if identifier in seen:
                    continue
                seen.add(identifier)
                if len(seen) > self.MAX_RECORDS:
                    raise BrowserError(f"Có hơn {self.MAX_RECORDS} hồ sơ. Hãy thu hẹp danh sách trước khi quét.")
                if identifier in excluded:
                    continue
                result.append(Record(identifier, full_name, status))
                if limit is not None and len(result) >= limit:
                    self.log(f"Đã lấy đủ {limit} hồ sơ chờ ký cho đợt này.")
                    return result
            self.log(f"Đã quét trang {page}/{max(pages, 1)}: {len(result)} hồ sơ chờ ký.")
            if page >= max(pages, 1):
                return result
            page += 1

    def scan_list_preview(self, stop_event=None) -> list[BulkRecord]:
        """Open Hành động -> Ký nhiều file and read five pending checkbox rows.

        Only opens the selector. Does not select records or send signing commands.
        """
        driver = self._require_connected()
        _cancelled(stop_event)
        # Prefer the selected tab. Never pick a different list when several
        # tabs may have different filters, and never navigate to guessed IDs.
        handles = [driver.current_window_handle] + [
            h for h in driver.window_handles if h != driver.current_window_handle]
        matches = []
        original = driver.current_window_handle
        for handle in handles:
            _cancelled(stop_event)
            driver.switch_to.window(handle)
            try:
                url = urlsplit(driver.current_url)
                is_list = (_origin(driver.current_url) == self.origin and
                           url.path.rstrip('/') == '/admin/operation/health-checkup')
            except BrowserError:
                is_list = False
            if is_list:
                matches.append(handle)
                if handle == original:
                    break
        if len(matches) != 1:
            if original in driver.window_handles:
                driver.switch_to.window(original)
            raise BrowserError("Hãy chọn đúng tab danh sách Phiếu khám cần quét thử rồi kết nối lại.")
        driver.switch_to.window(matches[0])
        self._ensure_site()
        rows = driver.execute_script(_VISIBLE_RECORDS_SCRIPT)
        if rows is None:
            _cancelled(stop_event)
            self.click_text("Hành động")
            _cancelled(stop_event)
            self.click_text("Ký nhiều file")
            deadline = time.monotonic() + 15
            while rows is None:
                _cancelled(stop_event)
                self._ensure_site()
                rows = driver.execute_script(_VISIBLE_RECORDS_SCRIPT)
                if rows is not None:
                    break
                if time.monotonic() >= deadline:
                    raise BrowserError("Chưa nhận diện được bảng chọn hồ sơ trong Ký nhiều file. Không gọi API thay thế.")
                if stop_event is not None:
                    stop_event.wait(0.2)
                else:
                    time.sleep(0.2)
        if not isinstance(rows, list):
            raise BrowserError("Không đọc được bảng chọn hồ sơ Ký nhiều file.")
        result = []
        seen = set()
        for row in rows:
            _cancelled(stop_event)
            fields = ('row_number', 'name', 'masked_identifier', 'status')
            if not isinstance(row, dict) or any(not isinstance(row.get(key), str) for key in fields):
                raise BrowserError("Dòng hồ sơ trong Ký nhiều file không đúng định dạng.")
            if ' '.join(row['status'].split()).casefold() != 'chưa ký số':
                continue
            if row.get('selectable') is not True:
                continue
            number, name, identifier = (row[key].strip() for key in fields[:3])
            if not number.isascii() or not number.isdigit() or not name or not identifier:
                raise BrowserError("Dòng hồ sơ thiếu STT, họ tên hoặc số định danh hiển thị.")
            if number in seen:
                raise BrowserError("Bảng có STT trùng; dừng để tránh đọc nhầm dòng.")
            seen.add(number)
            result.append(BulkRecord(number, name, identifier, 'Chưa ký số'))
            if len(result) == 5:
                break
        if not result:
            raise BrowserError("Không thấy hồ sơ Chưa ký số có thể chọn trên trang hiện tại.")
        self._base_handle = matches[0]
        self.log(f"Đã đọc thử {len(result)} hồ sơ Chưa ký số từ Ký nhiều file; chưa chọn phiếu hoặc gửi lệnh ký.")
        return result

    @contextmanager
    def open_record(self, record: Record) -> Iterator[None]:
        driver = self._require_connected()
        self._select_base()
        previous_handles = set(driver.window_handles)
        original = driver.current_window_handle
        owned = None
        completed = False
        try:
            driver.switch_to.new_window("tab")
            candidate = driver.current_window_handle
            if candidate in previous_handles:
                raise BrowserError("Chrome không tạo được tab hồ sơ mới.")
            owned = candidate
            expected_path = "/admin/operation/health-checkup/" + quote(str(record.check_up_id), safe="")
            driver.get(self.base_url + expected_path)
            self._ensure_site()
            # A same-origin redirect to an expired-session/login form must not
            # let the generic submit selector click a saved login credential.
            actual_path = urlsplit(driver.current_url).path
            if actual_path not in (expected_path, expected_path + "/"):
                raise BrowserError(
                    "Trang không còn đúng hồ sơ đã chọn. Có thể phiên đăng nhập đã hết hạn "
                    "hoặc hồ sơ đã chuyển; kiểm tra tab rồi quét lại trước khi ký."
                )
            yield
            completed = True
        finally:
            # On failure the tab may contain an in-flight signature or security
            # prompt. Keep it open for manual inspection rather than disrupting it.
            cleanup_error = None
            try:
                handles = list(driver.window_handles)
                if owned is not None and owned in handles and owned not in previous_handles:
                    if completed and not self.keep_completed_tabs:
                        driver.switch_to.window(owned)
                        driver.close()
                    elif completed:
                        self.log("Giữ tab đã gửi Complete để bạn kiểm tra trạng thái trên hệ thống.")
                    else:
                        self.log("Giữ tab hồ sơ gặp lỗi để bạn kiểm tra thủ công.")
            except Exception as exc:
                cleanup_error = exc
            try:
                handles = list(driver.window_handles)
                for handle in (self._base_handle, original, *previous_handles):
                    if handle in handles:
                        driver.switch_to.window(handle)
                        break
            except Exception as exc:
                cleanup_error = cleanup_error or exc
            if cleanup_error is not None:
                if completed:
                    raise BrowserError("Không quay lại được tab hệ thống. Kiểm tra Chrome trước khi tiếp tục.") from cleanup_error
                self.log("Không quay lại được tab hệ thống sau lỗi; kiểm tra Chrome thủ công.")

    def _find_clickable(self, by: str, selector: str, timeout: float, stop_event=None):
        end = time.monotonic() + timeout
        while True:
            _cancelled(stop_event)
            self._ensure_site()
            try:
                matches = [element for element in self.driver.find_elements(by, selector)
                           if element.is_displayed() and element.is_enabled()]
                if len(matches) > 1:
                    raise BrowserError("Có nhiều nút cùng khớp; dừng để tránh bấm nhầm: " + selector)
                if matches:
                    return matches[0]
            except BrowserError:
                raise
            except Exception as exc:
                # DOM updates can stale a matching element between find/is_displayed.
                if exc.__class__.__name__ not in ("StaleElementReferenceException", "NoSuchElementException"):
                    raise BrowserError("Không đọc được nút trên trang hồ sơ.") from exc
            if time.monotonic() >= end:
                raise BrowserError("Không tìm thấy nút đang hiển thị và có thể bấm: " + selector)
            if stop_event is not None:
                if stop_event.wait(min(0.2, max(0, end - time.monotonic()))):
                    _cancelled(stop_event)
            else:
                time.sleep(min(0.2, max(0, end - time.monotonic())))

    def click_css(self, selector: str, timeout: float = 30) -> None:
        element = self._find_clickable("css selector", selector, timeout)
        try:
            element.click()
        except Exception as exc:
            raise BrowserError("Không bấm được nút trên trang. Kiểm tra hộp thoại hoặc lớp phủ.") from exc

    def wait_record_loaded(self, record: Record, timeout: float = 30,
                           stop_event=None) -> None:
        """Do not open signing on an empty or mismatched patient form."""
        end = time.monotonic() + timeout
        normalize = lambda value: " ".join(value.split()).casefold()
        expected = normalize(record.full_name)
        while True:
            _cancelled(stop_event)
            self._ensure_site()
            try:
                fields = [element for element in self.driver.find_elements("css selector", "input[placeholder]")
                          if normalize(element.get_attribute("placeholder") or "")
                          in ("nhập họ tên", "nhập họ và tên") and element.is_displayed()]
                if len(fields) == 1:
                    actual = normalize(fields[0].get_attribute("value") or "")
                    if actual and (not expected or actual == expected):
                        return
            except Exception as exc:
                if exc.__class__.__name__ != "StaleElementReferenceException":
                    raise BrowserError("Không kiểm tra được dữ liệu hồ sơ; dừng trước khi mở ký.") from exc
            if time.monotonic() >= end:
                raise BrowserError("Hồ sơ chưa tải đúng họ tên đã quét. Không bấm Lưu thông tin hoặc ký; kiểm tra trang hồ sơ.")
            if stop_event is not None:
                stop_event.wait(0.2)
            else:
                time.sleep(0.2)

    def click_text(self, text: str, timeout: float = 30) -> None:
        literal = xpath_literal(text)
        selector = ("//*[self::a or self::button or @role='button' or @role='menuitem' or self::input]"
                    f"[normalize-space(.)={literal} or @aria-label={literal} or @value={literal}]")
        element = self._find_clickable("xpath", selector, timeout)
        try:
            element.click()
        except Exception as exc:
            raise BrowserError("Không bấm được nút " + text + ". Kiểm tra hộp thoại hoặc lớp phủ.") from exc

    def wait_complete(self, timeout: float = 120, stop_event=None) -> None:
        literal = xpath_literal("Complete")
        selector = ("//*[self::button or @role='button' or self::input]"
                    f"[normalize-space(.)={literal} or @aria-label={literal} or @value={literal}]")
        self._find_clickable("xpath", selector, timeout, stop_event)
