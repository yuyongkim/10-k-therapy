from sqlalchemy import String, Integer, Float, Index
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin


class AIProcessingLog(Base, TimestampMixin):
    __tablename__ = "ai_processing_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    filing_id: Mapped[str | None] = mapped_column(String(100))
    model_used: Mapped[str] = mapped_column(String(50))
    routing_decision: Mapped[str | None] = mapped_column(String(50))
    complexity_score: Mapped[int | None] = mapped_column(Integer)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    processing_time_sec: Mapped[float | None] = mapped_column(Float)
    input_tokens: Mapped[int | None] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int | None] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float | None] = mapped_column(Float, default=0)
    processing_path: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (
        Index("idx_ai_log_model", "model_used"),
        Index("idx_ai_log_created", "created_at"),
    )


class CostTracking(Base, TimestampMixin):
    __tablename__ = "cost_tracking"

    id: Mapped[int] = mapped_column(primary_key=True)
    month: Mapped[str] = mapped_column(String(7))  # YYYY-MM
    model: Mapped[str] = mapped_column(String(50))
    total_requests: Mapped[int] = mapped_column(Integer, default=0)
    total_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0)

    __table_args__ = (
        Index("idx_cost_month_model", "month", "model", unique=True),
    )
