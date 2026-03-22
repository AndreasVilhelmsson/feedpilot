"""SQLAlchemy model for product variants in FeedPilot.

Each parent Product can have multiple ProductVariants representing
concrete purchasable items — differentiated by color, size and/or
material. EAN barcodes are stored at the variant level since each
physical SKU has its own barcode.

SEO fields (seo_title, seo_description, search_keywords,
ai_search_snippet) are populated by the AI enrichment pipeline
and left null until that pipeline has run.
"""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, JSON,
    DateTime, ForeignKey, UniqueConstraint,
)
from app.models.product import Base


class ProductVariant(Base):
    """A single purchasable variant of a parent product.

    Identified uniquely by the combination of parent product,
    color and size. Carries its own EAN, SEO copy and optional
    variant-specific attributes.
    """

    __tablename__ = "product_variants"

    __table_args__ = (
        UniqueConstraint(
            "product_id", "color", "size",
            name="uq_variant_product_color_size",
        ),
    )

    id: int = Column(
        Integer, primary_key=True, autoincrement=True
    )
    product_id: int = Column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku_id: str = Column(
        String(255), nullable=True, index=True,
        comment="Variant-level SKU in the source system, if any",
    )
    ean: str = Column(
        String(13), unique=True, nullable=True, index=True,
        comment="EAN-13 barcode for this specific variant",
    )
    color: str = Column(String(100), nullable=True)
    size: str = Column(String(50), nullable=True)
    material: str = Column(String(200), nullable=True)
    attributes: dict = Column(
        JSON, nullable=True,
        comment="Additional variant-specific key-value attributes",
    )

    # AI-generated SEO fields — null until enrichment pipeline has run
    seo_title: str = Column(
        String(200), nullable=True,
        comment="AI-generated SEO title: Brand + Model + Type + Gender + Color + Size",
    )
    seo_description: str = Column(
        Text, nullable=True,
        comment="AI-generated SEO description, 150-200 words",
    )
    search_keywords: list = Column(
        JSON, nullable=True,
        comment="List of 8-12 search terms: exact, category and long-tail",
    )
    ai_search_snippet: str = Column(
        Text, nullable=True,
        comment="2-3 sentences optimised for AI search engines (ChatGPT, Perplexity)",
    )
    enriched_at: datetime = Column(
        DateTime, nullable=True,
        comment="Timestamp of the last successful AI enrichment run",
    )
    created_at: datetime = Column(
        DateTime, default=datetime.utcnow
    )

    def __repr__(self) -> str:
        """Return string representation for debugging."""
        return (
            f"<ProductVariant id={self.id} "
            f"product_id={self.product_id} "
            f"color={self.color!r} size={self.size!r} "
            f"ean={self.ean!r}>"
        )
