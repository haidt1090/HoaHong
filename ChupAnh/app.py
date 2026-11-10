import sys,json,hashlib,sqlite3,os,time,uuid,tempfile
from datetime import datetime
from collections import deque
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from folder_source import inventory,FolderTracker
from PySide6.QtCore import Qt,QTimer,QSize,QLockFile
from PySide6.QtGui import QImageReader,QIcon,QPixmap,QShortcut,QKeySequence
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QFormLayout,QVBoxLayout,
    QHBoxLayout,QPushButton,QComboBox,QSpinBox,QLineEdit,QFileDialog,QListWidget,
    QListWidgetItem,QListView,QAbstractItemView,QCheckBox,QMessageBox,QLabel,
    QTreeWidget,QTreeWidgetItem,QGroupBox,QSplitter,QSizePolicy)
from PySide6.QtPrintSupport import QPrinterInfo,QPrintPreviewDialog
from layout import PAPERS,PHOTOS,grid_slots,layout_kwargs
from formats import DEFAULT_GEOMETRY,clean_format
from printing import create_printer,render,PrintWorker,NativePrintJob,PDF_PRINTER,is_pdf_printer
from spooler import WindowsSpooler,status_text
_smoke_data=tempfile.TemporaryDirectory(prefix='chupanh-smoke-') if '--smoke-test' in sys.argv else None
BASE=Path(_smoke_data.name)/'TelegramPhotoPrint' if _smoke_data else Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'TelegramPhotoPrint'
BASE.mkdir(parents=True,exist_ok=True)
PATH_ROLE=int(Qt.ItemDataRole.UserRole)+1
GALLERY_LIMIT=100

