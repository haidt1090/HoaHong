from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QFormLayout,QVBoxLayout,QHBoxLayout,QLineEdit,
    QComboBox,QPushButton,QLabel,QMessageBox,QCheckBox)
from telegram_source import TelegramWorker
from connection_store import ConnectionStore

class TelegramDialog(QDialog):
    def __init__(self,owner,base):
        super().__init__(owner); self.owner=owner; self.base=base; self.worker=None; self.active=False; self.auth_stage='phone'; self.close_when_stopped=False
        self.saved=None; self.receiving_id=None; self.receiving_title=''; self.ready=False
        try: self.store=ConnectionStore(base); self.saved=self.store.load()
        except Exception: self.store=None
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
        root.addLayout(row)
        save_row=QHBoxLayout(); self.save_button=QPushButton('Lưu kết nối'); self.forget_button=QPushButton('Quên kết nối')
        self.auto_connect=QCheckBox('Tự kết nối khi mở phần mềm'); self.auto_connect.setChecked(True)
        save_row.addWidget(self.save_button); save_row.addWidget(self.forget_button); save_row.addWidget(self.auto_connect)
        root.addLayout(save_row); root.addWidget(self.state)
        help_text=QLabel('Bot chỉ thấy nhóm khi nhận được cập nhật từ nhóm: thêm bot, cho phép nhận ảnh bằng quyền quản trị hoặc tắt Group Privacy trong @BotFather, rồi gửi tin nhắn mới. Không lấy lịch sử.\nTài khoản: chọn một nhóm đang tham gia. Bản này nhận ảnh mới kể từ lúc chọn nhóm, không tự tải lịch sử.\nCó thể thu nhỏ cửa sổ này; kết nối tiếp tục chạy. Đóng cửa sổ này vẫn nhận ảnh; chỉ nút Ngắt kết nối hoặc thoát ứng dụng mới dừng.')
        help_text.setWordWrap(True); root.addWidget(help_text)
        self.connect_button.clicked.connect(self.connect_source); self.stop_button.clicked.connect(self.stop)
        self.login_button.clicked.connect(self.authenticate); self.select_button.clicked.connect(self.select)
        self.mode.currentIndexChanged.connect(self.change_mode); self.change_mode()
        self.save_button.clicked.connect(self.save_connection); self.forget_button.clicked.connect(self.forget_connection)
        if self.saved:
            self.mode.setCurrentIndex(0 if self.saved['mode']=='bot' else 1)
            creds=self.saved['credentials']
            self.token.setText(creds.get('token','')); self.api_id.setText(creds.get('api_id','')); self.api_hash.setText(creds.get('api_hash',''))
            self.auto_connect.setChecked(self.saved.get('auto_connect',True))
            self.group.addItem(f"{self.saved['group_title']}  [{self.saved['group_id']}]",self.saved['group_id'])
            self.state.setText('Đã khôi phục kết nối đã lưu. Token được giữ trong kho thông tin đăng nhập của hệ điều hành.')
    def credentials(self):
        if self.mode.currentIndex()==0: return {'token':self.token.text().strip()}
        return {'api_id':self.api_id.text().strip(),'api_hash':self.api_hash.text().strip()}
    def matches_saved(self):
        return self.saved and self.saved['mode']==('bot' if self.mode.currentIndex()==0 else 'account') and self.saved['credentials']==self.credentials()
    def restore_startup(self):
        if self.saved and self.saved.get('auto_connect'): self.connect_source(restore=True)
    def save_connection(self):
        if self.receiving_id is None:
            self.state.setText('Chọn nhóm và bấm Nhận ảnh từ nhóm trước khi lưu.'); return
        try:
            if not self.store: self.store=ConnectionStore(self.base)
            mode='bot' if self.mode.currentIndex()==0 else 'account'
            self.store.save(mode,self.credentials(),self.receiving_id,self.receiving_title,self.auto_connect.isChecked())
            self.saved=self.store.load()
            self.state.setText('Đã lưu bot/tài khoản và nhóm. Đóng cửa sổ này vẫn tiếp tục nhận ảnh.')
        except Exception:
            self.state.setText('Không lưu được vào kho thông tin đăng nhập Windows. Chạy lại CAI_DAT.bat để cài keyring; không lưu token dạng văn bản.')
    def forget_connection(self):
        try:
            if self.store: self.store.forget()
            self.saved=None; self.state.setText('Đã quên kết nối lưu. Kết nối hiện tại vẫn chạy; bấm Ngắt kết nối để dừng.')
        except Exception: self.state.setText('Chưa xóa được thông tin đăng nhập đã lưu trên máy.')
    def change_mode(self):
        bot=self.mode.currentIndex()==0
        for field,show in ((self.token,bot),(self.api_id,not bot),(self.api_hash,not bot),(self.auth,not bot)):
            field.setVisible(show); self.form.labelForField(field).setVisible(show)
        self.login_button.setVisible(not bot); self.login_button.setEnabled(False); self.select_button.setEnabled(False)
    def connect_source(self,restore=False):
        if self.worker: return
        mode='bot' if self.mode.currentIndex()==0 else 'account'
        if mode=='bot':
            creds={'token':self.token.text().strip()}
            if not creds['token']: self.state.setText('Nhập Bot token.'); return
        else:
            if not self.api_id.text().isdigit() or not self.api_hash.text().strip(): self.state.setText('Nhập API ID dạng số và API Hash.'); return
            creds={'api_id':self.api_id.text(),'api_hash':self.api_hash.text()}
        if not restore: self.owner.auto.setChecked(False)
        self.active=True
        worker=TelegramWorker(mode,creds,self.base,self); self.worker=worker
        self.ready=False; self.receiving_id=None
        if self.matches_saved():
            self.receiving_id=int(self.saved['group_id']); self.receiving_title=self.saved['group_title']
            worker.selected=self.receiving_id; worker.known[self.receiving_id]=self.receiving_title
        worker.status.connect(self.update_status); worker.groups.connect(self.set_groups)
        worker.stage.connect(self.set_stage); worker.image.connect(self.receive)
        worker.finished.connect(self.finished_worker)
        self.connect_button.setEnabled(False); self.mode.setEnabled(False)
        self.token.setEnabled(False); self.api_id.setEnabled(False); self.api_hash.setEnabled(False)
        self.group.clear()
        if self.receiving_id is not None: self.group.addItem(f'{self.receiving_title}  [{self.receiving_id}]',self.receiving_id)
        self.state.setText('Đang kết nối…'); worker.start()
    def update_status(self,text):
        self.state.setText(text); self.owner.status.setText('Telegram: '+text)
    def set_stage(self,stage):
        if stage=='ready':
            self.ready=True; self.login_button.setEnabled(False); self.select_button.setEnabled(True)
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
            self.receiving_id=self.group.currentData(); self.receiving_title=self.group.currentText().rsplit('  [',1)[0]
            self.worker.command('select',self.receiving_id)
            self.state.setText('Đang chọn nhóm. In tự động đã tắt; kiểm tra ảnh nhận được rồi bật lại nếu cần.')
    def receive(self,path):
        if self.active:
            from pathlib import Path
            if self.owner.enqueue(Path(path),self.owner.auto.isChecked(),allow_hidden=True,occurrence='telegram:'+str(Path(path).resolve())):
                # Do not change the user's manual batch selection as new photos arrive.
                self.update_status('Đã nhận ảnh: '+Path(path).name+(' — đã bật in tự động.' if self.owner.auto.isChecked() else ' — chờ bạn bấm in.'))
    def stop(self):
        self.active=False; self.owner.auto.setChecked(False)
        if self.worker: self.worker.command('stop'); self.state.setText('Đang ngắt kết nối…'); self.select_button.setEnabled(False)
    def finished_worker(self):
        self.active=False; self.ready=False; self.owner.auto.setChecked(False)
        old=self.worker; self.worker=None
        if old: old.deleteLater()
        self.connect_button.setEnabled(True); self.mode.setEnabled(True)
        self.token.setEnabled(True); self.api_id.setEnabled(True); self.api_hash.setEnabled(True)
        self.select_button.setEnabled(False); self.login_button.setEnabled(False)
        if self.close_when_stopped:
            self.close_when_stopped=False; self.close()
    def closeEvent(self,event):
        # Configuration window is independent of the connection lifetime.
        event.accept()
