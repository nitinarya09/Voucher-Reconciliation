# -*- coding: utf-8 -*-
"""
Voucher Reconciliation Suite Pro (PyWebView Desktop Application)
Connects COMPAY (Gross Compilation) with SOP Text Files (Gross, Deductions, Net).
"""

import os
import sys
import json
import subprocess
import datetime
import webview
from reconciliation_engine import ReconciliationEngine

# Set current directory
APP_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(APP_DIR)

class ReconciliationApi:
    def __init__(self):
        self.engine = None
        self.last_results = None
        self.compay_path = ""
        self.sop_folder = ""

    def get_default_paths(self):
        """Returns auto-detected default paths in the workspace."""
        default_cp = os.path.join(APP_DIR, "COMPAY_DATA_VAL_10_2025.XLS")
        default_sop = os.path.join(APP_DIR, "vallabh bhawan")
        
        return {
            "compay_path": default_cp if os.path.exists(default_cp) else "",
            "sop_folder": default_sop if os.path.isdir(default_sop) else ""
        }

    def browse_file(self):
        """Native file dialog to choose COMPAY file."""
        try:
            window = webview.windows[0] if webview.windows else None
            if window:
                result = window.create_file_dialog(
                    webview.OPEN_DIALOG,
                    allow_multiple=False,
                    file_types=('Compilation Files (*.xls;*.xlsx;*.tsv;*.csv)', 'All files (*.*)')
                )
                if result and len(result) > 0:
                    return result[0]
        except Exception:
            pass

        # Fallback to tkinter
        try:
            from tkinter import Tk, filedialog
            root = Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            selected = filedialog.askopenfilename(
                title="Select COMPAY File",
                filetypes=[("Excel / TSV / CSV Files", "*.xls;*.xlsx;*.tsv;*.csv"), ("All files", "*.*")]
            )
            root.destroy()
            return selected or ""
        except Exception:
            return ""

    def browse_folder(self):
        """Native folder dialog to choose SOP files folder."""
        try:
            window = webview.windows[0] if webview.windows else None
            if window:
                result = window.create_file_dialog(
                    webview.FOLDER_DIALOG
                )
                if result and len(result) > 0:
                    return result[0]
        except Exception:
            pass

        # Fallback to tkinter
        try:
            from tkinter import Tk, filedialog
            root = Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            selected = filedialog.askdirectory(title="Select SOP Text Files Folder")
            root.destroy()
            return selected or ""
        except Exception:
            return ""

    def reconcile(self, compay_path, sop_folder):
        """Runs the 3-Way & 5-File Voucher Reconciliation."""
        try:
            if not os.path.exists(compay_path):
                return {"error": f"COMPAY file not found: {compay_path}"}
            if not os.path.isdir(sop_folder):
                return {"error": f"SOP folder not found: {sop_folder}"}

            self.compay_path = compay_path
            self.sop_folder = sop_folder
            self.engine = ReconciliationEngine(compay_path, sop_folder)
            self.last_results = self.engine.run()
            return self.last_results
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

    def export_excel(self):
        """Exports the full audit report to an Excel workbook."""
        try:
            if not self.engine or not self.last_results:
                return {"error": "No reconciliation results available. Please run reconciliation first."}

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"Audit_Reconciliation_Report_{timestamp}.xlsx"
            out_path = os.path.join(APP_DIR, filename)

            self.engine.export_excel(out_path)
            return {
                "success": True,
                "filename": filename,
                "path": out_path
            }
        except Exception as e:
            return {"error": str(e)}

    def open_folder(self):
        """Opens working folder in Windows Explorer."""
        try:
            os.startfile(APP_DIR)
            return True
        except Exception:
            try:
                subprocess.Popen(f'explorer "{APP_DIR}"')
                return True
            except Exception:
                return False


def main():
    api = ReconciliationApi()
    ui_path = os.path.join(APP_DIR, "ui", "index.html")

    window = webview.create_window(
        title="Voucher Reconciliation Suite Pro — Vallabh Bhawan (052 / VAL)",
        url=ui_path,
        js_api=api,
        width=1420,
        height=880,
        min_size=(1050, 700),
        background_color='#0f172a'
    )

    webview.start(debug=False)


if __name__ == "__main__":
    main()
