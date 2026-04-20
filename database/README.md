# Database Notes

## Quick Local DB (SQLite)

Build a local analytics DB from existing SEC and DART outputs:

```powershell
python database\build_sqlite_db.py
```

Output:

- `data/processed/sec_dart_analytics.db`

Source inputs:

- SEC: `license_summary.json`
- DART: `data/dart/unified_schema/**/*.json` (excluding `run_summary_*.json`)

Main tables:

- `sec_scan_summary`
- `sec_agreements`
- `dart_filings`
- `dart_sections`
- `dart_filing_rollups`

## Existing PostgreSQL Loader

Legacy scripts are still available:

- Schema: `database/schema.sql`
- Loader: `database/load_data.py`

Note:

- `schema.sql` now includes `companies.name` unique constraint to match loader conflict handling.
