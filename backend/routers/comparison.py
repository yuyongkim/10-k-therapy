import statistics
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import LicenseContract, FinancialTerm
from ..schemas import ComparisonRequest, ComparisonResponse, ContractOut
from .contracts import _build_contract_out

router = APIRouter(prefix="/comparison", tags=["comparison"])


@router.post("/", response_model=ComparisonResponse)
def find_comparables(req: ComparisonRequest, db: Session = Depends(get_db)):
    """Find comparable license contracts for valuation benchmarking."""
    q = db.query(LicenseContract).filter(
        LicenseContract.confidence_score >= req.min_confidence
    )

    if req.tech_category:
        q = q.filter(func.lower(LicenseContract.tech_category) == req.tech_category.lower())

    if req.industry:
        q = q.filter(func.lower(LicenseContract.industry) == req.industry.lower())

    if req.territory:
        q = q.filter(LicenseContract.territory.ilike(f"%{req.territory}%"))

    q = q.order_by(LicenseContract.confidence_score.desc().nullslast())
    comparables = q.limit(50).all()

    # Collect financial metrics
    royalties = []
    upfronts = []
    terms = []

    for c in comparables:
        for ft in c.financial_terms:
            if ft.term_type == "royalty" and ft.rate is not None and 0 < ft.rate < 100:
                royalties.append(ft.rate)
            elif ft.term_type == "upfront" and ft.amount is not None and ft.amount > 0:
                upfronts.append(ft.amount)
        if c.term_years and c.term_years > 0:
            terms.append(c.term_years)

    def _range_stats(values):
        if not values:
            return {"min": None, "max": None, "median": None, "mean": None, "count": 0}
        return {
            "min": round(min(values), 2),
            "max": round(max(values), 2),
            "median": round(statistics.median(values), 2),
            "mean": round(statistics.mean(values), 2),
            "count": len(values),
        }

    contract_outs = [_build_contract_out(c, db) for c in comparables[:20]]

    return ComparisonResponse(
        comparable_count=len(comparables),
        royalty_range=_range_stats(royalties),
        upfront_range=_range_stats(upfronts),
        term_range=_range_stats(terms),
        comparables=contract_outs,
    )
