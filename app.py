# -*- coding: utf-8 -*-
"""
IFMIS–VLC Voucher Reconciliation Tool
Desktop Application Main Entrypoint (PyWebView + Python Engine)
Delegates directly to main.py
"""
import sys
import os

from main import main, DesktopReconciliationApi

# Alias for backward compatibility
ReconciliationApi = DesktopReconciliationApi

if __name__ == "__main__":
    main()
