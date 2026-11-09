"""PDF jobs run in a worker; native printer rendering advances on the GUI thread."""
import tempfile,threading
from pathlib import Path
from PySide6.QtCore import QThread,QSizeF,QRectF,QSize,Qt,QObject,QTimer,Signal
from PySide6.QtGui import QImageReader,QPainter,QPageSize,QPageLayout
from PySide6.QtPrintSupport import QPrinter,QPrinterInfo
from layout import PAPERS,batch_pages
from spooler import WindowsSpooler

PDF_PRINTER='Xuất PDF trực tiếp'
def is_pdf_printer(name):
    name=str(name).strip().casefold()
    return name==PDF_PRINTER.casefold() or any(marker in name for marker in (
        'microsoft print to pdf','adobe pdf','bullzip pdf','dopdf','cutepdf','pdfcreator'))
class PrintCancelled(Exception): pass
class PrintControl:
    def __init__(self): self.condition=threading.Condition(); self.paused=False; self.cancelled=False
    def pause(self):
        with self.condition: self.paused=True
    def resume(self):
        with self.condition: self.paused=False; self.condition.notify_all()
    def cancel(self):
        with self.condition: self.cancelled=True; self.condition.notify_all()
    def wait(self):
        with self.condition:
            while self.paused and not self.cancelled: self.condition.wait()
            if self.cancelled: raise PrintCancelled()

def create_printer(settings,pdf=None):
    printer=QPrinter(QPrinter.PrinterMode.HighResolution)
    if pdf:
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat); printer.setOutputFileName(str(pdf))
    else:
        name=settings['printer']
        if not name or QPrinterInfo.printerInfo(name).isNull():
            raise ValueError('Máy in đã chọn không còn khả dụng. Kiểm tra driver và chọn lại máy in.')
        printer.setPrinterName(name)
    printer.setDocName(settings.get('document','ChupAnh'))
    printer.setCopyCount(1); printer.setResolution(300)
    if not printer.setPageSize(QPageSize(QSizeF(*PAPERS[settings['paper']]),QPageSize.Unit.Millimeter)):
        raise ValueError('Máy in không chấp nhận khổ giấy đã chọn')
    printer.setPageOrientation(QPageLayout.Orientation.Portrait); printer.setFullPage(True)
    return printer

class RenderSession:
    def __init__(self,printer,paths,settings,progress=None):
        self.printer=printer; self.progress=progress; self.done=0; self.total=len(paths)*settings['count']
        self.pages=iter(batch_pages(settings['paper'],settings['photo'],[(path,settings['count']) for path in paths]))
        self.placements=iter(()); self.page_index=-1; self.images={}
        self.factor=printer.resolution()/25.4; self.painter=QPainter()
        if not self.painter.begin(printer): raise RuntimeError('Không mở được tác vụ in')
        self.painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    def step(self):
        try: path,rect=next(self.placements)
        except StopIteration:
            try: page=next(self.pages)
            except StopIteration: return True
            self.page_index+=1; self.images.clear()
            if self.page_index and not self.printer.newPage(): raise RuntimeError('Không tạo được trang in')
            self.placements=iter(page); path,rect=next(self.placements)
        x,y,w,h=rect; factor=self.factor
        if self.progress: self.progress(self.done,self.total,str(path))
        if path not in self.images:
            reader=QImageReader(str(path)); reader.setAutoTransform(True)
            original=reader.size(); pixels=max(1,round(max(w,h)*factor))
            if original.isValid() and max(original.width(),original.height())>pixels:
                reader.setScaledSize(original.scaled(QSize(pixels,pixels),Qt.AspectRatioMode.KeepAspectRatio))
            image=reader.read()
            if image.isNull(): raise ValueError('Không đọc được ảnh: '+str(path))
            self.images[path]=image
        image=self.images[path]; ratio=min(w*factor/image.width(),h*factor/image.height())
        dw,dh=image.width()*ratio,image.height()*ratio
        self.painter.drawImage(QRectF(x*factor+(w*factor-dw)/2,y*factor+(h*factor-dh)/2,dw,dh),image)
        self.done+=1
        if self.progress: self.progress(self.done,self.total,str(path))
        return self.done>=self.total
    def close(self,abort=False):
        if abort: self.printer.abort()
        if self.painter.isActive(): self.painter.end()
        self.images.clear(); self.printer=None

def render(printer,paths,settings,control=None,progress=None):
    session=RenderSession(printer,paths,settings,progress); success=False
    try:
        while True:
            if control: control.wait()
            if session.step(): break
        success=True
    finally: session.close(abort=not success)

def export_pdf(paths,settings,destination,control=None,progress=None):
    destination=Path(destination)
    with tempfile.NamedTemporaryFile(prefix='.chupanh-',suffix='.pdf',dir=destination.parent,delete=False) as temp:
        temporary=Path(temp.name)
    try:
        printer=create_printer(settings,temporary)
        try: render(printer,paths,settings,control,progress)
        finally: del printer
        if control: control.wait()
        temporary.replace(destination)
    finally: temporary.unlink(missing_ok=True)

class PrintWorker(QThread):
    progress=Signal(int,int,str)
    def __init__(self,paths,settings,parent=None):
        super().__init__(parent); self.paths=list(paths); self.settings=dict(settings)
        self.error=None; self.cancelled=False; self.control=PrintControl()
    def pause(self): self.control.pause()
    def resume(self): self.control.resume()
    def cancel(self): self.control.cancel()
    def run(self):
        try:
            if not self.settings.get('pdf_output'): raise ValueError('Chưa chọn đường dẫn PDF')
            export_pdf(self.paths,self.settings,self.settings['pdf_output'],self.control,self.progress.emit)
        except PrintCancelled: self.cancelled=True
        except Exception as exc: self.error=str(exc)

class NativePrintJob(QObject):
    finished=Signal(); progress=Signal(int,int,str); spool_job=Signal(int)
    def __init__(self,paths,settings,parent=None):
        super().__init__(parent); self.paths=list(paths); self.settings=dict(settings)
        self.error=None; self.cancelled=False; self.control=PrintControl(); self.session=None; self.ended=False
    def pause(self): self.control.pause()
    def resume(self): self.control.resume()
    def cancel(self): self.control.cancel()
    def start(self): QTimer.singleShot(0,self.begin)
    def begin(self):
        if self.control.cancelled: self.cancelled=True; self.finish(); return
        if self.control.paused: QTimer.singleShot(50,self.begin); return
        try: self.session=RenderSession(create_printer(self.settings),self.paths,self.settings,self.progress.emit)
        except Exception as exc: self.error=str(exc); self.finish(); return
        spooler=WindowsSpooler()
        if spooler.available:
            try:
                job_id=spooler.find_job_id(self.settings['printer'],self.settings.get('document','ChupAnh'))
                if job_id is not None: self.spool_job.emit(job_id)
            except Exception: pass
        QTimer.singleShot(0,self.step)
    def step(self):
        if self.control.cancelled: self.cancelled=True; self.finish(); return
        if self.control.paused: QTimer.singleShot(50,self.step); return
        try:
            if self.session.step(): self.finish(); return
        except Exception as exc: self.error=str(exc); self.finish(); return
        QTimer.singleShot(0,self.step)
    def finish(self):
        if self.ended: return
        self.ended=True
        if self.session:
            self.session.close(abort=self.cancelled or bool(self.error)); self.session=None
        self.finished.emit()
