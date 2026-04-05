"""SeedService — ingest AppFolio report exports in dependency order.

Encapsulates the full seed workflow: parse XLSX reports, auto-assign
properties to managers via embedded tags, run signal + embedding pipelines.
Used by both the CLI (``remi seed``) and the API (``POST /api/v1/seed/reports``).

Accepts any directory of XLSX/CSV exports — report type is detected by
the LLM ingestion pipeline from column headers and row content, not from
filenames.  Property directory reports (the "migration" type that creates
managers and properties) are detected by a lightweight column-header
heuristic and ingested first so that dependent reports can attach to
existing entities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import structlog
from pydantic import BaseModel

from remi.application.core.protocols import DocumentParser, PropertyStore
from remi.application.services.embedding.pipeline import EmbeddingPipeline
from remi.application.services.ingestion.pipeline import DocumentIngestService
from remi.application.services.queries.auto_assign import AutoAssignService

logger = structlog.get_logger(__name__)

_REPORT_EXTENSIONS = frozenset({".xlsx", ".xls", ".csv"})

_PROPERTY_DIR_COLUMNS = frozenset({
    "site manager name",
    "property manager",
    "manager name",
    "assigned manager",
})


class IngestedReport(BaseModel, frozen=True):
    filename: str
    report_type: str
    rows: int
    entities: int
    relationships: int


@dataclass
class SeedResult:
    ok: bool = True
    reports_ingested: list[IngestedReport] = field(default_factory=list)
    managers_created: int = 0
    properties_created: int = 0
    auto_assigned: int = 0
    errors: list[str] = field(default_factory=list)


def _is_property_directory(
    path: Path,
    doc_parser: DocumentParser,
    extra_skip_patterns: tuple[str, ...] = (),
) -> bool:
    """Heuristic: parse just the column headers and check for manager columns."""
    try:
        doc = doc_parser.parse(
            path.name, path.read_bytes(), "",
            extra_skip_patterns=extra_skip_patterns,
        )
        lower_cols = {c.lower().strip() for c in doc.column_names}
        return bool(lower_cols & _PROPERTY_DIR_COLUMNS)
    except Exception:
        return False


def discover_reports(
    report_dir: Path,
    doc_parser: DocumentParser,
    extra_skip_patterns: tuple[str, ...] = (),
) -> list[Path]:
    """Find report files and order them: property directories first.

    Uses a lightweight column-header heuristic to detect property directory
    reports so they are ingested before dependent report types.
    """
    all_files = sorted(
        p for p in report_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _REPORT_EXTENSIONS
    )
    if not all_files:
        return []

    prop_dirs: list[Path] = []
    others: list[Path] = []
    for p in all_files:
        if _is_property_directory(p, doc_parser, extra_skip_patterns):
            prop_dirs.append(p)
        else:
            others.append(p)

    return prop_dirs + others


class SeedService:
    """Orchestrates seeding from a directory of AppFolio exports."""

    def __init__(
        self,
        document_ingest: DocumentIngestService,
        auto_assign: AutoAssignService,
        embedding_pipeline: EmbeddingPipeline,
        property_store: PropertyStore,
        document_parser: DocumentParser,
        metadata_skip_patterns: tuple[str, ...] = (),
    ) -> None:
        self._ingest = document_ingest
        self._auto_assign = auto_assign
        self._embedding_pipeline = embedding_pipeline
        self._ps = property_store
        self._doc_parser = document_parser
        self._skip_patterns = metadata_skip_patterns

    async def seed_from_reports(
        self,
        report_dir: Path | None = None,
        *,
        force: bool = False,
    ) -> SeedResult:
        """Ingest reports in dependency order, auto-assign, run pipelines.

        Accepts any directory of XLSX/CSV exports.  Report type is detected
        by the LLM pipeline — filenames don't matter.  Property directory
        reports are discovered via column-header heuristic and ingested first.
        """
        if report_dir is None:
            raise ValueError(
                "report_dir is required — pass the directory containing your "
                "AppFolio XLSX/CSV exports."
            )
        result = SeedResult()

        if not report_dir.exists():
            result.ok = False
            result.errors.append(f"Report directory not found: {report_dir}")
            return result

        ordered = discover_reports(report_dir, self._doc_parser, self._skip_patterns)
        if not ordered:
            result.ok = False
            result.errors.append(
                f"No report files ({', '.join(_REPORT_EXTENSIONS)}) "
                f"found in {report_dir}"
            )
            return result

        logger.info(
            "seed_reports_discovered",
            count=len(ordered),
            files=[p.name for p in ordered],
        )

        for path in ordered:
            try:
                content = path.read_bytes()
                ingest_result = await self._ingest.ingest_upload(
                    path.name,
                    content,
                    "",
                    manager=None,
                    run_pipelines=False,
                )
                result.reports_ingested.append(
                    IngestedReport(
                        filename=path.name,
                        report_type=ingest_result.report_type,
                        rows=ingest_result.doc.row_count,
                        entities=ingest_result.entities_extracted,
                        relationships=ingest_result.relationships_extracted,
                    )
                )
                logger.info(
                    "seed_report_ingested",
                    filename=path.name,
                    report_type=ingest_result.report_type,
                    rows=ingest_result.doc.row_count,
                    entities=ingest_result.entities_extracted,
                )
            except Exception as exc:
                msg = f"{path.name}: {exc}"
                result.errors.append(msg)
                logger.exception("seed_report_failed", filename=path.name)

        try:
            assign_result = await self._auto_assign.auto_assign()
            result.auto_assigned = assign_result.assigned
            logger.info("seed_auto_assign_complete", assigned=assign_result.assigned)
        except Exception as exc:
            result.errors.append(f"auto_assign: {exc}")
            logger.exception("seed_auto_assign_failed")

        # TODO: replace with delta — currently re-embeds all entities
        try:
            embed_result = await self._embedding_pipeline.run_full()
            logger.info("seed_embeddings_complete", embedded=embed_result.embedded)
        except Exception as exc:
            result.errors.append(f"embedding_pipeline: {exc}")
            logger.exception("seed_embeddings_failed")

        managers = await self._ps.list_managers()
        properties = await self._ps.list_properties()
        result.managers_created = len(managers)
        result.properties_created = len(properties)

        result.ok = len(result.errors) == 0
        return result
