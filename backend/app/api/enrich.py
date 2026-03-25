"""Enrich router for FeedPilot.

Note: json.JSONDecodeError is a subclass of ValueError. Both exception
handlers below must be ordered with JSONDecodeError first to avoid
routing parse failures as 404 Not Found.

Receives HTTP requests and delegates all logic to EnrichmentService.
No business logic lives here.

Routes:
    POST /enrich/bulk        — queue an async ARQ enrichment job (defined
                               first to prevent FastAPI matching 'bulk' as
                               sku_id)
    POST /enrich/{sku_id}    — enrich a single product by SKU
"""

import json
import uuid

from arq import create_pool
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.job import Job
from app.schemas.enrich import (
    BulkEnrichRequest,
    EnrichResponse,
)
from app.schemas.job import EnqueueResponse
from app.services.enrichment_service import EnrichmentService, get_enrichment_service
from app.workers.settings import get_redis_settings

router = APIRouter(
    prefix="/enrich",
    tags=["enrich"],
)


@router.post(
    "/bulk",
    response_model=EnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Köa asynkront bulk-enrichment",
    description=(
        "Skapar ett bakgrundsjobb som enrichar upp till `limit` produkter. "
        "Returnerar omedelbart med ett job_id. "
        "Följ progress på GET /api/v1/jobs/{job_id}."
    ),
)
async def enrich_bulk(
    request: BulkEnrichRequest,
    db: Session = Depends(get_db),
) -> EnqueueResponse:
    """Queue an async ARQ enrichment job and return a job_id.

    Args:
        request: Validated request body containing `limit`.
        db: Injected database session.

    Returns:
        EnqueueResponse with job_id and polling instructions.

    Raises:
        HTTPException: 500 if job creation or enqueueing fails.
    """
    try:
        job_id = str(uuid.uuid4())
        job = Job(
            id=job_id,
            job_type="enrich_bulk",
            status="queued",
            total=request.limit,
        )
        db.add(job)
        db.commit()

        redis = await create_pool(get_redis_settings())
        await redis.enqueue_job(
            "enrich_bulk_task",
            job_id=job_id,
            limit=request.limit,
        )
        await redis.aclose()

        return EnqueueResponse(
            job_id=job_id,
            status="queued",
            message=(
                f"Enrichment av upp till {request.limit} produkter köat. "
                f"Följ progress på /api/v1/jobs/{job_id}"
            ),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Kunde inte köa enrichment-jobb: {exc}",
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
