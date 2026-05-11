"""Tests for FEED-065: Enrichment Planner contract.

Covers plan_enrichment() for all complexity levels, filtering, deduplication,
ordering, and determinism. No database, no AI calls.
"""

from app.services.enrichment_planner import DEFAULT_TEXT_MODEL, plan_enrichment
from app.services.field_metadata import FIELD_REGISTRY


# ---------------------------------------------------------------------------
# 1. Low complexity
# ---------------------------------------------------------------------------


def test_low_complexity_plan() -> None:
    plan = plan_enrichment(["brand"])

    assert plan.target_fields == ["brand"]
    assert plan.complexity == "low"
    assert plan.model_strategy == "cheap"
    assert plan.model == DEFAULT_TEXT_MODEL
    assert plan.use_rag is True
    assert plan.use_web_search is False
    assert plan.use_image_analysis is False


# ---------------------------------------------------------------------------
# 2. High complexity wins for mixed fields
# ---------------------------------------------------------------------------


def test_high_complexity_wins_for_mixed_fields() -> None:
    plan = plan_enrichment(["brand", "description"])

    assert "brand" in plan.target_fields
    assert "description" in plan.target_fields
    assert plan.complexity == "high"
    assert plan.model_strategy == "strong"
    assert plan.model == DEFAULT_TEXT_MODEL


# ---------------------------------------------------------------------------
# 3. Medium complexity
# ---------------------------------------------------------------------------


def test_medium_complexity_plan() -> None:
    plan = plan_enrichment(["title"])

    assert plan.target_fields == ["title"]
    assert plan.complexity == "medium"
    assert plan.model_strategy == "standard"
    assert plan.model == DEFAULT_TEXT_MODEL
    assert plan.use_rag is True


# ---------------------------------------------------------------------------
# 4. Unknown field is filtered silently
# ---------------------------------------------------------------------------


def test_unknown_field_is_filtered_silently() -> None:
    plan = plan_enrichment(["nonexistent_field"])

    assert plan.target_fields == []
    assert plan.complexity == "low"
    assert plan.use_rag is False
    assert plan.use_web_search is False
    assert plan.use_image_analysis is False


# ---------------------------------------------------------------------------
# 5. Empty missing_fields
# ---------------------------------------------------------------------------


def test_empty_missing_fields_returns_empty_low_plan() -> None:
    plan = plan_enrichment([])

    assert plan.target_fields == []
    assert plan.complexity == "low"
    assert plan.model_strategy == "cheap"
    assert plan.model == DEFAULT_TEXT_MODEL
    assert plan.use_rag is False


# ---------------------------------------------------------------------------
# 6. Determinism
# ---------------------------------------------------------------------------


def test_plan_is_deterministic() -> None:
    fields = ["brand", "color", "material"]
    plan_a = plan_enrichment(fields)
    plan_b = plan_enrichment(fields)

    assert plan_a.target_fields == plan_b.target_fields
    assert plan_a.complexity == plan_b.complexity
    assert plan_a.model_strategy == plan_b.model_strategy
    assert plan_a.model == plan_b.model
    assert plan_a.use_rag == plan_b.use_rag
    assert plan_a.use_web_search == plan_b.use_web_search
    assert plan_a.use_image_analysis == plan_b.use_image_analysis


# ---------------------------------------------------------------------------
# 7. All target_fields come from FIELD_REGISTRY with is_enrichable=True
# ---------------------------------------------------------------------------


def test_plan_uses_registry_fields_only() -> None:
    mixed = ["brand", "nonexistent_one", "color", "nonexistent_two", "material"]
    plan = plan_enrichment(mixed)

    for field_name in plan.target_fields:
        meta = FIELD_REGISTRY.get(field_name)
        assert meta is not None, f"{field_name!r} saknas i FIELD_REGISTRY"
        assert meta.is_enrichable is True, f"{field_name!r} har is_enrichable=False"


# ---------------------------------------------------------------------------
# 8. Deduplication preserves first-occurrence order
# ---------------------------------------------------------------------------


def test_duplicate_fields_are_deduplicated_preserving_order() -> None:
    plan = plan_enrichment(["brand", "description", "brand"])

    assert plan.target_fields == ["brand", "description"]
