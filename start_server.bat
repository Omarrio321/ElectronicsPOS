@echo off
:: ============================================================
:: start_server.bat — ElectroPOS Production Launcher
:: ============================================================
:: What it does : Kills any stale server, activates the venv,
::                starts server.py silently via pythonw.exe,
::                waits for Waitress + mDNS to initialise, then
::                opens the browser automatically.
:: When to run  : Called by launcher.vbs (desktop shortcut).
::                You can also double-click it directly.
:: Admin rights : NOT required.
:: ============================================================
cd /d "%~dp0"

:: ── Kill any stale Python server on port 5000 ────────────────────────────────
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /r ":5000 .*LISTENING" 2^>nul') do (
    if %%a GTR 9 (
        taskkill /PID %%a /F >nul 2>&1
    )
)

:: ── Also clear any orphan pythonw.exe from previous runs ─────────────────────
taskkill /F /IM pythonw.exe >nul 2>&1
:: (error is expected when none are running — safe to ignore)

:: ── Activate virtual environment ─────────────────────────────────────────────
if exist "venv\Scripts\activate.bat" call venv\Scripts\activate.bat

:: ── Pick Python executable (silent pythonw preferred) ────────────────────────
set PYTHONEXE=python.exe
if exist "venv\Scripts\pythonw.exe" set PYTHONEXE=venv\Scripts\pythonw.exe

:: ── Set runtime environment ───────────────────────────────────────────────────
set PORT=5000
set FLASK_ENV=development

:: ── Launch server in background (no console window) ──────────────────────────
start /B "" %PYTHONEXE% server.py

:: ── Wait for Waitress + mDNS to come up (5 seconds) ──────────────────────────
timeout /t 5 /nobreak >nul

:: ── Open browser ─────────────────────────────────────────────────────────────
start "" "http://originalelectronics.local:5000"
