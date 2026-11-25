@echo off
title Fabric Identification System - Real-Time Launcher
echo ================================================================
echo    Starting Fabric Identification System in Real-Time Mode
echo ================================================================

IF EXIST .venv\Scripts\python.exe (
    .venv\Scripts\python.exe run_realtime.py
) ELSE (
    python run_realtime.py
)

pause
