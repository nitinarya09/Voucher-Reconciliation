# -*- coding: utf-8 -*-
"""
Smart File Detector Module
Automatically scans, identifies, and classifies IFMIS and VLC reconciliation files
using a two-tier hybrid of filename pattern heuristics and deep content/structural fingerprinting.
"""

import os
import re
import pandas as pd


class SmartFileIdentifier:
    """
    Intelligently identifies and maps 6 reconciliation files within a given directory
    using a combination of filename patterns and deep structural content fingerprinting.
    """
    AG_HEADS = {"8009", "0070", "7610", "8011", "7615"}
    TRY_HEADS = {"8658", "0028", "0216", "0043", "0029"}

    @classmethod
    def scan_folder(cls, folder_path, check_parent_for_compay=True):
        """
        Scans folder_path and identifies file_1 through file_6.
        Returns:
            identified: dict of {file_id: absolute_path}
            logs: list of audit strings describing how each file was identified
            unmatched: list of files that were not matched to any role
        """
        if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
            return {}, [f"Directory not found: {folder_path}"], []

        candidates = []
        for root, dirs, files in os.walk(folder_path):
            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                if ext in ['.txt', '.csv', '.tsv', '.dat', '.xls', '.xlsx']:
                    full_p = os.path.join(root, fn)
                    candidates.append((fn, full_p))

        # Check parent folder for COMPAY if not present in folder
        if check_parent_for_compay:
            parent_dir = os.path.dirname(os.path.abspath(folder_path))
            if parent_dir and os.path.exists(parent_dir):
                for fn in os.listdir(parent_dir):
                    ext = os.path.splitext(fn)[1].lower()
                    if ext in ['.xls', '.xlsx', '.csv', '.txt'] and "compay" in fn.lower():
                        candidates.append((fn, os.path.join(parent_dir, fn)))

        identified = {}
        logs = []
        remaining = list(candidates)

        # -------------------------------------------------------------
        # Pass 1: Filename Pattern Matching (Fast Path)
        # -------------------------------------------------------------
        for fn, full_p in list(remaining):
            lfn = fn.lower()
            role = None

            # File 6: COMPAY / VLC Posted Vouchers
            if "compay" in lfn or "vlc" in lfn or re.search(r'(^0?6[_\s\.-]|file[_\s-]?0?6\b)', lfn):
                role = "file_6"
            # File 2: Voucher Detail - Details Headwise (checked before File 1 to catch 'headwise')
            elif re.search(r'(details[_\s-]?headwise|headwise|gross[_\s-]?exp|detailed|classification|^0?2[_\s\.-]|file[_\s-]?0?2\b)', lfn):
                role = "file_2"
            # File 1: Voucher Details
            elif re.search(r'(voucher[_\s-]?details|bill[_\s-]?master|gross[_\s-]?net|^0?1[_\s\.-]|file[_\s-]?0?1\b)', lfn):
                role = "file_1"
            # File 4: NON AG Deduction (checked before AG to catch 'non_ag')
            elif re.search(r'(non[_\s-]?ag|try[_\s-]?ded|treasury[_\s-]?ded|tds|^0?4[_\s\.-]|file[_\s-]?0?4\b)', lfn):
                role = "file_4"
            # File 3: AG Deduction
            elif re.search(r'(ag[_\s-]?deduction|ag[_\s-]?ded|gpf|^0?3[_\s\.-]|file[_\s-]?0?3\b)', lfn):
                role = "file_3"
            # File 5: Voucher Summary (Net SOP)
            elif re.search(r'(voucher[_\s-]?summary|net[_\s-]?sop|netsop|^0?5[_\s\.-]|file[_\s-]?0?5\b)', lfn) or (lfn.endswith("sop.txt") and not re.match(r'^[1234][_\.]', lfn)):
                role = "file_5"

            if role and role not in identified:
                identified[role] = full_p
                if (fn, full_p) in remaining:
                    remaining.remove((fn, full_p))
                logs.append(f"[Pattern Match] Identified '{fn}' as {role.upper()}")

        # -------------------------------------------------------------
        # Pass 2: Deep Content Inspection for any unassigned roles
        # -------------------------------------------------------------
        needed_roles = [f"file_{i}" for i in range(1, 7) if f"file_{i}" not in identified]

        for fn, full_p in list(remaining):
            if not needed_roles:
                break

            role, reason = cls._fingerprint_file(full_p, needed_roles)
            if role and role in needed_roles:
                identified[role] = full_p
                needed_roles.remove(role)
                if (fn, full_p) in remaining:
                    remaining.remove((fn, full_p))
                logs.append(f"[Content Fingerprint] Identified '{fn}' as {role.upper()} ({reason})")

        unmatched = [fn for fn, _ in remaining]
        return identified, logs, unmatched

    @classmethod
    def _fingerprint_file(cls, file_path, needed_roles):
        ext = os.path.splitext(file_path)[1].lower()

        # Excel inspection
        if ext in ['.xls', '.xlsx']:
            if "file_6" in needed_roles:
                try:
                    df = pd.read_excel(file_path, nrows=5)
                    cols = [str(c).upper() for c in df.columns]
                    if any(k in cols for k in ['SS_SOP', 'TE_NO', 'COMPAY', 'GROSS_AMT', 'MHCD']):
                        return "file_6", "Excel file containing COMPAY columns"
                    return "file_6", "Excel dataset candidate for COMPAY"
                except Exception:
                    return "file_6", "Excel file candidate"

        # Text file inspection
        try:
            with open(file_path, 'r', encoding='latin-1', errors='replace') as f:
                lines = [f.readline().strip() for _ in range(12)]
            lines = [l for l in lines if l]
            if not lines:
                return None, "Empty file"

            # Detect delimiter
            delims = [',', '\t', '|', ';']
            best_delim = ','
            max_c = 0
            for d in delims:
                c = lines[0].count(d)
                if c > max_c:
                    max_c = c
                    best_delim = d

            parsed_rows = [l.split(best_delim) for l in lines]
            col_count = len(parsed_rows[0])
            first_row_upper = [c.strip().upper() for c in parsed_rows[0]]

            # Check for header
            has_header = any(k in first_row_upper for k in ['TRY_CD', 'VOU_NO', 'MHCD', 'GROSS_AMT', 'NET_AMT', 'DED_AMT', 'SS_SOP'])
            
            if has_header:
                if 'SS_SOP' in first_row_upper or 'TE_NO' in first_row_upper:
                    return "file_6", "Header contains SS_SOP/TE_NO"
                if 'GROSS_AMT' in first_row_upper and 'NET_AMT' in first_row_upper and ('DED_AMT' in first_row_upper or 'AG_DED' in first_row_upper):
                    return "file_1", "Header contains Gross, Net and Deductions"
                if 'GROSS_AMT' in first_row_upper and 'NET_AMT' not in first_row_upper:
                    return "file_2", "Header contains Gross Amount without Net Amount"
                if 'NET_AMT' in first_row_upper and 'GROSS_AMT' not in first_row_upper:
                    return "file_5", "Header contains Net Amount without Gross Amount"
                if 'DED_MHCD' in first_row_upper or 'DED_AMT' in first_row_upper:
                    idx = first_row_upper.index('DED_MHCD') if 'DED_MHCD' in first_row_upper else 7
                    heads = [r[idx].strip() for r in parsed_rows[1:] if len(r) > idx]
                    ag_score = sum(1 for h in heads if h in cls.AG_HEADS)
                    try_score = sum(1 for h in heads if h in cls.TRY_HEADS)
                    if ag_score >= try_score:
                        return "file_3", f"Header deduction schedule with AG heads (score: {ag_score})"
                    else:
                        return "file_4", f"Header deduction schedule with Treasury heads (score: {try_score})"

            # No header: Structural column counts (Standard Treasury formats)
            if col_count == 18 and "file_1" in needed_roles:
                return "file_1", "18-column standard IFMIS Bill Master signature"
            elif col_count == 16 and "file_2" in needed_roles:
                return "file_2", "16-column detailed budget classification signature"
            elif col_count == 10 and "file_5" in needed_roles:
                return "file_5", "10-column standard Net SOP signature"
            elif col_count == 15:
                # Distinguish between File 3 and File 4 via Major Head at index 7
                heads = [r[7].strip() for r in parsed_rows if len(r) > 7]
                ag_score = sum(1 for h in heads if h in cls.AG_HEADS)
                try_score = sum(1 for h in heads if h in cls.TRY_HEADS)
                if ag_score > try_score and "file_3" in needed_roles:
                    return "file_3", f"15-column schedule with AG deduction heads (score: {ag_score})"
                elif try_score > ag_score and "file_4" in needed_roles:
                    return "file_4", f"15-column schedule with Treasury deduction heads (score: {try_score})"
                elif "file_3" in needed_roles:
                    return "file_3", "15-column deduction schedule candidate (File 3)"
                elif "file_4" in needed_roles:
                    return "file_4", "15-column deduction schedule candidate (File 4)"

            if (col_count in [7, 8, 9]) and "file_6" in needed_roles:
                return "file_6", f"{col_count}-column COMPAY posted voucher signature"

        except Exception as e:
            return None, f"Error inspecting file: {e}"

        return None, "Unrecognized format"
