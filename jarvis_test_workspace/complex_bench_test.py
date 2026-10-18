"""Regression and integration tests for the expense-report analyzer."""

import csv
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from complex_bench_analyze import DEFAULT_CSV, DEFAULT_REPORT, analyze_expenses


ROOT = Path(__file__).resolve().parent


class TestExpenseReport(unittest.TestCase):
    def test_csv_has_eight_valid_rows(self):
        with DEFAULT_CSV.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
        self.assertEqual(len(rows), 8)
        self.assertTrue(all(len(row) == 2 for row in rows))

    def test_food_count_and_total(self):
        counts, totals, invalid = analyze_expenses(DEFAULT_CSV)
        self.assertEqual(invalid, [])
        self.assertEqual(counts["Food"], 3)
        self.assertEqual(totals["Food"], Decimal("30.00"))

    def test_travel_count_and_total(self):
        counts, totals, invalid = analyze_expenses(DEFAULT_CSV)
        self.assertEqual(invalid, [])
        self.assertEqual(counts["Travel"], 3)
        self.assertEqual(totals["Travel"], Decimal("60.00"))

    def test_supplies_count_and_total(self):
        counts, totals, invalid = analyze_expenses(DEFAULT_CSV)
        self.assertEqual(invalid, [])
        self.assertEqual(counts["Supplies"], 2)
        self.assertEqual(totals["Supplies"], Decimal("20.00"))

    def test_grand_total(self):
        counts, totals, invalid = analyze_expenses(DEFAULT_CSV)
        self.assertEqual(invalid, [])
        self.assertEqual(sum(totals.values(), Decimal("0.00")), Decimal("110.00"))

    def test_invalid_rows_are_rejected_without_mutating_source(self):
        original = DEFAULT_CSV.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "invalid.csv"
            sample.write_text("Food,12.50\n,2\nTravel,nope\nBad,0\nSupplies,5,extra\n", encoding="utf-8")
            counts, totals, invalid = analyze_expenses(sample)
        self.assertEqual(len(invalid), 4)
        self.assertEqual(counts, {"Food": 1})
        self.assertEqual(totals["Food"], Decimal("12.50"))
        self.assertEqual(DEFAULT_CSV.read_bytes(), original)

    def test_running_analyzer_writes_report_from_csv(self):
        # Write to a fresh temporary report rather than replacing the checked-in
        # workspace report, which may be open in an editor and locked on Windows.
        with tempfile.TemporaryDirectory() as tmp:
            output_report = Path(tmp) / "complex_bench_report.md"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "complex_bench_analyze.py"),
                    str(DEFAULT_CSV),
                    str(output_report),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertTrue(output_report.is_file())
            report = output_report.read_text(encoding="utf-8")
            self.assertIn("| Food | 3 | 30.00 |", report)
            self.assertIn("| Travel | 3 | 60.00 |", report)
            self.assertIn("| Supplies | 2 | 20.00 |", report)
            self.assertIn("**Grand total: 110.00**", report)
            self.assertIn("Invalid rows: 0", report)


if __name__ == "__main__":
    unittest.main()
