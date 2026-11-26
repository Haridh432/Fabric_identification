@echo off
title Fabric Sample Collection - Real-Time Launcher
echo ================================================================
echo    Fabric Sample Collection System - Real-Time Launcher
echo ================================================================

IF NOT EXIST .venv\Scripts\python.exe (
    echo [FIRST-TIME SETUP] Creating Python virtual environment...
    python -m venv .venv
    IF ERRORLEVEL 1 (
        echo [ERROR] Python is not installed or not in PATH. Please install Python 3.10+.
        pause
        exit /b 1
    )
    echo [FIRST-TIME SETUP] Installing required packages...
    .venv\Scripts\python.exe -m pip install --upgrade pip
    .venv\Scripts\pip.exe install -r backend\requirements.txt
    .venv\Scripts\pip.exe install pyserial
    echo [FIRST-TIME SETUP] Setup complete!
    echo.
)

.venv\Scripts\python.exe run_realtime.py
pause
