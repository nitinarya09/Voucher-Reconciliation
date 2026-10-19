# -*- coding: utf-8 -*-
"""
File Importer Module
Handles streaming/chunked parsing of delimited text and Excel files,
source-row preservation, validation, and conversion to NormalizedRecords.
"""

import os
import csv
import pandas as pd
from core.format_detector import FormatDetector
from core.column_mapper import ColumnMapper
from core.data_normalizer import DataNormalizer

class ImportedDataset:
    def __init__(self, file_id, file_path, file_role="generic", mapping=None, delimiter=None, encoding=None, has_header=None, target_month=None, target_year=None):
        self.file_id = file_id
        if isinstance(file_path, (list, tuple)):
            self.file_paths = [p for p in file_path if p and os.path.exists(p)]
            self.file_path = self.file_paths[0] if self.file_paths else ""
            self.filename = f"{len(self.file_paths)} Files Merged" if len(self.file_paths) > 1 else (os.path.basename(self.file_path) if self.file_path else "")
            self.file_size = sum(os.path.getsize(p) for p in self.file_paths)
        else:
            self.file_paths = [file_path] if file_path and os.path.exists(file_path) else []
            self.file_path = file_path
            self.filename = os.path.basename(file_path) if file_path else ""
            self.file_size = os.path.getsize(file_path) if file_path and os.path.exists(file_path) else 0

        self.file_role = file_role
        self.delimiter = delimiter
        self.encoding = encoding
        self.has_header = has_header
        self.target_month = str(target_month).strip() if target_month and str(target_month).strip().upper() != 'ALL' else None
        self.target_year = str(target_year).strip() if target_year and str(target_year).strip().upper() != 'ALL' else None

        self.mapper = mapping or ColumnMapper()
        self.records = []
        self.headers = []

        self.total_lines = 0
        self.blank_lines = 0
        self.malformed_records = []
        self.import_warnings = []
        self.import_errors = []
        self.is_loaded = False

    def load(self, max_records=None):
        """Loads and parses the file (or list of files) into NormalizedRecords."""
        if not self.file_paths:
            self.import_errors.append(f"File(s) not found for role {self.file_id}: {self.file_path}")
            return False

        self.records = []
        self.malformed_records = []
        self.total_lines = 0
        self.blank_lines = 0

        for current_path in self.file_paths:
            curr_fn = os.path.basename(current_path)

            # 1. Gracefully skip empty downloads (0 bytes)
            if not os.path.exists(current_path) or os.path.getsize(current_path) == 0:
                self.import_warnings.append(f"Skipped empty file (0 bytes): '{curr_fn}'")
                continue

            # 2. Gracefully detect and skip IFMIS / VLC portal timeout or HTML error pages
            try:
                with open(current_path, 'rb') as f_chk:
                    head_bytes = f_chk.read(512).lower()
                    if b'<!doctype' in head_bytes or b'<html' in head_bytes or b'504 gateway' in head_bytes or b'session expired' in head_bytes:
                        self.import_warnings.append(f"Skipped corrupt download (HTML error/gateway timeout): '{curr_fn}'")
                        continue
            except Exception:
                pass

            ext = os.path.splitext(curr_fn)[1].lower()

            # 3. Native Excel parsing for .xlsx / .xls files (e.g. COMPAY files)
            if ext in ['.xlsx', '.xls']:
                try:
                    import pandas as pd
                    try:
                        df = pd.read_excel(current_path, dtype=str, engine='calamine')
                    except Exception:
                        df = pd.read_excel(current_path, dtype=str)
                    df = df.fillna('')

                    # Filter by target month if specified and MONTH column exists
                    if self.target_month and 'MONTH' in df.columns:
                        clean_target_m = str(int(self.target_month)) if self.target_month.isdigit() else self.target_month
                        df = df[df['MONTH'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True) == clean_target_m]

                    headers = [str(c).strip() for c in df.columns]
                    if not self.headers:
                        self.headers = headers

                    row_extractor = self.mapper.build_row_extractor(headers)
                    raw_values = df.values
                    norm_rec_fn = DataNormalizer.normalize_record

                    for row_idx, row_values in enumerate(raw_values, start=2):
                        self.total_lines += 1
                        try:
                            raw_mapped = row_extractor(row_values)
                            norm_rec = norm_rec_fn(
                                raw_mapped=raw_mapped,
                                source_file=curr_fn,
                                source_row=row_idx
                            )
                            self.records.append(norm_rec)
                            if not norm_rec.is_valid:
                                self.malformed_records.append(norm_rec)
                        except Exception as ex:
                            self.malformed_records.append({"row": row_idx, "error": str(ex), "raw": row_values, "file": curr_fn})

                        if max_records and len(self.records) >= max_records:
                            break
                    continue
                except Exception as ex:
                    self.import_errors.append(f"Excel import failed for '{curr_fn}': {str(ex)}")
                    continue

            # 4. Standard text/csv/tsv file parsing
            meta = FormatDetector.inspect_file(current_path)
            enc = self.encoding or meta['encoding']
            delim = self.delimiter or meta['delimiter']
            has_hdr = self.has_header if self.has_header is not None else meta['has_header']

            try:
                with open(current_path, 'r', encoding=enc, errors='replace') as f:
                    reader = csv.reader(f, delimiter=delim)
                    
                    header_row = None
                    start_row = 1
                    if has_hdr:
                        header_row = next(reader, None)
                        self.total_lines += 1
                        start_row = 2
                        if header_row and not self.headers:
                            self.headers = [h.strip() for h in header_row]

                    row_extractor = self.mapper.build_row_extractor(self.headers)
                    norm_rec_fn = DataNormalizer.normalize_record

                    for row_idx, row in enumerate(reader, start=start_row):
                        self.total_lines += 1
                        if not row or (len(row) == 1 and not row[0].strip()):
                            self.blank_lines += 1
                            continue

                        # Map raw columns to internal fields using fast extractor
                        try:
                            raw_mapped = row_extractor(row)
                            norm_rec = norm_rec_fn(
                                raw_mapped=raw_mapped,
                                source_file=curr_fn,
                                source_row=row_idx
                            )
                            self.records.append(norm_rec)
                            if not norm_rec.is_valid:
                                self.malformed_records.append(norm_rec)
                        except Exception as ex:
                            self.malformed_records.append({"row": row_idx, "error": str(ex), "raw": row, "file": curr_fn})

                        if max_records and len(self.records) >= max_records:
                            break

            except Exception as e:
                self.import_errors.append(f"Import failed for '{curr_fn}': {str(e)}")

        self.is_loaded = len(self.records) > 0
        return self.is_loaded

    def get_summary(self):
        """Returns metadata summary of the imported dataset."""
        unique_vouchers = set()
        for r in self.records:
            v_no = r.get('vou_no')
            if v_no:
                unique_vouchers.add((r.get('try_cd') or '', r.get('mhcd') or '', str(v_no).strip()))

        return {
            "file_id": self.file_id,
            "filename": self.filename,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "encoding": self.encoding,
            "delimiter": self.delimiter,
            "has_header": self.has_header,
            "total_lines": self.total_lines,
            "blank_lines": self.blank_lines,
            "valid_records_count": len(self.records) - len(self.malformed_records),
            "malformed_records_count": len(self.malformed_records),
            "total_parsed_records": len(self.records),
            "unique_vouchers_count": len(unique_vouchers),
            "is_loaded": self.is_loaded,
            "errors": self.import_errors,
            "warnings": self.import_warnings
        }


