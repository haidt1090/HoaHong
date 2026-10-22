@echo off
setlocal
cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
  echo Can cai Node.js 24 LTS de chinh sua va dong goi ung dung.
  pause
  exit /b 1
)
call npm ci
if errorlevel 1 goto failed
call npm run pack:win
if errorlevel 1 goto failed
start "" "%~dp0release"
echo Da dong goi. File EXE nam trong thu muc release.
pause
exit /b 0
:failed
echo Dong goi chua thanh cong. Xem thong bao loi o tren.
pause
exit /b 1
