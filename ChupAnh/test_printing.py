import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtGui import QImage,QColor
from PySide6.QtWidgets import QApplication
from PySide6.QtPdf import QPdfDocument
import printing
from layout import batch_pages
class BatchLayoutTests(unittest.TestCase):
    def test_mixed_photos_share_page_and_keep_counts(self):
        result=list(batch_pages('A5','3 × 4 cm',[('a',4),('b',4)]))
        self.assertEqual(len(result),1)
        self.assertEqual([p for p,_ in result[0]],['a']*4+['b']*4)
        self.assertEqual(len({rect for _,rect in result[0]}),8)
    def test_multiple_pages_and_invalid_count(self):
        result=list(batch_pages('A5','3 × 4 cm',[('a',37),('b',37)]))
        self.assertEqual(len(result),5); self.assertEqual(sum(len(page) for page in result),74)
        with self.assertRaises(ValueError): list(batch_pages('A5','3 × 4 cm',[('a',0)]))
class RealPrintThreadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.qt=QApplication.instance() or QApplication([])
    def test_real_print_thread_renders_multipage_pdf(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'photo.png'; output=Path(d)/'output.pdf'
            image=QImage(2400,3200,QImage.Format.Format_RGB32); image.fill(QColor('blue')); image.save(str(path))
            settings={'paper':'A6','photo':'4 × 6 cm','count':17,'printer':'unused','pdf_output':str(output)}
            worker=printing.PrintWorker([path],settings); worker.start()
            self.assertTrue(worker.wait(10000)); self.assertIsNone(worker.error)
            pdf=QPdfDocument(); pdf.load(str(output)); self.assertEqual(pdf.pageCount(),5); pdf.close()

class ControlledPrintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.qt=QApplication.instance() or QApplication([])
    def setup_photo(self,d):
        path=Path(d)/'photo.png'; image=QImage(300,400,QImage.Format.Format_RGB32); image.fill(QColor('blue')); image.save(str(path)); return path
    def settings(self,output): return {'paper':'A6','photo':'4 × 6 cm','count':17,'printer':'unused','pdf_output':str(output)}
    def test_pdf_pause_resume_and_progress(self):
        from PySide6.QtCore import Qt
        with tempfile.TemporaryDirectory() as d:
            path=self.setup_photo(d); output=Path(d)/'paused.pdf'; worker=printing.PrintWorker([path],self.settings(output))
            progress=[]; worker.progress.connect(lambda done,total,path:progress.append((done,total,path)),Qt.ConnectionType.DirectConnection)
            worker.pause(); worker.start(); self.assertFalse(worker.wait(50)); worker.resume()
            self.assertTrue(worker.wait(10000)); self.assertIsNone(worker.error); self.assertFalse(worker.cancelled)
            self.assertTrue(output.exists()); self.assertEqual(progress[-1][:2],(17,17)); self.assertTrue(all(row[2]==str(path) for row in progress))
    def test_cancel_paused_pdf_preserves_existing_destination(self):
        with tempfile.TemporaryDirectory() as d:
            path=self.setup_photo(d); output=Path(d)/'keep.pdf'; output.write_bytes(b'original file')
            worker=printing.PrintWorker([path],self.settings(output)); worker.pause(); worker.start(); self.assertFalse(worker.wait(50)); worker.cancel()
            self.assertTrue(worker.wait(10000)); self.assertTrue(worker.cancelled); self.assertIsNone(worker.error)
            self.assertEqual(output.read_bytes(),b'original file'); self.assertEqual(list(Path(d).glob('.chupanh-*')),[])
    def test_invalid_photo_pdf_failure_keeps_original(self):
        with tempfile.TemporaryDirectory() as d:
            output=Path(d)/'keep.pdf'; output.write_bytes(b'original file')
            worker=printing.PrintWorker([Path(d)/'missing.jpg'],self.settings(output)); worker.start(); self.assertTrue(worker.wait(10000))
            self.assertIsNotNone(worker.error); self.assertEqual(output.read_bytes(),b'original file'); self.assertEqual(list(Path(d).glob('.chupanh-*')),[])
    def test_native_renderer_runs_on_gui_thread_and_can_pause_resume(self):
        import time
        from types import SimpleNamespace
        from PySide6.QtCore import QThread,QTimer,Qt
        with tempfile.TemporaryDirectory() as d:
            path=self.setup_photo(d); output=Path(d)/'native-test.pdf'; settings=self.settings(output)
            job=printing.NativePrintJob([path],settings); create=printing.create_printer; observed=[]; paused=[]
            def progress(done,total,current):
                observed.append((done,total,QThread.currentThread()==self.qt.thread()))
                if done==1 and not paused:
                    paused.append(True); job.pause(); QTimer.singleShot(20,job.resume)
            job.progress.connect(progress,Qt.ConnectionType.DirectConnection)
            with patch.object(printing,'create_printer',side_effect=lambda cfg:create(cfg,output)),patch.object(printing,'WindowsSpooler',return_value=SimpleNamespace(available=False)):
                job.start(); deadline=time.monotonic()+10
                while not job.ended and time.monotonic()<deadline: self.qt.processEvents(); QThread.msleep(1)
            self.assertTrue(job.ended); self.assertIsNone(job.error); self.assertTrue(paused)
            self.assertTrue(all(row[2] for row in observed)); self.assertEqual(observed[-1][:2],(17,17))
    def test_native_cancel_stops_before_all_copies(self):
        import time
        from types import SimpleNamespace
        from PySide6.QtCore import QThread,Qt
        with tempfile.TemporaryDirectory() as d:
            path=self.setup_photo(d); output=Path(d)/'native-test.pdf'; job=printing.NativePrintJob([path],self.settings(output)); create=printing.create_printer; seen=[]
            def progress(done,total,current):
                seen.append(done)
                if done==1: job.cancel()
            job.progress.connect(progress,Qt.ConnectionType.DirectConnection)
            with patch.object(printing,'create_printer',side_effect=lambda cfg:create(cfg,output)),patch.object(printing,'WindowsSpooler',return_value=SimpleNamespace(available=False)):
                job.start(); deadline=time.monotonic()+10
                while not job.ended and time.monotonic()<deadline: self.qt.processEvents(); QThread.msleep(1)
            self.assertTrue(job.ended); self.assertTrue(job.cancelled); self.assertLess(max(seen),17)

if __name__=='__main__': unittest.main()
