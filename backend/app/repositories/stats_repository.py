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
        """Return the number of products whose latest analysis is 'enriched'.

        Mirrors the catalog definition exactly: uses the most recent
        AnalysisResult per product, requires overall_score IS NOT NULL,
        and excludes return_risk='high' (those are counted separately).

        Args:
            db: Active database session.

        Returns:
            Count of products with a successful latest analysis that is
            not flagged as high return risk.
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
            .filter(
                AnalysisResult.overall_score.isnot(None),
                AnalysisResult.return_risk != "high",
            )
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


def get_stats_repository() -> StatsRepository:
    """Dependency injection factory for StatsRepository.

    Returns:
        A ready-to-use StatsRepository instance.
    """
    return StatsRepository()
