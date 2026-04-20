"""
AI-powered License Intelligence Assistant.
Uses Qwen3 (local) + RAG to answer natural language queries about license contracts.
"""
import json
import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, text

from ..database import get_db
from ..models import LicenseContract, FinancialTerm, Filing, Company

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from services.ai_router import QwenProcessor
from services.rag_engine import RAGEngine
from utils.common import clean_qwen_json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/assistant", tags=["assistant"])

# Lazy init
_qwen: QwenProcessor | None = None
_rag: RAGEngine | None = None


def _get_qwen() -> QwenProcessor:
    global _qwen
    if _qwen is None:
        _qwen = QwenProcessor(model="qwen3:8b")
    return _qwen


def _get_rag() -> RAGEngine:
    global _rag
    if _rag is None:
        _rag = RAGEngine()
    return _rag


class AssistantQuery(BaseModel):
    question: str
    max_results: int = 10


class SearchSuggestion(BaseModel):
    keywords: list[str]
    categories: list[str]
    reasoning: str


class ContractSummary(BaseModel):
    id: int
    licensor: str | None
    licensee: str | None
    tech_name: str | None
    category: str | None
    royalty_rate: float | None
    upfront_amount: float | None
    term_years: float | None
    territory: str | None
    confidence: float | None
    company: str | None
    year: int | None


class AnalysisResult(BaseModel):
    summary: str
    market_range: dict | None
    recommendation: str


class AssistantResponse(BaseModel):
    search_suggestions: SearchSuggestion
    contracts: list[ContractSummary]
    analysis: AnalysisResult
    rag_context_used: bool


@router.post("/query", response_model=AssistantResponse)
def assistant_query(req: AssistantQuery, db: Session = Depends(get_db)):
    """
    Natural language query → search suggestions → DB search → AI analysis.

    Flow:
    1. Qwen3 interprets the question and suggests search keywords/categories
    2. DB + RAG search for matching contracts
    3. Qwen3 analyzes results and provides recommendations
    """
    qwen = _get_qwen()

    # Step 1: Generate search suggestions from the question
    suggestions = _generate_search_suggestions(qwen, req.question)

    # Step 2: Search DB with suggested keywords/categories
    contracts = _search_contracts(db, suggestions, req.max_results)

    # Step 3: Get RAG context for additional similarity
    rag_context = ""
    rag_used = False
    try:
        rag = _get_rag()
        rag_results = rag.search_similar(req.question, n_results=5)
        if rag_results:
            rag_context = "\n".join(r["document"][:300] for r in rag_results)
            rag_used = True
    except Exception as e:
        logger.warning("RAG search failed: %s", e)

    # Step 4: Analyze results with Qwen3
    analysis = _analyze_results(qwen, req.question, contracts, rag_context)

    return AssistantResponse(
        search_suggestions=suggestions,
        contracts=contracts,
        analysis=analysis,
        rag_context_used=rag_used,
    )


def _generate_search_suggestions(qwen: QwenProcessor, question: str) -> SearchSuggestion:
    """Ask Qwen3 to interpret the question and suggest search terms."""
    prompt = f"""You are a license agreement search assistant. The user wants to find relevant technology license contracts.

User's question: "{question}"

Based on this question, suggest:
1. keywords: 5-10 English search keywords to find relevant license agreements in a database. Include specific company names known as technology licensors in this field (e.g. for petrochemical: Honeywell, UOP, LyondellBasell, TechnipFMC, KBR, Shell, ExxonMobil). Also include specific technology terms (e.g. catalyst, cracking, polymerization, reforming).
2. categories: 2-5 technology categories that match (from: Pharmaceutical, Software, Semiconductor, Energy, Chemical, Petroleum, Automotive, Telecommunications, Biotechnology, Medical Device, Downstream, Refining, Catalyst, Other)
3. reasoning: Brief explanation of why these search terms are relevant (1-2 sentences)

Output valid JSON only:
{{"keywords": ["keyword1", "keyword2", ...], "categories": ["category1", ...], "reasoning": "..."}}"""

    try:
        result = qwen.extract_contracts(prompt, "")
        raw = result.get("raw_response", "{}")
        data = clean_qwen_json(raw)
        if data:
            return SearchSuggestion(
                keywords=data.get("keywords", []),
                categories=data.get("categories", []),
                reasoning=data.get("reasoning", ""),
            )
    except Exception as e:
        logger.warning("Search suggestion generation failed: %s", e)

    # Fallback: extract simple keywords from question
    words = question.lower().split()
    return SearchSuggestion(
        keywords=words[:5],
        categories=["Chemical", "Energy"],
        reasoning="Fallback: extracted keywords directly from question.",
    )


