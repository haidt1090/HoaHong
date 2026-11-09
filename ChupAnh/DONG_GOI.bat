@echo off
cd /d "%~dp0"
if exist .venv\Scripts\python.exe goto build
py -3 -m venv .venv
if errorlevel 1 goto fail
:build
.venv\Scripts\python.exe build_windows.py
if errorlevel 1 goto fail
echo.
echo Hoan tat: dist\ChupAnh-Windows.zip
if not defined CHUPANH_NONINTERACTIVE pause
exit /b 0
:fail
echo Dong goi that bai. Xem thong bao ben tren.
if not defined CHUPANH_NONINTERACTIVE pause
exit /b 1
