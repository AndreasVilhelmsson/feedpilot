"""Products router for FeedPilot.

Routes:
    GET  /products/{sku_id}        — full product detail with latest enrichment
    POST /products/{sku_id}/enrich — trigger AI enrichment for a single product
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.analysis_result import AnalysisResult
from app.models.product import Product
from app.schemas.product_detail import (
    EnrichmentDetail,
    EnrichResponse,
    ImageUrlRequest,
    ImageUrlResponse,
    IssueDetail,
    ProductDetailResponse,
)
from app.services.enrichment_service import get_enrichment_service

router = APIRouter(
    prefix="/products",
    tags=["products"],
)


def _get_product_or_404(sku_id: str, db: Session) -> Product:
    product = db.query(Product).filter(Product.sku_id == sku_id).first()
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produkt med sku_id '{sku_id}' hittades inte.",
        )
    return product


def _latest_analysis(product_id: int, db: Session) -> AnalysisResult | None:
    return (
        db.query(AnalysisResult)
        .filter(AnalysisResult.product_id == product_id)
        .order_by(AnalysisResult.id.desc())
        .first()
    )


@router.get(
    "/{sku_id}",
    response_model=ProductDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Hämta produktdetalj",
)
def get_product(sku_id: str, db: Session = Depends(get_db)) -> ProductDetailResponse:
    """Return full product detail with the latest enrichment result."""
    product = _get_product_or_404(sku_id, db)
    ar = _latest_analysis(product.id, db)

    attrs: dict = product.attributes or {}

    enriched_fields: list[EnrichmentDetail] = []
    if ar and ar.enriched_fields:
        for field, data in ar.enriched_fields.items():
            enriched_fields.append(
                EnrichmentDetail(
                    field=field,
                    suggested_value=str(data.get("suggested_value", "")),
                    reasoning=str(data.get("reasoning", "")),
                    confidence=float(data.get("confidence", 0.0)),
                )
            )

    issues: list[IssueDetail] = []
    if ar and ar.issues:
        for issue in ar.issues:
            issues.append(
                IssueDetail(
                    field=str(issue.get("field", "")),
                    severity=str(issue.get("severity", "low")),
                    problem=str(issue.get("problem", "")),
                    suggestion=str(issue.get("suggestion", "")),
                )
            )

    return ProductDetailResponse(
        sku_id=product.sku_id,
        title=product.title,
        description=product.description,
        category=product.category,
        brand=attrs.get("brand"),
        price=product.price,
        feed_source=product.feed_source,
        detected_source=product.detected_source,
        attributes=attrs,
        overall_score=ar.overall_score if ar else None,
        return_risk=ar.return_risk if ar else None,
        return_risk_reason=None,
        action_items=ar.action_items or [] if ar else [],
        issues=issues,
        enriched_fields=enriched_fields,
        enriched_at=ar.created_at.isoformat() if ar else None,
        prompt_version=ar.prompt_version if ar else None,
        total_tokens=ar.total_tokens if ar else None,
        image_url=product.image_url,
    )


@router.post(
    "/{sku_id}/enrich",
    response_model=EnrichResponse,
    status_code=status.HTTP_200_OK,
    summary="Berika en enskild produkt",
)
def enrich_product(
    sku_id: str,
    db: Session = Depends(get_db),
    service=Depends(get_enrichment_service),
) -> EnrichResponse:
    """Trigger AI enrichment for a single product and return the result."""
    _get_product_or_404(sku_id, db)
    try:
        result = service.enrich_product(sku_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Enrichment misslyckades: {exc}",
        ) from exc

    return EnrichResponse(
        sku_id=result["sku_id"],
        analysis_id=result["analysis_id"],
        overall_score=result.get("overall_score"),
        return_risk=result.get("return_risk"),
        enrichment_priority=result.get("enrichment_priority", "medium"),
        total_tokens=result.get("total_tokens"),
    )


@router.patch(
    "/{sku_id}/image",
    response_model=ImageUrlResponse,
    status_code=status.HTTP_200_OK,
    summary="Spara bild-URL för produkt",
)
def save_image_url(
    sku_id: str,
    body: ImageUrlRequest,
    db: Session = Depends(get_db),
) -> ImageUrlResponse:
    """Persist an image URL on the product record."""
    product = _get_product_or_404(sku_id, db)
    product.image_url = body.image_url
    db.commit()
    return ImageUrlResponse(sku_id=product.sku_id, image_url=product.image_url)
