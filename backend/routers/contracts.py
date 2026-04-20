from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_
from typing import Optional
import math

from ..database import get_db
from ..models import LicenseContract, FinancialTerm, Filing, Company
from ..schemas import (
    ContractOut, ContractDetail, ContractListResponse,
    FinancialTermOut, PaginationMeta,
)
from .helpers import extract_financial_terms, get_company_info, apply_scope_filter

router = APIRouter(prefix="/contracts", tags=["contracts"])


def _build_contract_out(c, db: Session) -> ContractOut:
    """Build ContractOut from ORM object with denormalized fields."""
    info = get_company_info(db, c)
    fin = extract_financial_terms(c)

    return ContractOut(
        id=c.id,
        licensor_name=c.licensor_name,
        licensee_name=c.licensee_name,
        tech_name=c.tech_name,
        tech_category=c.tech_category,
        industry=c.industry,
        territory=c.territory,
        term_years=c.term_years,
        confidence_score=c.confidence_score,
        extraction_model=c.extraction_model,
        source_system=c.source_system,
        company_name=info["company_name"],
        ticker=info["ticker"],
        filing_year=info["filing_year"],
        accession_number=info["accession_number"],
        rcept_no=info["rcept_no"],
        filing_date=info["filing_date"],
        source_url=info["source_url"],
        royalty_rate=fin["royalty_rate"],
        upfront_amount=fin["upfront_amount"],
    )


@router.get("", response_model=ContractListResponse)
def list_contracts(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    search: Optional[str] = None,
    category: Optional[str] = None,
    industry: Optional[str] = None,
    min_confidence: Optional[float] = None,
    source: Optional[str] = None,
    quality: Optional[str] = Query("clean", description="Quality filter: clean, all, noise, duplicate, low_quality"),
    sort: str = "confidence_score:desc",
    db: Session = Depends(get_db),
):
    q = db.query(LicenseContract)

    if quality and quality != "all":
        q = q.filter(LicenseContract.quality_flag == quality)
        if quality == "clean":
            # Extra strictness — drop scope-leaked agreements + placeholder licensors
            q = apply_scope_filter(q, LicenseContract)

    if search:
        term = f"%{search.lower()}%"
        q = q.filter(
            or_(
                func.lower(LicenseContract.licensor_name).like(term),
                func.lower(LicenseContract.licensee_name).like(term),
                func.lower(LicenseContract.tech_name).like(term),
                func.lower(LicenseContract.tech_category).like(term),
            )
        )

    if category:
        q = q.filter(func.lower(LicenseContract.tech_category) == category.lower())

    if industry:
        q = q.filter(func.lower(LicenseContract.industry) == industry.lower())

    if min_confidence is not None:
        q = q.filter(LicenseContract.confidence_score >= min_confidence)

    if source:
        q = q.filter(LicenseContract.source_system == source.upper())

    # Sorting
    sort_parts = sort.split(":")
    sort_col = getattr(LicenseContract, sort_parts[0], LicenseContract.confidence_score)
    if len(sort_parts) > 1 and sort_parts[1] == "asc":
        q = q.order_by(sort_col.asc().nullslast())
    else:
        q = q.order_by(sort_col.desc().nullslast())

    total = q.count()
    total_pages = max(1, math.ceil(total / page_size))
    offset = (page - 1) * page_size

    rows = q.offset(offset).limit(page_size).all()
    data = [_build_contract_out(c, db) for c in rows]

    return ContractListResponse(
        data=data,
        pagination=PaginationMeta(
            page=page, page_size=page_size, total=total, total_pages=total_pages,
        ),
    )


@router.get("/{contract_id}", response_model=ContractDetail)
def get_contract(contract_id: int, db: Session = Depends(get_db)):
    c = db.query(LicenseContract).filter(LicenseContract.id == contract_id).first()
    if not c:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Contract not found")

    base = _build_contract_out(c, db)
    terms = [FinancialTermOut.model_validate(ft) for ft in c.financial_terms]

    return ContractDetail(
        **base.model_dump(),
        exclusivity=c.exclusivity,
        complexity_score=c.complexity_score,
        processing_cost_usd=c.processing_cost_usd,
        reasoning=c.reasoning,
        financial_terms=terms,
        created_at=c.created_at,
    )
