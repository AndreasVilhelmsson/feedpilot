"""Business logic for FeedPilot variant-level SEO enrichment.

Orchestrates the variant enrichment pipeline:
  1. Fetch variant + parent product from database
  2. Build Claude user message with EAN, variant and product context
  3. Call Claude with the v3_variant_seo prompt
  4. Parse and persist SEO fields back onto the variant
  5. Return a structured VariantEnrichResponse
"""

import json
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.ai import ask_claude
from app.models.product import Product
from app.models.variant import ProductVariant
from app.prompts.prompt_manager import get_prompt, get_version
from app.repositories.variant_repository import (
    VariantRepository,
    get_variant_repository,
)

PROMPT_NAME = "variant_seo_v3"
MAX_TOKENS = 2048


def _build_user_message(
    variant: ProductVariant, product: Product
) -> str:
    """Serialize variant and parent product data into the Claude user message.

    Args:
        variant: The ProductVariant ORM instance to enrich.
        product: The parent Product ORM instance.

    Returns:
        JSON string to pass as the Claude user message.
    """
    payload = {
        "variant": {
            "ean": variant.ean,
            "color": variant.color,
            "size": variant.size,
            "material": variant.material,
            "attributes": variant.attributes or {},
        },
        "product": {
            "sku_id": product.sku_id,
            "title": product.title,
            "description": product.description,
            "category": product.category,
            "price": product.price,
            "attributes": product.attributes or {},
        },
    }
    return json.dumps(payload, ensure_ascii=False)


def _extract_json(text: str) -> dict:
    """Extract and parse the first JSON object from model output.

    Locates the outermost JSON object (first { to last }) to handle
    any preamble or trailing text the model may include.

    Args:
        text: Raw model output string.

    Returns:
        Parsed dict from the JSON object.

    Raises:
        RuntimeError: If no JSON object boundary is found.
        json.JSONDecodeError: If the extracted text is not valid JSON.
    """
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise RuntimeError(
            f"Claude returnerade inget JSON-objekt. Svar: {text[:200]!r}"
        )
    json_str = text[start:end]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Rå radbrytningar och tabulatorer inuti JSON-strängar är ogiltiga
        # kontrollkaraktärer — ersätt dem med mellanslag och försök igen.
        cleaned = json_str.replace("\n", " ").replace("\r", " ").replace("\t", " ")
        return json.loads(cleaned)


class VariantEnrichmentService:
    """Orchestrates the AI SEO enrichment pipeline for product variants."""

    def __init__(self, variant_repo: VariantRepository) -> None:
        """Initialise the service with a variant repository.

        Args:
            variant_repo: Data-access layer for ProductVariant records.
        """
        self._repo = variant_repo

    def enrich_variant(self, variant_id: int, db: Session) -> dict:
        """Run the full SEO enrichment pipeline for a single variant.

        Fetches the variant and its parent product, calls Claude with
        the v3 SEO prompt, persists the generated copy and returns a
        structured response dict.

        Args:
            variant_id: Primary key of the variant to enrich.
            db: Active SQLAlchemy database session.

        Returns:
            Dict matching VariantEnrichResponse field names.

        Raises:
            ValueError: If no variant with the given ID exists, or if
                the parent product cannot be found.
            RuntimeError: If Claude returns an empty or non-JSON response.
            json.JSONDecodeError: If the extracted text is malformed JSON.
        """
        variant = self._repo.get_by_id(variant_id, db)
        if variant is None:
            raise ValueError(
                f"Variant med id={variant_id!r} hittades inte."
            )

        product: Product | None = (
            db.query(Product)
            .filter_by(id=variant.product_id)
            .first()
        )
        if product is None:
            raise ValueError(
                f"Förälderprodukten (product_id={variant.product_id}) "
                f"för variant id={variant_id} hittades inte."
            )

        user_message = _build_user_message(variant, product)
        ai_response = ask_claude(
            prompt=user_message,
            system=get_prompt(PROMPT_NAME),
            max_tokens=MAX_TOKENS,
        )

        parsed = _extract_json(ai_response["answer"])

        self._repo.save_seo(
            variant=variant,
            seo_title=parsed.get("seo_title"),
            seo_description=parsed.get("seo_description"),
            search_keywords=parsed.get("search_keywords"),
            ai_search_snippet=parsed.get("ai_search_snippet"),
            db=db,
        )
        db.commit()
        db.refresh(variant)

        return {
            "variant_id": variant.id,
            "ean": variant.ean,
            "seo_title": variant.seo_title,
            "seo_description": variant.seo_description,
            "search_keywords": variant.search_keywords,
            "ai_search_snippet": variant.ai_search_snippet,
            "confidence": parsed.get("confidence"),
            "reasoning": parsed.get("reasoning"),
            "prompt_version": get_version(PROMPT_NAME),
            "total_tokens": ai_response["total_tokens"],
        }

    def enrich_all_variants(
        self, db: Session, limit: int = 50
    ) -> dict:
        """Enrich all unenriched variants up to the given limit.

        Fetches variants where enriched_at IS NULL and processes them
        one at a time. Per-variant errors are captured without aborting
        the batch.

        Args:
            db: Active SQLAlchemy database session.
            limit: Maximum number of variants to process.

        Returns:
            Dict with keys 'processed', 'results' and 'errors'.
        """
        variants = self._repo.get_unenriched(db, limit=limit)
        results: list[dict] = []
        errors: list[dict] = []

        for variant in variants:
            try:
                result = self.enrich_variant(variant.id, db)
                results.append(result)
            except Exception as exc:  # noqa: BLE001
                errors.append({"variant_id": variant.id, "error": str(exc)})

        return {
            "processed": len(results),
            "results": results,
            "errors": errors,
        }


def get_variant_enrichment_service() -> VariantEnrichmentService:
    """Dependency injection factory for VariantEnrichmentService.

    Returns:
        A ready-to-use VariantEnrichmentService instance.
    """
    return VariantEnrichmentService(variant_repo=get_variant_repository())
