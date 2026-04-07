# Ingestion Test Fixtures

Five edge-case AppFolio-style CSV reports for testing the ingestion pipeline.
Each is designed to exercise a different code path or failure mode.

| File | Pipeline Path | What It Tests |
|------|--------------|---------------|
| `01_maintenance_per_unit.csv` | Rule/LLM column-map | Known entity, per-unit scope, date range in header, non-standard column names |
| `02_recurring_service_contracts.csv` | LLM capture | Completely novel entity type — triggers `observations_likely`, capture step, `extend` proposal |
| `03_unit_inspection_report.csv` | LLM capture | Novel type with explicit unit/property references — tests relationship inference |
| `04_owner_distribution_statement.csv` | LLM capture | Mixed financial line items per property — no row-per-entity structure |
| `05_delinquency_eviction_tracker.csv` | Rule/LLM column-map + capture | Known base type (BalanceObservation) + meaningful unknown columns for legal proceedings |
