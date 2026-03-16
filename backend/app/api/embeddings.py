"""Embeddings router for FeedPilot.

Handles triggering of product embedding generation.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.embedding_service import (
    EmbeddingService,
    get_embedding_service,
)

router = APIRouter(
    prefix="/embeddings",
    tags=["embeddings"],
)


@router.post(
    "/embed-all",
    status_code=status.HTTP_200_OK,
    summary="Skapa embeddings för alla produkter",
    description="Chunkar och embeddar alla produkter i databasen.",
)
async def embed_all(
    limit: int = 100,
    db: Session = Depends(get_db),
    service: EmbeddingService = Depends(get_embedding_service),
) -> dict:
    """Trigger embedding generation for all products.

    Args:
        limit: Max products to process.
        db: Injected database session.
        service: Injected EmbeddingService.

    Returns:
        Statistics with products_processed and chunks_created.

    Raises:
        HTTPException: 500 if embedding generation fails.
    """
    try:
        return service.embed_all_products(db=db, limit=limit)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Embedding misslyckades: {exc}",
        ) from exc