"""Render print snapshots without reading GUI widgets from the print thread."""
from PySide6.QtCore import QThread,QSizeF,QRectF,QSize,Qt
from PySide6.QtGui import QImageReader,QPainter,QPageSize,QPageLayout
from PySide6.QtPrintSupport import QPrinter,QPrinterInfo
from layout import PAPERS,batch_pages

def create_printer(settings,pdf=None):
    printer=QPrinter(QPrinter.PrinterMode.HighResolution)
    if pdf:
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat); printer.setOutputFileName(str(pdf))
    else:
        name=settings['printer']
        if not name or QPrinterInfo.printerInfo(name).isNull():
            raise ValueError('Máy in đã chọn không còn khả dụng. Kiểm tra driver và chọn lại máy in.')
        printer.setPrinterName(name)
    printer.setResolution(300)
    if not printer.setPageSize(QPageSize(QSizeF(*PAPERS[settings['paper']]),QPageSize.Unit.Millimeter)):
        raise ValueError('Máy in không chấp nhận khổ giấy đã chọn')
    printer.setPageOrientation(QPageLayout.Orientation.Portrait); printer.setFullPage(True)
    return printer

def render(printer,paths,settings):
    painter=QPainter()
    if not painter.begin(printer): raise RuntimeError('Không mở được tác vụ in')
    try:
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        factor=printer.resolution()/25.4
        for i,placements in enumerate(batch_pages(settings['paper'],settings['photo'],[(path,settings['count']) for path in paths])):
            if i and not printer.newPage(): raise RuntimeError('Không tạo được trang in')
            images={}
            for path,(x,y,w,h) in placements:
                if path not in images:
                    reader=QImageReader(str(path)); reader.setAutoTransform(True)
                    original=reader.size(); pixels=max(1,round(max(w,h)*factor))
                    if original.isValid() and max(original.width(),original.height())>pixels:
                        reader.setScaledSize(original.scaled(QSize(pixels,pixels),Qt.AspectRatioMode.KeepAspectRatio))
                    image=reader.read()
                    if image.isNull(): raise ValueError('Không đọc được ảnh: '+str(path))
                    images[path]=image
                image=images[path]
                ratio=min(w*factor/image.width(),h*factor/image.height())
                dw,dh=image.width()*ratio,image.height()*ratio
                painter.drawImage(QRectF(x*factor+(w*factor-dw)/2,y*factor+(h*factor-dh)/2,dw,dh),image)
    finally: painter.end()

class PrintWorker(QThread):
    def __init__(self,paths,settings,parent=None):
        super().__init__(parent); self.paths=list(paths); self.settings=dict(settings); self.error=None
    def run(self):
        try: render(create_printer(self.settings),self.paths,self.settings)
        except Exception as exc: self.error=str(exc)
