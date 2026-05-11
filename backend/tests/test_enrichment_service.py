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
from app.services.field_metadata import FIELD_REGISTRY


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
    return {
        "answer": json.dumps(payload),
        "input_tokens": 300,
        "output_tokens": 200,
        "total_tokens": 500,
    }


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


def test_enrich_product_sends_minimal_payload_for_brand(db: Session) -> None:
    # Only brand is missing; description, material, price and gender have values.
    p = Product(
        sku_id="TEST-BRAND-001",
        title="Running Shoe",
        description="A good shoe.",
        category="Shoes",
        price=599.0,
        attributes={"color": "red", "material": "leather", "gender": "unisex"},
        feed_source="auto",
        detected_source="generic_csv",
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    service = _make_service()

    with patch(
        "app.services.enrichment_service.ask_claude",
        return_value=_ai_answer(VALID_AI_RESPONSE),
    ) as mock_ask:
        with patch.object(ProductRepository, "semantic_search", return_value=[]):
            service.enrich_product("TEST-BRAND-001", db)

    prompt_json: str = mock_ask.call_args.kwargs["prompt"]
    payload = json.loads(prompt_json)
    product = payload["product"]

    brand_ctx = FIELD_REGISTRY["brand"].context_fields
    expected_keys = {"sku_id"} | {
        "attributes" if f == "extra_attributes" else f
        for f in brand_ctx
    }
    assert set(product.keys()) == expected_keys

    # Irrelevant fields must be absent regardless of registry changes.
    for field in ("description", "material", "price", "gender", "extra_attributes"):
        if field not in brand_ctx:
            assert field not in product, f"Irrelevant fält '{field}' skickades till ask_claude"


def test_planner_triggers_rag_when_brand_is_missing(db: Session) -> None:
    # brand is missing — planner sets use_rag=True, semantic_search must be called.
    p = Product(
        sku_id="TEST-PLANNER-RAG-001",
        title="Running Shoe",
        description="A solid everyday shoe.",
        category="Shoes",
        price=599.0,
        attributes={"color": "red", "material": "leather"},
        feed_source="auto",
        detected_source="generic_csv",
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    service = _make_service()

    with patch(
        "app.services.enrichment_service.ask_claude",
        return_value=_ai_answer(VALID_AI_RESPONSE),
    ) as mock_ask:
        with patch.object(ProductRepository, "semantic_search", return_value=[]) as mock_search:
            service.enrich_product("TEST-PLANNER-RAG-001", db)

    mock_search.assert_called_once()

    payload = json.loads(mock_ask.call_args.kwargs["prompt"])
    assert payload["missing_fields"] == ["brand"]


def test_planner_skips_rag_when_no_target_fields(db: Session) -> None:
    # All core fields present — planner sets use_rag=False, semantic_search must NOT be called.
    p = Product(
        sku_id="TEST-PLANNER-NORAG-001",
        title="Complete Shoe",
        description="A fully described shoe.",
        category="Shoes",
        price=499.0,
        attributes={"brand": "Nike", "color": "red", "material": "leather"},
        feed_source="auto",
        detected_source="generic_csv",
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    service = _make_service()

    with patch(
        "app.services.enrichment_service.ask_claude",
        return_value=_ai_answer(VALID_AI_RESPONSE),
    ) as mock_ask:
        with patch.object(ProductRepository, "semantic_search", return_value=[]) as mock_search:
            service.enrich_product("TEST-PLANNER-NORAG-001", db)

    mock_search.assert_not_called()

    payload = json.loads(mock_ask.call_args.kwargs["prompt"])
    assert payload["missing_fields"] == []
    assert payload["rag_context"] == []


def test_log_ai_request_called_on_success(db: Session) -> None:
    p = Product(
        sku_id="TEST-OBS-SUCCESS-001",
        title="Running Shoe",
        description="A good shoe.",
        category="Shoes",
        price=599.0,
        attributes={"color": "red", "material": "leather"},
        feed_source="auto",
        detected_source="generic_csv",
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    service = _make_service()

    with patch("app.services.enrichment_service.ask_claude", return_value=_ai_answer(VALID_AI_RESPONSE)):
        with patch.object(ProductRepository, "semantic_search", return_value=[]):
            with patch("app.services.enrichment_service.observability.log_ai_request") as mock_log:
                service.enrich_product("TEST-OBS-SUCCESS-001", db)

    mock_log.assert_called_once()
    metadata = mock_log.call_args.args[0]

    assert metadata.status == "success"
    assert metadata.error_type is None
    assert metadata.sku_id == "TEST-OBS-SUCCESS-001"
    assert metadata.prompt_name == "enrichment_v2"
    assert metadata.target_fields == ["brand"]
    assert metadata.use_rag is True
    assert metadata.input_tokens == 300
    assert metadata.output_tokens == 200
    assert metadata.total_tokens == 500


def test_log_ai_request_called_with_error_on_validation_failure(db: Session) -> None:
    p = Product(
        sku_id="TEST-OBS-ERROR-001",
        title="Running Shoe",
        description="A good shoe.",
        category="Shoes",
        price=599.0,
        attributes={"color": "red", "material": "leather"},
        feed_source="auto",
        detected_source="generic_csv",
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    service = _make_service()

    with patch("app.services.enrichment_service.ask_claude", return_value=_ai_answer({"return_risk": "extreme"})):
        with patch.object(ProductRepository, "semantic_search", return_value=[]):
            with patch("app.services.enrichment_service.observability.log_ai_request") as mock_log:
                with pytest.raises(ValidationError):
                    service.enrich_product("TEST-OBS-ERROR-001", db)

    mock_log.assert_called_once()
    metadata = mock_log.call_args.args[0]

    assert metadata.status == "error"
    assert metadata.error_type is not None
    assert metadata.input_tokens == 300
    assert metadata.output_tokens == 200
    assert metadata.total_tokens == 500
    assert db.query(AnalysisResult).count() == 0
