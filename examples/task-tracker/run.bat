@echo off
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel% equ 0 (
    py -3 app.py --host 127.0.0.1 --port 8080
) else (
    python app.py --host 127.0.0.1 --port 8080
)
pause
