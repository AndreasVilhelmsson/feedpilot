"""Business logic for FeedPilot catalog statistics.

Orchestrates aggregate queries via StatsRepository and computes
derived metrics (enrichment_rate) before returning a StatsResponse.
"""

from sqlalchemy.orm import Session

from app.repositories.stats_repository import StatsRepository, get_stats_repository
from app.schemas.stats import StatsResponse


class StatsService:
    """Computes catalog-wide enrichment statistics."""

    def __init__(self, stats_repo: StatsRepository) -> None:
        """Initialise the service with a stats repository.

        Args:
            stats_repo: Data-access layer for aggregate stats queries.
        """
        self._repo = stats_repo

    def get_stats(self, db: Session) -> StatsResponse:
        """Fetch and compute catalog enrichment statistics.

        Runs four aggregate queries and derives enrichment_rate.
        A total_products of zero returns 0.0 for enrichment_rate
        to avoid ZeroDivisionError.

        Args:
            db: Active SQLAlchemy database session.

        Returns:
            StatsResponse with total, enriched, pending, failed
            and enrichment_rate fields populated.
        """
        total = self._repo.get_total_products(db)
        enriched = self._repo.get_enriched_count(db)
        pending = self._repo.get_pending_count(db)
        failed = self._repo.get_failed_count(db)

        enrichment_rate = round(enriched / total * 100, 1) if total > 0 else 0.0

        return StatsResponse(
            total_products=total,
            enriched=enriched,
            pending=pending,
            failed=failed,
            enrichment_rate=enrichment_rate,
        )


def get_stats_service() -> StatsService:
    """Dependency injection factory for StatsService.

    Returns:
        A ready-to-use StatsService instance.
    """
    return StatsService(stats_repo=get_stats_repository())
