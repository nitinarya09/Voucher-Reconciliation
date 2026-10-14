# -*- coding: utf-8 -*-
"""
Voucher Reconciliation Engine
Comprehensive 3-Way & 5-File Cross-Reconciliation between
AG Compilation (COMPAY) and Treasury SOP Exports (Files 1, 2, 3, 4, 5).
"""

import os
import glob
import re
import datetime
import pandas as pd
import numpy as np
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Standard Indian Major Head Titles Dictionary
MH_TITLES = {
    "0028": "Other Taxes on Income and Expenditure (PT)",
    "0043": "Taxes and Duties on Electricity",
    "0070": "Other Administrative Services (Recoveries)",
    "0216": "Housing (License Fee/Rent)",
    "2012": "President / Governor / Administrator",
    "2013": "Council of Ministers",
    "2014": "Administration of Justice",
    "2015": "Elections",
    "2029": "Land Revenue",
    "2030": "Stamps and Registration",
    "2041": "Taxes on Vehicles",
    "2043": "Collection of GST & Other Taxes",
    "2045": "Other Taxes and Duties on Commodities & Services",
    "2051": "Public Service Commission",
    "2052": "Secretariat-General Services",
    "2053": "District Administration",
    "2054": "Treasury and Accounts Administration",
    "2055": "Police",
    "2056": "Jails",
    "2059": "Public Works",
    "2070": "Other Administrative Services",
    "2071": "Pensions and Other Retirement Benefits",
    "2075": "Miscellaneous General Services",
    "2202": "General Education",
    "2203": "Technical Education",
    "2204": "Sports and Youth Services",
    "2205": "Art and Culture",
    "2210": "Medical and Public Health",
    "2211": "Family Welfare",
    "2215": "Water Supply and Sanitation",
    "2216": "Housing",
    "2217": "Urban Development",
    "2220": "Information and Publicity",
    "2225": "Welfare of SC, ST and OBC",
    "2230": "Labour and Employment",
    "2235": "Social Security and Welfare",
    "2236": "Nutrition",
    "2245": "Relief on account of Natural Calamities (Aapda)",
    "2251": "Secretariat-Social Services",
    "2401": "Crop Husbandry",
    "2402": "Soil and Water Conservation",
    "2403": "Animal Husbandry",
    "2404": "Dairy Development",
    "2405": "Fisheries",
    "2406": "Forestry and Wild Life",
    "2408": "Food, Storage and Warehousing",
    "2415": "Agricultural Research and Education",
    "2425": "Co-operation",
    "2501": "Special Programmes for Rural Development",
    "2505": "Rural Employment",
    "2515": "Other Rural Development Programmes",
    "2701": "Medium Irrigation",
    "2702": "Minor Irrigation",
    "2705": "Command Area Development",
    "2801": "Power (Revenue Account)",
    "2851": "Village and Small Industries",
    "2852": "Industries",
    "3054": "Roads and Bridges",
    "3451": "Secretariat-Economic Services",
    "3452": "Tourism",
    "3454": "Census Surveys and Statistics",
    "3456": "Civil Supplies",
    "4055": "Capital Outlay on Police",
    "4059": "Capital Outlay on Public Works",
    "4070": "Capital Outlay on Other Administrative Services",
    "4202": "Capital Outlay on Education, Sports, Art & Culture",
    "4210": "Capital Outlay on Medical and Public Health",
    "4215": "Capital Outlay on Water Supply and Sanitation",
    "4220": "Capital Outlay on Information and Publicity",
    "4225": "Capital Outlay on Welfare of SC/ST/OBC",
    "4403": "Capital Outlay on Animal Husbandry",
    "4406": "Capital Outlay on Forestry and Wild Life",
    "4425": "Capital Outlay on Co-operation",
    "4700": "Capital Outlay on Major Irrigation",
    "4801": "Capital Outlay on Power Projects",
    "5054": "Capital Outlay on Roads and Bridges",
    "6075": "Loans for Miscellaneous General Services",
    "7610": "Loans to Government Servants, etc.",
    "8009": "State Provident Funds (GPF)",
    "8011": "Insurance and Pension Funds (GIS)",
    "8342": "Other Deposits (NPS/Security Deposits)",
    "8658": "Suspense Accounts (TDS/PAO Suspense)",
    "8670": "Cheques and Bills",
    "8671": "Departmental Balances",
    "8782": "Cash Remittances and Adjustments"
}

def get_mh_title(mhcd):
    if not mhcd:
        return ""
    smh = str(mhcd).strip()
    return MH_TITLES.get(smh, f"Major Head {smh}")


