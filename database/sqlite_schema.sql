PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sec_scan_summary (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    scan_timestamp TEXT,
    total_companies INTEGER,
    companies_with_licenses INTEGER,
    total_license_files INTEGER,
    total_agreements INTEGER,
    scan_errors INTEGER,
    loaded_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sec_agreements (
    agreement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    company TEXT,
    cik TEXT,
    ticker TEXT,
    filing_type TEXT,
    filing_year INTEGER,
    licensor_name TEXT,
    licensee_name TEXT,
    tech_name TEXT,
    tech_category TEXT,
    confidence REAL,
    royalty_rate REAL,
    royalty_unit TEXT,
    upfront_amount REAL,
    upfront_currency TEXT,
    has_upfront INTEGER NOT NULL DEFAULT 0,
    has_royalty INTEGER NOT NULL DEFAULT 0,
    term_years REAL,
    territory TEXT,
    reasoning TEXT
);

CREATE INDEX IF NOT EXISTS idx_sec_agreements_cik ON sec_agreements(cik);
CREATE INDEX IF NOT EXISTS idx_sec_agreements_company ON sec_agreements(company);
CREATE INDEX IF NOT EXISTS idx_sec_agreements_year ON sec_agreements(filing_year);
CREATE INDEX IF NOT EXISTS idx_sec_agreements_category ON sec_agreements(tech_category);
CREATE INDEX IF NOT EXISTS idx_sec_agreements_confidence ON sec_agreements(confidence);

CREATE TABLE IF NOT EXISTS dart_filings (
    filing_id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_identifier TEXT NOT NULL,
    company_name TEXT,
    company_country TEXT,
    source_system TEXT,
    document_id TEXT,
    file_name TEXT NOT NULL UNIQUE,
    filing_date TEXT,
    period_end TEXT,
    document_type TEXT,
    language TEXT,
    parser_version TEXT,
    total_tokens INTEGER,
    total_sections INTEGER,
    sections_with_tables INTEGER,
    risk_keyword_signal INTEGER,
    detected_currencies_json TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dart_filings_company ON dart_filings(company_identifier);
CREATE INDEX IF NOT EXISTS idx_dart_filings_date ON dart_filings(filing_date);

CREATE TABLE IF NOT EXISTS dart_sections (
    row_id INTEGER PRIMARY KEY AUTOINCREMENT,
    filing_id INTEGER NOT NULL REFERENCES dart_filings(filing_id) ON DELETE CASCADE,
    section_key TEXT NOT NULL,
    section_id TEXT,
    common_tag TEXT,
    sec_label TEXT,
    dart_label TEXT,
    dart_eng_label TEXT,
    order_index INTEGER,
    token_count INTEGER,
    has_tables INTEGER NOT NULL DEFAULT 0,
    has_financial_data INTEGER NOT NULL DEFAULT 0,
    money_mentions INTEGER NOT NULL DEFAULT 0,
    percent_mentions INTEGER NOT NULL DEFAULT 0,
    year_mentions INTEGER NOT NULL DEFAULT 0,
    keyword_business INTEGER NOT NULL DEFAULT 0,
    keyword_advantage INTEGER NOT NULL DEFAULT 0,
    keyword_regulation INTEGER NOT NULL DEFAULT 0,
    candidate_score INTEGER NOT NULL DEFAULT 0,
    keyword_hits_json TEXT,
    structured_cost_keys_json TEXT,
    license_costs_json TEXT,
    preview TEXT,
    plain_text TEXT,
    UNIQUE (filing_id, section_key)
);

CREATE INDEX IF NOT EXISTS idx_dart_sections_filing ON dart_sections(filing_id);
CREATE INDEX IF NOT EXISTS idx_dart_sections_score ON dart_sections(candidate_score);
CREATE INDEX IF NOT EXISTS idx_dart_sections_section_id ON dart_sections(section_id);

CREATE TABLE IF NOT EXISTS dart_filing_rollups (
    filing_id INTEGER PRIMARY KEY REFERENCES dart_filings(filing_id) ON DELETE CASCADE,
    candidate_sections INTEGER NOT NULL DEFAULT 0,
    structured_sections INTEGER NOT NULL DEFAULT 0,
    high_signal_sections INTEGER NOT NULL DEFAULT 0,
    avg_score REAL NOT NULL DEFAULT 0,
    top_keywords_json TEXT,
    signal_buckets_json TEXT
);

-- AI Processing Log
CREATE TABLE IF NOT EXISTS ai_processing_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filing_id TEXT,
    model_used TEXT NOT NULL,
    routing_decision TEXT,
    complexity_score INTEGER,
    confidence_score REAL,
    processing_time_sec REAL,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0.0,
    processing_path TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_log_model ON ai_processing_log(model_used);
CREATE INDEX IF NOT EXISTS idx_ai_log_created ON ai_processing_log(created_at);

-- Monthly Cost Tracking
CREATE TABLE IF NOT EXISTS cost_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT NOT NULL,
    model TEXT NOT NULL,
    total_requests INTEGER DEFAULT 0,
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    total_cost_usd REAL DEFAULT 0.0,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(month, model)
);
