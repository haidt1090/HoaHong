@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
if exist ".venv\Scripts\python.exe" goto install
py -3.12 -m venv .venv
if errorlevel 1 py -3 -m venv .venv
if errorlevel 1 python -m venv .venv
if errorlevel 1 goto failed
:install
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Cai dat xong. Bam CHAY_PHAN_MEM.bat de mo ung dung.
pause
exit /b 0
:failed
echo Chua cai duoc. Hay cai Python 3.12 64-bit tu python.org, gom Tcl/Tk va pip.
pause
exit /b 1
