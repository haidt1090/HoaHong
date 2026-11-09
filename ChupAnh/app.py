import sys, json, hashlib, sqlite3, subprocess, os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from folder_source import inventory, FolderTracker
from PySide6.QtCore import Qt, QTimer, QSizeF
from PySide6.QtGui import QImageReader, QPainter, QPageSize, QPageLayout
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QFormLayout,QVBoxLayout,
    QHBoxLayout,QPushButton,QComboBox,QSpinBox,QLineEdit,QFileDialog,QListWidget,
    QCheckBox,QMessageBox,QLabel)
from PySide6.QtPrintSupport import QPrinter,QPrinterInfo,QPrintPreviewDialog
from layout import PAPERS,PHOTOS,pages
BASE=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'TelegramPhotoPrint'
BASE.mkdir(parents=True,exist_ok=True)
class Window(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('Telegram Photo Print — Windows'); self.resize(850,650)
        self.db=sqlite3.connect(BASE/'history.sqlite')
        self.db.execute('CREATE TABLE IF NOT EXISTS jobs (digest TEXT PRIMARY KEY, state TEXT, file TEXT)')
        self.pending={}; self.stable={}; self.busy=False
        self.pool=ThreadPoolExecutor(max_workers=1); self.future=None; self.generation=0
        self.tracker=FolderTracker(); self.processed={}
        self.settings=BASE/"settings.json"
        try: saved=json.loads(self.settings.read_text(encoding="utf-8"))
        except (OSError,ValueError): saved={}
        (BASE/'inbox').mkdir(exist_ok=True)
        self.folder=QLineEdit(saved.get('folder',str(BASE/'inbox'))); self.folder.setReadOnly(True)
        self.recursive=QCheckBox('Đọc cả thư mục con'); self.recursive.setChecked(saved.get('recursive',False))
        self.recursive.toggled.connect(self.source_changed)
        self.paper=QComboBox(); self.paper.addItems(PAPERS)
        self.photo=QComboBox(); self.photo.addItems(PHOTOS)
        self.printer=QComboBox(); self.refresh_printers()
        self.count=QSpinBox(); self.count.setRange(1,999); self.count.setValue(4)
        self.auto=QCheckBox('Tự động in ảnh MỚI sau khi bật (dùng cấu hình hiện tại)')
        self.list=QListWidget(); self.status=QLabel('Sẵn sàng. Chọn ảnh để xem trước hoặc in.')
        form=QFormLayout(); form.addRow('Thư mục ảnh bổ sung (tùy chọn)',self.folder)
        form.addRow('',self.recursive)
        form.addRow('Khổ giấy',self.paper); form.addRow('Máy in',self.printer)
        form.addRow('Kích thước ảnh',self.photo); form.addRow('Số ảnh / mỗi tệp',self.count)
        root=QVBoxLayout(); root.addLayout(form)
        buttons=QHBoxLayout()
        for label,fn in [('Chọn thư mục',self.choose_folder),('Mở thư mục',self.open_folder),('Thêm ảnh',self.add_files),('Làm mới máy in',self.refresh_printers),('Kết nối Telegram',self.collect)]:
            b=QPushButton(label); b.clicked.connect(fn); buttons.addWidget(b)
        root.addLayout(buttons); root.addWidget(self.auto); root.addWidget(self.list)
        actions=QHBoxLayout()
        for label,fn in [('Xem trước',self.preview),('In ảnh đã chọn',self.manual),('Xuất PDF',self.pdf)]:
            b=QPushButton(label); b.clicked.connect(fn); actions.addWidget(b)
        root.addLayout(actions); root.addWidget(self.status)
        widget=QWidget(); widget.setLayout(root); self.setCentralWidget(widget)
        self.auto.toggled.connect(self.arm); self.timer=QTimer(self); self.timer.timeout.connect(self.scan); self.timer.start(2000)
    def refresh_printers(self):
        self.printer.clear(); self.printer.addItems([p.printerName() for p in QPrinterInfo.availablePrinters()])
    def error(self,e): QMessageBox.warning(self,'Thông báo',str(e))
    def choose_folder(self):
        p=QFileDialog.getExistingDirectory(self,'Chọn thư mục ảnh')
        if p: self.auto.setChecked(False); self.folder.setText(p); self.source_changed()
    def source_changed(self,*args):
        self.auto.setChecked(False); self.generation+=1
        self.tracker.reset(); self.processed.clear()
        self.pending.clear(); self.list.clear()
        self.settings.write_text(json.dumps({'folder':self.folder.text(),'recursive':self.recursive.isChecked()},ensure_ascii=False),encoding='utf-8')
        self.status.setText('Đã chọn nguồn ảnh. Ảnh có sẵn chỉ vào danh sách, không tự in khi bật chế độ tự động.')
    def open_folder(self):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(self.folder.text())):
            self.error('Không mở được thư mục. Hãy chọn lại thư mục tồn tại.')
    def closeEvent(self,event):
        if hasattr(self,'telegram_dialog') and self.telegram_dialog.worker:
            self.telegram_dialog.show(); self.telegram_dialog.stop()
            self.status.setText('Đang ngắt Telegram; chờ vài giây rồi đóng lại ứng dụng.'); event.ignore(); return
        self.timer.stop(); self.pool.shutdown(wait=False,cancel_futures=True)
        self.db.close(); event.accept()
    def add_files(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Chọn ảnh','','Ảnh (*.jpg *.jpeg *.png *.webp *.bmp)')
        for p in paths: self.enqueue(Path(p),False)
    def arm(self,on):
        if on:
            # Existing files become baseline; enabling auto never prints old backlog.
            self.generation+=1
            self.tracker.arm(inventory(self.folder.text(),self.recursive.isChecked()))
            self.status.setText('Đang tự động: chỉ ảnh mới, không in lại nội dung đã gửi máy in.')
    def enqueue(self,p,automatic):
        try:
            reader=QImageReader(str(p)); reader.setAutoTransform(True)
            if not reader.canRead() or reader.read().isNull(): return False
            digest=hashlib.sha256(p.read_bytes()).hexdigest()
            if digest in self.pending: return True
            self.pending[digest]=str(p); self.list.addItem(str(p)); item=self.list.item(self.list.count()-1); item.setData(Qt.ItemDataRole.UserRole,digest)
            known=self.db.execute('SELECT state FROM jobs WHERE digest=?',(digest,)).fetchone()
            if automatic and not known:
                self.list.setCurrentItem(item); self.send(p,digest)
            return True
        except Exception as e: self.auto.setChecked(False); self.error(e)
    def scan(self):
        # Directory traversal runs outside the GUI; ignore stale source results.
        if self.future is not None:
            if not self.future.done(): return
            generation,result=self.future.result(); self.future=None
            if generation==self.generation:
                for path,is_new in self.tracker.update(result):
                    stamp=result[str(path)]
                    if self.processed.get(str(path))==stamp: continue
                    if self.enqueue(path,self.auto.isChecked() and is_new):
                        self.processed[str(path)]=stamp
        generation=self.generation; folder=self.folder.text(); recursive=self.recursive.isChecked()
        self.future=self.pool.submit(lambda:(generation,inventory(folder,recursive)))
    def selected(self):
        item=self.list.currentItem()
        if not item: raise ValueError('Hãy chọn một ảnh trong danh sách')
        return Path(item.text()),item.data(Qt.ItemDataRole.UserRole)
    def setup(self,pdf=None):
        p=QPrinter(QPrinter.PrinterMode.HighResolution)
        if pdf: p.setOutputFormat(QPrinter.OutputFormat.PdfFormat); p.setOutputFileName(pdf)
        else:
            if not self.printer.currentText(): raise ValueError('Không tìm thấy máy in. Hãy cài driver và làm mới.')
            p.setPrinterName(self.printer.currentText())
        p.setResolution(300)
        if not p.setPageSize(QPageSize(QSizeF(*PAPERS[self.paper.currentText()]),QPageSize.Unit.Millimeter)):
            raise ValueError('Máy in không chấp nhận khổ giấy đã chọn')
        p.setPageOrientation(QPageLayout.Orientation.Portrait); p.setFullPage(True)
        return p
    def draw(self,p,path):
        reader=QImageReader(str(path)); reader.setAutoTransform(True); img=reader.read()
        if img.isNull(): raise ValueError('Không đọc được ảnh: '+str(path))
        painter=QPainter()
        if not painter.begin(p): raise RuntimeError('Không mở được tác vụ in')
        try:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            factor=p.resolution()/25.4
            for i,slots in enumerate(pages(self.paper.currentText(),self.photo.currentText(),self.count.value())):
                if i and not p.newPage(): raise RuntimeError('Không tạo được trang in')
                for x,y,w,h in slots:
                    from PySide6.QtCore import QRectF
                    # Fit entire photo without cropping; white borders may appear.
                    ratio=min(w*factor/img.width(),h*factor/img.height())
                    dw,dh=img.width()*ratio,img.height()*ratio
                    painter.drawImage(QRectF(x*factor+(w*factor-dw)/2,y*factor+(h*factor-dh)/2,dw,dh),img)
        finally: painter.end()
    def preview(self):
        try:
            path,_=self.selected(); p=self.setup(str(BASE/'preview.pdf'))
            dialog=QPrintPreviewDialog(p,self); dialog.paintRequested.connect(lambda printer:self.draw(printer,path)); dialog.exec()
        except Exception as e: self.error(e)
    def pdf(self):
        try:
            path,_=self.selected(); dest,_=QFileDialog.getSaveFileName(self,'Lưu PDF','anh-in.pdf','PDF (*.pdf)')
            if dest: self.draw(self.setup(dest),path); self.status.setText('Đã xuất PDF: '+dest)
        except Exception as e: self.error(e)
    def send(self,path,digest):
        # Reserve BEFORE spool submission: ambiguous jobs never retry automatically.
        self.db.execute('INSERT OR REPLACE INTO jobs VALUES (?,?,?)',(digest,'sending',str(path))); self.db.commit()
        try:
            self.draw(self.setup(),path)
            self.db.execute('UPDATE jobs SET state=? WHERE digest=?',('submitted',digest)); self.db.commit()
            self.status.setText('Đã gửi tới hàng đợi máy in: '+path.name+' (chưa xác nhận giấy đã ra)')
        except Exception:
            self.db.execute('UPDATE jobs SET state=? WHERE digest=?',('review',digest)); self.db.commit()
            self.auto.setChecked(False); raise
    def manual(self):
        try:
            path,digest=self.selected()
            if QMessageBox.question(self,'Xác nhận in',f'In {self.count.value()} ảnh từ {path.name} trên giấy {self.paper.currentText()}?')==QMessageBox.StandardButton.Yes: self.send(path,digest)
        except Exception as e: self.error(e)
    def collect(self):
        from telegram_ui import TelegramDialog
        if not hasattr(self,'telegram_dialog'):
            self.telegram_dialog=TelegramDialog(self,BASE)
        self.telegram_dialog.show(); self.telegram_dialog.raise_(); self.telegram_dialog.activateWindow()
if __name__=='__main__':
    app=QApplication(sys.argv); w=Window(); w.show(); sys.exit(app.exec())
