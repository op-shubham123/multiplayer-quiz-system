@echo off
cd /d "%~dp0"
echo Starting QuizVerse server...
where py >nul 2>&1
if %errorlevel%==0 (
    py server.py
) else (
    python server.py
)
echo.
echo Server stopped. Press any key to close.
pause >nul
