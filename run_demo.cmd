@echo off
setlocal
cd /d "%~dp0"
set "PYTHON=.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
  echo Python environment is not ready. Run setup_windows.cmd first.
  pause
  exit /b 1
)

"%PYTHON%" -m value_dislocation.cli screen --config config/default.yaml --as-of 2026-07-31
if errorlevel 1 goto :error

"%PYTHON%" -m value_dislocation.cli propose-orders --config config/default.yaml
if errorlevel 1 goto :error

"%PYTHON%" -m value_dislocation.cli backtest --config config/default.yaml
if errorlevel 1 goto :error

echo.
echo Demo data generation completed.
echo Starting the dashboard at http://localhost:8501
echo Keep this window open while using the dashboard.
echo Press Ctrl+C in this window to stop the server.
echo.

"%PYTHON%" -m streamlit run dashboard.py --server.address 127.0.0.1 --server.port 8501 --server.headless false --browser.gatherUsageStats false
if errorlevel 1 goto :dashboard_error
exit /b 0

:error
echo.
echo Demo data generation failed. Review the error message above.
pause
exit /b 1

:dashboard_error
echo.
echo The dashboard server stopped or failed to start.
echo Review the error message above.
pause
exit /b 1
