@echo off
:: ============================================================
:: start_tunnel.bat — ElectroPOS + Cloudflare Tunnel Launcher
:: ============================================================
:: Starts the Flask/Waitress server on localhost:5000, then
:: opens a Cloudflare Quick Tunnel for secure HTTPS access from
:: any device (phone, tablet) without certificate installation.
::
:: FIRST-TIME SETUP (run once):
::
::   Install Cloudflare Tunnel tool:
::     Option A — Chocolatey (recommended):
::       choco install cloudflared -y
::
::     Option B — Manual download:
::       https://github.com/cloudflare/cloudflared/releases/latest
::       Download cloudflared-windows-amd64.exe
::       Rename to cloudflared.exe and move to C:\Windows\System32\
::
::   Verify installation:
::     cloudflared --version
::
:: USAGE:
::   Double-click this file, or run from a terminal.
::   Two windows will open — keep both open while using the POS.
::   The Cloudflare window shows the public HTTPS URL
::   (e.g. https://random-name.trycloudflare.com).
::   Share that URL with mobile devices — no certificate setup needed.
::
:: STOP:
::   Close both windows, or press Ctrl+C in each.
:: ============================================================
cd /d "%~dp0"

echo.
echo  ElectroPOS — Starting with Cloudflare Tunnel
echo  ============================================================

:: ── Check cloudflared is installed ───────────────────────────────────────────
where cloudflared >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  [ERROR] cloudflared not found.
    echo  Install it with:  choco install cloudflared -y
    echo  Or download from: https://github.com/cloudflare/cloudflared/releases
    echo.
    pause
    exit /b 1
)

:: ── Kill any stale server on port 5000 ───────────────────────────────────────
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /r ":5000 .*LISTENING" 2^>nul') do (
    if %%a GTR 9 (
        taskkill /PID %%a /F >nul 2>&1
    )
)

:: ── Activate virtual environment if present ──────────────────────────────────
if exist "venv\Scripts\activate.bat" call venv\Scripts\activate.bat

:: ── [1/2] Start Flask/Waitress server in a new window ────────────────────────
echo  [1/2] Starting Flask server on http://localhost:5000...
start "ElectroPOS Server" cmd /k "python server.py"
timeout /t 3 /nobreak >nul

:: ── [2/2] Start Cloudflare Quick Tunnel in a new window ──────────────────────
echo  [2/2] Starting Cloudflare Tunnel...
echo.
echo  ============================================================
echo  Watch the Cloudflare window for your public HTTPS URL.
echo  It will look like: https://xxxx-xxxx.trycloudflare.com
echo  Open that URL on any mobile device — camera will work!
echo  ============================================================
echo.
start "Cloudflare Tunnel" cmd /k "cloudflared tunnel --url http://localhost:5000"

