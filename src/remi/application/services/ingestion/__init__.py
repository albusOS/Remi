"""Ingestion — report parsing, classification, mapping, and persistence.

``DocumentIngestService`` orchestrates the full inbound path: parse,
classify, map columns, validate, persist entities, and store the document.

``IngestionService`` handles the persistence tier: mapped rows through
per-entity-type persisters.
"""
