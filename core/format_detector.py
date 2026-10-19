# -*- coding: utf-8 -*-
"""
File Format & Encoding Detector Module
Detects encoding, delimiter, header presence, and extracts preview rows.
"""

import os
import csv
import io

COMMON_ENCODINGS = ['utf-8-sig', 'utf-8', 'cp1252', 'latin1', 'ascii']
COMMON_DELIMITERS = [',', '\t', '|', ';']

class FormatDetector:
    @staticmethod
    def detect_encoding(file_path, sample_bytes=65536):
        """Detects the character encoding of the file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(file_path, 'rb') as f:
            raw = f.read(sample_bytes)

        if raw.startswith(b'\xef\xbb\xbf'):
            return 'utf-8-sig'

        for enc in ['utf-8', 'cp1252', 'latin1']:
            try:
                raw.decode(enc)
                return enc
            except UnicodeDecodeError:
                continue

        return 'latin1'

    @staticmethod
    def detect_delimiter(sample_lines):
        """Detects the most consistent delimiter from a list of sample text lines."""
        if not sample_lines:
            return ','

        best_delim = ','
        best_score = -1

        for delim in COMMON_DELIMITERS:
            counts = [line.count(delim) for line in sample_lines if line.strip()]
            if not counts or all(c == 0 for c in counts):
                continue
            
            # Check consistency of count across lines
            if len(set(counts)) == 1 and counts[0] > 0:
                score = counts[0] * 100
            else:
                avg = sum(counts) / len(counts)
                variance = sum((c - avg) ** 2 for c in counts) / len(counts)
                score = (avg / (1 + variance)) * 10

            if score > best_score:
                best_score = score
                best_delim = delim

        return best_delim

    @staticmethod
    def detect_header(parsed_rows):
        """Detects if the first row is a header row."""
        if len(parsed_rows) < 2:
            return False

        row0 = parsed_rows[0]
        row1 = parsed_rows[1]

        # Common known header tokens in treasury / compilation
        known_tokens = {'YEAR_FROM', 'YEAR_TO', 'SS_SOP', 'TRY_CD', 'VOU_NO', 'MHCD', 'AMOUNT', 'GROSS', 'NET', 'DDO_CD', 'BILL_NO'}
        if any(col.strip().upper() in known_tokens for col in row0):
            return True

        # If row 0 has strings with no digits, and row 1 has digits in numeric columns
        row0_numeric = sum(1 for c in row0 if c.strip().replace('.', '', 1).replace('-', '', 1).isdigit())
        row1_numeric = sum(1 for c in row1 if c.strip().replace('.', '', 1).replace('-', '', 1).isdigit())

        if row0_numeric == 0 and row1_numeric > 0:
            return True

        return False

    @classmethod
    def inspect_file(cls, file_path, max_preview_rows=15):
        """
        Performs full inspection of the input file.
        Returns a dict of metadata, detected options, and sample rows.
        """
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        if file_size == 0:
            return {
                "file_path": file_path,
                "filename": os.path.basename(file_path),
                "file_size": 0,
                "encoding": "utf-8",
                "delimiter": ",",
                "has_header": False,
                "headers": [],
                "column_count": 0,
                "total_lines": 0,
                "blank_lines": 0,
                "data_records_estimate": 0,
                "preview_rows": [],
                "is_empty": True
            }

        ext = os.path.splitext(file_path)[1].lower()
        if ext in ['.xlsx', '.xls']:
            try:
                import pandas as pd
                df = pd.read_excel(file_path, nrows=max_preview_rows + 2, dtype=str)
                df = df.fillna('')
                headers = [str(c).strip() for c in df.columns]
                preview = [list(r) for r in df.values[:max_preview_rows]]
                return {
                    "file_path": file_path,
                    "filename": os.path.basename(file_path),
                    "file_size": file_size,
                    "encoding": "binary/xlsx",
                    "delimiter": "[Excel Sheet]",
                    "has_header": True,
                    "headers": headers,
                    "column_count": len(headers),
                    "total_lines": len(df),
                    "blank_lines": 0,
                    "data_records_estimate": len(df),
                    "preview_rows": preview,
                    "is_excel": True
                }
            except Exception:
                pass

        encoding = cls.detect_encoding(file_path)

        # Read sample lines
        sample_lines = []
        total_lines = 0
        blank_lines = 0

        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            for idx, line in enumerate(f):
                total_lines += 1
                if not line.strip():
                    blank_lines += 1
                if len(sample_lines) < 50:
                    sample_lines.append(line)

        delimiter = cls.detect_delimiter(sample_lines[:20])

        # Parse preview rows with detected delimiter
        parsed_preview = []
        for line in sample_lines:
            if line.strip():
                reader = csv.reader([line], delimiter=delimiter)
                try:
                    row = next(reader)
                    parsed_preview.append(row)
                except Exception:
                    parsed_preview.append(line.split(delimiter))

        has_header = cls.detect_header(parsed_preview)

        if has_header and parsed_preview:
            headers = [h.strip() for h in parsed_preview[0]]
            data_rows = parsed_preview[1:max_preview_rows + 1]
        else:
            col_count = len(parsed_preview[0]) if parsed_preview else 0
            headers = [f"Col_{i}" for i in range(col_count)]
            data_rows = parsed_preview[:max_preview_rows]

        return {
            "file_path": file_path,
            "filename": os.path.basename(file_path),
            "file_size": file_size,
            "encoding": encoding,
            "delimiter": delimiter,
            "has_header": has_header,
            "headers": headers,
            "column_count": len(headers),
            "total_lines": total_lines,
            "blank_lines": blank_lines,
            "data_records_estimate": total_lines - blank_lines - (1 if has_header else 0),
            "preview_rows": data_rows
        }
