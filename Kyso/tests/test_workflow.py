from contextlib import contextmanager
from dataclasses import dataclass
from threading import Event
import unittest

from kyso.workflow import BatchSigner


@dataclass(frozen=True)
class Record:
    check_up_id: str
    full_name: str = "Tên bệnh nhân không được ghi vào log"
    status: str = "init"


class FakeBrowser:
    def __init__(self, fail=None, after_security=None, fail_open=False):
        self.calls = []
        self.fail = fail
        self.after_security = after_security
        self.fail_open = fail_open

    @contextmanager
    def open_record(self, record):
        self.calls.append(("open", record.check_up_id))
        if self.fail_open:
            raise RuntimeError("No tab")
        try:
            yield
        finally:
            self.calls.append(("close", record.check_up_id))

    def click_css(self, selector):
        self._click("css", selector)

    def click_text(self, text):
        self._click("text", text)
        if text == "Sign with USB Token" and self.after_security:
            self.after_security()

    def _click(self, kind, selector):
        self.calls.append((kind, selector))
        if selector == self.fail:
            raise RuntimeError("May have received click")

    def wait_complete(self, timeout=120, stop_event=None):
        self.calls.append(("wait", timeout))
        if stop_event and stop_event.is_set():
            raise RuntimeError("Unexpected in-flight cancellation")


class FakeToken:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def handle(self, certificate, pin, stop_event):
        self.calls.append((certificate, pin))
        if stop_event.is_set():
            raise RuntimeError("Unexpected in-flight cancellation")
        if self.fail:
            raise RuntimeError("bad PIN")


class BatchSignerTests(unittest.TestCase):
    def test_runs_selected_snapshot_once_in_order_and_never_claims_server_success(self):
        browser, token, logs = FakeBrowser(), FakeToken(), []
        result = BatchSigner(browser, token, logs.append).run(
            [Record("a"), Record("a"), Record("b")], certificate="cert", pin="secret")
        self.assertEqual((result.attempted, result.completed_steps, result.failed), (2, 2, 0))
        self.assertFalse(result.stopped)
        self.assertEqual(result.needs_review, [])
        self.assertEqual(browser.calls[:9], [
            ("open", "a"),
            ("css", 'button[type="submit"]'),
            ("css", 'button[aria-label="Chọn chữ ký để đặt vào PDF"]'),
            ("text", "Tạo chữ ký mới"), ("text", "Save signature"),
            ("text", "Sign with USB Token"), ("wait", 120),
            ("text", "Complete"), ("close", "a")])
        self.assertEqual(token.calls, [("cert", "secret"), ("cert", "secret")])
        self.assertIn("cần kiểm tra trạng thái", " ".join(logs))
        self.assertNotIn("secret", " ".join(logs))
        self.assertNotIn("Tên bệnh nhân", " ".join(logs))

    def test_validates_entire_snapshot_before_any_signing(self):
        for invalid in [Record(""), Record("  "), Record("a "), Record("x", status="signed")]:
            with self.subTest(invalid=invalid):
                browser = FakeBrowser()
                with self.assertRaises(ValueError):
                    BatchSigner(browser, FakeToken()).run([Record("valid"), invalid])
                self.assertEqual(browser.calls, [])

    def test_preexisting_stop_does_not_open_any_record(self):
        stop = Event()
        stop.set()
        browser = FakeBrowser()
        result = BatchSigner(browser, FakeToken()).run([Record("a")], stop_event=stop)
        self.assertEqual(result.attempted, 0)
        self.assertTrue(result.stopped)
        self.assertEqual(browser.calls, [])

    def test_stop_after_security_finishes_current_record_only(self):
        stop = Event()
        browser = FakeBrowser(after_security=stop.set)
        token = FakeToken()
        result = BatchSigner(browser, token).run([Record("a"), Record("b")], stop_event=stop)
        self.assertEqual((result.attempted, result.completed_steps, result.failed), (1, 1, 0))
        self.assertTrue(result.stopped)
        self.assertEqual(browser.calls[-2:], [("text", "Complete"), ("close", "a")])
        self.assertEqual(len(token.calls), 1)
        self.assertNotIn(("open", "b"), browser.calls)

    def test_uncertain_complete_error_closes_owned_tab_stops_batch_and_does_not_retry(self):
        browser = FakeBrowser(fail="Complete")
        result = BatchSigner(browser, FakeToken()).run([Record("a"), Record("b")])
        self.assertEqual((result.attempted, result.completed_steps, result.failed), (1, 0, 1))
        self.assertTrue(result.stopped)
        self.assertEqual(result.needs_review, ["a"])
        self.assertIn("bước gửi nút Complete", result.error)
        self.assertEqual(browser.calls.count(("text", "Complete")), 1)
        self.assertEqual(browser.calls[-1], ("close", "a"))
        self.assertNotIn(("open", "b"), browser.calls)

    def test_pin_error_never_retries_pin_or_sends_complete(self):
        browser, token = FakeBrowser(), FakeToken(fail=True)
        result = BatchSigner(browser, token).run([Record("a"), Record("b")], pin="secret")
        self.assertEqual(result.failed, 1)
        self.assertEqual(len(token.calls), 1)
        self.assertEqual(result.needs_review, ["a"])
        self.assertNotIn(("text", "Complete"), browser.calls)
        self.assertIn("chọn chứng thư và xác nhận PIN USB Token", result.error)
        self.assertNotIn("bad PIN", result.error)
        self.assertNotIn("secret", result.error)

    def test_open_failure_stops_without_marking_unissued_commands_uncertain(self):
        browser = FakeBrowser(fail_open=True)
        result = BatchSigner(browser, FakeToken()).run([Record("a"), Record("b")])
        self.assertEqual(result.failed, 1)
        self.assertEqual(result.needs_review, [])
        self.assertEqual(browser.calls, [("open", "a")])

    def test_logging_failure_cannot_cause_a_retry(self):
        def broken_logger(_message):
            raise RuntimeError("logger unavailable")
        browser = FakeBrowser()
        result = BatchSigner(browser, FakeToken(), broken_logger).run([Record("a")])
        self.assertEqual(result.completed_steps, 1)
        self.assertEqual(browser.calls.count(("text", "Complete")), 1)

    def test_empty_selection_performs_no_commands(self):
        browser = FakeBrowser()
        result = BatchSigner(browser, FakeToken()).run([])
        self.assertEqual(result.attempted, 0)
        self.assertEqual(browser.calls, [])


if __name__ == "__main__":
    unittest.main()
