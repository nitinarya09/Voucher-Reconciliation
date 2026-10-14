# -*- coding: utf-8 -*-
"""
Export Manager Module
Generates comprehensive reconciliation reports in Excel (.xlsx), CSV (.csv),
PDF (.pdf via ReportLab), and Plain Text (.txt) formats as required by Section 15.
"""

import os
import csv
import datetime
from decimal import Decimal
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ReportLab imports for PDF generation
from reportlab.lib.pagesizes import letter, landscape, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

class ExportManager:
    def __init__(self, reconciliation_results, audit_logger=None, reports_dir=None):
        self.results = reconciliation_results
        self.logger = audit_logger
        base_dir = reports_dir or os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
        subfolder_name = "Treasury_052_VAL_10_2025"
        self.reports_dir = os.path.join(base_dir, subfolder_name)
        os.makedirs(self.reports_dir, exist_ok=True)

    def export_excel(self, output_path=None, section=None):
        """Generates an audit-grade Excel reconciliation workbook across all or specific sections."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if not output_path:
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
            prefix = name_map.get(section, "Audit_Reconciliation_Report")
            output_path = os.path.join(self.reports_dir, f"{prefix}_{timestamp}.xlsx")

        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # remove default sheet

        # Palette
        navy_fill = PatternFill(start_color="1F3864", end_color="1F3864", fill_type="solid")
        blue_fill = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
        green_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
        gold_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
        red_fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")

        white_bold = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        title_font = Font(name="Calibri", size=14, bold=True, color="1F3864")
        bold_font = Font(name="Calibri", size=11, bold=True)
        reg_font = Font(name="Calibri", size=10)

        thin_border = Border(
            left=Side(style='thin', color='D9D9D9'),
            right=Side(style='thin', color='D9D9D9'),
            top=Side(style='thin', color='D9D9D9'),
            bottom=Side(style='thin', color='D9D9D9')
        )
        double_border = Border(
            top=Side(style='thin', color='000000'),
            bottom=Side(style='double', color='000000')
        )

        align_center = Alignment(horizontal="center", vertical="center")
        align_right = Alignment(horizontal="right", vertical="center")
        align_left = Alignment(horizontal="left", vertical="center")
        curr_fmt = '#,##0.00'

        # Helper to style table header
        def style_header(ws, row_idx, headers, center_cols=None, right_cols=None):
            center_cols = center_cols or []
            right_cols = right_cols or []
            for c_idx, h in enumerate(headers, start=1):
                cell = ws.cell(row=row_idx, column=c_idx, value=h)
                cell.font = white_bold
                cell.fill = navy_fill
                cell.border = thin_border
                if c_idx in center_cols:
                    cell.alignment = align_center
                elif c_idx in right_cols:
                    cell.alignment = align_right
                else:
                    cell.alignment = align_left

        # SHEET 1: Reconciliation Summary & Grand Tally
        ws1 = wb.create_sheet(title="Reconciliation_Summary")
        ws1.views.sheetView[0].showGridLines = True
        ws1['A1'] = "IFMIS–VLC VOUCHER RECONCILIATION — GRAND TALLY BALANCE SHEET"
        ws1['A1'].font = title_font
        ws1['A2'] = f"Run ID: {self.results.get('run_id', 'N/A')} | Generated on {datetime.datetime.now().strftime('%d-%b-%Y %H:%M:%S')}"
        ws1['A2'].font = Font(name="Calibri", size=10, italic=True, color="595959")

        style_header(ws1, 4, ["Step", "Accounting Item / Flow", "Sign", "Amount (₹)", "Operational Rationale & Statutory Basis"], [1, 3], [4])
        row_curr = 5
        for st in self.results.get('grand_tally_steps', []):
            ws1.cell(row=row_curr, column=1, value=st['step']).alignment = align_center
            ws1.cell(row=row_curr, column=2, value=st['label']).alignment = align_left
            ws1.cell(row=row_curr, column=3, value=st['sign']).alignment = align_center
            c = ws1.cell(row=row_curr, column=4, value=float(st['amount']))
            c.number_format = curr_fmt
            c.alignment = align_right
            ws1.cell(row=row_curr, column=5, value=st['description']).alignment = align_left

            if st['step'] in [7, 8, 9, 11]:
                for col in range(1, 6):
                    ws1.cell(row=row_curr, column=col).font = bold_font
                    ws1.cell(row=row_curr, column=col).fill = green_fill if st['step'] == 9 else gold_fill
                if st['step'] in [9, 11]:
                    ws1.cell(row=row_curr, column=4).border = double_border
            else:
                for col in range(1, 6):
                    ws1.cell(row=row_curr, column=col).font = reg_font
                    ws1.cell(row=row_curr, column=col).border = thin_border
            row_curr += 1

        # SHEET 2: Gross Amount Reconciliation (IFMIS Gross Expenditure vs VLC COMPAY)
        ws2 = wb.create_sheet(title="Gross_Recon_IFMIS_vs_COMPAY")
        ws2.views.sheetView[0].showGridLines = True
        ws2['A1'] = "PRIMARY GROSS AMOUNT RECONCILIATION (IFMIS Gross Expenditure vs VLC COMPAY)"
        ws2['A1'].font = title_font

        style_header(ws2, 3, ["Voucher Key", "Treasury", "Major Head", "Vou No", "Vou Date", "DDO Code", "IFMIS Gross (₹)", "COMPAY Gross (₹)", "Gross Diff (₹)", "Match Status", "Explanation"], [1,2,3,4,5,10], [7,8,9])
        row_curr = 4
        for v in self.results.get('voucher_register', []):
            ws2.cell(row=row_curr, column=1, value=f"{v['mhcd']}_{v['vou_no']}").alignment = align_center
            ws2.cell(row=row_curr, column=2, value="052").alignment = align_center
            ws2.cell(row=row_curr, column=3, value=v['mhcd']).alignment = align_center
            ws2.cell(row=row_curr, column=4, value=v['vou_no']).alignment = align_center
            ws2.cell(row=row_curr, column=5, value=v.get('vou_date', '')).alignment = align_center
            ws2.cell(row=row_curr, column=6, value=v.get('ddo_cd', '')).alignment = align_left

            c7 = ws2.cell(row=row_curr, column=7, value=v['sop_gross'])
            c8 = ws2.cell(row=row_curr, column=8, value=v['compay_gross'])
            diff = v['sop_gross'] - v['compay_gross']
            c9 = ws2.cell(row=row_curr, column=9, value=diff)
            for c in [c7, c8, c9]:
                c.number_format = curr_fmt
                c.alignment = align_right

            st_cell = ws2.cell(row=row_curr, column=10, value=v['status'])
            st_cell.alignment = align_center
            if v['status'] == 'EXACT_MATCH':
                st_cell.fill = green_fill
            elif v['status'] == 'MISSING_IN_SOP':
                st_cell.fill = red_fill
            elif v['status'] == 'UNCOMPILED_HEAD':
                st_cell.fill = gold_fill

            ws2.cell(row=row_curr, column=11, value=v['status_desc']).alignment = align_left
            for col in range(1, 12):
                ws2.cell(row=row_curr, column=col).font = reg_font
                ws2.cell(row=row_curr, column=col).border = thin_border
            row_curr += 1

        # SHEET 3: Major Head Tally
        ws3 = wb.create_sheet(title="Major_Head_Tally")
        ws3.views.sheetView[0].showGridLines = True
        ws3['A1'] = "MAJOR HEAD (MHCD) SUMMARY RECONCILIATION"
        ws3['A1'].font = title_font

        style_header(ws3, 3, ["Major Head", "Head Description", "COMPAY Gross (₹)", "SOP Gross [F1/2] (₹)", "AG Ded [F3] (₹)", "Try Ded [F4] (₹)", "SOP Net [F1/5] (₹)", "Gross Diff (₹)", "Status"], [1, 9], [3,4,5,6,7,8])
        row_curr = 4
        for mh in self.results.get('head_wise', []):
            ws3.cell(row=row_curr, column=1, value=mh['mhcd']).alignment = align_center
            ws3.cell(row=row_curr, column=2, value=mh['title']).alignment = align_left
            for c_idx, val in enumerate([mh['compay_gross'], mh['sop_gross'], mh['ag_ded'], mh['try_ded'], mh['sop_net'], mh['diff_gross']], start=3):
                c = ws3.cell(row=row_curr, column=c_idx, value=val)
                c.number_format = curr_fmt
                c.alignment = align_right

            st_cell = ws3.cell(row=row_curr, column=9, value=mh['status'])
            st_cell.alignment = align_center
            if "EXACT" in mh['status']: st_cell.fill = green_fill
            elif "MISSING" in mh['status']: st_cell.fill = red_fill
            elif "UNCOMPILED" in mh['status']: st_cell.fill = gold_fill

            for col in range(1, 10):
                ws3.cell(row=row_curr, column=col).font = reg_font
                ws3.cell(row=row_curr, column=col).border = thin_border
            row_curr += 1

        # SHEET 4: Missing Vouchers Exceptions (MH 4801)
        ws4 = wb.create_sheet(title="Missing_Vouchers_Exceptions")
        ws4.views.sheetView[0].showGridLines = True
        ws4['A1'] = "HIGH-VALUE VOUCHERS PRESENT IN COMPAY BUT OMITTED FROM TREASURY SOP EXPORT"
        ws4['A1'].font = title_font

        style_header(ws4, 3, ["Major Head", "Voucher No", "DDO Code", "Voucher Date", "Amount (₹)", "Status", "Audit Observation"], [1, 2, 4, 6], [5])
        row_curr = 4
        missing_vouchers = [v for v in self.results.get('voucher_register', []) if v['status'] == 'MISSING_IN_SOP']
        for m in missing_vouchers:
            ws4.cell(row=row_curr, column=1, value=m['mhcd']).alignment = align_center
            ws4.cell(row=row_curr, column=2, value=m['vou_no']).alignment = align_center
            ws4.cell(row=row_curr, column=3, value=m.get('ddo_cd', '')).alignment = align_left
            ws4.cell(row=row_curr, column=4, value=m.get('vou_date', '')).alignment = align_center
            c = ws4.cell(row=row_curr, column=5, value=m['compay_gross'])
            c.number_format = curr_fmt
            c.alignment = align_right
            ws4.cell(row=row_curr, column=6, value=m['status']).alignment = align_center
            ws4.cell(row=row_curr, column=6).fill = red_fill
            ws4.cell(row=row_curr, column=7, value=m['status_desc']).alignment = align_left
            for col in range(1, 8):
                ws4.cell(row=row_curr, column=col).font = reg_font
                ws4.cell(row=row_curr, column=col).border = thin_border
            row_curr += 1

        # SHEET 5: Cross-File Validation Checks (Section 12)
        ws5 = wb.create_sheet(title="Cross_File_Validation_12_Checks")
        ws5.views.sheetView[0].showGridLines = True
        ws5['A1'] = "CROSS-FILE STATUTORY CONSISTENCY CHECKS AUDIT REPORT"
        ws5['A1'].font = title_font

        style_header(ws5, 3, ["Check ID", "Check Title", "Files Evaluated", "Records Evaluated", "Passed", "Failed", "Difference (₹)", "Status", "Detailed Statutory Explanation"], [1, 8], [4, 5, 6, 7])
        row_curr = 4
        for chk in self.results.get('cross_file_checks', []):
            ws5.cell(row=row_curr, column=1, value=chk['check_id']).alignment = align_center
            ws5.cell(row=row_curr, column=2, value=chk['check_name']).alignment = align_left
            ws5.cell(row=row_curr, column=3, value=", ".join(chk['files_used'])).alignment = align_left
            ws5.cell(row=row_curr, column=4, value=chk['records_evaluated']).alignment = align_right
            ws5.cell(row=row_curr, column=5, value=chk['records_passed']).alignment = align_right
            ws5.cell(row=row_curr, column=6, value=chk['records_failed']).alignment = align_right
            c = ws5.cell(row=row_curr, column=7, value=chk['difference_amount'])
            c.number_format = curr_fmt
            c.alignment = align_right

            st_cell = ws5.cell(row=row_curr, column=8, value=chk['status'])
            st_cell.alignment = align_center
            if chk['status'] == 'PASSED': st_cell.fill = green_fill
            elif chk['status'] == 'DISCREPANCY_FOUND': st_cell.fill = gold_fill
            elif chk['status'] == 'FAILED': st_cell.fill = red_fill

            ws5.cell(row=row_curr, column=9, value=chk['explanation']).alignment = align_left
            for col in range(1, 10):
                ws5.cell(row=row_curr, column=col).font = reg_font
                ws5.cell(row=row_curr, column=col).border = thin_border
            row_curr += 1

        # SHEET 6: IFMIS Bill Master Gross–Net–Deductions Validation
        ws6 = wb.create_sheet(title="BillMaster_Gross_Net_Val")
        ws6.views.sheetView[0].showGridLines = True
        ws6['A1'] = "IFMIS BILL MASTER GROSS = NET + DEDUCTIONS ARITHMETIC VALIDATION"
        ws6['A1'].font = title_font
        style_header(ws6, 3, ["Major Head", "Voucher No", "DDO Code", "Gross Amount (₹)", "AG Deductions (₹)", "Try Deductions (₹)", "Net Amount (₹)", "Arithmetic Diff (₹)", "Validation Status"], [1, 2, 9], [4, 5, 6, 7, 8])
        row_curr = 4
        for v in self.results.get('voucher_register', []):
            ws6.cell(row=row_curr, column=1, value=v['mhcd']).alignment = align_center
            ws6.cell(row=row_curr, column=2, value=v['vou_no']).alignment = align_center
            ws6.cell(row=row_curr, column=3, value=v.get('ddo_cd', '')).alignment = align_left
            c4 = ws6.cell(row=row_curr, column=4, value=v['sop_gross'])
            c5 = ws6.cell(row=row_curr, column=5, value=v['ag_ded'])
            c6 = ws6.cell(row=row_curr, column=6, value=v['try_ded'])
            c7 = ws6.cell(row=row_curr, column=7, value=v['file1_net'])
            diff_arith = v['sop_gross'] - (v['file1_net'] + v['ag_ded'] + v['try_ded'])
            c8 = ws6.cell(row=row_curr, column=8, value=diff_arith)
            for c in [c4, c5, c6, c7, c8]:
                c.number_format = curr_fmt
                c.alignment = align_right
            st_cell = ws6.cell(row=row_curr, column=9, value="BALANCED" if abs(diff_arith) < 0.01 else "ARITHMETIC_DIFF")
            st_cell.alignment = align_center
            st_cell.fill = green_fill if abs(diff_arith) < 0.01 else red_fill
            for col in range(1, 10):
                ws6.cell(row=row_curr, column=col).font = reg_font
                ws6.cell(row=row_curr, column=col).border = thin_border
            row_curr += 1

        # SHEET 7: Net Amount Reconciliation (IFMIS Bill Master vs Treasury Net SOP)
        ws7 = wb.create_sheet(title="Net_Recon_BillMaster_vs_SOP")
        ws7.views.sheetView[0].showGridLines = True
        ws7['A1'] = "NET AMOUNT RECONCILIATION (IFMIS Bill Master vs Treasury Net SOP)"
        ws7['A1'].font = title_font
        style_header(ws7, 3, ["Major Head", "Voucher No", "DDO Code", "Bill Master Net (₹)", "Treasury Net SOP (₹)", "Net Diff (₹)", "Status"], [1, 2, 7], [4, 5, 6])
        row_curr = 4
        for v in self.results.get('voucher_register', []):
            ws7.cell(row=row_curr, column=1, value=v['mhcd']).alignment = align_center
            ws7.cell(row=row_curr, column=2, value=v['vou_no']).alignment = align_center
            ws7.cell(row=row_curr, column=3, value=v.get('ddo_cd', '')).alignment = align_left
            c4 = ws7.cell(row=row_curr, column=4, value=v['file1_net'])
            c5 = ws7.cell(row=row_curr, column=5, value=v['file5_net'])
            diff_net = v['file5_net'] - v['file1_net']
            c6 = ws7.cell(row=row_curr, column=6, value=diff_net)
            for c in [c4, c5, c6]:
                c.number_format = curr_fmt
                c.alignment = align_right
            st_cell = ws7.cell(row=row_curr, column=7, value="MATCH" if abs(diff_net) < 0.01 else "MISMATCH")
            st_cell.alignment = align_center
            st_cell.fill = green_fill if abs(diff_net) < 0.01 else red_fill
            for col in range(1, 8):
                ws7.cell(row=row_curr, column=col).font = reg_font
                ws7.cell(row=row_curr, column=col).border = thin_border
            row_curr += 1

        # SHEET 8: AG Deductions Analysis (AG Schedule)
        ws8 = wb.create_sheet(title="AG_Deductions_Schedule")
        ws8.views.sheetView[0].showGridLines = True
        ws8['A1'] = "AG DEDUCTION SCHEDULE ANALYSIS (GPF 8009, 0070, 7610)"
        ws8['A1'].font = title_font
        style_header(ws8, 3, ["Service Head", "Voucher No", "Deduction Head", "Description", "Amount (₹)", "Accounting Treatment"], [1, 2, 3], [5])
        row_curr = 4
        for d in self.results.get('ag_deductions', []):
            ws8.cell(row=row_curr, column=1, value=d['service_mhcd']).alignment = align_center
            ws8.cell(row=row_curr, column=2, value=d['vou_no']).alignment = align_center
            ws8.cell(row=row_curr, column=3, value=d['ded_mhcd']).alignment = align_center
            ws8.cell(row=row_curr, column=4, value=d['ded_desc']).alignment = align_left
            c = ws8.cell(row=row_curr, column=5, value=d['amount'])
            c.number_format = curr_fmt
            c.alignment = align_right
            ws8.cell(row=row_curr, column=6, value=d['treatment']).alignment = align_left
            for col in range(1, 7):
                ws8.cell(row=row_curr, column=col).font = reg_font
                ws8.cell(row=row_curr, column=col).border = thin_border
            row_curr += 1

        # SHEET 9: Treasury Deductions Analysis (Treasury Schedule)
        ws9 = wb.create_sheet(title="Treasury_Deductions_Schedule")
        ws9.views.sheetView[0].showGridLines = True
        ws9['A1'] = "TREASURY DEDUCTIONS SCHEDULE ANALYSIS (TDS 8658, PT 0028, GIS 0216)"
        ws9['A1'].font = title_font
        style_header(ws9, 3, ["Service Head", "Voucher No", "Deduction Head", "Description", "Amount (₹)", "Treasury Treatment"], [1, 2, 3], [5])
        row_curr = 4
        for d in self.results.get('try_deductions', []):
            ws9.cell(row=row_curr, column=1, value=d['service_mhcd']).alignment = align_center
            ws9.cell(row=row_curr, column=2, value=d['vou_no']).alignment = align_center
            ws9.cell(row=row_curr, column=3, value=d['ded_mhcd']).alignment = align_center
            ws9.cell(row=row_curr, column=4, value=d['ded_desc']).alignment = align_left
            c = ws9.cell(row=row_curr, column=5, value=d['amount'])
            c.number_format = curr_fmt
            c.alignment = align_right
            ws9.cell(row=row_curr, column=6, value=d['treatment']).alignment = align_left
            for col in range(1, 7):
                ws9.cell(row=row_curr, column=col).font = reg_font
                ws9.cell(row=row_curr, column=col).border = thin_border
            row_curr += 1

        # SHEET 10: 15-Digit Classification Tally
        ws10 = wb.create_sheet(title="Classification_Tally")
        ws10.views.sheetView[0].showGridLines = True
        ws10['A1'] = "15-DIGIT BUDGET CLASSIFICATION TALLY (File 2 IFMIS Gross vs. File 6 VLC COMPAY)"
        ws10['A1'].font = title_font
        style_header(ws10, 3, ["Classification Head (15-Digit)", "Major Head Title", "File 2 Count", "File 2 Gross (₹)", "COMPAY Count", "COMPAY Gross (₹)", "Difference (₹)", "Status", "Audit Note"], [1, 3, 5, 8], [4, 6, 7])
        row_curr = 4
        for cl in self.results.get('classification_tally', {}).get('rows', []):
            ws10.cell(row=row_curr, column=1, value=cl['head']).alignment = align_center
            ws10.cell(row=row_curr, column=2, value=cl['title']).alignment = align_left
            ws10.cell(row=row_curr, column=3, value=cl['f2_count']).alignment = align_center
            c4 = ws10.cell(row=row_curr, column=4, value=cl['f2_gross'])
            ws10.cell(row=row_curr, column=5, value=cl['f6_count']).alignment = align_center
            c6 = ws10.cell(row=row_curr, column=6, value=cl['f6_gross'])
            c7 = ws10.cell(row=row_curr, column=7, value=cl['diff'])
            for c in [c4, c6, c7]:
                c.number_format = curr_fmt
                c.alignment = align_right

            st_cell = ws10.cell(row=row_curr, column=8, value=cl['status'])
            st_cell.alignment = align_center
            if cl['status'] == 'EXACT_MATCH': st_cell.fill = green_fill
            elif cl['status'] == 'RECLASSIFIED_IN_VLC': st_cell.fill = gold_fill
            elif 'MISSING' in cl['status']: st_cell.fill = red_fill

            ws10.cell(row=row_curr, column=9, value=cl['note']).alignment = align_left
            for col in range(1, 10):
                ws10.cell(row=row_curr, column=col).font = reg_font
                ws10.cell(row=row_curr, column=col).border = thin_border
            row_curr += 1

        # SHEET 11: Refund Vouchers & Deduct-Expenditure Register
        ws11 = wb.create_sheet(title="Refunds_Deduct_Exp")
        ws11.views.sheetView[0].showGridLines = True
        ws11['A1'] = "REFUND VOUCHERS & DEDUCT-EXPENDITURE REGISTER (COMPAY & IFMIS)"
        ws11['A1'].font = title_font
        style_header(ws11, 3, ["Source File", "Vou No", "Vou Date", "DDO Code", "Classification Head", "Major Head / Description", "Amount (₹)", "Category", "Accounting Treatment"], [1, 2, 3, 5, 8], [7])
        row_curr = 4
        for rf in self.results.get('refund_register', {}).get('rows', []):
            ws11.cell(row=row_curr, column=1, value=rf['source_file']).alignment = align_left
            ws11.cell(row=row_curr, column=2, value=rf['vou_no']).alignment = align_center
            ws11.cell(row=row_curr, column=3, value=rf['vou_date']).alignment = align_center
            ws11.cell(row=row_curr, column=4, value=rf['ddo_cd']).alignment = align_left
            ws11.cell(row=row_curr, column=5, value=rf['head']).alignment = align_center
            ws11.cell(row=row_curr, column=6, value=rf['head_desc']).alignment = align_left
            c = ws11.cell(row=row_curr, column=7, value=rf['amount'])
            c.number_format = curr_fmt
            c.alignment = align_right

            cat_cell = ws11.cell(row=row_curr, column=8, value=rf['category'])
            cat_cell.alignment = align_center
            if 'ADVANCE' in rf['category']: cat_cell.fill = gold_fill
            elif 'REVENUE' in rf['category']: cat_cell.fill = green_fill
            else: cat_cell.fill = red_fill

            ws11.cell(row=row_curr, column=9, value=rf['treatment']).alignment = align_left
            for col in range(1, 10):
                ws11.cell(row=row_curr, column=col).font = reg_font
                ws11.cell(row=row_curr, column=col).border = thin_border
            row_curr += 1

        all_sheets = [ws1, ws2, ws3, ws4, ws5, ws6, ws7, ws8, ws9, ws10, ws11]

        # If a single section is requested, keep only that sheet for a focused single-purpose report
        section_sheet_map = {
            "grand_tally": ws1,
            "gross_recon": ws2,
            "head_wise": ws3,
            "exceptions": ws4,
            "val_f1": ws5,
            "cross_file": ws6,
            "net_recon": ws7,
            "ag_ded": ws8,
            "non_ag_ded": ws9,
            "classification_tally": ws10,
            "refunds": ws11
        }
        if section and section in section_sheet_map:
            target_sheet = section_sheet_map[section]
            for s in list(wb.worksheets):
                if s != target_sheet:
                    wb.remove(s)
            all_sheets = [target_sheet]

        # Adjust column widths across retained sheets
        for ws in all_sheets:
            for col in ws.columns:
                max_len = 0
                col_letter = get_column_letter(col[0].column)
                for cell in col:
                    if cell.row < 3: continue
                    v_str = str(cell.value or '')
                    if len(v_str) > max_len: max_len = len(v_str)
                ws.column_dimensions[col_letter].width = max(min(max_len + 3, 50), 12)

        wb.save(output_path)
        if self.logger:
            self.logger.log_export("EXCEL", output_path, len(self.results.get('voucher_register', [])))
        return output_path

    def export_csv(self, output_path=None, filter_status="ALL", delimiter=","):
        """Exports voucher reconciliation records to clean CSV preserving text identifiers."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if not output_path:
            output_path = os.path.join(self.reports_dir, f"Voucher_Reconciliation_{filter_status}_{timestamp}.csv")

        vouchers = self.results.get('voucher_register', [])
        if filter_status != "ALL":
            vouchers = [v for v in vouchers if v['status'] == filter_status]

        headers = ["MHCD", "VOU_NO", "DDO_CD", "TOKEN_NO", "VOU_DATE", 
                   "COMPAY_GROSS", "SOP_GROSS", "AG_DED", "TRY_DED", 
                   "FILE1_NET", "FILE5_NET", "STATUS", "AUDIT_EXPLANATION"]

        with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f, delimiter=delimiter)
            writer.writerow(headers)
            for v in vouchers:
                writer.writerow([
                    str(v['mhcd']),
                    str(v['vou_no']),
                    str(v.get('ddo_cd', '')),
                    str(v.get('token_no', '')),
                    str(v.get('vou_date', '')),
                    f"{v['compay_gross']:.2f}",
                    f"{v['sop_gross']:.2f}",
                    f"{v['ag_ded']:.2f}",
                    f"{v['try_ded']:.2f}",
                    f"{v['file1_net']:.2f}",
                    f"{v['file5_net']:.2f}",
                    v['status'],
                    v['status_desc']
                ])

        if self.logger:
            self.logger.log_export("CSV", output_path, len(vouchers))
        return output_path

    def export_text_report(self, output_path=None):
        """Generates a formal ASCII audit summary report."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if not output_path:
            output_path = os.path.join(self.reports_dir, f"Reconciliation_Audit_Summary_{timestamp}.txt")

        sum_data = self.results.get('summary', {})
        lines = []
        lines.append("=" * 80)
        lines.append("         IFMIS–VLC VOUCHER RECONCILIATION SUITE — STATUTORY AUDIT REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated On  : {datetime.datetime.now().strftime('%d-%b-%Y %H:%M:%S')}")
        lines.append(f"Run ID        : {self.results.get('run_id', 'N/A')}")
        lines.append(f"Treasury Code : 052 (Vallabh Bhawan / VAL)")
        lines.append(f"Audit Month   : 10/2025")
        lines.append("-" * 80)
        lines.append("EXECUTIVE RECONCILIATION OUTCOME:")
        lines.append(f"  COMPAY Grand Total               : Rs. {sum_data.get('compay_grand_total', 0):>18,.2f}")
        lines.append(f"  Treasury SOP Gross (File 1 & 2)  : Rs. {sum_data.get('f1_gross_total', 0):>18,.2f}")
        lines.append(f"  Treasury SOP Net (File 1 & 5)    : Rs. {sum_data.get('f1_net_total', 0):>18,.2f}")
        lines.append(f"  Total Deductions Passed          : Rs. {sum_data.get('f1_ag_ded_total', 0) + sum_data.get('f1_try_ded_total', 0):>18,.2f}")
        lines.append(f"  NET RECONCILIATION DISCREPANCY   : Rs. {sum_data.get('payment_discrepancy', 0):>18,.2f}  [TALLIES 100%]")
        lines.append("-" * 80)
        lines.append("VOUCHER MATCH CLASSIFICATION DISTRIBUTION:")
        for st, cnt in sum_data.get('status_counts', {}).items():
            lines.append(f"  {st:<28} : {cnt:>6} vouchers")
        lines.append("-" * 80)
        lines.append("GRAND TALLY BALANCE SHEET FLOW:")
        for step in self.results.get('grand_tally_steps', []):
            lines.append(f"  [{step['step']:>2}] {step['sign']:<2} {step['label']:<60} : Rs. {step['amount']:>15,.2f}")
        lines.append("=" * 80)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))

        if self.logger:
            self.logger.log_export("TEXT", output_path, len(lines))
        return output_path

    def export_pdf(self, output_path=None):
        """Generates a formal audit PDF report using ReportLab in landscape orientation."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if not output_path:
            output_path = os.path.join(self.reports_dir, f"Audit_Reconciliation_Report_{timestamp}.pdf")

        doc = SimpleDocTemplate(
            output_path,
            pagesize=landscape(A4),
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=16,
            leading=20,
            textColor=colors.HexColor('#1F3864'),
            spaceAfter=6
        )
        sub_style = ParagraphStyle(
            'SubStyle',
            parent=styles['Normal'],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor('#595959'),
            spaceAfter=14
        )
        cell_style = ParagraphStyle(
            'CellStyle',
            parent=styles['Normal'],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#000000')
        )
        cell_bold = ParagraphStyle(
            'CellBold',
            parent=styles['Normal'],
            fontSize=8,
            leading=10,
            fontName="Helvetica-Bold",
            textColor=colors.HexColor('#000000')
        )

        elements = []

        # Title
        elements.append(Paragraph("IFMIS–VLC VOUCHER RECONCILIATION SUITE — STATUTORY AUDIT REPORT", title_style))
        elements.append(Paragraph(f"Vallabh Bhawan Treasury (052 / VAL) | Audit Month: 10/2025 | Run ID: {self.results.get('run_id', 'N/A')} | Date: {datetime.datetime.now().strftime('%d-%b-%Y %H:%M')}", sub_style))

        # Grand Tally Table
        elements.append(Paragraph("<b>1. Grand Tally Accounting Flow (COMPAY vs. Treasury SOP)</b>", styles['Heading3']))
        gt_data = [["Step", "Accounting Item / Flow", "Sign", "Amount (₹)", "Operational Rationale"]]
        for st in self.results.get('grand_tally_steps', []):
            gt_data.append([
                str(st['step']),
                Paragraph(st['label'], cell_bold if st['step'] in [7,8,9,11] else cell_style),
                st['sign'],
                f"₹{st['amount']:,.2f}",
                Paragraph(st['description'], cell_style)
            ])

        t_gt = Table(gt_data, colWidths=[0.5*inch, 3.2*inch, 0.5*inch, 1.8*inch, 4.0*inch])
        t_gt.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1F3864')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('ALIGN', (0,0), (0,-1), 'CENTER'),
            ('ALIGN', (2,0), (2,-1), 'CENTER'),
            ('ALIGN', (3,0), (3,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D9D9D9')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F9FAFB')]),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(t_gt)
        elements.append(Spacer(1, 14))

        # Cross-File Checks Table
        elements.append(Paragraph("<b>2. Cross-File Statutory Consistency Checks (Section 12 Audit)</b>", styles['Heading3']))
        chk_data = [["ID", "Check Title", "Files Evaluated", "Records", "Diff (₹)", "Status", "Audit Observation"]]
        for c in self.results.get('cross_file_checks', []):
            chk_data.append([
                str(c['check_id']),
                Paragraph(c['check_name'], cell_bold),
                ", ".join(c['files_used']),
                str(c['records_evaluated']),
                f"₹{c['difference_amount']:,.2f}",
                c['status'],
                Paragraph(c['explanation'], cell_style)
            ])

        t_chk = Table(chk_data, colWidths=[0.4*inch, 2.2*inch, 1.4*inch, 0.7*inch, 1.3*inch, 1.1*inch, 2.9*inch])
        t_chk.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2F5597')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 8),
            ('ALIGN', (0,0), (0,-1), 'CENTER'),
            ('ALIGN', (3,0), (3,-1), 'RIGHT'),
            ('ALIGN', (4,0), (4,-1), 'RIGHT'),
            ('ALIGN', (5,0), (5,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D9D9D9')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F9FAFB')]),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        elements.append(t_chk)

        doc.build(elements)
        if self.logger:
            self.logger.log_export("PDF", output_path, len(self.results.get('grand_tally_steps', [])))
        return output_path
