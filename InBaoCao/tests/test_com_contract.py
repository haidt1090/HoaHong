"""Check the actual pywin32 no-type-info method generator, without Word/printer."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import MethodType, SimpleNamespace
import threading
import unittest
from unittest.mock import patch

from inbaocao.printing import print_batch

try:
    from win32com.client import build
except ImportError:
    build = None


@unittest.skipIf(build is None, "pywin32 COM generator requires Windows")
class ComContractTests(unittest.TestCase):
    def test_real_pywin32_varargs_wrappers_accept_entire_print_workflow(self):
        calls = []

        class ComObject:
            def __init__(self, commands):
                self.commands = commands
                self._oleobj_ = self
                for index, name in enumerate(commands, 1):
                    entry = SimpleNamespace(
                        desc=None, names=(name,), doc=None, dispid=index,
                    )
                    # Same generator used by dynamic._FlagAsMethod when no
                    # parameter metadata exists. It emits def Method(self,*args).
                    lines = build.DispatchItem().MakeVarArgsFuncMethod(entry, name, 0)
                    namespace = {}
                    exec("\n".join(lines), namespace)
                    setattr(self, name, MethodType(namespace[name], self))

            def Invoke(self, dispid, lcid, flags, result_wanted, *args):
                name = list(self.commands)[dispid - 1]
                calls.append((name, args))
                return self.commands[name](*args)

            def _get_good_object_(self, result, name):
                return result

        def no_result(*args):
            return None

        document = ComObject({"PrintOut": no_result, "Close": no_result})
        documents = ComObject({"Open": lambda *args: document})
        basic = ComObject({"FilePrintSetup": no_result})
        basic._FlagAsMethod = lambda name: None
        word = ComObject({"Quit": no_result})
        word.Documents = documents
        word.WordBasic = basic

        # Reproduce the exact error in the user's screenshot with the real
        # pywin32 generator, rather than a mock accepting arbitrary **kwargs.
        with self.assertRaisesRegex(TypeError, "unexpected keyword argument"):
            basic.FilePrintSetup(Printer="Microsoft Print to PDF")

        progress = []
        with TemporaryDirectory() as directory:
            def merge(source, target, values):
                Path(target).write_bytes(b"test document")

            with patch("inbaocao.printing.merge_docx", side_effect=merge):
                result = print_batch(
                    "unused.docx", [], [{}], {}, {}, "Microsoft Print to PDF",
                    threading.Event(), lambda *args: progress.append(args),
                    dispatch=lambda name: word,
                )
        self.assertEqual(result, 1)
        self.assertEqual(progress, [(1, 1)])
        self.assertEqual([name for name, args in calls],
                         ["FilePrintSetup", "Open", "PrintOut", "Close", "Quit"])
        self.assertEqual(calls[0][1], ("Microsoft Print to PDF", 0, 0, 1))
        self.assertEqual(calls[1][1][1:], (False, True, False))
        self.assertEqual(calls[2][1], (False, False, 0, "", "", "", 0, 1))
        self.assertEqual(calls[3][1], (0,))
        self.assertEqual(calls[4][1], (0,))
