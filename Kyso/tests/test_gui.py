"""Desktop checks enabled by KYSO_GUI_TESTS=1 and an actual display/Xvfb."""
from concurrent.futures import Future
from dataclasses import FrozenInstanceError
import os
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from kyso.browser import Record
from kyso.gui import SignerApp
from kyso.settings import AppSettings, load_settings
from kyso.windows import Certificate
from kyso.workflow import BatchResult


class ImmediateExecutor:
    def __init__(self):
        self.shutdown_options = None

    def submit(self, work):
        result = Future()
        try:
            result.set_result(work())
        except Exception as exc:
            result.set_exception(exc)
        return result

    def shutdown(self, **options):
        self.shutdown_options = options


@unittest.skipUnless(os.environ.get("KYSO_GUI_TESTS") == "1", "Cần màn hình; bật KYSO_GUI_TESTS=1")
class GuiTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.executor = ImmediateExecutor()
        with patch("kyso.gui.load_settings", return_value=AppSettings()):
            self.app = SignerApp(self.root, executor=self.executor, autoload=False)
        self.root.update()

    def tearDown(self):
        if not self.app.destroyed:
            self.app.closing = True
            self.app._finish_close()

    def drain(self):
        self.app._poll()
        self.root.update()

    def test_actions_fit_minimum_window_and_selection_controls_sign(self):
        self.root.geometry("900x700")
        self.root.update()
        self.assertIn("disabled", self.app.sign_button.state())
        for widget in [self.app.toolbar, self.app.controls, self.app.log_text,
                       self.app.stop_button, self.app.sign_button]:
            self.assertTrue(widget.winfo_ismapped())
            self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(), self.root.winfo_rootx() + self.root.winfo_width())
            self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(), self.root.winfo_rooty() + self.root.winfo_height())
        self.app._set_records([Record("test-id", "Du lieu gia")])
        self.app.tree.selection_set("record-0")
        self.root.update()
        self.assertNotIn("disabled", self.app.sign_button.state())
        self.assertIn("1 đã chọn", self.app.selection_summary.get())

    def test_saving_immutable_settings_excludes_pin(self):
        cert = Certificate("A" * 40, "CN=Test", "Test")
        self.app._set_certificates([cert])
        self.app.certificate_combo.current(0)
        self.app.automatic_pin.set(True)
        self.app.pin.set("not-to-save")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "settings.json"
            with patch("kyso.settings.settings_path", return_value=target):
                self.app.save()
            self.assertEqual(load_settings(target).certificate_thumbprint, "A" * 40)
            self.assertNotIn("not-to-save", target.read_text())
        self.assertTrue(self.app.settings.automatic_pin)

    def test_confirmation_cancel_sends_no_browser_commands(self):
        self.app._set_records([Record("one"), Record("two")])
        self.app.tree.selection_set("record-1")
        with patch("kyso.gui.messagebox.askyesno", return_value=False), patch.object(self.app, "_ensure_browser") as browser:
            self.app.sign_selected()
        browser.assert_not_called()
        self.assertFalse(self.app.busy)
        self.assertEqual(len(self.app.records), 2)

    def test_only_selected_records_run_and_snapshot_and_pin_are_cleared(self):
        self.app._set_records([Record("one"), Record("two")])
        self.app.tree.selection_set("record-1")
        self.app.pin.set("session-pin")
        browser = Mock()
        with patch("kyso.gui.messagebox.askyesno", return_value=True), \
             patch.object(self.app, "_ensure_browser", return_value=browser), \
             patch("kyso.gui.BatchSigner") as signer:
            signer.return_value.run.return_value = BatchResult(attempted=1, completed_steps=1)
            self.app.sign_selected()
            self.drain()
        selected = signer.return_value.run.call_args.args[0]
        self.assertEqual([r.check_up_id for r in selected], ["two"])
        self.assertEqual(signer.return_value.run.call_args.kwargs["pin"], "")
        self.assertEqual(self.app.pin.get(), "")
        self.assertFalse(self.app.records)
        self.assertIn("hoàn tất thao tác 1", self.app.status.get())
        self.assertIn("disabled", self.app.sign_button.state())

    def test_failed_scan_cannot_leave_previous_signable_snapshot(self):
        self.app._set_records([Record("old")])
        self.app.tree.selection_set("record-0")
        browser = Mock()
        browser.scan_pending.side_effect = RuntimeError("fixture failure")
        with patch.object(self.app, "_ensure_browser", return_value=browser), patch("kyso.gui.messagebox.showerror"):
            self.app.scan()
            self.drain()
        self.assertFalse(self.app.records)
        self.assertIn("disabled", self.app.sign_button.state())

    def test_automatic_pin_requires_selected_certificate(self):
        self.app._set_records([Record("one")])
        self.app.tree.selection_set("record-0")
        self.app.automatic_pin.set(True)
        self.app.pin.set("session-pin")
        with patch("kyso.gui.messagebox.showwarning") as warn, patch("kyso.gui.messagebox.askyesno") as confirm:
            self.app.sign_selected()
        warn.assert_called_once()
        confirm.assert_not_called()
        self.assertFalse(self.app.busy)

    def test_logged_pin_is_redacted_and_manual_mode_clears_pin(self):
        self.app.pin.set("sensitive-pin")
        self.app.log("accidental sensitive-pin")
        self.drain()
        self.assertNotIn("sensitive-pin", self.app.log_text.get("1.0", "end"))
        self.app.automatic_pin.set(False)
        self.app._pin_mode()
        self.assertEqual(self.app.pin.get(), "")

    def test_close_detaches_browser_and_does_not_cancel_detach(self):
        browser = Mock()
        self.app.browser = browser
        self.app.close()
        browser.disconnect.assert_called_once()
        self.assertFalse(self.executor.shutdown_options["cancel_futures"])


if __name__ == "__main__":
    unittest.main()
