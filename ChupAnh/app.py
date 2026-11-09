import sys,json,hashlib,sqlite3,os,time
from collections import deque
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from folder_source import inventory,FolderTracker
from PySide6.QtCore import Qt,QTimer,QSize,QLockFile
from PySide6.QtGui import QImageReader,QIcon,QPixmap
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QFormLayout,QVBoxLayout,
    QHBoxLayout,QPushButton,QComboBox,QSpinBox,QLineEdit,QFileDialog,QListWidget,
    QListWidgetItem,QListView,QAbstractItemView,QCheckBox,QMessageBox,QLabel)
from PySide6.QtPrintSupport import QPrinterInfo,QPrintPreviewDialog
from layout import PAPERS,PHOTOS
from printing import create_printer,render,PrintWorker
BASE=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'TelegramPhotoPrint'
BASE.mkdir(parents=True,exist_ok=True)
PATH_ROLE=int(Qt.ItemDataRole.UserRole)+1

class Window(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('Telegram Photo Print 1.2.1 — Windows'); self.resize(1040,820)
        self.db=sqlite3.connect(BASE/'history.sqlite')
        self.db.execute('CREATE TABLE IF NOT EXISTS jobs (digest TEXT PRIMARY KEY,state TEXT,file TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS images (digest TEXT PRIMARY KEY,path TEXT,added REAL)')
        self.recovered=self.db.execute("UPDATE jobs SET state='review' WHERE state IN ('queued','sending')").rowcount
        self.db.commit()
        self.pending={}; self.items={}; self.stable={}; self.closing=False; self.closed=False
        self.print_queue=deque(); self.print_worker=None; self.current_print_job=None
        self.pool=ThreadPoolExecutor(max_workers=1); self.future=None; self.generation=0
        self.tracker=FolderTracker(); self.processed={}; self.settings=BASE/'settings.json'
        try: self.saved=json.loads(self.settings.read_text(encoding='utf-8'))
        except (OSError,ValueError): self.saved={}
        if not isinstance(self.saved,dict): self.saved={}
        (BASE/'inbox').mkdir(exist_ok=True)
        self.folder=QLineEdit(self.saved.get('folder',str(BASE/'inbox'))); self.folder.setReadOnly(True)
        self.recursive=QCheckBox('Đọc cả thư mục con'); self.recursive.setChecked(bool(self.saved.get('recursive',False)))
        self.paper=QComboBox(); self.paper.addItems(PAPERS); self.paper.setCurrentText(self.saved.get('paper','A5'))
        self.photo=QComboBox(); self.photo.addItems(PHOTOS); self.photo.setCurrentText(self.saved.get('photo','3 × 4 cm'))
        self.printer=QComboBox(); self.refresh_printers()
        self.count=QSpinBox(); self.count.setRange(1,999)
        try: self.count.setValue(int(self.saved.get('count',4)))
        except (TypeError,ValueError): self.count.setValue(4)
        self.auto=QCheckBox('Tự động in ảnh MỚI — gửi in ngay, không cần bấm In ảnh đã chọn')
        self.list=QListWidget(); self.list.setViewMode(QListView.ViewMode.IconMode)
        self.list.setIconSize(QSize(100,130)); self.list.setGridSize(QSize(150,185))
        self.list.setResizeMode(QListView.ResizeMode.Adjust); self.list.setMovement(QListView.Movement.Static)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection); self.list.setWordWrap(True)
        self.list.setSpacing(5)
        self.summary=QLabel('0 ảnh • đã chọn 0 ảnh')
        self.status=QLabel('Sẵn sàng. Tích ô ảnh hoặc dùng Ctrl/Shift để chọn nhiều ảnh.'); self.status.setWordWrap(True)
        form=QFormLayout(); form.addRow('Thư mục ảnh bổ sung (tùy chọn)',self.folder); form.addRow('',self.recursive)
        form.addRow('Khổ giấy',self.paper); form.addRow('Máy in',self.printer)
        form.addRow('Kích thước ảnh',self.photo); form.addRow('Số bản / mỗi ảnh',self.count)
        root=QVBoxLayout(); root.addLayout(form)
        buttons=QHBoxLayout()
        for label,fn in [('Chọn thư mục',self.choose_folder),('Mở thư mục',self.open_folder),('Thêm ảnh',self.add_files),('Làm mới máy in',self.refresh_printers),('Kết nối Telegram',self.collect),('Lưu cài đặt',self.save_settings)]:
            button=QPushButton(label); button.clicked.connect(fn); buttons.addWidget(button)
        root.addLayout(buttons); root.addWidget(self.auto)
        select_row=QHBoxLayout()
        for label,fn in [('Chọn tất cả',lambda:self.check_all(True)),('Bỏ chọn',lambda:self.check_all(False))]:
            button=QPushButton(label); button.clicked.connect(fn); select_row.addWidget(button)
        select_row.addWidget(self.summary,1); root.addLayout(select_row); root.addWidget(self.list,1)
        actions=QHBoxLayout()
        for label,fn in [('Xem trước ảnh đã chọn',self.preview),('In ảnh đã chọn',self.manual),('Xuất PDF ảnh đã chọn',self.pdf)]:
            button=QPushButton(label); button.clicked.connect(fn); actions.addWidget(button)
        root.addLayout(actions)
        if self.recovered:
            notice=QLabel(f'{self.recovered} ảnh có tác vụ cũ chưa rõ kết quả. Đã bỏ trạng thái chờ bị kẹt; kiểm tra hàng đợi Windows trước khi in lại bằng tay.')
            notice.setWordWrap(True); root.addWidget(notice)
        root.addWidget(self.status)
        widget=QWidget(); widget.setLayout(root); self.setCentralWidget(widget)
        self.recursive.toggled.connect(self.source_changed); self.auto.toggled.connect(self.arm)
        self.list.itemSelectionChanged.connect(self.update_summary); self.list.itemChanged.connect(self.update_summary)
        self.timer=QTimer(self); self.timer.timeout.connect(self.scan); self.timer.start(2000)
        self.restore_paths=deque(path for path, in self.db.execute('SELECT path FROM images ORDER BY added'))
        from telegram_ui import TelegramDialog
        self.telegram_dialog=TelegramDialog(self,BASE)
        QTimer.singleShot(0,self.startup)
    def startup(self):
        if self.closing: return
        self.load_library_chunk()
        self.auto.setChecked(bool(self.saved.get('auto_print',False)))
        self.telegram_dialog.restore_startup()
    def load_library_chunk(self):
        if self.closing: return
        for _ in range(min(10,len(self.restore_paths))):
            path=Path(self.restore_paths.popleft())
            if path.is_file(): self.enqueue(path,False)
        if self.restore_paths: QTimer.singleShot(0,self.load_library_chunk)
    def snapshot(self):
        return {'paper':self.paper.currentText(),'photo':self.photo.currentText(),
                'printer':self.printer.currentText(),'count':self.count.value()}
    def write_settings(self):
        temporary=self.settings.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.saved,ensure_ascii=False,indent=2),encoding='utf-8'); temporary.replace(self.settings)
    def save_settings(self):
        try:
            self.saved.update(self.snapshot()); self.saved.update(folder=self.folder.text(),recursive=self.recursive.isChecked(),auto_print=self.auto.isChecked())
            self.write_settings(); self.status.setText('Đã lưu máy in, khổ giấy, kích thước, số bản, thư mục và trạng thái tự động in.')
        except OSError as exc: self.error(exc)
    def refresh_printers(self):
        preferred=self.printer.currentText() or self.saved.get('printer','')
        self.printer.clear(); self.printer.addItems([p.printerName() for p in QPrinterInfo.availablePrinters()])
        if preferred: self.printer.setCurrentIndex(self.printer.findText(preferred))
    def error(self,exc): QMessageBox.warning(self,'Thông báo',str(exc))
    def choose_folder(self):
        path=QFileDialog.getExistingDirectory(self,'Chọn thư mục ảnh')
        if path: self.folder.setText(path); self.source_changed()
    def source_changed(self,*args):
        self.auto.setChecked(False); self.generation+=1; self.tracker.reset(); self.processed.clear()
        self.saved.update(folder=self.folder.text(),recursive=self.recursive.isChecked(),auto_print=False)
        try: self.write_settings()
        except OSError as exc: self.error(exc)
        self.status.setText('Đã chọn thư mục. Ảnh có sẵn chỉ vào thư viện, không tự in khi bật tự động.')
    def open_folder(self):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(self.folder.text())): self.error('Không mở được thư mục.')
    def closeEvent(self,event):
        if self.closed: event.accept(); return
        self.closing=True; self.auto.setChecked(False); self.cancel_queued_prints()
        waiting=False
        if self.telegram_dialog.worker:
            waiting=True
            if not getattr(self,'closing_telegram',False):
                self.closing_telegram=True
                self.telegram_dialog.worker.finished.connect(lambda:QTimer.singleShot(0,self.close)); self.telegram_dialog.stop()
        if self.print_worker: waiting=True
        if waiting:
            self.status.setText('Đang kết thúc tác vụ hiện tại và ngắt Telegram…'); event.ignore(); return
        self.timer.stop(); self.pool.shutdown(wait=False,cancel_futures=True); self.closed=True
        self.db.close(); event.accept()
    def add_files(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Chọn ảnh','','Ảnh (*.jpg *.jpeg *.png *.webp *.bmp)')
        for path in paths: self.enqueue(Path(path),self.auto.isChecked())
    def arm(self,on):
        if on:
            if not self.printer.currentText():
                self.auto.setChecked(False); self.status.setText('Hãy chọn máy in khả dụng trước khi bật tự động.'); return
            self.generation+=1; self.tracker.arm(inventory(self.folder.text(),self.recursive.isChecked()))
            self.status.setText('Đang tự động: ảnh MỚI sẽ gửi in ngay, không cần bấm nút in.')
        else:
            self.cancel_queued_prints(automatic_only=True)
    def check_all(self,checked):
        self.list.blockSignals(True)
        for index in range(self.list.count()): self.list.item(index).setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self.list.clearSelection(); self.list.blockSignals(False); self.update_summary()
    def selection_items(self):
        checked=[self.list.item(i) for i in range(self.list.count()) if self.list.item(i).checkState()==Qt.CheckState.Checked]
        return checked or self.list.selectedItems()
    def update_summary(self,*args):
        self.summary.setText(f'{self.list.count()} ảnh • đã chọn {len(self.selection_items())} ảnh')
    def selected_entries(self):
        selected=self.selection_items()
        if not selected: raise ValueError('Tích ô các ảnh hoặc chọn ảnh bằng Ctrl/Shift trước khi in.')
        return [(Path(item.data(PATH_ROLE)),item.data(Qt.ItemDataRole.UserRole)) for item in selected]
    def selected(self): return self.selected_entries()[0]
    def enqueue(self,path,automatic):
        if self.closing: return False
        try:
            path=Path(path); reader=QImageReader(str(path)); reader.setAutoTransform(True)
            size=reader.size()
            if size.isValid(): reader.setScaledSize(size.scaled(QSize(100,130),Qt.AspectRatioMode.KeepAspectRatio))
            thumbnail=reader.read()
            if thumbnail.isNull(): return False
            hasher=hashlib.sha256()
            with path.open('rb') as source:
                for chunk in iter(lambda:source.read(1024*1024),b''): hasher.update(chunk)
            digest=hasher.hexdigest()
            if digest in self.pending: return True
            self.pending[digest]=str(path)
            item=QListWidgetItem(QIcon(QPixmap.fromImage(thumbnail)),path.name)
            item.setData(Qt.ItemDataRole.UserRole,digest); item.setData(PATH_ROLE,str(path)); item.setToolTip(str(path))
            item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable); item.setCheckState(Qt.CheckState.Unchecked)
            self.list.addItem(item); self.items[digest]=item
            self.db.execute('INSERT OR REPLACE INTO images VALUES (?,?,?)',(digest,str(path),time.time())); self.db.commit()
            self.update_summary()
            state=self.db.execute('SELECT state FROM jobs WHERE digest=?',(digest,)).fetchone()
            if automatic and (not state or state[0]=='cancelled'): self.send(path,digest)
            return True
        except Exception as exc:
            self.auto.setChecked(False); self.status.setText('Không nhận/in được ảnh: '+str(exc)); return False
    def scan(self):
        if self.closing: return
        if self.future is not None:
            if not self.future.done(): return
            generation,result=self.future.result(); self.future=None
            if generation==self.generation:
                for path,is_new in self.tracker.update(result):
                    stamp=result[str(path)]
                    if self.processed.get(str(path))==stamp: continue
                    if self.enqueue(path,self.auto.isChecked() and is_new): self.processed[str(path)]=stamp
        generation=self.generation; folder=self.folder.text(); recursive=self.recursive.isChecked()
        self.future=self.pool.submit(lambda:(generation,inventory(folder,recursive)))
    def setup(self,pdf=None): return create_printer(self.snapshot(),pdf)
    def draw(self,printer,path): render(printer,[path],self.snapshot())
    def preview(self):
        try:
            entries=self.selected_entries(); paths=[path for path,_ in entries]; settings=self.snapshot()
            printer=create_printer(settings,BASE/'preview.pdf'); dialog=QPrintPreviewDialog(printer,self)
            dialog.paintRequested.connect(lambda p:render(p,paths,settings)); dialog.exec()
        except Exception as exc: self.error(exc)
    def pdf(self):
        try:
            paths=[path for path,_ in self.selected_entries()]; dest,_=QFileDialog.getSaveFileName(self,'Lưu PDF','anh-in.pdf','PDF (*.pdf)')
            if dest:
                settings=self.snapshot(); render(create_printer(settings,dest),paths,settings)
                self.status.setText(f'Đã xuất PDF cho {len(paths)} ảnh: {dest}')
        except Exception as exc: self.error(exc)
    def send(self,path,digest): self.send_batch([(Path(path),digest)],automatic=True)
    def active_digests(self):
        jobs=list(self.print_queue)
        if self.current_print_job: jobs.append(self.current_print_job)
        return {digest for job in jobs for _,digest in job['entries']}
    def send_batch(self,entries,automatic=False):
        if self.closing: return
        settings=self.snapshot()
        if not settings['printer']: raise ValueError('Hãy chọn máy in trước khi in.')
        active=self.active_digests(); original_count=len(entries)
        entries=[(path,digest) for path,digest in entries if digest not in active]
        skipped=original_count-len(entries)
        if not entries:
            self.status.setText('Các ảnh này đang được xử lý; không xếp thêm bản trùng. Bạn có thể tiếp tục chọn ảnh khác.')
            return
        for path,digest in entries:
            self.db.execute('INSERT OR REPLACE INTO jobs VALUES (?,?,?)',(digest,'queued',str(path)))
        self.db.commit(); self.print_queue.append({'entries':list(entries),'settings':settings,'automatic':automatic})
        self.status.setText(f'Đã xếp hàng {len(entries)} ảnh, {settings["count"]} bản mỗi ảnh.'+(f' Bỏ qua {skipped} ảnh đang được xử lý.' if skipped else ''))
        QTimer.singleShot(0,self.start_next_print)
    def cancel_queued_prints(self,automatic_only=False):
        keep=deque()
        for job in self.print_queue:
            if automatic_only and not job['automatic']: keep.append(job); continue
            for _,digest in job['entries']: self.db.execute('UPDATE jobs SET state=? WHERE digest=?',('cancelled',digest))
        self.print_queue=keep; self.db.commit()
    def start_next_print(self):
        if self.closing or self.print_worker or not self.print_queue: return
        job=self.print_queue.popleft(); self.current_print_job=job
        for _,digest in job['entries']: self.db.execute('UPDATE jobs SET state=? WHERE digest=?',('sending',digest))
        self.db.commit()
        worker=PrintWorker([path for path,_ in job['entries']],job['settings'],self); self.print_worker=worker
        worker.finished.connect(lambda:self.print_finished(worker,job),Qt.ConnectionType.QueuedConnection); worker.start()
        self.status.setText(f'Đang gửi {len(job["entries"])} ảnh tới máy in…')
    def print_finished(self,worker,job):
        state='review' if worker.error else 'submitted'
        for _,digest in job['entries']: self.db.execute('UPDATE jobs SET state=? WHERE digest=?',(state,digest))
        self.db.commit(); self.print_worker=None; self.current_print_job=None; worker.deleteLater()
        if worker.error:
            self.auto.setChecked(False); self.cancel_queued_prints()
            self.status.setText('In gặp lỗi: '+worker.error+' Kiểm tra hàng đợi máy in trước khi in lại.')
        else: self.status.setText(f'Đã gửi {len(job["entries"])} ảnh tới hàng đợi máy in; chưa xác nhận giấy đã ra.')
        if self.closing: QTimer.singleShot(0,self.close)
        else: QTimer.singleShot(0,self.start_next_print)
    def manual(self):
        try:
            entries=self.selected_entries(); total=len(entries)*self.count.value()
            review=sum(1 for _,digest in entries if self.db.execute('SELECT state FROM jobs WHERE digest=?',(digest,)).fetchone()==('review',))
            warning=f'\n{review} ảnh có tác vụ trước chưa rõ kết quả; hãy kiểm tra hàng đợi Windows trước khi in lại.' if review else ''
            if QMessageBox.question(self,'Xác nhận in',f'In {len(entries)} ảnh khác nhau × {self.count.value()} bản = {total} ảnh, giấy {self.paper.currentText()}?'+warning)==QMessageBox.StandardButton.Yes:
                self.send_batch(entries)
        except Exception as exc: self.error(exc)
    def collect(self):
        self.telegram_dialog.show(); self.telegram_dialog.raise_(); self.telegram_dialog.activateWindow()
if __name__=='__main__':
    app=QApplication(sys.argv)
    instance_lock=QLockFile(str(BASE/'application.lock'))
    if not instance_lock.tryLock(0):
        QMessageBox.information(None,'Ứng dụng đang chạy','Telegram Photo Print đã mở. Chuyển sang cửa sổ đang chạy để tiếp tục.'); sys.exit(0)
    window=Window(); window.show(); sys.exit(app.exec())
