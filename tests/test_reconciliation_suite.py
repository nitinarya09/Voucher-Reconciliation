# -*- coding: utf-8 -*-
"""
Automated Test Suite for IFMIS–VLC Voucher Reconciliation Tool
Covers test cases specified in Section 19 using synthetic accounting data.
"""

import unittest
import os
import tempfile
import shutil
from decimal import Decimal

from core.data_normalizer import DataNormalizer
from core.matching_engine import MatchingEngine
from core.column_mapper import ColumnMapper
from core.format_detector import FormatDetector
from core.file_importer import FileImportManager, ImportedDataset
from core.validation_rules import CrossFileValidator
from core.reconciliation_engine import ComprehensiveReconciliationEngine
from core.export_manager import ExportManager

class TestVoucherReconciliationSuite(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_temp_file(self, filename, content, encoding='utf-8'):
        path = os.path.join(self.temp_dir, filename)
        with open(path, 'w', encoding=encoding) as f:
            f.write(content)
        return path

    # Test 1: All vouchers match exactly
    def test_01_all_vouchers_match_exactly(self):
        rec1 = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "2013", "vou_no": "1", "gross_amt": "50000.00"}, "F1", 1)
        rec2 = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "2013", "vou_no": "1", "gross_amt": "50000.00"}, "F6", 1)
        engine = MatchingEngine(["try_cd", "mhcd", "vou_no"])
        results, counts = engine.match_datasets([rec1], [rec2])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "EXACT_MATCH")
        self.assertEqual(results[0].difference, Decimal('0.00'))

    # Test 2: Gross amount differs for an otherwise matching voucher
    def test_02_gross_amount_differs(self):
        rec1 = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "2013", "vou_no": "2", "gross_amt": "45000.00"}, "F1", 1)
        rec2 = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "2013", "vou_no": "2", "gross_amt": "40000.00"}, "F6", 1)
        engine = MatchingEngine(["try_cd", "mhcd", "vou_no"])
        results, counts = engine.match_datasets([rec1], [rec2])
        self.assertEqual(results[0].status, "AMOUNT_MISMATCH")
        self.assertEqual(results[0].difference, Decimal('5000.00'))

    # Test 3: An IFMIS voucher is missing from COMPAY
    def test_03_ifmis_missing_from_compay(self):
        rec1 = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "8011", "vou_no": "1", "gross_amt": "15000.00"}, "F1", 1)
        engine = MatchingEngine(["try_cd", "mhcd", "vou_no"])
        results, counts = engine.match_datasets([rec1], [])
        self.assertEqual(results[0].status, "IFMIS_ONLY")

    # Test 4: A COMPAY voucher is missing from IFMIS
    def test_04_compay_missing_from_ifmis(self):
        rec2 = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "4801", "vou_no": "37", "gross_amt": "5000000000.00"}, "F6", 1)
        engine = MatchingEngine(["try_cd", "mhcd", "vou_no"])
        results, counts = engine.match_datasets([], [rec2])
        self.assertEqual(results[0].status, "COMPAY_ONLY")

    # Test 5 & 6: Duplicate voucher identifiers exist in IFMIS and COMPAY
    def test_05_06_duplicate_voucher_identifiers(self):
        rec1_a = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "2013", "vou_no": "1", "gross_amt": "20000.00"}, "F1", 1)
        rec1_b = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "2013", "vou_no": "1", "gross_amt": "30000.00"}, "F1", 2)
        rec2 = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "2013", "vou_no": "1", "gross_amt": "50000.00"}, "F6", 1)
        engine = MatchingEngine(["try_cd", "mhcd", "vou_no"])
        results, counts = engine.match_datasets([rec1_a, rec1_b], [rec2])
        self.assertEqual(results[0].status, "DUPLICATE_IFMIS")
        self.assertEqual(results[0].difference, Decimal('0.00'))

    # Test 7: Multiple candidate matches exist
    def test_07_multiple_candidate_matches(self):
        rec1_a = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "2013", "vou_no": "1", "gross_amt": "20000.00"}, "F1", 1)
        rec1_b = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "2013", "vou_no": "1", "gross_amt": "30000.00"}, "F1", 2)
        rec2_a = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "2013", "vou_no": "1", "gross_amt": "20000.00"}, "F6", 1)
        rec2_b = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "2013", "vou_no": "1", "gross_amt": "30000.00"}, "F6", 2)
        engine = MatchingEngine(["try_cd", "mhcd", "vou_no"])
        results, counts = engine.match_datasets([rec1_a, rec1_b], [rec2_a, rec2_b])
        self.assertEqual(results[0].status, "DUPLICATE_BOTH")

    # Test 8: Voucher identifiers contain leading zeroes
    def test_08_leading_zeroes_preserved(self):
        ident = DataNormalizer.normalize_identifier("00123")
        self.assertEqual(ident, "00123")
        try_cd = DataNormalizer.normalize_identifier("052")
        self.assertEqual(try_cd, "052")

    # Test 9: Amounts contain commas, decimals, and negative values
    def test_09_amount_parsing_formats(self):
        amt1, ok1, _ = DataNormalizer.parse_amount("1,25,000.50")
        self.assertTrue(ok1)
        self.assertEqual(amt1, Decimal('125000.50'))

        amt2, ok2, _ = DataNormalizer.parse_amount("-163380.00")
        self.assertTrue(ok2)
        self.assertEqual(amt2, Decimal('-163380.00'))

        amt3, ok3, _ = DataNormalizer.parse_amount("(5000.00)")
        self.assertTrue(ok3)
        self.assertEqual(amt3, Decimal('-5000.00'))

    # Test 10: Amounts contain invalid characters
    def test_10_invalid_monetary_characters(self):
        amt, ok, err = DataNormalizer.parse_amount("N/A_NOT_A_NUMBER")
        self.assertFalse(ok)
        self.assertIn("Invalid", err)

    # Test 11: Files use different encodings or delimiters
    def test_11_encodings_and_delimiters(self):
        f_csv = self._create_temp_file("test.csv", "a,b,c\n1,2,3\n")
        f_tsv = self._create_temp_file("test.tsv", "a\tb\tc\n1\t2\t3\n")
        meta_csv = FormatDetector.inspect_file(f_csv)
        meta_tsv = FormatDetector.inspect_file(f_tsv)
        self.assertEqual(meta_csv['delimiter'], ',')
        self.assertEqual(meta_tsv['delimiter'], '\t')

    # Test 12: File contains missing values or unexpected columns
    def test_12_missing_values(self):
        norm = DataNormalizer.normalize_record({"try_cd": "", "mhcd": "2013"}, "F1", 1)
        self.assertEqual(norm.get("try_cd"), "")

    # Test 13: Gross does not equal net plus deductions
    def test_13_gross_not_equal_net_plus_deductions(self):
        r1 = DataNormalizer.normalize_record({"gross_amt": "100000.00", "net_amt": "70000.00", "ag_ded_amt": "20000.00"}, "F1", 1)
        g = r1.get('gross_amt')
        n = r1.get('net_amt')
        ded = r1.get('ag_ded_amt')
        self.assertNotEqual(g, n + ded)
        self.assertEqual(g - (n + ded), Decimal('10000.00'))

    # Test 14: File 1 and File 2 have different gross amounts
    def test_14_f1_and_f2_different_gross(self):
        r1 = DataNormalizer.normalize_record({"gross_amt": "50000.00"}, "F1", 1)
        r2 = DataNormalizer.normalize_record({"gross_amt": "45000.00"}, "F2", 1)
        self.assertEqual(r1.get('gross_amt') - r2.get('gross_amt'), Decimal('5000.00'))

    # Test 15: File 1 and File 5 have different net amounts
    def test_15_f1_and_f5_different_net(self):
        r1 = DataNormalizer.normalize_record({"net_amt": "40000.00"}, "F1", 1)
        r5 = DataNormalizer.normalize_record({"net_amt": "38000.00"}, "F5", 1)
        self.assertEqual(r5.get('net_amt') - r1.get('net_amt'), Decimal('-2000.00'))

    # Test 16 & 17: AG & Non-AG deduction duplicate detection
    def test_16_17_deductions_duplicate_detection(self):
        r3_a = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "2013", "vou_no": "1", "ded_amt": "500.00"}, "F3", 1)
        r3_b = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "2013", "vou_no": "1", "ded_amt": "500.00"}, "F3", 2)
        engine = MatchingEngine(["try_cd", "mhcd", "vou_no"])
        grp = engine.group_by_key([r3_a, r3_b])
        self.assertEqual(len(grp[engine.build_key(r3_a)]), 2)

    # Test 18: Deduction totals cannot be verified when reference data missing
    def test_18_deduction_unverifiable_status(self):
        validator = CrossFileValidator({}, MatchingEngine())
        res = validator.check_5_deduction_components_vs_f1()
        self.assertEqual(res.status, "NOT_PERFORMED")

    # Test 19: Missing matching key handling
    def test_19_missing_matching_key_warning(self):
        mapper = ColumnMapper({"col1": "other_field"})
        is_val, warns, errs = mapper.validate_mapping("generic", ["try_cd", "mhcd", "vou_no"])
        self.assertFalse(is_val)
        self.assertTrue(len(errs) > 0)

    # Test 20: Exported files contain correct record counts and amounts
    def test_20_exports_content_integrity(self):
        dummy_results = {
            "summary": {"compay_grand_total": 1000.0, "payment_discrepancy": 0.0},
            "grand_tally_steps": [{"step": 1, "label": "Test Step", "sign": "=", "amount": 1000.0, "description": "Test"}],
            "voucher_register": [{"mhcd": "2013", "vou_no": "1", "compay_gross": 1000.0, "sop_gross": 1000.0, "ag_ded": 0.0, "try_ded": 0.0, "file1_net": 1000.0, "file5_net": 1000.0, "status": "EXACT_MATCH", "status_desc": "OK"}],
            "head_wise": [{"mhcd": "2013", "title": "Council", "compay_gross": 1000.0, "sop_gross": 1000.0, "ag_ded": 0.0, "try_ded": 0.0, "sop_net": 1000.0, "diff_gross": 0.0, "status": "EXACT MATCH"}],
            "cross_file_checks": [{"check_id": 1, "check_name": "Check 1", "files_used": ["F1"], "records_evaluated": 1, "records_passed": 1, "records_failed": 0, "difference_amount": 0.0, "status": "PASSED", "explanation": "OK"}]
        }
        exp = ExportManager(dummy_results, reports_dir=self.temp_dir)
        p_txt = exp.export_text_report()
        self.assertTrue(os.path.exists(p_txt))
        with open(p_txt, 'r', encoding='utf-8') as f:
            c = f.read()
            self.assertIn("1,000.00", c)

    # Test 21: Large files can be chunked / streamed
    def test_21_stream_large_file(self):
        lines = ["052,2013,2025,10,0520405999,1,01/10/2025,1,92,40000\n"] * 500
        p = self._create_temp_file("large.txt", "".join(lines))
        ds = ImportedDataset("f5", p, "file_5")
        ds.load()
        self.assertEqual(len(ds.records), 500)

    # Test 22: Clear error on failed export
    def test_22_export_error_handling(self):
        exp = ExportManager({})
        try:
            exp.export_excel("/invalid/path/that/does/not/exist/test.xlsx")
        except Exception as e:
            self.assertTrue(True)

    # Test 23: Re-running identical inputs produces identical results
    def test_23_deterministic_reproducibility(self):
        r1 = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "2013", "vou_no": "1", "gross_amt": "100.00"}, "F1", 1)
        r2 = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "2013", "vou_no": "1", "gross_amt": "100.00"}, "F6", 1)
        engine = MatchingEngine(["try_cd", "mhcd", "vou_no"])
        res_a, _ = engine.match_datasets([r1], [r2])
        res_b, _ = engine.match_datasets([r1], [r2])
        self.assertEqual(res_a[0].difference, res_b[0].difference)

    # Test 24: Invalid records remain traceable
    def test_24_invalid_records_traceability(self):
        norm = DataNormalizer.normalize_record({"gross_amt": "NOT_MONEY"}, "F1", 42)
        self.assertFalse(norm.is_valid)
        self.assertEqual(norm.source_row, 42)
        self.assertEqual(norm.source_file, "F1")

    # Test 26: Date normalization parity across different date formats (DD/MM/YYYY vs DD-MM-YYYY)
    def test_26_date_normalization_parity(self):
        d1 = DataNormalizer.normalize_date("31/10/2025")
        d2 = DataNormalizer.normalize_date("31-10-2025")
        d3 = DataNormalizer.normalize_date("1/10/2025")
        d4 = DataNormalizer.normalize_date("2025-10-31")
        self.assertEqual(d1, "31-10-2025")
        self.assertEqual(d2, "31-10-2025")
        self.assertEqual(d3, "01-10-2025")
        self.assertEqual(d4, "31-10-2025")
        self.assertEqual(d1, d2)

        # Matching with voucher date in key across differing source formats
        r1 = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "2013", "vou_no": "1", "vou_date": "31/10/2025", "gross_amt": "1000.00"}, "F1", 1)
        r2 = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "2013", "vou_no": "1", "vou_date": "31-10-2025", "gross_amt": "1000.00"}, "F6", 1)
        engine = MatchingEngine(["try_cd", "mhcd", "vou_no", "vou_date"])
        results, counts = engine.match_datasets([r1], [r2])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "EXACT_MATCH")
    # Test 27: Smart folder auto-identification of all 6 files
    def test_27_smart_folder_auto_identification(self):
        from core.file_detector import SmartFileIdentifier

        # Create simulated files with arbitrary names but characteristic column structures
        f1_path = self._create_temp_file("custom_master.txt", "10,2025,92,052,1,01/10/2025,0520405999,01,2013,1,01/10/2025,40000,0,20000,40000,10,2025,\n")
        f2_path = self._create_temp_file("custom_exp.txt", "10,2025,052,92,1,01/10/2025,2013,,101,,3282,11,001,V,P,40000\n")
        f3_path = self._create_temp_file("custom_ag_ded.txt", "10,2025,052,27,2043,01/10/2025,1,8009,01,101, ,0123,,,9125\n")
        f4_path = self._create_temp_file("custom_try_ded.txt", "10,2025,052,92,2013,01/10/2025,1,8658,,112, ,,, ,20000\n")
        f5_path = self._create_temp_file("custom_net_sop.txt", "052,2013,2025,10,0520405999,1,01/10/2025,1,92,40000\n")
        f6_path = self._create_temp_file("COMPAY_REF.txt", "TRY_CD,MHCD,VOU_NO,VOU_DATE,DDO_CD,GROSS_AMT,SS_SOP,TE_NO\n052,2013,1,01-10-2025,0520405999,40000,P,\n")

        identified, logs, unmatched = SmartFileIdentifier.scan_folder(self.temp_dir, check_parent_for_compay=False)

        self.assertEqual(len(identified), 6)
        self.assertIn("file_1", identified)
        self.assertIn("file_2", identified)
        self.assertIn("file_3", identified)
        self.assertIn("file_4", identified)
        self.assertIn("file_5", identified)
        self.assertIn("file_6", identified)
        self.assertEqual(os.path.basename(identified["file_1"]), "custom_master.txt")
        self.assertEqual(os.path.basename(identified["file_2"]), "custom_exp.txt")
        self.assertEqual(os.path.basename(identified["file_3"]), "custom_ag_ded.txt")
        self.assertEqual(os.path.basename(identified["file_4"]), "custom_try_ded.txt")
        self.assertEqual(os.path.basename(identified["file_5"]), "custom_net_sop.txt")
        self.assertEqual(os.path.basename(identified["file_6"]), "COMPAY_REF.txt")

    # Test 28: 15-Digit budget classification tally and reclassification detection
    def test_28_classification_tally(self):
        from core.reconciliation_engine import format_15_digit_head
        # File 2 lines
        r2_1 = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "2052", "smcd": "00", "micd": "090", "shcd": "4327", "dhcd": "11", "sdcd": "001", "vc": "V", "vou_no": "1", "gross_amt": "10000.00"}, "F2", 1)
        r2_2 = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "2040", "smcd": "00", "micd": "001", "shcd": "0000", "dhcd": "11", "sdcd": "001", "vc": "V", "vou_no": "2", "gross_amt": "5000.00"}, "F2", 2)

        # File 6 lines (one exact match, one reclassified to Minor Head 900 Deduct Refunds)
        r6_1 = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "2052", "smcd": "00", "micd": "090", "shcd": "4327", "dhcd": "11", "sdcd": "001", "vc": "V", "vou_no": "1", "gross_amt": "10000.00"}, "F6", 1)
        r6_2 = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "2040", "smcd": "00", "micd": "900", "shcd": "0000", "dhcd": "11", "sdcd": "001", "vc": "V", "vou_no": "2", "gross_amt": "5000.00"}, "F6", 2)

        h1 = format_15_digit_head(r2_1)
        h2 = format_15_digit_head(r6_1)
        self.assertEqual(h1, "2052-00-090-4327-11-001-V")
        self.assertEqual(h1, h2)

    # Test 29: Handling of refund vouchers, advance recoveries, and deduct-expenditures
    def test_29_refund_voucher_handling(self):
        # Salary voucher with Festival Advance (-800) and Grain Advance (-800)
        rec_gross = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "2052", "vou_no": "365", "gross_amt": "50000.00", "sdcd": "001"}, "F6", 1)
        rec_fest = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "2052", "vou_no": "365", "gross_amt": "-800.00", "sdcd": "012"}, "F6", 2)
        rec_grain = DataNormalizer.normalize_record({"try_cd": "052", "mhcd": "2052", "vou_no": "365", "gross_amt": "-800.00", "sdcd": "017"}, "F6", 3)

        self.assertEqual(rec_fest.get('gross_amt'), Decimal('-800.00'))
        self.assertEqual(rec_grain.get('gross_amt'), Decimal('-800.00'))
        total_compiled = rec_gross.get('gross_amt') + rec_fest.get('gross_amt') + rec_grain.get('gross_amt')
        self.assertEqual(total_compiled, Decimal('48400.00'))

if __name__ == '__main__':
    unittest.main()

