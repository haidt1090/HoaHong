"""Shared setup/run/build launcher. Never changes the user's system Python."""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = os.name == "nt"
MIN_VERSION = (3, 10)
MAX_VERSION = (3, 15)
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
            [str(executable), "-c", PROBE],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        details = json.loads(result.stdout)
        return details if compatible(details["version"], details["bits"]) else None
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return None


def choose_environment(root=ROOT):
    for name in (".venv", ".venv315"):
        executable = environment_python(Path(root) / name)
        details = probe_python(executable)
        if details:
            return executable, details
    return None


def execute(executable, *arguments):
    subprocess.run([str(executable), *map(str, arguments)], cwd=ROOT, check=True)


def create_environment(root=ROOT, creator=sys.executable):
    root = Path(root)
    folder = root / ".venv"
    if folder.exists():
        backup = folder.with_name(
            ".venv-backup-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        )
        folder.rename(backup)
        print(f"Đã giữ môi trường cũ tại {backup.name}; không xóa dữ liệu.", flush=True)
    subprocess.run([str(creator), "-m", "venv", str(folder)], cwd=root, check=True)
    executable = environment_python(folder)
    details = probe_python(executable)
    if not details:
        raise RuntimeError("Không tạo được Python 64-bit hợp lệ trong .venv.")
    return executable, details


def check_runtime_dependencies(executable):
    imports = "import tkinter, openpyxl"
    if WINDOWS:
        imports += "; import win32print, win32com.client, pythoncom"
    result = subprocess.run(
        [str(executable), "-c", imports], cwd=ROOT, capture_output=True, text=True
    )
    return result.returncode == 0


def setup(executable, build=False):
    print("Kiểm tra Tcl/Tk…", flush=True)
    try:
        execute(executable, "-c", "import tkinter")
    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            "Python thiếu Tcl/Tk. Mở bộ cài Python và bật Tcl/Tk; không cần đổi phiên bản."
        ) from error
    print("Cài/cập nhật thư viện đúng phiên bản…", flush=True)
    execute(
        executable,
        "-m",
        "pip",
        "install",
        "-r",
        ROOT / ("requirements-build.txt" if build else "requirements.txt"),
    )
    execute(executable, "-m", "pip", "check")
    if not check_runtime_dependencies(executable):
        raise RuntimeError(
            "Chưa nạp được thư viện giao diện/Excel/Windows. Xem lỗi pip phía trên, rồi chạy lại CaiDat.cmd."
        )


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["setup", "run", "build"])
    args = parser.parse_args(argv)
    if not compatible(sys.version_info[:2], struct.calcsize("P") * 8):
        print(
            "Cần Python 64-bit 3.10–3.15. Không cần cài thêm 3.12 nếu đã có 3.15.",
            file=sys.stderr,
        )
        return 1
    try:
        selected = choose_environment()
        created = selected is None
        executable, details = selected or create_environment()
        version = ".".join(map(str, details["version"]))
        print(
            f'InBaoCao dùng Python {version} {details["bits"]}-bit: {executable}',
            flush=True,
        )
        if (
            args.mode in ("setup", "build")
            or created
            or not check_runtime_dependencies(executable)
        ):
            setup(executable, build=args.mode == "build")
        if args.mode == "setup":
            print("Cài đặt xong. Mở CHAY_PHAN_MEM.bat để chạy.", flush=True)
        elif args.mode == "run":
            execute(executable, ROOT / "app.py")
        else:
            if not WINDOWS:
                raise RuntimeError("Cần build Windows EXE trên máy Windows.")
            execute(executable, "-m", "unittest", "discover", "-s", "tests", "-v")
            execute(
                executable,
                "-m",
                "PyInstaller",
                "--noconfirm",
                "--clean",
                ROOT / "InBaoCao.spec",
            )
            output = ROOT / "dist" / "InBaoCao.exe"
            if not output.is_file() or output.stat().st_size == 0:
                raise RuntimeError(
                    "Build kết thúc nhưng chưa tìm thấy dist/InBaoCao.exe."
                )
            print(f"Đã đóng gói thành công: {output}", flush=True)
            os.startfile(str(output.parent))
        return 0
    except subprocess.CalledProcessError as error:
        print(
            f"Tác vụ chưa hoàn thành (mã lỗi {error.returncode}). Xem lệnh và thông báo phía trên. Không cần gỡ Python.",
            file=sys.stderr,
        )
        return error.returncode if 0 < error.returncode < 256 else 1
    except (OSError, RuntimeError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
