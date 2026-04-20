-- Database Schema for SEC License Extraction System

-- Companies
CREATE TABLE IF NOT EXISTS companies (
    company_id SERIAL PRIMARY KEY,
    name VARCHAR(500) NOT NULL UNIQUE,
    cik VARCHAR(10),
    company_type VARCHAR(50), 
    industry_sector VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_company_cik UNIQUE (cik) 
);

-- SEC Filings
CREATE TABLE IF NOT EXISTS sec_filings (
    filing_id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(company_id),
    cik VARCHAR(10) NOT NULL,
    accession_number VARCHAR(50) NOT NULL UNIQUE,
    filing_type VARCHAR(10),
    filing_date DATE,
    form VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- License Agreements
CREATE TABLE IF NOT EXISTS license_agreements (
    agreement_id SERIAL PRIMARY KEY,
    filing_id INTEGER REFERENCES sec_filings(filing_id),
    licensor_id INTEGER REFERENCES companies(company_id), -- simplified, may need to resolve dynamically
    licensor_name VARCHAR(500), -- store name directly if ID not available
    licensee_name VARCHAR(500),
    
    internal_agreement_name VARCHAR(500),
    execution_date DATE,
    effective_date DATE,
    expiration_date DATE,
    
    territory JSONB,
    exclusivity VARCHAR(100),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Technologies
CREATE TABLE IF NOT EXISTS technologies (
    technology_id SERIAL PRIMARY KEY,
    agreement_id INTEGER REFERENCES license_agreements(agreement_id),
    name VARCHAR(500),
    category VARCHAR(200),
    description TEXT,
    capacity_value NUMERIC,
    capacity_unit VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Financial Terms
CREATE TABLE IF NOT EXISTS financial_terms (
    term_id SERIAL PRIMARY KEY,
    agreement_id INTEGER REFERENCES license_agreements(agreement_id),
    
    upfront_amount NUMERIC,
    upfront_currency VARCHAR(10),
    
    royalty_rate NUMERIC,
    royalty_unit VARCHAR(50), -- e.g. % or $/unit
    royalty_basis VARCHAR(100),
    
    milestones JSONB,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Valuation Comparables
CREATE TABLE IF NOT EXISTS valuation_comparables (
    comparable_id SERIAL PRIMARY KEY,
    source_agreement_id INTEGER REFERENCES license_agreements(agreement_id),
    comparable_agreement_id INTEGER REFERENCES license_agreements(agreement_id),
    similarity_score NUMERIC(3, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AI Processing Log (routing decisions, costs, performance)
CREATE TABLE IF NOT EXISTS ai_processing_log (
    id SERIAL PRIMARY KEY,
    filing_id INTEGER REFERENCES sec_filings(filing_id),
    model_used VARCHAR(50) NOT NULL,
    routing_decision VARCHAR(50),
    complexity_score INTEGER,
    confidence_score NUMERIC(4, 3),
    processing_time_sec NUMERIC(8, 3),
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_usd NUMERIC(10, 6) DEFAULT 0,
    processing_path VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Monthly Cost Tracking
CREATE TABLE IF NOT EXISTS cost_tracking (
    id SERIAL PRIMARY KEY,
    month VARCHAR(7) NOT NULL,
    model VARCHAR(50) NOT NULL,
    total_requests INTEGER DEFAULT 0,
    total_input_tokens INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    total_cost_usd NUMERIC(10, 4) DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(month, model)
);

-- RAG Document Registry
CREATE TABLE IF NOT EXISTS rag_documents (
    id SERIAL PRIMARY KEY,
    collection_name VARCHAR(100) NOT NULL,
    doc_id VARCHAR(200) NOT NULL UNIQUE,
    source_type VARCHAR(50),
    source_id VARCHAR(200),
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    embedding_model VARCHAR(100) DEFAULT 'all-MiniLM-L6-v2'
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_companies_cik ON companies(cik);
CREATE INDEX IF NOT EXISTS idx_filings_accession ON sec_filings(accession_number);
CREATE INDEX IF NOT EXISTS idx_agreements_filing ON license_agreements(filing_id);
CREATE INDEX IF NOT EXISTS idx_ai_log_model ON ai_processing_log(model_used);
CREATE INDEX IF NOT EXISTS idx_ai_log_filing ON ai_processing_log(filing_id);
CREATE INDEX IF NOT EXISTS idx_cost_month ON cost_tracking(month);
