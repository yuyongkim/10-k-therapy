"""DART RAG routes - RAG-based search and benchmark endpoints."""
import os
import logging
import statistics
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional

from ..database import get_db
from ..models import LicenseContract, FinancialTerm, Filing
from .helpers import (
    format_contracts, calculate_benchmark, extract_search_keywords,
    get_available_industries,
)

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from services.rag_engine import RAGEngine

logger = logging.getLogger(__name__)

# Lazy RAG init
_rag: RAGEngine | None = None

def _get_rag() -> RAGEngine:
    global _rag
    if _rag is None:
        _rag = RAGEngine()
    return _rag

router = APIRouter(tags=["dart"])


class SimilarCaseQuery(BaseModel):
    query: str  # e.g. "화학 촉매 기술 라이선스 로열티율" or "polyethylene license cost"
    industry: Optional[str] = None  # e.g. "Chemical", "Pharmaceutical"
    source: Optional[str] = None  # "sec", "dart", "litigation", or None for all
    max_results: int = 10


@router.post("/similar-cases")
def search_similar_cases(req: SimilarCaseQuery, db: Session = Depends(get_db)):
    """
    RAG 기반 유사 라이선스 사례 검색.
    ChromaDB 벡터 검색 + DB 계약 데이터를 결합하여 유사 산업/기술 사례를 반환합니다.

    사용 예시:
    - {"query": "폴리에틸렌 촉매 기술 라이선스 비용"}
    - {"query": "반도체 특허 로열티율", "industry": "Semiconductor"}
    - {"query": "pharmaceutical patent royalty rate", "source": "sec"}
    """
    rag = _get_rag()
    results = {"rag_results": [], "db_contracts": [], "benchmark": None}

    # 1. RAG vector search across collections
    collections_to_search = []
    if req.source == "sec":
        collections_to_search = [("license_agreements", req.max_results)]
    elif req.source == "dart":
        collections_to_search = [("dart_filings", req.max_results)]
    elif req.source == "litigation":
        collections_to_search = [("litigation_royalties", req.max_results)]
    else:
        # Search all
        collections_to_search = [
            ("license_agreements", req.max_results),
            ("dart_filings", min(5, req.max_results)),
            ("litigation_royalties", min(5, req.max_results)),
        ]

    all_rag = []
    for coll_name, n in collections_to_search:
        try:
            where_filter = None
            if req.industry and coll_name == "license_agreements":
                where_filter = {"tech_category": req.industry}

            hits = rag.search_similar(
                req.query, n_results=n,
                collection_name=coll_name,
                where_filter=where_filter,
            )
            for h in hits:
                h["collection"] = coll_name
            all_rag.extend(hits)
        except Exception as e:
            logger.warning("RAG search failed for %s: %s", coll_name, e)

    # Sort by distance (lower = more similar)
    all_rag.sort(key=lambda x: x.get("distance", 999))
    results["rag_results"] = [
        {
            "id": r["id"],
            "source": r.get("metadata", {}).get("source", r.get("collection", "")),
            "company": r.get("metadata", {}).get("company", ""),
            "category": r.get("metadata", {}).get("tech_category", ""),
            "score": r.get("metadata", {}).get("score", r.get("metadata", {}).get("confidence", 0)),
            "distance": round(r.get("distance", 0), 4),
            "snippet": r.get("document", "")[:500],
        }
        for r in all_rag[:req.max_results]
    ]

    # 2. DB contract search - keyword-based from query
    keywords = extract_search_keywords(req.query)
    if keywords:
        keyword_conditions = []
        for kw in keywords:
            term = f"%{kw}%"
            keyword_conditions.append(func.lower(LicenseContract.tech_name).like(term))
            keyword_conditions.append(func.lower(LicenseContract.licensor_name).like(term))
            keyword_conditions.append(func.lower(LicenseContract.tech_category).like(term))

        q = db.query(LicenseContract).filter(or_(*keyword_conditions))
        if req.industry:
            q = q.filter(func.lower(LicenseContract.tech_category).like(f"%{req.industry.lower()}%"))

        contracts = q.order_by(
            LicenseContract.confidence_score.desc().nullslast()
        ).limit(req.max_results).all()

        results["db_contracts"] = format_contracts(db, contracts)

    # 3. Benchmark calculation from found contracts
    results["benchmark"] = calculate_benchmark(db, contracts if keywords else [], req.industry)

    return results


