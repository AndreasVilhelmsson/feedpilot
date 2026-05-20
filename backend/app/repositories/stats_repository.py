"""Stats repository for FeedPilot.

Provides aggregate queries across the Product and AnalysisResult tables.
Kept separate from product_repository.py because it crosses model boundaries
and has no CRUD responsibility.
"""

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.analysis_result import AnalysisResult
from app.models.product import Product


class StatsRepository:
    """Aggregate data access for catalog statistics."""

    def get_total_products(self, db: Session) -> int:
        """Return the total number of products in the catalog.

        Args:
            db: Active database session.

        Returns:
            Count of all rows in the products table.
        """
        return db.query(func.count(Product.id)).scalar() or 0

    def get_enriched_count(self, db: Session) -> int:
        """Return the number of products that have been through AI enrichment.

        A product is 'enriched' if its latest AnalysisResult has an
        overall_score — regardless of return_risk. return_risk='high' is
        an output of enrichment, not a sign that enrichment didn't happen.

        Args:
            db: Active database session.

        Returns:
            Count of products whose latest analysis has overall_score IS NOT NULL.
        """
        latest_subq = (
            db.query(
                AnalysisResult.product_id,
                func.max(AnalysisResult.id).label("latest_id"),
            )
            .group_by(AnalysisResult.product_id)
            .subquery()
        )
        return (
            db.query(func.count(AnalysisResult.product_id))
            .join(latest_subq, AnalysisResult.id == latest_subq.c.latest_id)
            .filter(AnalysisResult.overall_score.isnot(None))
            .scalar()
            or 0
        )

    def get_pending_count(self, db: Session) -> int:
        """Return the number of products with no AnalysisResult at all.

        Args:
            db: Active database session.

        Returns:
            Count of products that have zero rows in analysis_results.
        """
        enriched_subquery = (
            db.query(AnalysisResult.product_id)
            .distinct()
            .subquery()
        )
        return (
            db.query(func.count(Product.id))
            .filter(Product.id.notin_(enriched_subquery))
            .scalar()
            or 0
        )

    def get_failed_count(self, db: Session) -> int:
        """Return the number of products whose latest enrichment run failed.

        A failed run is defined as the most recent AnalysisResult for a
        product having overall_score IS NULL (the AI call completed but
        returned no parseable score).

        Args:
            db: Active database session.

        Returns:
            Count of products with a failed latest analysis.
        """
        # Subquery: latest analysis id per product
        latest_subq = (
            db.query(
                AnalysisResult.product_id,
                func.max(AnalysisResult.id).label("latest_id"),
            )
            .group_by(AnalysisResult.product_id)
            .subquery()
        )

        return (
            db.query(func.count(AnalysisResult.id))
            .join(
                latest_subq,
                AnalysisResult.id == latest_subq.c.latest_id,
            )
            .filter(AnalysisResult.overall_score.is_(None))
            .scalar()
            or 0
        )


    def get_return_risk_high_count(self, db: Session) -> int:
        """Return the number of products whose latest analysis has return_risk='high'.

        Args:
            db: Active database session.

        Returns:
            Count of products with high return risk in their latest analysis.
        """
        latest_subq = (
            db.query(
                AnalysisResult.product_id,
                func.max(AnalysisResult.id).label("latest_id"),
            )
            .group_by(AnalysisResult.product_id)
            .subquery()
        )
        return (
            db.query(func.count(AnalysisResult.product_id))
            .join(latest_subq, AnalysisResult.id == latest_subq.c.latest_id)
            .filter(AnalysisResult.return_risk == "high")
            .scalar()
            or 0
        )


    def get_avg_enrichment_score(self, db: Session) -> float | None:
        """Return the average overall_score across the latest AnalysisResult per product.

        Uses MAX(created_at) to identify the most recent run per product —
        the canonical timestamp for ordering in this model. Other methods in
        this file use MAX(id) for the same purpose; created_at is preferred
        here because it reflects when the analysis was performed, not insertion
        order, which matters if rows are ever back-filled or re-ordered.

        Only rows with overall_score IS NOT NULL are included; products whose
        latest run failed (score=None) do not contribute to the average.

        Args:
            db: Active database session.

        Returns:
            Average overall_score rounded to one decimal place, or None if no
            enriched products exist.
        """
        # Subquery: most recent analysis timestamp per product
        latest_subq = (
            db.query(
                AnalysisResult.product_id,
                func.max(AnalysisResult.created_at).label("latest_created_at"),
            )
            .group_by(AnalysisResult.product_id)
            .subquery()
        )
        result = (
            db.query(func.avg(AnalysisResult.overall_score))
            .join(
                latest_subq,
                (AnalysisResult.product_id == latest_subq.c.product_id)
                & (AnalysisResult.created_at == latest_subq.c.latest_created_at),
            )
            .filter(AnalysisResult.overall_score.isnot(None))
            .scalar()
        )
        return round(float(result), 1) if result is not None else None


def get_stats_repository() -> StatsRepository:
    """Dependency injection factory for StatsRepository.

    Returns:
        A ready-to-use StatsRepository instance.
    """
    return StatsRepository()
