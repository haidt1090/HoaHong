"""Interactive preview using the exact millimetre placements used by printing."""
from pathlib import Path
from PySide6.QtCore import Qt,QRectF,QSize,QTimer
from PySide6.QtGui import QColor,QPen,QBrush,QImageReader,QPixmap,QPainter
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QComboBox,QSpinBox,
    QDoubleSpinBox,QLineEdit,QPushButton,QLabel,QGraphicsView,QGraphicsScene)
from layout import PAPERS,PHOTOS,batch_pages,layout_kwargs
from formats import FormatStore,clean_format

class PreviewEditor(QDialog):
    def __init__(self,owner,entries,base):
        super().__init__(owner); self.owner=owner; self.entries=list(entries); self.store=FormatStore(base); self.pages=[]
        self.setWindowTitle('Xem trước và chỉnh mẫu in'); self.resize(980,780)
        self.paper=QComboBox(); self.paper.addItems(PAPERS)
        self.photo=QComboBox(); self.photo.addItems(PHOTOS)
        self.count=QSpinBox(); self.count.setRange(1,999)
        self.margin=self.distance(0,50); self.gap_x=self.distance(-59,50); self.gap_y=self.distance(-59,50)
        self.templates=QComboBox(); self.templates.addItem('Chọn mẫu đã lưu…'); self.templates.addItems(self.store.load())
        self.name=QLineEdit(owner.saved.get('active_format','Mẫu in của tôi'))
        self.page=QSpinBox(); self.page.setRange(1,1); self.page.setPrefix('Trang ')
        self.status=QLabel(); self.status.setWordWrap(True)
        self.scene=QGraphicsScene(self); self.view=QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform); self.view.setBackgroundBrush(QColor('#d9dde2'))
        form=QFormLayout(); form.addRow('Khổ giấy',self.paper); form.addRow('Kích thước ảnh',self.photo); form.addRow('Số bản / mỗi ảnh',self.count)
        form.addRow('Lề giấy (mm)',self.margin); form.addRow('Khoảng cách ngang (mm)',self.gap_x); form.addRow('Khoảng cách dọc (mm)',self.gap_y)
        root=QVBoxLayout(self); template_row=QHBoxLayout(); template_row.addWidget(self.templates,1); template_row.addWidget(self.name,1)
        save=QPushButton('Lưu mẫu'); save.clicked.connect(self.save_template); template_row.addWidget(save); root.addLayout(template_row)
        root.addLayout(form); root.addWidget(QLabel('Khoảng cách dương: tách xa • 0: sát nhau • âm: chồng ảnh. Thứ tự chồng giống bản in.'))
        root.addWidget(self.page); root.addWidget(self.view,1); root.addWidget(self.status)
        actions=QHBoxLayout(); self.apply_button=QPushButton('Áp dụng và lưu cài đặt'); self.apply_button.clicked.connect(self.apply_and_close)
        self.print_button=QPushButton('In ảnh đã chọn'); self.print_button.clicked.connect(self.print_selected)
        close=QPushButton('Đóng'); close.clicked.connect(self.reject)
        for button in (self.apply_button,self.print_button,close): actions.addWidget(button)
        root.addLayout(actions)
        for field in (self.paper,self.photo): field.currentTextChanged.connect(self.rebuild)
        for field in (self.count,self.margin,self.gap_x,self.gap_y): field.valueChanged.connect(self.rebuild)
        self.page.valueChanged.connect(self.show_page); self.templates.currentIndexChanged.connect(self.load_template)
        self.set_values(owner.snapshot())
    def distance(self,low,high):
        field=QDoubleSpinBox(); field.setRange(low,high); field.setDecimals(1); field.setSingleStep(.5); field.setSuffix(' mm'); return field
    def values(self):
        return clean_format({'paper':self.paper.currentText(),'photo':self.photo.currentText(),'count':self.count.value(),
            'margin_mm':self.margin.value(),'gap_x_mm':self.gap_x.value(),'gap_y_mm':self.gap_y.value()})
    def set_values(self,values):
        fields=(self.paper,self.photo,self.count,self.margin,self.gap_x,self.gap_y)
        for field in fields: field.blockSignals(True)
        self.paper.setCurrentText(values['paper']); self.photo.setCurrentText(values['photo']); self.count.setValue(values.get('count',4))
        self.margin.setValue(values.get('margin_mm',7)); self.gap_x.setValue(values.get('gap_x_mm',3)); self.gap_y.setValue(values.get('gap_y_mm',3))
        for field in fields: field.blockSignals(False)
        self.rebuild()
    def rebuild(self,*args):
        pw,ph=PHOTOS[self.photo.currentText()]
        self.gap_x.blockSignals(True); self.gap_y.blockSignals(True)
        self.gap_x.setMinimum(5-pw); self.gap_y.setMinimum(5-ph)
        self.gap_x.blockSignals(False); self.gap_y.blockSignals(False)
        try:
            values=self.values(); self.pages=list(batch_pages(values['paper'],values['photo'],[(path,values['count']) for path,_ in self.entries],**layout_kwargs(values)))
            self.page.blockSignals(True); self.page.setRange(1,max(1,len(self.pages))); self.page.blockSignals(False)
            self.apply_button.setEnabled(True); self.print_button.setEnabled(True)
            self.status.setText(f'{len(self.entries)} ảnh × {values["count"]} bản • {len(self.pages)} trang. Mẫu này áp dụng cho cả in tay, tự động và PDF.')
            self.show_page()
        except (ValueError,KeyError) as exc:
            self.pages=[]; self.scene.clear(); self.apply_button.setEnabled(False); self.print_button.setEnabled(False); self.status.setText(str(exc))
    def show_page(self,*args):
        self.scene.clear()
        if not self.pages: return
        values=self.values(); width,height=PAPERS[values['paper']]
        self.scene.setSceneRect(QRectF(-3,-3,width+6,height+6))
        self.scene.addRect(QRectF(0,0,width,height),QPen(QColor('#777'),.3),QBrush(QColor('white')))
        cache={}
        for order,(path,(x,y,w,h)) in enumerate(self.pages[self.page.value()-1]):
            if path not in cache:
                reader=QImageReader(str(path)); reader.setAutoTransform(True); original=reader.size()
                if original.isValid(): reader.setScaledSize(original.scaled(QSize(450,600),Qt.AspectRatioMode.KeepAspectRatio))
                cache[path]=QPixmap.fromImage(reader.read())
            pixmap=cache[path]
            if pixmap.isNull(): continue
            scale=min(w/pixmap.width(),h/pixmap.height()); item=self.scene.addPixmap(pixmap); item.setScale(scale)
            item.setPos(x+(w-pixmap.width()*scale)/2,y+(h-pixmap.height()*scale)/2); item.setZValue(order+1)
        self.view.fitInView(self.scene.sceneRect(),Qt.AspectRatioMode.KeepAspectRatio)
    def showEvent(self,event):
        super().showEvent(event); QTimer.singleShot(0,self.show_page)
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'view'): self.view.fitInView(self.scene.sceneRect(),Qt.AspectRatioMode.KeepAspectRatio)
    def save_template(self):
        try:
            self.store.save(self.name.text(),self.values()); self.status.setText('Đã lưu mẫu: '+self.name.text())
            self.templates.blockSignals(True); self.templates.clear(); self.templates.addItem('Chọn mẫu đã lưu…'); self.templates.addItems(self.store.load()); self.templates.setCurrentText(self.name.text()); self.templates.blockSignals(False)
        except (ValueError,OSError) as exc: self.status.setText(str(exc))
    def load_template(self,index):
        values=self.store.load().get(self.templates.currentText())
        if values: self.name.setText(self.templates.currentText()); self.set_values(values)
    def apply_values(self):
        values=self.values()
        if self.name.text().strip(): self.store.save(self.name.text(),values)
        self.owner.apply_format(values,self.name.text().strip()); self.owner.save_settings()
    def apply_and_close(self):
        try: self.apply_values(); self.accept()
        except (ValueError,OSError) as exc: self.status.setText(str(exc))
    def print_selected(self):
        try: self.apply_values(); self.owner.print_entries(self.entries)
        except (ValueError,OSError) as exc: self.status.setText(str(exc))
