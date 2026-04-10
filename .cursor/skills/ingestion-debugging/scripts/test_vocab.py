#!/usr/bin/env python3
"""Test vocabulary matching against an Excel file.

Shows exactly what the deterministic pipeline sees: column map, detected
report type, unrecognized headers, and whether the LLM path is needed.

Usage:
    uv run python .cursor/skills/ingestion-debugging/scripts/test_vocab.py <file.xlsx>
    uv run python .cursor/skills/ingestion-debugging/scripts/test_vocab.py <file.xlsx> --sheet "Sheet2"
"""

from __future__ import annotations

import sys
from pathlib import Path


def extract_headers(path: Path, sheet_name: str | None = None) -> list[str]:
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[sheet_name] if sheet_name else wb.active

    for row in ws.iter_rows(values_only=True):
        non_null = [c for c in row if c is not None]
        if len(non_null) >= 3:
            return [str(c).strip() for c in row if c is not None]

    return []


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: test_vocab.py <file.xlsx> [--sheet <name>]")
        sys.exit(1)

    path = Path(sys.argv[1])
    sheet_name = None
    if "--sheet" in sys.argv:
        idx = sys.argv.index("--sheet")
        sheet_name = sys.argv[idx + 1]

    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    # Add src to path so we can import remi modules directly
    src_root = Path(__file__).parent.parent.parent.parent.parent / "src"
    if src_root.exists():
        sys.path.insert(0, str(src_root))

    from remi.application.ingestion.vocab import match_columns

    headers = extract_headers(path, sheet_name)
    if not headers:
        print("No header row found (need 3+ non-null cells in a row).")
        sys.exit(1)

    print(f"\nFile: {path.name}")
    if sheet_name:
        print(f"Sheet: {sheet_name}")
    print(f"\nRaw headers ({len(headers)}):")
    for h in headers:
        print(f"  {h!r}")

    result = match_columns(headers)

    print(f"\n{'='*60}")
    print(f"Report type:    {result.report_type}")
    print(f"Entity type:    {result.primary_entity_type}")
    print(f"Should proceed: {result.should_proceed}  ({'deterministic path' if result.should_proceed else 'FALLS THROUGH TO LLM'})")

    print(f"\nColumn map ({len(result.column_map)}):")
    for raw, canonical in result.column_map.items():
        marker = "  [PRIVATE]" if canonical.startswith("_") else ""
        print(f"  {raw!r:40s} → {canonical}{marker}")

    if result.unrecognized:
        print(f"\nUnrecognized headers ({len(result.unrecognized)}) — add these to VOCAB in vocab.py:")
        for h in result.unrecognized:
            print(f"  {h!r}")

    if result.review_notes:
        print(f"\nReview notes:")
        for note in result.review_notes:
            print(f"  • {note}")

    print()


if __name__ == "__main__":
    main()
