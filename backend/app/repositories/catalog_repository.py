"""Catalog repository for FeedPilot.

Handles all database queries for the paginated, filterable product catalog.
Keeps the latest-AnalysisResult join, search/status filtering and pagination
out of the API layer.

Kept separate from product_repository.py because it crosses model boundaries
(Product × AnalysisResult) and has presentation-level concerns (status derivation,
CatalogProduct mapping) that belong together with the query that produces them.
"""

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.analysis_result import AnalysisResult
from app.models.product import Product
from app.schemas.catalog import CatalogProduct


class CatalogRepository:
    """Data access and row-mapping layer for the product catalog endpoint."""

    def get_page(
        self,
        db: Session,
        *,
        page: int,
        page_size: int,
        status_filter: str,
        search: str,
    ) -> tuple[int, list[CatalogProduct]]:
        """Return one page of catalog products with enrichment status.

        Joins each product with its most recent AnalysisResult to compute
        status and score. Supports free-text search and status filtering.

        Args:
            db: Active database session.
            page: 1-based page number.
            page_size: Number of products per page.
            status_filter: One of 'all', 'enriched', 'needs_review', 'return_risk'.
            search: Free-text search against title and sku_id (case-insensitive).

        Returns:
            A tuple of (total_matching, list_of_CatalogProduct_for_this_page).
        """
        # Subquery: latest AnalysisResult id per product
        latest_ar_sq = (
            db.query(
                AnalysisResult.product_id,
                func.max(AnalysisResult.id).label("latest_id"),
            )
            .group_by(AnalysisResult.product_id)
            .subquery()
        )

        # Base query: LEFT JOIN so un-enriched products are included
        query = (
            db.query(Product, AnalysisResult)
            .outerjoin(latest_ar_sq, Product.id == latest_ar_sq.c.product_id)
            .outerjoin(AnalysisResult, AnalysisResult.id == latest_ar_sq.c.latest_id)
        )

        # Search filter
        if search:
            term = f"%{search}%"
            query = query.filter(
                or_(
                    Product.title.ilike(term),
                    Product.sku_id.ilike(term),
                )
            )

        # Status filter
        if status_filter == "enriched":
            query = query.filter(
                AnalysisResult.id.isnot(None),
                AnalysisResult.return_risk != "high",
            )
        elif status_filter == "return_risk":
            query = query.filter(AnalysisResult.return_risk == "high")
        elif status_filter == "needs_review":
            query = query.filter(AnalysisResult.id.is_(None))

        total = query.count()
        rows = query.offset((page - 1) * page_size).limit(page_size).all()

        products = [
            CatalogProduct(
                sku_id=product.sku_id,
                title=product.title,
                category=product.category,
                brand=(product.attributes or {}).get("brand"),
                price=product.price,
                status=self._determine_status(ar),
                overall_score=ar.overall_score if ar else None,
                return_risk=ar.return_risk if ar else None,
                enriched_at=ar.created_at.isoformat() if ar else None,
            )
            for product, ar in rows
        ]

        return total, products

    @staticmethod
    def _determine_status(ar: AnalysisResult | None) -> str:
        """Derive enrichment status from the latest AnalysisResult.

        Args:
            ar: The most recent AnalysisResult for this product, or None.

        Returns:
            'return_risk' if return_risk is 'high',
            'enriched' if an analysis exists,
            'needs_review' if no analysis exists.
        """
        if ar is None:
            return "needs_review"
        if ar.return_risk == "high":
            return "return_risk"
        return "enriched"


def get_catalog_repository() -> CatalogRepository:
    """Dependency injection factory for CatalogRepository."""
    return CatalogRepository()
