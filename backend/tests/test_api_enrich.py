"""HTTP-level tests for POST /api/v1/enrich/preflight and POST /api/v1/enrich/{sku_id}.

All tests use:
- FastAPI TestClient
- SQLite in-memory database (overrides get_db — no PostgreSQL calls)
- Mocked EnrichmentService and PreflightService (no AI or DB calls)
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import get_db
from app.main import app
from app.models.analysis_result import AnalysisResult  # noqa: F401 — registers table in Base.metadata
from app.models.product import Base
from app.schemas.enrich import PreflightResponse
from app.services.enrichment_service import EnrichmentService, get_enrichment_service
from app.services.preflight_service import PreflightService, get_preflight_service

MOCK_ENRICH_RESULT = {
    "sku_id": "SKU-001",
    "analysis_id": 1,
    "overall_score": 72,
    "enriched_fields": {},
    "issues": [],
    "return_risk": "low",
    "return_risk_reason": "Complete data.",
    "action_items": [],
    "prompt_version": "2.0.0",
    "total_tokens": 500,
}

MOCK_PREFLIGHT_RESPONSE = PreflightResponse(
    product_count=2,
    estimated_ai_calls=2,
    estimated_input_tokens=1600,
    estimated_output_tokens=2400,
    estimated_total_tokens=4000,
    estimated_cost_usd=0.02,
    fields_to_enrich={"brand": 1},
    tool_plan={"rag": True, "web_search": False, "image_analysis": False},
    requires_confirmation=True,
)


@pytest.fixture
def sqlite_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def mock_enrichment_service():
    return MagicMock(spec=EnrichmentService)


@pytest.fixture
def mock_preflight_service():
    return MagicMock(spec=PreflightService)


@pytest.fixture
def enrich_client(mock_enrichment_service, mock_preflight_service, sqlite_db):
    app.dependency_overrides[get_enrichment_service] = lambda: mock_enrichment_service
    app.dependency_overrides[get_preflight_service] = lambda: mock_preflight_service
    app.dependency_overrides[get_db] = lambda: sqlite_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# --- POST /api/v1/enrich/preflight ---


def test_preflight_happy_path(enrich_client, mock_preflight_service):
    mock_preflight_service.compute_preflight.return_value = MOCK_PREFLIGHT_RESPONSE

    response = enrich_client.post("/api/v1/enrich/preflight", json={"limit": 10})

    assert response.status_code == 200
    data = response.json()
    assert data["product_count"] == 2
    assert data["requires_confirmation"] is True


def test_preflight_missing_body_returns_422(enrich_client):
    response = enrich_client.post("/api/v1/enrich/preflight")

    assert response.status_code == 422


# --- POST /api/v1/enrich/{sku_id} ---


def test_enrich_product_happy_path(enrich_client, mock_enrichment_service):
    mock_enrichment_service.enrich_product.return_value = MOCK_ENRICH_RESULT

    response = enrich_client.post("/api/v1/enrich/SKU-001")

    assert response.status_code == 200
    data = response.json()
    assert data["sku_id"] == "SKU-001"
    assert data["overall_score"] == 72


def test_enrich_product_not_found(enrich_client, mock_enrichment_service):
    mock_enrichment_service.enrich_product.side_effect = ValueError(
        "Produkt SKU-999 hittades inte"
    )

    response = enrich_client.post("/api/v1/enrich/SKU-999")

    assert response.status_code == 404


def test_enrich_product_unexpected_error(enrich_client, mock_enrichment_service):
    mock_enrichment_service.enrich_product.side_effect = RuntimeError("Unexpected error")

    response = enrich_client.post("/api/v1/enrich/SKU-001")

    assert response.status_code == 500
