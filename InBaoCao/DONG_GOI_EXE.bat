@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" (
  echo Hay chay CaiDat.cmd truoc.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m unittest discover -s tests -v
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean InBaoCao.spec
if errorlevel 1 goto failed
start "" "%~dp0dist"
echo Da dong goi thanh cong: dist\InBaoCao.exe
pause
exit /b 0
:failed
echo Dong goi chua thanh cong. Xem loi o tren; khong dung file EXE tu lan build loi.
pause
exit /b 1