class FileImportManager:
    """Manages independent loading, validation, and access for all 6 input files."""
    def __init__(self, config=None):
        self.config = config or {}
        self.files = {
            "file_1": None,  # IFMIS Gross, Net, Deductions
            "file_2": None,  # IFMIS Gross Amount
            "file_3": None,  # IFMIS AG Deduction
            "file_4": None,  # IFMIS Non-AG Deduction
            "file_5": None,  # IFMIS Net Amount
            "file_6": None   # VLC COMPAY
        }

    def register_file(self, file_id, file_path, custom_mapping=None, delimiter=None, encoding=None, has_header=None, target_month=None, target_year=None):
        """Registers and imports one of the 6 files."""
        if file_id not in self.files:
            raise ValueError(f"Invalid file_id: {file_id}. Must be one of {list(self.files.keys())}")

        mapper = ColumnMapper(custom_mapping) if custom_mapping else ColumnMapper.get_default_profile(file_id)
        dataset = ImportedDataset(
            file_id=file_id,
            file_path=file_path,
            file_role=file_id,
            mapping=mapper,
            delimiter=delimiter,
            encoding=encoding,
            has_header=has_header,
            target_month=target_month,
            target_year=target_year
        )
        dataset.load()
        self.files[file_id] = dataset
        return dataset.get_summary()

    def get_file(self, file_id):
        return self.files.get(file_id)

    def is_ready_to_reconcile(self):
        """Checks if minimum required files are loaded to run reconciliation.
        At minimum, File 2 (Detailed Gross) and File 6 (VLC COMPAY) must be loaded.
        Alternatively, File 1 (Bill Master) and File 6 (VLC COMPAY) can run reconciliation.
        """
        has_f6 = bool(self.files.get("file_6") and self.files["file_6"].is_loaded)
        has_f2 = bool(self.files.get("file_2") and self.files["file_2"].is_loaded)
        has_f1 = bool(self.files.get("file_1") and self.files["file_1"].is_loaded)
        return has_f6 and (has_f2 or has_f1)

    def is_all_6_ready(self):
        """Returns True if all 6 files are loaded."""
        return all(ds is not None and ds.is_loaded for ds in self.files.values())

    def is_all_ready(self):
        """Returns True if primary reconciliation files are ready."""
        return self.is_ready_to_reconcile()

    def get_all_summaries(self):
        summaries = {}
        for fid, ds in self.files.items():
            if ds:
                summaries[fid] = ds.get_summary()
            else:
                summaries[fid] = {"file_id": fid, "is_loaded": False}
        return summaries
