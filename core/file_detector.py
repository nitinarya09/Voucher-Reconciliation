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
    def scan_folder(cls, folder_path, treasury_code=None, month=None, year=None, check_parent_for_compay=True):
        """
        Scans folder_path and identifies file_1 through file_6.
        Optionally filters/prioritizes by treasury_code (e.g. '052'/'VAL'),
        month (e.g. '04'/'April'), and year (e.g. '2025').
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
            has_compay = any("compay" in fn.lower() or "vlc" in fn.lower() for fn, _ in candidates)
            if not has_compay:
                parent_dir = os.path.dirname(os.path.abspath(folder_path))
                if parent_dir and os.path.exists(parent_dir):
                    for fn in os.listdir(parent_dir):
                        ext = os.path.splitext(fn)[1].lower()
                        if ext in ['.xls', '.xlsx', '.csv', '.txt'] and "compay" in fn.lower():
                            candidates.append((fn, os.path.join(parent_dir, fn)))

        # Month keywords helper
        MONTH_MAP = {
            '1': ['01', 'jan', 'january'], '01': ['01', 'jan', 'january'],
            '2': ['02', 'feb', 'february'], '02': ['02', 'feb', 'february'],
            '3': ['03', 'mar', 'march'], '03': ['03', 'mar', 'march'],
            '4': ['04', 'apr', 'april'], '04': ['04', 'apr', 'april'],
            '5': ['05', 'may'], '05': ['05', 'may'],
            '6': ['06', 'jun', 'june'], '06': ['06', 'jun', 'june'],
            '7': ['07', 'jul', 'july'], '07': ['07', 'jul', 'july'],
            '8': ['08', 'aug', 'august'], '08': ['08', 'aug', 'august'],
            '9': ['09', 'sep', 'sept', 'september'], '09': ['09', 'sep', 'sept', 'september'],
            '10': ['10', 'oct', 'october'],
            '11': ['11', 'nov', 'november'],
            '12': ['12', 'dec', 'december']
        }
        is_all_months = (str(month).strip().upper() == 'ALL') if month else False
        is_all_treasuries = (str(treasury_code).strip().upper() == 'ALL') if treasury_code else False
        is_multi_mode = is_all_months or is_all_treasuries

        month_tokens = []
        other_month_tokens = []
        if month and not is_all_months:
            m_clean = str(month).strip().lower()
            month_tokens = MONTH_MAP.get(m_clean, [m_clean])
            for k, toks in MONTH_MAP.items():
                if k != m_clean:
                    other_month_tokens.extend(toks)

        year_tokens = []
        if year and str(year).strip().upper() != 'ALL':
            y_str = str(year).strip()
            if '-' in y_str:
                p = y_str.split('-')
                year_tokens = [p[0], p[1], p[0][-2:], p[1][-2:]]
            elif len(y_str) == 4:
                year_tokens = [y_str, y_str[2:]]
                if is_all_months:
                    next_y = str(int(y_str) + 1)
                    year_tokens.extend([next_y, next_y[2:]])
            else:
                year_tokens = [y_str]

        try_tokens = []
        if treasury_code and not is_all_treasuries:
            t_clean = str(treasury_code).strip().lower()
            try_tokens = [t_clean]
            if t_clean == '052' or t_clean == 'val':
                try_tokens.extend(['052', 'val', 'vallabh'])
            elif t_clean == '051' or t_clean == 'vin':
                try_tokens.extend(['051', 'vin', 'vindhyachal'])
            elif t_clean == '050' or t_clean == 'bpl':
                try_tokens.extend(['050', 'bpl', 'bhopal'])

        # -------------------------------------------------------------
        # Multi-File Mode: Full Financial Year / Multi-Treasury Ingestion
        # -------------------------------------------------------------
        if is_multi_mode:
            identified = {f"file_{i}": [] for i in range(1, 7)}
            seen_keys = set()
            logs = []

            for fn, full_p in candidates:
                # 1. Skip empty files
                if not os.path.exists(full_p) or os.path.getsize(full_p) == 0:
                    continue
                # 2. Skip HTML error downloads
                try:
                    with open(full_p, 'rb') as f_chk:
                        h = f_chk.read(256).lower()
                        if b'<!doctype' in h or b'<html' in h or b'504 gateway' in h:
                            continue
                except Exception:
                    pass

                lfn = fn.lower()
                role = None
                if "compay" in lfn or "vlc" in lfn or re.search(r'(^0?6[_\s\.-]|file[_\s-]?0?6\b)', lfn):
                    role = "file_6"
                elif re.search(r'(details[_\s-]?headwise|headwise|gross[_\s-]?exp|detailed|classification|^0?2[_\s\.-]|file[_\s-]?0?2\b)', lfn):
                    role = "file_2"
                elif re.search(r'(voucher[_\s-]?details|bill[_\s-]?master|gross[_\s-]?net|^0?1[_\s\.-]|file[_\s-]?0?1\b)', lfn):
                    role = "file_1"
                elif re.search(r'(non[_\s-]?ag|try[_\s-]?ded|treasury[_\s-]?ded|tds|^0?4[_\s\.-]|file[_\s-]?0?4\b)', lfn):
                    role = "file_4"
                elif re.search(r'(ag[_\s-]?deduction|ag[_\s-]?ded|gpf|^0?3[_\s\.-]|file[_\s-]?0?3\b)', lfn):
                    role = "file_3"
                elif re.search(r'(voucher[_\s-]?summary|net[_\s-]?sop|netsop|^0?5[_\s\.-]|file[_\s-]?0?5\b)', lfn) or (lfn.endswith("sop.txt") and not re.match(r'^[1234][_\.]', lfn)):
                    role = "file_5"

                if not role:
                    continue

                haystack = (fn + " " + full_p).lower()
                if try_tokens and not any(tok in haystack for tok in try_tokens):
                    continue
                if year_tokens and not any(tok in haystack for tok in year_tokens):
                    continue
                if month_tokens:
                    has_target = any(re.search(r'(?:^|[\W_])' + re.escape(tok) + r'(?:$|[\W_])', haystack) for tok in month_tokens)
                    if not has_target:
                        matches_year = year_tokens and any(tok in haystack for tok in year_tokens)
                        if role == "file_6" and (matches_year or "compay" in lfn):
                            pass
                        else:
                            continue

                dedup_key = (role, fn.lower(), os.path.getsize(full_p))
                if dedup_key in seen_keys:
                    continue
                seen_keys.add(dedup_key)
                identified[role].append(full_p)

            # If File 6 contains month-specific COMPAY files, prefer them over annual split files
            if month_tokens and identified["file_6"]:
                month_specific_f6 = [p for p in identified["file_6"] if any(re.search(r'(?:^|[\W_])' + re.escape(tok) + r'(?:$|[\W_])', (os.path.basename(p) + " " + p).lower()) for tok in month_tokens)]
                if month_specific_f6:
                    identified["file_6"] = month_specific_f6

            # Fallback fingerprinting for empty roles
            empty_roles = [r for r, fl in identified.items() if not fl]
            if empty_roles:
                for fn, full_p in candidates:
                    dedup_key = (fn.lower(), os.path.getsize(full_p))
                    if any(dedup_key == (os.path.basename(p).lower(), os.path.getsize(p)) for fl in identified.values() for p in fl):
                        continue
                    role, reason = cls._fingerprint_file(full_p, empty_roles)
                    if role and role in empty_roles:
                        identified[role].append(full_p)
                        logs.append(f"[Content Fingerprint] Identified '{fn}' as {role.upper()} ({reason})")

            for r in identified:
                identified[r].sort(key=lambda p: os.path.basename(p).lower())
                cnt = len(identified[r])
                if cnt > 0:
                    logs.append(f"[Multi-File Scan] Identified {cnt} files for {r.upper()}")

            all_matched = {p for fl in identified.values() for p in fl}
            unmatched = [fn for fn, full_p in candidates if full_p not in all_matched]
            return identified, logs, unmatched

        def compute_candidate_score(filename, full_path):
            haystack = (filename + " " + full_path).lower()
            score = 0
            if month_tokens:
                if any(re.search(r'(?:^|[\W_])' + re.escape(tok) + r'(?:$|[\W_])', haystack) for tok in month_tokens):
                    score += 20
                elif any(tok in haystack for tok in month_tokens):
                    score += 10
            if year_tokens:
                if any(re.search(r'(?:^|[\W_])' + re.escape(tok) + r'(?:$|[\W_])', haystack) for tok in year_tokens):
                    score += 20
                elif any(tok in haystack for tok in year_tokens):
                    score += 10
            if try_tokens:
                if any(re.search(r'(?:^|[\W_])' + re.escape(tok) + r'(?:$|[\W_])', haystack) for tok in try_tokens):
                    score += 20
                elif any(tok in haystack for tok in try_tokens):
                    score += 10
            return score

        # Sort candidates so the ones best matching the requested Treasury/Month/Year come first
        candidates_scored = [(compute_candidate_score(fn, fp), fn, fp) for fn, fp in candidates]
        candidates_scored.sort(key=lambda x: x[0], reverse=True)
        remaining = [(fn, fp) for _, fn, fp in candidates_scored]

        identified = {}
        logs = []

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
