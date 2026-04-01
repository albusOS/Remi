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

1. **Property Directory** — creates PMs and properties (the spine)
2. **Delinquency** — attaches tenants and balances
3. **Lease Expiration** — attaches leases with real dates
4. **Rent Roll** — fills in unit vacancy and listing status

## Security

Do NOT commit reports containing real tenant PII. The `.gitignore` excludes
`data/sample_reports/**/*.xlsx` and `data/sample_reports/**/*.csv`.
