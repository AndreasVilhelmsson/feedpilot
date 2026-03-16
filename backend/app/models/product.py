"""SQLAlchemy product model for FeedPilot.

Represents a normalized product from any e-commerce
feed format — Shopify, WooCommerce, Google Shopping etc.
"""

from datetime import datetime
from sqlalchemy import (
    Column, String, Text, JSON,
    DateTime, Integer, Float
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


class Product(Base):
    """Normalized product representation.

    Stores both normalized fields and raw source data
    so we can always trace back to the original feed.
    """

    __tablename__ = "products"

    id: int = Column(
        Integer, primary_key=True, autoincrement=True
    )
    sku_id: str = Column(
        String(255), unique=True, nullable=False, index=True
    )
    title: str = Column(String(500), nullable=True)
    description: str = Column(Text, nullable=True)
    category: str = Column(String(255), nullable=True)
    price: float = Column(Float, nullable=True)
    attributes: dict = Column(JSON, nullable=True)
    raw_data: dict = Column(JSON, nullable=True)
    feed_source: str = Column(String(100), nullable=True)
    detected_source: str = Column(String(100), nullable=True)
    quality_warnings: list = Column(JSON, nullable=True)
    created_at: datetime = Column(
        DateTime, default=datetime.utcnow
    )
    updated_at: datetime = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def __repr__(self) -> str:
        """Return string representation for debugging."""
        return f"<Product sku_id={self.sku_id} title={self.title!r}>"