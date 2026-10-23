# Build on Windows. No Electron, Node.js, NSIS or LibreOffice bundled.
from pathlib import Path

base = Path(SPECPATH)
a = Analysis(
    [str(base / "app.py")],
    pathex=[str(base)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "win32timezone",
        "win32com.client",
        "pythoncom",
        "pywintypes",
        "win32print",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["numpy", "pandas", "matplotlib", "scipy", "PIL", "pytest", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="InBaoCao",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
