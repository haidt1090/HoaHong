import os,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PySide6.QtCore import QObject,Signal,Qt
from PySide6.QtGui import QImage,QColor
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtPdf import QPdfDocument
with patch.dict(os.environ,{'LOCALAPPDATA':tempfile.gettempdir()}):
    import app as application
from connection_store import ConnectionStore
from test_connection import Vault

class FakePrintWorker(QObject):
    finished=Signal()
    def __init__(self,paths,settings,parent=None):
        super().__init__(parent); self.paths=list(paths); self.settings=dict(settings); self.error=None; self.started=False
    def start(self): self.started=True

class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.qt=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.base=Path(self.temp.name); self.vault=Vault()
        self.patches=[patch.object(application,'BASE',self.base),
            patch('telegram_ui.ConnectionStore',side_effect=lambda base:ConnectionStore(base,self.vault)),
            patch.object(application.QPrinterInfo,'availablePrinters',return_value=[SimpleNamespace(printerName=lambda:'Test printer')]),
            patch.object(application,'PrintWorker',FakePrintWorker)]
        for p in self.patches: p.start()
        self.windows=[]; self.window=self.new_window()
    def new_window(self):
        window=application.Window(); self.windows.append(window); self.qt.processEvents(); window.timer.stop(); return window
    def photo(self,name,color):
        path=self.base/name; image=QImage(300,400,QImage.Format.Format_RGB32); image.fill(QColor(color)); image.save(str(path)); return path
    def finish_print(self,window,error=None):
        if window.print_worker:
            window.print_worker.error=error; window.print_worker.finished.emit(); self.qt.processEvents(); self.qt.processEvents()
    def tearDown(self):
        for w in self.windows:
            if w.print_worker: self.finish_print(w)
            if not w.closed: w.close()
        self.qt.processEvents()
        for p in reversed(self.patches): p.stop()
        self.temp.cleanup()
    def test_thumbnails_checkbox_batch_selection_and_manual_print(self):
        w=self.window
        for name,color in [('one.jpg','blue'),('two.jpg','red')]: self.assertTrue(w.enqueue(self.photo(name,color),False))
        self.assertFalse(w.list.item(0).icon().isNull()); self.assertEqual(w.list.item(0).text(),'one.jpg')
        w.check_all(True); self.assertEqual(len(w.selected_entries()),2)
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes): w.manual()
        self.qt.processEvents(); self.assertTrue(w.print_worker.started); self.assertEqual(len(w.print_worker.paths),2)
        self.finish_print(w); self.assertEqual(w.db.execute("SELECT COUNT(*) FROM jobs WHERE state='submitted'").fetchone()[0],2)
        w.check_all(False)
        with self.assertRaises(ValueError): w.selected_entries()
    def test_auto_receiving_prints_without_confirmation_and_no_duplicate(self):
        w=self.window; w.auto.setChecked(True); path=self.photo('auto.png','green')
        with patch.object(QMessageBox,'question',side_effect=AssertionError('Auto must not ask for confirmation')):
            w.enqueue(path,True); self.qt.processEvents()
            self.assertTrue(w.print_worker.started); self.assertEqual(w.print_worker.paths,[path])
            w.enqueue(path,True); self.assertEqual(len(w.print_queue),0)
            self.finish_print(w)
        self.assertEqual(w.db.execute('SELECT state FROM jobs').fetchone()[0],'submitted')
    def test_add_files_also_prints_immediately_when_auto_enabled(self):
        w=self.window; path=self.photo('import.png','purple'); w.auto.setChecked(True)
        with patch.object(application.QFileDialog,'getOpenFileNames',return_value=([str(path)],'')):
            w.add_files()
        self.qt.processEvents(); self.assertIsNotNone(w.print_worker); self.assertEqual(w.print_worker.paths,[path]); self.finish_print(w)
    def test_old_photo_does_not_auto_print_when_auto_is_enabled(self):
        w=self.window; path=self.photo('old.png','yellow'); w.enqueue(path,False)
        w.auto.setChecked(True); self.qt.processEvents(); self.assertIsNone(w.print_worker)
    def test_new_photo_keeps_existing_manual_selection(self):
        w=self.window; w.enqueue(self.photo('one.png','blue'),False); w.check_all(True)
        w.telegram_dialog.active=True; w.telegram_dialog.receive(str(self.photo('two.png','red')))
        self.assertEqual([path.name for path,_ in w.selected_entries()],['one.png'])
    def test_save_and_restore_print_settings_and_auto(self):
        w=self.window; w.paper.setCurrentText('A6'); w.photo.setCurrentText('4 × 6 cm'); w.count.setValue(7)
        w.auto.setChecked(True); w.save_settings(); w.close()
        restored=self.new_window()
        self.assertEqual(restored.paper.currentText(),'A6'); self.assertEqual(restored.photo.currentText(),'4 × 6 cm')
        self.assertEqual(restored.count.value(),7); self.assertEqual(restored.printer.currentText(),'Test printer')
        self.assertTrue(restored.auto.isChecked())
    def test_library_is_restored_without_auto_printing_old_images(self):
        w=self.window; w.enqueue(self.photo('old.png','orange'),False); w.auto.setChecked(True); w.save_settings(); w.close()
        restored=self.new_window(); self.assertEqual(restored.list.count(),1); self.assertTrue(restored.auto.isChecked())
        self.assertIsNone(restored.print_worker)
    def test_multi_image_pdf_shares_page(self):
        w=self.window; paths=[self.photo('one.png','red'),self.photo('two.png','blue')]
        settings=w.snapshot(); settings.update(paper='A5',count=4)
        output=self.base/'batch.pdf'
        application.render(application.create_printer(settings,output),paths,settings)
        document=QPdfDocument(); document.load(str(output))
        self.assertEqual(document.pageCount(),1)
        self.assertAlmostEqual(document.pagePointSize(0).width(),148*72/25.4,delta=1)
        document.close()
    def test_auto_queue_cancellation_and_snapshot(self):
        w=self.window; w.auto.setChecked(True); w.count.setValue(3); w.enqueue(self.photo('one.png','red'),True)
        self.qt.processEvents(); self.assertEqual(w.print_worker.settings['count'],3)
        w.count.setValue(6); w.enqueue(self.photo('two.png','blue'),True)
        self.assertEqual(w.print_queue[0]['settings']['count'],6)
        w.auto.setChecked(False); self.assertEqual(len(w.print_queue),0)
        self.assertTrue(w.print_worker.started); self.finish_print(w)
        states=[r[0] for r in w.db.execute('SELECT state FROM jobs')]
        self.assertCountEqual(states,['submitted','cancelled'])
    def test_print_failure_stops_auto_and_marks_review(self):
        w=self.window; w.auto.setChecked(True); w.enqueue(self.photo('one.png','red'),True); self.qt.processEvents()
        self.finish_print(w,error='Printer unavailable')
        self.assertFalse(w.auto.isChecked()); self.assertIn('Printer unavailable',w.status.text())
        self.assertEqual(w.db.execute('SELECT state FROM jobs').fetchone()[0],'review')
    def test_stale_queue_is_recovered_and_manual_reprint_is_allowed(self):
        w=self.window; path=self.photo('old.png','orange'); w.enqueue(path,False)
        digest=next(iter(w.pending)); w.db.execute('INSERT INTO jobs VALUES (?,?,?)',(digest,'sending',str(path))); w.db.commit(); w.close()
        restored=self.new_window(); self.assertEqual(restored.recovered,1)
        self.assertEqual(restored.db.execute('SELECT state FROM jobs').fetchone()[0],'review')
        restored.send_batch([(path,digest)]); self.qt.processEvents()
        self.assertIsNotNone(restored.print_worker); self.finish_print(restored)
    def test_busy_photo_is_skipped_but_other_photos_can_print(self):
        w=self.window; one=self.photo('one.png','red'); two=self.photo('two.png','blue')
        w.enqueue(one,False); w.enqueue(two,False); entries=[(Path(path),digest) for digest,path in w.pending.items()]
        w.send_batch(entries[:1]); self.qt.processEvents()
        w.send_batch(entries)
        self.assertEqual(len(w.print_queue),1); self.assertEqual(len(w.print_queue[0]['entries']),1)
        self.assertEqual(w.print_queue[0]['entries'][0][0],two)
        self.finish_print(w); self.finish_print(w)
    def test_clicking_same_busy_photo_again_does_not_throw(self):
        w=self.window; path=self.photo('one.png','red'); w.enqueue(path,False)
        entry=(path,next(iter(w.pending))); w.send_batch([entry]); self.qt.processEvents()
        w.send_batch([entry]); self.assertEqual(len(w.print_queue),0)
        self.assertIn('không xếp thêm bản trùng',w.status.text()); self.finish_print(w)
if __name__=='__main__': unittest.main()
