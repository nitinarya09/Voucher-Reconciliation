# -*- coding: utf-8 -*-
"""
Data Normalizer Module
Converts raw string fields into normalized internal representation with Decimal precision.
Preserves original values, leading zeroes, source file and source row traceability.
"""

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

TREASURY_MAPPING = {
    # Master Catalog of all 58 Madhya Pradesh Treasuries
    "BAL": "010", "010": "010",
    "BAD": "020", "020": "020",
    "BET": "030", "030": "030",
    "BHI": "040", "040": "040",
    "BPL": "050", "050": "050",
    "VIN": "051", "051": "051",
    "VAL": "052", "052": "052",
    "CTB": "054", "054": "054",
    "CHA": "060", "060": "060",
    "CHI": "070", "070": "070",
    "DAM": "080", "080": "080",
    "DAT": "090", "090": "090",
    "DEW": "100", "100": "100",
    "DHA": "110", "110": "110",
    "DIN": "120", "120": "120",
    "GUN": "130", "130": "130",
    "GWL": "140", "140": "140",
    "MML": "141", "141": "141",
    "HAR": "150", "150": "150",
    "HOS": "160", "160": "160",
    "IND": "170", "170": "170",
    "INC": "171", "171": "171",
    "JBP": "180", "180": "180",
    "JHA": "190", "190": "190",
    "KAT": "200", "200": "200",
    "KHA": "210", "210": "210",
    "KAR": "220", "220": "220",
    "MAN": "230", "230": "230",
    "MND": "240", "240": "240",
    "MOE": "250", "250": "250", "MOR": "250",
    "NAR": "260", "260": "260",
    "NEE": "270", "270": "270",
    "PAN": "280", "280": "280",
    "RIS": "290", "290": "290",
    "RAJ": "300", "300": "300",
    "RAT": "310", "310": "310",
    "REW": "320", "320": "320",
    "SAG": "330", "330": "330",
    "SAT": "340", "340": "340",
    "SEH": "350", "350": "350",
    "SEO": "360", "360": "360",
    "SHA": "370", "370": "370",
    "SAJ": "380", "380": "380",
    "SHI": "390", "390": "390",
    "SHE": "400", "400": "400",
    "SID": "410", "410": "410",
    "TIK": "420", "420": "420",
    "UJJ": "430", "430": "430",
    "UMA": "440", "440": "440",
    "VID": "450", "450": "450",
    "ANU": "460", "460": "460",
    "ASH": "470", "470": "470",
    "BUR": "480", "480": "480",
    "ALI": "490", "490": "490",
    "SNG": "500", "500": "500",
    "AGR": "510", "510": "510",
    "NIW": "520", "520": "520",
    "MAU": "530", "530": "530",
    "PDH": "540", "540": "540",
    "MAI": "550", "550": "550"
}

class NormalizedRecord:
    def __init__(self, source_file, source_row, raw_dict, normalized_dict, errors=None, warnings=None):
        self.source_file = source_file
        self.source_row = source_row
        self.raw_data = raw_dict  # original source strings
        self.data = normalized_dict  # normalized values (Decimal for money, clean strings for IDs)
        self.errors = errors or []
        self.warnings = warnings or []

    @property
    def is_valid(self):
        return len(self.errors) == 0

    def get(self, field, default=None):
        return self.data.get(field, default)

    def get_raw(self, field, default=""):
        return self.raw_data.get(field, default)


