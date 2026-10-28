"""Independent setup/run/build launcher for KySoPython; preserves old environments."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MIN_VERSION = (3, 10)
MAX_VERSION = (3, 15)
WINDOWS = os.name == "nt"
RUN_LOG = None
PROBE = "import json,sys,struct; print(json.dumps({'version':list(sys.version_info[:2]),'bits':struct.calcsize('P')*8}))"


def compatible(version, bits):
    return MIN_VERSION <= tuple(version) <= MAX_VERSION and bits == 64


def environment_python(directory, windows=None):
    if windows is None:
        windows = WINDOWS
    return Path(directory) / ("Scripts/python.exe" if windows else "bin/python")


def probe_python(executable):
    try:
        result = subprocess.run(
            [str(executable), "-c", PROBE], check=True, capture_output=True,
            text=True, timeout=15,
        )
        details = json.loads(result.stdout)
        return details if compatible(details["version"], details["bits"]) else None
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return None


def execute(executable, *arguments):
    command = [str(executable), *map(str, arguments)]
    child_env = os.environ.copy()
    child_env["PYTHONUTF8"] = "1"
    with subprocess.Popen(command, cwd=ROOT, env=child_env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                          errors="replace", bufsize=1) as process:
        for line in process.stdout:
            print(line, end="", flush=True)
            if RUN_LOG is not None:
                RUN_LOG.write(line)
                RUN_LOG.flush()
        code = process.wait()
    if code:
        raise subprocess.CalledProcessError(code, command)


def choose_environment(root=ROOT):
    executable = environment_python(Path(root) / ".venv")
    details = probe_python(executable)
    return (executable, details) if details else None


def create_environment(root=ROOT, creator=sys.executable):
    folder = Path(root) / ".venv"
    if folder.exists():
        backup = folder.with_name(".venv-backup-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
        folder.rename(backup)
        print(f"Đã giữ môi trường cũ tại {backup.name}.", flush=True)
    subprocess.run([str(creator), "-m", "venv", str(folder)], cwd=root, check=True)
    executable = environment_python(folder)
    details = probe_python(executable)
    if not details:
        raise RuntimeError("Không tạo được Python 64-bit hợp lệ trong .venv.")
    return executable, details


def check_runtime_dependencies(executable):
    imports = "import tkinter, selenium; from kyso.gui import SignerApp"
    # UI Automation is optional; importing it must not block manual mode.
    result = subprocess.run([str(executable), "-c", imports], cwd=ROOT, capture_output=True, text=True)
    return result.returncode == 0


def setup(executable, build=False):
    print("Kiểm tra Tcl/Tk…", flush=True)
    try:
        execute(executable, "-c", "import tkinter")
    except subprocess.CalledProcessError as error:
        raise RuntimeError("Python thiếu Tcl/Tk. Bật Tcl/Tk trong bộ cài Python.") from error
    execute(executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "-r",
            ROOT / ("requirements-build.txt" if build else "requirements.txt"))
    execute(executable, "-m", "pip", "check")
    if not check_runtime_dependencies(executable):
        raise RuntimeError("Chưa nạp được thư viện. Kiểm tra lỗi phía trên rồi chạy lại CaiDat.cmd.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["setup", "run", "build"])
    parser.add_argument("--smoke-test", action="store_true", help="Open and close GUI with no browser/token activity")
    args = parser.parse_args(argv)
    if not compatible(sys.version_info[:2], struct.calcsize("P") * 8):
        print("Cần Python 64-bit 3.10–3.15 có Tcl/Tk.", file=sys.stderr)
        return 1
    try:
        if args.mode in ("run", "build") and not WINDOWS:
            raise RuntimeError("Ứng dụng USB Token và bản EXE cần chạy/build trên Windows.")
        selected = choose_environment()
        created = selected is None
        executable, details = selected or create_environment()
        print(f"KySoPython dùng Python {'.'.join(map(str, details['version']))} 64-bit: {executable}", flush=True)
        if args.mode in ("setup", "build") or created or not check_runtime_dependencies(executable):
            setup(executable, build=args.mode == "build")
        if args.mode == "setup":
            print("Cài đặt xong. Mở CHAY_PHAN_MEM.bat để chạy.", flush=True)
        elif args.mode == "run":
            execute(executable, ROOT / "app.py", *(["--smoke-test"] if args.smoke_test else []))
        else:
            execute(executable, "-m", "unittest", "discover", "-s", "tests", "-v")
            execute(executable, "-m", "PyInstaller", "--noconfirm", "--clean", ROOT / "KySoPython.spec")
            output = ROOT / "dist" / "KySoPython.exe"
            if not output.is_file() or output.stat().st_size == 0:
                raise RuntimeError("Build chưa tạo dist/KySoPython.exe.")
            print(f"Đã đóng gói: {output}", flush=True)
        return 0
    except subprocess.CalledProcessError as error:
        print(f"Chưa hoàn thành (mã lỗi {error.returncode}). Xem lỗi phía trên.", file=sys.stderr)
        return error.returncode if 0 < error.returncode < 256 else 1
    except (OSError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1


def logged_main():
    global RUN_LOG
    import tempfile
    root = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "KySoPython" / "diagnostics"
    try:
        root.mkdir(parents=True, exist_ok=True)
        path = root / "last-launch.log"
        stream = path.open("w", encoding="utf-8")
    except OSError:
        return main()  # Logging is optional; never retry a command that already ran.
    try:
        with stream:
            RUN_LOG = stream
            print(f"Nhat ky cai dat/khoi dong: {path}", flush=True)
            stream.write(f"Python {sys.version.split()[0]}, {struct.calcsize('P') * 8}-bit\n")
            stream.flush()
            code = main()
            stream.write(f"\nExit code: {code}\n")
            return code
    finally:
        RUN_LOG = None


if __name__ == "__main__":
    raise SystemExit(logged_main())
