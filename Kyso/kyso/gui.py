"""Tkinter desktop shell. Browser and token automation share one worker thread."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .browser import ChromeSession
from .settings import AppSettings, load_settings, save_settings
from .windows import (
    AutomatedTokenPrompt, ManualTokenPrompt, launch_chrome, list_certificates,
)
from .workflow import BatchSigner


class SignerApp(ttk.Frame):
    def __init__(self, master: tk.Tk, *, executor=None, autoload=True):
        super().__init__(master, padding=16)
        self.root = master
        self.executor = executor or ThreadPoolExecutor(max_workers=1, thread_name_prefix="kyso")
        self.events = queue.Queue()
        self.stop_event = threading.Event()
        self.browser = None
        self.records = {}
        self.certificates = []
        self.busy = False
        self.closing = False
        self.destroyed = False
        self.signing = False
        self.settings_error = ""
        try:
            self.settings = load_settings()
        except (OSError, ValueError) as exc:
            self.settings = AppSettings()
            self.settings_error = str(exc)
        self.status = tk.StringVar(value="Mở Chrome riêng, đăng nhập rồi quét hồ sơ.")
        self.selection_summary = tk.StringVar(value="0 hồ sơ · 0 đã chọn")
        self.certificate_value = tk.StringVar()
        self.pin = tk.StringVar()
        self.automatic_pin = tk.BooleanVar(value=self.settings.automatic_pin)
        self._build()
        self.pack(fill="both", expand=True)
        master.protocol("WM_DELETE_WINDOW", self.close)
        self._poll_after = self.after(80, self._poll)
        self._autoload_after = None
        if self.settings_error:
            self.log("Không đọc được cài đặt; đang dùng mặc định. " + self.settings_error)
        if autoload:
            self._autoload_after = self.after(150, self.refresh_certificates)

    def _build(self):
        self.root.title("Ký số hồ sơ — Python")
        self.root.geometry("1080x800")
        self.root.minsize(900, 700)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(4, weight=3)
        self.rowconfigure(7, weight=1)
        style = ttk.Style(self)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Title.TLabel", font=("Segoe UI", 19, "bold"))
        style.configure("Treeview", rowheight=27)
        ttk.Label(self, text="Ký số hồ sơ", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(self, text="admin.csdlksk.vn  •  Đăng nhập bằng tài khoản của bạn trong Chrome riêng").grid(row=1, column=0, sticky="w", pady=(4, 12))

        self.toolbar = ttk.Frame(self)
        self.toolbar.grid(row=2, column=0, sticky="ew")
        self.action_buttons = []
        for column, (label, command) in enumerate([
            ("1. Mở Chrome", self.open_chrome),
            ("2. Kết nối", self.connect),
            ("3. Quét hồ sơ", self.scan),
            ("Lấy chứng thư USB", self.refresh_certificates),
            ("Lưu cài đặt", self.save),
        ]):
            button = ttk.Button(self.toolbar, text=label, command=command)
            button.grid(row=0, column=column, padx=(0, 8), pady=(0, 10))
            self.action_buttons.append(button)

        config = ttk.LabelFrame(self, text="Chứng thư và USB Token", padding=10)
        config.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        config.columnconfigure(1, weight=1)
        ttk.Label(config, text="Chứng thư:").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.certificate_combo = ttk.Combobox(config, textvariable=self.certificate_value, state="readonly")
        self.certificate_combo.grid(row=0, column=1, columnspan=3, sticky="ew")
        self.pin_toggle = ttk.Checkbutton(config, text="Tự chọn chứng thư và nhập PIN (Windows)", variable=self.automatic_pin, command=self._pin_mode)
        self.pin_toggle.grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
        ttk.Label(config, text="PIN:").grid(row=1, column=2, sticky="e", padx=8, pady=(10, 0))
        self.pin_entry = ttk.Entry(config, textvariable=self.pin, show="*", width=24)
        self.pin_entry.grid(row=1, column=3, sticky="e", pady=(10, 0))
        ttk.Label(config, text="PIN chỉ giữ trong phiên này. Khi tắt tự nhập, bạn tự chọn chứng thư/nhập PIN trên cửa sổ USB Token.", wraplength=960).grid(row=2, column=0, columnspan=4, sticky="w", pady=(8, 0))
        self._pin_mode()

        table = ttk.Frame(self)
        table.grid(row=4, column=0, sticky="nsew")
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(table, columns=("id", "name", "status"), show="headings", selectmode="extended")
        for key, title, width in [("id", "Mã hồ sơ", 230), ("name", "Họ và tên", 340), ("status", "Trạng thái lúc quét", 200)]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=100)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind("<<TreeviewSelect>>", lambda _: self._selection_changed())

        self.controls = ttk.Frame(self)
        self.controls.grid(row=5, column=0, sticky="ew", pady=10)
        self.controls.columnconfigure(2, weight=1)
        self.select_all = ttk.Button(self.controls, text="Chọn tất cả", command=lambda: self.tree.selection_set(self.tree.get_children()))
        self.select_all.grid(row=0, column=0, padx=(0, 8))
        self.select_none = ttk.Button(self.controls, text="Bỏ chọn", command=lambda: self.tree.selection_remove(self.tree.selection()))
        self.select_none.grid(row=0, column=1, padx=(0, 8))
        ttk.Label(self.controls, textvariable=self.selection_summary).grid(row=0, column=2, sticky="w")
        self.sign_button = ttk.Button(self.controls, text="Ký hồ sơ đã chọn", command=self.sign_selected, state="disabled")
        self.sign_button.grid(row=0, column=3, padx=8)
        self.stop_button = ttk.Button(self.controls, text="Dừng sau hồ sơ này", command=self.stop, state="disabled")
        self.stop_button.grid(row=0, column=4)
        self.continuous_button = ttk.Button(
            self.controls, text="Ký liên tục từng đợt 100",
            command=lambda: self.sign_selected(continuous=True))
        self.continuous_button.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 0))

        ttk.Label(self, textvariable=self.status, wraplength=980).grid(row=6, column=0, sticky="w", pady=(0, 8))
        log_frame = ttk.LabelFrame(self, text="Nhật ký phiên làm việc", padding=6)
        log_frame.grid(row=7, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=7, wrap="word", state="disabled", font=("Consolas", 10))
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=log_scroll.set)
        ttk.Label(self, text="Hoàn tất thao tác không đồng nghĩa máy chủ đã xác nhận ký. Hãy kiểm tra trạng thái hồ sơ trên hệ thống.", wraplength=980).grid(row=8, column=0, sticky="w", pady=(8, 0))

    def _pin_mode(self):
        self.pin_entry.configure(state="normal" if self.automatic_pin.get() else "disabled")
        if not self.automatic_pin.get():
            self.pin.set("")

    def log(self, text):
        """Thread-safe: worker never calls Tcl or reads Tk variables."""
        self.events.put(("log", str(text)))

    def _append_log(self, text):
        secret = self.pin.get()
        if secret:
            text = text.replace(secret, "[PIN ẩn]")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{datetime.now():%H:%M:%S}] {text}\n")
        # Bound session logs and keep all logs in memory only.
        if int(self.log_text.index("end-1c").split(".")[0]) > 1200:
            self.log_text.delete("1.0", "201.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _submit(self, label, work, on_result=None):
        if self.busy or self.closing:
            return
        self.busy = True
        self.status.set(label)
        self._update_controls()
        future = self.executor.submit(work)
        def finished(task):
            try:
                value = task.result()
                self.events.put(("done", (on_result, value, None)))
            except Exception as exc:
                self.events.put(("done", (on_result, None, exc)))
        future.add_done_callback(finished)

    def _poll(self):
        if self.destroyed:
            return
        # Tests and event handlers can drain the queue early. Keep only one timer.
        if self._poll_after is not None:
            self.after_cancel(self._poll_after)
            self._poll_after = None
        while not self.events.empty():
            kind, payload = self.events.get_nowait()
            if kind == "log":
                self._append_log(payload)
            elif kind == "done":
                callback, value, error = payload
                was_signing = self.signing
                self.busy = False
                self.signing = False
                if error:
                    if was_signing:
                        self.pin.set("")
                        self._clear_records()
                    self.status.set("Không hoàn tất. Xem nhật ký để xử lý rồi thử lại.")
                    self._append_log(str(error))
                    if not self.closing:
                        messagebox.showerror("Không hoàn tất", str(error), parent=self.root)
                elif callback:
                    callback(value)
                else:
                    self.status.set("Đã hoàn tất thao tác.")
                self._update_controls()
                if self.closing:
                    self._finish_close()
                    return
        if not self.destroyed:
            self._poll_after = self.after(80, self._poll)

    def _update_controls(self):
        state = "disabled" if self.busy or self.closing else "normal"
        for button in self.action_buttons + [self.select_all, self.select_none, self.pin_toggle]:
            button.configure(state=state)
        self.certificate_combo.configure(state="disabled" if self.busy else "readonly")
        self.pin_entry.configure(state="normal" if not self.busy and self.automatic_pin.get() else "disabled")
        self.sign_button.configure(state="normal" if not self.busy and self.tree.selection() and not self.closing else "disabled")
        self.stop_button.configure(state="normal" if self.busy and self.signing and not self.stop_event.is_set() else "disabled")
        self.continuous_button.configure(state=state)

    def _selection_changed(self):
        self.selection_summary.set(f"{len(self.records)} hồ sơ · {len(self.tree.selection())} đã chọn")
        self._update_controls()

    def _ensure_browser(self):
        if self.browser is None:
            browser = ChromeSession(debugger_address=self.settings.debugger_address,
                                    base_url=self.settings.base_url, log=self.log,
                                    keep_completed_tabs=True)
            try:
                browser.connect()
            except Exception:
                browser.disconnect()
                raise
            self.browser = browser
        return self.browser

    def open_chrome(self):
        port = int(self.settings.debugger_address.rsplit(":", 1)[1])
        self._submit("Đang mở Chrome riêng…", lambda: launch_chrome(self.settings.base_url, port=port),
                     lambda _: self.status.set("Chrome đã sẵn sàng. Đăng nhập hệ thống, rồi bấm Kết nối."))

    def connect(self):
        if self.busy:
            return
        self._clear_records()
        def work():
            if self.browser is not None:
                self.browser.disconnect()
                self.browser = None
            self._ensure_browser()
        self._submit("Đang kết nối Chrome…", work,
                     lambda _: self.status.set("Đã kết nối. Bấm Quét hồ sơ để lấy danh sách chưa ký."))

    def scan(self):
        if self.busy:
            return
        self._clear_records()
        self.stop_event.clear()
        self._submit("Đang quét tối đa 100 hồ sơ chưa ký…", lambda: self._ensure_browser().scan_pending(self.stop_event, limit=100), self._set_records)

    def _set_records(self, records):
        self._clear_records()
        for index, record in enumerate(records):
            iid = f"record-{index}"
            self.records[iid] = record
            self.tree.insert("", "end", iid=iid, values=(record.check_up_id, record.full_name, record.status))
        self._selection_changed()
        self.status.set(f"Tìm thấy {len(self.records)} hồ sơ chưa ký. Chọn hồ sơ cần ký; danh sách là ảnh chụp tại thời điểm quét.")

    def refresh_certificates(self):
        self._submit("Đang lấy chứng thư có khóa riêng trên Windows…", list_certificates, self._set_certificates)

    def _set_certificates(self, certificates):
        self.certificates = certificates
        self.certificate_combo.configure(values=[c.label for c in certificates])
        self.certificate_value.set("")
        for index, cert in enumerate(certificates):
            if cert.thumbprint == self.settings.certificate_thumbprint:
                self.certificate_combo.current(index)
                break
        self.status.set(f"Tìm thấy {len(certificates)} chứng thư có khóa riêng. Chọn đúng chứng thư của bạn.")

    def _certificate(self):
        index = self.certificate_combo.current()
        return self.certificates[index] if 0 <= index < len(self.certificates) else None

    def save(self):
        cert = self._certificate()
        try:
            updated = replace(self.settings,
                              certificate_thumbprint=cert.thumbprint if cert else "",
                              automatic_pin=self.automatic_pin.get())
            save_settings(updated)
            self.settings = updated
        except (OSError, ValueError) as exc:
            messagebox.showerror("Lỗi lưu cài đặt", str(exc), parent=self.root)
            return
        self.status.set("Đã lưu lựa chọn chứng thư và chế độ nhập PIN. Không lưu PIN.")

    def sign_selected(self, *, continuous=False):
        if self.busy:
            return
        records = [self.records[i] for i in self.tree.selection() if i in self.records]
        if not records and not continuous:
            return
        automatic = self.automatic_pin.get()
        certificate = self._certificate()
        pin = self.pin.get() if automatic else ""
        if automatic and (certificate is None or not pin):
            messagebox.showwarning("Thiếu thông tin", "Chọn chứng thư và nhập PIN, hoặc tắt chế độ tự nhập PIN.", parent=self.root)
            return
        mode = "Tool sẽ tự chọn chứng thư và gửi PIN đúng một lần cho mỗi hồ sơ." if automatic else "Bạn tự chọn chứng thư/nhập PIN khi USB Token yêu cầu."
        scope = (
            "Quét tối đa 100 hồ sơ chưa ký theo thứ tự API, ký lần lượt, rồi tự quét đợt 100 tiếp theo. "
            "Chạy đến khi hết hồ sơ mới, gặp lỗi hoặc bạn bấm Dừng. "
            "Hồ sơ đã thao tác trong phiên sẽ không được ký lại."
            if continuous else f"Bạn sắp gửi lệnh ký cho {len(records)} hồ sơ đã chọn.")
        if not messagebox.askyesno("Xác nhận ký số", f"{scope}\n\n{mode}\n\nHãy kiểm tra đúng hồ sơ và chứng thư. Tiếp tục?", parent=self.root):
            return
        self.stop_event.clear()
        self.signing = True
        def work():
            browser = self._ensure_browser()
            token = AutomatedTokenPrompt(log=self.log) if automatic else ManualTokenPrompt(log=self.log)
            signer = BatchSigner(browser, token, log=self.log)
            if continuous:
                return signer.run_pending(certificate=certificate, pin=pin, stop_event=self.stop_event)
            return signer.run(records, certificate=certificate, pin=pin, stop_event=self.stop_event)
        self._submit("Đang thực hiện các bước ký…", work, self._signed)

    def _signed(self, result):
        self.pin.set("")
        # Invalidate the snapshot after any batch: never sign the same selection twice.
        self._clear_records()
        text = f"Đã thử {result.attempted}; hoàn tất thao tác {result.completed_steps}; lỗi {result.failed}."
        if result.stopped:
            text += " Đã dừng."
        text += " Kiểm tra trạng thái trên hệ thống và quét lại trước đợt ký mới."
        self.status.set(text)
        self._append_log(text)
        if result.error:
            self._append_log(result.error)
        if result.needs_review and not self.closing:
            messagebox.showwarning("Cần kiểm tra hồ sơ", result.error or "Có hồ sơ chưa xác định kết quả. Hãy kiểm tra trên website trước khi ký lại. Không tự động thử lại.", parent=self.root)

    def _clear_records(self):
        self.records.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._selection_changed()

    def stop(self):
        self.stop_event.set()
        self.status.set("Đã yêu cầu dừng. Hoàn tất/xử lý hồ sơ đang mở trước khi dừng; không tự hủy chữ ký đã gửi.")
        self._update_controls()

    def close(self):
        if self.closing:
            return
        if self.busy:
            if not messagebox.askyesno("Đóng ứng dụng", "Chờ thao tác hiện tại kết thúc rồi đóng? Nếu đang ký, tool sẽ dừng trước hồ sơ tiếp theo.", parent=self.root):
                return
            self.closing = True
            self.stop_event.set()
            self._update_controls()
            self.status.set("Đang chờ thao tác hiện tại kết thúc để đóng an toàn…")
        else:
            self.closing = True
            self._finish_close()

    def _finish_close(self):
        self.pin.set("")
        for timer in (self._poll_after, self._autoload_after):
            if timer is not None:
                self.after_cancel(timer)
        if self.browser is not None:
            self.executor.submit(self.browser.disconnect)
        self.executor.shutdown(wait=False, cancel_futures=False)
        self.destroyed = True
        self.root.destroy()


def main():
    root = tk.Tk()
    SignerApp(root)
    root.mainloop()
