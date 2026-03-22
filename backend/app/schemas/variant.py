"""Pydantic schemas for product variants in FeedPilot.

Covers ingest (VariantCreateSchema), full representation (VariantSchema)
and enrichment responses (VariantEnrichResponse, BulkVariantEnrichResponse).
"""

from datetime import datetime
from pydantic import BaseModel, Field


class VariantCreateSchema(BaseModel):
    """Input schema for ingesting a single product variant.

    Uses `product_sku` to identify the parent product so callers
    do not need to know the internal product_id primary key.
    """

    product_sku: str = Field(
        ..., description="SKU of the parent product (matches products.sku_id)."
    )
    sku_id: str | None = Field(
        None, description="Variant-level SKU in the source system, if any."
    )
    ean: str | None = Field(
        None,
        min_length=13,
        max_length=13,
        description="EAN-13 barcode for this variant.",
    )
    color: str | None = Field(None, description="Colour name as shown to the customer.")
    size: str | None = Field(None, description="Size label, e.g. '42', 'M', 'One size'.")
    material: str | None = Field(None, description="Primary material, e.g. 'Läder'.")
    attributes: dict | None = Field(
        None, description="Additional variant-specific key-value attributes."
    )


class VariantSchema(BaseModel):
    """Full database representation of a product variant."""

    id: int
    product_id: int
    sku_id: str | None
    ean: str | None
    color: str | None
    size: str | None
    material: str | None
    attributes: dict | None
    seo_title: str | None
    seo_description: str | None
    search_keywords: list[str] | None
    ai_search_snippet: str | None
    enriched_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class VariantIngestResponse(BaseModel):
    """Summary returned after a bulk variant ingest operation."""

    created: int = Field(description="Number of new variants inserted.")
    updated: int = Field(description="Number of existing variants updated.")
    total: int = Field(description="Total variants processed.")


class VariantEnrichResponse(BaseModel):
    """Enrichment result for a single product variant."""

    variant_id: int
    ean: str | None
    seo_title: str | None
    seo_description: str | None
    search_keywords: list[str] | None
    ai_search_snippet: str | None
    confidence: float | None = Field(
        None, ge=0.0, le=1.0,
        description="Claude's overall confidence in the SEO copy (0.0–1.0).",
    )
    reasoning: str | None = Field(
        None, description="Brief explanation of the SEO choices made by Claude."
    )
    prompt_version: str
    total_tokens: int


class BulkVariantEnrichResponse(BaseModel):
    """Aggregated result from enriching multiple variants in one batch."""

    processed: int = Field(description="Number of variants successfully enriched.")
    results: list[VariantEnrichResponse]
    errors: list[dict] = Field(
        description="List of {variant_id, error} dicts for failed variants."
    )
