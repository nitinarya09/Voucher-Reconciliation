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

    MP_TREASURY_NAMES = {
        "010": "BALAGHAT TREASURY",
        "020": "Barwani District Treasury",
        "030": "Betul District Treasury",
        "040": "Bhind Treasury",
        "050": "District Treasury Office Bhopal",
        "051": "Vindhyachal Treasury",
        "052": "Vallabh Bhawan Treasury, Bhopal",
        "054": "Principal Treasury Officer Centre Treasury Bhopal",
        "060": "Chhatarpur Treasury",
        "070": "Chhindwara Treasury",
        "080": "Damoh Treasury",
        "090": "Datia Treasury",
        "100": "Dewas Treasury",
        "110": "Dhar Treasury",
        "120": "Dindori Treasury",
        "130": "Guna Treasury",
        "140": "Gwalior Gorkhi Treasury",
        "141": "Motimahal Gwalior Treasury",
        "150": "Harda Treasury",
        "160": "Hoshangabad Treasury",
        "170": "Indore District Treasury",
        "171": "Indore City Treasury",
        "180": "Jabalpur District Treasury",
        "181": "Jabalpur City Treasury",
        "190": "Jhabua Treasury",
        "200": "Katni Treasury",
        "210": "Khandva Treasury",
        "220": "Khargaun Treasury",
        "230": "Mandla Treasury",
        "240": "Mandsaur Treasury",
        "250": "Morena Treasury",
        "260": "Narsinghpur Treasury",
        "270": "Neemuch District Treasury",
        "280": "Panna Treasury",
        "290": "Raisen Treasury",
        "300": "Rajgarh Treasury",
        "310": "Ratlam Treasury",
        "320": "Rewa Treasury",
        "330": "Sagar Treasury",
        "340": "Satna Treasury",
        "350": "Sehore Treasury",
        "360": "Seoni Treasury",
        "370": "Shahdol Treasury",
        "380": "Shajapur Treasury",
        "390": "Shivpuri Treasury",
        "400": "Sheopur Treasury",
        "410": "Seedhi Treasury",
        "420": "Tikamgarh Treasury",
        "430": "Ujjain Treasury",
        "440": "Umaria Treasury",
        "450": "Vidisha Treasury",
        "460": "Anupur Treasury",
        "470": "Ashoknagar Treasury",
        "480": "Burhanpur Treasury",
        "490": "Alirajpur Treasury",
        "500": "Singrauli Treasury",
        "510": "Agar Malwa Treasury",
        "520": "District Treasury Office Niwari",
        "530": "District Treasury Mauganj",
        "540": "District Treasury Pandhurna",
        "550": "District Treasury Maihar"
    }

    last_disparity_report = None

    @classmethod
    def get_treasury_name(cls, code):
        if not code:
            return ""
        c = str(code).strip()
        from core.data_normalizer import TREASURY_MAPPING
        norm_c = TREASURY_MAPPING.get(c.upper(), c)
        return cls.MP_TREASURY_NAMES.get(norm_c, f"Treasury {norm_c}")

    @classmethod
    def extract_treasury_info(cls, filename, full_path):
        """Extracts treasury code and treasury descriptive name from file path/name."""
        norm_path = (full_path or '').replace('/', '\\')
        # 1. Check folder name: e.g. '054 - Principal Treasury Officer Centre Treasury Bhopal'
        m_dir = re.search(r'[\\/](\d{3})\s*-\s*([^\\/]+)[\\/]', norm_path)
        if m_dir:
            code = m_dir.group(1)
            name = m_dir.group(2).strip()
            return code, cls.get_treasury_name(code) or name

        # 2. Check filename 3-digit numeric treasury code
        m_fn = re.search(r'(?:^|[\W_])(\d{3})(?:[\W_]|$)', filename or '')
        if m_fn:
            code = m_fn.group(1)
            return code, cls.get_treasury_name(code)

        # 3. Check 3-letter short code: e.g. TRY_BAL, Split-ACD
        m_short = re.search(r'(?:TRY[_\s-]|Split-)([A-Z]{3})', filename or '', re.IGNORECASE)
        if m_short:
            sc = m_short.group(1).upper()
            from core.data_normalizer import TREASURY_MAPPING
            code = TREASURY_MAPPING.get(sc, sc)
            return code, cls.get_treasury_name(code)

        return "", ""

    @classmethod
    def classify_role_by_filename(cls, filename):
        lfn = (filename or '').lower()
        if "compay" in lfn or "vlc" in lfn or re.search(r'(^0?6[_\s\.-]|file[_\s-]?0?6\b)', lfn):
            return "file_6"
        elif re.search(r'(details[_\s-]?headwise|headwise|gross[_\s-]?exp|detailed|classification|^0?2[_\s\.-]|file[_\s-]?0?2\b)', lfn):
            return "file_2"
        elif re.search(r'(voucher[_\s-]?details|bill[_\s-]?master|gross[_\s-]?net|^0?1[_\s\.-]|file[_\s-]?0?1\b)', lfn):
            return "file_1"
        elif re.search(r'(non[_\s-]?ag|try[_\s-]?ded|treasury[_\s-]?ded|tds|^0?4[_\s\.-]|file[_\s-]?0?4\b)', lfn):
            return "file_4"
        elif re.search(r'(ag[_\s-]?deduction|ag[_\s-]?ded|gpf|^0?3[_\s\.-]|file[_\s-]?0?3\b)', lfn):
            return "file_3"
        elif re.search(r'(voucher[_\s-]?summary|net[_\s-]?sop|netsop|^0?5[_\s\.-]|file[_\s-]?0?5\b)', lfn) or (lfn.endswith("sop.txt") and not re.match(r'^[1234][_\.]', lfn)):
            return "file_5"
        return None

    @classmethod
    def scan_folder(cls, folder_path, treasury_code=None, month=None, year=None, check_parent_for_compay=True, return_diagnostics=False):
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

        # Check parent and sibling folders for COMPAY (especially month-specific consolidated files)
        if check_parent_for_compay:
            has_month_compay = False
            if month_tokens:
                for fn, fp in candidates:
                    lfn = fn.lower()
                    if ("compay" in lfn or "vlc" in lfn) and any(re.search(r'(?:^|[\W_])' + re.escape(tok) + r'(?:$|[\W_])', (fn + " " + fp).lower()) for tok in month_tokens):
                        has_month_compay = True
                        break

            has_any_compay = any("compay" in fn.lower() or "vlc" in fn.lower() for fn, _ in candidates)

            # If no month-specific COMPAY in folder, search parent & sibling folders
            if not has_month_compay or not has_any_compay:
                parent_dir = os.path.dirname(os.path.abspath(folder_path))
                if parent_dir and os.path.exists(parent_dir):
                    # Check files in parent dir
                    try:
                        for fn in os.listdir(parent_dir):
                            ext = os.path.splitext(fn)[1].lower()
                            if ext in ['.xls', '.xlsx', '.csv', '.txt'] and ("compay" in fn.lower() or "vlc" in fn.lower()):
                                candidates.append((fn, os.path.join(parent_dir, fn)))
                    except Exception:
                        pass
                    # Check sibling folders (e.g. compay_2025_26)
                    try:
                        for sub in os.listdir(parent_dir):
                            sub_p = os.path.join(parent_dir, sub)
                            if os.path.isdir(sub_p) and sub_p.lower() != os.path.abspath(folder_path).lower():
                                if "compay" in sub.lower() or "vlc" in sub.lower():
                                    for sfn in os.listdir(sub_p):
                                        ext = os.path.splitext(sfn)[1].lower()
                                        if ext in ['.xls', '.xlsx', '.csv', '.txt'] and ("compay" in sfn.lower() or "vlc" in sfn.lower()):
                                            candidates.append((sfn, os.path.join(sub_p, sfn)))
                    except Exception:
                        pass

        # -------------------------------------------------------------
        # Multi-File Mode: Full Financial Year / Multi-Treasury Ingestion
        # -------------------------------------------------------------
        if is_multi_mode:
            identified = {f"file_{i}": [] for i in range(1, 7)}
            role_treasuries = {f"file_{i}": {} for i in range(1, 7)}
            skipped_empty = []
            skipped_html = []
            seen_keys = set()
            logs = []

            for fn, full_p in candidates:
                role = cls.classify_role_by_filename(fn)
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
                        if role == "file_6" and (matches_year or "compay" in fn.lower()):
                            pass
                        else:
                            continue

                t_code, t_name = cls.extract_treasury_info(fn, full_p)

                # 1. Skip empty files (record for disparity analysis)
                if not os.path.exists(full_p) or os.path.getsize(full_p) == 0:
                    skipped_empty.append({
                        "role": role,
                        "code": t_code,
                        "name": t_name,
                        "filename": fn,
                        "path": full_p,
                        "reason": "Empty file on disk (0 bytes)"
                    })
                    continue

                # 2. Skip HTML error downloads (record for disparity analysis)
                is_html_error = False
                try:
                    with open(full_p, 'rb') as f_chk:
                        h = f_chk.read(256).lower()
                        if b'<!doctype' in h or b'<html' in h or b'504 gateway' in h:
                            is_html_error = True
                except Exception:
                    pass

                if is_html_error:
                    skipped_html.append({
                        "role": role,
                        "code": t_code,
                        "name": t_name,
                        "filename": fn,
                        "path": full_p,
                        "reason": "Corrupt HTML / 504 Gateway error download"
                    })
                    continue

                dedup_key = (role, fn.lower(), os.path.getsize(full_p))
                if dedup_key in seen_keys:
                    continue
                seen_keys.add(dedup_key)
                identified[role].append(full_p)
                if t_code:
                    role_treasuries[role][t_code] = {
                        "code": t_code,
                        "name": t_name,
                        "filename": fn,
                        "path": full_p,
                        "size": os.path.getsize(full_p)
                    }

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

            # Build Disparity & Missing Files Report
            ROLE_LABELS = {
                "file_1": "Voucher Details (File 01)",
                "file_2": "Voucher Detail - Details Headwise (File 02)",
                "file_3": "AG Deduction (File 03)",
                "file_4": "NON AG Deduction (File 04)",
                "file_5": "Voucher Summary (File 05)",
                "file_6": "VLC COMPAY (File 06)"
            }
            ifmis_roles = ["file_1", "file_2", "file_3", "file_4", "file_5"]
            active_ifmis = [r for r in ifmis_roles if len(identified[r]) > 0]
            counts = {r: len(identified[r]) for r in active_ifmis}
            max_count = max(counts.values()) if counts else 0
            all_active_codes = set().union(*[set(role_treasuries[r].keys()) for r in active_ifmis]) if active_ifmis else set()

            disparities = {}
            has_disparity = False
            for r in ifmis_roles:
                r_count = len(identified[r])
                r_codes = set(role_treasuries[r].keys())
                missing_for_r = []
                diff_codes = all_active_codes - r_codes
                if diff_codes and r_count > 0:
                    has_disparity = True
                    for dc in sorted(diff_codes):
                        skip_item = next((s for s in skipped_empty + skipped_html if s.get("role") == r and s.get("code") == dc), None)
                        t_name = cls.get_treasury_name(dc) or (skip_item.get("name") if skip_item else dc)
                        reason = skip_item["reason"] if skip_item else "File missing from folder on disk"
                        filename = skip_item["filename"] if skip_item else ""
                        present_in = [ROLE_LABELS[pr] for pr in active_ifmis if dc in role_treasuries[pr]]
                        missing_for_r.append({
                            "code": dc,
                            "name": t_name,
                            "filename": filename,
                            "reason": reason,
                            "present_in": present_in
                        })
                disparities[r] = {
                    "role": r,
                    "label": ROLE_LABELS.get(r, r),
                    "count": r_count,
                    "expected": max_count,
                    "missing_count": len(missing_for_r),
                    "missing_treasuries": missing_for_r
                }

            # Identify unpopulated treasuries across all IFMIS roles (0 bytes in all roles)
            empty_codes_by_role = {}
            for s in skipped_empty:
                c = s.get("code")
                if c:
                    empty_codes_by_role.setdefault(c, set()).add(s.get("role"))
            unpopulated_statewide = []
            for c, r_set in sorted(empty_codes_by_role.items()):
                if len(r_set) >= 4 and c not in all_active_codes:
                    unpopulated_statewide.append({
                        "code": c,
                        "name": cls.get_treasury_name(c),
                        "reason": "Unpopulated download (0 bytes across all files - no transactions in period)"
                    })

            disparity_report = {
                "has_disparity": has_disparity,
                "max_count": max_count,
                "active_treasuries_count": len(all_active_codes),
                "disparities": disparities,
                "unpopulated_statewide": unpopulated_statewide,
                "skipped_empty": skipped_empty,
                "skipped_html": skipped_html,
                "skipped_empty_count": len(skipped_empty),
                "skipped_html_count": len(skipped_html)
            }
            cls.last_disparity_report = disparity_report

            if return_diagnostics:
                return identified, logs, unmatched, disparity_report
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
        ROLE_LABELS = {
            "file_1": "Voucher Details (File 01)",
            "file_2": "Voucher Detail - Details Headwise (File 02)",
            "file_3": "AG Deduction (File 03)",
            "file_4": "NON AG Deduction (File 04)",
            "file_5": "Voucher Summary (File 05)",
            "file_6": "VLC COMPAY (File 06)"
        }
        disparities = {}
        for r_id, r_lbl in ROLE_LABELS.items():
            loaded = r_id in identified
            disparities[r_id] = {
                "role": r_id,
                "label": r_lbl,
                "count": 1 if loaded else 0,
                "expected": 1,
                "missing_count": 0 if loaded else 1,
                "missing_treasuries": [] if loaded else [{"code": treasury_code or "", "name": cls.get_treasury_name(treasury_code), "reason": "Not found in directory"}]
            }
        disparity_report = {
            "has_disparity": len(identified) < 6,
            "max_count": 1,
            "active_treasuries_count": 1 if identified else 0,
            "disparities": disparities,
            "unpopulated_statewide": [],
            "skipped_empty": [],
            "skipped_html": [],
            "skipped_empty_count": 0,
            "skipped_html_count": 0
        }
        cls.last_disparity_report = disparity_report

        if return_diagnostics:
            return identified, logs, unmatched, disparity_report
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
