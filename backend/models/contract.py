from sqlalchemy import (
    String, Integer, Float, Text, ForeignKey, Index, CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin


class LicenseContract(Base, TimestampMixin):
    __tablename__ = "license_contracts"

    id: Mapped[int] = mapped_column(primary_key=True)
    filing_id: Mapped[int | None] = mapped_column(ForeignKey("filings.id"))

    # Parties
    licensor_name: Mapped[str | None] = mapped_column(Text)
    licensee_name: Mapped[str | None] = mapped_column(Text)

    # Technology
    tech_name: Mapped[str | None] = mapped_column(Text)
    tech_category: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(Text)

    # Contract terms
    exclusivity: Mapped[str | None] = mapped_column(String(50))
    territory: Mapped[str | None] = mapped_column(Text)  # JSON array as text
    term_years: Mapped[float | None] = mapped_column(Float)

    # AI extraction metadata
    extraction_model: Mapped[str | None] = mapped_column(String(50))  # qwen, claude, gemini, hybrid
    confidence_score: Mapped[float | None] = mapped_column(Float)
    complexity_score: Mapped[int | None] = mapped_column(Integer)
    processing_cost_usd: Mapped[float | None] = mapped_column(Float, default=0)
    reasoning: Mapped[str | None] = mapped_column(Text)

    # Source tracking
    source_system: Mapped[str | None] = mapped_column(String(10))  # EDGAR, DART

    # Quality control
    quality_flag: Mapped[str | None] = mapped_column(String(20))  # clean, noise, duplicate, low_quality
    noise_reason: Mapped[str | None] = mapped_column(Text)  # why flagged as noise

    # Relationships
    filing = relationship("Filing", back_populates="contracts")
    financial_terms = relationship("FinancialTerm", back_populates="contract")

    __table_args__ = (
        Index("idx_contract_confidence", "confidence_score"),
        Index("idx_contract_category", "tech_category"),
        Index("idx_contract_model", "extraction_model"),
        Index("idx_contract_filing", "filing_id"),
        CheckConstraint("confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
                         name="ck_confidence_range"),
    )
