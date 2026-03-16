"""Business logic for product chunking and embedding.

Splits products into semantic chunks and creates
vector embeddings for each chunk.
"""

from typing import Any
from sqlalchemy.orm import Session
from app.core.embeddings import create_embedding
from app.models.product import Product
from app.models.embedding import ProductEmbedding


def chunk_product(product: Product) -> list[dict[str, Any]]:
    """Split a product into semantic chunks for embedding.

    Each chunk represents a meaningful unit of product
    information — title, description, attributes etc.

    Args:
        product: A Product instance from the database.

    Returns:
        List of chunk dicts with text and chunk_type.
    """
    chunks: list[dict[str, Any]] = []

    if product.title:
        chunks.append({
            "text": f"Produkttitel: {product.title}",
            "chunk_type": "title",
        })

    if product.description:
        chunks.append({
            "text": f"Beskrivning: {product.description}",
            "chunk_type": "description",
        })

    if product.category:
        chunks.append({
            "text": f"Kategori: {product.category}",
            "chunk_type": "category",
        })

    if product.attributes:
        attrs_text = " | ".join(
            f"{k}: {v}"
            for k, v in product.attributes.items()
            if v
        )
        if attrs_text:
            chunks.append({
                "text": f"Attribut: {attrs_text}",
                "chunk_type": "attributes",
            })

    full_text_parts = [
        product.title or "",
        product.description or "",
        product.category or "",
    ]
    full_text = " ".join(p for p in full_text_parts if p)
    if full_text:
        chunks.append({
            "text": full_text,
            "chunk_type": "full",
        })

    return chunks


class EmbeddingService:
    """Handles chunking and embedding for products."""

    def embed_product(
        self,
        product: Product,
        db: Session,
    ) -> dict[str, int]:
        """Create embeddings for all chunks of a product.

        Deletes existing embeddings before creating new ones
        to ensure idempotency.

        Args:
            product: The product to embed.
            db: Active database session.

        Returns:
            Dict with chunks_created count.
        """
        db.query(ProductEmbedding).filter_by(
            product_id=product.id
        ).delete()

        chunks = chunk_product(product)

        for i, chunk in enumerate(chunks):
            embedding_vector = create_embedding(chunk["text"])
            db.add(ProductEmbedding(
                product_id=product.id,
                sku_id=product.sku_id,
                chunk_index=i,
                chunk_text=chunk["text"],
                chunk_type=chunk["chunk_type"],
                embedding=embedding_vector,
            ))

        db.commit()
        return {"chunks_created": len(chunks)}

    def embed_all_products(
        self,
        db: Session,
        limit: int = 100,
    ) -> dict[str, int]:
        """Create embeddings for all products in the database.

        Args:
            db: Active database session.
            limit: Max products to process in one call.

        Returns:
            Dict with products_processed and chunks_created.
        """
        products = db.query(Product).limit(limit).all()
        total_chunks = 0

        for product in products:
            result = self.embed_product(product, db)
            total_chunks += result["chunks_created"]

        return {
            "products_processed": len(products),
            "chunks_created": total_chunks,
        }


def get_embedding_service() -> EmbeddingService:
    """Dependency injection factory for EmbeddingService.

    Returns:
        A ready-to-use EmbeddingService instance.
    """
    return EmbeddingService()