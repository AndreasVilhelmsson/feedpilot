"""Pydantic schemas for the FeedPilot enrichment API.

Defines request and response shapes for POST /enrich/{sku_id}
and POST /enrich/bulk.
"""

from pydantic import BaseModel, Field


class EnrichedField(BaseModel):
    """Per-field enrichment result following the Reason-then-Score pattern."""

    reasoning: str = Field(
        ..., description="Claude's reasoning before assigning the confidence score."
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score for the suggested value (0.0–1.0)."
    )
    suggested_value: str | dict | None = Field(
        None, description="Proposed improved value, or null if no change is needed."
    )


class EnrichIssue(BaseModel):
    """A single data quality issue identified during enrichment."""

    field: str
    severity: str = Field(..., pattern="^(high|medium|low)$")
    problem: str
    suggestion: str


class EnrichResponse(BaseModel):
    """Response from a single product enrichment run."""

    sku_id: str
    analysis_id: int
    overall_score: int | None
    enriched_fields: dict[str, EnrichedField] | None
    issues: list[EnrichIssue]
    return_risk: str | None
    return_risk_reason: str | None
    action_items: list[str]
    prompt_version: str
    total_tokens: int


class BulkEnrichRequest(BaseModel):
    """Request body for bulk enrichment."""

    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of products to enrich in this batch.",
    )


class BulkEnrichError(BaseModel):
    """Describes a failed enrichment within a bulk run."""

    sku_id: str
    error: str


class BulkEnrichResponse(BaseModel):
    """Response from a bulk enrichment run."""

    processed: int
    results: list[EnrichResponse]
    errors: list[BulkEnrichError]
