@echo off
setlocal
cd /d "%~dp0"
set "PYTHON=.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
  echo Python environment is not ready. Run setup_windows.cmd first.
  pause
  exit /b 1
)

set "APP_NAME=Japanese Equity Value Dislocation Research"
set /p APP_NAME=Enter the new application name [%APP_NAME%]: 
if "%APP_NAME%"=="" set "APP_NAME=Japanese Equity Value Dislocation Research"

"%PYTHON%" scripts\generate_app.py --name "%APP_NAME%"
if errorlevel 1 (
  echo Generation failed.
  pause
  exit /b 1
)

echo.
echo Generation completed under the generated folder.
pause
