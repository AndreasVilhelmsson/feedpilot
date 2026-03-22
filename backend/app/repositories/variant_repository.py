"""Variant repository for FeedPilot.

Handles all database queries for ProductVariant records.
Follows the same patterns as product_repository.py — all methods
receive the session as an explicit parameter so the caller
controls transaction boundaries.
"""

from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.variant import ProductVariant


class VariantRepository:
    """Data access layer for product variants."""

    def get_by_ean(self, ean: str, db: Session) -> ProductVariant | None:
        """Return a variant by its EAN-13 barcode.

        Args:
            ean: The 13-digit EAN barcode to look up.
            db: Active database session.

        Returns:
            ProductVariant instance or None if not found.
        """
        return db.query(ProductVariant).filter_by(ean=ean).first()

    def get_by_id(self, variant_id: int, db: Session) -> ProductVariant | None:
        """Return a variant by its primary key.

        Args:
            variant_id: Internal primary key of the variant.
            db: Active database session.

        Returns:
            ProductVariant instance or None if not found.
        """
        return db.query(ProductVariant).filter_by(id=variant_id).first()

    def get_by_product(
        self, product_id: int, db: Session
    ) -> list[ProductVariant]:
        """Return all variants belonging to a given parent product.

        Args:
            product_id: Primary key of the parent product.
            db: Active database session.

        Returns:
            List of ProductVariant instances, possibly empty.
        """
        return (
            db.query(ProductVariant)
            .filter_by(product_id=product_id)
            .all()
        )

    def upsert(self, data: dict, db: Session) -> tuple[ProductVariant, bool]:
        """Insert or update a variant keyed on product_id + color + size.

        If a variant with the given (product_id, color, size) combination
        already exists its mutable fields are updated in place. Otherwise
        a new row is inserted.

        Args:
            data: Dict containing at minimum 'product_id'. May include
                  sku_id, ean, color, size, material and attributes.
            db: Active database session. Caller must commit.

        Returns:
            Tuple of (ProductVariant, created) where created is True
            if a new row was inserted and False if an existing row
            was updated.
        """
        existing = (
            db.query(ProductVariant)
            .filter(
                and_(
                    ProductVariant.product_id == data["product_id"],
                    ProductVariant.color == data.get("color"),
                    ProductVariant.size == data.get("size"),
                )
            )
            .first()
        )

        mutable_fields = ("sku_id", "ean", "material", "attributes")

        if existing:
            for field in mutable_fields:
                if field in data and data[field] is not None:
                    setattr(existing, field, data[field])
            return existing, False

        variant = ProductVariant(
            product_id=data["product_id"],
            sku_id=data.get("sku_id"),
            ean=data.get("ean"),
            color=data.get("color"),
            size=data.get("size"),
            material=data.get("material"),
            attributes=data.get("attributes"),
        )
        db.add(variant)
        return variant, True

    def save_seo(
        self,
        variant: ProductVariant,
        seo_title: str | None,
        seo_description: str | None,
        search_keywords: list[str] | None,
        ai_search_snippet: str | None,
        db: Session,
    ) -> ProductVariant:
        """Persist AI-generated SEO fields onto an existing variant.

        Args:
            variant: The ProductVariant to update.
            seo_title: AI-generated SEO title string.
            seo_description: AI-generated SEO description.
            search_keywords: List of search keyword strings.
            ai_search_snippet: Short snippet for AI search engines.
            db: Active database session. Caller must commit.

        Returns:
            The updated ProductVariant instance.
        """
        variant.seo_title = seo_title
        variant.seo_description = seo_description
        variant.search_keywords = search_keywords
        variant.ai_search_snippet = ai_search_snippet
        variant.enriched_at = datetime.utcnow()
        return variant

    def get_unenriched(
        self, db: Session, limit: int = 50
    ) -> list[ProductVariant]:
        """Return variants that have not yet been enriched by AI.

        A variant is considered unenriched when enriched_at IS NULL.

        Args:
            db: Active database session.
            limit: Maximum number of variants to return.

        Returns:
            List of unenriched ProductVariant instances.
        """
        return (
            db.query(ProductVariant)
            .filter(ProductVariant.enriched_at.is_(None))
            .limit(limit)
            .all()
        )


def get_variant_repository() -> VariantRepository:
    """Dependency injection factory for VariantRepository.

    Returns:
        A ready-to-use VariantRepository instance.
    """
    return VariantRepository()
