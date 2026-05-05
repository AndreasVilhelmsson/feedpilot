"""Service-level tests for IngestionService.

Runs against an isolated SQLite in-memory database per test.
No real AI calls, no external services, no Docker required for this module.
"""

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.models.product import Base, Product
from app.services.ingestion_service import IngestionService

FIXTURES = Path(__file__).parent / "fixtures"


def _read(filename: str) -> bytes:
    return (FIXTURES / filename).read_bytes()


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_csv_creates_products(db: Session) -> None:
    result = IngestionService().ingest_csv(_read("test_feed.csv"), "auto", db)

    assert result["total"] == 3
    assert result["created"] == 3
    assert result["updated"] == 0
    assert result["skipped"] == 0
    assert result["detected_source"] == "generic_csv"

    assert db.query(Product).count() == 3

    shoe2 = db.query(Product).filter_by(sku_id="SHOE-002").first()
    assert shoe2 is not None
    assert shoe2.attributes["brand"] == "Ecco"
    assert shoe2.attributes["size"] == "42"
    assert shoe2.price == 1299.00


def test_csv_missing_sku_skips_row(db: Session) -> None:
    result = IngestionService().ingest_csv(_read("test_bad.csv"), "auto", db)

    assert result["total"] == 2
    assert result["created"] == 1
    assert result["skipped"] == 1

    skipped_warning = result["warnings"][0]
    assert any(w["field"] == "sku_id" for w in skipped_warning["warnings"])

    products = db.query(Product).all()
    assert len(products) == 1
    assert products[0].sku_id == "SHOE-001"


def test_duplicate_sku_updates_product(db: Session) -> None:
    IngestionService().ingest_csv(_read("test_feed.csv"), "auto", db)
    result = IngestionService().ingest_csv(_read("test_feed.csv"), "auto", db)

    assert result["created"] == 0
    assert result["updated"] == 3
    assert db.query(Product).count() == 3


def test_new_products_csv_canonical_fields(db: Session) -> None:
    result = IngestionService().ingest_csv(_read("new_products.csv"), "auto", db)

    assert result["created"] == 10
    assert result["detected_source"] == "generic_csv"

    jacket1 = db.query(Product).filter_by(sku_id="JACKET-001").first()
    assert jacket1 is not None
    assert jacket1.attributes["brand"] == "Hugo Boss"
    assert jacket1.attributes["material"] == "Wool"
    # gender is not in CANONICAL_FIELDS so it flows through extra_attributes to attributes
    assert jacket1.attributes.get("gender") == "Male"
