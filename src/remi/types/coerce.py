"""Type coercion — safe conversion of arbitrary user-supplied strings.

These functions handle the messy reality of spreadsheet data: currency
symbols, parenthetical negatives, mixed date formats, empty strings.
All functions are pure (no I/O) and return a safe default rather than
raising on bad input.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

__all__ = [
    "to_date",
    "to_decimal",
    "to_decimal_or_none",
    "to_int",
]

_DATE_FORMATS = (
    "%m/%d/%Y",
    "%Y-%m-%d",
    "%m-%d-%Y",
    "%m/%d/%y",
    "%Y/%m/%d",
    "%d-%b-%Y",
    "%b %d, %Y",
)


def to_date(val: object) -> date | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    text = str(val).strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


_CURRENCY_STRIP_RE = re.compile(r"[$,\s]")
_PARENS_RE = re.compile(r"^\((.+)\)$")


def to_decimal(val: object) -> Decimal:
    if val is None:
        return Decimal("0")
    if isinstance(val, bool):
        return Decimal("0")
    if isinstance(val, Decimal):
        return val
    if isinstance(val, (int, float)):
        return Decimal(str(val))
    text = _CURRENCY_STRIP_RE.sub("", str(val).strip())
    if not text:
        return Decimal("0")
    m = _PARENS_RE.match(text)
    if m:
        text = f"-{m.group(1)}"
    try:
        return Decimal(text)
    except InvalidOperation:
        return Decimal("0")


def to_decimal_or_none(val: object) -> Decimal | None:
    """Like ``to_decimal`` but returns ``None`` for absent/empty values.

    Lets callers distinguish "not provided" from "$0".
    """
    if val is None:
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, Decimal):
        return val
    if isinstance(val, (int, float)):
        return Decimal(str(val))
    text = _CURRENCY_STRIP_RE.sub("", str(val).strip())
    if not text:
        return None
    m = _PARENS_RE.match(text)
    if m:
        text = f"-{m.group(1)}"
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def to_int(val: object) -> int | None:
    if val is None:
        return None
    if isinstance(val, int):
        return val
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return None
