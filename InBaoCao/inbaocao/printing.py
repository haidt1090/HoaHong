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
            from win32com.client.dynamic import DumbDispatch
        except ImportError as exc:
            raise RuntimeError(
                "Thiếu pywin32. Chạy lại CaiDat.cmd trên máy phát triển."
            ) from exc
        pythoncom.CoInitialize()
        # Bypass stale/generated makepy wrappers on the user machine.
        def dispatch(name):
            return DumbDispatch(DispatchEx(name)._oleobj_)
    word = None
    submitted = 0
    stage = "khởi động Microsoft Word"
    failed = False
    try:
        try:
            word = dispatch("Word.Application")
        except Exception as exc:
            raise RuntimeError(
                "Không mở được Microsoft Word. Cần cài và mở Word desktop một lần trước khi in; Word Online không hỗ trợ in trực tiếp."
            ) from exc
        stage = "thiết lập Microsoft Word"
        word.Visible = False
        word.DisplayAlerts = 0
        word.AutomationSecurity = (
            3  # Disable macros in the isolated automation instance.
        )
        if printer:
            stage = f"chọn máy in {printer}"
            word_basic = word.WordBasic
            # WordBasic exposes legacy macro commands without reliable type info.
            # pywin32 otherwise reads FilePrintSetup as a property, returning None.
            flag_method = getattr(word_basic, "_FlagAsMethod", None)
            if callable(flag_method):
                flag_method("FilePrintSetup")
            # WordBasic: Printer, Options, Network, DoNotSetAsSysDefault.
            # _FlagAsMethod creates a *args-only pywin32 wrapper: no keywords.
            word_basic.FilePrintSetup(printer, 0, 0, 1)
        with TemporaryDirectory(prefix="inbaocao-print-") as work:
            for index, row in enumerate(rows):
                if cancel.is_set():
                    break
                target = Path(work) / f"{index+1:06d}.docx"
                stage = f"điền mẫu cho người thứ {index + 1}"
                merge_docx(
                    template_file, target, row_values(tokens, row, mapping, constants)
                )
                document = None
                try:
                    stage = f"mở sổ người thứ {index + 1} trong Word"
                    document = word.Documents.Open(
                        str(target.resolve()),
                        False,  # ConfirmConversions
                        True,  # ReadOnly
                        False,  # AddToRecentFiles
                    )
                    stage = f"gửi lệnh in người thứ {index + 1}"
                    # Background, Append, Range, OutputFileName, From, To,
                    # Item (wdPrintDocumentContent=0), Copies. Positional COM
                    # arguments also work when type metadata is unavailable.
                    document.PrintOut(False, False, 0, "", "", "", 0, 1)
                    submitted += 1
                    progress(submitted, len(rows))
                    stage = f"đóng sổ người thứ {index + 1}"
                finally:
                    if document is not None:
                        original_error = sys.exc_info()[0] is not None
                        try:
                            document.Close(0)
                        except Exception:
                            if not original_error:
                                raise
                target.unlink(missing_ok=True)
        return submitted
    except Exception as exc:
        failed = True
        raise RuntimeError(f"Lỗi tại bước {stage}: {exc}") from exc
    finally:
        try:
            if word is not None:
                try:
                    word.Quit(0)
                except Exception:
                    if not failed:
                        raise
        finally:
            if pythoncom is not None:
                pythoncom.CoUninitialize()
