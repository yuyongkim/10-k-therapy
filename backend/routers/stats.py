from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, select

from ..database import get_db
from ..models import LicenseContract, FinancialTerm, Filing, Company, CostTracking
from ..schemas import StatsResponse

router = APIRouter(prefix="/stats", tags=["statistics"])


@router.get("/", response_model=StatsResponse)
def get_stats(quality: str = Query("clean"), db: Session = Depends(get_db)):
    qf = LicenseContract.quality_flag == quality if quality != "all" else True

    total = db.query(func.count(LicenseContract.id)).filter(qf).scalar() or 0

    # Companies
    company_count = (
        db.query(func.count(func.distinct(Filing.company_id)))
        .join(LicenseContract, LicenseContract.filing_id == Filing.id)
        .filter(qf)
        .scalar() or 0
    )

    # Clean contract IDs for financial term filtering
    if quality != "all":
        clean_ids_q = db.query(LicenseContract.id).filter(qf).subquery()
        ft_filter = FinancialTerm.contract_id.in_(select(clean_ids_q))
    else:
        ft_filter = True

    # Royalty + upfront
    contracts_with_royalty = set(
        r[0] for r in db.query(FinancialTerm.contract_id)
        .filter(FinancialTerm.term_type == "royalty", FinancialTerm.rate.isnot(None), ft_filter).all()
    )
    contracts_with_upfront = set(
        r[0] for r in db.query(FinancialTerm.contract_id)
        .filter(FinancialTerm.term_type == "upfront", FinancialTerm.amount.isnot(None), ft_filter).all()
    )
    both = len(contracts_with_royalty & contracts_with_upfront)

    # Avg royalty
    avg_royalty = (
        db.query(func.avg(FinancialTerm.rate))
        .filter(FinancialTerm.term_type == "royalty", FinancialTerm.rate > 0, FinancialTerm.rate < 100, ft_filter)
        .scalar()
    )

    # Avg confidence
    avg_conf = db.query(func.avg(LicenseContract.confidence_score)).filter(qf).scalar()

    # By model
    model_rows = (
        db.query(LicenseContract.extraction_model, func.count())
        .filter(qf)
        .group_by(LicenseContract.extraction_model).all()
    )
    by_model = {(r[0] or "unknown"): r[1] for r in model_rows}

    # By source
    source_rows = (
        db.query(LicenseContract.source_system, func.count())
        .filter(qf)
        .group_by(LicenseContract.source_system).all()
    )
    by_source = {(r[0] or "unknown"): r[1] for r in source_rows}

    # By category
    cat_rows = (
        db.query(LicenseContract.tech_category, func.count())
        .filter(qf, LicenseContract.tech_category.isnot(None))
        .group_by(LicenseContract.tech_category)
        .order_by(func.count().desc()).limit(15).all()
    )
    by_category = [{"category": r[0], "count": r[1]} for r in cat_rows]

    # By year
    year_rows = (
        db.query(Filing.fiscal_year, func.count())
        .join(LicenseContract, LicenseContract.filing_id == Filing.id)
        .filter(qf, Filing.fiscal_year.isnot(None))
        .group_by(Filing.fiscal_year).order_by(Filing.fiscal_year).all()
    )
    by_year = [{"year": r[0], "count": r[1]} for r in year_rows]

    # Monthly cost
    from datetime import datetime, timezone
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    monthly_cost = (
        db.query(func.coalesce(func.sum(CostTracking.total_cost_usd), 0))
        .filter(CostTracking.month == month).scalar() or 0
    )

    return StatsResponse(
        total_contracts=total,
        total_companies=company_count,
        both_financial_terms=both,
        avg_royalty_rate=round(avg_royalty, 2) if avg_royalty else None,
        avg_confidence=round(avg_conf, 3) if avg_conf else None,
        by_model=by_model,
        by_source=by_source,
        by_category=by_category,
        by_year=by_year,
        monthly_api_cost=float(monthly_cost),
    )
