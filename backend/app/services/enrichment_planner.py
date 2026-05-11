"""Deterministic enrichment planner for FeedPilot.

Decides model strategy, RAG usage, and tool flags for a single enrichment
task based on missing_fields and FIELD_REGISTRY. No AI calls are made here.

Usage:
    from app.services.enrichment_planner import plan_enrichment

    plan = plan_enrichment(["brand", "description"])
    # plan.complexity      -> "high"
    # plan.model_strategy  -> "strong"
    # plan.use_rag         -> True
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.field_metadata import FIELD_REGISTRY

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

Complexity = Literal["low", "medium", "high"]
ModelStrategy = Literal["cheap", "standard", "strong"]

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

DEFAULT_TEXT_MODEL: str = "claude-sonnet-4-6"

_COMPLEXITY_RANK: dict[str, int] = {"low": 0, "medium": 1, "high": 2}

_STRATEGY_BY_COMPLEXITY: dict[Complexity, ModelStrategy] = {
    "low": "cheap",
    "medium": "standard",
    "high": "strong",
}


# ---------------------------------------------------------------------------
# EnrichmentPlan
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EnrichmentPlan:
    """Immutable enrichment plan for a single task.

    Produced by plan_enrichment() and consumed by the enrichment pipeline.
    All fields are derived from FIELD_REGISTRY — never from prompt text.

    Attributes:
        target_fields:     Enrichable fields from missing_fields, in original
                           order, deduplicated.
        complexity:        Worst-case complexity across target_fields.
        model_strategy:    Abstract strategy tier ("cheap" / "standard" /
                           "strong") for future model routing.
        model:             Concrete model ID to pass to ask_claude().
        use_rag:           Whether to fetch and include RAG context.
        use_web_search:    Reserved for future use; always False in this pass.
        use_image_analysis: Reserved for future use; always False in this pass.
    """

    target_fields: list[str]
    complexity: Complexity
    model_strategy: ModelStrategy
    model: str
    use_rag: bool
    use_web_search: bool
    use_image_analysis: bool


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def plan_enrichment(missing_fields: list[str]) -> EnrichmentPlan:
    """Build a deterministic enrichment plan from a list of missing fields.

    Fields not present in FIELD_REGISTRY or with is_enrichable=False are
    silently ignored. Duplicate field names are deduplicated while preserving
    the order of the first occurrence.

    Args:
        missing_fields: Canonical field names that need to be enriched.

    Returns:
        EnrichmentPlan with complexity, model strategy, and tool flags.
    """
    seen: set[str] = set()
    target_fields: list[str] = []
    for field_name in missing_fields:
        if field_name in seen:
            continue
        meta = FIELD_REGISTRY.get(field_name)
        if meta is not None and meta.is_enrichable:
            target_fields.append(field_name)
            seen.add(field_name)

    if not target_fields:
        return EnrichmentPlan(
            target_fields=[],
            complexity="low",
            model_strategy="cheap",
            model=DEFAULT_TEXT_MODEL,
            use_rag=False,
            use_web_search=False,
            use_image_analysis=False,
        )

    complexity: Complexity = max(
        (FIELD_REGISTRY[f].complexity for f in target_fields),
        key=lambda c: _COMPLEXITY_RANK[c],
    )

    return EnrichmentPlan(
        target_fields=target_fields,
        complexity=complexity,
        model_strategy=_STRATEGY_BY_COMPLEXITY[complexity],
        model=DEFAULT_TEXT_MODEL,
        use_rag=True,
        use_web_search=False,
        use_image_analysis=False,
    )
