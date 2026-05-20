"""HTTP-level tests for /api/v1/products/{sku_id} endpoints.

All tests use:
- FastAPI TestClient
- SQLite in-memory database (overrides get_db — no PostgreSQL calls)
- Real ORM rows (Product + AnalysisResult) to lock in current query behavior
- Mocked EnrichmentService for /enrich tests — no AI calls
- No mock of _get_product_or_404 or _latest_analysis — those helpers are what
  these tests protect before the repository extraction in FEED-070B.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.main import app
from app.models.analysis_result import AnalysisResult  # noqa: F401 — registers table in Base.metadata
from app.models.product import Base, Product
from app.services.enrichment_service import EnrichmentService, get_enrichment_service

MOCK_ENRICH_RESULT = {
    "sku_id": "SKU-001",
    "analysis_id": 1,
    "overall_score": 72,
    "return_risk": "low",
    "enrichment_priority": "medium",
    "total_tokens": 500,
}


@pytest.fixture
def sqlite_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def seeded_db(sqlite_db):
    """Two products: one without enrichment, one with two AnalysisResult rows.

    SKU-002 has an older high-risk result (id=1) and a newer low-risk result
    (id=2). This verifies that _latest_analysis() selects the row with the
    highest id (ORDER BY id DESC).
    """
    p1 = Product(sku_id="SKU-001", title="Skor A", description="Bra skor.")
    p2 = Product(sku_id="SKU-002", title="Jacka B")
    sqlite_db.add_all([p1, p2])
    sqlite_db.flush()

    sqlite_db.add_all([
        AnalysisResult(
            product_id=p2.id,
            sku_id="SKU-002",
            return_risk="high",
            overall_score=30,
            prompt_version="1.0.0",
            total_tokens=200,
            action_items=[],
            issues=[],
            enriched_fields={},
        ),
        AnalysisResult(
            product_id=p2.id,
            sku_id="SKU-002",
            return_risk="low",
            overall_score=75,
            prompt_version="2.0.0",
            total_tokens=400,
            action_items=["Komplettera beskrivning"],
            issues=[],
            enriched_fields={},
        ),
    ])
    sqlite_db.commit()
    return sqlite_db


@pytest.fixture
def mock_enrichment_service():
    return MagicMock(spec=EnrichmentService)


@pytest.fixture
def products_client(seeded_db, mock_enrichment_service):
    app.dependency_overrides[get_db] = lambda: seeded_db
    app.dependency_overrides[get_enrichment_service] = lambda: mock_enrichment_service
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# --- GET /api/v1/products/{sku_id} ---


def test_get_product_returns_200_for_existing_product(products_client):
    response = products_client.get("/api/v1/products/SKU-001")

    assert response.status_code == 200
    data = response.json()
    assert data["sku_id"] == "SKU-001"
    assert data["title"] == "Skor A"
    assert data["overall_score"] is None
    assert data["enriched_at"] is None


def test_get_product_returns_latest_analysis_result(products_client):
    response = products_client.get("/api/v1/products/SKU-002")

    assert response.status_code == 200
    data = response.json()
    assert data["sku_id"] == "SKU-002"
    # Must be the newer row (overall_score=75, low risk), not the older (30, high)
    assert data["overall_score"] == 75
    assert data["return_risk"] == "low"
    assert data["enriched_at"] is not None


def test_get_product_returns_404_for_missing_product(products_client):
    response = products_client.get("/api/v1/products/SKU-MISSING")

    assert response.status_code == 404


# --- POST /api/v1/products/{sku_id}/enrich ---


def test_enrich_product_returns_200_with_mocked_service(
    products_client, mock_enrichment_service
):
    mock_enrichment_service.enrich_product.return_value = MOCK_ENRICH_RESULT

    response = products_client.post("/api/v1/products/SKU-001/enrich")

    assert response.status_code == 200
    data = response.json()
    assert data["sku_id"] == "SKU-001"
    assert data["analysis_id"] == 1
    assert data["enrichment_priority"] == "medium"


def test_enrich_product_returns_404_when_service_raises_value_error(
    products_client, mock_enrichment_service
):
    # SKU-001 exists in seeded_db so _get_product_or_404 passes;
    # the 404 here comes from the service raising ValueError.
    mock_enrichment_service.enrich_product.side_effect = ValueError(
        "Produkt SKU-001 hittades inte i enrichment-logiken"
    )

    response = products_client.post("/api/v1/products/SKU-001/enrich")

    assert response.status_code == 404


# --- PATCH /api/v1/products/{sku_id}/fields ---


def test_apply_fields_returns_200_and_updated_fields(products_client):
    response = products_client.patch(
        "/api/v1/products/SKU-001/fields",
        json={"fields": {"title": "Nytt namn"}},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["sku_id"] == "SKU-001"
    assert "title" in data["updated_fields"]


def test_apply_fields_returns_404_for_missing_product(products_client):
    response = products_client.patch(
        "/api/v1/products/SKU-MISSING/fields",
        json={"fields": {"title": "x"}},
    )

    assert response.status_code == 404
