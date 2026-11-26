@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creating Python virtual environment...
  py -3 -m venv .venv
  if errorlevel 1 (echo Python 3 not found. Install Python 3.12+ and try again.& exit /b 1)
)
call ".venv\Scripts\activate.bat"
python -m pip install -r requirements.txt
if errorlevel 1 (echo Dependency installation failed.& exit /b 1)
if not defined NMR_JWT_SECRET (
  for /f %%I in ('python -c "import secrets;print(secrets.token_hex(32))"') do set "NMR_JWT_SECRET=%%I"
)
set "NMR_DEMO_MODE=true"
echo.
echo NMR Workplace Finance demo running at http://127.0.0.1:8000/
echo API documentation: http://127.0.0.1:8000/docs
echo Press CTRL+C to stop.
echo.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
endlocal
