"""Pydantic schemas for the FeedPilot catalog API.

Defines request and response shapes for GET /api/v1/catalog.
"""

from typing import Literal

from pydantic import BaseModel, Field


class CatalogProduct(BaseModel):
    """Single product row returned by the catalog endpoint."""

    sku_id: str
    title: str | None
    category: str | None
    brand: str | None
    price: float | None
    status: Literal["enriched", "needs_review", "return_risk"]
    overall_score: int | None
    return_risk: str | None
    enriched_at: str | None


class CatalogResponse(BaseModel):
    """Paginated catalog response."""

    total: int = Field(description="Total matching products.")
    page: int = Field(description="Current page (1-based).")
    page_size: int = Field(description="Products per page.")
    products: list[CatalogProduct]
