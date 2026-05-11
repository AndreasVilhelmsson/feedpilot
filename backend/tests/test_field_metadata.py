"""Tests for FEED-064: Field Metadata and Minimal AI Payload.

Covers FIELD_REGISTRY contents and build_enrichment_payload() behaviour.
No database, no AI calls, no enrichment_service imports.
"""

from unittest.mock import patch

from app.schemas.canonical import CanonicalProduct
from app.services.field_metadata import FIELD_REGISTRY, get_field_meta
from app.services.payload_builder import build_enrichment_payload

_REQUIRED_FIELDS = ["title", "description", "brand", "category", "color", "material"]

_CANONICAL_TO_PAYLOAD_KEY = {"extra_attributes": "attributes"}


def _payload_key(canonical_field: str) -> str:
    return _CANONICAL_TO_PAYLOAD_KEY.get(canonical_field, canonical_field)


def _make_canonical(**overrides) -> CanonicalProduct:
    defaults = dict(
        sku_id="TEST-001",
        title="Blue Running Shoe",
        description="A comfortable running shoe.",
        brand="Nike",
        category="Shoes",
        price=799.0,
        color="blue",
        material="mesh",
        gender="unisex",
        extra_attributes={"waterproof": "yes", "sole": "rubber"},
    )
    defaults.update(overrides)
    return CanonicalProduct(**defaults)


# ---------------------------------------------------------------------------
# 1. Registry contents
# ---------------------------------------------------------------------------


def test_registry_contains_required_fields() -> None:
    for field_name in _REQUIRED_FIELDS:
        assert field_name in FIELD_REGISTRY, f"{field_name!r} saknas i FIELD_REGISTRY"
        meta = FIELD_REGISTRY[field_name]
        assert meta.is_enrichable is True, f"{field_name!r} har is_enrichable=False"


def test_get_field_meta_returns_registered_metadata_or_none() -> None:
    meta = get_field_meta("brand")

    assert meta is not None
    assert meta.name == "brand"
    assert get_field_meta("nonexistent_field") is None


# ---------------------------------------------------------------------------
# 2. Irrelevant fields excluded for single missing field
# ---------------------------------------------------------------------------


def test_payload_excludes_irrelevant_fields_for_brand() -> None:
    canonical = _make_canonical()
    payload = build_enrichment_payload(canonical, ["brand"], [])
    product = payload["product"]

    brand_context = FIELD_REGISTRY["brand"].context_fields
    expected_keys = {"sku_id"} | {_payload_key(f) for f in brand_context}

    assert set(product.keys()) == expected_keys

    if "extra_attributes" in brand_context:
        assert "attributes" in product
        assert "extra_attributes" not in product

    assert "description" not in product
    assert "price" not in product


# ---------------------------------------------------------------------------
# 3. Union of context_fields for multiple missing fields
# ---------------------------------------------------------------------------


def test_payload_union_for_multiple_missing_fields() -> None:
    canonical = _make_canonical()
    payload = build_enrichment_payload(canonical, ["brand", "color"], [])
    product = payload["product"]

    brand_ctx = set(FIELD_REGISTRY["brand"].context_fields)
    color_ctx = set(FIELD_REGISTRY["color"].context_fields)
    union_canonical = brand_ctx | color_ctx
    expected_keys = {"sku_id"} | {_payload_key(f) for f in union_canonical}

    assert set(product.keys()) == expected_keys


# ---------------------------------------------------------------------------
# 4. sku_id always present
# ---------------------------------------------------------------------------


def test_sku_id_always_present_for_unknown_missing_field() -> None:
    canonical = _make_canonical()
    payload = build_enrichment_payload(canonical, ["nonexistent_field"], [])
    assert "sku_id" in payload["product"]
    assert payload["product"]["sku_id"] == "TEST-001"


def test_sku_id_always_present_with_empty_missing_fields() -> None:
    canonical = _make_canonical()
    payload = build_enrichment_payload(canonical, [], [])
    assert "sku_id" in payload["product"]


# ---------------------------------------------------------------------------
# 5. No AI calls
# ---------------------------------------------------------------------------


def test_no_ai_calls_in_payload_builder() -> None:
    canonical = _make_canonical()
    with patch(
        "app.core.ai.ask_claude",
        side_effect=AssertionError("ask_claude ska inte anropas av payload_builder"),
    ):
        payload = build_enrichment_payload(canonical, ["brand", "color"], [])

    assert "product" in payload
    assert "missing_fields" in payload
