"""Business logic for FeedPilot product enrichment.

Orchestrates the full enrichment pipeline:
  1. Fetch product from database
  2. Convert to CanonicalProduct for structured access
  3. Retrieve RAG context via semantic search
  4. Call Claude with the v2 enrichment prompt
  5. Parse and persist the analysis result
  6. Return a structured enrichment response
"""

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.ai import ask_claude
from app.models.analysis_result import AnalysisResult
from app.models.product import Product
from app.prompts.prompt_manager import get_prompt, get_version
from app.repositories.product_repository import ProductRepository, get_product_repository
from app.schemas.canonical import CanonicalProduct
from app.schemas.enrich import EnrichmentAIOutput

PROMPT_NAME: str = "enrichment_v2"
RAG_CONTEXT_LIMIT: int = 3

# Max tokens per enrichment priority level.
# A full enrichment response (enriched_fields + issues + action_items) is
# typically 500-2000 tokens. Set a safe floor of 4096 for all priorities so
# the JSON is never truncated mid-object.
MAX_TOKENS_BY_PRIORITY: dict[str, int] = {
    "critical": 4096,
    "high": 4096,
    "medium": 4096,
    "low": 4096,
}


def _extract_json(text: str) -> dict:
    """Extract JSON from Claude response, handling markdown and truncation.

    Strategy:
    1. Strip markdown code fences if present.
    2. Try a direct json.loads() — covers the happy path.
    3. Use brace-depth scanning to locate the outermost complete {...} block,
       which is robust against leading/trailing prose.
    4. If no closing brace is found the response was truncated — raise a
       descriptive ValueError so the caller can log the exact cause.

    Args:
        text: Raw model output from ask_claude().

    Returns:
        Parsed JSON as a dict.

    Raises:
        ValueError: If the response is truncated or contains no JSON object.
    """
    text = text.strip()

    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    if text.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", text)
        stripped = re.sub(r"\s*```$", "", stripped).strip()
        if stripped:
            text = stripped

    # 1. Direct parse (fast path)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Brace-depth scan — find the outermost complete {...} block
    start = text.find("{")
    if start == -1:
        raise ValueError(
            f"Inget JSON-objekt hittades i Claude-svaret. "
            f"Svar ({len(text)} tecken): {text[:200]!r}"
        )

    depth = 0
    in_str = False
    esc = False
    end = -1

    for i, ch in enumerate(text[start:], start):
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if end == -1:
        raise ValueError(
            f"JSON trunkerat — inget avslutande '}}' hittades "
            f"(stop_reason=max_tokens?). "
            f"Svar ({len(text)} tecken): {text[:200]!r}"
        )

    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"JSON-parsfel trots komplett block: {exc}. "
            f"Block ({end - start} tecken): {text[start:start + 200]!r}"
        ) from exc


def _build_user_message(
    canonical: CanonicalProduct,
    rag_context: list[dict],
    missing_fields: list[str],
) -> str:
    """Serialise canonical product data and RAG context into the Claude user message.

    Args:
        canonical: CanonicalProduct representation of the product to enrich.
        rag_context: List of semantically similar products from RAG search.
        missing_fields: Core fields that are missing and should be enriched.

    Returns:
        JSON string to pass as the Claude user message.
    """
    payload: dict[str, Any] = {
        "product": {
            "sku_id": canonical.sku_id,
            "title": canonical.title,
            "description": canonical.description,
            "brand": canonical.brand,
            "category": canonical.category,
            "price": canonical.price,
            "color": canonical.color,
            "material": canonical.material,
            "size": canonical.size,
            "gender": canonical.gender,
            "attributes": canonical.extra_attributes,
        },
        "rag_context": [
            {
                "sku_id": ctx["sku_id"],
                "title": ctx["title"],
                "category": ctx["category"],
                "attributes": ctx["attributes"],
                "similarity": ctx["similarity"],
            }
            for ctx in rag_context
        ],
        "missing_fields": missing_fields,
        "enrichment_instruction": (
            f"Följande kärnfält saknas och ska enrichas: {missing_fields}"
        ),
    }
    return json.dumps(payload, ensure_ascii=False)


