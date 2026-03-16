"""SQLAlchemy embedding model for FeedPilot.

Stores vector embeddings for product chunks.
Each product can have multiple chunks with embeddings.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from pgvector.sqlalchemy import Vector
from app.models.product import Base

EMBEDDING_DIMENSIONS = 1536


class ProductEmbedding(Base):
    """Vector embedding for a product chunk.

    A product is split into chunks and each chunk
    gets its own embedding for granular semantic search.
    """

    __tablename__ = "product_embeddings"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    product_id: int = Column(
        Integer,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sku_id: str = Column(String(255), nullable=False, index=True)
    chunk_index: int = Column(Integer, nullable=False)
    chunk_text: str = Column(Text, nullable=False)
    chunk_type: str = Column(String(50), nullable=True)
    embedding = Column(Vector(EMBEDDING_DIMENSIONS), nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<ProductEmbedding sku_id={self.sku_id} chunk={self.chunk_index}>"