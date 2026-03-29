"""Catalog router for FeedPilot.

Returns a paginated, filterable product list with enrichment status
derived from the latest AnalysisResult per product.

Routes:
    GET /catalog — paginated product catalog with status & score
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.analysis_result import AnalysisResult
from app.models.product import Product
from app.schemas.catalog import CatalogProduct, CatalogResponse

router = APIRouter(
    prefix="/catalog",
    tags=["catalog"],
)


def _determine_status(ar: AnalysisResult | None) -> str:
    """Derive enrichment status from the latest AnalysisResult.

    Args:
        ar: The most recent AnalysisResult for this product, or None.

    Returns:
        'return_risk' if return_risk is 'high',
        'enriched' if an analysis exists,
        'needs_review' if no analysis exists.
    """
    if ar is None:
        return "needs_review"
    if ar.return_risk == "high":
        return "return_risk"
    return "enriched"


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
    db: Session = Depends(get_db),
) -> CatalogResponse:
    """Return a paginated, filtered product catalog.

    Joins each product with its most recent AnalysisResult to compute
    status and score. Supports free-text search and status filtering.

    Args:
        page: 1-based page number.
        page_size: Number of products per page.
        status_filter: Enrichment status to filter by.
        search: Free-text search against title and sku_id.
        db: Injected database session.

    Returns:
        CatalogResponse with pagination metadata and product rows.

    Raises:
        HTTPException: 500 if the database query fails.
    """
    try:
        # Subquery: latest AnalysisResult id per product
        latest_ar_sq = (
            db.query(
                AnalysisResult.product_id,
                func.max(AnalysisResult.id).label("latest_id"),
            )
            .group_by(AnalysisResult.product_id)
            .subquery()
        )

        # Base query: LEFT JOIN so un-enriched products are included
        query = (
            db.query(Product, AnalysisResult)
            .outerjoin(latest_ar_sq, Product.id == latest_ar_sq.c.product_id)
            .outerjoin(AnalysisResult, AnalysisResult.id == latest_ar_sq.c.latest_id)
        )

        # Search filter
        if search:
            term = f"%{search}%"
            query = query.filter(
                or_(
                    Product.title.ilike(term),
                    Product.sku_id.ilike(term),
                )
            )

        # Status filter
        if status_filter == "enriched":
            query = query.filter(
                AnalysisResult.id.isnot(None),
                AnalysisResult.return_risk != "high",
            )
        elif status_filter == "return_risk":
            query = query.filter(AnalysisResult.return_risk == "high")
        elif status_filter == "needs_review":
            query = query.filter(AnalysisResult.id.is_(None))

        total = query.count()
        rows = query.offset((page - 1) * page_size).limit(page_size).all()

        products = [
            CatalogProduct(
                sku_id=product.sku_id,
                title=product.title,
                category=product.category,
                brand=(product.attributes or {}).get("brand"),
                price=product.price,
                status=_determine_status(ar),
                overall_score=ar.overall_score if ar else None,
                return_risk=ar.return_risk if ar else None,
                enriched_at=ar.created_at.isoformat() if ar else None,
            )
            for product, ar in rows
        ]

        return CatalogResponse(
            total=total,
            page=page,
            page_size=page_size,
            products=products,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Kunde inte hämta katalog: {exc}",
        ) from exc