def _search_contracts(
    db: Session, suggestions: SearchSuggestion, max_results: int
) -> list[ContractSummary]:
    """Search PostgreSQL for contracts matching the suggestions.
    Uses a two-pass approach: strict keyword match first, then broader category match."""

    # Pass 1: Strict keyword match on tech_name, licensor_name, and reasoning
    keyword_conditions = []
    for kw in suggestions.keywords:
        # Split compound keywords for better matching
        for word in kw.lower().split():
            if len(word) >= 3:  # Include shorter words like UOP, KBR
                term = f"%{word}%"
                keyword_conditions.append(func.lower(LicenseContract.tech_name).like(term))
                keyword_conditions.append(func.lower(LicenseContract.licensor_name).like(term))
                keyword_conditions.append(func.lower(LicenseContract.reasoning).like(term))

    rows = []
    if keyword_conditions:
        # Count how many keyword conditions each row matches for relevance ranking
        from sqlalchemy import case, literal_column
        relevance_parts = []
        for kw in suggestions.keywords:
            for word in kw.lower().split():
                if len(word) >= 3:
                    term = f"%{word}%"
                    relevance_parts.append(
                        case((func.lower(LicenseContract.tech_name).like(term), 2), else_=0)
                    )
                    relevance_parts.append(
                        case((func.lower(LicenseContract.licensor_name).like(term), 2), else_=0)
                    )
                    relevance_parts.append(
                        case((func.lower(LicenseContract.reasoning).like(term), 1), else_=0)
                    )

        if relevance_parts:
            relevance_score = sum(relevance_parts)
            q = (
                db.query(LicenseContract)
                .filter(or_(*keyword_conditions))
                .filter(LicenseContract.confidence_score >= 0.4)
                .order_by(relevance_score.desc(), LicenseContract.confidence_score.desc().nullslast())
            )
        else:
            q = (
                db.query(LicenseContract)
                .filter(or_(*keyword_conditions))
                .filter(LicenseContract.confidence_score >= 0.4)
                .order_by(LicenseContract.confidence_score.desc().nullslast())
            )
        rows = q.limit(max_results).all()

    # Pass 2: If not enough results, broaden to category match
    if len(rows) < max_results:
        existing_ids = {r.id for r in rows}
        cat_conditions = []
        for cat in suggestions.categories:
            cat_conditions.append(
                func.lower(LicenseContract.tech_category).like(f"%{cat.lower()}%")
            )
        if cat_conditions:
            q2 = (
                db.query(LicenseContract)
                .filter(or_(*cat_conditions))
                .filter(LicenseContract.confidence_score >= 0.6)
                .filter(LicenseContract.id.notin_(existing_ids))
                .order_by(LicenseContract.confidence_score.desc().nullslast())
            )
            rows.extend(q2.limit(max_results - len(rows)).all())

    results = []
    for c in rows:
        # Get financial terms
        royalty = None
        upfront = None
        for ft in c.financial_terms:
            if ft.term_type == "royalty" and ft.rate is not None:
                royalty = ft.rate
            elif ft.term_type == "upfront" and ft.amount is not None:
                upfront = ft.amount

        # Get company info
        company_name = None
        filing_year = None
        if c.filing_id:
            filing = db.query(Filing).filter(Filing.id == c.filing_id).first()
            if filing:
                filing_year = filing.fiscal_year
                co = db.query(Company).filter(Company.id == filing.company_id).first()
                if co:
                    company_name = co.name_en

        results.append(ContractSummary(
            id=c.id,
            licensor=c.licensor_name,
            licensee=c.licensee_name,
            tech_name=c.tech_name,
            category=c.tech_category,
            royalty_rate=royalty,
            upfront_amount=upfront,
            term_years=c.term_years,
            territory=c.territory,
            confidence=c.confidence_score,
            company=company_name,
            year=filing_year,
        ))

    return results


