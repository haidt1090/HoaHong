"""Windows Word automation only. No PDF conversion, Electron or LibreOffice."""

from pathlib import Path
from tempfile import TemporaryDirectory
import os
import sys
from .core import merge_docx, row_values


def open_document(filename):
    if sys.platform != "win32":
        raise RuntimeError(
            "Nút xem thử mở Microsoft Word trên Windows. Có thể dùng Xuất Word để lấy file ở hệ điều hành khác."
        )
    os.startfile(str(Path(filename).resolve()))


def list_printers():
    if sys.platform != "win32":
        return [], ""
    try:
        import win32print

        printers = sorted(
            {
                p[2]
                for p in win32print.EnumPrinters(
                    win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
                )
            }
        )
        try:
            default = win32print.GetDefaultPrinter()
        except Exception:
            default = ""
        return printers, default
    except ImportError:
        return [], ""


def print_batch(
    template_file,
    tokens,
    rows,
    mapping,
    constants,
    printer,
    cancel,
    progress,
    dispatch=None,
):
    """One job per person, no review windows. Report submitted jobs, not physical output.

    The isolated Word instance closes every file and quits on success or failure.
    cancel is checked between jobs; already submitted jobs cannot be recalled.
    """
    if dispatch is None and sys.platform != "win32":
        raise RuntimeError(
            "In trực tiếp cần Windows và Microsoft Word bản desktop đã cài."
        )
    pythoncom = None
    if dispatch is None:
        try:
            import pythoncom
            from win32com.client import DispatchEx
        except ImportError as exc:
            raise RuntimeError(
                "Thiếu pywin32. Chạy lại CaiDat.cmd trên máy phát triển."
            ) from exc
        pythoncom.CoInitialize()
        dispatch = DispatchEx
    word = None
    submitted = 0
    try:
        try:
            word = dispatch("Word.Application")
        except Exception as exc:
            raise RuntimeError(
                "Không mở được Microsoft Word. Cần cài và mở Word desktop một lần trước khi in; Word Online không hỗ trợ in trực tiếp."
            ) from exc
        word.Visible = False
        word.DisplayAlerts = 0
        word.AutomationSecurity = (
            3  # Disable macros in the isolated automation instance.
        )
        if printer:
            word.WordBasic.FilePrintSetup(Printer=printer, DoNotSetAsSysDefault=1)
        with TemporaryDirectory(prefix="inbaocao-print-") as work:
            for index, row in enumerate(rows):
                if cancel.is_set():
                    break
                target = Path(work) / f"{index+1:06d}.docx"
                merge_docx(
                    template_file, target, row_values(tokens, row, mapping, constants)
                )
                document = None
                try:
                    document = word.Documents.Open(
                        str(target.resolve()),
                        ReadOnly=True,
                        AddToRecentFiles=False,
                        ConfirmConversions=False,
                    )
                    document.PrintOut(Background=False, Copies=1)
                finally:
                    if document is not None:
                        document.Close(SaveChanges=0)
                submitted += 1
                progress(submitted, len(rows))
                target.unlink(missing_ok=True)
        return submitted
    finally:
        try:
            if word is not None:
                word.Quit(SaveChanges=0)
        finally:
            if pythoncom is not None:
                pythoncom.CoUninitialize()
