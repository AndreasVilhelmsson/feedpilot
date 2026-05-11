"""Field metadata registry for FeedPilot enrichment.

Defines which canonical fields are enrichable by AI and which context
fields are needed to enrich each one. This is a product rule owned by
code — not by prompt text.

Usage:
    from app.services.field_metadata import FIELD_REGISTRY, get_field_meta

    meta = get_field_meta("description")
    # meta.context_fields -> ["title", "brand", "category", ...]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class FieldMeta:
    """Metadata for a single canonical product field.

    Attributes:
        name:          Field name as it appears in CanonicalProduct.
        is_enrichable: Whether AI can enrich this field.
        context_fields: Other canonical fields useful as context when
                        enriching this field. Used by payload_builder to
                        produce a minimal AI input dict.
        complexity:    Task complexity hint for the future model/tool
                       planner (FEED-065). Not used for decisions yet.
    """

    name: str
    is_enrichable: bool
    context_fields: list[str] = field(default_factory=list)
    complexity: Literal["low", "medium", "high"] = "low"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
# Keys are canonical field names (matching CanonicalProduct attributes).
# Only enrichable fields are listed here. Non-enrichable fields (sku_id,
# raw_data, quality_warnings, feed_source, …) are intentionally absent.

FIELD_REGISTRY: dict[str, FieldMeta] = {
    # --- Core fields (also tracked by CanonicalProduct.missing_core_fields) ---
    "title": FieldMeta(
        name="title",
        is_enrichable=True,
        context_fields=["brand", "category", "color", "material", "gender"],
        complexity="medium",
    ),
    "description": FieldMeta(
        name="description",
        is_enrichable=True,
        context_fields=["title", "brand", "category", "color", "material", "gender"],
        complexity="high",
    ),
    "brand": FieldMeta(
        name="brand",
        is_enrichable=True,
        context_fields=["title", "category", "extra_attributes"],
        complexity="low",
    ),
    "category": FieldMeta(
        name="category",
        is_enrichable=True,
        context_fields=["title", "brand", "description"],
        complexity="low",
    ),
    "color": FieldMeta(
        name="color",
        is_enrichable=True,
        context_fields=["title", "brand", "category", "extra_attributes"],
        complexity="low",
    ),
    "material": FieldMeta(
        name="material",
        is_enrichable=True,
        context_fields=["title", "brand", "category", "extra_attributes"],
        complexity="low",
    ),
    # --- Additional enrichable fields ---
    "gender": FieldMeta(
        name="gender",
        is_enrichable=True,
        context_fields=["title", "brand", "category", "extra_attributes"],
        complexity="low",
    ),
    "seo_title": FieldMeta(
        name="seo_title",
        is_enrichable=True,
        context_fields=["title", "description", "brand", "category", "color", "material"],
        complexity="medium",
    ),
    "seo_description": FieldMeta(
        name="seo_description",
        is_enrichable=True,
        context_fields=["title", "description", "brand", "category", "color", "material"],
        complexity="medium",
    ),
}


def get_field_meta(name: str) -> FieldMeta | None:
    """Return metadata for a canonical field, or None if not registered.

    Args:
        name: Canonical field name (e.g. "description", "brand").

    Returns:
        FieldMeta if the field is registered, otherwise None.
    """
    return FIELD_REGISTRY.get(name)
