"""Ingest router for FeedPilot.

Handles product feed uploads and returns
ingestion statistics and data quality warnings.
"""

from fastapi import (
    APIRouter, Depends, HTTPException,
    UploadFile, File, status
)
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.ingestion_service import (
    IngestionService, get_ingestion_service
)
from app.schemas.product import IngestResponse

router = APIRouter(
    prefix="/ingest",
    tags=["ingest"],
)

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post(
    "/csv",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ladda upp en produktfeed som CSV",
    description=(
        "Parsear, mappar och normaliserar en CSV-feed "
        "och lagrar produkterna i databasen. "
        "Stöder Shopify, WooCommerce, Google Shopping, "
        "Akeneo och generisk CSV automatiskt."
    ),
)
async def ingest_csv(
    file: UploadFile = File(...),
    feed_source: str = "auto",
    db: Session = Depends(get_db),
    service: IngestionService = Depends(get_ingestion_service),
) -> IngestResponse:
    """Accept a CSV upload and ingest products into the database.

    Args:
        file: The uploaded CSV file.
        feed_source: Source system name or 'auto' for detection.
        db: Injected database session.
        service: Injected IngestionService.

    Returns:
        Ingestion statistics with quality warnings.

    Raises:
        HTTPException: 400 if file is too large or unreadable.
        HTTPException: 500 if ingestion fails unexpectedly.
    """
    contents = await file.read()

    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filen är för stor. Max 10 MB tillåtet.",
        )

    try:
        result = service.ingest_csv(
            contents=contents,
            feed_source=feed_source,
            db=db,
        )
        return IngestResponse(
            filename=file.filename or "unknown",
            feed_source=feed_source,
            **result,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion misslyckades: {exc}",
        ) from exc