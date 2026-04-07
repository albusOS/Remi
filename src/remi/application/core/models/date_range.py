"""DateRange — a closed date interval [start, end]."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, model_validator


class DateRange(BaseModel, frozen=True):
    """A closed date interval [start, end].

    Represents the data period a report covers — distinct from the report's
    export date (Document.effective_date). For example, a "2024 Annual
    Maintenance History" exported on 2025-01-15 has:

        effective_date  = 2025-01-15   (when the report was run)
        coverage        = DateRange(start=2024-01-01, end=2024-12-31)
    """

    start: date
    end: date

    @model_validator(mode="after")
    def _validate_order(self) -> DateRange:
        if self.end < self.start:
            raise ValueError(f"DateRange end {self.end!r} precedes start {self.start!r}")
        return self

    def overlaps(self, other: DateRange) -> bool:
        """True when the two intervals share at least one day."""
        return self.start <= other.end and other.start <= self.end

    def contains(self, d: date) -> bool:
        """True when *d* falls within this interval (inclusive)."""
        return self.start <= d <= self.end

    def duration_days(self) -> int:
        """Calendar days in the interval (inclusive on both ends)."""
        return (self.end - self.start).days + 1

    def __str__(self) -> str:
        return f"{self.start} – {self.end}"
