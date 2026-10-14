# -*- coding: utf-8 -*-
"""
Data Normalizer Module
Converts raw string fields into normalized internal representation with Decimal precision.
Preserves original values, leading zeroes, source file and source row traceability.
"""

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

TREASURY_MAPPING = {
    "VAL": "052",
    "052": "052"
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
        for id_field in ['try_cd', 'mhcd', 'vou_no', 'ddo_cd', 'token_no', 'ded_mhcd', 'te_no', 'ss_sop', 'sctnd_code', 'bill_no', 'smcd', 'micd', 'shcd', 'dhcd', 'sdcd', 'vc', 'pn', 'refund']:
            raw_v = raw_mapped.get(id_field, "")
            norm[id_field] = cls.normalize_identifier(raw_v)

        # Treasury code normalization
        if norm.get('try_cd'):
            norm['try_cd'] = cls.normalize_treasury_code(norm['try_cd'])

        # Date normalization
        if 'vou_date' in raw_mapped:
            norm['vou_date'] = cls.normalize_date(raw_mapped.get('vou_date', ''))

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
