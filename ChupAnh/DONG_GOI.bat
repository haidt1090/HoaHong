@echo off
cd /d "%~dp0"
if exist .build-venv\Scripts\python.exe goto build
py -3.12 -m venv .build-venv
if errorlevel 1 goto fail
:build
.build-venv\Scripts\python.exe build_windows.py
if errorlevel 1 goto fail
echo.
echo Hoan tat: dist\ChupAnh-Windows.zip
echo Day la ban standalone native. Can giai nen ca thu muc.
if not defined CHUPANH_NONINTERACTIVE pause
exit /b 0
:fail
echo Dong goi that bai. Can Windows x64, Python 3.12 x64 va Internet.
echo Xem thong bao ben tren. Source van chay bang MO_UNG_DUNG.bat.
if not defined CHUPANH_NONINTERACTIVE pause
exit /b 1
