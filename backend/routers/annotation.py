"""Annotation API: random sample + human verification for paper validation."""
import random
import sqlite3
import os
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import LicenseContract, FinancialTerm, Filing, Company

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/annotation", tags=["annotation"])

SQLITE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "processed", "sec_dart_analytics.db",
)

ANNOTATION_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "annotation_results.json",
)


def _load_annotations() -> dict:
    try:
        with open(ANNOTATION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"annotations": [], "stats": {}}


def _save_annotations(data: dict):
    os.makedirs(os.path.dirname(ANNOTATION_FILE), exist_ok=True)
    with open(ANNOTATION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def _get_dart_source_text(reasoning: str) -> str:
    """Try to retrieve DART source text from SQLite based on reasoning field."""
    if not reasoning or "DART section" not in reasoning:
        return ""
    try:
        # Extract section info from reasoning like "DART section score=9, section=6. 주요계약..."
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        # Get a matching section by dart_label
        parts = reasoning.split("section=")
        if len(parts) > 1:
            section_label = parts[1].strip()
            row = conn.execute(
                "SELECT plain_text FROM dart_sections WHERE dart_label LIKE ? LIMIT 1",
                (f"%{section_label[:20]}%",)
            ).fetchone()
            if row:
                conn.close()
                return row["plain_text"][:2000]
        conn.close()
    except Exception as e:
        logger.debug("Failed to get DART source: %s", e)
    return ""


@router.get("/sample")
def get_annotation_sample(
    n: int = Query(100, ge=1, le=500),
    source: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get N random contracts for annotation, with source text where available."""
    existing = _load_annotations()
    annotated_ids = {a["contract_id"] for a in existing.get("annotations", [])}

    q = db.query(LicenseContract).filter(LicenseContract.confidence_score >= 0.5)
    if source:
        q = q.filter(LicenseContract.source_system == source)

    all_contracts = q.all()
    # Exclude already annotated
    candidates = [c for c in all_contracts if c.id not in annotated_ids]

    if len(candidates) < n:
        n = len(candidates)

    sampled = random.sample(candidates, n) if candidates else []

    results = []
    for c in sampled:
        # Get financial terms
        terms = db.query(FinancialTerm).filter(FinancialTerm.contract_id == c.id).all()
        term_data = [
            {"type": t.term_type, "rate": t.rate, "amount": t.amount,
             "unit": t.rate_unit, "currency": t.currency}
            for t in terms
        ]

        # Get company info
        company_name = None
        filing_year = None
        if c.filing_id:
            filing = db.query(Filing).filter(Filing.id == c.filing_id).first()
            if filing:
                filing_year = filing.fiscal_year
                co = db.query(Company).filter(Company.id == filing.company_id).first()
                if co:
                    company_name = co.name_local or co.name_en

        # Get source text
        source_text = ""
        if c.source_system == "DART":
            source_text = _get_dart_source_text(c.reasoning or "")

        results.append({
            "contract_id": c.id,
            "source_system": c.source_system,
            "company": company_name,
            "filing_year": filing_year,
            "extraction": {
                "licensor": c.licensor_name,
                "licensee": c.licensee_name,
                "tech_name": c.tech_name,
                "tech_category": c.tech_category,
                "territory": c.territory,
                "exclusivity": c.exclusivity,
                "confidence": c.confidence_score,
                "model": c.extraction_model,
            },
            "financial_terms": term_data,
            "reasoning": c.reasoning,
            "source_text": source_text,
        })

    return {
        "total_sampled": len(results),
        "already_annotated": len(annotated_ids),
        "data": results,
    }


@router.get("/next")
def get_next_unannotated(db: Session = Depends(get_db)):
    """Get the next single contract to annotate."""
    existing = _load_annotations()
    annotated_ids = {a["contract_id"] for a in existing.get("annotations", [])}

    # Prioritize: DART first (less data), then SEC, high confidence first
    for source in ["DART", "EDGAR"]:
        contract = db.query(LicenseContract).filter(
            LicenseContract.source_system == source,
            LicenseContract.confidence_score >= 0.5,
            ~LicenseContract.id.in_(annotated_ids) if annotated_ids else True,
        ).order_by(func.random()).first()

        if contract:
            terms = db.query(FinancialTerm).filter(
                FinancialTerm.contract_id == contract.id
            ).all()

            company_name = None
            filing_year = None
            if contract.filing_id:
                filing = db.query(Filing).filter(Filing.id == contract.filing_id).first()
                if filing:
                    filing_year = filing.fiscal_year
                    co = db.query(Company).filter(Company.id == filing.company_id).first()
                    if co:
                        company_name = co.name_local or co.name_en

            source_text = ""
            if contract.source_system == "DART":
                source_text = _get_dart_source_text(contract.reasoning or "")

            return {
                "contract_id": contract.id,
                "source_system": contract.source_system,
                "company": company_name,
                "filing_year": filing_year,
                "extraction": {
                    "licensor": contract.licensor_name,
                    "licensee": contract.licensee_name,
                    "tech_name": contract.tech_name,
                    "tech_category": contract.tech_category,
                    "territory": contract.territory,
                    "exclusivity": contract.exclusivity,
                    "confidence": contract.confidence_score,
                    "model": contract.extraction_model,
                },
                "financial_terms": [
                    {"type": t.term_type, "rate": t.rate, "amount": t.amount,
                     "unit": t.rate_unit, "currency": t.currency}
                    for t in terms
                ],
                "reasoning": contract.reasoning,
                "source_text": source_text,
                "progress": {
                    "annotated": len(annotated_ids),
                    "target": 50,
                },
            }

    return {"error": "No more contracts to annotate"}


class AnnotationSubmit(BaseModel):
    contract_id: int
    # Per-field correctness
    licensor_correct: bool
    licensee_correct: bool
    tech_name_correct: bool
    category_correct: bool
    royalty_correct: bool
    territory_correct: bool
    # Overall
    is_real_license: bool  # Is this actually a license agreement (not loan/lease/etc)?
    is_hallucination: bool  # Did the model make this up entirely?
    notes: str = ""


@router.post("/submit")
def submit_annotation(ann: AnnotationSubmit):
    """Submit a single annotation verdict."""
    data = _load_annotations()

    # Check for duplicate
    for existing in data["annotations"]:
        if existing["contract_id"] == ann.contract_id:
            raise HTTPException(400, "Already annotated")

    fields_checked = [
        ann.licensor_correct, ann.licensee_correct, ann.tech_name_correct,
        ann.category_correct, ann.royalty_correct, ann.territory_correct,
    ]
    correct_count = sum(fields_checked)

    record = {
        "contract_id": ann.contract_id,
        "licensor_correct": ann.licensor_correct,
        "licensee_correct": ann.licensee_correct,
        "tech_name_correct": ann.tech_name_correct,
        "category_correct": ann.category_correct,
        "royalty_correct": ann.royalty_correct,
        "territory_correct": ann.territory_correct,
        "is_real_license": ann.is_real_license,
        "is_hallucination": ann.is_hallucination,
        "field_accuracy": correct_count / 6,
        "notes": ann.notes,
    }
    data["annotations"].append(record)

    # Update running stats
    annotations = data["annotations"]
    n = len(annotations)
    data["stats"] = {
        "total": n,
        "target": 50,
        "real_license_rate": sum(1 for a in annotations if a["is_real_license"]) / n,
        "hallucination_rate": sum(1 for a in annotations if a["is_hallucination"]) / n,
        "field_precision": {
            "licensor": sum(1 for a in annotations if a["licensor_correct"]) / n,
            "licensee": sum(1 for a in annotations if a["licensee_correct"]) / n,
            "tech_name": sum(1 for a in annotations if a["tech_name_correct"]) / n,
            "category": sum(1 for a in annotations if a["category_correct"]) / n,
            "royalty": sum(1 for a in annotations if a["royalty_correct"]) / n,
            "territory": sum(1 for a in annotations if a["territory_correct"]) / n,
        },
        "avg_field_accuracy": sum(a["field_accuracy"] for a in annotations) / n,
    }

    _save_annotations(data)
    return {"status": "ok", "progress": f"{n}/100", "stats": data["stats"]}


@router.get("/stats")
def get_annotation_stats():
    """Get current annotation statistics for the paper."""
    data = _load_annotations()
    return data.get("stats", {"total": 0, "target": 100})
