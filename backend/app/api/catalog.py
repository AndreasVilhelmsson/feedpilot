"""Catalog router for FeedPilot.

Returns a paginated, filterable product list with enrichment status
derived from the latest AnalysisResult per product.

Routes:
    GET /catalog — paginated product catalog with status & score
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.catalog_repository import CatalogRepository, get_catalog_repository
from app.schemas.catalog import CatalogResponse

router = APIRouter(
    prefix="/catalog",
    tags=["catalog"],
)


@router.get(
    "",
    response_model=CatalogResponse,
    status_code=status.HTTP_200_OK,
    summary="Hämta produktkatalog",
    description=(
        "Returnerar en paginerad produktlista med enrichment-status och score. "
        "Statusen bestäms av senaste AnalysisResult per produkt."
    ),
)
def get_catalog(
    page: int = Query(default=1, ge=1, description="Sidnummer (1-baserat)."),
    page_size: int = Query(default=10, ge=1, le=100, description="Produkter per sida."),
    status_filter: str = Query(
        default="all",
        alias="status",
        description="all | enriched | needs_review | return_risk",
    ),
    search: str = Query(default="", description="Fritextsökning på titel eller SKU."),
    repo: CatalogRepository = Depends(get_catalog_repository),
    db: Session = Depends(get_db),
) -> CatalogResponse:
    """Return a paginated, filtered product catalog.

    Delegates all database access and row mapping to CatalogRepository.

    Args:
        page: 1-based page number.
        page_size: Number of products per page.
        status_filter: Enrichment status to filter by.
        search: Free-text search against title and sku_id.
        repo: Injected CatalogRepository instance.
        db: Injected database session.

    Returns:
        CatalogResponse with pagination metadata and product rows.

    Raises:
        HTTPException: 500 if the database query fails.
    """
    try:
        total, products = repo.get_page(
            db,
            page=page,
            page_size=page_size,
            status_filter=status_filter,
            search=search,
        )
        return CatalogResponse(total=total, page=page, page_size=page_size, products=products)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Kunde inte hämta katalog: {exc}",
        ) from exc
