"""Canonical product schema for FeedPilot.

The single source of truth for product data in the system.
All source formats (CSV, Excel, JSON API) are converted to this
schema before enrichment, normalization, or persistence.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict


class CanonicalDimensions(BaseModel):
    """Physical product dimensions in centimetres and kilograms."""

    width: float | None = None
    depth: float | None = None
    height: float | None = None
    weight: float | None = None

    model_config = ConfigDict(str_strip_whitespace=True)


class CanonicalVariant(BaseModel):
    """A single product variant with size, colour and material."""

    ean: str | None = None
    color: str | None = None
    size: str | None = None
    size_system: str | None = None
    material: str | None = None
    attributes: dict[str, str] = {}

    model_config = ConfigDict(str_strip_whitespace=True)


class CanonicalProduct(BaseModel):
    """Canonical internal product representation.

    All connectors normalise their output to this schema before
    enrichment, validation, or persistence takes place.
    """

    # Identification
    sku_id: str
    feed_source: str = "unknown"
    detected_source: str = "generic_csv"

    # Core fields — always enriched
    title: str | None = None
    description: str | None = None
    brand: str | None = None
    category: str | None = None
    price: float | None = None
    currency: str = "SEK"

    # Physical attributes
    color: str | None = None
    material: str | None = None
    size: str | None = None
    size_system: str | None = None
    gender: str | None = None
    dimensions: CanonicalDimensions | None = None

    # EAN / barcode (top-level for single-variant products)
    ean: str | None = None

    # SEO
    seo_title: str | None = None
    seo_description: str | None = None
    search_keywords: list[str] = []

    # Variants
    variants: list[CanonicalVariant] = []

    # Unknown fields from the supplier
    extra_attributes: dict[str, str] = {}

    # Image
    image_url: str | None = None

    # Raw data — always preserve original
    raw_data: dict[str, Any] = {}

    # Quality
    quality_warnings: list[dict] = []

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    def missing_core_fields(self) -> list[str]:
        """Return list of missing core fields.

        Used by enrichment to determine what needs to be filled in.

        Returns:
            List of field names that are None or empty.
        """
        core = ["title", "description", "brand", "category", "color", "material"]
        return [f for f in core if not getattr(self, f)]

    def enrichment_priority(self) -> str:
        """Calculate enrichment priority based on missing core fields.

        Returns:
            Priority string: 'critical', 'high', 'medium', or 'low'.
        """
        missing = len(self.missing_core_fields())
        if missing >= 4:
            return "critical"
        elif missing >= 2:
            return "high"
        elif missing >= 1:
            return "medium"
        return "low"
