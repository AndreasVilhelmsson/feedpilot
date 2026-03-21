"""SQLAlchemy model for product enrichment analysis results.

Stores the output of each AI enrichment run — including per-field
reasoning, confidence scores and overall quality metrics — so that
results are auditable and can be tracked over time per product.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, JSON,
    DateTime, ForeignKey, Float,
)
from app.models.product import Base


class AnalysisResult(Base):
    """Persisted result from one enrichment analysis run.

    One row is created per enrich_product call. Historical runs
    are kept so quality trends can be measured over time.
    """

    __tablename__ = "analysis_results"

    id: int = Column(
        Integer, primary_key=True, autoincrement=True
    )
    product_id: int = Column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku_id: str = Column(
        String(255), nullable=False, index=True
    )
    overall_score: int = Column(
        Integer, nullable=True
    )
    issues: list = Column(
        JSON, nullable=True,
        comment="List of {field, severity, problem, suggestion} dicts",
    )
    enriched_fields: dict = Column(
        JSON, nullable=True,
        comment="Per-field {reasoning, confidence, suggested_value} dicts",
    )
    return_risk: str = Column(
        String(20), nullable=True,
        comment="high | medium | low",
    )
    action_items: list = Column(
        JSON, nullable=True,
        comment="Prioritised list of recommended actions",
    )
    prompt_version: str = Column(
        String(20), nullable=True,
        comment="Semantic version of the prompt used, e.g. '2.0.0'",
    )
    total_tokens: int = Column(
        Integer, nullable=True,
        comment="Sum of input + output tokens consumed by this run",
    )
    created_at: datetime = Column(
        DateTime, default=datetime.utcnow
    )

    def __repr__(self) -> str:
        """Return string representation for debugging."""
        return (
            f"<AnalysisResult id={self.id} "
            f"sku_id={self.sku_id!r} "
            f"score={self.overall_score}>"
        )
