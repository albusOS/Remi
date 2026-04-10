---
name: ingestion-debugging
description: Debug and develop the REMI ingestion pipeline for AppFolio property management reports. Use when inspecting Excel files, testing vocabulary matching, adding new report types to vocab.py, investigating why a report falls through to the LLM path, or diagnosing ingestion failures.
---

# Ingestion Debugging

## Architecture in one sentence

Tabular files hit `vocab.py` (deterministic header matching) → if matched, `operations.py` extracts entities inline; if not, returns `status="processing"` and the ingester agent takes over via LLM.

## Key files

| File | Role |
|------|------|
| `src/remi/application/ingestion/vocab.py` | Column vocabulary (`VOCAB` dict) + report `PROFILES` + `match_columns()` |
| `src/remi/application/ingestion/rules.py` | Junk filtering, address normalization, manager tag validation, type coercion |
| `src/remi/application/ingestion/operations.py` | Full extraction pipeline — calls `run_deterministic_pipeline()` |
| `src/remi/application/ingestion/upload.py` | Entry point — `DocumentIngestService.ingest_upload()` |
| `src/remi/application/ingestion/cli.py` | CLI commands: `upload`, `documents`, `document-search` |

## Sample files

```
data/sample_reports/Alex_Budavich_Reports/
  property_directory-20260330.xlsx   ← always ingest first (establishes managers/properties)
  Rent Roll_Vacancy (1).xlsx
  Lease Expiration Detail By Month.xlsx
  Delinquency.xlsx
```

## Utility scripts

### 1. Inspect an Excel file's structure

```bash
uv run python .cursor/skills/ingestion-debugging/scripts/inspect_xlsx.py <file>
```

Outputs: sheet names, header row (with row index), all column headers, sample data rows, row count.
Use this first — tells you the raw shape of any file before anything else.

### 2. Test vocabulary matching

```bash
uv run python .cursor/skills/ingestion-debugging/scripts/test_vocab.py <file>
```

Outputs: `column_map`, detected `report_type`, `unrecognized` headers, `review_notes`, `should_proceed`.
If `should_proceed=False` → the file falls through to LLM. Check `unrecognized` to know what to add to `VOCAB`.

### 3. Run the full ingestion CLI

```bash
uv run remi ingestion upload "data/sample_reports/Alex_Budavich_Reports/property_directory-20260330.xlsx"
uv run remi ingestion upload "data/sample_reports/Alex_Budavich_Reports/Rent Roll_Vacancy (1).xlsx"
uv run remi ingestion documents
```

Always upload `property_directory` first — it seeds the manager/property source of truth.

## Report types and detection fingerprints

Detection in `vocab.py` is set-membership: a `Profile` matches when ALL its `required` fields are present.

| Report type | Required canonical fields | Primary entity |
|-------------|--------------------------|----------------|
| `property_directory` | `site_manager_name`, `_unit_count` | PropertyManager |
| `delinquency` | `balance_total`, `balance_0_30` | BalanceObservation |
| `lease_expiration` | `lease_expires`, `tenant_name` | Lease |
| `rent_roll` | `_bd_ba`, `days_vacant` OR `_bd_ba` + `lease_expires` + `property_address` | Unit |
| `maintenance` | `scheduled_date`, `completed_date` | MaintenanceRequest |
| `tenant_directory` | `tenant_name`, `email`, `phone` | Tenant |
| `owner_directory` | `email`, `company` | Owner |
| `vendor_directory` | `vendor`, `category` | Vendor |

## Adding a new column variant

Edit `src/remi/application/ingestion/vocab.py` → `VOCAB` dict:

```python
"your new header variant":  "existing_canonical_field",
```

Run `test_vocab.py` to confirm the file now resolves. No other files need changing for new column names.

## Adding a new report type

1. Add new canonical fields to `VOCAB` if needed
2. Add a `Profile` to `PROFILES` in `vocab.py`:
   ```python
   Profile(
       report_type="your_report_type",
       entity_type="YourEntityType",
       required=frozenset({"field_a", "field_b"}),
       ambiguous_as={"_name_ambiguous": "tenant_name"},
   )
   ```
3. Add extraction logic in `operations.py`
4. Run `test_vocab.py` to confirm detection

## Known gaps in current VOCAB

`Rent Roll_Vacancy (1).xlsx` has 3 unrecognized headers that are stored as private fields (ignored by extraction):
- `Posted To Website` → `_posted_to_website`
- `Posted To Internet` → `_posted_to_internet`
- `Revenue` → `_revenue`

Add to `VOCAB` if you want these extracted.

## Common problems

**File falls through to LLM (`should_proceed=False`)**
→ Run `test_vocab.py`. Check `unrecognized` — those headers need entries in `VOCAB`.

**Wrong report type detected**
→ The `required` fields of a less-specific profile are a subset of a more-specific one. The most-specific profile (most required fields) wins. Add a distinguishing required field to the correct profile.

**Junk rows included**
→ Check `is_junk_property()` in `rules.py`. Patterns: `_JUNK_PREFIXES`, `_JUNK_EXACT`, `_JUNK_CONTAINS`.

**Manager created from a lease tag**
→ Check `is_manager_tag()` in `rules.py`. The `Tags` column → `_manager_tag` → filtered by manager heuristics.

**Address normalization wrong**
→ Check `normalize_address()` in `rules.py`. AppFolio format: `"Label - Full Address"` → strips label. "DO NOT USE" prefix → strips prefix, marks inactive.
