@echo off
:: ============================================================
:: create_shortcut.bat — Desktop Shortcut Creator
:: ============================================================
:: What it does : Creates an "Original Electronics" shortcut on
::                the Desktop that silently launches the POS via
::                launcher.vbs.  Safe to run multiple times.
:: When to run  : Once after installation, or to restore a
::                deleted shortcut.
:: Admin rights : NOT required.
:: ============================================================

cd /d "%~dp0"

echo.
echo ============================================================
echo  ElectroPOS — Creating Desktop Shortcut
echo ============================================================
echo.

:: Get the Desktop path and project root
set PROJECT_DIR=%~dp0
:: Remove trailing backslash
if "%PROJECT_DIR:~-1%"=="\" set PROJECT_DIR=%PROJECT_DIR:~0,-1%

:: Use PowerShell to create the .lnk shortcut
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$desktop = [System.Environment]::GetFolderPath('Desktop');" ^
  "$lnkPath  = Join-Path $desktop 'Original Electronics.lnk';" ^
  "$shell    = New-Object -ComObject WScript.Shell;" ^
  "$sc       = $shell.CreateShortcut($lnkPath);" ^
  "$sc.TargetPath      = '%PROJECT_DIR%\launcher.vbs';" ^
  "$sc.WorkingDirectory= '%PROJECT_DIR%';" ^
  "$sc.WindowStyle     = 7;" ^
  "$sc.IconLocation    = 'shell32.dll,14';" ^
  "$sc.Description     = 'Start ElectroPOS — Original Electronics POS System';" ^
  "$sc.Save();" ^
  "Write-Host '  [SUCCESS] Shortcut created at: ' + $lnkPath"

if %errorlevel% equ 0 (
    echo.
    echo  A shortcut named "Original Electronics" has been added to your Desktop.
    echo  Double-click it to start the server and open the browser automatically.
) else (
    echo.
    echo  [ERROR] Failed to create the shortcut. Check PowerShell permissions.
)

echo.
echo ============================================================
pause
