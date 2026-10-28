import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('kyso_launcher', Path(__file__).resolve().parents[1] / 'scripts/windows_env.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class LauncherTests(unittest.TestCase):
    def test_supports_315_but_rejects_32bit_and_unsupported(self):
        self.assertTrue(launcher.compatible((3, 15), 64))
        self.assertFalse(launcher.compatible((3, 15), 32))
        self.assertFalse(launcher.compatible((3, 9), 64))
        self.assertFalse(launcher.compatible((3, 16), 64))

    def test_execute_captures_traceback_and_preserves_failure(self):
        log = io.StringIO()
        with patch.object(launcher, 'RUN_LOG', log), patch('sys.stdout', new_callable=io.StringIO):
            with self.assertRaises(subprocess.CalledProcessError) as error:
                launcher.execute(sys.executable, '-c', 'raise RuntimeError("startup-fixture")')
        self.assertNotEqual(error.exception.returncode, 0)
        self.assertIn('RuntimeError: startup-fixture', log.getvalue())

    def test_manual_mode_dependencies_do_not_import_optional_uia(self):
        with patch.object(launcher.subprocess, 'run') as run:
            run.return_value.returncode = 0
            self.assertTrue(launcher.check_runtime_dependencies(sys.executable))
        self.assertNotIn('pywinauto', run.call_args.args[0][-1])

    def test_runtime_probe_imports_application(self):
        self.assertTrue(launcher.check_runtime_dependencies(sys.executable))

    def test_startup_failure_is_logged_without_retry(self):
        with tempfile.TemporaryDirectory() as directory, \
             patch.dict(launcher.os.environ, {'LOCALAPPDATA': directory}), \
             patch.object(launcher, 'main', return_value=7) as main:
            self.assertEqual(launcher.logged_main(), 7)
            main.assert_called_once()
            self.assertIn('Exit code: 7', (Path(directory)/'KySoPython/diagnostics/last-launch.log').read_text())

    def test_logging_failure_does_not_repeat_main(self):
        with patch.object(launcher.Path, 'mkdir', side_effect=PermissionError), patch.object(launcher, 'main', return_value=9) as main:
            self.assertEqual(launcher.logged_main(), 9)
            main.assert_called_once()
