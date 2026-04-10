"""Dev tool: run vocab matching on a file's column headers.

Usage:
    uv run scripts/ingest_match.py <file>

Shows the detected report profile, the raw→canonical column map, any
unrecognised headers, and whether the deterministic pipeline will run
(should_proceed=true) or the LLM fallback is needed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _guess_content_type(path: Path) -> str:
    return {
        ".csv": "text/csv",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".pdf": "application/pdf",
        ".txt": "text/plain",
    }.get(path.suffix.lower(), "application/octet-stream")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Vocab-match a document's columns.")
    parser.add_argument("file", type=Path)
    args = parser.parse_args()

    path: Path = args.file
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    from remi.agent.documents.adapters.parsers import parse_document
    from remi.application.ingestion.vocab import match_columns

    doc = parse_document(path.name, path.read_bytes(), _guess_content_type(path))

    if not doc.column_names:
        print("error: no columns found — is this a tabular file?", file=sys.stderr)
        sys.exit(1)

    vocab = match_columns(doc.column_names)

    out = {
        "report_type": vocab.report_type,
        "primary_entity_type": vocab.primary_entity_type,
        "should_proceed": vocab.should_proceed,
        "column_map": vocab.column_map,
        "unrecognized": vocab.unrecognized,
        "review_notes": vocab.review_notes,
    }
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
