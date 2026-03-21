"""Business logic for FeedPilot product enrichment.

Orchestrates the full enrichment pipeline:
  1. Fetch product from database
  2. Retrieve RAG context via semantic search
  3. Call Claude with the v2 enrichment prompt
  4. Parse and persist the analysis result
  5. Return a structured enrichment response
"""

import json
import re
from sqlalchemy.orm import Session

from app.core.ai import ask_claude
from app.models.analysis_result import AnalysisResult
from app.models.product import Product
from app.prompts.prompt_manager import get_prompt, get_version
from app.repositories.product_repository import ProductRepository, get_product_repository

PROMPT_NAME = "enrichment_v2"
RAG_CONTEXT_LIMIT = 3
MAX_TOKENS = 4096


def _strip_markdown(text: str) -> str:
    """Strip markdown code fences if the model returns them.

    Args:
        text: Raw model output.

    Returns:
        Clean JSON string without markdown wrapping.
    """
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _build_user_message(product: Product, rag_context: list[dict]) -> str:
    """Serialize product data and RAG context into the Claude user message.

    Args:
        product: The product ORM instance to enrich.
        rag_context: List of semantically similar products from RAG search.

    Returns:
        JSON-serializable string to pass as the Claude user message.
    """
    payload = {
        "product": {
            "sku_id": product.sku_id,
            "title": product.title,
            "description": product.description,
            "category": product.category,
            "price": product.price,
            "attributes": product.attributes or {},
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

    def enrich_product(self, sku_id: str, db: Session) -> dict:
        """Run the full enrichment pipeline for a single product.

        Fetches the product, retrieves RAG context, calls Claude,
        persists the result and returns a structured enrichment dict.

        Args:
            sku_id: The SKU identifier of the product to enrich.
            db: Active SQLAlchemy database session.

        Returns:
            Dict containing sku_id, analysis_id, overall_score,
            enriched_fields, issues, return_risk, action_items,
            prompt_version and total_tokens.

        Raises:
            ValueError: If no product with the given sku_id exists.
            json.JSONDecodeError: If Claude returns malformed JSON.
        """
        product = self._repo.get_by_sku(sku_id, db)
        if product is None:
            raise ValueError(f"Produkt med sku_id '{sku_id}' hittades inte.")

        rag_query = " ".join(
            filter(None, [product.title, product.category])
        )
        rag_context = self._repo.semantic_search(
            query=rag_query,
            db=db,
            limit=RAG_CONTEXT_LIMIT,
        )

        user_message = _build_user_message(product, rag_context)
        ai_response = ask_claude(
            prompt=user_message,
            system=get_prompt(PROMPT_NAME),
            max_tokens=MAX_TOKENS,
        )

        raw_text = ai_response["answer"]
        start = raw_text.find("{")
        end = raw_text.rfind("}") + 1
        if start == -1 or end == 0:
            raise RuntimeError(
                f"Claude returnerade inget JSON-objekt. Svar: {raw_text[:200]!r}"
            )
        parsed: dict = json.loads(raw_text[start:end])

        analysis = AnalysisResult(
            product_id=product.id,
            sku_id=sku_id,
            overall_score=parsed.get("overall_score"),
            issues=parsed.get("issues"),
            enriched_fields=parsed.get("enriched_fields"),
            return_risk=parsed.get("return_risk"),
            action_items=parsed.get("action_items"),
            prompt_version=get_version(PROMPT_NAME),
            total_tokens=ai_response["total_tokens"],
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)

        return {
            "sku_id": sku_id,
            "analysis_id": analysis.id,
            "overall_score": parsed.get("overall_score"),
            "enriched_fields": parsed.get("enriched_fields"),
            "issues": parsed.get("issues", []),
            "return_risk": parsed.get("return_risk"),
            "return_risk_reason": parsed.get("return_risk_reason"),
            "action_items": parsed.get("action_items", []),
            "prompt_version": get_version(PROMPT_NAME),
            "total_tokens": ai_response["total_tokens"],
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
        products = self._repo.get_all(db, limit=limit)
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
