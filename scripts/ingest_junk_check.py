"""Dev tool: test whether an address string would be filtered by ingestion rules.

Usage:
    uv run scripts/ingest_junk_check.py "1234 Morning Meeting"
    uv run scripts/ingest_junk_check.py "DO NOT USE - 42 Oak Street"

Runs the same is_junk_property / is_inactive_property / normalize_address
logic the pipeline applies to every row. Useful when adding new junk patterns
or debugging why a property is being dropped or incorrectly kept.
"""

from __future__ import annotations

import json
import sys


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Test an address against ingestion junk/inactive rules.")
    parser.add_argument("address", help="Address string to test")
    args = parser.parse_args()

    from remi.application.ingestion.rules import is_inactive_property, is_junk_property, normalize_address

    address: str = args.address
    is_junk = is_junk_property(address)
    is_inactive = is_inactive_property(address)
    normalized = normalize_address(address)

    verdict = (
        "DROPPED (junk)"
        if is_junk
        else "INACTIVE — stripped prefix, property created"
        if is_inactive
        else "ACCEPTED"
    )

    print(
        json.dumps(
            {
                "input": address,
                "is_junk": is_junk,
                "is_inactive": is_inactive,
                "normalized": normalized,
                "verdict": verdict,
            },
            indent=2,
        )
    )

    if is_junk:
        sys.exit(2)


if __name__ == "__main__":
    main()
