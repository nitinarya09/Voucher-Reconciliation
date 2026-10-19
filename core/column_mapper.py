# -*- coding: utf-8 -*-
"""
Column Mapper Module
Handles mapping between raw file columns (or indices) and standard internal fields.
"""

import json
import os

INTERNAL_FIELDS = {
    "try_cd": {"label": "Treasury Code", "type": "string", "required_for_matching": True},
    "mhcd": {"label": "Major Head (MHCD)", "type": "string", "required_for_matching": True},
    "vou_no": {"label": "Voucher Number", "type": "string", "required_for_matching": True},
    "vou_date": {"label": "Voucher Date", "type": "date", "required_for_matching": False},
    "ddo_cd": {"label": "DDO Code", "type": "string", "required_for_matching": False},
    "token_no": {"label": "Token Number / Bill No", "type": "string", "required_for_matching": False},
    "gross_amt": {"label": "Gross Amount", "type": "decimal", "required_for_matching": False},
    "net_amt": {"label": "Net Amount", "type": "decimal", "required_for_matching": False},
    "ag_ded_amt": {"label": "AG Deduction Amount", "type": "decimal", "required_for_matching": False},
    "try_ded_amt": {"label": "Non-AG / Treasury Deduction Amount", "type": "decimal", "required_for_matching": False},
    "ded_amt": {"label": "Itemized Deduction Amount", "type": "decimal", "required_for_matching": False},
    "ded_mhcd": {"label": "Deduction Major Head", "type": "string", "required_for_matching": False},
    "te_no": {"label": "Transfer Entry (TE) Number", "type": "string", "required_for_matching": False},
    "ss_sop": {"label": "SOP Payment Flag", "type": "string", "required_for_matching": False},
    "sctnd_code": {"label": "Section Code", "type": "string", "required_for_matching": False},
    "smcd": {"label": "Sub-Major Head", "type": "string", "required_for_matching": False},
    "micd": {"label": "Minor Head", "type": "string", "required_for_matching": False},
    "shcd": {"label": "Scheme / Sub Head", "type": "string", "required_for_matching": False},
    "dhcd": {"label": "Detail Head", "type": "string", "required_for_matching": False},
    "sdcd": {"label": "Sub-Detail / Object Head", "type": "string", "required_for_matching": False},
    "vc": {"label": "Voted / Charged", "type": "string", "required_for_matching": False},
    "pn": {"label": "Plan / Non-Plan", "type": "string", "required_for_matching": False},
    "refund": {"label": "Refund Flag", "type": "string", "required_for_matching": False},
    "sec_mhcd": {"label": "Section Major Head (SEC_MHCD)", "type": "string", "required_for_matching": False},
    "month": {"label": "Accounting Month", "type": "string", "required_for_matching": False},
    "year": {"label": "Financial Year", "type": "string", "required_for_matching": False}
}

class ColumnMapper:
    def __init__(self, mapping_dict=None):
        """
        mapping_dict: dict mapping source column identifier (name or stringified index) to internal field key.
        e.g., {"3": "try_cd", "8": "mhcd", ...} or {"TRY_CD": "try_cd", ...}
        """
        self.mapping = mapping_dict or {}

    def map_record(self, raw_row, headers=None):
        """
        Maps a single raw row (list of values or dict) to internal fields dict.
        Returns: {internal_field: raw_value_str}
        """
        mapped = {}
        if isinstance(raw_row, dict):
            for src_col, target_field in self.mapping.items():
                if src_col in raw_row:
                    mapped[target_field] = str(raw_row[src_col] or "").strip()
        elif isinstance(raw_row, (list, tuple)):
            for src_key, target_field in self.mapping.items():
                val = ""
                # Check if src_key is an integer index
                if str(src_key).isdigit():
                    idx = int(src_key)
                    if 0 <= idx < len(raw_row):
                        val = str(raw_row[idx] or "").strip()
                elif headers and src_key in headers:
                    idx = headers.index(src_key)
                    if 0 <= idx < len(raw_row):
                        val = str(raw_row[idx] or "").strip()
                mapped[target_field] = val

    def build_row_extractor(self, headers=None):
        """
        Precomputes column index to target field mapping once,
        allowing high-speed O(1) row extraction without repeated headers.index() lookups.
        """
        extracted_indices = []
        if headers:
            header_map = {str(h).strip().upper(): idx for idx, h in enumerate(headers)}
            for src_key, target_field in self.mapping.items():
                s_key = str(src_key).strip().upper()
                if s_key in header_map:
                    extracted_indices.append((header_map[s_key], target_field))
                elif s_key.isdigit():
                    idx = int(s_key)
                    if idx < len(headers):
                        extracted_indices.append((idx, target_field))
        else:
            for src_key, target_field in self.mapping.items():
                if isinstance(src_key, int) or (isinstance(src_key, str) and src_key.isdigit()):
                    extracted_indices.append((int(src_key), target_field))

        def fast_extractor(row_vals):
            mapped = {}
            row_len = len(row_vals)
            for idx, target_field in extracted_indices:
                if idx < row_len:
                    v = row_vals[idx]
                    mapped[target_field] = str(v).strip() if v is not None else ""
                else:
                    mapped[target_field] = ""
            return mapped

        return fast_extractor

    def validate_mapping(self, file_role="generic", matching_keys=None):
        """
        Validates if the column mapping contains all required fields for its role.
        Returns: (is_valid: bool, warnings: list, errors: list)
        """
        errors = []
        warnings = []
        mapped_targets = set(self.mapping.values())

        if matching_keys:
            for k in matching_keys:
                if k not in mapped_targets:
                    errors.append(f"Matching key field '{INTERNAL_FIELDS.get(k, {}).get('label', k)}' is not mapped.")

        # Check role-specific amount expectations
        if file_role in ["ifmis_file_1"]:
            for f in ["gross_amt", "net_amt"]:
                if f not in mapped_targets:
                    warnings.append(f"Field '{f}' is not mapped in File 1 (Gross/Net/Deductions).")
        elif file_role in ["ifmis_file_2", "vlc_compay_file_6"]:
            if "gross_amt" not in mapped_targets:
                errors.append(f"Gross Amount is mandatory for {file_role} but not mapped.")
        elif file_role in ["ifmis_file_5"]:
            if "net_amt" not in mapped_targets:
                errors.append("Net Amount is mandatory for File 5 but not mapped.")
        elif file_role in ["ifmis_file_3", "ifmis_file_4"]:
            if "ded_amt" not in mapped_targets:
                errors.append("Deduction Amount is mandatory for deduction schedules but not mapped.")

        return len(errors) == 0, warnings, errors

    @classmethod
    def get_default_profile(cls, file_key, config_path=None):
        """Loads default mapping from configuration file."""
        if not config_path:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "default_settings.json")

        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
                profiles = cfg.get("default_column_mappings", {})
                if file_key in profiles:
                    return cls(profiles[file_key].get("columns", {}))

        return cls({})
