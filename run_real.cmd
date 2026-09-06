@echo off
setlocal
cd /d "%~dp0"
set "PYTHON=.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
  echo Python environment is not ready. Run setup_windows.cmd first.
  pause
  exit /b 1
)

findstr /B /C:"JQUANTS_API_KEY=" .env >nul 2>nul
if errorlevel 1 (
  echo JQUANTS_API_KEY is not configured in .env.
  echo You may still start the dashboard and enter the key in its local password field.
  echo.
  goto :dashboard
)

for /f "tokens=1,* delims==" %%A in ('findstr /B /C:"JQUANTS_API_KEY=" .env') do set "JQUANTS_API_KEY=%%B"
if "%JQUANTS_API_KEY%"=="" (
  echo JQUANTS_API_KEY is empty in .env.
  echo You may enter it in the dashboard instead.
  echo.
  goto :dashboard
)

echo Fetching actual Japanese stock data from J-Quants...
"%PYTHON%" -m value_dislocation.cli run-real --config config/real_data.yaml
if errorlevel 1 goto :fetch_error

:dashboard
echo Starting the dashboard at http://localhost:8501
"%PYTHON%" -m streamlit run dashboard.py --server.address 127.0.0.1 --server.port 8501 --server.headless false --browser.gatherUsageStats false
if errorlevel 1 goto :dashboard_error
exit /b 0

:fetch_error
echo.
echo Actual data retrieval failed. Review the error above.
echo The dashboard will still start so you can retry from the UI.
pause

goto :dashboard

:dashboard_error
echo.
echo The dashboard stopped or failed to start.
pause
exit /b 1
