# SEC License Extraction

A data pipeline project that structures license agreement information from disclosure documents (SEC 10-K and DART), then connects it with litigation royalty data and valuation workflows.

## Product Overview
- Goal: transform unstructured disclosure documents into analyzable structured data
- Inputs: SEC/DART filing documents, CourtListener litigation data
- Outputs: `license_summary.json`, unified schema JSON, CSV reports, SQLite analytics DB, dashboards
- Use cases: compare license terms, analyze technology-category patterns, build evidence for valuation assumptions
- Non-goals: legal advice automation, fully automated investment decisions

## Current Code Scan Summary (2026-02-28)
- SEC pipeline: clearly split flow in code as `crawler -> parser -> extractor -> scan_licenses`
- DART pipeline: `orchestrator/run_dart_pipeline.py` supports single-target and listed-company chunk runs
- Unified parser: `parser/unified_disclosure_parser.py` outputs a common SEC/DART schema
- Analytics layer: local analytics loop via `database/build_sqlite_db.py` and `utils/analyze_sqlite.py`
- UI: both Streamlit dashboard and Next.js dashboard are available
- Tests: unit tests exist for DART crawler/parser and unified parser

## Quick Start
### 1. Install
```powershell
cd F:\SEC\License\sec-license-extraction
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Prepare config files
```powershell
Copy-Item .\config_demo.yaml .\config.yaml -Force
Copy-Item .\.env.example .\.env -Force
```

### 3. Required environment variables
- `GEMINI_API_KEY` or `OLLAMA_BASE_URL` for local LLM
- `DART_API_KEY` (for DART pipeline)
- `COURTLISTENER_API_KEY` (for litigation collection)
- `DB_PASSWORD` (for PostgreSQL loader)

## How To Use
### A. SEC license extraction
1. Collect SEC filings
```powershell
python -c "from crawler.sec_crawler import SECEdgarCrawler; SECEdgarCrawler('config.yaml').batch_process()"
```
2. Parse notes and extract candidates
```powershell
python -c "from parser.html_parser import batch_process; batch_process('config.yaml')"
```
3. Run LLM-based structured extraction
```powershell
python -c "from extractor.license_extractor import batch_process; batch_process('config.yaml')"
```
4. Build consolidated scan summary
```powershell
python scan_licenses.py
```

### B. DART unified schema generation
1. Single stock run
```powershell
python -m orchestrator.run_dart_pipeline `
  --config config.yaml `
  --stock-code 005930 `
  --start-date 20240101 `
  --end-date 20260220 `
  --max-filings 2
```
2. Listed-company chunk run
```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_dart_listed_chunks.ps1 `
  -StartOffset 0 `
  -EndOffset 2000 `
  -ChunkSize 200 `
  -MaxFilingsPerTarget 1
```

### C. Litigation data collection
```powershell
python orchestrator\run_pipeline.py --config config.yaml
```
- Note: currently `run_pipeline.py` has SEC stages commented out, so it effectively runs litigation collection.

### D. Valuation report generation
```powershell
python orchestrator\run_valuation.py --config config.yaml
```

### E. Build SQLite analytics DB and report
1. Build DB
```powershell
python database\build_sqlite_db.py
```
2. Generate analysis report
```powershell
python utils\analyze_sqlite.py `
  --db-path data/processed/sec_dart_analytics.db `
  --out data/exports/analysis/sqlite_analysis_latest.md
```

### F. Run dashboards
1. Streamlit
```powershell
streamlit run dashboard\app.py
```
2. Next.js
```powershell
cd next-finance-dashboard
npm install
npm run sync:data
npm run dev -- --port 3007
```

## Core Directories
```text
sec-license-extraction/
  crawler/                  # SEC and DART crawlers
  parser/                   # SEC note parser and SEC/DART unified parser
  extractor/                # LLM-based license agreement extraction
  litigation/               # CourtListener collection and judgment parsing
  valuation/                # DCF + comparable-based valuation
  orchestrator/             # entry points
  database/                 # PostgreSQL/SQLite schemas and loaders
  dashboard/                # Streamlit dashboard
  next-finance-dashboard/   # Next.js dashboard
  utils/                    # operational utility scripts
  tests/                    # parser/crawler tests
  data/                     # raw/intermediate/output data
```

## Key Outputs
- `data/raw_filings/`: SEC raw filings
- `data/parsed_footnotes/`: parsed SEC notes
- `data/extracted_licenses/`: structured license extraction outputs
- `license_summary.json`: consolidated SEC scan summary
- `data/dart/raw_filings/`: DART raw files and metadata
- `data/dart/unified_schema/`: DART unified schema JSON outputs
- `data/litigation/parsed/`: parsed royalty judgment outputs
- `data/exports/*.csv`: CSV reports
- `data/processed/sec_dart_analytics.db`: local analytics database

## How This Product Can Be Used
- Research: quickly compare license agreement patterns across industries and companies
- Strategy: build negotiation benchmarks by combining historical terms with litigation royalty data
- Data engineering: normalize SEC/DART unstructured documents into a reusable common schema
- Analytics automation: generate repeatable internal reports using SQLite-based pipelines

## Future Development Directions
### 1) Reliability and operations
- Standardize request `timeout` and retry policy in `litigation/court_crawler.py`
- Add stage-level checkpoints and reprocessing queue design
- Strengthen throughput/failure/cost observability for large batch runs

### 2) Data quality
- Improve normalization rules for tech categories, party names, currencies, and units
- Add re-extraction loop using `confidence_score` thresholds
- Improve DART section scoring model with benchmark datasets

### 3) Productization
- Unify metrics and filtering model between Streamlit and Next dashboards
- Separate company/technology/time-based API layer
- Integrate batch scheduler and notifications (Slack/Email)

## Operational Notes
- The `data/` directory can become very large; separate storage paths or external drives are recommended.
- If some Korean values in `config.yaml` appear broken, re-enter and save them as UTF-8.
- For status snapshot refresh, refer to `python utils/update_readme_status.py`; stabilizing encoding in that script first is recommended.
