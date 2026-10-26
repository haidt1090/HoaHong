import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts import windows_env as launcher


class RuntimeTests(unittest.TestCase):
    def test_accepts_python_315_without_requiring_312(self):
        for version in [(3, 10), (3, 12), (3, 13), (3, 14), (3, 15)]:
            self.assertTrue(launcher.compatible(version, 64))
        for version, bits in [((3, 15), 32), ((3, 9), 64), ((3, 16), 64)]:
            self.assertFalse(launcher.compatible(version, bits))

    def test_reuses_venv315_from_previous_instructions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            expected = launcher.environment_python(root / ".venv315")

            def inspect(executable):
                return (
                    {"version": [3, 15], "bits": 64} if executable == expected else None
                )

            with patch.object(launcher, "probe_python", side_effect=inspect):
                self.assertEqual(launcher.choose_environment(root)[0], expected)

    def test_invalid_interpreter_or_missing_runtime_is_not_selected(self):
        with patch.object(launcher.subprocess, "run", side_effect=FileNotFoundError):
            self.assertIsNone(launcher.probe_python("missing-python"))
        completed = subprocess.CompletedProcess(
            [], 0, stdout='{"version":[3,15],"bits":32}', stderr=""
        )
        with patch.object(launcher.subprocess, "run", return_value=completed):
            self.assertIsNone(launcher.probe_python("32-bit-python"))

    def test_repair_preserves_old_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old = root / ".venv"
            old.mkdir()
            (old / "keep.txt").write_text("old environment")

            def create(*args, **kwargs):
                (root / ".venv").mkdir()

            with patch.object(
                launcher.subprocess, "run", side_effect=create
            ), patch.object(
                launcher, "probe_python", return_value={"version": [3, 15], "bits": 64}
            ):
                executable, _ = launcher.create_environment(
                    root, creator="python315.exe"
                )
            self.assertEqual(executable, launcher.environment_python(root / ".venv"))
            backups = list(root.glob(".venv-backup-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / "keep.txt").read_text(), "old environment")

    def test_run_uses_selected_environment_and_does_not_install_when_ready(self):
        executable = Path("existing-venv315/python.exe")
        with patch.object(
            launcher,
            "choose_environment",
            return_value=(executable, {"version": [3, 15], "bits": 64}),
        ), patch.object(
            launcher, "check_runtime_dependencies", return_value=True
        ), patch.object(
            launcher, "execute"
        ) as execute, patch.object(
            launcher, "setup"
        ) as setup:
            self.assertEqual(launcher.main(["run"]), 0)
            execute.assert_called_once_with(executable, launcher.ROOT / "app.py")
            setup.assert_not_called()

    def test_install_failure_preserves_underlying_exit_code(self):
        with patch.object(
            launcher,
            "choose_environment",
            return_value=(Path("python.exe"), {"version": [3, 15], "bits": 64}),
        ), patch.object(
            launcher,
            "setup",
            side_effect=subprocess.CalledProcessError(42, ["pip", "install"]),
        ):
            self.assertEqual(launcher.main(["setup"]), 42)

    def test_build_cannot_report_success_without_exe(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(launcher, "ROOT", Path(folder)), patch.object(
                launcher, "WINDOWS", True
            ), patch.object(
                launcher,
                "choose_environment",
                return_value=(Path("python.exe"), {"version": [3, 15], "bits": 64}),
            ), patch.object(
                launcher, "setup"
            ), patch.object(
                launcher, "execute"
            ):
                self.assertEqual(launcher.main(["build"]), 1)


if __name__ == "__main__":
    unittest.main()
