@echo off
title Build Portable IFMIS-VLC Reconciliation Suite EXE
echo =========================================================================
echo Building Standalone Portable EXE (PyInstaller)
echo =========================================================================
echo.

"C:\Users\nitin\AppData\Local\Python\pythoncore-3.14-64\python.exe" -m PyInstaller --clean reconciliation_suite.spec

echo.
if exist "dist\IFMIS_VLC_Voucher_Reconciliation_Suite_v1.0_Portable.exe" (
    echo =========================================================================
    echo SUCCESS: Portable EXE created at:
    echo dist\IFMIS_VLC_Voucher_Reconciliation_Suite_v1.0_Portable.exe
    echo =========================================================================
) else (
    echo BUILD FAILED. Check console output above.
)
pause
