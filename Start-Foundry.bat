@echo off
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel% equ 0 (
    py -3 run.py --open
) else (
    python run.py --open
)
pause
