@echo off
setlocal
cd /d "%~dp0"

echo Starting setup...
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_windows.ps1"
set "SETUP_EXIT=%ERRORLEVEL%"

if not "%SETUP_EXIT%"=="0" (
  echo.
  echo Setup failed with exit code %SETUP_EXIT%.
  echo Please copy the full error message and send it for review.
  pause
  exit /b %SETUP_EXIT%
)

echo.
echo Setup completed successfully.
echo You can now run start_dashboard.cmd for actual data or run_demo.cmd for sample data.
pause
exit /b 0
