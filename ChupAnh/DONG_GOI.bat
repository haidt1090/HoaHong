@echo off
cd /d "%~dp0"
py -3.12 -c "import struct; assert struct.calcsize('P') == 8" >nul 2>&1
if errorlevel 1 goto fallback
py -3.12 setup_environment.py --target .build-venv
if errorlevel 1 goto fail
goto build
:fallback
python -c "import sys,struct; assert sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8" >nul 2>&1
if errorlevel 1 goto fail
python setup_environment.py --target .build-venv
if errorlevel 1 goto fail
:build
.build-venv\Scripts\python.exe build_windows.py --skip-install
if errorlevel 1 goto fail
echo Hoan tat: dist\ChupAnh-Windows.zip
if not defined CHUPANH_NONINTERACTIVE pause
exit /b 0
:fail
echo Dong goi that bai. Can Windows x64, Python 3.12 x64 va Internet. Xem thong bao ben tren.
if not defined CHUPANH_NONINTERACTIVE pause
exit /b 1
