"""Stats router for FeedPilot.

Exposes aggregate catalog enrichment metrics.
No business logic lives here — all computation is
delegated to StatsService.

Routes:
    GET /stats — return catalog-wide enrichment statistics
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.stats import StatsResponse
from app.services.stats_service import StatsService, get_stats_service

router = APIRouter(
    prefix="/stats",
    tags=["stats"],
)


@router.get(
    "",
    response_model=StatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Hämta katalogstatistik",
    description=(
        "Returnerar aggregerade enrichment-mätvärden för hela katalogen: "
        "totalt antal produkter, antal enrichade, pending och misslyckade, "
        "samt enrichment-rate i procent."
    ),
)
def get_stats(
    db: Session = Depends(get_db),
    service: StatsService = Depends(get_stats_service),
) -> StatsResponse:
    """Return catalog-wide enrichment statistics.

    Args:
        db: Injected database session.
        service: Injected StatsService instance.

    Returns:
        StatsResponse with total_products, enriched, pending,
        failed and enrichment_rate.

    Raises:
        HTTPException: 500 if the database queries fail unexpectedly.
    """
    try:
        return service.get_stats(db=db)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Kunde inte hämta statistik: {exc}",
        ) from exc
