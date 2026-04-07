"""Pydantic schemas for the FeedPilot product detail API.

Defines request and response shapes for:
    GET  /api/v1/products/{sku_id}
    POST /api/v1/products/{sku_id}/enrich
"""

from typing import Any

from pydantic import BaseModel


class EnrichmentDetail(BaseModel):
    """Per-field enrichment result from the latest AnalysisResult."""

    field: str
    suggested_value: str
    reasoning: str
    confidence: float


class IssueDetail(BaseModel):
    """A quality issue identified for a product field."""

    field: str
    severity: str
    problem: str
    suggestion: str


class ProductDetailResponse(BaseModel):
    """Full product detail including enrichment data."""

    sku_id: str
    title: str | None
    description: str | None
    category: str | None
    brand: str | None
    price: float | None
    feed_source: str | None
    detected_source: str | None
    attributes: dict[str, Any]

    # Latest enrichment result (None if never enriched)
    overall_score: int | None
    return_risk: str | None
    return_risk_reason: str | None
    action_items: list[str]
    issues: list[IssueDetail]
    enriched_fields: list[EnrichmentDetail]
    enriched_at: str | None
    prompt_version: str | None
    total_tokens: int | None
    image_url: str | None


class ApplyFieldsRequest(BaseModel):
    """Accepted enrichment fields to write back to the product.

    Top-level product columns (title, description, category) are written
    directly. All other keys are merged into the product's attributes JSON.
    """

    fields: dict[str, str]


class ApplyFieldsResponse(BaseModel):
    """Confirmation that enrichment fields were applied to the product."""

    sku_id: str
    updated_fields: list[str]


class ImageUrlRequest(BaseModel):
    """Request body for saving a product image URL."""

    image_url: str


class ImageUrlResponse(BaseModel):
    """Response after saving a product image URL."""

    sku_id: str
    image_url: str


class EnrichResponse(BaseModel):
    """Response from triggering a single-product enrichment."""

    sku_id: str
    analysis_id: int
    overall_score: int | None
    return_risk: str | None
    enrichment_priority: str
    total_tokens: int | None
