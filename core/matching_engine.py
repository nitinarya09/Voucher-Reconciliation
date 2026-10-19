# -*- coding: utf-8 -*-
"""
Matching Engine Module
Constructs configurable composite voucher matching keys, performs deterministic
voucher matching, detects duplicates, and classifies match outcomes.
"""

from decimal import Decimal
from collections import defaultdict

class VoucherMatchResult:
    def __init__(self, key, status, ifmis_records=None, compay_records=None, 
                 ifmis_amount=Decimal('0.00'), compay_amount=Decimal('0.00'), 
                 difference=Decimal('0.00'), explanation=""):
        self.key = key
        self.status = status  # EXACT_MATCH, AMOUNT_MISMATCH, IFMIS_ONLY, COMPAY_ONLY, DUPLICATES, AMBIGUOUS, INVALID
        self.ifmis_records = ifmis_records or []
        self.compay_records = compay_records or []
        self.ifmis_amount = ifmis_amount
        self.compay_amount = compay_amount
        self.difference = difference
        self.explanation = explanation

    def to_dict(self):
        # Extract primary identifiers
        first_rec = self.ifmis_records[0] if self.ifmis_records else (self.compay_records[0] if self.compay_records else None)
        try_cd = first_rec.get("try_cd", "") if first_rec else ""
        mhcd = first_rec.get("mhcd", "") if first_rec else ""
        vou_no = first_rec.get("vou_no", "") if first_rec else ""
        vou_date = first_rec.get("vou_date", "") if first_rec else ""
        ddo_cd = first_rec.get("ddo_cd", "") if first_rec else ""

        ifmis_sources = [{"file": r.source_file, "row": r.source_row} for r in self.ifmis_records]
        compay_sources = [{"file": r.source_file, "row": r.source_row} for r in self.compay_records]

        return {
            "key": self.key,
            "try_cd": try_cd,
            "mhcd": mhcd,
            "vou_no": vou_no,
            "vou_date": vou_date,
            "ddo_cd": ddo_cd,
            "ifmis_amount": float(self.ifmis_amount),
            "compay_amount": float(self.compay_amount),
            "difference": float(self.difference),
            "status": self.status,
            "explanation": self.explanation,
            "ifmis_count": len(self.ifmis_records),
            "compay_count": len(self.compay_records),
            "ifmis_sources": ifmis_sources,
            "compay_sources": compay_sources
        }


class MatchingEngine:
    def __init__(self, key_fields=None, tolerance=Decimal('0.00')):
        """
        key_fields: list of field names used to form composite key.
        Default: ["try_cd", "mhcd", "vou_no"]
        """
        self.key_fields = key_fields or ["try_cd", "mhcd", "vou_no"]
        self.tolerance = Decimal(str(tolerance))

    def build_key(self, record):
        """Constructs normalized composite key from record."""
        m = record.get("month", "")
        y = record.get("year", "")
        try_cd = record.get("try_cd", "")
        sec_m = str(record.get("sec_mhcd") or "").strip()
        effective_mhcd = '8009' if sec_m == '8009' else (record.get("mhcd") or "")
        vou_no = record.get("vou_no", "")

        # When multi-month/period data is loaded, incorporate month & year to prevent collisions
        if m and y:
            return f"{str(try_cd).strip()}_{str(m).strip()}_{str(y).strip()}_{str(effective_mhcd).strip()}_{str(vou_no).strip()}"

        parts = []
        for k in self.key_fields:
            if k == 'mhcd':
                parts.append(str(effective_mhcd).strip())
            else:
                val = record.get(k, "")
                parts.append(str(val).strip())
        return "_".join(parts)

    def group_by_key(self, records):
        """Groups list of NormalizedRecords by matching key."""
        grouped = defaultdict(list)
        for rec in records:
            key = self.build_key(rec)
            grouped[key].append(rec)
        return grouped

    def match_datasets(self, ifmis_records, compay_records, amount_field="gross_amt"):
        """
        Performs 1-to-1 and 1-to-many voucher matching between IFMIS and COMPAY records.
        Returns list of VoucherMatchResult objects and summary counts.
        """
        ifmis_grouped = self.group_by_key(ifmis_records)
        compay_grouped = self.group_by_key(compay_records)

        all_keys = set(ifmis_grouped.keys()) | set(compay_grouped.keys())
        results = []

        summary_counts = {
            "EXACT_MATCH": 0,
            "AMOUNT_MISMATCH": 0,
            "IFMIS_ONLY": 0,
            "COMPAY_ONLY": 0,
            "DUPLICATE_IFMIS": 0,
            "DUPLICATE_COMPAY": 0,
            "DUPLICATE_BOTH": 0,
            "AMBIGUOUS_MATCH": 0
        }

        for key in sorted(all_keys):
            if_list = ifmis_grouped.get(key, [])
            cp_list = compay_grouped.get(key, [])

            # Check IFMIS Only
            if if_list and not cp_list:
                amt = sum((r.get(amount_field) or Decimal('0.00')) for r in if_list)
                is_dup = len(if_list) > 1
                status = "DUPLICATE_IFMIS" if is_dup else "IFMIS_ONLY"
                expl = f"Present in IFMIS ({len(if_list)} rows), not found in COMPAY"
                results.append(VoucherMatchResult(key, status, if_list, [], amt, Decimal('0.00'), amt, expl))
                summary_counts[status] += 1
                continue

            # Check COMPAY Only
            if cp_list and not if_list:
                amt = sum((r.get(amount_field) or Decimal('0.00')) for r in cp_list)
                is_dup = len(cp_list) > 1
                status = "DUPLICATE_COMPAY" if is_dup else "COMPAY_ONLY"
                expl = f"Present in COMPAY ({len(cp_list)} rows), not found in IFMIS"
                results.append(VoucherMatchResult(key, status, [], cp_list, Decimal('0.00'), amt, -amt, expl))
                summary_counts[status] += 1
                continue

            # Present in both
            if_count = len(if_list)
            cp_count = len(cp_list)

            # Sum amounts
            if_amt = sum((r.get(amount_field) or Decimal('0.00')) for r in if_list)
            cp_amt = sum((r.get(amount_field) or Decimal('0.00')) for r in cp_list)
            diff = if_amt - cp_amt

            if if_count == 1 and cp_count == 1:
                # Single-to-Single match
                if abs(diff) <= self.tolerance:
                    status = "EXACT_MATCH"
                    expl = "Exact identifier and exact amount match"
                else:
                    status = "AMOUNT_MISMATCH"
                    expl = f"Gross amount mismatch of ₹{diff:,.2f}"
                results.append(VoucherMatchResult(key, status, if_list, cp_list, if_amt, cp_amt, diff, expl))
                summary_counts[status] += 1
            else:
                # Duplicate records exist on one or both sides
                status = "DUPLICATE_BOTH" if (if_count > 1 and cp_count > 1) else ("DUPLICATE_IFMIS" if if_count > 1 else "DUPLICATE_COMPAY")
                expl = f"Duplicate records detected: IFMIS has {if_count} row(s), COMPAY has {cp_count} row(s). Difference = ₹{diff:,.2f}"
                results.append(VoucherMatchResult(key, status, if_list, cp_list, if_amt, cp_amt, diff, expl))
                summary_counts[status] += 1

        return results, summary_counts
