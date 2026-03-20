"""RAG service for FeedPilot.

Orchestrates retrieval augmented generation:
1. Semantic search for relevant product chunks
2. Context building with product data and quality signals
3. AI analysis with grounded context and reasoning
"""

from sqlalchemy.orm import Session
from app.repositories.product_repository import ProductRepository
from app.core.ai import ask_claude
from app.prompts.prompt_manager import get_prompt


class RAGService:
    """Retrieval Augmented Generation for product analysis."""

    def __init__(self, repository: ProductRepository) -> None:
        """Initialize with a product repository.

        Args:
            repository: Data access layer for products.
        """
        self._repository = repository

    def _build_context(self, chunks: list[dict]) -> str:
        """Build a structured context string from retrieved chunks.

        Deduplicates by SKU and includes quality warnings
        so Claude has full visibility of data quality.

        Args:
            chunks: List of retrieved product chunks.

        Returns:
            Formatted XML-tagged context string for Claude.
        """
        if not chunks:
            return "<products>Inga relevanta produkter hittades.</products>"

        seen_skus: set[str] = set()
        products: list[dict] = []

        for chunk in chunks:
            sku = chunk["sku_id"]
            if sku not in seen_skus:
                seen_skus.add(sku)
                products.append(chunk)

        parts: list[str] = []
        for product in products:
            warnings = product.get("quality_warnings") or []
            warning_text = (
                " | ".join(w.get("message", "") for w in warnings)
                if warnings
                else "Inga varningar"
            )
            attributes = product.get("attributes") or {}
            attr_text = " | ".join(
                f"{k}: {v}" for k, v in attributes.items() if v
            )

            parts.append(
                f"<product>\n"
                f"  <sku>{product['sku_id']}</sku>\n"
                f"  <title>{product['title']}</title>\n"
                f"  <category>{product['category']}</category>\n"
                f"  <price>{product['price']}</price>\n"
                f"  <attributes>{attr_text}</attributes>\n"
                f"  <quality_warnings>{warning_text}</quality_warnings>\n"
                f"  <relevance>{product['similarity']:.0%}</relevance>\n"
                f"</product>"
            )

        return f"<products>\n" + "\n\n".join(parts) + "\n</products>"

    def _build_unique_sources(
        self,
        chunks: list[dict],
    ) -> list[dict]:
        """Extract unique sources from retrieved chunks.

        Args:
            chunks: List of retrieved product chunks.

        Returns:
            Deduplicated list of source dicts.
        """
        seen: set[str] = set()
        sources: list[dict] = []

        for chunk in chunks:
            sku = chunk["sku_id"]
            if sku not in seen:
                seen.add(sku)
                sources.append({
                    "sku_id": sku,
                    "title": chunk["title"],
                    "similarity": chunk["similarity"],
                })

        return sources

    def query(
        self,
        question: str,
        db: Session,
        top_k: int = 5,
    ) -> dict:
        """Answer a question using retrieved product context.

        Args:
            question: The user's question about products.
            db: Active database session.
            top_k: Number of chunks to retrieve.

        Returns:
            Dict with answer, sources and token usage.

        Raises:
            anthropic.APIError: If the Claude API call fails.
        """
        chunks = self._repository.semantic_search(
            query=question,
            db=db,
            limit=top_k,
        )

        context = self._build_context(chunks)
        sources = self._build_unique_sources(chunks)

        augmented_prompt = f"""
<question>
{question}
</question>

{context}

<instructions>
Du är FeedPilot. Analysera produktkontexten ovan och svara på frågan.
Basera ditt svar ENBART på produktkontexten ovan.
Om frågan är generell — svara med en sammanfattning av alla produkter.
Om frågan gäller en specifik produkt — analysera den i detalj.
Returnera alltid ett strukturerat JSON-svar.
</instructions>
"""
 
        result = ask_claude(
            prompt=augmented_prompt,
            system=get_prompt("feedfixer_v1"),
        )

        return {
            "answer": result["answer"],
            "sources": sources,
            "chunks_retrieved": len(chunks),
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "total_tokens": result["total_tokens"],
        }


def get_rag_service() -> RAGService:
    """Dependency injection factory for RAGService.

    Returns:
        A ready-to-use RAGService instance.
    """
    return RAGService(repository=ProductRepository())