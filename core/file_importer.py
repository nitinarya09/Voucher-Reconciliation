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
    def __init__(self, file_id, file_path, file_role="generic", mapping=None, delimiter=None, encoding=None, has_header=None):
        self.file_id = file_id
        self.file_path = file_path
        self.file_role = file_role
        self.filename = os.path.basename(file_path) if file_path else ""
        self.file_size = os.path.getsize(file_path) if file_path and os.path.exists(file_path) else 0

        self.delimiter = delimiter
        self.encoding = encoding
        self.has_header = has_header

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
        """Loads and parses the file into NormalizedRecords."""
        if not self.file_path or not os.path.exists(self.file_path):
            self.import_errors.append(f"File not found: {self.file_path}")
            return False

        # Detect format if not explicitly provided
        if not self.encoding or not self.delimiter or self.has_header is None:
            meta = FormatDetector.inspect_file(self.file_path)
            self.encoding = self.encoding or meta['encoding']
            self.delimiter = self.delimiter or meta['delimiter']
            if self.has_header is None:
                self.has_header = meta['has_header']

        self.records = []
        self.malformed_records = []
        self.total_lines = 0
        self.blank_lines = 0

        try:
            with open(self.file_path, 'r', encoding=self.encoding, errors='replace') as f:
                reader = csv.reader(f, delimiter=self.delimiter)
                
                header_row = None
                start_row = 1
                if self.has_header:
                    header_row = next(reader, None)
                    self.total_lines += 1
                    start_row = 2
                    if header_row:
                        self.headers = [h.strip() for h in header_row]

                for row_idx, row in enumerate(reader, start=start_row):
                    self.total_lines += 1
                    if not row or (len(row) == 1 and not row[0].strip()):
                        self.blank_lines += 1
                        continue

                    # Map raw columns to internal fields
                    try:
                        raw_mapped = self.mapper.map_record(row, self.headers)
                        norm_rec = DataNormalizer.normalize_record(
                            raw_mapped=raw_mapped,
                            source_file=self.filename,
                            source_row=row_idx
                        )
                        self.records.append(norm_rec)
                        if not norm_rec.is_valid:
                            self.malformed_records.append(norm_rec)
                    except Exception as ex:
                        self.malformed_records.append({"row": row_idx, "error": str(ex), "raw": row})

                    if max_records and len(self.records) >= max_records:
                        break

            self.is_loaded = True
            return True

        except Exception as e:
            self.import_errors.append(f"Import failed: {str(e)}")
            self.is_loaded = False
            return False

    def get_summary(self):
        """Returns metadata summary of the imported dataset."""
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

    def register_file(self, file_id, file_path, custom_mapping=None, delimiter=None, encoding=None, has_header=None):
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
            has_header=has_header
        )
        dataset.load()
        self.files[file_id] = dataset
        return dataset.get_summary()

    def get_file(self, file_id):
        return self.files.get(file_id)

    def is_all_ready(self):
        return all(ds is not None and ds.is_loaded for ds in self.files.values())

    def get_all_summaries(self):
        summaries = {}
        for fid, ds in self.files.items():
            if ds:
                summaries[fid] = ds.get_summary()
            else:
                summaries[fid] = {"file_id": fid, "is_loaded": False}
        return summaries
