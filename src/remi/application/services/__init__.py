"""Services — application-level orchestration over domain + agent ports.

    ingestion/      Document ingestion pipeline (parse → extract → resolve → persist)
    auto_assign.py  KB-tag-based property-to-manager assignment
    search.py       RE-aware hybrid search

Computed views live in ``application/views/``, not here.
"""
