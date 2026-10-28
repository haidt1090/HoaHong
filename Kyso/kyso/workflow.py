"""Execute one reviewed snapshot, without retrying uncertain signing commands."""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import Event
from typing import Any, Callable, Iterable


@dataclass
class BatchResult:
    attempted: int = 0
    completed_steps: int = 0
    failed: int = 0
    stopped: bool = False
    needs_review: list[str] = field(default_factory=list)
    error: str = ""


class BatchSigner:
    """Stop at record boundaries; a UI action is not proof of a valid signature.

    Each record is opened once, and an exception ends the entire batch.  In
    particular, failures after sending a token or Complete command must never
    cause an automatic retry: the server may already have applied the command.
    """

    def __init__(self, browser: Any, token_prompt: Any,
                 log: Callable[[str], None] | None = None) -> None:
        self.browser = browser
        self.token_prompt = token_prompt
        self.log = log or (lambda message: None)

    @staticmethod
    def _snapshot(records: Iterable[Any]) -> list[Any]:
        snapshot: list[Any] = []
        seen: set[str] = set()
        for record in records:
            record_id = getattr(record, "check_up_id", None)
            if not isinstance(record_id, str) or not record_id.strip():
                raise ValueError("Hồ sơ được chọn thiếu check_up_id hợp lệ.")
            if record_id != record_id.strip():
                raise ValueError("check_up_id không được chứa khoảng trắng ở hai đầu.")
            status = getattr(record, "status", None)
            if not isinstance(status, str) or status.casefold() != "init":
                raise ValueError("Chỉ được ký hồ sơ có trạng thái init.")
            if record_id not in seen:
                seen.add(record_id)
                snapshot.append(record)
        return snapshot

    def _log(self, message: str) -> None:
        # A broken observer must not interrupt or retry a signing operation.
        try:
            self.log(message)
        except Exception:
            pass

    def run(self, records: Iterable[Any], certificate: Any = None,
            pin: str = "", stop_event: Event | None = None) -> BatchResult:
        snapshot = self._snapshot(records)
        stop_event = stop_event if stop_event is not None else Event()
        result = BatchResult()
        for record in snapshot:
            if stop_event.is_set():
                result.stopped = True
                self._log("Đã dừng trước hồ sơ tiếp theo.")
                break
            record_id = record.check_up_id
            result.attempted += 1
            self._log(f"Đang thao tác hồ sơ ID={record_id}.")
            # The UI's stop button applies to the next record.  Do not cancel
            # an ongoing smart-card transaction or close its tab halfway.
            in_flight = Event()
            issued_command = False
            stage = "mở tab hồ sơ"
            try:
                with self.browser.open_record(record):
                    # Mark uncertain *before* dispatch: a driver exception may
                    # arrive after the click was received by the application.
                    issued_command = True
                    stage = "mở tài liệu bằng nút submit"
                    self.browser.click_css('button[type="submit"]')
                    stage = "chọn vị trí chữ ký trên PDF"
                    self.browser.click_css(
                        'button[aria-label="Chọn chữ ký để đặt vào PDF"]')
                    stage = "tạo chữ ký mới"
                    self.browser.click_text("Tạo chữ ký mới")
                    stage = "lưu vị trí chữ ký (Save signature)"
                    self.browser.click_text("Save signature")
                    stage = "gửi lệnh Sign with USB Token"
                    self.browser.click_text("Sign with USB Token")
                    stage = "chọn chứng thư và xác nhận PIN USB Token"
                    self.token_prompt.handle(certificate, pin, in_flight)
                    stage = "chờ nút Complete sau khi xử lý USB Token"
                    self.browser.wait_complete(timeout=120, stop_event=in_flight)
                    stage = "gửi nút Complete"
                    self.browser.click_text("Complete")
                    stage = "đóng tab hồ sơ sau khi gửi Complete"
                result.completed_steps += 1
                self._log(
                    f"ID={record_id}: đã gửi Complete; cần kiểm tra trạng thái "
                    "và chữ ký trên hệ thống.")
            except Exception as exc:
                result.failed += 1
                if issued_command:
                    result.needs_review.append(record_id)
                # Do not expose arbitrary exception text: an external driver or
                # token implementation could include sensitive input in it.
                result.error = (
                    f"Dừng tại ID={record_id}, bước {stage} ({type(exc).__name__}). "
                    "Kiểm tra cửa sổ trình duyệt/USB và trạng thái hồ sơ trước "
                    "khi thao tác lại. Ứng dụng không tự thử lại.")
                self._log(result.error)
                result.stopped = True
                break
            if stop_event.is_set():
                result.stopped = True
                self._log("Đã hoàn tất thao tác hiện tại và dừng theo yêu cầu.")
                break
        return result
