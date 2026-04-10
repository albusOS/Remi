"""Dev tool: run the full deterministic ingestion pipeline without persisting.

Usage:
    uv run scripts/ingest_dry_run.py <file> [--manager NAME] [--verbose]

Parses the file, runs vocab matching, then executes the full extraction
pipeline against an in-memory store. Nothing is written to disk or the
database. Shows entities that *would* be created, rows accepted/rejected,
and any validation warnings.

Exits non-zero if the file requires the LLM fallback path — fix the vocab
first (scripts/ingest_match.py will show you which headers are unrecognised).
"""

from __future__ import annotations

import asyncio
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


async def _run(path: Path, manager_override: str | None, verbose: bool) -> dict:
    from remi.agent.documents.adapters.parsers import parse_document
    from remi.application.core.models.enums import ReportType
    from remi.application.ingestion.models import IngestionResult
    from remi.application.ingestion.operations import run_deterministic_pipeline
    from remi.application.ingestion.rules import resolve_manager_from_metadata, resolve_report_dates
    from remi.application.ingestion.vocab import match_columns
    from remi.application.stores.mem import InMemoryPropertyStore

    doc = parse_document(path.name, path.read_bytes(), _guess_content_type(path))

    if not doc.column_names or not doc.rows:
        print("error: file has no columns or rows", file=sys.stderr)
        sys.exit(1)

    vocab = match_columns(doc.column_names)

    if not vocab.should_proceed:
        print(
            f"error: no profile matched — LLM path required.\n"
            f"  unrecognized headers: {vocab.unrecognized}\n"
            f"  run ingest_match.py for the full column map",
            file=sys.stderr,
        )
        sys.exit(1)

    meta = doc.metadata or {}
    report_dates = resolve_report_dates(meta, path.name)
    manager_from_meta, scope = resolve_manager_from_metadata(meta)
    effective_manager = manager_override or manager_from_meta

    result = IngestionResult(
        document_id=doc.id,
        report_type=ReportType.UNKNOWN,
        as_of_date=report_dates.effective_date,
    )

    extract_data: dict[str, object] = {
        "report_type": vocab.report_type,
        "primary_entity_type": vocab.primary_entity_type,
        "column_map": vocab.column_map,
        "platform": "appfolio",
        "manager": effective_manager,
        "scope": scope,
        "as_of_date": report_dates.effective_date,
    }

    await run_deterministic_pipeline(
        ps=InMemoryPropertyStore(),
        doc_id=doc.id,
        platform="appfolio",
        result=result,
        all_rows=doc.rows,
        extract_data=extract_data,
    )

    out: dict[str, object] = {
        "report_type": result.report_type.value,
        "as_of_date": result.as_of_date.isoformat() if result.as_of_date else None,
        "manager": effective_manager,
        "scope": scope,
        "rows_total": len(doc.rows),
        "rows_accepted": result.rows_accepted,
        "rows_rejected": result.rows_rejected,
        "rows_skipped": result.rows_skipped,
        "entities_created": result.entities_created,
        "relationships_created": result.relationships_created,
        "review_items": [
            {
                "kind": item.kind.value,
                "severity": item.severity.value,
                "message": item.message,
                "context": item.context,
            }
            for item in result.review_items
        ],
        "vocab_review_notes": vocab.review_notes,
    }

    if verbose:
        out["validation_warnings"] = [
            {
                "row_index": w.row_index,
                "row_type": w.row_type,
                "field": w.field,
                "issue": w.issue,
            }
            for w in result.validation_warnings
        ]

    return out


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Dry-run the ingestion pipeline (no persistence).")
    parser.add_argument("file", type=Path)
    parser.add_argument("--manager", default=None, metavar="NAME", help="Override manager from metadata")
    parser.add_argument("--verbose", "-v", action="store_true", help="Include per-row validation warnings")
    args = parser.parse_args()

    path: Path = args.file
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    out = asyncio.run(_run(path, args.manager, args.verbose))
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
