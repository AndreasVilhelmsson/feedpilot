"""Pydantic schemas for the FeedPilot enrichment API.

Defines request and response shapes for POST /enrich/{sku_id}
and POST /enrich/bulk, plus the internal AI output validation model.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


class EnrichmentAIOutput(BaseModel):
    """Internal validation model for raw AI enrichment output.

    Applied between _extract_json() and AnalysisResult persistence.
    Rejects structurally invalid output before anything is written to DB.
    """

    model_config = ConfigDict(extra="ignore")

    overall_score: int | None = Field(None, ge=0, le=100)
    enriched_fields: dict[str, EnrichedField] = Field(default_factory=dict)
    issues: list[EnrichIssue] = Field(default_factory=list)
    return_risk: Literal["high", "medium", "low"] | None = None
    return_risk_reason: str | None = None
    action_items: list[str] = Field(default_factory=list)


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


class PreflightRequest(BaseModel):
    """Request body for bulk enrichment preflight."""

    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of products to include in the preflight estimate.",
    )


class PreflightResponse(BaseModel):
    """Preflight estimate for a bulk enrichment run.

    All token and cost fields are estimates based on fixed constants.
    Actual values will differ once jobs execute.
    """

    product_count: int
    estimated_ai_calls: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_total_tokens: int
    estimated_cost_usd: float
    fields_to_enrich: dict[str, int]
    tool_plan: dict[str, bool]
    requires_confirmation: bool
