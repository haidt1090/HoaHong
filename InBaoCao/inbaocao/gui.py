from __future__ import annotations
import queue
import shutil
import tempfile
import threading
import sys
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from .core import (
    ExcelData,
    FIELDS,
    auto_mapping,
    aliases_for,
    normalize,
    merge_docx,
    row_values,
    scan_tokens,
)
from . import __version__
from .storage import Library
from .printing import open_document, list_printers, print_batch

BLANK = "(Để trống / giá trị chung)"
FONT = "Segoe UI" if sys.platform == "win32" else "DejaVu Sans"


class App:
    def __init__(self, root, library=None):
        self.root = root
        self.library = library or Library()
        self.excel = None
        self.headers = []
        self.rows = []
        self.checked = set()
        self.map_vars = {}
        self.constant_vars = {}
        self.events = queue.Queue()
        self.busy = False
        self.cancel = threading.Event()
        self.preview_dirs = []
        self.poll_timer = None
        self.template_var = tk.StringVar()
        self.sheet_var = tk.StringVar()
        self.header_var = tk.IntVar(value=1)
        self.printer_var = tk.StringVar()
        self.print_summary = tk.StringVar(
            value="Chưa chọn mẫu • Chưa có danh sách • Chưa chọn máy in"
        )
        self.print_status = tk.StringVar(
            value="Chưa bắt đầu in. Xem thử một người là tùy chọn."
        )
        self.job_kind = None
        self.job_done = 0
        self.job_total = 0
        self.print_compact = None
        self.status = tk.StringVar(
            value="Nhập mẫu Word có keyword → chọn Excel → kiểm tra 1 người → in hàng loạt."
        )
        self.count = tk.StringVar(value="Chưa nhập danh sách")
        self.filename = tk.StringVar(value="Chưa chọn file Excel")
        self.template_info = tk.StringVar(
            value="Keyword ví dụ: $hovaten, $gt, $ngaysinh, $cccd, $so"
        )
        self._build()
        self.printer_var.trace_add("write", lambda *_: self.update_print_info())
        self.template_var.trace_add("write", lambda *_: self.update_print_info())
        self.refresh_templates()
        self.refresh_printers()
        self.update_print_info()
        self.poll_timer = self.root.after(100, self.poll)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    @property
    def template(self):
        index = self.template_combo.current()
        return (
            self.library.templates[index]
            if 0 <= index < len(self.library.templates)
            else None
        )

    def _build(self):
        r = self.root
        r.title(f"InBaoCao · Word & Excel · Python {__version__}")
        width = min(1320, max(960, r.winfo_screenwidth() - 80))
        height = min(880, max(620, r.winfo_screenheight() - 100))
        r.geometry(f"{width}x{height}")
        r.minsize(960, 620)
        style = ttk.Style(r)
        style.theme_use("clam")
        style.configure(".", font=(FONT, 10), background="#f5f7f8")
        style.configure("TButton", padding=(10, 7))
        style.configure(
            "Accent.TButton",
            background="#147c64",
            foreground="white",
            font=(FONT, 10, "bold"),
        )
        style.map(
            "Accent.TButton",
            background=[("active", "#09614c"), ("disabled", "#a2bcb3")],
        )
        style.configure(
            "Treeview", rowheight=29, background="white", fieldbackground="white"
        )
        style.configure("Treeview.Heading", font=(FONT, 9, "bold"), padding=7)
        header = tk.Frame(r, bg="#147c64", padx=22, pady=15)
        header.pack(fill="x")
        tk.Label(
            header, text="InBaoCao", font=(FONT, 23, "bold"), bg="#147c64", fg="white"
        ).pack(side="left")
        tk.Label(
            header,
            text="WORD + EXCEL  •  IN SỔ KHÁM SỨC KHỎE",
            font=(FONT, 10),
            bg="#147c64",
            fg="#d6eee6",
        ).pack(side="left", padx=24)
        ttk.Button(header, text="Hướng dẫn keyword", command=self.help).pack(
            side="right"
        )
        body = ttk.Frame(r, padding=16)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)
        self.workspace = ttk.Frame(body)
        self.workspace.grid(row=0, column=0, sticky="nsew")
        self.workspace.columnconfigure(0, weight=1)
        self.workspace.rowconfigure(1, weight=1)
        top = ttk.Frame(self.workspace)
        self.setup_panel = top
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)
        left = ttk.LabelFrame(top, text="1. Mẫu Word (.docx)", padding=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.template_combo = ttk.Combobox(
            left, textvariable=self.template_var, state="readonly"
        )
        self.template_combo.pack(fill="x")
        self.template_combo.bind("<<ComboboxSelected>>", lambda _: self.show_mapping())
        line = ttk.Frame(left)
        line.pack(fill="x", pady=8)
        self.import_button = ttk.Button(
            line, text="Nhập mẫu Word", command=self.import_template
        )
        self.import_button.pack(side="left")
        ttk.Button(line, text="Đặt tên", command=self.rename_template).pack(
            side="left", padx=4
        )
        ttk.Button(line, text="Xóa mẫu", command=self.delete_template).pack(side="left")
        ttk.Button(line, text="Đọc lại keyword", command=self.rescan).pack(side="right")
        line2 = ttk.Frame(left)
        line2.pack(fill="x")
        ttk.Button(line2, text="Mở mẫu để sửa", command=self.edit_template).pack(
            side="left"
        )
        ttk.Button(line2, text="Sao lưu kho mẫu", command=self.backup).pack(
            side="left", padx=4
        )
        ttk.Button(line2, text="Khôi phục ZIP", command=self.restore).pack(side="left")
        ttk.Label(left, textvariable=self.template_info, wraplength=560).pack(
            anchor="w", pady=(9, 0)
        )
        right = ttk.LabelFrame(top, text="2. Danh sách người khám (.xlsx)", padding=12)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        row = ttk.Frame(right)
        row.pack(fill="x")
        self.excel_button = ttk.Button(
            row, text="Chọn file Excel", command=self.import_excel
        )
        self.excel_button.pack(side="left")
        ttk.Label(row, textvariable=self.filename, wraplength=340).pack(
            side="left", padx=10
        )
        selectors = ttk.Frame(right)
        selectors.pack(fill="x", pady=12)
        ttk.Label(selectors, text="Trang tính").pack(side="left")
        self.sheet_combo = ttk.Combobox(
            selectors, textvariable=self.sheet_var, state="readonly", width=24
        )
        self.sheet_combo.pack(side="left", padx=8)
        self.sheet_combo.bind("<<ComboboxSelected>>", lambda _: self.select_sheet())
        ttk.Label(selectors, text="Dòng tiêu đề").pack(side="left")
        ttk.Spinbox(
            selectors, from_=1, to=10000, width=5, textvariable=self.header_var
        ).pack(side="left", padx=8)
        ttk.Button(selectors, text="Đọc lại", command=self.read_excel).pack(side="left")
        ttk.Label(
            right,
            text="Tự tìm dòng tiêu đề, bỏ qua hoa thường, dấu tiếng Việt và (*).\nTrường thiếu để trống; không bắt buộc thông tin người khám.",
        ).pack(anchor="w")
        notebook = ttk.Notebook(self.workspace)
        notebook.grid(row=1, column=0, sticky="nsew", pady=(10, 10))
        listing = ttk.Frame(notebook, padding=10)
        mapping = ttk.Frame(notebook, padding=10)
        notebook.add(listing, text="Danh sách & chọn người in")
        notebook.add(mapping, text="Liên kết keyword với cột Excel")
        toolbar = ttk.Frame(listing)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(
            toolbar, text="Chọn tất cả", command=lambda: self.select_all(True)
        ).pack(side="left")
        ttk.Button(
            toolbar, text="Bỏ chọn tất cả", command=lambda: self.select_all(False)
        ).pack(side="left", padx=5)
        ttk.Label(toolbar, textvariable=self.count).pack(side="left", padx=15)
        ttk.Label(
            toolbar, text="Bấm ô [x] để chọn/bỏ chọn; chọn dòng để xem thử."
        ).pack(side="right")
        frame = ttk.Frame(listing)
        frame.pack(fill="both", expand=True)
        columns = ("check", "number", "name", "gender", "birth", "employee", "identity")
        self.tree = ttk.Treeview(
            frame, columns=columns, show="headings", selectmode="browse"
        )
        headings = [
            "IN",
            "STT",
            "HỌ VÀ TÊN",
            "GIỚI TÍNH",
            "NGÀY SINH",
            "MÃ NHÂN VIÊN",
            "CCCD",
        ]
        for col, label, width in zip(
            columns, headings, [50, 65, 260, 90, 120, 130, 180]
        ):
            self.tree.heading(col, text=label)
            self.tree.column(
                col, width=width, minwidth=45, stretch=col in ["name", "identity"]
            )
        self.tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind("<Button-1>", self.toggle_row)
        self.tree.bind("<Double-1>", lambda _: self.preview())
        ttk.Label(
            mapping,
            text="Mẫu Word quyết định bố cục, cỡ giấy và vị trí chữ. Một keyword có thể dùng ở nhiều vị trí.",
        ).pack(anchor="w")
        map_toolbar = ttk.Frame(mapping)
        map_toolbar.pack(fill="x", pady=8)
        ttk.Button(
            map_toolbar,
            text="Tự liên kết lại",
            command=lambda: self.show_mapping(force=True),
        ).pack(side="left")
        ttk.Button(map_toolbar, text="Lưu liên kết", command=self.save_mapping).pack(
            side="left", padx=6
        )
        ttk.Label(
            map_toolbar, text="Không có cột? Để trống hoặc nhập giá trị chung bên phải."
        ).pack(side="left", padx=8)
        canvas = tk.Canvas(mapping, highlightthickness=0, bg="#f5f7f8")
        yscroll = ttk.Scrollbar(mapping, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=yscroll.set)
        yscroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self.mapping_frame = ttk.Frame(canvas)
        window = canvas.create_window((0, 0), window=self.mapping_frame, anchor="nw")
        self.mapping_frame.bind(
            "<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.bind(
            "<Configure>", lambda event: canvas.itemconfigure(window, width=event.width)
        )
        self.print_panel = ttk.LabelFrame(
            body, text="3. Máy in và điều khiển in", padding=(10, 8)
        )
        self.print_panel.grid(row=1, column=0, sticky="ew")
        self.print_panel.columnconfigure(0, weight=1)
        printer_line = ttk.Frame(self.print_panel)
        printer_line.grid(row=0, column=0, sticky="ew")
        printer_line.columnconfigure(1, weight=1)
        ttk.Label(printer_line, text="Máy in").grid(row=0, column=0, sticky="w")
        self.printer_combo = ttk.Combobox(
            printer_line, textvariable=self.printer_var, state="readonly", width=30
        )
        self.printer_combo.grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(
            printer_line, text="Tải lại máy in", command=self.refresh_printers
        ).grid(row=0, column=2)
        self.print_summary_label = ttk.Label(
            self.print_panel,
            textvariable=self.print_summary,
            wraplength=1100,
        )
        self.print_summary_label.grid(row=1, column=0, sticky="ew", pady=(5, 5))
        buttons = ttk.Frame(self.print_panel)
        self.print_buttons = buttons
        buttons.grid(row=2, column=0, sticky="ew")
        buttons.columnconfigure(2, weight=1)
        self.preview_button = ttk.Button(
            buttons, text="Xem thử 1 người", command=self.preview
        )
        self.preview_button.grid(row=0, column=0, sticky="nsew")
        self.export_button = ttk.Button(buttons, text="Xuất Word", command=self.export)
        self.export_button.grid(row=0, column=1, sticky="nsew", padx=6)
        self.print_button = ttk.Button(
            buttons,
            text="BẮT ĐẦU IN HÀNG LOẠT",
            style="Accent.TButton",
            command=self.print_all,
        )
        self.print_button.grid(row=0, column=2, sticky="nsew", padx=(0, 6))
        self.stop_button = ttk.Button(
            buttons, text="Dừng sau sổ hiện tại", command=self.stop, state="disabled"
        )
        self.stop_button.grid(row=0, column=3, sticky="nsew")
        buttons.bind("<Configure>", self.fit_print_buttons)
        self.print_status_label = ttk.Label(
            self.print_panel,
            textvariable=self.print_status,
            wraplength=1100,
        )
        self.print_status_label.grid(row=3, column=0, sticky="ew", pady=(5, 3))
        self.progress = ttk.Progressbar(self.print_panel, mode="determinate")
        self.progress.grid(row=4, column=0, sticky="ew")
        self.status_label = ttk.Label(body, textvariable=self.status, wraplength=1100)
        self.status_label.grid(row=2, column=0, sticky="ew", pady=(5, 0))
        body.bind("<Configure>", self.fit_print_labels)

    def fit_print_buttons(self, event):
        controls = (
            self.preview_button,
            self.export_button,
            self.print_button,
            self.stop_button,
        )
        required = sum(button.winfo_reqwidth() for button in controls) + 24
        compact = event.width < required
        if compact == self.print_compact:
            return
        self.print_compact = compact
        for button in controls:
            button.grid_forget()
        for column in range(4):
            self.print_buttons.columnconfigure(column, weight=0)
        if compact:
            for column in range(3):
                self.print_buttons.columnconfigure(column, weight=1)
            self.print_button.grid(
                row=0, column=0, columnspan=3, sticky="nsew", padx=0, pady=(0, 5)
            )
            for column, button in enumerate(
                (self.preview_button, self.export_button, self.stop_button)
            ):
                button.grid(
                    row=1,
                    column=column,
                    columnspan=1,
                    sticky="nsew",
                    padx=(0, 5) if column < 2 else 0,
                    pady=0,
                )
        else:
            self.print_buttons.columnconfigure(2, weight=1)
            for column, button in enumerate(controls):
                button.grid(
                    row=0,
                    column=column,
                    columnspan=1,
                    sticky="nsew",
                    padx=(0, 6) if column < 3 else 0,
                    pady=0,
                )

    def fit_print_labels(self, event):
        width = max(240, event.width - 32)
        for label in (
            self.print_summary_label,
            self.print_status_label,
            self.status_label,
        ):
            label.configure(wraplength=width)

    def update_print_info(self):
        item = self.template
        template = item["name"] if item else "Chưa chọn mẫu"
        printer = self.printer_var.get() or "Chưa chọn máy in"
        self.print_summary.set(
            f"Mẫu: {template} • Đã chọn {len(self.checked)}/{len(self.rows)} người • Máy in: {printer}"
        )

    def fail(self, error):
        self.status.set(str(error))
        messagebox.showerror("InBaoCao", str(error), parent=self.root)

    def guard(self, callback):
        try:
            return callback()
        except Exception as error:
            self.fail(error)

    def refresh_templates(self, selected=None):
        self.template_combo.configure(
            values=[t["name"] for t in self.library.templates]
        )
        if self.library.templates:
            index = next(
                (
                    i
                    for i, t in enumerate(self.library.templates)
                    if t["id"] == selected
                ),
                0,
            )
            self.template_combo.current(index)
        else:
            self.template_var.set("")
        self.show_mapping()

    def import_template(self):
        if self.busy:
            return
        filename = filedialog.askopenfilename(
            title="Chọn mẫu Word có keyword", filetypes=[("Word DOCX", "*.docx")]
        )
        if filename:

            def action():
                item = self.library.add(filename)
                self.refresh_templates(item["id"])
                self.status.set(
                    f"Đã lưu mẫu {item['name']} — {len(item['tokens'])} keyword. Mẫu gốc không bị sửa."
                )

            self.guard(action)

    def rename_template(self):
        item = self.template
        if not item:
            return
        name = simpledialog.askstring(
            "Đặt tên mẫu", "Tên mẫu:", initialvalue=item["name"], parent=self.root
        )
        if name and name.strip():
            item["name"] = name.strip()
            self.guard(self.library.save)
            self.refresh_templates(item["id"])

    def delete_template(self):
        item = self.template
        if (
            item
            and not self.busy
            and messagebox.askyesno(
                "Xóa mẫu", f"Xóa mẫu {item['name']} khỏi kho? File gốc không bị xóa."
            )
        ):
            self.guard(lambda: self.library.delete(item))
            self.refresh_templates()

    def edit_template(self):
        if self.busy:
            return
        if self.template:
            self.guard(lambda: open_document(self.library.file(self.template)))

    def rescan(self):
        item = self.template
        if not item:
            return

        def action():
            item["tokens"] = scan_tokens(self.library.file(item))
            self.library.save()
            self.show_mapping()
            self.status.set(
                "Đã đọc lại keyword. Hãy lưu file trong Word trước khi đọc lại."
            )

        self.guard(action)

    def show_mapping(self, force=False):
        for widget in self.mapping_frame.winfo_children():
            widget.destroy()
        self.map_vars = {}
        self.constant_vars = {}
        item = self.template
        if not item:
            self.template_info.set("Nhập Word có $hovaten, $gt, $ngaysinh… để bắt đầu.")
            return
        self.template_info.set(
            f"{len(item['tokens'])} keyword • giữ nguyên bố cục/cỡ giấy của Word • trường thiếu để trống"
        )
        suggested = auto_mapping(item["tokens"], self.headers)
        for col, text in enumerate(
            ["KEYWORD TRONG WORD", "CỘT EXCEL", "GIÁ TRỊ CHUNG (TÙY CHỌN)"]
        ):
            ttk.Label(self.mapping_frame, text=text, font=(FONT, 9, "bold")).grid(
                row=0, column=col, sticky="w", padx=8, pady=9
            )
        for index, token in enumerate(item["tokens"], 1):
            saved = item.get("mapping", {}).get(token, "")
            current = (
                suggested.get(token, "")
                if force
                else next(
                    (
                        h
                        for h in self.headers
                        if normalize(h) == normalize(saved) and saved
                    ),
                    suggested.get(token, ""),
                )
            )
            var = tk.StringVar(value=current or BLANK)
            constant = tk.StringVar(value=item.get("constants", {}).get(token, ""))
            self.map_vars[token] = var
            self.constant_vars[token] = constant
            ttk.Label(self.mapping_frame, text=token).grid(
                row=index, column=0, sticky="w", padx=8, pady=6
            )
            combo = ttk.Combobox(
                self.mapping_frame,
                textvariable=var,
                values=[BLANK, *self.headers],
                state="readonly",
                width=40,
            )
            combo.grid(row=index, column=1, sticky="ew", padx=8, pady=6)
            entry = ttk.Entry(self.mapping_frame, textvariable=constant, width=40)
            entry.grid(row=index, column=2, sticky="ew", padx=8, pady=6)

            def changed(event=None, entry=entry, var=var):
                entry.configure(state="normal" if var.get() == BLANK else "disabled")
                if event is not None:
                    self.render_rows()

            combo.bind("<<ComboboxSelected>>", changed)
            changed()
        self.mapping_frame.columnconfigure(1, weight=1)
        self.mapping_frame.columnconfigure(2, weight=1)
        self.render_rows()

    def mapping(self):
        return {
            t: ("" if v.get() == BLANK else v.get()) for t, v in self.map_vars.items()
        }

    def constants(self):
        return {t: v.get() for t, v in self.constant_vars.items()}

    def save_mapping(self):
        if self.template:
            self.template["mapping"] = self.mapping()
            self.template["constants"] = self.constants()
            self.guard(self.library.save)
            self.render_rows()
            self.status.set("Đã lưu liên kết cho mẫu hiện tại.")

    def import_excel(self):
        if self.busy:
            return
        filename = filedialog.askopenfilename(
            title="Chọn danh sách người khám", filetypes=[("Excel XLSX", "*.xlsx")]
        )
        if not filename:
            return

        def work():
            data = ExcelData(filename)
            try:
                sheet = data.sheets[0]
                header = data.guess_header(sheet)
                headers, rows = data.read(sheet, header)
                self.events.put(
                    ("excel", (data, sheet, header, headers, rows, Path(filename).name))
                )
            except Exception:
                data.close()
                raise

        self.start(work, "Đang đọc Excel…")

    def select_sheet(self):
        if self.excel and not self.busy:
            self.header_var.set(self.excel.guess_header(self.sheet_var.get()))
            self.read_excel()

    def read_excel(self):
        if not self.excel or self.busy:
            return

        def action():
            headers, rows = self.excel.read(self.sheet_var.get(), self.header_var.get())
            self.headers, self.rows = headers, rows
            self.checked = set(range(len(rows)))
            self.show_mapping()

        self.guard(action)

    def render_rows(self):
        if not hasattr(self, "tree"):
            return
        old = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        default = auto_mapping(
            ["$so", "$hovaten", "$gt", "$ngaysinh", "$manv", "$cccd"], self.headers
        )
        columns = ["$so", "$hovaten", "$gt", "$ngaysinh", "$manv", "$cccd"]
        display_constants = {}
        current_mapping, current_constants = self.mapping(), self.constants()
        for target in columns:
            for token in self.map_vars:
                if normalize(target.lstrip("$")) in {
                    normalize(a) for a in aliases_for(token)
                }:
                    default[target] = current_mapping.get(token, "")
                    display_constants[target] = current_constants.get(token, "")
                    break
        for i, row in enumerate(self.rows):
            values = row_values(columns, row, default, display_constants)
            self.tree.insert(
                "",
                "end",
                iid=str(i),
                values=[
                    "[x]" if i in self.checked else "[ ]",
                    values["$so"] or str(i + 1),
                    *[values[t] for t in columns[1:]],
                ],
            )
        if old and self.tree.exists(old[0]):
            self.tree.selection_set(old)
        self.update_count()

    def toggle_row(self, event):
        if self.busy:
            return
        item = self.tree.identify_row(event.y)
        if item and self.tree.identify_column(event.x) == "#1":
            index = int(item)
            if index in self.checked:
                self.checked.remove(index)
            else:
                self.checked.add(index)
            self.tree.set(item, "check", "[x]" if index in self.checked else "[ ]")
            self.update_count()

    def update_count(self):
        self.count.set(f"{len(self.rows)} người • Đã chọn {len(self.checked)} người")
        self.update_print_info()

    def select_all(self, checked):
        if not self.busy:
            self.checked = set(range(len(self.rows))) if checked else set()
            self.render_rows()

    def refresh_printers(self):
        if self.busy:
            return
        names, default = list_printers()
        self.printer_combo.configure(values=names)
        self.printer_var.set(
            default if default in names else (names[0] if names else "")
        )

    def prepare(self):
        item = self.template
        if not item:
            raise ValueError("Hãy nhập và chọn mẫu Word trước.")
        if not item["tokens"]:
            raise ValueError("Mẫu chưa có keyword. Mở Word để chèn và đọc lại keyword.")
        if not self.rows:
            raise ValueError("Hãy chọn danh sách Excel có dữ liệu.")
        self.save_mapping()
        return item, self.library.file(item), self.mapping(), self.constants()

    def preview(self):
        if self.busy:
            return

        def action():
            item, source, mapping, constants = self.prepare()
            selection = self.tree.selection()
            index = (
                int(selection[0])
                if selection
                else min(self.checked) if self.checked else 0
            )
            directory = Path(tempfile.mkdtemp(prefix="inbaocao-preview-"))
            self.preview_dirs.append(directory)
            output = directory / "Xem-thu-1-nguoi.docx"
            merge_docx(
                source,
                output,
                row_values(item["tokens"], self.rows[index], mapping, constants),
            )
            open_document(output)
            self.status.set(
                f"Đã mở Word xem thử người ở dòng danh sách {index+1}. In hàng loạt không bắt buộc xem thử."
            )

        self.guard(action)

    def export(self):
        if self.busy:
            return

        def action():
            item, source, mapping, constants = self.prepare()
            chosen = [dict(self.rows[i]) for i in sorted(self.checked)]
            if not chosen:
                raise ValueError("Chọn ít nhất một người.")
            directory = filedialog.askdirectory(title="Chọn nơi lưu Word đã điền")
            if not directory:
                return
            output = Path(tempfile.mkdtemp(prefix="InBaoCao-", dir=directory))
            tokens = list(item["tokens"])

            def work():
                count = 0
                for index, row in enumerate(chosen, 1):
                    if self.cancel.is_set():
                        break
                    merge_docx(
                        source,
                        output / f"So-{index:06d}.docx",
                        row_values(tokens, row, mapping, constants),
                    )
                    count += 1
                    self.events.put(("progress", (count, len(chosen))))
                self.events.put(("message", f"Đã lưu {count} file Word tại {output}"))

            self.start(work, "Đang xuất Word…")

        self.guard(action)

    def print_all(self):
        if self.busy:
            return

        def action():
            item, source, mapping, constants = self.prepare()
            chosen = [dict(self.rows[i]) for i in sorted(self.checked)]
            if not chosen:
                raise ValueError("Chọn ít nhất một người cần in.")
            printer = self.printer_var.get()
            if not printer:
                raise ValueError(
                    "Chọn máy in trước. Bấm Tải lại máy in nếu danh sách trống."
                )
            tokens = list(item["tokens"])

            def work():
                submitted = [0]

                def progress(done, total):
                    submitted[0] = done
                    self.events.put(("progress", (done, total)))

                try:
                    count = print_batch(
                        source,
                        tokens,
                        chosen,
                        mapping,
                        constants,
                        printer,
                        self.cancel,
                        progress,
                    )
                    self.events.put(
                        (
                            "message",
                            f"{'Đã dừng. ' if self.cancel.is_set() else 'Hoàn tất gửi lệnh. '}Đã gửi {count}/{len(chosen)} sổ tới máy in {printer}; không xác nhận giấy đã in.",
                        )
                    )
                except Exception as error:
                    raise RuntimeError(
                        f"Đã gửi {submitted[0]} sổ trước khi dừng. Không in lại những sổ này để tránh trùng.\n{error}"
                    ) from error

            self.start(
                work,
                f"Đang gửi {len(chosen)} sổ tới máy in — không mở từng bản để review…",
                job_kind="print",
                total=len(chosen),
            )

        self.guard(action)

    def start(self, work, message, job_kind=None, total=0):
        self.job_kind = job_kind
        self.job_done = 0
        self.job_total = total
        if job_kind == "print":
            self.print_status.set(
                f"Đang in: đã gửi 0/{total} sổ. Không cần review từng người."
            )
        self.busy = True
        self.cancel.clear()
        self.status.set(message)
        self.progress.configure(value=0, maximum=max(total, 1))
        for button in [
            self.import_button,
            self.excel_button,
            self.preview_button,
            self.export_button,
            self.print_button,
        ]:
            button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.template_combo.configure(state="disabled")
        self.sheet_combo.configure(state="disabled")
        self.printer_combo.configure(state="disabled")

        def worker():
            try:
                work()
            except Exception as error:
                self.events.put(("error", str(error)))
            finally:
                self.events.put(("done", None))

        threading.Thread(target=worker, daemon=True).start()

    def stop(self):
        self.cancel.set()
        if self.job_kind == "print":
            self.print_status.set(
                f"Đang dừng sau sổ hiện tại • Đã gửi {self.job_done}/{self.job_total} sổ."
            )
        self.status.set(
            "Đã yêu cầu dừng sau sổ hiện tại. Lệnh đã gửi tới máy in không tự hủy được."
        )

    def poll(self):
        if self.poll_timer is not None:
            try:
                self.root.after_cancel(self.poll_timer)
            except tk.TclError:
                pass
            self.poll_timer = None
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "excel":
                    data, sheet, header, headers, rows, name = value
                    if self.excel:
                        self.excel.close()
                    self.excel = data
                    self.sheet_combo.configure(values=data.sheets)
                    self.sheet_var.set(sheet)
                    self.header_var.set(header)
                    self.filename.set(name)
                    self.headers, self.rows = headers, rows
                    self.checked = set(range(len(rows)))
                    self.show_mapping()
                    self.status.set(
                        f"Đã đọc {len(rows)} người. Dòng tiêu đề: {header}."
                    )
                elif kind == "progress":
                    done, total = value
                    self.job_done, self.job_total = done, total
                    if self.job_kind == "print":
                        self.print_status.set(
                            f"Đang in: đã gửi {done}/{total} sổ tới {self.printer_var.get()}."
                        )
                    self.progress.configure(maximum=max(total, 1), value=done)
                    self.status.set(f"Đã xử lý {done}/{total} người…")
                elif kind == "message":
                    self.status.set(value)
                    if self.job_kind == "print":
                        self.print_status.set(value)
                elif kind == "error":
                    if self.job_kind == "print":
                        self.print_status.set(
                            f"Lỗi in • Đã gửi {self.job_done}/{self.job_total} sổ. {value}"
                        )
                    self.fail(value)
                elif kind == "done":
                    self.busy = False
                    for button in [
                        self.import_button,
                        self.excel_button,
                        self.preview_button,
                        self.export_button,
                        self.print_button,
                    ]:
                        button.configure(state="normal")
                    self.stop_button.configure(state="disabled")
                    self.template_combo.configure(state="readonly")
                    self.sheet_combo.configure(state="readonly")
                    self.printer_combo.configure(state="readonly")
                    self.job_kind = None
        except queue.Empty:
            pass
        self.poll_timer = self.root.after(100, self.poll)

    def backup(self):
        filename = filedialog.asksaveasfilename(
            title="Sao lưu mẫu Word và liên kết",
            defaultextension=".zip",
            initialfile="InBaoCao-kho-mau.zip",
            filetypes=[("ZIP", "*.zip")],
        )
        if filename:
            self.guard(lambda: self.library.backup(filename))
            self.status.set(
                "Đã sao lưu kho mẫu Word. Chép ZIP cùng EXE sang máy mới và chọn Khôi phục ZIP."
            )

    def restore(self):
        if self.busy:
            return
        filename = filedialog.askopenfilename(
            title="Khôi phục kho mẫu Word Python", filetypes=[("ZIP", "*.zip")]
        )
        if filename:

            def action():
                count = self.library.restore(filename)
                self.refresh_templates()
                self.status.set(
                    f"Đã khôi phục {count} mẫu. Không thay thế các mẫu đang có."
                )

            self.guard(action)

    def help(self):
        messagebox.showinfo(
            "Keyword trong Word",
            "Mở mẫu bằng Word, thay các chỗ điền bằng keyword:\n\n"
            + "\n".join(f"${key}  →  {label}" for key, label, _ in FIELDS)
            + "\n\nCó thể dùng keyword riêng như $makham hoặc ${Tên cột Excel}.\nMột keyword có thể xuất hiện nhiều lần, ở bảng/đầu trang/cuối trang.\nNhập mẫu → chọn Excel → chỉnh liên kết ở tab thứ hai.\nGiữ nguyên A3/hướng giấy trong Word. Xem thử 1 người là tùy chọn.\nIn trực tiếp cần Microsoft Word desktop trên Windows, không cần LibreOffice.",
            parent=self.root,
        )

    def close(self):
        if self.busy:
            messagebox.showinfo(
                "Đang xử lý",
                "Bấm Dừng sau sổ hiện tại và đợi tác vụ kết thúc rồi đóng ứng dụng.",
                parent=self.root,
            )
            return
        if self.excel:
            self.excel.close()
        for directory in self.preview_dirs:
            shutil.rmtree(directory, ignore_errors=True)
        if self.poll_timer is not None:
            self.root.after_cancel(self.poll_timer)
            self.poll_timer = None
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        App(root)
    except Exception as error:
        messagebox.showerror("Không mở được InBaoCao", str(error), parent=root)
        root.destroy()
        return
    root.mainloop()
