@echo off
cd /d "%~dp0"
echo Starting QuizVerse client...
where py >nul 2>&1
if %errorlevel%==0 (
    py client.py
) else (
    python client.py
)
echo.
echo Client closed. Press any key to close.
pause >nul
