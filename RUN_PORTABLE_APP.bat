@echo off
title Launch IFMIS-VLC Voucher Reconciliation Tool
if exist "dist\IFMIS_VLC_Voucher_Reconciliation_Suite_v1.0_Portable.exe" (
    start "" "dist\IFMIS_VLC_Voucher_Reconciliation_Suite_v1.0_Portable.exe"
) else (
    echo Portable EXE not found. Building it now...
    call BUILD_PORTABLE_EXE.bat
)
