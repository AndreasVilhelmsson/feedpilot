"""SQLAlchemy model for customer PIM system configuration.

Stores the field mapping between a customer's PIM system
and FeedPilot's canonical schema, enabling per-customer
ingestion and gap analysis.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String

from app.models.product import Base


class CustomerPIMConfig(Base):
    """Configuration for a customer's PIM system.

    Captures which fields the customer's PIM exposes, how they map
    to the FeedPilot canonical schema, and which canonical fields
    are absent (and therefore candidates for enrichment).
    """

    __tablename__ = "customer_pim_configs"

    id: int = Column(Integer, primary_key=True, autoincrement=True)

    customer_id: str = Column(
        String(255), nullable=False, index=True
    )
    pim_system: str = Column(
        String(100), nullable=True
    )

    # List of field names available in the customer's PIM
    available_fields: list = Column(JSON, nullable=True)

    # Mapping: customer PIM field → FeedPilot canonical field
    field_mapping: dict = Column(JSON, nullable=True)

    # Canonical fields not present in the customer's PIM (enrichment targets)
    missing_fields: list = Column(JSON, nullable=True)

    created_at: datetime = Column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: datetime = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True
    )

    def __repr__(self) -> str:
        """Return string representation for debugging."""
        return (
            f"<CustomerPIMConfig customer_id={self.customer_id!r}"
            f" pim_system={self.pim_system!r}>"
        )
