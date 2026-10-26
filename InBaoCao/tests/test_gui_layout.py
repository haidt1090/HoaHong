"""Opt-in real Tk geometry checks: INBAOCAO_GUI_TESTS=1 + a display is required."""

import os
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch
from inbaocao.gui import App
from inbaocao.storage import Library


@unittest.skipUnless(
    os.environ.get("INBAOCAO_GUI_TESTS") == "1",
    "Kiểm tra GUI cần màn hình; bật INBAOCAO_GUI_TESTS=1",
)
class LayoutTests(unittest.TestCase):
    def make_app(self, folder, scaling):
        root = tk.Tk()
        root.tk.call("tk", "scaling", scaling)
        with patch(
            "inbaocao.gui.list_printers",
            return_value=(["Máy in thử A3"], "Máy in thử A3"),
        ):
            app = App(root, Library(folder))
        return root, app

    def assert_fully_visible(self, root, widget):
        self.assertTrue(widget.winfo_ismapped(), widget)
        self.assertGreaterEqual(widget.winfo_height(), widget.winfo_reqheight(), widget)
        top = widget.winfo_rooty() - root.winfo_rooty()
        left = widget.winfo_rootx() - root.winfo_rootx()
        self.assertGreaterEqual(top, 0)
        self.assertLessEqual(top + widget.winfo_height(), root.winfo_height())
        self.assertGreaterEqual(left, 0)
        self.assertLessEqual(left + widget.winfo_width(), root.winfo_width())

    def test_print_controls_keep_full_height_at_small_sizes_and_high_dpi(self):
        with tempfile.TemporaryDirectory() as folder:
            for scaling in [1.3333, 1.6667, 2.0]:
                root, app = self.make_app(Path(folder) / str(scaling), scaling)
                try:
                    for width, height in [(960, 620), (1280, 720), (1640, 1000)]:
                        with self.subTest(scaling=scaling, size=(width, height)):
                            root.geometry(f"{width}x{height}")
                            root.update()
                            for control in [
                                app.print_button,
                                app.preview_button,
                                app.export_button,
                                app.stop_button,
                                app.printer_combo,
                                app.progress,
                                app.print_status_label,
                            ]:
                                self.assert_fully_visible(root, control)
                            self.assertEqual(
                                app.print_button.cget("text"), "BẮT ĐẦU IN HÀNG LOẠT"
                            )
                finally:
                    app.close()

    def test_large_setup_area_cannot_push_print_buttons_off_screen(self):
        with tempfile.TemporaryDirectory() as folder:
            root, app = self.make_app(folder, 2.0)
            try:
                root.geometry("960x620")
                app.setup_panel.grid_propagate(False)
                app.setup_panel.configure(height=900)
                root.update()
                for control in [
                    app.print_button,
                    app.preview_button,
                    app.stop_button,
                    app.progress,
                ]:
                    self.assert_fully_visible(root, control)
            finally:
                app.close()

    def test_buttons_wrap_to_two_rows_when_requested_width_exceeds_window(self):
        with tempfile.TemporaryDirectory() as folder:
            root, app = self.make_app(folder, 2.0)
            try:
                root.geometry("960x620")
                app.print_button.configure(width=150)
                root.update()
                self.assertTrue(app.print_compact)
                self.assertEqual(int(app.print_button.grid_info()["columnspan"]), 3)
                for control in [
                    app.print_button,
                    app.preview_button,
                    app.export_button,
                    app.stop_button,
                ]:
                    self.assert_fully_visible(root, control)
            finally:
                app.close()

    def test_visible_summary_and_progress_follow_selection_and_print_events(self):
        with tempfile.TemporaryDirectory() as folder:
            root, app = self.make_app(folder, 1.6667)
            try:
                app.rows = [{"name": "Người thử A"}, {"name": "Người thử B"}]
                app.checked = {0}
                app.update_count()
                self.assertIn("1/2 người", app.print_summary.get())
                self.assertIn("Máy in thử A3", app.print_summary.get())
                self.assertIn("Chưa chọn mẫu", app.print_summary.get())
                app.job_kind = "print"
                app.events.put(("progress", (1, 2)))
                app.poll()
                self.assertIn("1/2 sổ", app.print_status.get())
                self.assertEqual(app.job_done, 1)
                app.stop()
                self.assertIn("Đang dừng", app.print_status.get())
                app.events.put(("message", "Hoàn tất gửi lệnh. Đã gửi 1/2 sổ."))
                app.poll()
                self.assertIn("Hoàn tất", app.print_status.get())
            finally:
                app.close()


if __name__ == "__main__":
    unittest.main()
