# DATA_STRUCTURE

## 1) Data Inventory (Local `./data`)

Scan date: `2026-02-21`  
Total: `94,554 files`, `104.052 GB`

| Path (relative) | Files | Size | Note |
|---|---:|---:|---|
| `data/raw_filings/` | 94,488 | 100.899 GB | SEC/DART raw filing archive (largest) |
| `data/parsed_contracts/` | 35 | 3.107 GB | Parsed contract batch JSON |
| `data/dart/` | 18 | 0.043 GB | DART raw + unified schema |
| `data/exports/` | 12 | 0.002 GB | CSV/JSON export results |
| `data/company_tickers.json` | 1 | 0.001 GB | SEC ticker reference |

Large files over 100MB:
- `data/parsed_contracts/parsed_contracts_31999.json` (111.67 MB)
- `data/parsed_contracts/parsed_contracts_30999.json` (106.84 MB)
- `data/parsed_contracts/parsed_contracts_25999.json` (105.56 MB)
- `data/parsed_contracts/parsed_contracts_27999.json` (104.27 MB)
- `data/parsed_contracts/parsed_contracts_17999.json` (102.11 MB)
- `data/parsed_contracts/parsed_contracts_28999.json` (101.43 MB)
- `data/parsed_contracts/parsed_contracts_9999.json` (101.22 MB)
- `data/parsed_contracts/parsed_contracts_23999.json` (101.20 MB)
- `data/parsed_contracts/parsed_contracts_29999.json` (100.91 MB)
- `data/parsed_contracts/parsed_contracts_16999.json` (100.81 MB)
- `data/parsed_contracts/parsed_contracts_7999.json` (100.08 MB)

## 2) 3-Tier Data Classification

### A. Git-included data (<10MB)
- Purpose: schema samples, small reference files, reproducible examples
- Recommended:
  - `data/exports/` lightweight samples (curated)
  - `data/dart/unified_schema/` selected sample JSON only
  - `data/company_tickers.json` (if versioned intentionally)
- Rule: keep only minimal sample set required for onboarding/tests

### B. Local-only data (10MB-1GB)
- Purpose: active development artifacts
- Recommended:
  - `license_summary.json` (~27.81MB)
  - day-to-day CSV exports under `data/exports/`
  - temporary run outputs
- Rule: keep on local SSD, do not commit large/generated snapshots by default

### C. External-drive required data (>1GB, directory-level)
- Purpose: full-scale historical archive / heavy processing input
- Current candidates:
  - `data/raw_filings/` (~100.899GB)
  - `data/parsed_contracts/` (~3.107GB)
- Rule: mount external storage before batch pipeline execution

## 3) Path Standardization (Relative First)

Primary relative paths:
- `./data`
- `./data/raw_filings`
- `./data/parsed_contracts`
- `./data/exports`

Absolute path examples (example only, adjust per machine):
- `G:/SEC/sec-license-extraction-data/raw_filings` (estimated example)
- `G:/SEC/sec-license-extraction-data/parsed_contracts` (estimated example)

Environment variable proposal:
- `DATA_DIR=./data`
- `EXTERNAL_DATA_ROOT=G:/SEC/sec-license-extraction-data` (example)
- `RAW_FILINGS_DIR=${EXTERNAL_DATA_ROOT}/raw_filings`
- `PARSED_CONTRACTS_DIR=${EXTERNAL_DATA_ROOT}/parsed_contracts`
- `DART_RAW_DIR=${DATA_DIR}/dart/raw_filings`
- `DART_SCHEMA_DIR=${DATA_DIR}/dart/unified_schema`

## 4) Hardcoded Absolute Path Findings

Found local absolute path usage:
- `dashboard/app.py:25`
- `dashboard/app.py:51`
- `utils/batch_extractor.py:140`
- `utils/batch_parser.py:112`
- `tests/test_contract_parser_verification.py:10`

Refactor direction:
- Replace hardcoded `C:/...` with `Path(os.getenv(...))` fallback chain:
  - env var -> relative project path -> warning message

## 5) Migration Checklist (for another PC)

- [ ] Clone/open project at target location.
- [ ] Create and fill `.env` from `.env.example`.
- [ ] Set external drive root (`EXTERNAL_DATA_ROOT`) to actual mounted path.
- [ ] Ensure `RAW_FILINGS_DIR` and `PARSED_CONTRACTS_DIR` exist and are readable.
- [ ] Validate `config.yaml` path keys use relative/env-resolved values.
- [ ] Run a smoke test:
  - `python scan_licenses.py`
  - `python orchestrator/run_pipeline.py --config config.yaml`

## 6) External Drive Disconnected Behavior (Design)

- On startup, validate required paths and fail fast with clear errors:
  - Missing directory
  - Permission denied
  - Empty expected dataset
- Recommended error format:
  - `DATA_PATH_MISSING: RAW_FILINGS_DIR not found at <resolved_path>`
  - `ACTION: connect external drive and retry`
