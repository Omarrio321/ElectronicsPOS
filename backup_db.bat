@echo off
title Electronics POS - Database Backup
cd /d "%~dp0"
echo ============================================
echo   Electronics POS - Database Backup
echo ============================================
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

REM Create backups directory
if not exist "backups" mkdir backups

REM Generate timestamped filename
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set DATETIME=%%I
set TIMESTAMP=%DATETIME:~0,8%_%DATETIME:~8,4%
set BACKUP_FILE=backups\pos_backup_%TIMESTAMP%.sql

echo Creating backup: %BACKUP_FILE%
echo Database: %DB_NAME% on %DB_HOST%
echo.

REM Run mysqldump
if "%DB_PASSWORD%"=="" (
    mysqldump -h%DB_HOST% -u%DB_USER% --single-transaction --routines --triggers %DB_NAME% > "%BACKUP_FILE%" 2>&1
) else (
    mysqldump -h%DB_HOST% -u%DB_USER% -p%DB_PASSWORD% --single-transaction --routines --triggers %DB_NAME% > "%BACKUP_FILE%" 2>&1
)

if %errorlevel% == 0 (
    echo.
    echo Backup successful!
    echo File: %BACKUP_FILE%
    echo.
    REM Show file size
    for %%F in ("%BACKUP_FILE%") do echo Size: %%~zF bytes
) else (
    echo.
    echo ERROR: Backup failed.
    echo Check that MySQL is running and credentials in .env are correct.
    echo mysqldump must be installed and in PATH ^(comes with MySQL^).
)

echo.
pause
