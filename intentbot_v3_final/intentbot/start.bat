@echo off
REM ══════════════════════════════════════════════════════════════════════════════
REM                   Intent™ BOT v3.0 — start.bat (Windows)
REM ══════════════════════════════════════════════════════════════════════════════
title Intent BOT v3.0

IF NOT EXIST ".env" (
    echo ERROR: .env not found. Copy .env.example to .env and fill in your token.
    pause
    exit /b 1
)

IF EXIST "venv\Scripts\activate.bat" (
    echo Starting with virtual environment...
    call venv\Scripts\activate.bat
) ELSE (
    echo WARNING: No venv found. Running with system Python.
)

:start
echo [%date% %time%] Starting Intent BOT v3.0...
python main.py

IF %ERRORLEVEL% NEQ 0 (
    echo Bot exited with error code %ERRORLEVEL%. Restarting in 10 seconds...
    timeout /t 10
    goto start
)
echo Bot stopped cleanly.
pause
