# -*- coding: utf-8 -*-
"""
IFMIS–VLC Voucher Reconciliation Tool
Desktop Application Main Entrypoint (PyWebView + Python Engine)
"""

import os
import sys
import json
import subprocess
import datetime
from decimal import Decimal
import webview

from core.file_importer import FileImportManager
from core.format_detector import FormatDetector
from core.reconciliation_engine import ComprehensiveReconciliationEngine
from core.export_manager import ExportManager
from core.audit_log import AuditLogger

APP_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(APP_DIR)

class DesktopReconciliationApi:
    def __init__(self):
        self._importer = FileImportManager()
        self._logger = AuditLogger()
        self._engine = None
        self._last_results = None
        # Eagerly preload default workspace files so data is immediately available
        self._auto_detect_default_files()
        if self._importer.is_all_ready():
            try:
                self._engine = ComprehensiveReconciliationEngine(self._importer, logger=self._logger)
                self._last_results = self._engine.execute()
            except Exception as e:
                self._logger.log_error("STARTUP_RECON", str(e))

    def get_initial_state(self):
        """Initial state passed to UI upon launch."""
        if not self._importer.is_all_ready():
            self._auto_detect_default_files()

        summaries = self._importer.get_all_summaries()
        
        file_states = {}
        for fid, s in summaries.items():
            file_states[fid] = {
                "path": s.get("file_path", ""),
                "loaded": s.get("is_loaded", False),
                "records": s.get("valid_records_count", 0),
                "size": s.get("file_size", 0)
            }

        # Auto-run reconciliation if all 6 default files are loaded and not already computed
        if not self._last_results and self._importer.is_all_ready():
            try:
                self._engine = ComprehensiveReconciliationEngine(self._importer, logger=self._logger)
                self._last_results = self._engine.execute()
            except Exception as e:
                self._logger.log_error("STARTUP_RECON", str(e))

        return {
            "file_states": file_states,
            "reconciliation_results": self._last_results,
            "audit_logs": self._logger.events[-50:]
        }

    def _auto_detect_default_files(self):
        """Automatically links default workspace files if present."""
        vb_folder = os.path.join(APP_DIR, "vallabh bhawan")
        compay_file = os.path.join(APP_DIR, "COMPAY_DATA_VAL_10_2025.XLS")

        f_map = {
            "file_1": os.path.join(vb_folder, "1_0521020253sop.txt"),
            "file_2": os.path.join(vb_folder, "2_0521020253sop.txt"),
            "file_3": os.path.join(vb_folder, "3_0521020253sop.txt"),
            "file_4": os.path.join(vb_folder, "4_0521020253sop.txt"),
            "file_5": os.path.join(vb_folder, "0521020253sop.txt"),
            "file_6": compay_file
        }

        for fid, p in f_map.items():
            if os.path.exists(p) and not self._importer.files.get(fid):
                try:
                    self._importer.register_file(fid, p)
                except Exception as ex:
                    self._logger.log_warning("AUTODETECT", f"Failed to register {fid}: {ex}")

    def load_default_files(self):
        self._auto_detect_default_files()
        summaries = self._importer.get_all_summaries()
        file_states = {}
        for fid, s in summaries.items():
            file_states[fid] = {
                "path": s.get("file_path", ""),
                "loaded": s.get("is_loaded", False),
                "records": s.get("valid_records_count", 0),
                "size": s.get("file_size", 0)
            }
        return {"file_states": file_states}

    def browse_folder_and_auto_import(self):
        """
        Opens native directory dialog to pick a folder containing reconciliation files,
        automatically identifies each of the 6 files, registers them, and returns updated states.
        """
        selected_folder = ""
        try:
            window = webview.windows[0] if webview.windows else None
            if window:
                dialog_type = getattr(webview.FileDialog, 'FOLDER', getattr(webview, 'FOLDER_DIALOG', 20))
                res = window.create_file_dialog(dialog_type)
                if res and len(res) > 0:
                    selected_folder = res[0]
        except Exception:
            pass

        if not selected_folder:
            try:
                from tkinter import Tk, filedialog
                root = Tk()
                root.withdraw()
                root.attributes('-topmost', True)
                selected_folder = filedialog.askdirectory(title="Select Folder Containing All Reconciliation Files")
                root.destroy()
            except Exception:
                pass

        if not selected_folder or not os.path.isdir(selected_folder):
            return {"cancelled": True}

        from core.file_detector import SmartFileIdentifier
        identified, logs, unmatched = SmartFileIdentifier.scan_folder(selected_folder)

        loaded_count = 0
        for fid, path in identified.items():
            try:
                self._importer.register_file(fid, path)
                loaded_count += 1
                self._logger.log_event("AUTO_IMPORT", f"Auto-mapped {fid.upper()} to '{os.path.basename(path)}'")
            except Exception as e:
                self._logger.log_error("AUTO_IMPORT", f"Failed to register {fid}: {e}")

        summaries = self._importer.get_all_summaries()
        file_states = {}
        for fid, s in summaries.items():
            file_states[fid] = {
                "path": s.get("file_path", ""),
                "loaded": s.get("is_loaded", False),
                "records": s.get("valid_records_count", 0),
                "size": s.get("file_size", 0)
            }

        return {
            "success": True,
            "folder": selected_folder,
            "folder_name": os.path.basename(selected_folder),
            "loaded_count": loaded_count,
            "identified": {k: os.path.basename(v) for k, v in identified.items()},
            "logs": logs,
            "unmatched": unmatched,
            "file_states": file_states,
            "is_all_ready": self._importer.is_all_ready()
        }


    def browse_file(self, file_id):
        """Opens native file dialog to choose a file for specific role."""
        selected_path = ""
        try:
            window = webview.windows[0] if webview.windows else None
            if window:
                res = window.create_file_dialog(
                    webview.OPEN_DIALOG,
                    allow_multiple=False,
                    file_types=('Data Files (*.txt;*.csv;*.tsv;*.xls;*.xlsx)', 'All files (*.*)')
                )
                if res and len(res) > 0:
                    selected_path = res[0]
        except Exception:
            pass

        if not selected_path:
            try:
                from tkinter import Tk, filedialog
                root = Tk()
                root.withdraw()
                root.attributes('-topmost', True)
                selected_path = filedialog.askopenfilename(
                    title=f"Select {file_id.upper()} Input File",
                    filetypes=[("Data Files", "*.txt;*.csv;*.tsv;*.xls;*.xlsx"), ("All files", "*.*")]
                )
                root.destroy()
            except Exception:
                pass

        if selected_path and os.path.exists(selected_path):
            summary = self._importer.register_file(file_id, selected_path)
            return {
                "path": selected_path,
                "filename": os.path.basename(selected_path),
                "is_loaded": summary.get("is_loaded", False),
                "records_count": summary.get("valid_records_count", 0),
                "file_size": summary.get("file_size", 0)
            }
        return {}

    def preview_file(self, file_id):
        """Returns preview rows and inspection metadata for modal display."""
        ds = self._importer.get_file(file_id)
        if not ds or not ds.file_path or not os.path.exists(ds.file_path):
            return {"error": "File not selected or not found."}

        try:
            meta = FormatDetector.inspect_file(ds.file_path, max_preview_rows=15)
            return meta
        except Exception as e:
            return {"error": str(e)}

    def run_reconciliation(self, key_config, tolerance=0.00):
        """Executes full reconciliation with user-selected matching key and tolerance."""
        try:
            if not self._importer.is_all_ready():
                self._auto_detect_default_files()

            # Build key fields list
            key_fields = []
            if key_config.get("try_cd", True): key_fields.append("try_cd")
            if key_config.get("mhcd", True): key_fields.append("mhcd")
            if key_config.get("vou_no", True): key_fields.append("vou_no")
            if key_config.get("vou_date", False): key_fields.append("vou_date")
            if key_config.get("ddo_cd", False): key_fields.append("ddo_cd")

            if not key_fields:
                key_fields = ["try_cd", "mhcd", "vou_no"]

            self._engine = ComprehensiveReconciliationEngine(
                self._importer,
                key_fields=key_fields,
                tolerance=Decimal(str(tolerance)),
                logger=self._logger
            )
            self._last_results = self._engine.execute()
            return self._last_results
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

    def export_report(self, format_type, section=None):
        """Exports the current reconciliation results to specified format."""
        if not self._last_results:
            return {"error": "No reconciliation results available to export."}

        exporter = ExportManager(self._last_results, self._logger)
        try:
            if format_type == 'excel':
                p = exporter.export_excel(section=section)
            elif format_type == 'csv':
                p = exporter.export_csv()
            elif format_type == 'pdf':
                p = exporter.export_pdf()
            elif format_type == 'txt':
                p = exporter.export_text_report()
            else:
                return {"error": f"Unknown format: {format_type}"}

            return {
                "success": True,
                "filename": os.path.basename(p),
                "path": p,
                "events": self._logger.events[-10:]
            }
        except Exception as e:
            return {"error": str(e)}

    def export_report_save_as(self, format_type, section=None):
        """Allows user to select custom destination for export using native Save File dialog."""
        if not self._last_results:
            return {"error": "No reconciliation results available to export."}

        name_map = {
            "grand_tally": "Grand_Tally_Balance_Sheet",
            "gross_recon": "Gross_Recon_IFMIS_vs_COMPAY",
            "val_f1": "IFMIS_BillMaster_Gross_Net_Deductions",
            "net_recon": "Net_Recon_BillMaster_vs_NetSOP",
            "ag_ded": "AG_Deductions_Schedule",
            "non_ag_ded": "Treasury_Deductions_Schedule",
            "cross_file": "Statutory_Cross_File_12_Checks",
            "exceptions": "Exceptions_Register_MH4801_Uncompiled",
            "head_wise": "Major_Head_Summary_Tally",
            "classification_tally": "Classification_Tally_15_Digit",
            "refunds": "Refund_Vouchers_And_Deduct_Exp"
        }
        ext = ".xlsx" if format_type == 'excel' else (".pdf" if format_type == 'pdf' else (".csv" if format_type == 'csv' else ".txt"))
        prefix = name_map.get(section, "Audit_Reconciliation_Report")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"{prefix}_{timestamp}{ext}"

        selected_path = ""
        try:
            window = webview.windows[0] if webview.windows else None
            if window:
                dialog_type = getattr(webview.FileDialog, 'SAVE', getattr(webview, 'SAVE_DIALOG', 10))
                file_types = ('Excel Files (*.xlsx)', '*.xlsx') if ext == '.xlsx' else (('PDF Files (*.pdf)', '*.pdf') if ext == '.pdf' else ('All Files (*.*)', '*.*'))
                res = window.create_file_dialog(dialog_type, save_filename=default_name, file_types=[file_types])
                if res:
                    selected_path = res if isinstance(res, str) else res[0]
        except Exception:
            pass

        if not selected_path:
            try:
                from tkinter import Tk, filedialog
                root = Tk()
                root.withdraw()
                root.attributes('-topmost', True)
                selected_path = filedialog.asksaveasfilename(
                    initialfile=default_name,
                    defaultextension=ext,
                    filetypes=[("Excel Files", "*.xlsx")] if ext == '.xlsx' else [("All Files", "*.*")]
                )
                root.destroy()
            except Exception:
                pass

        if not selected_path:
            return {"cancelled": True}

        exporter = ExportManager(self._last_results, self._logger)
        try:
            if format_type == 'excel':
                p = exporter.export_excel(output_path=selected_path, section=section)
            elif format_type == 'csv':
                p = exporter.export_csv(output_path=selected_path)
            elif format_type == 'pdf':
                p = exporter.export_pdf(output_path=selected_path)
            elif format_type == 'txt':
                p = exporter.export_text_report(output_path=selected_path)
            else:
                return {"error": f"Unknown format: {format_type}"}

            return {
                "success": True,
                "filename": os.path.basename(p),
                "path": p,
                "events": self._logger.events[-10:]
            }
        except Exception as e:
            return {"error": str(e)}

    def open_file(self, file_path):
        """Opens specified file in its default OS application (e.g. Microsoft Excel)."""
        if file_path and os.path.exists(file_path):
            try:
                os.startfile(file_path)
                return True
            except Exception:
                try:
                    subprocess.Popen(f'explorer "{file_path}"')
                    return True
                except Exception:
                    return False
        return False

    def open_output_folder(self):
        target_dir = os.path.join(APP_DIR, "reports", "Treasury_052_VAL_10_2025")
        if not os.path.exists(target_dir):
            target_dir = os.path.join(APP_DIR, "reports")
        os.makedirs(target_dir, exist_ok=True)
        try:
            os.startfile(target_dir)
            return True
        except Exception:
            try:
                subprocess.Popen(f'explorer "{target_dir}"')
                return True
            except Exception:
                return False


def main():
    api = DesktopReconciliationApi()
    ui_path = os.path.join(APP_DIR, "ui", "index.html")

    # Start maximized
    window = webview.create_window(
        title="IFMIS–VLC Voucher Reconciliation Tool — State Treasury Suite",
        url=ui_path,
        js_api=api,
        width=1440,
        height=900,
        min_size=(1080, 720),
        background_color='#f8fafc'
    )

    def on_loaded():
        try:
            window.maximize()
        except Exception:
            pass

    window.events.loaded += on_loaded
    webview.start(debug=False)


if __name__ == "__main__":
    main()
