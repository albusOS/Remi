"""RE inbound data pipeline — ontology-driven ingestion.

LLM extraction pipeline (classify → extract → enrich) produces typed rows.
The resolver maps rows directly to domain models and persists to
PropertyStore + KnowledgeStore in one pass. No intermediate event layer.
"""
