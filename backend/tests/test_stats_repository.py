"""Unit tests for StatsRepository.get_avg_enrichment_score().

All tests use:
- SQLite in-memory database (no PostgreSQL required)
- Real ORM rows (Product + AnalysisResult) inserted directly
- StatsRepository called directly — no HTTP layer involved

These tests are intentionally RED until get_avg_enrichment_score()
is added to stats_repository.py (FEED-071).
"""

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.analysis_result import AnalysisResult  # noqa: F401 — registers table in Base.metadata
from app.models.product import Base, Product
from app.repositories.stats_repository import StatsRepository


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
def repo() -> StatsRepository:
    return StatsRepository()


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_get_avg_enrichment_score_empty_catalog(sqlite_db, repo):
    result = repo.get_avg_enrichment_score(sqlite_db)

    assert result is None


def test_get_avg_enrichment_score_single_product(sqlite_db, repo):
    p = Product(sku_id="SKU-001", title="Skor A")
    sqlite_db.add(p)
    sqlite_db.flush()

    sqlite_db.add(AnalysisResult(
        product_id=p.id,
        sku_id="SKU-001",
        overall_score=80,
        return_risk="low",
        created_at=datetime(2026, 1, 1, 10, 0, 0),
    ))
    sqlite_db.commit()

    result = repo.get_avg_enrichment_score(sqlite_db)

    assert result == pytest.approx(80.0, abs=0.1)


def test_get_avg_enrichment_score_multiple_products(sqlite_db, repo):
    p1 = Product(sku_id="SKU-001", title="Skor A")
    p2 = Product(sku_id="SKU-002", title="Jacka B")
    p3 = Product(sku_id="SKU-003", title="Vaska C")
    sqlite_db.add_all([p1, p2, p3])
    sqlite_db.flush()

    sqlite_db.add_all([
        AnalysisResult(
            product_id=p1.id, sku_id="SKU-001", overall_score=60,
            return_risk="low", created_at=datetime(2026, 1, 1, 10, 0, 0),
        ),
        AnalysisResult(
            product_id=p2.id, sku_id="SKU-002", overall_score=70,
            return_risk="low", created_at=datetime(2026, 1, 1, 10, 0, 0),
        ),
        AnalysisResult(
            product_id=p3.id, sku_id="SKU-003", overall_score=80,
            return_risk="low", created_at=datetime(2026, 1, 1, 10, 0, 0),
        ),
    ])
    sqlite_db.commit()

    result = repo.get_avg_enrichment_score(sqlite_db)

    assert result == pytest.approx(70.0, abs=0.1)


def test_get_avg_enrichment_score_uses_latest_only(sqlite_db, repo):
    """Only the most recent AnalysisResult per product (by created_at) counts."""
    p = Product(sku_id="SKU-001", title="Skor A")
    sqlite_db.add(p)
    sqlite_db.flush()

    sqlite_db.add_all([
        AnalysisResult(
            product_id=p.id, sku_id="SKU-001", overall_score=40,
            return_risk="high", created_at=datetime(2026, 1, 1, 10, 0, 0),
        ),
        AnalysisResult(
            product_id=p.id, sku_id="SKU-001", overall_score=90,
            return_risk="low", created_at=datetime(2026, 1, 2, 10, 0, 0),
        ),
    ])
    sqlite_db.commit()

    result = repo.get_avg_enrichment_score(sqlite_db)

    # Average of latest-only (90), not all runs (40+90)/2 = 65
    assert result == pytest.approx(90.0, abs=0.1)


def test_get_avg_enrichment_score_excludes_null_scores(sqlite_db, repo):
    """Products whose latest analysis has overall_score=None are excluded."""
    p1 = Product(sku_id="SKU-001", title="Skor A")
    p2 = Product(sku_id="SKU-002", title="Jacka B")
    sqlite_db.add_all([p1, p2])
    sqlite_db.flush()

    sqlite_db.add_all([
        AnalysisResult(
            product_id=p1.id, sku_id="SKU-001", overall_score=80,
            return_risk="low", created_at=datetime(2026, 1, 1, 10, 0, 0),
        ),
        AnalysisResult(
            product_id=p2.id, sku_id="SKU-002", overall_score=None,
            return_risk=None, created_at=datetime(2026, 1, 1, 10, 0, 0),
        ),
    ])
    sqlite_db.commit()

    result = repo.get_avg_enrichment_score(sqlite_db)

    # p2 has score=None (failed enrichment) — only p1's score=80 counts
    assert result == pytest.approx(80.0, abs=0.1)