class EnrichmentService:
    """Orchestrates the AI enrichment pipeline for products."""

    def __init__(self, product_repo: ProductRepository) -> None:
        """Initialise the service with a product repository.

        Args:
            product_repo: Data-access layer for products and embeddings.
        """
        self._repo = product_repo

    def _product_to_canonical(self, product: Product) -> CanonicalProduct:
        """Convert a SQLAlchemy Product ORM instance to a CanonicalProduct.

        Structured sub-fields (brand, color, material, size, size_system,
        gender) are extracted from the product's attributes JSON column.

        Args:
            product: Product ORM instance from the database.

        Returns:
            CanonicalProduct with all available fields populated.
        """
        attrs: dict[str, Any] = product.attributes or {}
        known_attr_keys = {"brand", "color", "material", "size", "size_system", "gender"}

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
                k: str(v) for k, v in attrs.items() if k not in known_attr_keys
            },
            raw_data=product.raw_data or {},
            quality_warnings=product.quality_warnings or [],
        )

    def enrich_product(self, sku_id: str, db: Session) -> dict:
        """Run the full enrichment pipeline for a single product.

        Fetches the product, converts to canonical schema, retrieves RAG
        context, calls Claude, persists the result and returns a structured
        enrichment dict.

        Args:
            sku_id: The SKU identifier of the product to enrich.
            db: Active SQLAlchemy database session.

        Returns:
            Dict containing sku_id, analysis_id, overall_score,
            enriched_fields, issues, return_risk, action_items,
            prompt_version, total_tokens and enrichment_priority.

        Raises:
            ValueError: If no product with the given sku_id exists.
            RuntimeError: If Claude returns no JSON object.
            json.JSONDecodeError: If Claude returns malformed JSON.
            pydantic.ValidationError: If AI output fails schema validation.
        """
        product = self._repo.get_by_sku(sku_id, db)
        if product is None:
            raise ValueError(f"Produkt med sku_id '{sku_id}' hittades inte.")

        canonical = self._product_to_canonical(product)
        missing_fields = canonical.missing_core_fields()
        priority = canonical.enrichment_priority()
        max_tokens = MAX_TOKENS_BY_PRIORITY[priority]

        rag_query = " ".join(filter(None, [product.title, product.category]))
        rag_context = self._repo.semantic_search(
            query=rag_query,
            db=db,
            limit=RAG_CONTEXT_LIMIT,
        )

        user_message = _build_user_message(canonical, rag_context, missing_fields)
        ai_response = ask_claude(
            prompt=user_message,
            system=get_prompt(PROMPT_NAME),
            max_tokens=max_tokens,
        )

        raw_text = ai_response["answer"]
        if not raw_text or "{" not in raw_text:
            raise RuntimeError(
                f"Claude returnerade inget JSON-objekt. Svar: {raw_text[:200]!r}"
            )
        parsed: dict = _extract_json(raw_text)
        validated = EnrichmentAIOutput.model_validate(parsed)

        analysis = AnalysisResult(
            product_id=product.id,
            sku_id=sku_id,
            overall_score=validated.overall_score,
            issues=[i.model_dump() for i in validated.issues],
            enriched_fields={k: v.model_dump() for k, v in validated.enriched_fields.items()},
            return_risk=validated.return_risk,
            action_items=validated.action_items,
            prompt_version=get_version(PROMPT_NAME),
            total_tokens=ai_response["total_tokens"],
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)

        return {
            "sku_id": sku_id,
            "analysis_id": analysis.id,
            "overall_score": validated.overall_score,
            "enriched_fields": {k: v.model_dump() for k, v in validated.enriched_fields.items()},
            "issues": [i.model_dump() for i in validated.issues],
            "return_risk": validated.return_risk,
            "return_risk_reason": validated.return_risk_reason,
            "action_items": validated.action_items,
            "prompt_version": get_version(PROMPT_NAME),
            "total_tokens": ai_response["total_tokens"],
            "enrichment_priority": priority,
            "missing_fields": missing_fields,
        }

    def enrich_bulk(
        self,
        db: Session,
        limit: int = 10,
    ) -> dict:
        """Enrich all products up to the given limit.

        Iterates over products in insertion order. Errors on individual
        products are captured and reported without aborting the batch.

        Args:
            db: Active SQLAlchemy database session.
            limit: Maximum number of products to process.

        Returns:
            Dict with keys 'processed', 'results' and 'errors'.
        """
        products = self._repo.get_unenriched(db, limit=limit)
        results: list[dict] = []
        errors: list[dict] = []

        for product in products:
            try:
                result = self.enrich_product(product.sku_id, db)
                results.append(result)
            except Exception as exc:  # noqa: BLE001
                errors.append({"sku_id": product.sku_id, "error": str(exc)})

        return {
            "processed": len(results),
            "results": results,
            "errors": errors,
        }


def get_enrichment_service() -> EnrichmentService:
    """Dependency injection factory for EnrichmentService.

    Returns:
        A ready-to-use EnrichmentService instance.
    """
    return EnrichmentService(product_repo=get_product_repository())
