from sqlalchemy import String, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin


class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    country: Mapped[str] = mapped_column(String(2))  # US, KR
    name_en: Mapped[str] = mapped_column(String(500))
    name_local: Mapped[str | None] = mapped_column(String(500))

    # Country-specific identifiers
    cik: Mapped[str | None] = mapped_column(String(10))       # US SEC
    ticker: Mapped[str | None] = mapped_column(String(20))    # US stock
    corp_code: Mapped[str | None] = mapped_column(String(10)) # KR DART
    stock_code: Mapped[str | None] = mapped_column(String(10))# KR KRX

    industry_sector: Mapped[str | None] = mapped_column(String(200))

    # Relationships
    filings = relationship("Filing", back_populates="company")

    __table_args__ = (
        Index("idx_company_country_name", "country", "name_en"),
        Index("idx_company_cik", "cik", unique=True, postgresql_where="cik IS NOT NULL"),
        Index("idx_company_corp_code", "corp_code", unique=True, postgresql_where="corp_code IS NOT NULL"),
        CheckConstraint("country IN ('US', 'KR')", name="ck_company_country"),
    )
