"""Structural report type detection for AppFolio exports.

Scores column fingerprints against known definitions.  The best-matching
type above its minimum score threshold wins.  Returns UNKNOWN with confidence
0.0 when nothing qualifies.
"""

from __future__ import annotations

from remi.ingestion.adapters.appfolio.schema import (
    REPORT_TYPE_DEFINITIONS,
    AppFolioReportType,
)


def detect_report_type_scored(column_names: list[str]) -> tuple[str, float]:
    """Scored structural detection. Returns (report_type_str, confidence 0-1).

    confidence = fraction of signature_columns that matched (1.0 when no
    signature columns are defined). UNKNOWN is returned with confidence 0.0
    when nothing qualifies.
    """
    col_set = set(column_names)
    best_type: str = AppFolioReportType.UNKNOWN
    best_score: float = 0.0

    for defn in REPORT_TYPE_DEFINITIONS:
        if not defn.required_columns.issubset(col_set):
            continue

        if defn.signature_columns:
            score = len(defn.signature_columns & col_set) / len(defn.signature_columns)
        else:
            score = 1.0

        if score >= defn.min_score and score > best_score:
            best_type = defn.report_type
            best_score = score

    return best_type, best_score


def detect_report_type(column_names: list[str]) -> AppFolioReportType:
    """Identify report type from column names.

    Returns the best-matching known type, or UNKNOWN when no definition meets
    its required columns + minimum signature score.
    """
    report_type, _ = detect_report_type_scored(column_names)
    try:
        return AppFolioReportType(report_type)
    except ValueError:
        return AppFolioReportType.UNKNOWN
