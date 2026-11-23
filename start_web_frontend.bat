@echo off
setlocal
cd /d "%~dp0web\frontend"
where npm >NUL 2>NUL
if errorlevel 1 (
  echo ERROR: Node.js / npm is not installed or is not on PATH.
  echo Install Node.js 20+ from https://nodejs.org/ then restart VS Code.
  pause
  exit /b 1
)
echo [QuizVerse] Browser frontend: http://localhost:5173
if not exist node_modules (
  echo Installing React and Vite packages (internet required on first run)...
  call npm install
  if errorlevel 1 goto failed
)
call npm run dev
:failed
echo.
echo Frontend stopped. Review errors above. Press any key to close.
pause >NUL
