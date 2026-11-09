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
            settings={'paper':'A6','photo':'4 × 6 cm','count':17,'printer':'unused'}
            create=printing.create_printer
            with patch.object(printing,'create_printer',side_effect=lambda config:create(config,output)):
                worker=printing.PrintWorker([path],settings); worker.start()
                self.assertTrue(worker.wait(10000)); self.assertIsNone(worker.error)
            pdf=QPdfDocument(); pdf.load(str(output)); self.assertEqual(pdf.pageCount(),5); pdf.close()
if __name__=='__main__': unittest.main()
