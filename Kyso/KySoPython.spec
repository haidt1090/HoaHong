# Build on Windows: includes Selenium Manager and native UI Automation imports.
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

base = Path(SPECPATH)
selenium_datas, selenium_binaries, selenium_hidden = collect_all("selenium")
ui_imports = collect_submodules("pywinauto", filter=lambda name: ".unittests" not in name)
a = Analysis(
    [str(base / "app.py")],
    pathex=[str(base)],
    binaries=selenium_binaries,
    datas=selenium_datas,
    hiddenimports=selenium_hidden + ui_imports + ["win32timezone", "comtypes.gen.UIAutomationClient"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="KySoPython", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False, disable_windowed_traceback=False,
)
