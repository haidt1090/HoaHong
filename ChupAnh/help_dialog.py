from pathlib import Path
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QTabWidget,QTextBrowser,QTextEdit,QPushButton,QLabel

class HelpDialog(QDialog):
    def __init__(self,owner,base):
        super().__init__(owner); self.path=Path(base)/'requirements-notes.md'
        self.setWindowTitle('Hướng dẫn và tổng hợp yêu cầu'); self.resize(820,650)
        root=QVBoxLayout(self); tabs=QTabWidget(); root.addWidget(tabs,1)
        hotkeys=QTextBrowser(); hotkeys.setPlainText(
            'Alt+1 … Alt+9: in ngay ảnh mới nhất theo vị trí từ trái qua phải, trên xuống dưới.\n\n'
            'Alt+A: chỉ in ảnh mới chưa gửi in, bỏ qua ảnh đang chờ, đã in/xuất PDF hoặc cần kiểm tra.\n\n'
            'F1 hoặc ?: mở hướng dẫn. Phím tắt có tác dụng trong cửa sổ chính.\n\n'
            'In tay không hỏi Yes/No. Nếu chọn PDF vẫn hỏi nơi lưu.\n\n'
            'Xem trước ảnh đã chọn: chỉnh khổ, kích thước, số bản, lề, khoảng cách ngang/dọc. Khoảng cách âm là chồng ảnh.\n\n'
            'Lưu mẫu để tái sử dụng; Áp dụng và lưu cài đặt để dùng cho in tay/tự động/PDF.\n\n'
            'Lưu cài đặt nhớ cả trạng thái Tự động in. Sửa kết nối cho phép đổi token, username và nhóm; token nằm trong kho thông tin đăng nhập Windows.\n\n'
            'Xóa tất cả tiến độ chỉ xóa lịch sử đã kết thúc. Lệnh còn trong Windows chưa được báo hoàn tất.')
        tabs.addTab(hotkeys,'Hướng dẫn / Hotkey')
        self.notes=QTextEdit()
        try: text=self.path.read_text(encoding='utf-8')
        except OSError:
            try: text=Path(__file__).with_name('YEU_CAU.md').read_text(encoding='utf-8')
            except OSError: text='Tổng hợp yêu cầu và ghi chú tùy chỉnh.\n'
        self.notes.setPlainText(text); tabs.addTab(self.notes,'Yêu cầu — có thể chỉnh sửa')
        self.status=QLabel('Nội dung ghi chú không tự thay đổi mã/chức năng phần mềm.'); self.status.setWordWrap(True); root.addWidget(self.status)
        buttons=QHBoxLayout(); save=QPushButton('Lưu nội dung yêu cầu'); save.clicked.connect(self.save_notes)
        close=QPushButton('Đóng'); close.clicked.connect(self.accept); buttons.addWidget(save); buttons.addWidget(close); root.addLayout(buttons)
    def save_notes(self):
        try:
            self.path.parent.mkdir(parents=True,exist_ok=True); temporary=self.path.with_suffix('.tmp')
            temporary.write_text(self.notes.toPlainText(),encoding='utf-8'); temporary.replace(self.path)
            self.status.setText('Đã lưu nội dung yêu cầu / ghi chú trên máy này.')
        except OSError as exc: self.status.setText('Không lưu được: '+str(exc))
