import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication
from PySide6.QtPdf import QPdfDocument
from PySide6.QtGui import QImage,QColor
from layout import grid_slots
from formats import FormatStore
import test_app as support
import test_connection as connection_support
from preview_editor import PreviewEditor
from help_dialog import HelpDialog
from connection_defaults import seed_needs_apply
from telegram_access import allowed_bot

class GeometryTests(unittest.TestCase):
    def test_negative_zero_and_positive_gap(self):
        for gap in [-10,0,3]:
            slots=grid_slots('A5','4 × 6 cm',gap_x=gap,gap_y=gap)
            self.assertAlmostEqual(slots[1][0]-slots[0][0]-40,gap)
            for x,y,w,h in slots:
                self.assertGreaterEqual(x,7); self.assertLessEqual(x+w,148-7+1e-6); self.assertLessEqual(y+h,210-7+1e-6)
    def test_invalid_overlap_rejected(self):
        with self.assertRaises(ValueError): grid_slots('A6','4 × 6 cm',gap_x=-40)
    def test_named_format_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            store=FormatStore(d); data={'paper':'A6','photo':'4 × 6 cm','count':4,'margin_mm':7,'gap_x_mm':-5,'gap_y_mm':0}
            store.save('Mẫu sát và chồng',data)
            self.assertEqual(store.load()['Mẫu sát và chồng']['gap_x_mm'],-5)
            self.assertNotIn('token',store.path.read_text())
    def test_custom_bot_username_can_be_changed_explicitly(self):
        self.assertFalse(allowed_bot({'username':'another_bot'})); self.assertTrue(allowed_bot({'username':'another_bot'},'another_bot'))

class PrivateFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.qt=QApplication.instance() or QApplication([])
    setUp=support.AppTests.setUp
    tearDown=support.AppTests.tearDown
    new_window=support.AppTests.new_window
    photo=support.AppTests.photo
    finish_print=support.AppTests.finish_print
    def test_preview_and_real_pdf_have_identical_custom_pagination(self):
        w=self.window
        w.enqueue(self.photo('one.png','red'),False); w.enqueue(self.photo('two.png','blue'),False); w.check_all(True)
        dialog=PreviewEditor(w,w.selected_entries(),self.base)
        dialog.set_values({'paper':'A6','photo':'4 × 6 cm','count':4,'margin_mm':7,'gap_x_mm':50,'gap_y_mm':50})
        self.assertEqual(len(dialog.pages),8); dialog.apply_values()
        path=self.base/'format.pdf'; support.application.render(support.application.create_printer(w.snapshot(),path),[entry[0] for entry in w.selected_entries()],w.snapshot())
        pdf=QPdfDocument(); pdf.load(str(path)); self.assertEqual(pdf.pageCount(),8); pdf.close(); del pdf
        self.qt.processEvents(); dialog.close()
    def test_apply_format_restores_with_auto_print_preference(self):
        w=self.window; w.enqueue(self.photo('one.png','red'),False); w.check_all(True); w.auto.setChecked(True)
        dialog=PreviewEditor(w,w.selected_entries(),self.base); dialog.name.setText('Chồng ngang')
        dialog.set_values({'paper':'A6','photo':'4 × 6 cm','count':4,'margin_mm':7,'gap_x_mm':-5,'gap_y_mm':0}); dialog.apply_and_close()
        self.assertTrue(w.auto.isChecked()); self.assertEqual(w.snapshot()['gap_x_mm'],-5)
        w.close(); restored=self.new_window()
        self.assertTrue(restored.auto.isChecked()); self.assertEqual(restored.snapshot()['gap_x_mm'],-5)
        self.assertIn('Chồng ngang',FormatStore(self.base).load())
    def test_private_seed_applies_once_and_saved_edits_win(self):
        seed={'mode':'bot','credentials':{'token':'123:test','expected_username':'pkhoahongbot'},'group_id':-123,'group_title':'Default group','auto_connect':True}
        # Use a fresh data folder to exercise the first private start, without any real token/network.
        w=self.window; w.close()
        with patch('telegram_ui.default_connection',return_value=seed),patch('telegram_ui.TelegramWorker',connection_support.Worker):
            first=self.new_window(); dialog=first.telegram_dialog
            self.assertTrue(dialog.token.text()=='123:test'); self.assertEqual(dialog.worker.selected,-123)
            first.auto.setChecked(True); dialog.group_id.setText('-456'); dialog.group_title.setText('Changed group'); dialog.select(); first.save_settings()
            self.assertTrue(first.auto.isChecked())
            worker=dialog.worker; dialog.stop(); worker.finished.emit(); self.qt.processEvents(); first.close()
            second=self.new_window(); self.assertEqual(second.telegram_dialog.worker.selected,-456); self.assertTrue(second.auto.isChecked())
            worker=second.telegram_dialog.worker; second.telegram_dialog.stop(); worker.finished.emit(); self.qt.processEvents()
    def test_notes_can_be_edited_and_reopened(self):
        dialog=HelpDialog(self.window,self.base); dialog.notes.setPlainText('Yêu cầu bổ sung của tôi'); dialog.save_notes(); dialog.close()
        other=HelpDialog(self.window,self.base); self.assertEqual(other.notes.toPlainText(),'Yêu cầu bổ sung của tôi'); other.close()
if __name__=='__main__': unittest.main()
