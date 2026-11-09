@echo off
cd /d "%~dp0"
py -3.12 -c "import struct; assert struct.calcsize('P') == 8" >nul 2>&1
if errorlevel 1 goto fallback
py -3.12 setup_environment.py --target .venv
if errorlevel 1 goto fail
goto success
:fallback
python -c "import sys,struct; assert sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8" >nul 2>&1
if errorlevel 1 goto missing
python setup_environment.py --target .venv
if errorlevel 1 goto fail
:success
echo Cai dat DU thu vien thanh cong. Chay MO_UNG_DUNG.bat
if not defined CHUPANH_NONINTERACTIVE pause
exit /b 0
:missing
echo Can cai Python 3.12 x64 tu https://www.python.org/downloads/windows/
echo Python 3.14/3.15 hoac 32-bit khong duoc dung cho moi truong nay.
:fail
echo Cai dat that bai. Xem thong bao ben tren; khong tu cai Visual C++ de sua loi zstandard.
if not defined CHUPANH_NONINTERACTIVE pause
exit /b 1
