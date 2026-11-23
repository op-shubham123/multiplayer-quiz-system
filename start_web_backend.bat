@echo off
setlocal
cd /d "%~dp0"
where py >NUL 2>NUL
if errorlevel 1 (
  echo ERROR: Python launcher 'py' not found. Install Python 3.10+.
  pause
  exit /b 1
)
echo [QuizVerse] WebSocket backend: http://127.0.0.1:8000/health
py -c "import fastapi, uvicorn" 2>NUL
if errorlevel 1 (
  echo Installing FastAPI and Uvicorn (internet required on first run)...
  py -m pip install -r web\backend\requirements.txt
  if errorlevel 1 goto failed
)
py -m uvicorn web.backend.app:app --host 127.0.0.1 --port 8000 --reload
:failed
echo.
echo Backend stopped. Review errors above. Press any key to close.
pause >NUL
