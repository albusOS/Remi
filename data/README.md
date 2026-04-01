# Data Directory

AppFolio report exports for development and production seeding.

## Expected Structure

```
data/
  sample_reports/
    Alex_Budavich_Reports/
      property_directory-*.xlsx
      Delinquency.xlsx
      Lease Expiration Detail By Month.xlsx
      Rent Roll_Vacancy (1).xlsx
```

## Usage

- `uv run remi serve --seed` ingests reports at startup
- `uv run remi seed` ingests reports via CLI
- `POST /api/v1/seed/reports` ingests reports via API

## Ingestion Order

Reports are ingested in dependency order:

1. **Property Directory** (migration) — creates managers and properties. Uses frequency-based
   classification to distinguish real manager names from operational tags in the "Site Manager Name"
   column. Only report type that creates `PropertyManager` / `Portfolio` records.
2. **Delinquency** (recurring) — attaches tenants and balances. Never creates managers.
3. **Lease Expiration** (recurring) — attaches leases with real dates. Never creates managers.
4. **Rent Roll** (recurring) — fills in unit vacancy and listing status. Never creates managers.

## Security

Do NOT commit reports containing real tenant PII. The `.gitignore` excludes
`data/sample_reports/**/*.xlsx` and `data/sample_reports/**/*.csv`.
