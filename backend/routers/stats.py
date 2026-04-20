from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, select

from ..database import get_db
from ..models import LicenseContract, FinancialTerm, Filing, Company, CostTracking
from ..schemas import StatsResponse
from .helpers import scope_filter_conditions

router = APIRouter(prefix="/stats", tags=["statistics"])


@router.get("", response_model=StatsResponse)
def get_stats(quality: str = Query("clean"), db: Session = Depends(get_db)):
    # Build filter predicates. For 'clean' we add the scope blacklist +
    # placeholder-licensor exclusions so false positives (customs permits,
    # equity transfers, debt guarantees) don't skew counts.
    quality_preds = []
    if quality != "all":
        quality_preds.append(LicenseContract.quality_flag == quality)
    if quality == "clean":
        quality_preds.extend(scope_filter_conditions(LicenseContract))

    # Convenience: None if empty, for building .filter() calls.
    def qfilter(q):
        return q.filter(*quality_preds) if quality_preds else q

    total = qfilter(db.query(func.count(LicenseContract.id))).scalar() or 0

    # Companies
    company_count = qfilter(
        db.query(func.count(func.distinct(Filing.company_id)))
        .join(LicenseContract, LicenseContract.filing_id == Filing.id)
    ).scalar() or 0

    # Clean contract IDs for financial term filtering
    if quality_preds:
        clean_ids_q = qfilter(db.query(LicenseContract.id)).subquery()
        ft_filter = FinancialTerm.contract_id.in_(select(clean_ids_q))
    else:
        ft_filter = True

    # Royalty + upfront (with sanity filtering to exclude 199% / 0% / sub-$10K noise)
    contracts_with_royalty = set(
        r[0] for r in db.query(FinancialTerm.contract_id)
        .filter(
            FinancialTerm.term_type == "royalty",
            FinancialTerm.rate.isnot(None),
            FinancialTerm.rate >= 0.01,
            FinancialTerm.rate <= 30,
            ft_filter,
        ).all()
    )
    contracts_with_upfront = set(
        r[0] for r in db.query(FinancialTerm.contract_id)
        .filter(
            FinancialTerm.term_type == "upfront",
            FinancialTerm.amount.isnot(None),
            FinancialTerm.amount >= 10_000,
            ft_filter,
        ).all()
    )
    both = len(contracts_with_royalty & contracts_with_upfront)

    # Avg royalty (same sanity band)
    avg_royalty = (
        db.query(func.avg(FinancialTerm.rate))
        .filter(
            FinancialTerm.term_type == "royalty",
            FinancialTerm.rate >= 0.01,
            FinancialTerm.rate <= 30,
            ft_filter,
        )
        .scalar()
    )

    # Avg confidence
    avg_conf = qfilter(db.query(func.avg(LicenseContract.confidence_score))).scalar()

    # By model
    model_rows = qfilter(
        db.query(LicenseContract.extraction_model, func.count())
    ).group_by(LicenseContract.extraction_model).all()
    by_model = {(r[0] or "unknown"): r[1] for r in model_rows}

    # By source
    source_rows = qfilter(
        db.query(LicenseContract.source_system, func.count())
    ).group_by(LicenseContract.source_system).all()
    by_source = {(r[0] or "unknown"): r[1] for r in source_rows}

    # By category
    cat_rows = qfilter(
        db.query(LicenseContract.tech_category, func.count())
        .filter(LicenseContract.tech_category.isnot(None))
    ).group_by(LicenseContract.tech_category).order_by(func.count().desc()).limit(15).all()
    by_category = [{"category": r[0], "count": r[1]} for r in cat_rows]

    # By year
    year_rows = qfilter(
        db.query(Filing.fiscal_year, func.count())
        .join(LicenseContract, LicenseContract.filing_id == Filing.id)
        .filter(Filing.fiscal_year.isnot(None))
    ).group_by(Filing.fiscal_year).order_by(Filing.fiscal_year).all()
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
