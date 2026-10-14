@echo off
title IFMIS–VLC Voucher Reconciliation Tool
cd /d "%~dp0"

echo =========================================================================
echo             IFMIS–VLC VOUCHER RECONCILIATION TOOL
echo         State Treasury & VLC Compilation Audit Suite
echo =========================================================================
echo.
echo Starting Application in Maximized Mode...

"C:\Users\nitin\AppData\Local\Python\pythoncore-3.14-64\python.exe" main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application exited with an error code: %ERRORLEVEL%
    pause
)
