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

if getattr(sys, 'frozen', False):
    APP_DIR = sys._MEIPASS
    EXE_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    EXE_DIR = APP_DIR
os.chdir(EXE_DIR)

class DesktopReconciliationApi:
    def __init__(self):
        self._importer = FileImportManager()
        self._logger = AuditLogger(log_dir=os.path.join(EXE_DIR, "logs"))
        self._engine = None
        self._last_results = None

    def get_initial_state(self):
        """Initial state passed to UI upon launch - opens 100% clean and blank."""
        summaries = self._importer.get_all_summaries()
        
        file_states = {}
        for fid in ["file_1", "file_2", "file_3", "file_4", "file_5", "file_6"]:
            s = summaries.get(fid, {})
            file_states[fid] = {
                "path": s.get("file_path", ""),
                "loaded": s.get("is_loaded", False),
                "records": s.get("valid_records_count", 0),
                "unique_vouchers": s.get("unique_vouchers_count", 0),
                "size": s.get("file_size", 0)
            }

        return {
            "file_states": file_states,
            "reconciliation_results": self._last_results,
            "audit_logs": self._logger.events[-50:]
        }

    def _auto_detect_default_files(self):
        """Automatically links default workspace files if present."""
        vb_folder = os.path.join(EXE_DIR, "vallabh bhawan")
        if not os.path.isdir(vb_folder):
            vb_folder = os.path.join(APP_DIR, "vallabh bhawan")

        compay_file = os.path.join(EXE_DIR, "COMPAY_DATA_VAL_10_2025.XLS")
        if not os.path.exists(compay_file):
            compay_file = os.path.join(APP_DIR, "COMPAY_DATA_VAL_10_2025.XLS")

        f_map = {
            "file_1": [os.path.join(vb_folder, "Voucher Details - file 01.txt"), os.path.join(vb_folder, "1_0521020253sop.txt")],
            "file_2": [os.path.join(vb_folder, "Voucher Detail - Details Headwise - file 02.txt"), os.path.join(vb_folder, "2_0521020253sop.txt")],
            "file_3": [os.path.join(vb_folder, "AG Deduction - file 03.txt"), os.path.join(vb_folder, "3_0521020253sop.txt")],
            "file_4": [os.path.join(vb_folder, "NON AG Deduction - file 04.txt"), os.path.join(vb_folder, "4_0521020253sop.txt")],
            "file_5": [os.path.join(vb_folder, "Voucher Summary - file 05.txt"), os.path.join(vb_folder, "0521020253sop.txt")],
            "file_6": [os.path.join(EXE_DIR, "VLC COMPAY - file 06.XLS"), compay_file]
        }

        for fid, paths in f_map.items():
            if not self._importer.files.get(fid):
                for p in paths:
                    if p and os.path.exists(p):
                        try:
                            self._importer.register_file(fid, p)
                            break
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
                "unique_vouchers": s.get("unique_vouchers_count", 0),
                "size": s.get("file_size", 0)
            }
        return {"file_states": file_states}

    def browse_folder_and_auto_import(self, criteria=None):
        """
        Opens native directory dialog to pick a folder containing reconciliation files,
        automatically identifies each of the 6 files, registers them, and returns updated states.
        Accepts optional criteria: { treasury_code, month, year, folder_path }.
        """
        criteria = criteria or {}
        selected_folder = criteria.get('folder_path', '')
        if not selected_folder:
            opened_dialog = False
            try:
                window = webview.windows[0] if webview.windows else None
                if window:
                    dialog_type = getattr(webview.FileDialog, 'FOLDER', getattr(webview, 'FOLDER_DIALOG', 20))
                    res = window.create_file_dialog(dialog_type)
                    opened_dialog = True
                    if res and len(res) > 0:
                        selected_folder = res[0]
            except Exception:
                opened_dialog = False

            if not selected_folder and not opened_dialog:
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

        def _send_progress(status_text, current_file="", role="", step=0, total_steps=8):
            try:
                window = webview.windows[0] if webview.windows else None
                if window:
                    payload = json.dumps({
                        "status_text": status_text,
                        "current_file": current_file,
                        "role": role,
                        "step": step,
                        "total_steps": total_steps
                    })
                    window.evaluate_js(f"window.onImportProgress && window.onImportProgress({payload});")
            except Exception:
                pass

        _send_progress(f"Folder selected: '{os.path.basename(selected_folder)}'. Scanning directory...", step=1, total_steps=8)

        from core.file_detector import SmartFileIdentifier
        identified, logs, unmatched, disparity_report = SmartFileIdentifier.scan_folder(
            selected_folder,
            treasury_code=criteria.get('treasury_code'),
            month=criteria.get('month'),
            year=criteria.get('year'),
            return_diagnostics=True
        )

        active_roles = [r for r, p in identified.items() if p]
        total_steps = len(active_roles) + 2
        step = 1
        _send_progress(f"Found files for {len(active_roles)} roles. Importing records...", step=step, total_steps=total_steps)

        loaded_count = 0
        ROLE_TITLES = {
            "file_1": "File 01 (Bill Master)",
            "file_2": "File 02 (Detailed Gross)",
            "file_3": "File 03 (AG Deduction)",
            "file_4": "File 04 (Non-AG Deduction)",
            "file_5": "File 05 (Summary SOP)",
            "file_6": "File 06 (VLC COMPAY)"
        }
        for fid, path in identified.items():
            if not path:
                continue
            step += 1
            disp_name = os.path.basename(path) if isinstance(path, str) else (f"{len(path)} files merged" if len(path) > 1 else (os.path.basename(path[0]) if path else "None"))
            r_label = ROLE_TITLES.get(fid, fid.upper())
            _send_progress(f"Importing {r_label}: {disp_name}...", current_file=disp_name, role=fid, step=step, total_steps=total_steps)
            try:
                self._importer.register_file(
                    fid,
                    path,
                    target_month=criteria.get('month'),
                    target_year=criteria.get('year')
                )
                loaded_count += 1
                self._logger.log_event("AUTO_IMPORT", f"Auto-mapped {fid.upper()} to '{disp_name}'")
            except Exception as e:
                self._logger.log_error("AUTO_IMPORT", f"Failed to register {fid}: {e}")

        _send_progress("Reconciliation files successfully loaded and verified!", step=total_steps, total_steps=total_steps)

        summaries = self._importer.get_all_summaries()
        file_states = {}
        for fid, s in summaries.items():
            file_states[fid] = {
                "path": s.get("file_path", ""),
                "filename": s.get("filename", ""),
                "loaded": s.get("is_loaded", False),
                "records": s.get("valid_records_count", 0),
                "unique_vouchers": s.get("unique_vouchers_count", 0),
                "size": s.get("file_size", 0)
            }

        identified_display = {}
        for k, v in identified.items():
            if isinstance(v, str):
                identified_display[k] = os.path.basename(v)
            elif isinstance(v, (list, tuple)) and v:
                if len(v) == 1:
                    identified_display[k] = os.path.basename(v[0])
                else:
                    identified_display[k] = f"{len(v)} files ({os.path.basename(v[0])}...)"
            else:
                identified_display[k] = ""

        return {
            "success": True,
            "folder": selected_folder,
            "folder_name": os.path.basename(selected_folder),
            "loaded_count": loaded_count,
            "identified": identified_display,
            "logs": logs,
            "unmatched": unmatched,
            "file_states": file_states,
            "is_all_ready": self._importer.is_all_6_ready(),
            "is_ready_to_reconcile": self._importer.is_ready_to_reconcile(),
            "disparity_report": disparity_report,
            "skipped_empty_count": disparity_report.get("skipped_empty_count", 0) if disparity_report else 0,
            "skipped_html_count": disparity_report.get("skipped_html_count", 0) if disparity_report else 0
        }

    def rescan_folder(self, criteria):
        """Re-evaluates an existing folder with updated treasury, month, or year parameters."""
        return self.browse_folder_and_auto_import(criteria)


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
                "unique_vouchers": summary.get("unique_vouchers_count", 0),
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
        """Executes full reconciliation with user-selected matching key, tolerance, and major head scope."""
        try:
            if not self._importer.is_ready_to_reconcile():
                return {"error": "Please load at least File 2 (Detailed Gross) and File 6 (VLC COMPAY) before running reconciliation."}

            # Build key fields list
            key_fields = []
            if key_config.get("try_cd", True): key_fields.append("try_cd")
            if key_config.get("mhcd", True): key_fields.append("mhcd")
            if key_config.get("vou_no", True): key_fields.append("vou_no")
            if key_config.get("vou_date", False): key_fields.append("vou_date")
            if key_config.get("ddo_cd", False): key_fields.append("ddo_cd")

            if not key_fields:
                key_fields = ["try_cd", "mhcd", "vou_no"]

            mh_scope = key_config.get("mh_scope_0001_5999", True)
            target_month = key_config.get("target_month")

            self._engine = ComprehensiveReconciliationEngine(
                self._importer,
                key_fields=key_fields,
                tolerance=Decimal(str(tolerance)),
                logger=self._logger,
                mh_scope_consolidated=mh_scope,
                target_month=target_month
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

        exporter = ExportManager(self._last_results, self._logger, reports_dir=os.path.join(EXE_DIR, "reports"))
        try:
            if format_type == 'excel':
                p = exporter.export_excel(section=section)
            elif format_type == 'csv':
                p = exporter.export_csv(section=section)
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
            "grand_tally": "IFMIS_VLC_Grand_Tally_Balance_Sheet",
            "gross_recon": "IFMIS_VLC_Primary_Gross_Reconciliation_File02_vs_File06",
            "val_f1": "IFMIS_BillMaster_Gross_Net_Deductions",
            "net_recon": "IFMIS_Net_Reconciliation",
            "ag_ded": "IFMIS_AG_Deductions_Schedule",
            "non_ag_ded": "IFMIS_Treasury_Deductions_Schedule",
            "cross_file": "IFMIS_12_Cross_File_Consistency_Checks",
            "exceptions": "IFMIS_Exceptions_Register",
            "head_wise": "IFMIS_Major_Head_Summary_Tally",
            "classification_tally": "IFMIS_15_Digit_Classification_Tally",
            "refunds": "IFMIS_Refund_Vouchers_And_Deduct_Exp"
        }
        ext = ".xlsx" if format_type == 'excel' else (".pdf" if format_type == 'pdf' else (".csv" if format_type == 'csv' else ".txt"))
        prefix = name_map.get(section, "IFMIS_VLC_Reconciliation_Workbook")
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

        exporter = ExportManager(self._last_results, self._logger, reports_dir=os.path.join(EXE_DIR, "reports"))
        try:
            if format_type == 'excel':
                p = exporter.export_excel(output_path=selected_path, section=section)
            elif format_type == 'csv':
                p = exporter.export_csv(output_path=selected_path, section=section)
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
        if not file_path:
            return False
        abs_p = os.path.abspath(file_path)
        if os.path.exists(abs_p):
            try:
                os.startfile(abs_p)
                return True
            except Exception:
                try:
                    subprocess.Popen(['explorer.exe', abs_p])
                    return True
                except Exception:
                    return False
        return False

    def show_in_folder(self, file_path):
        """Opens Windows Explorer with the specific file selected."""
        if not file_path:
            return self.open_output_folder()
        abs_p = os.path.abspath(file_path)
        if os.path.exists(abs_p):
            try:
                subprocess.Popen(f'explorer.exe /select,"{abs_p}"')
                return True
            except Exception:
                folder = os.path.dirname(abs_p)
                try:
                    os.startfile(folder)
                    return True
                except Exception:
                    return False
        return self.open_output_folder()

    def open_output_folder(self):
        """Opens the reports output folder in Windows Explorer."""
        target_dir = os.path.join(EXE_DIR, "reports", "Treasury_052_VAL_10_2025")
        if not os.path.exists(target_dir):
            target_dir = os.path.join(EXE_DIR, "reports")
        os.makedirs(target_dir, exist_ok=True)
        abs_dir = os.path.abspath(target_dir)
        try:
            os.startfile(abs_dir)
            return True
        except Exception:
            try:
                subprocess.Popen(f'explorer.exe "{abs_dir}"')
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
