"""Ingestion context — inbound data.

Split into three categories:
- ``documents/`` — document parsing, LLM extraction, persistence
- ``embedding/`` — vector indexing of portfolio entities
- ``seeding/`` — initial data load from sample reports

Format adapters live in ``adapters/``.
"""
