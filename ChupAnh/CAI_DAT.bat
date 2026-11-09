@echo off
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 goto fail
echo Cai dat xong. Chay MO_UNG_DUNG.bat
pause
exit /b 0
:fail
echo Cai dat that bai. Kiem tra Python 3.11+ va ket noi Internet.
pause
exit /b 1
