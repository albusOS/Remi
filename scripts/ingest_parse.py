"""Dev tool: parse a file and print what the parser layer sees.

Usage:
    uv run scripts/ingest_parse.py <file> [--head N]

Shows filename, kind, metadata, column names, and the first N rows.
No vocab matching, no pipeline, no persistence.
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

    parser = argparse.ArgumentParser(description="Parse a document and show raw structure.")
    parser.add_argument("file", type=Path)
    parser.add_argument("--head", type=int, default=5, metavar="N", help="Rows to show (default 5)")
    args = parser.parse_args()

    path: Path = args.file
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    from remi.agent.documents.adapters.parsers import parse_document

    doc = parse_document(path.name, path.read_bytes(), _guess_content_type(path))

    out = {
        "filename": doc.filename,
        "kind": str(doc.kind),
        "row_count": doc.row_count,
        "column_count": len(doc.column_names),
        "chunk_count": len(doc.chunks),
        "page_count": doc.page_count,
        "metadata": doc.metadata or {},
        "tags": doc.tags,
        "column_names": doc.column_names,
        "sample_rows": doc.rows[: args.head],
    }
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