class Window(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('Telegram Photo Print 1.6 — Windows'); self.resize(1040,820)
        self.db=sqlite3.connect(BASE/'history.sqlite')
        self.db.execute('CREATE TABLE IF NOT EXISTS jobs (digest TEXT PRIMARY KEY,state TEXT,file TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS images (digest TEXT PRIMARY KEY,path TEXT,added REAL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS hidden_images (digest TEXT PRIMARY KEY)')
        self.db.execute('INSERT OR IGNORE INTO hidden_images SELECT digest FROM images ORDER BY added DESC LIMIT -1 OFFSET ?',(GALLERY_LIMIT,))
        self.db.execute('DELETE FROM images WHERE digest IN (SELECT digest FROM hidden_images)')
        self.recovered=self.db.execute("UPDATE jobs SET state='review' WHERE state IN ('queued','sending')").rowcount
        self.db.execute('CREATE TABLE IF NOT EXISTS print_runs (id TEXT PRIMARY KEY,created REAL,label TEXT,state TEXT,done INTEGER,total INTEGER,current TEXT,printer TEXT,output TEXT,document TEXT,spool_id INTEGER)')
        self.db.execute('CREATE TABLE IF NOT EXISTS print_run_images (run_id TEXT,digest TEXT,PRIMARY KEY(run_id,digest))')
        self.db.commit()
        self.run_items={}; self.run_data={}; self.spool_jobs={}; self.queue_paused=False
        self.spooler=WindowsSpooler(); self.spool_pool=ThreadPoolExecutor(max_workers=1)
        self.spool_command_pool=ThreadPoolExecutor(max_workers=1); self.spool_reads={}; self.spool_commands=[]; self.last_progress_commit=0
        self.pending={}; self.items={}; self.stable={}; self.closing=False; self.closed=False
        self.print_queue=deque(); self.print_worker=None; self.current_print_job=None
        self.pool=ThreadPoolExecutor(max_workers=1); self.future=None; self.generation=0
        self.tracker=FolderTracker(); self.processed={}; self.settings=BASE/'settings.json'
        try: self.saved=json.loads(self.settings.read_text(encoding='utf-8'))
        except (OSError,ValueError): self.saved={}
        if not isinstance(self.saved,dict): self.saved={}
        self.layout_format={key:self.saved.get(key,value) for key,value in DEFAULT_GEOMETRY.items()}
        (BASE/'inbox').mkdir(exist_ok=True)
        self.folder=QLineEdit(self.saved.get('folder',str(BASE/'inbox'))); self.folder.setReadOnly(True)
        self.recursive=QCheckBox('Đọc cả thư mục con'); self.recursive.setChecked(bool(self.saved.get('recursive',False)))
        self.paper=QComboBox(); self.paper.addItems(PAPERS); self.paper.setCurrentText(self.saved.get('paper','A5'))
        self.photo=QComboBox(); self.photo.addItems(PHOTOS); self.photo.setCurrentText(self.saved.get('photo','3 × 4 cm'))
        self.printer=QComboBox(); self.refresh_printers()
        self.count=QSpinBox(); self.count.setRange(1,999)
        try: self.count.setValue(int(self.saved.get('count',4)))
        except (TypeError,ValueError): self.count.setValue(4)
        self.pdf_folder=QLineEdit(self.saved.get('pdf_folder',str(BASE/'pdf-output'))); self.pdf_folder.setReadOnly(True)
        self.auto=QCheckBox('Tự động in ảnh MỚI — gửi in ngay, không cần bấm In ảnh đã chọn')
        self.list=QListWidget(); self.list.setViewMode(QListView.ViewMode.IconMode)
        self.list.setIconSize(QSize(100,130)); self.list.setGridSize(QSize(150,185))
        self.list.setResizeMode(QListView.ResizeMode.Adjust); self.list.setMovement(QListView.Movement.Static)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection); self.list.setWordWrap(True)
        self.list.setSpacing(5)
        self.summary=QLabel('0/100 ảnh • đã chọn 0 ảnh')
        self.status=QLabel('Sẵn sàng. Tích ô ảnh hoặc dùng Ctrl/Shift để chọn nhiều ảnh.'); self.status.setWordWrap(True)
        form=QFormLayout(); form.addRow('Thư mục ảnh bổ sung (tùy chọn)',self.folder); form.addRow('',self.recursive)
        form.addRow('Khổ giấy',self.paper); form.addRow('Máy in',self.printer)
        form.addRow('Kích thước ảnh',self.photo); form.addRow('Số bản / mỗi ảnh',self.count)
        pdf_row=QHBoxLayout(); pdf_row.addWidget(self.pdf_folder)
        pdf_button=QPushButton('Chọn thư mục'); pdf_button.clicked.connect(self.choose_pdf_folder); pdf_row.addWidget(pdf_button)
        form.addRow('Thư mục PDF tự động',pdf_row)
        root=QVBoxLayout()
        self.developer_label=QLabel('PHÒNG KHÁM ĐA KHOA Y CAO HOA HỒNG\nCÔNG TY TNHH DỊCH VỤ VÀ Y TẾ HUỆ LINH')
        self.developer_label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.developer_label.setWordWrap(True)
        self.developer_label.setStyleSheet('font-weight: 600; color: #23435e; padding: 2px;')
        header=QWidget(); header.setStyleSheet('background: #f2f6fa;'); header_row=QHBoxLayout(header)
        header_row.setContentsMargins(2,0,2,0); header_row.setSpacing(6); header_row.addSpacing(34)
        header_row.addWidget(self.developer_label,1)
        self.help_button=QPushButton('?'); self.help_button.setFixedSize(28,28); self.help_button.setToolTip('Hướng dẫn phím tắt (F1)')
        self.help_button.clicked.connect(self.show_hotkey_help); header_row.addWidget(self.help_button)
        self.help_shortcut=QShortcut(QKeySequence('F1'),self); self.help_shortcut.setAutoRepeat(False)
        self.help_shortcut.activated.connect(self.show_hotkey_help)
        root.addWidget(header); root.addLayout(form)
        self.hotkeys=[]
        for position in range(1,10):
            shortcut=QShortcut(QKeySequence(f'Alt+{position}'),self); shortcut.setAutoRepeat(False)
            shortcut.activated.connect(lambda position=position:self.print_latest(position)); self.hotkeys.append(shortcut)
        shortcut=QShortcut(QKeySequence('Alt+A'),self); shortcut.setAutoRepeat(False)
        shortcut.activated.connect(self.print_all_new); self.hotkeys.append(shortcut)
        buttons=QHBoxLayout()
        for label,fn in [('Chọn thư mục',self.choose_folder),('Mở thư mục',self.open_folder),('Thêm ảnh',self.add_files),('Làm mới máy in',self.refresh_printers),('Kết nối Telegram',self.collect),('Lưu cài đặt',self.save_settings)]:
            button=QPushButton(label); button.clicked.connect(fn); buttons.addWidget(button)
        root.addLayout(buttons); root.addWidget(self.auto)
        select_row=QHBoxLayout()
        for label,fn in [('Chọn tất cả',lambda:self.check_all(True)),('Bỏ chọn',lambda:self.check_all(False)),('Xóa ảnh đã chọn',self.remove_selected_photos),('Làm trống khung ảnh',self.clear_gallery)]:
            button=QPushButton(label); button.clicked.connect(fn); select_row.addWidget(button)
        select_row.addWidget(self.summary,1); root.addLayout(select_row)
        photo_panel=QWidget(); photo_layout=QVBoxLayout(photo_panel); photo_layout.setContentsMargins(0,0,0,0)
        photo_layout.addWidget(self.list,1); photo_panel.setMinimumHeight(110)
        actions=QHBoxLayout()
        for label,fn in [('Xem trước ảnh đã chọn',self.preview),('In ảnh đã chọn',self.manual),('Xuất PDF ảnh đã chọn',self.pdf)]:
            button=QPushButton(label)
            if fn==self.manual:
                font=button.font(); font.setPointSize(font.pointSize()+2); font.setBold(True); button.setFont(font); button.setMinimumHeight(38)
            button.clicked.connect(fn); actions.addWidget(button)
        photo_layout.addLayout(actions)
        progress_group=QGroupBox('Tiến độ và hàng đợi in'); progress_layout=QVBoxLayout(progress_group)
        self.queue_table=QTreeWidget(); self.queue_table.setHeaderLabels(['Lượt in','Ảnh đang xử lý','Đã xử lý','Trạng thái','Máy in / PDF'])
        self.queue_table.currentItemChanged.connect(lambda *_:self.show_selected_progress())
        self.queue_table.setRootIsDecorated(False); self.queue_table.setAlternatingRowColors(True); self.queue_table.setMinimumHeight(65); self.queue_table.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Ignored)
        for index,width in enumerate([155,170,85,260,240]): self.queue_table.setColumnWidth(index,width)
        progress_layout.addWidget(self.queue_table)
        controls=QHBoxLayout()
        for label,fn in [('Tạm dừng',self.pause_printing),('Tiếp tục',self.resume_printing),('Hủy lệnh đã chọn',self.cancel_selected_print),('Mở hàng đợi Windows',self.open_windows_queue),('Xóa tất cả tiến độ',self.clear_progress)]:
            button=QPushButton(label); button.clicked.connect(fn); controls.addWidget(button)
        progress_layout.addLayout(controls); progress_group.setMinimumHeight(130)
        self.splitter=QSplitter(Qt.Orientation.Vertical); self.splitter.setChildrenCollapsible(False); self.splitter.setHandleWidth(8)
        self.splitter.addWidget(photo_panel); self.splitter.addWidget(progress_group)
        self.splitter.setStretchFactor(0,4); self.splitter.setStretchFactor(1,1)
        self.splitter.handle(1).setToolTip('Kéo lên/xuống để đổi kích thước khung ảnh và tiến độ')
        self.splitter.setStyleSheet('QSplitter::handle:vertical { background: #c9cdd2; margin: 1px 0; } QSplitter::handle:vertical:hover { background: #8796a5; }')
        panel_sizes=self.saved.get('panel_sizes',[600,175])
        if not isinstance(panel_sizes,list) or len(panel_sizes)!=2 or any(not isinstance(v,int) or v<=0 for v in panel_sizes): panel_sizes=[600,175]
        self.splitter.setSizes(panel_sizes); root.addWidget(self.splitter,1)
        if self.recovered:
            notice=QLabel(f'{self.recovered} ảnh có tác vụ cũ chưa rõ kết quả. Đã bỏ trạng thái chờ bị kẹt; kiểm tra hàng đợi Windows trước khi in lại bằng tay.')
            notice.setWordWrap(True); root.addWidget(notice)
        root.addWidget(self.status)
        widget=QWidget(); widget.setLayout(root); self.setCentralWidget(widget)
        self.recursive.toggled.connect(self.source_changed); self.auto.toggled.connect(self.arm)
        self.list.itemSelectionChanged.connect(self.update_summary); self.list.itemChanged.connect(self.update_summary)
        self.timer=QTimer(self); self.timer.timeout.connect(self.scan); self.timer.start(2000)
        self.restore_paths=deque(self.db.execute('SELECT path,added,digest FROM images ORDER BY added'))
        from telegram_ui import TelegramDialog
        self.telegram_dialog=TelegramDialog(self,BASE)
        self.load_run_history()
        self.spool_timer=QTimer(self); self.spool_timer.timeout.connect(self.poll_spooler); self.spool_timer.start(700)
        QTimer.singleShot(0,self.startup)
    def startup(self):
        if self.closing: return
        self.load_library_chunk()
        self.auto.setChecked(bool(self.saved.get('auto_print',False)))
        self.telegram_dialog.restore_startup()
    def load_library_chunk(self):
        if self.closing: return
        for _ in range(min(10,len(self.restore_paths))):
            stored_path,added,record_key=self.restore_paths.popleft(); path=Path(stored_path)
            if path.is_file(): self.enqueue(path,False,added=added,record_key=record_key)
        if self.restore_paths: QTimer.singleShot(0,self.load_library_chunk)
    def snapshot(self):
        return {'paper':self.paper.currentText(),'photo':self.photo.currentText(),
                'printer':self.printer.currentText(),'count':self.count.value(),**self.layout_format}
    def write_settings(self):
        temporary=self.settings.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.saved,ensure_ascii=False,indent=2),encoding='utf-8'); temporary.replace(self.settings)
    def save_settings(self):
        try:
            self.saved.update(self.snapshot()); self.saved.update(folder=self.folder.text(),recursive=self.recursive.isChecked(),auto_print=self.auto.isChecked(),pdf_folder=self.pdf_folder.text(),panel_sizes=self.splitter.sizes())
            self.write_settings()
            if self.telegram_dialog.ready and self.telegram_dialog.receiving_id is not None: self.telegram_dialog.save_connection()
            self.status.setText('Đã lưu máy in, mẫu bố trí, số bản, thư mục và trạng thái tự động in'+(' đang BẬT.' if self.auto.isChecked() else ' đang TẮT.'))
        except OSError as exc: self.error(exc)
    def refresh_printers(self):
        preferred=self.printer.currentText() or self.saved.get('printer','')
        self.printer.clear(); self.printer.addItems([p.printerName() for p in QPrinterInfo.availablePrinters()]); self.printer.addItem(PDF_PRINTER)
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
    def choose_pdf_folder(self):
        folder=QFileDialog.getExistingDirectory(self,'Chọn thư mục lưu PDF tự động',self.pdf_folder.text())
        if folder: self.pdf_folder.setText(folder)
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
        if self.print_worker:
            waiting=True; self.print_worker.cancel()
            if self.current_print_job and not self.current_print_job['settings'].get('pdf_output'):
                self.request_spool_command(self.current_print_job,'cancel')
        if waiting:
            self.status.setText('Đang kết thúc tác vụ hiện tại và ngắt Telegram…'); event.ignore(); return
        self.timer.stop(); self.spool_timer.stop(); self.pool.shutdown(wait=False,cancel_futures=True)
        self.spool_pool.shutdown(wait=False,cancel_futures=True); self.spool_command_pool.shutdown(wait=False); self.closed=True
        self.db.close(); event.accept()
    def add_files(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Chọn ảnh','','Ảnh (*.jpg *.jpeg *.png *.webp *.bmp)')
        for path in paths: self.enqueue(Path(path),self.auto.isChecked(),allow_hidden=True)
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
        self.summary.setText(f'{self.list.count()}/{GALLERY_LIMIT} ảnh • đã chọn {len(self.selection_items())} ảnh')
    def selected_entries(self):
        selected=self.selection_items()
        if not selected: raise ValueError('Tích ô các ảnh hoặc chọn ảnh bằng Ctrl/Shift trước khi in.')
        return [(Path(item.data(PATH_ROLE)),item.data(Qt.ItemDataRole.UserRole)) for item in selected]
    def selected(self): return self.selected_entries()[0]
    def enqueue(self,path,automatic,added=None,allow_hidden=False,occurrence=None,record_key=None):
        if self.closing: return False
        try:
            path=Path(path)
            if occurrence is None and record_key is None and str(path) in self.pending.values(): return True
            reader=QImageReader(str(path)); reader.setAutoTransform(True)
            size=reader.size()
            if size.isValid(): reader.setScaledSize(size.scaled(QSize(100,130),Qt.AspectRatioMode.KeepAspectRatio))
            thumbnail=reader.read()
            if thumbnail.isNull(): return False
            hasher=hashlib.sha256()
            with path.open('rb') as source:
                for chunk in iter(lambda:source.read(1024*1024),b''): hasher.update(chunk)
            content_digest=hasher.hexdigest()
            digest=record_key or (hashlib.sha256(occurrence.encode('utf-8')).hexdigest() if occurrence is not None else content_digest)
            if self.db.execute('SELECT 1 FROM hidden_images WHERE digest=?',(digest,)).fetchone():
                if not allow_hidden: return True
                self.db.execute('DELETE FROM hidden_images WHERE digest=?',(digest,))
            if digest in self.pending: return True
            self.pending[digest]=str(path)
            item=QListWidgetItem(QIcon(QPixmap.fromImage(thumbnail)),path.name)
            item.setData(Qt.ItemDataRole.UserRole,digest); item.setData(PATH_ROLE,str(path)); item.setToolTip(str(path))
            item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable); item.setCheckState(Qt.CheckState.Unchecked)
            added=time.time() if added is None else float(added)
            item.setData(PATH_ROLE+1,added)
            position=0
            while position<self.list.count() and self.list.item(position).data(PATH_ROLE+1)>added: position+=1
            self.list.insertItem(position,item); self.items[digest]=item
            self.db.execute('INSERT OR REPLACE INTO images VALUES (?,?,?)',(digest,str(path),added))
            while self.list.count()>GALLERY_LIMIT: self.forget_gallery_item(self.list.item(self.list.count()-1))
            self.db.commit(); self.update_summary()
            state=self.db.execute('SELECT state FROM jobs WHERE digest=?',(digest,)).fetchone()
            if automatic and (not state or state[0]=='cancelled'): self.send(path,digest)
            return True
        except Exception as exc:
            self.auto.setChecked(False); self.status.setText('Không nhận/in được ảnh: '+str(exc)); return False
    def forget_gallery_item(self,item):
        digest=item.data(Qt.ItemDataRole.UserRole)
        self.db.execute('INSERT OR IGNORE INTO hidden_images VALUES (?)',(digest,))
        self.db.execute('DELETE FROM images WHERE digest=?',(digest,))
        self.pending.pop(digest,None); self.items.pop(digest,None)
        self.list.takeItem(self.list.row(item))
    def remove_selected_photos(self):
        items=list(self.selection_items())
        if not items: self.status.setText('Chọn ảnh cần bỏ khỏi khung trước.'); return
        for item in items: self.forget_gallery_item(item)
        self.db.commit(); self.update_summary()
        self.status.setText(f'Đã bỏ {len(items)} ảnh khỏi khung. Giữ nguyên file ảnh và lệnh in đang chờ.')
    def clear_gallery(self):
        count=self.list.count(); self.restore_paths.clear()
        for index in range(self.list.count()-1,-1,-1): self.forget_gallery_item(self.list.item(index))
        self.db.commit(); self.update_summary()
        self.status.setText(f'Đã làm trống {count} ảnh trên khung. File ảnh và tiến độ in vẫn được giữ.')
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
    def apply_format(self,settings,name=''):
        values=clean_format(settings); self.paper.setCurrentText(values['paper']); self.photo.setCurrentText(values['photo']); self.count.setValue(values['count'])
        self.layout_format={key:values[key] for key in DEFAULT_GEOMETRY}; self.saved['active_format']=name
    def preview(self):
        try:
            from preview_editor import PreviewEditor
            self.preview_dialog=PreviewEditor(self,self.selected_entries(),BASE); self.preview_dialog.exec()
        except Exception as exc: self.error(exc)
    def ask_pdf_path(self):
        path,_=QFileDialog.getSaveFileName(self,'Lưu ảnh đã chọn thành PDF','anh-in.pdf','PDF (*.pdf)',options=QFileDialog.Option.DontUseNativeDialog)
        if not path: return None
        return str(Path(path).with_suffix('.pdf')) if Path(path).suffix.lower()!='.pdf' else path
    def pdf(self):
        try:
            entries=self.selected_entries(); destination=self.ask_pdf_path()
            if destination: self.send_batch(entries,pdf_output=destination)
            else: self.status.setText('Đã hủy lưu PDF. Chưa tạo tác vụ in.')
        except Exception as exc: self.error(exc)
    def send(self,path,digest): self.send_batch([(Path(path),digest)],automatic=True)
    def active_digests(self):
        jobs=list(self.print_queue)
        if self.current_print_job: jobs.append(self.current_print_job)
        jobs.extend(self.spool_jobs.values())
        return {digest for job in jobs for _,digest in job['entries']}
    def send_batch(self,entries,automatic=False,pdf_output=None):
        if self.closing: return
        settings=self.snapshot()
        grid_slots(settings['paper'],settings['photo'],**layout_kwargs(settings))
        if not settings['printer'] and not pdf_output: raise ValueError('Hãy chọn máy in trước khi in.')
        active=self.active_digests(); original_count=len(entries)
        entries=[(path,digest) for path,digest in entries if digest not in active]
        skipped=original_count-len(entries)
        if not entries:
            self.status.setText('Các ảnh này đang được xử lý; không xếp thêm bản trùng. Bạn có thể tiếp tục chọn ảnh khác.')
            return
        if is_pdf_printer(settings['printer']) and not pdf_output:
            if not automatic: raise ValueError('Chọn nơi lưu PDF trước khi gửi tác vụ.')
            folder=Path(self.pdf_folder.text()); folder.mkdir(parents=True,exist_ok=True)
            pdf_output=str(folder/('Anh_'+datetime.now().strftime('%Y%m%d_%H%M%S_')+uuid.uuid4().hex[:8]+'.pdf'))
        if pdf_output: settings['pdf_output']=str(pdf_output)
        run_id=uuid.uuid4().hex; settings['document']='ChupAnh '+run_id
        for path,digest in entries:
            self.db.execute('INSERT OR IGNORE INTO print_run_images VALUES (?,?)',(run_id,digest))
            self.db.execute('INSERT OR REPLACE INTO jobs VALUES (?,?,?)',(digest,'queued',str(path)))
        job={'id':run_id,'entries':list(entries),'settings':settings,'automatic':automatic,'render_complete':False,'spool_id':None,'cancel_requested':False}
        self.print_queue.append(job)
        self.add_run(job)
        self.status.setText(f'Đã xếp hàng {len(entries)} ảnh, {settings["count"]} bản mỗi ảnh.'+(f' Bỏ qua {skipped} ảnh đang được xử lý.' if skipped else ''))
        QTimer.singleShot(0,self.start_next_print)
    def cancel_queued_prints(self,automatic_only=False):
        keep=deque()
        for job in self.print_queue:
            if automatic_only and not job['automatic']: keep.append(job); continue
            for _,digest in job['entries']: self.db.execute('UPDATE jobs SET state=? WHERE digest=?',('cancelled',digest))
            self.set_run(job,'cancelled',text='Đã hủy trước khi gửi')
        self.print_queue=keep; self.db.commit()
    def start_next_print(self):
        if self.closing or self.queue_paused or self.print_worker or not self.print_queue: return
        job=self.print_queue.popleft(); self.current_print_job=job
        for _,digest in job['entries']: self.db.execute('UPDATE jobs SET state=? WHERE digest=?',('sending',digest))
        self.db.commit(); self.queue_table.setCurrentItem(self.run_items[job['id']]); self.set_run(job,'running',text='Đang xử lý ảnh')
        job_type=PrintWorker if job['settings'].get('pdf_output') else NativePrintJob
        worker=job_type([path for path,_ in job['entries']],job['settings'],self); self.print_worker=worker
        worker.progress.connect(lambda done,total,path:self.update_print_progress(job,done,total,path),Qt.ConnectionType.QueuedConnection)
        if hasattr(worker,'spool_job'): worker.spool_job.connect(lambda identity:self.attach_spool_job(job,identity),Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(lambda:self.print_finished(worker,job),Qt.ConnectionType.QueuedConnection); worker.start()
        self.status.setText(f'Đang xuất PDF cho {len(job["entries"])} ảnh…' if job['settings'].get('pdf_output') else f'Đang gửi {len(job["entries"])} ảnh tới máy in…')
    def print_finished(self,worker,job):
        job['render_complete']=True; job['finished_at']=time.monotonic(); job['render_error']=worker.error
        is_pdf=bool(job['settings'].get('pdf_output')); cancelled=worker.cancelled
        state='review' if worker.error else ('cancelled' if cancelled and is_pdf else ('review' if cancelled else ('exported' if is_pdf else 'submitted')))
        for _,digest in job['entries']: self.db.execute('UPDATE jobs SET state=? WHERE digest=?',(state,digest))
        self.db.commit(); self.print_worker=None; self.current_print_job=None; worker.deleteLater()
        if worker.error:
            self.auto.setChecked(False); self.cancel_queued_prints()
            self.set_run(job,'error',text='Lỗi: '+worker.error)
            self.status.setText('In gặp lỗi: '+worker.error+' Kiểm tra hàng đợi trước khi in lại.')
            if not is_pdf and self.spooler.available: self.spool_jobs[job['id']]=job
        elif is_pdf:
            if cancelled: self.set_run(job,'cancelled',text='Đã hủy PDF; không thay tệp đích')
            else:
                self.set_run(job,'exported',done=self.run_data[job['id']]['total'],text='PDF hoàn tất')
                self.status.setText('Đã lưu PDF: '+job['settings']['pdf_output'])
        else:
            if cancelled: job['cancel_requested']=True
            if self.spooler.available:
                self.spool_jobs[job['id']]=job
                self.status.setText('Đã gửi dữ liệu; đang theo dõi hàng đợi Windows để xác nhận kết thúc.')
                self.set_run(job,'cancelling' if job.get('cancel_requested') else 'spool_wait',text='Đang chờ Windows xác nhận hủy' if job.get('cancel_requested') else 'Đang chờ Windows xác nhận hàng đợi')
                if cancelled: self.request_spool_command(job,'cancel')
            else:
                self.set_run(job,'unconfirmed',text='Đã gửi; chưa đọc được hàng đợi Windows')
                self.status.setText('Đã gửi máy in, chưa xác nhận hoàn tất. Chạy lại CAI_DAT.bat để cài theo dõi hàng đợi Windows.')
        if self.closing: QTimer.singleShot(0,self.close)
        else: QTimer.singleShot(0,self.start_next_print)
    def manual(self):
        try: self.print_entries(self.selected_entries())
        except Exception as exc: self.error(exc)
    def print_entries(self,entries):
        entries=[entry for entry in entries if entry[1] not in self.active_digests()]
        if not entries:
            self.status.setText('Không có ảnh sẵn sàng in; ảnh đang xử lý sẽ không được xếp trùng.'); return
        destination=None
        if is_pdf_printer(self.printer.currentText()):
            destination=self.ask_pdf_path()
            if not destination:
                self.status.setText('Đã hủy lưu PDF. Chưa tạo tác vụ in.'); return
        self.send_batch(entries,pdf_output=destination)
    def print_latest(self,position):
        if self.closing: return
        if self.list.count()<position:
            self.status.setText(f'Chưa có ảnh thứ {position} trong khung.'); return
        item=self.list.item(position-1)
        try: self.print_entries([(Path(item.data(PATH_ROLE)),item.data(Qt.ItemDataRole.UserRole))])
        except Exception as exc: self.error(exc)
    def print_all_new(self):
        if self.closing: return
        active=self.active_digests(); entries=[]
        for index in range(self.list.count()):
            item=self.list.item(index); identity=item.data(Qt.ItemDataRole.UserRole)
            state=self.db.execute('SELECT state FROM jobs WHERE digest=?',(identity,)).fetchone()
            if identity not in active and (not state or state[0]=='cancelled'):
                entries.append((Path(item.data(PATH_ROLE)),identity))
        if not entries: self.status.setText('Không có ảnh mới chưa gửi in.'); return
        try: self.print_entries(entries)
        except Exception as exc: self.error(exc)
    def show_hotkey_help(self):
        from help_dialog import HelpDialog
        self.help_dialog=HelpDialog(self,BASE); self.help_dialog.exec()
    def add_run(self,job):
        total=len(job['entries'])*job['settings']['count']; created=time.time()
        label=datetime.fromtimestamp(created).strftime('%H:%M:%S')+f" • {len(job['entries'])} ảnh × {job['settings']['count']}"
        data={'id':job['id'],'created':created,'label':label,'state':'queued','done':0,'total':total,'current':'',
              'printer':job['settings']['printer'],'output':job['settings'].get('pdf_output',''),'document':job['settings']['document'],'spool_id':None}
        self.run_data[job['id']]=data; self.create_run_item(data)
        self.persist_run(data); self.db.commit(); self.set_run(job,'queued',text='Đang chờ' if not self.queue_paused else 'Chờ — hàng đợi đang tạm dừng')
    def create_run_item(self,data):
        item=QTreeWidgetItem([data['label'],Path(data['current']).name if data['current'] else '',f"{data['done']}/{data['total']}",data['state'],data['output'] or data['printer']])
        item.setData(0,Qt.ItemDataRole.UserRole,data['id']); item.setToolTip(4,data['output'] or data['printer'])
        self.queue_table.insertTopLevelItem(0,item); self.run_items[data['id']]=item
        if not self.queue_table.currentItem(): self.queue_table.setCurrentItem(item)
    def persist_run(self,data):
        self.db.execute('INSERT OR REPLACE INTO print_runs VALUES (?,?,?,?,?,?,?,?,?,?,?)',tuple(data[key] for key in ('id','created','label','state','done','total','current','printer','output','document','spool_id')))
    def set_run(self,job,state,done=None,current=None,text=None):
        data=self.run_data.get(job['id'])
        if not data: return
        data['state']=state
        if done is not None: data['done']=done
        if current is not None: data['current']=current
        data['spool_id']=job.get('spool_id')
        item=self.run_items[job['id']]; item.setText(1,Path(data['current']).name if data['current'] else '')
        item.setToolTip(1,data['current']); item.setText(2,f"{data['done']}/{data['total']}")
        item.setText(3,text or state)
        self.persist_run(data)
        if state!='running' or time.monotonic()-self.last_progress_commit>.25:
            self.db.commit(); self.last_progress_commit=time.monotonic()
        selected=self.queue_table.currentItem()
        if not selected or selected.data(0,Qt.ItemDataRole.UserRole)==job['id']: self.show_selected_progress()
    def show_selected_progress(self):
        item=self.queue_table.currentItem()
        if item: self.queue_table.setToolTip(' • '.join(item.text(column) for column in range(5)))
    def update_print_progress(self,job,done,total,path):
        state='paused' if self.queue_paused else 'running'
        self.set_run(job,state,done=done,current=path,text='Tạm dừng' if self.queue_paused else 'Đang xử lý ảnh')
    def load_run_history(self):
        columns=('id','created','label','state','done','total','current','printer','output','document','spool_id')
        rows=self.db.execute("SELECT * FROM print_runs WHERE state NOT IN ('exported','completed','cancelled','interrupted') OR id IN (SELECT id FROM print_runs ORDER BY created DESC LIMIT 100) ORDER BY created DESC").fetchall()
        for row in reversed(rows):
            data=dict(zip(columns,row)); self.run_data[data['id']]=data; self.create_run_item(data)
            unfinished=data['state'] in ('queued','running','paused','cancelling','spool_wait','spool_error','unconfirmed','error')
            entries=[(Path(path),digest) for path,digest in self.db.execute('SELECT jobs.file,jobs.digest FROM print_run_images JOIN jobs ON jobs.digest=print_run_images.digest WHERE print_run_images.run_id=?',(data['id'],))]
            job={'id':data['id'],'entries':entries,'settings':{'printer':data['printer'],'document':data['document'],'pdf_output':data['output']},'automatic':False,
                 'spool_id':data['spool_id'],'render_complete':True,'finished_at':time.monotonic(),'cancel_requested':data['state']=='cancelling','render_error':'Lỗi ở lần chạy trước' if data['state']=='error' else None}
            if unfinished and not data['output'] and self.spooler.available:
                self.spool_jobs[data['id']]=job; self.set_run(job,'spool_wait',text='Đang kiểm tra lại hàng đợi Windows')
            elif unfinished: self.set_run(job,'interrupted',text='Tác vụ trước bị gián đoạn — kiểm tra trước khi in lại')
            else:
                texts={'exported':'PDF hoàn tất','completed':'Không còn trong hàng đợi Windows','cancelled':'Đã hủy','error':'Lỗi ở lần chạy trước','interrupted':'Bị gián đoạn','submitted':'Đã gửi máy in'}
                self.run_items[data['id']].setText(3,texts.get(data['state'],data['state']))
        if self.queue_table.topLevelItemCount(): self.queue_table.setCurrentItem(self.queue_table.topLevelItem(0))
    def pause_printing(self):
        self.queue_paused=True
        if self.print_worker: self.print_worker.pause()
        targets=dict(self.spool_jobs)
        if self.current_print_job and not self.current_print_job['settings'].get('pdf_output'): targets[self.current_print_job['id']]=self.current_print_job
        for job in targets.values(): self.request_spool_command(job,'pause')
        if self.current_print_job: self.set_run(self.current_print_job,'paused',text='Đã tạm dừng xử lý')
        self.status.setText('Đã tạm dừng hàng đợi của phần mềm; đang gửi yêu cầu tạm dừng các lệnh Windows đã nhận diện.')
    def resume_printing(self):
        self.queue_paused=False
        if self.print_worker: self.print_worker.resume()
        targets=dict(self.spool_jobs)
        if self.current_print_job and not self.current_print_job['settings'].get('pdf_output'): targets[self.current_print_job['id']]=self.current_print_job
        for job in targets.values(): self.request_spool_command(job,'resume')
        if self.current_print_job: self.set_run(self.current_print_job,'running',text='Tiếp tục xử lý ảnh')
        self.start_next_print(); self.status.setText('Đã tiếp tục hàng đợi.')
    def cancel_selected_print(self):
        item=self.queue_table.currentItem()
        if not item: self.status.setText('Chọn một dòng tiến độ để hủy.'); return
        identity=item.data(0,Qt.ItemDataRole.UserRole)
        if self.current_print_job and self.current_print_job['id']==identity:
            job=self.current_print_job; job['cancel_requested']=True; self.print_worker.cancel()
            self.set_run(job,'cancelling',text='Đang hủy tác vụ')
            if not job['settings'].get('pdf_output'): self.request_spool_command(job,'cancel')
            return
        for job in list(self.print_queue):
            if job['id']==identity:
                self.print_queue.remove(job)
                for _,digest in job['entries']: self.db.execute('UPDATE jobs SET state=? WHERE digest=?',('cancelled',digest))
                self.set_run(job,'cancelled',text='Đã hủy trước khi gửi'); return
        if identity in self.spool_jobs:
            job=self.spool_jobs[identity]; job['cancel_requested']=True; self.set_run(job,'cancelling',text='Đang yêu cầu Windows hủy lệnh')
            self.request_spool_command(job,'cancel')
        else: self.status.setText('Dòng này đã kết thúc hoặc chưa có mã lệnh Windows. Có thể mở hàng đợi Windows để kiểm tra.')
    def request_spool_command(self,job,action):
        if not self.spooler.available:
            self.status.setText('Chưa có bộ điều khiển Windows. Chạy lại CAI_DAT.bat hoặc mở hàng đợi Windows để hủy.'); return
        future=self.spool_command_pool.submit(self.spooler.command,job['settings']['printer'],job['settings']['document'],job.get('spool_id'),action)
        self.spool_commands.append((job,action,future))
    def attach_spool_job(self,job,identity):
        job['spool_id']=identity; self.spool_jobs[job['id']]=job
        self.run_data[job['id']]['spool_id']=identity; self.persist_run(self.run_data[job['id']]); self.db.commit()
    def poll_spooler(self):
        if self.closed: return
        for job,action,future in list(self.spool_commands):
            if not future.done(): continue
            self.spool_commands.remove((job,action,future))
            try:
                result=future.result(); job.pop('control_error',None)
                if result.get('job_id') is not None: job['spool_id']=result['job_id']
                if job['id'] in self.spool_jobs or job is self.current_print_job:
                    text={'cancel':'Đã yêu cầu Windows hủy; chờ lệnh biến mất','pause':'Đã gửi yêu cầu tạm dừng đến Windows','resume':'Đã gửi yêu cầu tiếp tục đến Windows'}[action]
                    self.set_run(job,'cancelling' if action=='cancel' else 'spool_wait',text=text)
            except Exception as exc:
                job['control_error']='Windows chưa thực hiện được lệnh '+action+' ('+type(exc).__name__+')'
                self.set_run(job,'spool_error',text=job['control_error'])
        for identity,(issued,future) in list(self.spool_reads.items()):
            if not future.done(): continue
            self.spool_reads.pop(identity,None); job=self.spool_jobs.get(identity)
            if not job: continue
            try:
                info=future.result()
                if info['exists']:
                    job['spool_id']=info['job_id']; job['absent_count']=0
                    if job['render_complete']:
                        text=status_text(info)
                        if job.get('control_error'): text+=' • '+job['control_error']
                        if info.get('pages'): text+=f" • {info.get('printed',0)}/{info['pages']} trang"
                        self.set_run(job,'spool_error' if job.get('control_error') else ('cancelling' if job.get('cancel_requested') else 'spool_wait'),text=text)
                elif job['render_complete'] and issued>=job.get('finished_at',0):
                    job['absent_count']=job.get('absent_count',0)+1
                    if job.get('spool_id') is not None or job['absent_count']>=2:
                        cancelled=job.get('cancel_requested',False)
                        final='cancelled' if cancelled else ('error' if job.get('render_error') else 'completed')
                        self.set_run(job,final,text='Đã hủy / lệnh không còn trong Windows' if cancelled else ('Tác vụ lỗi; không còn lệnh trong Windows' if job.get('render_error') else 'Không còn trong hàng đợi Windows'))
                        self.spool_jobs.pop(identity,None)
                        if cancelled:
                            for _,digest in job['entries']: self.db.execute('UPDATE jobs SET state=? WHERE digest=?',('review',digest))
                            self.db.commit()
            except Exception as exc: self.set_run(job,'spool_error',text='Chưa đọc được hàng đợi Windows ('+type(exc).__name__+') — chưa hoàn tất')
        if not self.spooler.available: return
        for identity,job in list(self.spool_jobs.items()):
            if identity not in self.spool_reads:
                self.spool_reads[identity]=(time.monotonic(),self.spool_pool.submit(self.spooler.read,job['settings']['printer'],job['settings']['document'],job.get('spool_id')))
    def clear_progress(self):
        active={job['id'] for job in self.print_queue}|set(self.spool_jobs)
        if self.current_print_job: active.add(self.current_print_job['id'])
        terminal=('exported','completed','cancelled','error','interrupted')
        placeholders=','.join('?' for _ in terminal)
        condition=f'state IN ({placeholders})'; params=list(terminal)
        if active:
            condition+=' AND id NOT IN ('+','.join('?' for _ in active)+')'; params.extend(active)
        removed=self.db.execute('SELECT COUNT(*) FROM print_runs WHERE '+condition,params).fetchone()[0]
        self.db.execute('DELETE FROM print_run_images WHERE run_id IN (SELECT id FROM print_runs WHERE '+condition+')',params)
        self.db.execute('DELETE FROM print_runs WHERE '+condition,params)
        for identity in list(self.run_items):
            if identity in active or self.run_data[identity]['state'] not in terminal: continue
            item=self.run_items.pop(identity); self.queue_table.takeTopLevelItem(self.queue_table.indexOfTopLevelItem(item)); self.run_data.pop(identity,None)
        self.db.commit(); self.status.setText(f'Đã xóa tất cả {removed} dòng lịch sử đã kết thúc. Giữ nguyên lệnh đang chờ/in, file ảnh và chống in trùng.')
    def open_windows_queue(self):
        if sys.platform!='win32': self.status.setText('Chức năng này dùng trên Windows.'); return
        import subprocess
        item=self.queue_table.currentItem(); identity=item.data(0,Qt.ItemDataRole.UserRole) if item else None
        printer=self.run_data[identity]['printer'] if identity in self.run_data else self.printer.currentText()
        if not printer or is_pdf_printer(printer): self.status.setText('Chọn một tác vụ của máy in thật.'); return
        try: subprocess.Popen(['rundll32.exe','printui.dll,PrintUIEntry','/o','/n',printer])
        except OSError as exc: self.error(exc)
    def collect(self):
        self.telegram_dialog.show(); self.telegram_dialog.raise_(); self.telegram_dialog.activateWindow()
if __name__=='__main__':
    app=QApplication(sys.argv)
    if '--smoke-test' in sys.argv:
        from smoke import run_smoke_test
        import traceback
        try: report=run_smoke_test(Window,BASE); result=0
        except Exception: report={'ok':False,'error':traceback.format_exc()}; result=1
        if '--smoke-report' in sys.argv:
            destination=Path(sys.argv[sys.argv.index('--smoke-report')+1]); destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        elif sys.stdout: print(json.dumps(report,ensure_ascii=False))
        sys.exit(result)
    instance_lock=QLockFile(str(BASE/'application.lock'))
    if not instance_lock.tryLock(0):
        QMessageBox.information(None,'Ứng dụng đang chạy','Telegram Photo Print đã mở. Chuyển sang cửa sổ đang chạy để tiếp tục.'); sys.exit(0)
    window=Window(); window.show(); sys.exit(app.exec())
