"""DART contract routes - PostgreSQL-based contract endpoints."""
import math
import json
import os
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional

from ..database import get_db
from ..models import LicenseContract, FinancialTerm, Filing, Company
from .helpers import format_contracts

router = APIRouter(tags=["dart"])


@router.get("/contracts")
def dart_contracts(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    search: Optional[str] = None,
    category: Optional[str] = None,
    min_confidence: Optional[float] = None,
    sort: str = "confidence_score:desc",
    db: Session = Depends(get_db),
):
    """List extracted DART license contracts (from PostgreSQL)."""
    q = db.query(LicenseContract).filter(LicenseContract.source_system == "DART")

    if search:
        term = f"%{search.lower()}%"
        q = q.filter(or_(
            func.lower(LicenseContract.licensor_name).like(term),
            func.lower(LicenseContract.licensee_name).like(term),
            func.lower(LicenseContract.tech_name).like(term),
        ))
    if category:
        q = q.filter(func.lower(LicenseContract.tech_category) == category.lower())
    if min_confidence is not None:
        q = q.filter(LicenseContract.confidence_score >= min_confidence)

    sort_parts = sort.split(":")
    sort_col = getattr(LicenseContract, sort_parts[0], LicenseContract.confidence_score)
    q = q.order_by(sort_col.desc().nullslast() if len(sort_parts) <= 1 or sort_parts[1] != "asc" else sort_col.asc().nullslast())

    total = q.count()
    total_pages = max(1, math.ceil(total / page_size))
    rows = q.offset((page - 1) * page_size).limit(page_size).all()

    data = format_contracts(db, rows, include_reasoning=True)

    return {"data": data, "pagination": {"page": page, "page_size": page_size, "total": total, "total_pages": total_pages}}


@router.get("/contracts/stats")
def dart_contract_stats(db: Session = Depends(get_db)):
    """Stats for extracted DART contracts."""
    q = db.query(LicenseContract).filter(LicenseContract.source_system == "DART")
    total = q.count()
    companies = db.query(func.count(func.distinct(Filing.company_id))).join(
        LicenseContract, LicenseContract.filing_id == Filing.id
    ).filter(LicenseContract.source_system == "DART").scalar() or 0

    avg_conf = q.with_entities(func.avg(LicenseContract.confidence_score)).scalar()

    # Categories
    cats = db.query(LicenseContract.tech_category, func.count()).filter(
        LicenseContract.source_system == "DART", LicenseContract.tech_category.isnot(None)
    ).group_by(LicenseContract.tech_category).order_by(func.count().desc()).limit(15).all()

    # Royalty stats
    royalties = db.query(FinancialTerm.rate).join(LicenseContract).filter(
        LicenseContract.source_system == "DART", FinancialTerm.term_type == "royalty",
        FinancialTerm.rate.isnot(None), FinancialTerm.rate > 0, FinancialTerm.rate < 100,
    ).all()
    royalty_values = [r[0] for r in royalties]

    return {
        "total_contracts": total,
        "total_companies": companies,
        "avg_confidence": round(avg_conf, 3) if avg_conf else None,
        "avg_royalty": round(sum(royalty_values) / len(royalty_values), 2) if royalty_values else None,
        "contracts_with_royalty": len(royalty_values),
        "by_category": [{"category": r[0], "count": r[1]} for r in cats],
        "extraction_status": "running" if total < 100 else "done",
    }


@router.get("/extraction-status")
def extraction_status():
    """Check DART extraction progress."""
    import json
    status_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "dart_extraction_status.json",
    )
    try:
        with open(status_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"status": "not_started"}
    except Exception:
        return {"status": "unknown"}
