@echo off
title VIDYUT NETRA - AI Revenue Assurance Platform
color 0B
echo =====================================================================
echo           VIDYUT NETRA (TISC 2026 - CHALLENGE 12)
echo    Intelligent Revenue Assurance for Electricity Distribution
echo =====================================================================
echo.
echo [1/3] Checking Python environment...
python --version
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH! Please install Python 3.10+.
    pause
    exit /b
)

echo.
echo [2/3] Installing Python backend dependencies...
pip install -r backend\requirements.txt

echo.
echo [3/3] Launching Vidyut Netra Integrated Server on http://localhost:5000...
echo (The browser dashboard will open automatically in a few seconds)
echo.
start "" http://localhost:5000
python backend\app.py
pause
