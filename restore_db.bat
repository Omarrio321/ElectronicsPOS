@echo off
title Electronics POS - Database Restore
cd /d "%~dp0"
echo ============================================
echo   Electronics POS - Database Restore
echo ============================================
echo.
echo *** WARNING: This will OVERWRITE ALL current data in the database! ***
echo *** Make sure the POS application is stopped before restoring.     ***
echo.

REM Load DB credentials from .env file
set DB_HOST=localhost
set DB_NAME=electronics_pos
set DB_USER=root
set DB_PASSWORD=

for /f "usebackq tokens=1,* delims==" %%A in (".env") do (
    if "%%A"=="DB_HOST"     set DB_HOST=%%B
    if "%%A"=="DB_NAME"     set DB_NAME=%%B
    if "%%A"=="DB_USER"     set DB_USER=%%B
    if "%%A"=="DB_PASSWORD" set DB_PASSWORD=%%B
)

REM List available backups
echo Available backups in the backups\ folder:
echo.
if exist "backups\*.sql" (
    dir /b backups\*.sql
) else (
    echo No backup files found in backups\ folder.
    echo.
    pause
    exit /b 1
)

echo.
set /p BACKUP_FILE="Enter the backup filename (e.g. pos_backup_20260311_1430.sql): "
set FULL_PATH=backups\%BACKUP_FILE%

if not exist "%FULL_PATH%" (
    REM Try as full path
    if not exist "%BACKUP_FILE%" (
        echo ERROR: File not found: %FULL_PATH%
        echo.
        pause
        exit /b 1
    )
    set FULL_PATH=%BACKUP_FILE%
)

echo.
echo You are about to restore from: %FULL_PATH%
echo This will DELETE all current data and replace it with the backup.
echo.
set /p CONFIRM="Type YES (in uppercase) to confirm: "

if not "%CONFIRM%"=="YES" (
    echo Restore cancelled.
    pause
    exit /b 0
)

echo.
echo Restoring database...

if "%DB_PASSWORD%"=="" (
    mysql -h%DB_HOST% -u%DB_USER% %DB_NAME% < "%FULL_PATH%" 2>&1
) else (
    mysql -h%DB_HOST% -u%DB_USER% -p%DB_PASSWORD% %DB_NAME% < "%FULL_PATH%" 2>&1
)

if %errorlevel% == 0 (
    echo.
    echo Restore successful! Database has been restored from %FULL_PATH%
    echo You can now start the POS system.
) else (
    echo.
    echo ERROR: Restore failed.
    echo Check that MySQL is running and the backup file is not corrupted.
)

echo.
pause