class DataNormalizer:
    @staticmethod
    def parse_amount(val_str):
        """
        Parses a monetary string into an exact Decimal value.
        Handles commas, currency symbols, parentheses for negative amounts, and decimals.
        Returns: (Decimal value, is_valid: bool, error_msg: str)
        """
        if val_str is None:
            return Decimal('0.00'), True, ""
        
        s = str(val_str).strip()
        if not s:
            return Decimal('0.00'), True, ""

        # Remove currency symbols and spaces
        clean = re.sub(r'[₹$€£\s]', '', s)
        # Check for parentheses: (100.50) -> -100.50
        if clean.startswith('(') and clean.endswith(')'):
            clean = '-' + clean[1:-1]
        
        # Remove commas
        clean = clean.replace(',', '')

        try:
            dec = Decimal(clean).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            return dec, True, ""
        except (InvalidOperation, ValueError):
            return None, False, f"Invalid monetary value: '{s}'"

    @staticmethod
    def normalize_identifier(val_str):
        """
        Normalizes an identifier while strictly preserving leading zeroes and alphanumeric characters.
        """
        if val_str is None:
            return ""
        s = str(val_str).strip()
        # Remove trailing .0 from floating point imports
        if s.endswith('.0') and s[:-2].isdigit():
            s = s[:-2]
        return s

    @staticmethod
    def normalize_date(val_str):
        """
        Normalizes a date string into standard DD-MM-YYYY format across IFMIS (DD/MM/YYYY)
        and VLC COMPAY (DD-MM-YYYY or YYYY-MM-DD).
        """
        if not val_str:
            return ""
        s = str(val_str).strip()
        if not s:
            return ""
        # Standardize delimiters
        clean = re.sub(r'[/.\\]', '-', s)
        parts = clean.split('-')
        if len(parts) == 3:
            p0, p1, p2 = parts[0].strip(), parts[1].strip(), parts[2].strip()
            # Case: YYYY-MM-DD
            if len(p0) == 4 and p0.isdigit():
                return f"{p2.zfill(2)}-{p1.zfill(2)}-{p0}"
            # Case: DD-MM-YYYY
            elif len(p2) == 4 and p2.isdigit():
                return f"{p0.zfill(2)}-{p1.zfill(2)}-{p2}"
        return clean

    @classmethod
    def normalize_treasury_code(cls, try_val):
        """Normalizes treasury code to 3-digit numeric format where applicable."""
        code = cls.normalize_identifier(try_val).upper()
        return TREASURY_MAPPING.get(code, code)

    @classmethod
    def normalize_record(cls, raw_mapped, source_file, source_row):
        """
        Takes raw mapped dict {field_name: raw_string} and returns NormalizedRecord.
        """
        norm = {}
        errors = []
        warnings = []

        # Identifier and Classification fields
        for id_field in ['try_cd', 'mhcd', 'sec_mhcd', 'vou_no', 'ddo_cd', 'token_no', 'ded_mhcd', 'te_no', 'ss_sop', 'sctnd_code', 'bill_no', 'smcd', 'micd', 'shcd', 'dhcd', 'sdcd', 'vc', 'pn', 'refund']:
            raw_v = raw_mapped.get(id_field, "")
            norm[id_field] = cls.normalize_identifier(raw_v)

        # Treasury code normalization
        if norm.get('try_cd'):
            norm['try_cd'] = cls.normalize_treasury_code(norm['try_cd'])

        # Date normalization
        if 'vou_date' in raw_mapped:
            norm['vou_date'] = cls.normalize_date(raw_mapped.get('vou_date', ''))

        # Month and Year normalization
        if 'month' in raw_mapped and raw_mapped['month']:
            m_val = cls.normalize_identifier(raw_mapped['month'])
            norm['month'] = str(int(m_val)) if m_val.isdigit() else m_val
        if 'year' in raw_mapped and raw_mapped['year']:
            y_val = cls.normalize_identifier(raw_mapped['year'])
            if y_val.isdigit():
                norm['year'] = f"20{y_val}" if len(y_val) == 2 else y_val
            else:
                norm['year'] = y_val

        if norm.get('vou_date') and (not norm.get('month') or not norm.get('year')):
            d_parts = norm['vou_date'].split('-')
            if len(d_parts) == 3:
                if not norm.get('month') and d_parts[1].isdigit():
                    norm['month'] = str(int(d_parts[1]))
                if not norm.get('year') and d_parts[2].isdigit():
                    y_part = d_parts[2]
                    norm['year'] = f"20{y_part}" if len(y_part) == 2 else y_part

        # Monetary fields
        money_fields = ['gross_amt', 'net_amt', 'ag_ded_amt', 'try_ded_amt', 'ded_amt']
        for m_field in money_fields:
            if m_field in raw_mapped:
                raw_amt = raw_mapped.get(m_field, "")
                dec_val, is_valid, err_msg = cls.parse_amount(raw_amt)
                if not is_valid:
                    errors.append(f"{m_field}: {err_msg}")
                    norm[m_field] = None
                else:
                    norm[m_field] = dec_val

        return NormalizedRecord(
            source_file=source_file,
            source_row=source_row,
            raw_dict=raw_mapped,
            normalized_dict=norm,
            errors=errors,
            warnings=warnings
        )
