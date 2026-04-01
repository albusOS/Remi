# Data Directory

Sample AppFolio report exports for development and testing.

## Expected Structure

```
data/
  sample_reports/
    Alex_Budavich_Reports/
      property_directory-*.xlsx
      rent_roll-*.xlsx
      delinquencies-*.xlsx
      lease_expiration-*.xlsx
```

## Usage

- `uv run remi serve --seed` seeds demo data at startup
- `POST /api/v1/seed/reports` ingests sample reports from this directory
- `scripts/dry_run.py` runs the full ingestion pipeline against these files

## Security

Do NOT commit reports containing real tenant PII. Add `data/sample_reports/**/*.xlsx` and `data/sample_reports/**/*.csv` to `.gitignore` before committing real data.
