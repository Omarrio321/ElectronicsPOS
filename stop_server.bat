@echo off
:: ============================================================
:: stop_server.bat — ElectroPOS Server Stopper
:: ============================================================
:: What it does : Kills every process listening on port 5000
::                and every orphan pythonw.exe / python.exe
::                running server.py.  Zeroconf unregisters
::                automatically when the Python process exits.
:: When to run  : Whenever you need to stop the server from
::                outside the app (e.g. before a Windows update).
::                Prefer the in-app Admin > Settings > Shutdown.
:: Admin rights : RECOMMENDED (run as Administrator).
:: ============================================================

echo.
echo ============================================================
echo  ElectroPOS -- Stop Server
echo ============================================================
echo.

set KILLED=0

:: ── Kill every PID listening on port 5000 ────────────────────────────────────
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /r ":5000 .*LISTENING" 2^>nul') do (
    if %%a GTR 9 (
        echo  Stopping PID %%a on port 5000...
        taskkill /PID %%a /F >nul 2>&1
        if not errorlevel 1 set KILLED=1
    )
)

:: ── Kill all pythonw.exe instances (accumulated silent launchers) ─────────────
taskkill /F /IM pythonw.exe >nul 2>&1
if not errorlevel 1 set KILLED=1

echo.
if "%KILLED%"=="1" (
    echo  [SUCCESS] All ElectroPOS server processes stopped.
) else (
    echo  [INFO] No running server processes found.
)

echo.
echo ============================================================
pause
