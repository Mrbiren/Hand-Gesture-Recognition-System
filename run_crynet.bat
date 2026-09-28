@echo off
title CryNet — Gesture Control System
echo ========================================================
echo   CRYNET: Autonomous Offline Gesture Control System
echo ========================================================
cd /d "%~dp0"

if exist "venv\Scripts\python.exe" (
    echo Starting CryNet using local virtual environment...
    venv\Scripts\python.exe main.py
) else (
    echo Starting CryNet using system Python...
    python main.py
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo CryNet encountered an exit code: %ERRORLEVEL%
    pause
)