def _analyze_results(
    qwen: QwenProcessor,
    question: str,
    contracts: list[ContractSummary],
    rag_context: str,
) -> AnalysisResult:
    """Ask Qwen3 to analyze the search results."""
    if not contracts:
        return AnalysisResult(
            summary="No matching contracts found. Try broadening your search.",
            market_range=None,
            recommendation="Consider searching with different keywords or categories.",
        )

    # Build contract summary for LLM
    contract_texts = []
    royalties = []
    upfronts = []
    terms = []

    for c in contracts[:10]:
        parts = []
        if c.licensor:
            parts.append(f"Licensor: {c.licensor}")
        if c.tech_name:
            parts.append(f"Tech: {c.tech_name}")
        if c.royalty_rate is not None:
            parts.append(f"Royalty: {c.royalty_rate}%")
            if 0 < c.royalty_rate < 100:
                royalties.append(c.royalty_rate)
        if c.upfront_amount is not None:
            parts.append(f"Upfront: ${c.upfront_amount:,.0f}")
            if c.upfront_amount > 0:
                upfronts.append(c.upfront_amount)
        if c.term_years:
            parts.append(f"Term: {c.term_years}y")
            terms.append(c.term_years)
        if c.territory:
            parts.append(f"Territory: {c.territory}")
        contract_texts.append(" | ".join(parts))

    contracts_str = "\n".join(f"- {t}" for t in contract_texts)

    # Calculate market range
    import statistics
    market_range = {}
    if royalties:
        market_range["royalty"] = {
            "min": round(min(royalties), 2),
            "max": round(max(royalties), 2),
            "median": round(statistics.median(royalties), 2),
            "count": len(royalties),
        }
    if upfronts:
        market_range["upfront"] = {
            "min": round(min(upfronts), 0),
            "max": round(max(upfronts), 0),
            "median": round(statistics.median(upfronts), 0),
            "count": len(upfronts),
        }
    if terms:
        market_range["term_years"] = {
            "min": round(min(terms), 1),
            "max": round(max(terms), 1),
            "median": round(statistics.median(terms), 1),
            "count": len(terms),
        }

    prompt = f"""You are a technology licensing advisor for a petrochemical company.

User's question: "{question}"

Here are {len(contracts)} relevant license contracts found in the database:
{contracts_str}

{f"Additional context from similar past agreements: {rag_context[:500]}" if rag_context else ""}

Based on these results, provide:
1. summary: 2-3 sentence analysis of the market landscape for this type of technology license (in Korean)
2. recommendation: Specific actionable advice for the user (in Korean, 2-3 sentences)

Output valid JSON only:
{{"summary": "...", "recommendation": "..."}}"""

    try:
        result = qwen.extract_contracts(prompt, "")
        raw = result.get("raw_response", "{}")
        data = clean_qwen_json(raw)
        if data:
            return AnalysisResult(
                summary=data.get("summary", "분석 결과를 생성할 수 없습니다."),
                market_range=market_range if market_range else None,
                recommendation=data.get("recommendation", ""),
            )
    except Exception as e:
        logger.warning("Analysis generation failed: %s", e)

    # Fallback with just market data
    summary_parts = [f"총 {len(contracts)}건의 유사 계약을 찾았습니다."]
    if royalties:
        summary_parts.append(f"로열티 범위: {min(royalties):.1f}% ~ {max(royalties):.1f}%")
    if upfronts:
        summary_parts.append(f"업프론트 범위: ${min(upfronts):,.0f} ~ ${max(upfronts):,.0f}")

    return AnalysisResult(
        summary=" ".join(summary_parts),
        market_range=market_range if market_range else None,
        recommendation="상세 분석을 위해 검색 조건을 조정해보세요.",
    )


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    """List all available tech categories with counts."""
    rows = (
        db.query(LicenseContract.tech_category, func.count())
        .filter(LicenseContract.tech_category.isnot(None))
        .group_by(LicenseContract.tech_category)
        .order_by(func.count().desc())
        .limit(50)
        .all()
    )
    return [{"category": r[0], "count": r[1]} for r in rows]
