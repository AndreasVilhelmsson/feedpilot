"""Preflight estimation service for FeedPilot bulk enrichment.

Computes a deterministic cost/workload estimate for a bulk enrichment run
before any AI calls are made. No AI calls are triggered by this service.
"""

from typing import Any

from sqlalchemy.orm import Session

from app.models.product import Product
from app.repositories.product_repository import ProductRepository, get_product_repository
from app.schemas.canonical import CanonicalProduct
from app.schemas.enrich import PreflightResponse

# Estimation constants for claude-sonnet-4-* pricing.
# Values are intentionally conservative — actual cost depends on prompt length and output.
# Replace with observed averages from observability logs (FEED-066) once available.
ESTIMATED_INPUT_TOKENS_PER_PRODUCT: int = 1200
ESTIMATED_OUTPUT_TOKENS_PER_PRODUCT: int = 500
ESTIMATED_COST_PER_1K_INPUT_TOKENS_USD: float = 0.003
ESTIMATED_COST_PER_1K_OUTPUT_TOKENS_USD: float = 0.015

# Tool plan for first version — tools are backend-controlled, not prompt-driven.
_DEFAULT_TOOL_PLAN: dict[str, bool] = {
    "rag": True,
    "web_search": False,
    "image_analysis": False,
}

_KNOWN_ATTR_KEYS: frozenset[str] = frozenset(
    {"brand", "color", "material", "size", "size_system", "gender"}
)


def _product_to_canonical(product: Product) -> CanonicalProduct:
    """Convert a Product ORM instance to CanonicalProduct for field analysis."""
    attrs: dict[str, Any] = product.attributes or {}
    return CanonicalProduct(
        sku_id=product.sku_id,
        feed_source=product.feed_source or "unknown",
        detected_source=product.detected_source or "generic_csv",
        title=product.title,
        description=product.description,
        brand=attrs.get("brand"),
        category=product.category,
        price=product.price,
        color=attrs.get("color"),
        material=attrs.get("material"),
        size=attrs.get("size"),
        size_system=attrs.get("size_system"),
        gender=attrs.get("gender"),
        extra_attributes={
            k: str(v) for k, v in attrs.items() if k not in _KNOWN_ATTR_KEYS
        },
        raw_data=product.raw_data or {},
        quality_warnings=product.quality_warnings or [],
    )


class PreflightService:
    """Estimates cost and workload for a bulk enrichment run without AI calls."""

    def __init__(self, product_repo: ProductRepository) -> None:
        self._repo = product_repo

    def compute_preflight(self, limit: int, db: Session) -> PreflightResponse:
        """Compute a deterministic preflight estimate for bulk enrichment.

        Fetches candidate products, aggregates missing core fields,
        and calculates token/cost estimates using fixed constants.
        No AI calls are made.

        Args:
            limit: Maximum number of products to include in the estimate.
            db: Active database session.

        Returns:
            PreflightResponse with product count, field breakdown,
            token estimates, cost estimate and tool plan.
        """
        products = self._repo.get_unenriched(db, limit=limit)
        product_count = len(products)

        fields_to_enrich: dict[str, int] = {}
        for product in products:
            canonical = _product_to_canonical(product)
            for field in canonical.missing_core_fields():
                fields_to_enrich[field] = fields_to_enrich.get(field, 0) + 1

        estimated_input_tokens = product_count * ESTIMATED_INPUT_TOKENS_PER_PRODUCT
        estimated_output_tokens = product_count * ESTIMATED_OUTPUT_TOKENS_PER_PRODUCT
        estimated_cost_usd = round(
            (estimated_input_tokens / 1000 * ESTIMATED_COST_PER_1K_INPUT_TOKENS_USD)
            + (estimated_output_tokens / 1000 * ESTIMATED_COST_PER_1K_OUTPUT_TOKENS_USD),
            4,
        )

        return PreflightResponse(
            product_count=product_count,
            estimated_ai_calls=product_count,
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
            estimated_total_tokens=estimated_input_tokens + estimated_output_tokens,
            estimated_cost_usd=estimated_cost_usd,
            fields_to_enrich=fields_to_enrich,
            tool_plan=dict(_DEFAULT_TOOL_PLAN),
            requires_confirmation=True,
        )


def get_preflight_service() -> PreflightService:
    """Dependency injection factory for PreflightService."""
    return PreflightService(product_repo=get_product_repository())
