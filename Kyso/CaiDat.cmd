@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
pushd "%~dp0"
if errorlevel 1 exit /b 1
set "KYSO_PY="
if exist ".venv\Scripts\python.exe" (
  call :probe ".venv\Scripts\python.exe"
  if not errorlevel 1 (
    set KYSO_PY=".venv\Scripts\python.exe"
    goto ready
  )
)
call :probe python
if not errorlevel 1 (
  set "KYSO_PY=python"
  goto ready
)
call :probe py -3
if not errorlevel 1 (
  set "KYSO_PY=py -3"
  goto ready
)
for %%V in (3.15 3.14 3.13 3.12 3.11 3.10) do (
  call :probe py -%%V
  if not errorlevel 1 (
    set "KYSO_PY=py -%%V"
    goto ready
  )
)
echo Can Python 64-bit 3.10-3.15 co Tcl/Tk. Kiem tra python --version va py --list.
if not defined KYSO_NONINTERACTIVE pause
popd
exit /b 1
:ready
call %KYSO_PY% scripts\windows_env.py setup %*
set "KYSO_EXIT=%errorlevel%"
if not "%KYSO_EXIT%"=="0" (
  echo Khoi dong/cai dat that bai. Xem thong bao loi phia tren.
  echo Nhat ky trong LOCALAPPDATA\KySoPython\diagnostics\last-launch.log
  if not defined KYSO_NONINTERACTIVE pause
)
popd
exit /b %KYSO_EXIT%
:probe
call %* -c "import sys,struct; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,15) and struct.calcsize('P') == 8 else 1)" >nul 2>nul
if "%errorlevel%"=="0" exit /b 0
exit /b 1
