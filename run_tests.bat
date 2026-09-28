@echo off
title CryNet — Unit Test Suite
echo ========================================================
echo   Running CryNet Automated Test Suite
echo ========================================================
cd /d "%~dp0"

if exist "venv\Scripts\pytest.exe" (
    venv\Scripts\pytest.exe tests -v
) else (
    pytest tests -v
)

pause
