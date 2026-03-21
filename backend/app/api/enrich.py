"""Enrich router for FeedPilot.

Note: json.JSONDecodeError is a subclass of ValueError. Both exception
handlers below must be ordered with JSONDecodeError first to avoid
routing parse failures as 404 Not Found.

Receives HTTP requests and delegates all logic to EnrichmentService.
No business logic lives here.

Routes:
    POST /enrich/bulk        — enrich a batch of products (defined first
                               to prevent FastAPI matching 'bulk' as sku_id)
    POST /enrich/{sku_id}    — enrich a single product by SKU
"""

import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.enrich import (
    BulkEnrichRequest,
    BulkEnrichResponse,
    EnrichResponse,
)
from app.services.enrichment_service import EnrichmentService, get_enrichment_service

router = APIRouter(
    prefix="/enrich",
    tags=["enrich"],
)


@router.post(
    "/bulk",
    response_model=BulkEnrichResponse,
    status_code=status.HTTP_200_OK,
    summary="Enricha flera produkter i ett batch-anrop",
    description=(
        "Kör enrichment-pipeline på upp till `limit` produkter. "
        "Fel på enskilda produkter samlas i `errors` utan att avbryta batchen."
    ),
)
def enrich_bulk(
    request: BulkEnrichRequest,
    service: EnrichmentService = Depends(get_enrichment_service),
    db: Session = Depends(get_db),
) -> BulkEnrichResponse:
    """Enrich a batch of products and return aggregated results.

    Args:
        request: Validated request body containing `limit`.
        service: Injected EnrichmentService instance.
        db: Injected database session.

    Returns:
        BulkEnrichResponse with processed count, results and errors.

    Raises:
        HTTPException: 500 if the batch call fails unexpectedly.
    """
    try:
        result = service.enrich_bulk(db=db, limit=request.limit)
        return BulkEnrichResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk enrichment misslyckades: {exc}",
        ) from exc


@router.post(
    "/{sku_id}",
    response_model=EnrichResponse,
    status_code=status.HTTP_200_OK,
    summary="Enricha en specifik produkt",
    description=(
        "Kör full enrichment-pipeline för produkten med givet SKU: "
        "RAG-sökning, Claude-analys och persistering av resultat."
    ),
)
def enrich_product(
    sku_id: str,
    service: EnrichmentService = Depends(get_enrichment_service),
    db: Session = Depends(get_db),
) -> EnrichResponse:
    """Enrich a single product and return the analysis result.

    Args:
        sku_id: The SKU identifier of the product to enrich.
        service: Injected EnrichmentService instance.
        db: Injected database session.

    Returns:
        EnrichResponse with per-field reasoning, scores and action items.

    Raises:
        HTTPException: 404 if no product with the given sku_id exists.
        HTTPException: 500 if the AI call or persistence fails.
    """
    try:
        result = service.enrich_product(sku_id=sku_id, db=db)
        return EnrichResponse(**result)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Claude returnerade ogiltig JSON: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Enrichment misslyckades: {exc}",
        ) from exc
