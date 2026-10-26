@echo off
set "IBC_PY="
call :probe python
if not errorlevel 1 (
  set "IBC_PY=python"
  exit /b 0
)
call :probe py -3
if not errorlevel 1 (
  set "IBC_PY=py -3"
  exit /b 0
)
for %%V in (3.15 3.14 3.13 3.12 3.11 3.10) do (
  call :probe py -%%V
  if not errorlevel 1 (
    set "IBC_PY=py -%%V"
    exit /b 0
  )
)
for %%E in (.venv .venv315) do (
  if exist "%%E\Scripts\python.exe" (
    call :probe "%%E\Scripts\python.exe"
    if not errorlevel 1 (
      set IBC_PY="%%E\Scripts\python.exe"
      exit /b 0
    )
  )
)
echo Khong tim thay Python 64-bit 3.10-3.15 dang hoat dong.
echo Neu da cai Python 3.15, khong can cai them 3.12.
echo Kiem tra lenh python --version va py --list, hoac mo lai Terminal sau khi cai Python.
exit /b 1
:probe
call %* -c "import sys,struct; sys.exit(0 if (3,10) <= sys.version_info[:2] <= (3,15) and struct.calcsize('P') == 8 else 1)" >nul 2>nul
if "%errorlevel%"=="0" exit /b 0
exit /b 1
