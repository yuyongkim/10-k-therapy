from datetime import date
from sqlalchemy import String, Integer, Date, ForeignKey, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin


class Filing(Base, TimestampMixin):
    __tablename__ = "filings"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    source_system: Mapped[str] = mapped_column(String(10))  # EDGAR, DART

    # External identifiers
    accession_number: Mapped[str | None] = mapped_column(String(50))  # SEC
    rcept_no: Mapped[str | None] = mapped_column(String(20))          # DART

    filing_type: Mapped[str | None] = mapped_column(String(20))  # 10-K, 사업보고서
    report_type: Mapped[str | None] = mapped_column(String(20))  # ANNUAL, INTERIM
    filing_date: Mapped[date | None] = mapped_column(Date)
    fiscal_year: Mapped[int | None] = mapped_column(Integer)

    # Relationships
    company = relationship("Company", back_populates="filings")
    contracts = relationship("LicenseContract", back_populates="filing")

    __table_args__ = (
        Index("idx_filing_company_date", "company_id", "filing_date"),
        Index("idx_filing_accession", "accession_number", unique=True,
              postgresql_where="accession_number IS NOT NULL"),
        Index("idx_filing_rcept", "rcept_no", unique=True,
              postgresql_where="rcept_no IS NOT NULL"),
        CheckConstraint("source_system IN ('EDGAR', 'DART')", name="ck_filing_source"),
    )
