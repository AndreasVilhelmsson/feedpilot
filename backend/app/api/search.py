"""Search and RAG router for FeedPilot.

Provides semantic search and RAG-powered Q&A
over the indexed product database.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.repositories.product_repository import (
    ProductRepository,
    get_product_repository,
)
from app.services.rag_service import RAGService, get_rag_service

router = APIRouter(
    prefix="/search",
    tags=["search"],
)


class SearchRequest(BaseModel):
    """Request body for semantic search."""

    query: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Natural language search query.",
        examples=["skor med hög returgrad"],
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of results to return.",
    )


class RAGRequest(BaseModel):
    """Request body for RAG-powered Q&A."""

    question: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Question about your product catalog.",
        examples=["Vilka produkter har dålig produktdata?"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of chunks to retrieve.",
    )


@router.post(
    "/semantic",
    status_code=status.HTTP_200_OK,
    summary="Semantisk produktsökning",
    description="Hitta produkter baserat på semantisk likhet utan AI-analys.",
)
async def semantic_search(
    request: SearchRequest,
    db: Session = Depends(get_db),
    repository: ProductRepository = Depends(get_product_repository),
) -> dict:
    """Search for products semantically.

    Args:
        request: Search query and limit.
        db: Injected database session.
        repository: Injected product repository.

    Returns:
        List of matching products with similarity scores.

    Raises:
        HTTPException: 500 if search fails.
    """
    try:
        results = repository.semantic_search(
            query=request.query,
            db=db,
            limit=request.limit,
        )
        return {
            "query": request.query,
            "results": results,
            "total": len(results),
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sökning misslyckades: {exc}",
        ) from exc


@router.post(
    "/ask",
    status_code=status.HTTP_200_OK,
    summary="Ställ en fråga om din produktkatalog",
    description=(
        "RAG-baserad Q&A — hämtar relevant produktdata "
        "semantiskt och ger Claude rätt kontext automatiskt. "
        "Svaret inkluderar källor och token-användning."
    ),
)
async def ask(
    request: RAGRequest,
    db: Session = Depends(get_db),
    service: RAGService = Depends(get_rag_service),
) -> dict:
    """Answer a question using RAG over the product catalog.

    Args:
        request: Question and retrieval parameters.
        db: Injected database session.
        service: Injected RAGService.

    Returns:
        AI answer with sources and token usage.

    Raises:
        HTTPException: 500 if RAG pipeline fails.
    """
    try:
        return service.query(
            question=request.question,
            db=db,
            top_k=request.top_k,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG-anropet misslyckades: {exc}",
        ) from exc