"""Tests for PreflightService.

All tests use an isolated SQLite in-memory database per test.
No AI calls are made — preflight is deterministic backend code.
"""

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.models.analysis_result import AnalysisResult  # registers analysis_results in Base.metadata
from app.models.product import Base, Product
from app.repositories.product_repository import ProductRepository
from app.services.preflight_service import (
    ESTIMATED_INPUT_TOKENS_PER_PRODUCT,
    ESTIMATED_OUTPUT_TOKENS_PER_PRODUCT,
    PreflightService,
)


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


def _make_service() -> PreflightService:
    return PreflightService(product_repo=ProductRepository())


def _add_product(db: Session, sku: str, **overrides) -> Product:
    fields = {
        "title": "Product Title",
        "description": "A description",
        "category": "Category",
        "price": 199.0,
        "attributes": {"brand": "Brand", "color": "Red"},
        "feed_source": "auto",
        "detected_source": "generic_csv",
    }
    fields.update(overrides)
    p = Product(sku_id=sku, **fields)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_preflight_counts_products(db: Session) -> None:
    for i in range(3):
        _add_product(db, f"SKU-{i:03d}")

    result = _make_service().compute_preflight(limit=10, db=db)

    assert result.product_count == 3
    assert result.estimated_ai_calls == 3
    assert result.requires_confirmation is True


def test_preflight_aggregates_missing_fields(db: Session) -> None:
    # SKU-001: description=None, no brand/material in attributes → 3 missing
    _add_product(db, "SKU-001", description=None, attributes={"color": "Blue"})
    # SKU-002: description present, no brand/material in attributes → 2 missing
    _add_product(db, "SKU-002", attributes={"color": "Red"})
    # SKU-003: all core fields populated → 0 missing
    _add_product(db, "SKU-003", attributes={"brand": "Nike", "color": "Black", "material": "Cotton"})

    result = _make_service().compute_preflight(limit=10, db=db)

    assert result.product_count == 3
    assert result.fields_to_enrich["description"] == 1   # only SKU-001
    assert result.fields_to_enrich["brand"] == 2          # SKU-001 and SKU-002
    assert result.fields_to_enrich["material"] == 2       # SKU-001 and SKU-002


def test_preflight_makes_no_ai_calls(db: Session) -> None:
    _add_product(db, "SKU-001")

    with patch("app.core.ai.ask_claude", side_effect=AssertionError("AI must not be called during preflight")):
        result = _make_service().compute_preflight(limit=10, db=db)

    assert result.product_count == 1


def test_preflight_cost_estimate_is_deterministic(db: Session) -> None:
    for i in range(2):
        _add_product(db, f"SKU-{i:03d}")

    service = _make_service()
    result_a = service.compute_preflight(limit=10, db=db)
    result_b = service.compute_preflight(limit=10, db=db)

    assert result_a.estimated_input_tokens == 2 * ESTIMATED_INPUT_TOKENS_PER_PRODUCT
    assert result_a.estimated_output_tokens == 2 * ESTIMATED_OUTPUT_TOKENS_PER_PRODUCT
    assert result_a.estimated_total_tokens == result_a.estimated_input_tokens + result_a.estimated_output_tokens
    assert result_a.estimated_cost_usd > 0.0
    assert result_a.estimated_input_tokens == result_b.estimated_input_tokens
    assert result_a.estimated_cost_usd == result_b.estimated_cost_usd
