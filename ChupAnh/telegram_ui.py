from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QFormLayout,QVBoxLayout,QHBoxLayout,QLineEdit,
    QComboBox,QPushButton,QLabel,QMessageBox)
from telegram_source import TelegramWorker

class TelegramDialog(QDialog):
    def __init__(self,owner,base):
        super().__init__(owner); self.owner=owner; self.base=base; self.worker=None; self.active=False; self.auth_stage='phone'; self.close_when_stopped=False
        self.setWindowTitle('Kết nối Telegram'); self.resize(650,530)
        self.mode=QComboBox(); self.mode.addItems(['Bot Telegram','Tài khoản Telegram'])
        self.token=QLineEdit(); self.token.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_id=QLineEdit(); self.api_hash=QLineEdit(); self.api_hash.setEchoMode(QLineEdit.EchoMode.Password)
        self.auth=QLineEdit(); self.auth.setPlaceholderText('Số điện thoại dạng +84…')
        self.group=QComboBox(); self.group.setMinimumContentsLength(30)
        self.info=QLabel('Bot: lấy token từ @BotFather. Tài khoản: lấy API ID và API Hash tại my.telegram.org.'); self.info.setWordWrap(True)
        self.state=QLabel('Chưa kết nối'); self.state.setWordWrap(True)
        self.form=QFormLayout(); self.form.addRow('Chế độ',self.mode); self.form.addRow('Bot token',self.token)
        self.form.addRow('API ID',self.api_id); self.form.addRow('API Hash',self.api_hash)
        self.form.addRow('Đăng nhập',self.auth); self.form.addRow('Nhóm',self.group)
        root=QVBoxLayout(self); root.addWidget(self.info); root.addLayout(self.form)
        row=QHBoxLayout(); self.connect_button=QPushButton('Kết nối'); self.stop_button=QPushButton('Ngắt kết nối')
        self.login_button=QPushButton('Gửi số điện thoại'); self.select_button=QPushButton('Nhận ảnh từ nhóm')
        for b in (self.connect_button,self.stop_button,self.login_button,self.select_button): row.addWidget(b)
        root.addLayout(row); root.addWidget(self.state)
        help_text=QLabel('Bot chỉ thấy nhóm khi nhận được cập nhật từ nhóm: thêm bot, cho phép nhận ảnh bằng quyền quản trị hoặc tắt Group Privacy trong @BotFather, rồi gửi tin nhắn mới. Không lấy lịch sử.\nTài khoản: chọn một nhóm đang tham gia. Bản này nhận ảnh mới kể từ lúc chọn nhóm, không tự tải lịch sử.\nCó thể thu nhỏ cửa sổ này; kết nối tiếp tục chạy. Đóng cửa sổ sẽ dừng nhận ảnh.')
        help_text.setWordWrap(True); root.addWidget(help_text)
        self.connect_button.clicked.connect(self.connect_source); self.stop_button.clicked.connect(self.stop)
        self.login_button.clicked.connect(self.authenticate); self.select_button.clicked.connect(self.select)
        self.mode.currentIndexChanged.connect(self.change_mode); self.change_mode()
    def change_mode(self):
        bot=self.mode.currentIndex()==0
        for field,show in ((self.token,bot),(self.api_id,not bot),(self.api_hash,not bot),(self.auth,not bot)):
            field.setVisible(show); self.form.labelForField(field).setVisible(show)
        self.login_button.setVisible(not bot); self.login_button.setEnabled(False); self.select_button.setEnabled(False)
    def connect_source(self):
        if self.worker: return
        mode='bot' if self.mode.currentIndex()==0 else 'account'
        if mode=='bot':
            creds={'token':self.token.text().strip()}
            if not creds['token']: self.state.setText('Nhập Bot token.'); return
        else:
            if not self.api_id.text().isdigit() or not self.api_hash.text().strip(): self.state.setText('Nhập API ID dạng số và API Hash.'); return
            creds={'api_id':self.api_id.text(),'api_hash':self.api_hash.text()}
        self.owner.auto.setChecked(False); self.active=True
        worker=TelegramWorker(mode,creds,self.base,self); self.worker=worker
        worker.status.connect(self.state.setText); worker.groups.connect(self.set_groups)
        worker.stage.connect(self.set_stage); worker.image.connect(self.receive)
        worker.finished.connect(self.finished_worker)
        self.connect_button.setEnabled(False); self.mode.setEnabled(False)
        self.token.setEnabled(False); self.api_id.setEnabled(False); self.api_hash.setEnabled(False)
        self.group.clear(); self.state.setText('Đang kết nối…'); worker.start()
    def set_stage(self,stage):
        if stage=='ready': self.login_button.setEnabled(False); self.select_button.setEnabled(True)
        elif stage in ('phone','code','password'):
            self.auth_stage=stage; self.auth.clear(); self.login_button.setEnabled(True)
            self.auth.setEchoMode(QLineEdit.EchoMode.Password if stage in ('code','password') else QLineEdit.EchoMode.Normal)
            self.auth.setPlaceholderText({'phone':'Số điện thoại +84…','code':'Mã đăng nhập Telegram gửi cho bạn','password':'Mật khẩu xác thực hai bước'}[stage])
            self.login_button.setText({'phone':'Gửi số điện thoại','code':'Xác nhận mã','password':'Xác nhận mật khẩu'}[stage])
    def authenticate(self):
        if self.worker and self.auth.text():
            self.worker.command(self.auth_stage,self.auth.text()); self.auth.clear()
    def set_groups(self,groups):
        current=self.group.currentData(); self.group.clear()
        for chat_id,title in sorted(groups,key=lambda item:item[1].casefold()): self.group.addItem(f'{title}  [{chat_id}]',chat_id)
        index=self.group.findData(current)
        if index>=0: self.group.setCurrentIndex(index)
    def select(self):
        if self.worker and self.group.currentData() is not None:
            self.owner.auto.setChecked(False)
            self.worker.command('select',self.group.currentData())
            self.state.setText('Đang chọn nhóm. In tự động đã tắt; kiểm tra ảnh nhận được rồi bật lại nếu cần.')
    def receive(self,path):
        if self.active:
            from pathlib import Path
            self.owner.enqueue(Path(path),self.owner.auto.isChecked())
    def stop(self):
        self.active=False; self.owner.auto.setChecked(False)
        if self.worker: self.worker.command('stop'); self.state.setText('Đang ngắt kết nối…'); self.select_button.setEnabled(False)
    def finished_worker(self):
        self.active=False; self.owner.auto.setChecked(False)
        old=self.worker; self.worker=None
        if old: old.deleteLater()
        self.connect_button.setEnabled(True); self.mode.setEnabled(True)
        self.token.clear(); self.token.setEnabled(True); self.api_id.setEnabled(True); self.api_hash.setEnabled(True)
        self.select_button.setEnabled(False); self.login_button.setEnabled(False)
        if self.close_when_stopped:
            self.close_when_stopped=False; self.close()
    def closeEvent(self,event):
        if self.worker:
            self.close_when_stopped=True; self.stop(); self.state.setText('Đang dừng kết nối…'); event.ignore()
        else: event.accept()
