"""Shared helper functions for API routers.

Consolidates duplicated patterns:
- Contract ORM → dict conversion
- Financial term extraction (royalty/upfront)
- Benchmark calculation (royalty/upfront/term stats)
- Search keyword extraction
"""

import logging
import re
import statistics
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import LicenseContract, FinancialTerm, Filing, Company

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Contract formatting (used by contracts, dart, assistant routers)
# ---------------------------------------------------------------------------

def extract_financial_terms(contract) -> dict:
    """Extract royalty rate and upfront amount from a contract's financial_terms."""
    royalty = None
    upfront = None
    upfront_ccy = None
    for ft in contract.financial_terms:
        if ft.term_type == "royalty" and ft.rate is not None:
            royalty = ft.rate
        elif ft.term_type == "upfront" and ft.amount is not None:
            upfront = ft.amount
            upfront_ccy = ft.currency
    return {"royalty_rate": royalty, "upfront_amount": upfront, "upfront_currency": upfront_ccy}


def get_company_info(db: Session, contract) -> dict:
    """Resolve company name and filing year from a contract's filing relationship."""
    company_name = None
    ticker = None
    filing_year = None
    accession_number = None
    rcept_no = None
    filing_date = None
    source_url = None
    if contract.filing_id:
        filing = db.query(Filing).filter(Filing.id == contract.filing_id).first()
        if filing:
            filing_year = filing.fiscal_year
            accession_number = filing.accession_number
            rcept_no = filing.rcept_no
            filing_date = filing.filing_date
            if filing.source_system == "DART" and filing.rcept_no:
                source_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={filing.rcept_no}"
            elif filing.source_system == "EDGAR" and filing.accession_number:
                source_url = f"https://www.sec.gov/edgar/search/#/q={filing.accession_number}"
            co = db.query(Company).filter(Company.id == filing.company_id).first()
            if co:
                company_name = co.name_local or co.name_en
                ticker = co.ticker
    return {
        "company_name": company_name,
        "ticker": ticker,
        "filing_year": filing_year,
        "accession_number": accession_number,
        "rcept_no": rcept_no,
        "filing_date": filing_date,
        "source_url": source_url,
    }


def format_contract(db: Session, c, *, include_reasoning: bool = False) -> dict:
    """Format a single LicenseContract ORM object into an API response dict."""
    fin = extract_financial_terms(c)
    info = get_company_info(db, c)

    result = {
        "id": c.id,
        "company": info["company_name"],
        "ticker": info["ticker"],
        "licensor": c.licensor_name,
        "licensee": c.licensee_name,
        "tech_name": c.tech_name,
        "category": c.tech_category,
        "industry": c.industry,
        "royalty_rate": fin["royalty_rate"],
        "upfront_amount": fin["upfront_amount"],
        "upfront_currency": fin["upfront_currency"],
        "territory": c.territory,
        "term_years": c.term_years,
        "exclusivity": c.exclusivity,
        "confidence": c.confidence_score,
        "model": c.extraction_model,
        "source": c.source_system,
        "year": info["filing_year"],
        "accession_number": info["accession_number"],
        "rcept_no": info["rcept_no"],
        "filing_date": info["filing_date"],
        "source_url": info["source_url"],
    }
    if include_reasoning:
        result["reasoning"] = c.reasoning
    return result


def format_contracts(db: Session, contracts, **kwargs) -> List[dict]:
    """Format a list of contracts."""
    return [format_contract(db, c, **kwargs) for c in contracts]


# ---------------------------------------------------------------------------
# Benchmark calculation (used by dart, comparison routers)
# ---------------------------------------------------------------------------

def calculate_benchmark(db: Session, contracts, industry: Optional[str] = None) -> dict:
    """Calculate benchmark statistics from a set of contracts."""
    royalties = []
    upfronts = []
    terms = []

    for c in contracts:
        for ft in c.financial_terms:
            if ft.term_type == "royalty" and ft.rate and 0 < ft.rate < 100:
                royalties.append(ft.rate)
            elif ft.term_type == "upfront" and ft.amount and ft.amount > 0:
                upfronts.append(ft.amount)
        if c.term_years and c.term_years > 0:
            terms.append(c.term_years)

    benchmark = {}
    if royalties:
        benchmark["royalty"] = {
            "min": round(min(royalties), 2),
            "max": round(max(royalties), 2),
            "mean": round(statistics.mean(royalties), 2),
            "median": round(statistics.median(royalties), 2),
            "stdev": round(statistics.stdev(royalties), 2) if len(royalties) > 1 else 0,
            "count": len(royalties),
        }
    if upfronts:
        benchmark["upfront"] = {
            "min": round(min(upfronts)),
            "max": round(max(upfronts)),
            "mean": round(statistics.mean(upfronts)),
            "median": round(statistics.median(upfronts)),
            "count": len(upfronts),
        }
    if terms:
        benchmark["term_years"] = {
            "min": round(min(terms), 1),
            "max": round(max(terms), 1),
            "mean": round(statistics.mean(terms), 1),
            "median": round(statistics.median(terms), 1),
            "count": len(terms),
        }

    # Exclusivity breakdown
    excl_counts = {"exclusive": 0, "non-exclusive": 0, "unknown": 0}
    for c in contracts:
        ex = (c.exclusivity or "").lower()
        if "exclusive" in ex and "non" not in ex:
            excl_counts["exclusive"] += 1
        elif "non" in ex:
            excl_counts["non-exclusive"] += 1
        else:
            excl_counts["unknown"] += 1
    benchmark["exclusivity_breakdown"] = excl_counts

    return benchmark


# ---------------------------------------------------------------------------
# Search keyword extraction (used by dart, assistant routers)
# ---------------------------------------------------------------------------

STOPWORDS_KR = {
    "의", "에", "을", "를", "이", "가", "은", "는", "와", "과", "로", "으로",
    "에서", "대해", "관한", "위한", "어떤", "얼마", "정도", "사례", "비용",
    "검색", "찾기", "알려", "알고", "싶어", "문의", "질문",
}
STOPWORDS_EN = {
    "the", "a", "an", "of", "for", "in", "on", "is", "are", "what", "how",
    "much", "many", "about", "license", "licensing", "cost", "rate", "fee",
}


def extract_search_keywords(query: str, max_keywords: int = 10) -> List[str]:
    """Extract meaningful search keywords from a query string (Korean + English)."""
    tokens = re.split(r"[\s,;/]+", query)
    keywords = []
    for token in tokens:
        token = token.strip().lower()
        if len(token) < 2:
            continue
        if token in STOPWORDS_KR or token in STOPWORDS_EN:
            continue
        keywords.append(token)
    return keywords[:max_keywords]


def get_available_industries(db: Session) -> List[dict]:
    """Get list of industries with contract counts."""
    rows = (
        db.query(LicenseContract.tech_category, func.count())
        .filter(
            LicenseContract.tech_category.isnot(None),
            LicenseContract.confidence_score >= 0.5,
        )
        .group_by(LicenseContract.tech_category)
        .order_by(func.count().desc())
        .all()
    )
    return [{"category": r[0], "count": r[1]} for r in rows]
