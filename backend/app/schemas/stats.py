"""Pydantic schemas for the FeedPilot stats API.

Defines the response shape for GET /api/v1/stats.
"""

from pydantic import BaseModel, Field


class StatsResponse(BaseModel):
    """Catalog statistics returned by GET /api/v1/stats.

    Attributes:
        total_products: Total number of products in the catalog.
        enriched: Products with at least one successful AnalysisResult
            (overall_score IS NOT NULL).
        pending: Products with no AnalysisResult at all.
        failed: Products whose latest AnalysisResult has overall_score IS NULL
            (AI ran but returned no score — indicates a failed enrichment run).
        enrichment_rate: Percentage of total products that are enriched,
            rounded to one decimal place.
    """

    total_products: int = Field(description="Total products in catalog.")
    enriched: int = Field(description="Products with a successful analysis result.")
    pending: int = Field(description="Products not yet enriched.")
    failed: int = Field(description="Products whose latest enrichment run failed.")
    enrichment_rate: float = Field(
        description="enriched / total_products * 100, rounded to 1 decimal."
    )
