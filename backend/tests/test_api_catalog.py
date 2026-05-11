"""HTTP-level tests for GET /api/v1/catalog.

All tests use:
- FastAPI TestClient
- SQLite in-memory database (overrides get_db — no PostgreSQL calls)
- Real ORM rows (Product + AnalysisResult) to lock in current query and status behavior
- No service mock — the actual db.query logic in catalog.py is exercised directly
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.main import app
from app.models.analysis_result import AnalysisResult  # noqa: F401 — registers analysis_results in Base.metadata
from app.models.product import Base, Product


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
    """Three products: one unenriched, one low-risk enriched, one high-risk enriched.

    Titles use ASCII-only characters to avoid SQLite ilike vs PostgreSQL ilike
    divergence on non-ASCII input (å/ä/ö).
    """
    p1 = Product(sku_id="SKU-001", title="Skor A")
    p2 = Product(sku_id="SKU-002", title="Jacka B")
    p3 = Product(sku_id="SKU-003", title="Vaska C")
    sqlite_db.add_all([p1, p2, p3])
    sqlite_db.flush()  # Assigns product.id before AnalysisResult rows reference it

    sqlite_db.add_all([
        AnalysisResult(
            product_id=p2.id,
            sku_id="SKU-002",
            return_risk="low",
            overall_score=75,
            prompt_version="2.0.0",
            total_tokens=400,
        ),
        AnalysisResult(
            product_id=p3.id,
            sku_id="SKU-003",
            return_risk="high",
            overall_score=30,
            prompt_version="2.0.0",
            total_tokens=400,
        ),
    ])
    sqlite_db.commit()
    return sqlite_db


@pytest.fixture
def catalog_client(seeded_db):
    app.dependency_overrides[get_db] = lambda: seeded_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _by_sku(data: dict, sku_id: str) -> dict:
    return next(p for p in data["products"] if p["sku_id"] == sku_id)


# --- GET /api/v1/catalog ---


def test_catalog_returns_200_and_response_shape(catalog_client):
    response = catalog_client.get("/api/v1/catalog")

    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert isinstance(data["products"], list)


def test_catalog_product_without_analysis_is_needs_review(catalog_client):
    response = catalog_client.get("/api/v1/catalog?page_size=100")

    assert response.status_code == 200
    product = _by_sku(response.json(), "SKU-001")
    assert product["status"] == "needs_review"
    assert product["overall_score"] is None


def test_catalog_low_risk_analysis_is_enriched(catalog_client):
    response = catalog_client.get("/api/v1/catalog?page_size=100")

    assert response.status_code == 200
    product = _by_sku(response.json(), "SKU-002")
    assert product["status"] == "enriched"
    assert product["overall_score"] == 75


def test_catalog_high_risk_analysis_is_return_risk(catalog_client):
    response = catalog_client.get("/api/v1/catalog?page_size=100")

    assert response.status_code == 200
    product = _by_sku(response.json(), "SKU-003")
    assert product["status"] == "return_risk"


def test_catalog_status_filter_return_risk(catalog_client):
    response = catalog_client.get("/api/v1/catalog?status=return_risk")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["products"][0]["status"] == "return_risk"


def test_catalog_search_filters_by_title(catalog_client):
    response = catalog_client.get("/api/v1/catalog?search=Skor")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert "Skor" in data["products"][0]["title"]


def test_catalog_pagination_limits_products(catalog_client):
    response = catalog_client.get("/api/v1/catalog?page_size=1")

    assert response.status_code == 200
    data = response.json()
    assert len(data["products"]) == 1
    assert data["total"] == 3
    assert data["page"] == 1
    assert data["page_size"] == 1
