"""Service-level tests for EnrichmentService.

All tests use an isolated SQLite in-memory database per test.
ask_claude and semantic_search are mocked — no external API calls.
"""

import json
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.models.analysis_result import AnalysisResult  # registers analysis_results in Base.metadata
from app.models.product import Base, Product
from app.repositories.product_repository import ProductRepository
from app.services.enrichment_service import EnrichmentService


VALID_AI_RESPONSE: dict = {
    "overall_score": 72,
    "return_risk": "medium",
    "return_risk_reason": "Short description increases return risk.",
    "issues": [
        {
            "field": "description",
            "severity": "high",
            "problem": "Too short",
            "suggestion": "Expand the description",
        }
    ],
    "enriched_fields": {
        "description": {
            "reasoning": "Description is sparse",
            "confidence": 0.85,
            "suggested_value": "A richer product description",
        }
    },
    "action_items": ["Improve product description"],
}


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


@pytest.fixture
def product(db: Session) -> Product:
    p = Product(
        sku_id="TEST-001",
        title="Test Shoe",
        description="Short.",
        category="Shoes",
        price=499.0,
        attributes={"brand": "Nike", "color": "black"},
        feed_source="auto",
        detected_source="generic_csv",
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _make_service() -> EnrichmentService:
    return EnrichmentService(product_repo=ProductRepository())


def _ai_answer(payload: dict) -> dict:
    return {"answer": json.dumps(payload), "total_tokens": 500}


def test_valid_ai_output_is_persisted(db: Session, product: Product) -> None:
    service = _make_service()

    with patch("app.services.enrichment_service.ask_claude", return_value=_ai_answer(VALID_AI_RESPONSE)):
        with patch.object(ProductRepository, "semantic_search", return_value=[]):
            result = service.enrich_product("TEST-001", db)

    analysis = db.query(AnalysisResult).filter_by(sku_id="TEST-001").first()
    assert analysis is not None
    assert analysis.overall_score == 72
    assert analysis.return_risk == "medium"
    assert isinstance(analysis.issues, list)
    assert isinstance(analysis.enriched_fields, dict)

    assert result["overall_score"] == 72
    assert result["return_risk"] == "medium"
    assert result["return_risk_reason"] == "Short description increases return risk."


def test_invalid_return_risk_raises_and_does_not_persist(db: Session, product: Product) -> None:
    service = _make_service()

    with patch("app.services.enrichment_service.ask_claude", return_value=_ai_answer({"return_risk": "extreme"})):
        with patch.object(ProductRepository, "semantic_search", return_value=[]):
            with pytest.raises(ValidationError):
                service.enrich_product("TEST-001", db)

    assert db.query(AnalysisResult).count() == 0


def test_invalid_overall_score_raises_and_does_not_persist(db: Session, product: Product) -> None:
    service = _make_service()

    with patch("app.services.enrichment_service.ask_claude", return_value=_ai_answer({"overall_score": 999})):
        with patch.object(ProductRepository, "semantic_search", return_value=[]):
            with pytest.raises(ValidationError):
                service.enrich_product("TEST-001", db)

    assert db.query(AnalysisResult).count() == 0


def test_invalid_enriched_fields_shape_raises_and_does_not_persist(db: Session, product: Product) -> None:
    service = _make_service()

    with patch("app.services.enrichment_service.ask_claude", return_value=_ai_answer({"enriched_fields": ["not", "a", "dict"]})):
        with patch.object(ProductRepository, "semantic_search", return_value=[]):
            with pytest.raises(ValidationError):
                service.enrich_product("TEST-001", db)

    assert db.query(AnalysisResult).count() == 0
