@echo off
:: ============================================================
:: start_debug.bat — ElectroPOS Debug / Visible-Terminal Mode
:: ============================================================
:: What it does : Starts server.py in a VISIBLE console window
::                so you can read startup logs and errors live.
::                Full Waitress + mDNS — identical to production
::                except the terminal stays open.
:: When to run  : When diagnosing startup errors or testing
::                code changes before deploying via the shortcut.
:: Admin rights : NOT required.
:: ============================================================
title ElectroPOS — Debug Server
cd /d "%~dp0"

if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found.
    echo Run:  python -m venv venv  then  pip install -r requirements.txt
    pause & exit /b 1
)

if not exist ".env" (
    echo ERROR: .env file not found.
    echo Copy .env.example to .env and fill in your settings.
    pause & exit /b 1
)

call venv\Scripts\activate.bat

set PORT=5000
set FLASK_ENV=development

echo.
echo ============================================================
echo   ElectroPOS  --  Debug Mode  (port 5000, visible console)
echo ============================================================
echo   http://127.0.0.1:5000
echo   http://originalelectronics.local:5000
echo   Press Ctrl+C to stop.
echo.

python server.py
pause
