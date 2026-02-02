@echo off
REM EMS 2.0 Quick Start (Windows)
REM This batch file runs the PowerShell startup script

echo.
echo ========================================
echo   EMS 2.0 - Starting...
echo ========================================
echo.

REM Check if running as admin (needed for starting services)
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [WARN] Not running as Administrator.
    echo        Database services may fail to start.
    echo        Right-click and "Run as Administrator" for full functionality.
    echo.
)

REM Run the PowerShell script
powershell -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*

pause
