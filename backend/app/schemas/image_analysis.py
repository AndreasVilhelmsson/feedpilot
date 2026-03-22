"""Pydantic schemas for the FeedPilot image analysis API.

Covers URL-based and upload-based analysis requests and the
structured response containing detected attributes, quality
issues and enrichment suggestions.
"""

from pydantic import BaseModel, Field, HttpUrl


class SuggestedEnrichment(BaseModel):
    """A single data enrichment suggestion derived from image analysis."""

    field: str = Field(
        ..., description="Dot-notation field path in the product data, e.g. 'attributes.material'."
    )
    current_value: str | None = Field(
        None, description="The current value in the product data, or null if the field is absent."
    )
    suggested_value: str = Field(
        ..., description="The new value suggested based on what is visible in the image."
    )
    reasoning: str = Field(
        ..., description="Why the image justifies this specific change."
    )


class ImageAnalysisRequest(BaseModel):
    """Request body for URL-based image analysis."""

    url: HttpUrl = Field(
        ..., description="Publicly accessible URL of the product image to analyse."
    )
    sku_id: str = Field(
        ..., description="SKU of the product whose data should be enriched."
    )


class ImageAnalysisResponse(BaseModel):
    """Structured result from a single image analysis run."""

    sku_id: str
    detected_attributes: dict = Field(
        description="Key-value pairs of attributes Claude could identify in the image."
    )
    quality_issues: list[str] = Field(
        description="List of image quality problems from an e-commerce perspective."
    )
    suggested_enrichments: list[SuggestedEnrichment] = Field(
        description="Concrete enrichment suggestions backed by visual evidence."
    )
    image_quality_score: int = Field(
        ge=0, le=100,
        description="Overall image quality score on a 0-100 scale.",
    )
    overall_confidence: float = Field(
        ge=0.0, le=1.0,
        description="Claude's confidence in the analysis results (0.0–1.0).",
    )
    reasoning: str = Field(
        description="High-level explanation of the analysis and key findings."
    )
    total_tokens: int = Field(
        description="Total API tokens consumed by this analysis run."
    )
