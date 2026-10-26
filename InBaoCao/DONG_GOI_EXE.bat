@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
pushd "%~dp0"
if errorlevel 1 goto folder_error
call scripts\ChonPython.cmd
if errorlevel 1 goto runtime_error
call %IBC_PY% scripts\windows_env.py build
set "IBC_EXIT=%errorlevel%"
popd
pause
exit /b %IBC_EXIT%
:runtime_error
popd
pause
exit /b 1
:folder_error
echo Khong mo duoc thu muc source. Hay giai nen toan bo ZIP truoc khi chay.
pause
exit /b 1
