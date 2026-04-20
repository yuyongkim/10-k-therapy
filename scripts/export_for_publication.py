"""
Export PostgreSQL data to CSV for Zenodo/Figshare publication.

Outputs (data/exports/publication/):
  1. license_contracts.csv          — 38,114 rows (all extractions with quality flags)
  2. license_contracts_clean.csv    — 19,054 rows (quality_flag='clean' only)
  3. financial_terms.csv            — 17,497 rows (royalty/upfront linked to contracts)
  4. companies.csv                  — 2,523 rows
  5. filings.csv                    — 5,598 rows
  6. dataset_summary.json           - aggregate stats for Data Descriptor

Run: python scripts/export_for_publication.py
"""

import os
import sys
import json
import csv
from datetime import datetime

import psycopg2
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
load_dotenv()

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "exports", "publication")
os.makedirs(OUT_DIR, exist_ok=True)


def get_conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "license_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "1234"),
    )


def export_table(cur, query, filename, description):
    cur.execute(query)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()

    path = os.path.join(OUT_DIR, filename)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        writer.writerows(rows)

    size_mb = os.path.getsize(path) / (1024 * 1024)
    print(f"  {filename}: {len(rows):,} rows ({size_mb:.1f} MB) - {description}")
    return len(rows)


def main():
    conn = get_conn()
    cur = conn.cursor()
    stats = {}
    print(f"Exporting to: {OUT_DIR}\n")

    # 1. All license contracts (with quality flags, joined with company/filing info)
    stats["license_contracts_total"] = export_table(cur, """
        SELECT
            lc.id AS contract_id,
            lc.source_system,
            c.name_en AS company_name,
            c.cik,
            c.ticker,
            c.corp_code,
            c.stock_code,
            c.country AS company_country,
            c.industry_sector,
            f.filing_type,
            f.fiscal_year,
            f.filing_date,
            lc.licensor_name,
            lc.licensee_name,
            lc.tech_name,
            lc.tech_category,
            lc.industry,
            lc.exclusivity,
            lc.territory,
            lc.term_years,
            lc.extraction_model,
            lc.confidence_score,
            lc.complexity_score,
            lc.quality_flag,
            lc.noise_reason,
            lc.reasoning
        FROM license_contracts lc
        LEFT JOIN filings f ON lc.filing_id = f.id
        LEFT JOIN companies c ON f.company_id = c.id
        ORDER BY lc.id
    """, "license_contracts.csv", "All extractions with quality flags")

    # 2. Clean only
    stats["license_contracts_clean"] = export_table(cur, """
        SELECT
            lc.id AS contract_id,
            lc.source_system,
            c.name_en AS company_name,
            c.cik,
            c.ticker,
            c.corp_code,
            c.stock_code,
            c.country AS company_country,
            c.industry_sector,
            f.filing_type,
            f.fiscal_year,
            f.filing_date,
            lc.licensor_name,
            lc.licensee_name,
            lc.tech_name,
            lc.tech_category,
            lc.industry,
            lc.exclusivity,
            lc.territory,
            lc.term_years,
            lc.extraction_model,
            lc.confidence_score,
            lc.complexity_score,
            lc.reasoning
        FROM license_contracts lc
        LEFT JOIN filings f ON lc.filing_id = f.id
        LEFT JOIN companies c ON f.company_id = c.id
        WHERE lc.quality_flag = 'clean'
        ORDER BY lc.id
    """, "license_contracts_clean.csv", "Quality-filtered clean contracts only")

    # 3. Financial terms (joined with contract source info)
    stats["financial_terms"] = export_table(cur, """
        SELECT
            ft.id AS term_id,
            ft.contract_id,
            lc.source_system,
            ft.term_type,
            ft.amount,
            ft.currency,
            ft.rate,
            ft.rate_unit,
            ft.rate_basis,
            ft.description,
            lc.tech_name,
            lc.tech_category,
            lc.quality_flag
        FROM financial_terms ft
        JOIN license_contracts lc ON ft.contract_id = lc.id
        ORDER BY ft.id
    """, "financial_terms.csv", "Royalty rates & upfront payments")

    # 4. Companies
    stats["companies"] = export_table(cur, """
        SELECT
            id AS company_id,
            country,
            name_en,
            name_local,
            cik,
            ticker,
            corp_code,
            stock_code,
            industry_sector
        FROM companies
        ORDER BY id
    """, "companies.csv", "Company master list")

    # 5. Filings
    stats["filings"] = export_table(cur, """
        SELECT
            f.id AS filing_id,
            c.name_en AS company_name,
            f.source_system,
            f.accession_number,
            f.rcept_no,
            f.filing_type,
            f.report_type,
            f.filing_date,
            f.fiscal_year
        FROM filings f
        LEFT JOIN companies c ON f.company_id = c.id
        ORDER BY f.id
    """, "filings.csv", "SEC/DART filing metadata")

    # 6. Generate summary stats
    cur.execute("""
        SELECT source_system, quality_flag, COUNT(*)
        FROM license_contracts
        GROUP BY source_system, quality_flag
        ORDER BY source_system, quality_flag
    """)
    quality_breakdown = {}
    for src, flag, cnt in cur.fetchall():
        quality_breakdown[f"{src}/{flag}"] = cnt

    cur.execute("""
        SELECT COUNT(DISTINCT c.id)
        FROM companies c
        JOIN filings f ON f.company_id = c.id
        JOIN license_contracts lc ON lc.filing_id = f.id
        WHERE lc.quality_flag = 'clean'
    """)
    companies_with_clean = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM financial_terms ft
        JOIN license_contracts lc ON ft.contract_id = lc.id
        WHERE lc.quality_flag = 'clean' AND ft.term_type = 'royalty' AND ft.rate IS NOT NULL
    """)
    royalty_observations = cur.fetchone()[0]

    cur.execute("""
        SELECT tech_category, COUNT(*) FROM license_contracts
        WHERE quality_flag = 'clean'
        GROUP BY tech_category ORDER BY COUNT(*) DESC LIMIT 15
    """)
    top_categories = {r[0]: r[1] for r in cur.fetchall()}

    summary = {
        "export_date": datetime.now().isoformat(),
        "dataset_name": "IP License Agreements from Public Regulatory Filings (SEC EDGAR + DART)",
        "version": "1.0",
        "total_extractions": stats["license_contracts_total"],
        "clean_contracts": stats["license_contracts_clean"],
        "financial_terms": stats["financial_terms"],
        "companies": stats["companies"],
        "filings": stats["filings"],
        "companies_with_clean_contracts": companies_with_clean,
        "royalty_rate_observations": royalty_observations,
        "quality_breakdown": quality_breakdown,
        "top_categories_clean": top_categories,
        "sources": {
            "SEC_EDGAR": {"jurisdiction": "United States", "filing_type": "10-K", "period": "2019-2025"},
            "DART": {"jurisdiction": "South Korea", "filing_type": "Annual/Semi/Quarterly Reports", "period": "2023-2026"},
        },
        "extraction_models": {
            "SEC": "Google Gemini 2.0 Flash",
            "DART": "Gemma3-4B (local, via Ollama)"
        },
        "license": "CC BY 4.0",
        "files": [
            {"name": "license_contracts.csv", "rows": stats["license_contracts_total"], "description": "All extractions with quality flags"},
            {"name": "license_contracts_clean.csv", "rows": stats["license_contracts_clean"], "description": "Quality-filtered subset"},
            {"name": "financial_terms.csv", "rows": stats["financial_terms"], "description": "Royalty and upfront payment details"},
            {"name": "companies.csv", "rows": stats["companies"], "description": "Company master data"},
            {"name": "filings.csv", "rows": stats["filings"], "description": "Filing metadata"},
        ]
    }

    summary_path = os.path.join(OUT_DIR, "dataset_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  dataset_summary.json - aggregate stats")

    conn.close()
    print(f"\nDone. All files in: {OUT_DIR}")


if __name__ == "__main__":
    main()
