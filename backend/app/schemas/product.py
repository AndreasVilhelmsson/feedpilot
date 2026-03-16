"""Pydantic schemas for product API contracts.

Separate from SQLAlchemy models in app/models/product.py.
Schemas define what goes in/out of the API.
Models define what goes in/out of the database.
"""

from typing import Any
from pydantic import BaseModel, Field


class ProductSchema(BaseModel):
    """Public product representation returned by the API."""

    sku_id: str
    title: str | None = None
    description: str | None = None
    category: str | None = None
    price: float | None = None
    attributes: dict[str, Any] | None = None
    feed_source: str | None = None
    detected_source: str | None = None

    model_config = {"from_attributes": True}


class IngestResponse(BaseModel):
    """Response from the ingest endpoint."""

    filename: str = Field(description="Name of the uploaded file.")
    feed_source: str = Field(description="Source system identifier.")
    detected_source: str = Field(description="Auto-detected source system.")
    total: int = Field(description="Total rows processed.")
    created: int = Field(description="New products created.")
    updated: int = Field(description="Existing products updated.")
    skipped: int = Field(description="Rows skipped due to missing SKU.")
    warnings: list[dict] = Field(
        default_factory=list,
        description="Data quality warnings per SKU.",
    )