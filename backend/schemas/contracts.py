from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class FinancialTermOut(BaseModel):
    id: int
    term_type: str
    amount: Optional[float] = None
    currency: Optional[str] = None
    rate: Optional[float] = None
    rate_unit: Optional[str] = None
    rate_basis: Optional[str] = None
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class ContractOut(BaseModel):
    id: int
    licensor_name: Optional[str] = None
    licensee_name: Optional[str] = None
    tech_name: Optional[str] = None
    tech_category: Optional[str] = None
    industry: Optional[str] = None
    territory: Optional[str] = None
    term_years: Optional[float] = None
    confidence_score: Optional[float] = None
    extraction_model: Optional[str] = None
    source_system: Optional[str] = None

    # Denormalized for list view
    company_name: Optional[str] = None
    ticker: Optional[str] = None
    filing_year: Optional[int] = None
    accession_number: Optional[str] = None
    rcept_no: Optional[str] = None
    filing_date: Optional[date] = None
    source_url: Optional[str] = None
    royalty_rate: Optional[float] = None
    upfront_amount: Optional[float] = None

    model_config = {"from_attributes": True}


class ContractDetail(ContractOut):
    exclusivity: Optional[str] = None
    complexity_score: Optional[int] = None
    processing_cost_usd: Optional[float] = None
    reasoning: Optional[str] = None
    financial_terms: list[FinancialTermOut] = []
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class ContractListResponse(BaseModel):
    data: list[ContractOut]
    pagination: PaginationMeta


class StatsResponse(BaseModel):
    total_contracts: int
    total_companies: int
    both_financial_terms: int
    avg_royalty_rate: Optional[float]
    avg_confidence: Optional[float]
    by_model: dict[str, int]
    by_source: dict[str, int] = {}
    by_category: list[dict]
    by_year: list[dict]
    monthly_api_cost: float


class ComparisonRequest(BaseModel):
    tech_category: Optional[str] = None
    industry: Optional[str] = None
    territory: Optional[str] = None
    min_confidence: float = 0.6


class ComparisonResponse(BaseModel):
    comparable_count: int
    royalty_range: dict  # min, max, median, mean
    upfront_range: dict
    term_range: dict
    comparables: list[ContractOut]
