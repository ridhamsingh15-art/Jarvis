"""Validate transaction rows and write a report from the CSV data."""

import csv
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_CSV = ROOT / "complex_bench_transactions.csv"
DEFAULT_REPORT = ROOT / "complex_bench_report.md"


def analyze_expenses(file_path):
    """Return (counts, totals, invalid_rows) for a headerless Category,Amount CSV."""
    counts = defaultdict(int)
    totals = defaultdict(lambda: Decimal("0.00"))
    invalid_rows = []

    with open(file_path, "r", encoding="utf-8", newline="") as handle:
        for line_number, row in enumerate(csv.reader(handle), start=1):
            if len(row) != 2:
                invalid_rows.append((line_number, row, "expected exactly two columns"))
                continue
            category = row[0].strip()
            amount_text = row[1].strip()
            if not category:
                invalid_rows.append((line_number, row, "missing category"))
                continue
            try:
                amount = Decimal(amount_text)
                if not amount.is_finite() or amount <= 0:
                    raise InvalidOperation
            except (InvalidOperation, ValueError):
                invalid_rows.append((line_number, row, "amount must be a positive number"))
                continue
            counts[category] += 1
            totals[category] += amount

    return dict(counts), dict(totals), invalid_rows


def build_report(counts, totals, invalid_rows):
    grand_total = sum(totals.values(), Decimal("0.00"))
    lines = [
        "# Expense Report",
        "",
        "| Category | Count | Total |",
        "|---|---:|---:|",
    ]
    for category in sorted(totals):
        lines.append(f"| {category} | {counts[category]} | {totals[category]:.2f} |")
    lines.extend(["", f"**Grand total: {grand_total:.2f}**", "", f"Invalid rows: {len(invalid_rows)}"])
    if invalid_rows:
        lines.append("")
        lines.extend(f"- Line {line_number}: {row!r} ({reason})" for line_number, row, reason in invalid_rows)
    lines.append("")
    return "\n".join(lines)


def main():
    csv_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_CSV
    report_path = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else DEFAULT_REPORT
    counts, totals, invalid_rows = analyze_expenses(csv_path)
    report_path.write_text(build_report(counts, totals, invalid_rows), encoding="utf-8")
    print(f"Rows accepted: {sum(counts.values())}")
    print(f"Rows rejected: {len(invalid_rows)}")
    print(f"Grand total: {sum(totals.values(), Decimal('0.00')):.2f}")
    print(f"Report: {report_path}")
    return 1 if invalid_rows else 0


if __name__ == "__main__":
    raise SystemExit(main())
