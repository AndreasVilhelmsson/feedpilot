"""Product repository for FeedPilot.

Handles all database queries for products and embeddings.
Separates data access from business logic.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, or_, text
from app.models.product import Product
from app.core.embeddings import create_embedding


class ProductRepository:
    """Data access layer for products and embeddings."""

    def get_by_sku(self, sku_id: str, db: Session) -> Product | None:
        """Return a product by SKU ID.

        Args:
            sku_id: The product SKU identifier.
            db: Active database session.

        Returns:
            Product instance or None if not found.
        """
        return db.query(Product).filter_by(sku_id=sku_id).first()

    def get_all(
        self,
        db: Session,
        limit: int = 100,
    ) -> list[Product]:
        """Return all products up to limit.

        Args:
            db: Active database session.
            limit: Maximum number of products to return.

        Returns:
            List of Product instances.
        """
        return db.query(Product).limit(limit).all()

    def get_unenriched(
        self,
        db: Session,
        limit: int = 100,
    ) -> list[Product]:
        """Return products that need enrichment.

        Includes products that:
        - have no AnalysisResult at all (status = needs_review), OR
        - whose latest AnalysisResult has return_risk = 'high'
          (status = return_risk — still needs attention).

        Uses the same latest-AR join pattern as the catalog so the
        definition of "unenriched" stays consistent across the app.

        Args:
            db: Active database session.
            limit: Maximum number of products to return.

        Returns:
            List of Product instances that need (re-)enrichment.
        """
        from app.models.analysis_result import AnalysisResult

        latest_ar_sq = (
            db.query(
                AnalysisResult.product_id,
                func.max(AnalysisResult.id).label("latest_id"),
            )
            .group_by(AnalysisResult.product_id)
            .subquery()
        )

        found = (
            db.query(Product)
            .outerjoin(latest_ar_sq, Product.id == latest_ar_sq.c.product_id)
            .outerjoin(AnalysisResult, AnalysisResult.id == latest_ar_sq.c.latest_id)
            .filter(
                or_(
                    AnalysisResult.id.is_(None),
                    AnalysisResult.return_risk == "high",
                )
            )
            .limit(limit)
            .all()
        )
        print(
            f"[get_unenriched] filter=needs_review+return_risk "
            f"limit={limit} found={len(found)}"
        )
        return found

    def semantic_search(
        self,
        query: str,
        db: Session,
        limit: int = 5,
        chunk_type: str | None = None,
    ) -> list[dict]:
        """Find the most semantically similar product chunks."""
        query_embedding = create_embedding(query)

        # Konvertera Python-lista till PostgreSQL vector-format
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        chunk_filter = ""
        if chunk_type:
            chunk_filter = f"AND pe.chunk_type = '{chunk_type}'"

        sql = text(f"""
            SELECT
                pe.sku_id,
                pe.chunk_text,
                pe.chunk_type,
                p.title,
                p.category,
                p.price,
                p.attributes,
                p.quality_warnings,
                1 - (pe.embedding <=> '{embedding_str}'::vector) AS similarity
            FROM product_embeddings pe
            JOIN products p ON p.id = pe.product_id
            WHERE 1=1 {chunk_filter}
            ORDER BY pe.embedding <=> '{embedding_str}'::vector
            LIMIT :limit
        """)

        result = db.execute(sql, {"limit": limit})

        return [
            {
                "sku_id": row.sku_id,
                "chunk_text": row.chunk_text,
                "chunk_type": row.chunk_type,
                "title": row.title,
                "category": row.category,
                "price": row.price,
                "attributes": row.attributes,
                "quality_warnings": row.quality_warnings,
                "similarity": round(float(row.similarity), 4),
            }
            for row in result
        ]


def get_product_repository() -> ProductRepository:
    """Dependency injection factory for ProductRepository."""
    return ProductRepository()