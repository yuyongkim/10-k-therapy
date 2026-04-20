from sqlalchemy import String, Float, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin


class FinancialTerm(Base, TimestampMixin):
    __tablename__ = "financial_terms"

    id: Mapped[int] = mapped_column(primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("license_contracts.id"))

    term_type: Mapped[str] = mapped_column(String(30))
    # upfront, royalty, milestone, minimum_annual, lump_sum

    amount: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(Text, default="USD")
    rate: Mapped[float | None] = mapped_column(Float)          # e.g. 3.5 for 3.5%
    rate_unit: Mapped[str | None] = mapped_column(Text)  # %, $/unit, etc.
    rate_basis: Mapped[str | None] = mapped_column(Text)# net_sales, gross_revenue
    description: Mapped[str | None] = mapped_column(Text)

    # Relationships
    contract = relationship("LicenseContract", back_populates="financial_terms")

    __table_args__ = (
        Index("idx_financial_contract", "contract_id"),
        Index("idx_financial_type", "term_type"),
    )