@router.get("/benchmark/{industry}")
def industry_benchmark(industry: str, db: Session = Depends(get_db)):
    """
    특정 산업군의 라이선스 벤치마크 데이터를 반환합니다.

    SEC + DART 전체 데이터에서 로열티율, 업프론트, 계약기간 등의 통계를 제공합니다.
    """
    q = db.query(LicenseContract).filter(
        func.lower(LicenseContract.tech_category).like(f"%{industry.lower()}%"),
        LicenseContract.confidence_score >= 0.5,
    )
    contracts = q.all()

    if not contracts:
        return {
            "industry": industry,
            "total_contracts": 0,
            "message": f"No contracts found for industry '{industry}'",
            "available_industries": get_available_industries(db),
        }

    benchmark = calculate_benchmark(db, contracts, industry)
    benchmark["industry"] = industry
    benchmark["total_contracts"] = len(contracts)

    # Top licensors
    licensor_counts = {}
    for c in contracts:
        if c.licensor_name:
            name = c.licensor_name.strip()
            licensor_counts[name] = licensor_counts.get(name, 0) + 1
    benchmark["top_licensors"] = sorted(
        [{"name": k, "count": v} for k, v in licensor_counts.items()],
        key=lambda x: x["count"], reverse=True,
    )[:10]

    # Source breakdown
    sec_count = sum(1 for c in contracts if c.source_system == "EDGAR")
    dart_count = sum(1 for c in contracts if c.source_system == "DART")
    benchmark["by_source"] = {"SEC": sec_count, "DART": dart_count}

    # Year trend
    year_data = {}
    for c in contracts:
        if c.filing_id:
            filing = db.query(Filing).filter(Filing.id == c.filing_id).first()
            if filing and filing.fiscal_year:
                yr = filing.fiscal_year
                if yr not in year_data:
                    year_data[yr] = {"count": 0, "royalties": []}
                year_data[yr]["count"] += 1
                for ft in c.financial_terms:
                    if ft.term_type == "royalty" and ft.rate and 0 < ft.rate < 100:
                        year_data[yr]["royalties"].append(ft.rate)

    benchmark["year_trend"] = [
        {
            "year": yr,
            "count": d["count"],
            "avg_royalty": round(statistics.mean(d["royalties"]), 2) if d["royalties"] else None,
        }
        for yr, d in sorted(year_data.items())
    ]

    return benchmark


@router.get("/benchmark")
def all_benchmarks(db: Session = Depends(get_db)):
    """모든 산업군의 벤치마크 요약을 반환합니다."""
    industries = get_available_industries(db)
    results = []
    for ind in industries:
        name = ind["category"]
        q = db.query(LicenseContract).filter(
            func.lower(LicenseContract.tech_category) == name.lower(),
            LicenseContract.confidence_score >= 0.5,
        )
        contracts = q.all()
        royalties = []
        for c in contracts:
            for ft in c.financial_terms:
                if ft.term_type == "royalty" and ft.rate and 0 < ft.rate < 100:
                    royalties.append(ft.rate)

        results.append({
            "industry": name,
            "total_contracts": len(contracts),
            "contracts_with_royalty": len(royalties),
            "royalty_min": round(min(royalties), 2) if royalties else None,
            "royalty_max": round(max(royalties), 2) if royalties else None,
            "royalty_median": round(statistics.median(royalties), 2) if royalties else None,
        })

    return {"benchmarks": results}


@router.get("/rag-stats")
def rag_stats():
    """RAG 엔진의 인덱싱 상태를 반환합니다."""
    try:
        rag = _get_rag()
        return rag.get_collection_stats()
    except Exception as e:
        return {"error": str(e)}