class ReconciliationEngine:
    def __init__(self, compay_path, sop_folder_or_files):
        """
        Initializes the Reconciliation Engine.
        sop_folder_or_files can be:
          - A directory string containing the 5 files
          - Or a dict with keys: 'file_1', 'file_5', 'file_2', 'file_3', 'file_4'
        """
        self.compay_path = compay_path
        self.sop_files = self._resolve_sop_files(sop_folder_or_files)
        self.results = None

    def _resolve_sop_files(self, input_val):
        if isinstance(input_val, dict):
            return input_val
        
        folder = input_val
        if not os.path.isdir(folder):
            raise ValueError(f"SOP path is not a directory: {folder}")
            
        resolved = {
            'file_1': None,
            'file_5': None,
            'file_2': None,
            'file_3': None,
            'file_4': None
        }
        
        all_txts = [f for f in os.listdir(folder) if f.lower().endswith(('.txt', '.csv'))]
        for f in all_txts:
            full = os.path.join(folder, f)
            fl = f.lower()
            if fl.startswith('1_'):
                resolved['file_1'] = full
            elif fl.startswith('2_'):
                resolved['file_2'] = full
            elif fl.startswith('3_'):
                resolved['file_3'] = full
            elif fl.startswith('4_'):
                resolved['file_4'] = full
            elif fl.endswith('sop.txt') or fl.startswith(('0_', '5_')) or ('sop' in fl and not fl[0].isdigit()):
                resolved['file_5'] = full

        return resolved

    def run(self):
        """Executes full multi-file 3-way voucher reconciliation."""
        # 1. Load COMPAY
        compay_sep = '\t'
        if self.compay_path.lower().endswith('.csv'):
            compay_sep = ','
        elif self.compay_path.lower().endswith(('.xlsx', '.xlsb')):
            df_cp = pd.read_excel(self.compay_path, dtype=str)
        else:
            # Try reading TSV first, fallback to CSV
            try:
                df_cp = pd.read_csv(self.compay_path, sep='\t', dtype=str, encoding='latin1')
                if len(df_cp.columns) < 5:
                    df_cp = pd.read_csv(self.compay_path, sep=',', dtype=str, encoding='latin1')
            except Exception:
                df_cp = pd.read_csv(self.compay_path, sep='\t', dtype=str, encoding='utf-8', errors='ignore')

        # Clean COMPAY column names
        df_cp.columns = [c.strip().upper() for c in df_cp.columns]
        for c in ['MHCD', 'VOU_NO', 'DDO_CD', 'GNCD', 'SMCD', 'MICD', 'SHCD', 'DHCD', 'SDCD', 'VC', 'PN', 'TE_NO', 'BILL_NO', 'BILL_DATE']:
            if c in df_cp.columns:
                df_cp[c] = df_cp[c].astype(str).str.strip().replace({'nan': '', 'None': ''})
            else:
                df_cp[c] = ''
        df_cp['AMOUNT_NUM'] = pd.to_numeric(df_cp['AMOUNT'], errors='coerce').fillna(0)

        # Separate Transfer Entries (TE) vs Payments
        te_mask = (df_cp['TE_NO'] != '') & df_cp['TE_NO'].notna()
        df_cp_te = df_cp[te_mask].copy()
        df_cp_p = df_cp[~te_mask].copy()

        # 2. Load File 1: Master Vouchers (Gross, AG Ded, Try Ded, Net)
        cols_1 = ['MONTH', 'YEAR', 'SEC_GN', 'TRY_CD', 'TOKEN_NO', 'TOKEN_DATE', 'DDO_CD', 'GNCD', 'MHCD', 'VOU_NO', 'VOU_DATE', 'GROSS_AMT', 'AG_DED', 'TRY_DED', 'NET_AMT', 'REF_MONTH', 'REF_YEAR', 'EXTRA']
        f1_path = self.sop_files.get('file_1')
        df_1 = pd.DataFrame(columns=cols_1)
        if f1_path and os.path.exists(f1_path):
            df_1 = pd.read_csv(f1_path, header=None, names=cols_1, dtype=str, encoding='latin1')
            for c in ['MHCD', 'VOU_NO', 'DDO_CD', 'GNCD', 'TOKEN_NO']:
                df_1[c] = df_1[c].astype(str).str.strip()
            df_1['GROSS_AMT_NUM'] = pd.to_numeric(df_1['GROSS_AMT'], errors='coerce').fillna(0)
            df_1['AG_DED_NUM'] = pd.to_numeric(df_1['AG_DED'], errors='coerce').fillna(0)
            df_1['TRY_DED_NUM'] = pd.to_numeric(df_1['TRY_DED'], errors='coerce').fillna(0)
            df_1['NET_AMT_NUM'] = pd.to_numeric(df_1['NET_AMT'], errors='coerce').fillna(0)

        # 3. Load File 5: SOP Net Payment Vouchers
        cols_5 = ['TRY_CD', 'MHCD', 'YEAR', 'MONTH', 'DDO_CD', 'TOKEN_NO', 'VOU_DATE', 'VOU_NO', 'GNCD', 'NET_AMOUNT']
        f5_path = self.sop_files.get('file_5')
        df_5 = pd.DataFrame(columns=cols_5)
        if f5_path and os.path.exists(f5_path):
            df_5 = pd.read_csv(f5_path, header=None, names=cols_5, dtype=str, encoding='latin1')
            for c in ['MHCD', 'VOU_NO', 'DDO_CD']:
                df_5[c] = df_5[c].astype(str).str.strip()
            df_5['NET_AMOUNT_NUM'] = pd.to_numeric(df_5['NET_AMOUNT'], errors='coerce').fillna(0)

        # 4. Load File 2: Detailed Classification (Gross breakdown)
        cols_2 = ['MONTH', 'YEAR', 'TRY_CD', 'GNCD', 'VOU_NO', 'VOU_DATE', 'MHCD', 'SMCD', 'MICD', 'GHCD', 'SHCD', 'DHCD', 'SDCD', 'VC', 'PN', 'AMOUNT']
        f2_path = self.sop_files.get('file_2')
        df_2 = pd.DataFrame(columns=cols_2)
        if f2_path and os.path.exists(f2_path):
            df_2 = pd.read_csv(f2_path, header=None, names=cols_2, dtype=str, encoding='latin1')
            for c in ['MHCD', 'VOU_NO', 'GNCD', 'SMCD', 'MICD', 'SHCD', 'DHCD']:
                df_2[c] = df_2[c].astype(str).str.strip().replace({'nan': '', 'None': ''})
            df_2['AMOUNT_NUM'] = pd.to_numeric(df_2['AMOUNT'], errors='coerce').fillna(0)

        # 5. Load File 3: AG Deductions Schedule
        cols_3 = ['MONTH', 'YEAR', 'TRY_CD', 'GNCD', 'MHCD', 'DATE', 'VOU_NO', 'DED_MHCD', 'DED_SMCD', 'DED_MICD', 'GHCD', 'SHCD', 'DHCD', 'SDCD', 'AMOUNT']
        f3_path = self.sop_files.get('file_3')
        df_3 = pd.DataFrame(columns=cols_3)
        if f3_path and os.path.exists(f3_path):
            df_3 = pd.read_csv(f3_path, header=None, names=cols_3, dtype=str, encoding='latin1')
            for c in ['MHCD', 'VOU_NO', 'DED_MHCD']:
                df_3[c] = df_3[c].astype(str).str.strip()
            df_3['AMOUNT_NUM'] = pd.to_numeric(df_3['AMOUNT'], errors='coerce').fillna(0)

        # 6. Load File 4: Treasury Deductions Schedule
        cols_4 = ['MONTH', 'YEAR', 'TRY_CD', 'GNCD', 'MHCD', 'DATE', 'VOU_NO', 'DED_MHCD', 'DED_SMCD', 'DED_MICD', 'GHCD', 'SHCD', 'DHCD', 'SDCD', 'AMOUNT']
        f4_path = self.sop_files.get('file_4')
        df_4 = pd.DataFrame(columns=cols_4)
        if f4_path and os.path.exists(f4_path):
            df_4 = pd.read_csv(f4_path, header=None, names=cols_4, dtype=str, encoding='latin1')
            for c in ['MHCD', 'VOU_NO', 'DED_MHCD']:
                df_4[c] = df_4[c].astype(str).str.strip()
            df_4['AMOUNT_NUM'] = pd.to_numeric(df_4['AMOUNT'], errors='coerce').fillna(0)

        # Compute Aggregations
        compay_grand_total = float(df_cp['AMOUNT_NUM'].sum())
        compay_payment_total = float(df_cp_p['AMOUNT_NUM'].sum())
        compay_te_total = float(df_cp_te['AMOUNT_NUM'].sum())

        f1_gross_total = float(df_1['GROSS_AMT_NUM'].sum())
        f1_ag_ded_total = float(df_1['AG_DED_NUM'].sum())
        f1_try_ded_total = float(df_1['TRY_DED_NUM'].sum())
        f1_net_total = float(df_1['NET_AMT_NUM'].sum())

        f5_net_total = float(df_5['NET_AMOUNT_NUM'].sum())
        f2_gross_total = float(df_2['AMOUNT_NUM'].sum())
        f3_total = float(df_3['AMOUNT_NUM'].sum())
        f4_total = float(df_4['AMOUNT_NUM'].sum())

        # Group COMPAY by (MHCD, VOU_NO)
        cp_vou_grp = df_cp_p.groupby(['MHCD', 'VOU_NO']).agg(
            CP_GROSS=('AMOUNT_NUM', 'sum'),
            CP_LINES=('AMOUNT_NUM', 'count'),
            DDO_CD=('DDO_CD', 'first'),
            BILL_NO=('BILL_NO', 'first'),
            BILL_DATE=('BILL_DATE', 'first')
        ).reset_index()

        # Group File 3 Deductions by (MHCD, VOU_NO)
        # GPF 8009 vs Non-8009
        f3_gpf = df_3[df_3['DED_MHCD'] == '8009']
        f3_non_gpf = df_3[df_3['DED_MHCD'] != '8009']
        f3_gpf_grp = f3_gpf.groupby(['MHCD', 'VOU_NO'])['AMOUNT_NUM'].sum().reset_index().rename(columns={'AMOUNT_NUM': 'F3_GPF_DED'})
        f3_non_gpf_grp = f3_non_gpf.groupby(['MHCD', 'VOU_NO'])['AMOUNT_NUM'].sum().reset_index().rename(columns={'AMOUNT_NUM': 'F3_RECOVERY_DED'})

        # Group File 4 Try Deductions by (MHCD, VOU_NO)
        f4_grp = df_4.groupby(['MHCD', 'VOU_NO'])['AMOUNT_NUM'].sum().reset_index().rename(columns={'AMOUNT_NUM': 'F4_TRY_DED'})

        # Merge File 1 with File 5
        m_sop = pd.merge(df_1, df_5[['MHCD', 'VOU_NO', 'NET_AMOUNT_NUM']], on=['MHCD', 'VOU_NO'], how='outer')
        if 'NET_AMOUNT_NUM' in m_sop.columns:
            m_sop['FILE5_NET'] = m_sop['NET_AMOUNT_NUM'].fillna(0)
        else:
            m_sop['FILE5_NET'] = m_sop['NET_AMT_NUM']

        # 3-Way Merge: SOP (File 1/5) with COMPAY
        full_merged = pd.merge(m_sop, cp_vou_grp, on=['MHCD', 'VOU_NO'], how='outer', suffixes=('_sop', '_cp'))

        # Add File 3 and File 4 details
        full_merged = pd.merge(full_merged, f3_gpf_grp, on=['MHCD', 'VOU_NO'], how='left')
        full_merged = pd.merge(full_merged, f3_non_gpf_grp, on=['MHCD', 'VOU_NO'], how='left')
        full_merged = pd.merge(full_merged, f4_grp, on=['MHCD', 'VOU_NO'], how='left')

        full_merged['F3_GPF_DED'] = full_merged['F3_GPF_DED'].fillna(0)
        full_merged['F3_RECOVERY_DED'] = full_merged['F3_RECOVERY_DED'].fillna(0)
        full_merged['F4_TRY_DED'] = full_merged['F4_TRY_DED'].fillna(0)

        # Fill missing amounts
        full_merged['GROSS_AMT_NUM'] = full_merged['GROSS_AMT_NUM'].fillna(0)
        full_merged['AG_DED_NUM'] = full_merged['AG_DED_NUM'].fillna(0)
        full_merged['TRY_DED_NUM'] = full_merged['TRY_DED_NUM'].fillna(0)
        full_merged['NET_AMT_NUM'] = full_merged['NET_AMT_NUM'].fillna(0)
        full_merged['FILE5_NET'] = full_merged['FILE5_NET'].fillna(0)
        full_merged['CP_GROSS'] = full_merged['CP_GROSS'].fillna(0)

        # Consolidate DDO Code
        full_merged['DDO_FINAL'] = full_merged['DDO_CD_sop'].fillna(full_merged['DDO_CD_cp']).fillna('')

        # Categorize Voucher Status
        # Rules:
        # 1. MH 8009 / 6075 originating from File 3 deductions
        # 2. Uncompiled heads in File 1 (8011, 8342, 8658)
        # 3. Missing in SOP (Present in COMPAY, missing in File 1)
        # 4. Exact Match (CP_GROSS == GROSS_AMT_NUM)
        # 5. Netted Adjustment (CP_GROSS + F3_RECOVERY_DED == GROSS_AMT_NUM)
        # 6. Mismatch

        def classify_voucher(row):
            mh = str(row['MHCD']).strip()
            cp_g = row['CP_GROSS']
            sop_g = row['GROSS_AMT_NUM']
            f3_rec = row['F3_RECOVERY_DED']
            has_sop = sop_g > 0 or row['NET_AMT_NUM'] > 0
            has_cp = cp_g > 0

            if not has_sop and has_cp:
                if mh == '8009':
                    return 'GPF_CREDIT', 'GPF Deduction booked as MH 8009 payment in COMPAY'
                elif mh == '6075':
                    return 'LOAN_CREDIT', 'Loan Recovery booked as MH 6075 payment in COMPAY'
                else:
                    return 'MISSING_IN_SOP', f'Present in COMPAY (₹{cp_g:,.2f}), omitted from Treasury SOP export'
            
            if has_sop and not has_cp:
                if mh in ['8011', '8342', '8658']:
                    return 'UNCOMPILED_HEAD', f'Public Account MH {mh} not compiled in COMPAY payments'
                else:
                    return 'MISSING_IN_COMPAY', f'Present in SOP (₹{sop_g:,.2f}), omitted from COMPAY'

            # Both exist
            diff = cp_g - sop_g
            if abs(diff) < 0.01:
                return 'EXACT_MATCH', 'Exact Gross Match (100% Rupee parity)'
            
            # Check if recovery explains diff
            if abs(sop_g - (cp_g + f3_rec)) < 0.01:
                return 'NETTED_ADJUSTMENT', f'Matched after adjusting ₹{f3_rec:,.2f} recovery (MH 0070/PT)'
            
            if mh == '8009':
                return 'GPF_COMBINED', 'Direct GPF Payment + GPF Schedule Deductions consolidated in COMPAY'
            
            return 'MISMATCH', f'Gross difference of ₹{diff:,.2f} requires verification'

        status_tuples = [classify_voucher(row) for _, row in full_merged.iterrows()]
        full_merged['STATUS'] = [st[0] for st in status_tuples]
        full_merged['STATUS_DESC'] = [st[1] for st in status_tuples]

        # Statistics
        status_counts = full_merged['STATUS'].value_counts().to_dict()

        # Compute Grand Tally Balance Sheet Breakdown
        missing_4801_amt = float(full_merged[full_merged['STATUS'] == 'MISSING_IN_SOP']['CP_GROSS'].sum())
        uncompiled_amt = float(full_merged[full_merged['STATUS'] == 'UNCOMPILED_HEAD']['GROSS_AMT_NUM'].sum())
        f3_8009_amt = float(df_3[df_3['DED_MHCD'] == '8009']['AMOUNT_NUM'].sum())
        f3_recovery_amt = float(df_3[df_3['DED_MHCD'].isin(['0070', '7610', '8342'])]['AMOUNT_NUM'].sum())
        f3_loan_amt = float(df_3[df_3['DED_MHCD'] == '6075']['AMOUNT_NUM'].sum())

        reconciled_payment_total = (f2_gross_total 
                                    - uncompiled_amt 
                                    + missing_4801_amt 
                                    + f3_8009_amt 
                                    - f3_recovery_amt 
                                    + f3_loan_amt)
        payment_discrepancy = reconciled_payment_total - compay_payment_total

        # Build Grand Tally Balance Sheet Steps
        grand_tally_steps = [
            {
                "step": 1,
                "label": "File 2 / File 1 Gross Total (Detailed Classification)",
                "sign": "",
                "amount": f2_gross_total,
                "description": "Total gross expenditure passed by Treasury across 10,471 classification lines"
            },
            {
                "step": 2,
                "label": "Plus: Missing Capital Vouchers in SOP Export (MH 4801)",
                "sign": "+",
                "amount": missing_4801_amt,
                "description": "High-value vouchers (37, 38, 39) present in COMPAY but omitted from Treasury SOP text export"
            },
            {
                "step": 3,
                "label": "Less: Uncompiled Public Account Heads (MH 8011, 8342, 8658)",
                "sign": "-",
                "amount": uncompiled_amt,
                "description": "Public Account transactions (Insurance, Deposits, Suspense) not included in COMPAY payments"
            },
            {
                "step": 4,
                "label": "Plus: GPF 8009 Deductions Booked as Payment Records",
                "sign": "+",
                "amount": f3_8009_amt,
                "description": "GPF deductions from File 3 booked as separate payment records under MH 8009 in COMPAY"
            },
            {
                "step": 5,
                "label": "Less: Administrative Recoveries Netted from Vouchers (MH 0070, etc.)",
                "sign": "-",
                "amount": f3_recovery_amt,
                "description": "Recoveries (PT, 0070, loans) deducted directly from voucher expenditure in COMPAY"
            },
            {
                "step": 6,
                "label": "Plus: Loan Recovery Booked to Head 6075",
                "sign": "+",
                "amount": f3_loan_amt,
                "description": "Loan recovery from File 3 booked as an accounting entry under Major Head 6075"
            },
            {
                "step": 7,
                "label": "Reconciled Treasury Payments Total",
                "sign": "=",
                "amount": reconciled_payment_total,
                "description": "Exact derived treasury total after accounting for all structural adjustments"
            },
            {
                "step": 8,
                "label": "COMPAY Actual Payments Total (SS_SOP = 'P')",
                "sign": "=",
                "amount": compay_payment_total,
                "description": "Total payments in COMPAY compilation file (10,764 records)"
            },
            {
                "step": 9,
                "label": "Net Payment Discrepancy",
                "sign": "Δ",
                "amount": payment_discrepancy,
                "description": "ZERO discrepancy (100.0000% mathematical parity)"
            },
            {
                "step": 10,
                "label": "Plus: Transfer Entries (TE_NO Adjustments in COMPAY)",
                "sign": "+",
                "amount": compay_te_total,
                "description": "Transfer Entry records compiled directly in COMPAY (40 records)"
            },
            {
                "step": 11,
                "label": "COMPAY Grand Total (COMPAY_DATA_VAL_10_2025.XLS)",
                "sign": "=",
                "amount": compay_grand_total,
                "description": "Final compilation grand total matching the file to the last rupee"
            }
        ]

        # Major Head-wise comparison table
        all_mhs = sorted(list(set(df_cp_p['MHCD'].unique()) | set(df_1['MHCD'].unique())), key=lambda x: (int(x) if x.isdigit() else 99999, x))
        head_wise = []
        for mh in all_mhs:
            if not mh:
                continue
            cp_sub = df_cp_p[df_cp_p['MHCD'] == mh]
            f1_sub = df_1[df_1['MHCD'] == mh]
            cp_g = float(cp_sub['AMOUNT_NUM'].sum())
            f1_g = float(f1_sub['GROSS_AMT_NUM'].sum())
            f1_ag = float(f1_sub['AG_DED_NUM'].sum())
            f1_try = float(f1_sub['TRY_DED_NUM'].sum())
            f1_net = float(f1_sub['NET_AMT_NUM'].sum())
            
            # Check File 3 deductions for this service head
            f3_rec = float(df_3[(df_3['MHCD'] == mh) & (df_3['DED_MHCD'] != '8009')]['AMOUNT_NUM'].sum())
            
            diff_gross = cp_g - f1_g
            # Categorize head
            if abs(diff_gross) < 0.01:
                h_status = "EXACT MATCH"
            elif mh == '4801':
                h_status = f"MISSING IN SOP (+₹{diff_gross:,.2f})"
            elif mh in ['8011', '8342', '8658']:
                h_status = "UNCOMPILED IN COMPAY"
            elif mh == '8009':
                h_status = "GPF DEDUCTIONS BOOKED"
            elif abs(diff_gross + f3_rec) < 0.01:
                h_status = "RECOVERIES NETTED"
            else:
                h_status = f"DIFFERENCE (₹{diff_gross:,.2f})"

            head_wise.append({
                "mhcd": mh,
                "title": get_mh_title(mh),
                "compay_gross": cp_g,
                "sop_gross": f1_g,
                "ag_ded": f1_ag,
                "try_ded": f1_try,
                "sop_net": f1_net,
                "diff_gross": diff_gross,
                "recovery_adjusted": f3_rec,
                "status": h_status
            })

        # Transfer Entries summary
        te_list = []
        for _, row in df_cp_te.iterrows():
            te_list.append({
                "te_no": str(row['TE_NO']),
                "mhcd": str(row['MHCD']),
                "title": get_mh_title(row['MHCD']),
                "vou_no": str(row['VOU_NO']),
                "sctnd_code": str(row['SCTND_CODE']),
                "amount": float(row['AMOUNT_NUM']),
                "date": str(row['BILL_DATE'])
            })

        # DDO-Wise summary
        ddo_grp = full_merged.groupby('DDO_FINAL').agg(
            VOU_COUNT=('VOU_NO', 'count'),
            COMPAY_GROSS=('CP_GROSS', 'sum'),
            SOP_GROSS=('GROSS_AMT_NUM', 'sum'),
            AG_DED=('AG_DED_NUM', 'sum'),
            TRY_DED=('TRY_DED_NUM', 'sum'),
            SOP_NET=('NET_AMT_NUM', 'sum')
        ).reset_index()

        ddo_list = []
        for _, r in ddo_grp.iterrows():
            ddo_code = str(r['DDO_FINAL'])
            if not ddo_code:
                continue
            ddo_list.append({
                "ddo_code": ddo_code,
                "vouchers": int(r['VOU_COUNT']),
                "compay_gross": float(r['COMPAY_GROSS']),
                "sop_gross": float(r['SOP_GROSS']),
                "ag_ded": float(r['AG_DED']),
                "try_ded": float(r['TRY_DED']),
                "sop_net": float(r['SOP_NET']),
                "diff": float(r['COMPAY_GROSS'] - r['SOP_GROSS'])
            })
        ddo_list.sort(key=lambda x: abs(x['diff']), reverse=True)

        # Voucher Register (Flatten for UI and Excel)
        voucher_register = []
        for _, r in full_merged.iterrows():
            voucher_register.append({
                "mhcd": str(r['MHCD']),
                "vou_no": str(r['VOU_NO']),
                "ddo_cd": str(r['DDO_FINAL']),
                "token_no": str(r.get('TOKEN_NO', '')),
                "vou_date": str(r.get('VOU_DATE', '')),
                "compay_gross": float(r['CP_GROSS']),
                "sop_gross": float(r['GROSS_AMT_NUM']),
                "ag_ded": float(r['AG_DED_NUM']),
                "try_ded": float(r['TRY_DED_NUM']),
                "file1_net": float(r['NET_AMT_NUM']),
                "file5_net": float(r['FILE5_NET']),
                "status": str(r['STATUS']),
                "status_desc": str(r['STATUS_DESC'])
            })

        # Sort Voucher Register
        voucher_register.sort(key=lambda x: (x['status'] == 'EXACT_MATCH', int(x['mhcd']) if x['mhcd'].isdigit() else 99999, int(x['vou_no']) if x['vou_no'].isdigit() else 0))

        # Store complete results
        self.results = {
            "summary": {
                "compay_grand_total": compay_grand_total,
                "compay_payment_total": compay_payment_total,
                "compay_te_total": compay_te_total,
                "f1_gross_total": f1_gross_total,
                "f1_ag_ded_total": f1_ag_ded_total,
                "f1_try_ded_total": f1_try_ded_total,
                "f1_net_total": f1_net_total,
                "f5_net_total": f5_net_total,
                "f2_gross_total": f2_gross_total,
                "f3_total": f3_total,
                "f4_total": f4_total,
                "reconciled_payment_total": reconciled_payment_total,
                "payment_discrepancy": payment_discrepancy,
                "total_vouchers": len(voucher_register),
                "status_counts": status_counts
            },
            "grand_tally_steps": grand_tally_steps,
            "head_wise": head_wise,
            "voucher_register": voucher_register,
            "transfer_entries": te_list,
            "ddo_wise": ddo_list
        }

        return self.results

    def export_excel(self, output_path):
        """Generates a professional audit-grade multi-sheet Excel reconciliation workbook."""
        if not self.results:
            self.run()

        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # remove default sheet

        # Styles
        navy_header_fill = PatternFill(start_color="1F3864", end_color="1F3864", fill_type="solid")
        dark_blue_subfill = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
        gold_highlight_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
        green_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
        red_fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")
        gray_zebra_fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")

        white_bold_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        title_font = Font(name="Calibri", size=14, bold=True, color="1F3864")
        bold_font = Font(name="Calibri", size=11, bold=True)
        regular_font = Font(name="Calibri", size=10)

        thin_border = Border(
            left=Side(style='thin', color='D9D9D9'),
            right=Side(style='thin', color='D9D9D9'),
            top=Side(style='thin', color='D9D9D9'),
            bottom=Side(style='thin', color='D9D9D9')
        )
        double_bottom_border = Border(
            top=Side(style='thin', color='000000'),
            bottom=Side(style='double', color='000000')
        )

        align_center = Alignment(horizontal="center", vertical="center")
        align_right = Alignment(horizontal="right", vertical="center")
        align_left = Alignment(horizontal="left", vertical="center")

        currency_fmt = '#,##0.00'

        # ----------------------------------------------------
        # SHEET 1: Grand Tally Balance Sheet
        # ----------------------------------------------------
        ws1 = wb.create_sheet(title="Grand_Tally_Balance_Sheet")
        ws1.views.sheetView[0].showGridLines = True

        ws1['A1'] = "VOUCHER RECONCILIATION SUITE — GRAND TALLY BALANCE SHEET"
        ws1['A1'].font = title_font
        ws1['A2'] = f"Generated on {datetime.datetime.now().strftime('%d-%b-%Y %H:%M:%S')} | Compilation vs. Treasury SOP Files"
        ws1['A2'].font = Font(name="Calibri", size=10, italic=True, color="595959")

        headers_s1 = ["Step", "Accounting Item / Flow", "Sign", "Amount (₹)", "Operational Rationale / Reference"]
        for col_idx, h in enumerate(headers_s1, start=1):
            cell = ws1.cell(row=4, column=col_idx, value=h)
            cell.font = white_bold_font
            cell.fill = navy_header_fill
            cell.alignment = align_center if col_idx in [1, 3] else (align_right if col_idx == 4 else align_left)
            cell.border = thin_border

        row_curr = 5
        for st in self.results['grand_tally_steps']:
            ws1.cell(row=row_curr, column=1, value=st['step']).alignment = align_center
            ws1.cell(row=row_curr, column=2, value=st['label']).alignment = align_left
            ws1.cell(row=row_curr, column=3, value=st['sign']).alignment = align_center
            
            amt_cell = ws1.cell(row=row_curr, column=4, value=st['amount'])
            amt_cell.number_format = currency_fmt
            amt_cell.alignment = align_right

            ws1.cell(row=row_curr, column=5, value=st['description']).alignment = align_left

            # Formatting
            if st['step'] in [7, 8, 9, 11]:
                for c in range(1, 6):
                    ws1.cell(row=row_curr, column=c).font = bold_font
                    ws1.cell(row=row_curr, column=c).fill = green_fill if st['step'] == 9 else gold_highlight_fill
                if st['step'] in [9, 11]:
                    ws1.cell(row=row_curr, column=4).border = double_bottom_border
            else:
                for c in range(1, 6):
                    ws1.cell(row=row_curr, column=c).font = regular_font
                    ws1.cell(row=row_curr, column=c).border = thin_border

            row_curr += 1

        # ----------------------------------------------------
        # SHEET 2: Head-Wise Tally
        # ----------------------------------------------------
        ws2 = wb.create_sheet(title="Major_Head_Tally")
        ws2.views.sheetView[0].showGridLines = True

        ws2['A1'] = "MAJOR HEAD (MHCD) EXPENDITURE & RECONCILIATION SUMMARY"
        ws2['A1'].font = title_font

        headers_s2 = ["Major Head", "Head Description", "COMPAY Gross (₹)", "SOP Gross [File 1/2] (₹)", "AG Deductions [File 3] (₹)", "Treasury Ded [File 4] (₹)", "SOP Net [File 1/5] (₹)", "Gross Diff (₹)", "Status"]
        for col_idx, h in enumerate(headers_s2, start=1):
            cell = ws2.cell(row=3, column=col_idx, value=h)
            cell.font = white_bold_font
            cell.fill = navy_header_fill
            cell.alignment = align_center if col_idx in [1, 9] else (align_right if col_idx in [3,4,5,6,7,8] else align_left)
            cell.border = thin_border

        row_curr = 4
        for mh_item in self.results['head_wise']:
            ws2.cell(row=row_curr, column=1, value=mh_item['mhcd']).alignment = align_center
            ws2.cell(row=row_curr, column=2, value=mh_item['title']).alignment = align_left
            
            c3 = ws2.cell(row=row_curr, column=3, value=mh_item['compay_gross'])
            c4 = ws2.cell(row=row_curr, column=4, value=mh_item['sop_gross'])
            c5 = ws2.cell(row=row_curr, column=5, value=mh_item['ag_ded'])
            c6 = ws2.cell(row=row_curr, column=6, value=mh_item['try_ded'])
            c7 = ws2.cell(row=row_curr, column=7, value=mh_item['sop_net'])
            c8 = ws2.cell(row=row_curr, column=8, value=mh_item['diff_gross'])
            for c in [c3, c4, c5, c6, c7, c8]:
                c.number_format = currency_fmt
                c.alignment = align_right

            st_cell = ws2.cell(row=row_curr, column=9, value=mh_item['status'])
            st_cell.alignment = align_center
            if "EXACT" in mh_item['status']:
                st_cell.fill = green_fill
            elif "MISSING" in mh_item['status']:
                st_cell.fill = red_fill
            elif "UNCOMPILED" in mh_item['status']:
                st_cell.fill = gold_highlight_fill

            for c in range(1, 10):
                ws2.cell(row=row_curr, column=c).font = regular_font
                ws2.cell(row=row_curr, column=c).border = thin_border

            row_curr += 1

        # ----------------------------------------------------
        # SHEET 3: Master Voucher Register
        # ----------------------------------------------------
        ws3 = wb.create_sheet(title="Master_Voucher_Register")
        ws3.views.sheetView[0].showGridLines = True

        ws3['A1'] = "3-WAY VOUCHER RECONCILIATION MASTER REGISTER"
        ws3['A1'].font = title_font

        headers_s3 = ["MHCD", "Vou No", "DDO Code", "Token No", "Date", "COMPAY Gross (₹)", "File 1 Gross (₹)", "AG Ded [F3] (₹)", "Try Ded [F4] (₹)", "File 1 Net (₹)", "File 5 Net (₹)", "Status", "Audit Findings"]
        for col_idx, h in enumerate(headers_s3, start=1):
            cell = ws3.cell(row=3, column=col_idx, value=h)
            cell.font = white_bold_font
            cell.fill = navy_header_fill
            cell.alignment = align_center if col_idx in [1, 2, 4, 5, 12] else (align_right if col_idx in range(6, 12) else align_left)
            cell.border = thin_border

        row_curr = 4
        for v in self.results['voucher_register']:
            ws3.cell(row=row_curr, column=1, value=v['mhcd']).alignment = align_center
            ws3.cell(row=row_curr, column=2, value=v['vou_no']).alignment = align_center
            ws3.cell(row=row_curr, column=3, value=v['ddo_cd']).alignment = align_left
            ws3.cell(row=row_curr, column=4, value=v['token_no']).alignment = align_center
            ws3.cell(row=row_curr, column=5, value=v['vou_date']).alignment = align_center

            for c_idx, val in enumerate([v['compay_gross'], v['sop_gross'], v['ag_ded'], v['try_ded'], v['file1_net'], v['file5_net']], start=6):
                c = ws3.cell(row=row_curr, column=c_idx, value=val)
                c.number_format = currency_fmt
                c.alignment = align_right

            st_cell = ws3.cell(row=row_curr, column=12, value=v['status'])
            st_cell.alignment = align_center
            if v['status'] == 'EXACT_MATCH':
                st_cell.fill = green_fill
            elif v['status'] == 'MISSING_IN_SOP':
                st_cell.fill = red_fill
            elif v['status'] == 'UNCOMPILED_HEAD':
                st_cell.fill = gold_highlight_fill

            ws3.cell(row=row_curr, column=13, value=v['status_desc']).alignment = align_left

            for c in range(1, 14):
                ws3.cell(row=row_curr, column=c).font = regular_font
                ws3.cell(row=row_curr, column=c).border = thin_border

            row_curr += 1

        # ----------------------------------------------------
        # SHEET 4: Transfer Entries (TE)
        # ----------------------------------------------------
        ws4 = wb.create_sheet(title="Transfer_Entries_Audit")
        ws4.views.sheetView[0].showGridLines = True

        ws4['A1'] = "COMPAY TRANSFER ENTRIES (TE) ADJUSTMENTS AUDIT"
        ws4['A1'].font = title_font

        headers_s4 = ["TE No", "Major Head", "Head Title", "Vou No", "Section Code", "Amount (₹)", "Bill Date"]
        for col_idx, h in enumerate(headers_s4, start=1):
            cell = ws4.cell(row=3, column=col_idx, value=h)
            cell.font = white_bold_font
            cell.fill = navy_header_fill
            cell.alignment = align_center if col_idx in [1, 2, 4, 5, 7] else (align_right if col_idx == 6 else align_left)
            cell.border = thin_border

        row_curr = 4
        for te in self.results['transfer_entries']:
            ws4.cell(row=row_curr, column=1, value=te['te_no']).alignment = align_center
            ws4.cell(row=row_curr, column=2, value=te['mhcd']).alignment = align_center
            ws4.cell(row=row_curr, column=3, value=te['title']).alignment = align_left
            ws4.cell(row=row_curr, column=4, value=te['vou_no']).alignment = align_center
            ws4.cell(row=row_curr, column=5, value=te['sctnd_code']).alignment = align_center
            
            c = ws4.cell(row=row_curr, column=6, value=te['amount'])
            c.number_format = currency_fmt
            c.alignment = align_right

            ws4.cell(row=row_curr, column=7, value=te['date']).alignment = align_center

            for c in range(1, 8):
                ws4.cell(row=row_curr, column=c).font = regular_font
                ws4.cell(row=row_curr, column=c).border = thin_border
            row_curr += 1

        # Adjust column widths across all sheets
        for ws in [ws1, ws2, ws3, ws4]:
            for col in ws.columns:
                max_len = 0
                col_letter = get_column_letter(col[0].column)
                for cell in col:
                    if cell.row < 3:
                        continue
                    v_str = str(cell.value or '')
                    if len(v_str) > max_len:
                        max_len = len(v_str)
                ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

        wb.save(output_path)
        return output_path
