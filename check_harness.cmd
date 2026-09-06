@echo off
setlocal
cd /d "%~dp0"
set "PYTHON=.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
  echo Python environment is not ready. Run setup_windows.cmd first.
  pause
  exit /b 1
)

"%PYTHON%" scripts\harness_check.py
if errorlevel 1 goto :error

echo.
echo Harness checks completed successfully.
pause
exit /b 0

:error
echo.
echo Harness checks failed. Review the messages above and outputs\harness_report.json.
pause
exit /b 1
