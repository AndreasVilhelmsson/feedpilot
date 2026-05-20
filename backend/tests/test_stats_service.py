"""Service-level tests for StatsService.get_stats() — avg_enrichment_score field.

All tests use:
- MagicMock(spec=StatsRepository) — no database calls
- StatsService instantiated directly with the mock repo
- db argument passed as None (service only forwards it to repo methods, which are mocked)

These tests are intentionally RED until:
  1. StatsRepository.get_avg_enrichment_score() is added (FEED-071)
  2. StatsService.get_stats() calls it and passes the result to StatsResponse
  3. StatsResponse schema includes avg_enrichment_score field
"""

from unittest.mock import MagicMock

import pytest

from app.repositories.stats_repository import StatsRepository
from app.services.stats_service import StatsService


@pytest.fixture
def mock_repo() -> MagicMock:
    """StatsRepository with all existing methods stubbed to safe defaults."""
    repo = MagicMock(spec=StatsRepository)
    repo.get_total_products.return_value = 10
    repo.get_enriched_count.return_value = 6
    repo.get_pending_count.return_value = 3
    repo.get_failed_count.return_value = 1
    repo.get_return_risk_high_count.return_value = 2
    repo.get_avg_enrichment_score.return_value = 75.0  # overridden per test where needed
    return repo


@pytest.fixture
def service(mock_repo: MagicMock) -> StatsService:
    return StatsService(stats_repo=mock_repo)


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_get_stats_includes_avg_enrichment_score(service: StatsService, mock_repo: MagicMock) -> None:
    mock_repo.get_avg_enrichment_score.return_value = 75.0

    result = service.get_stats(db=None)

    assert hasattr(result, "avg_enrichment_score")
    assert result.avg_enrichment_score == pytest.approx(75.0, abs=0.1)
    mock_repo.get_avg_enrichment_score.assert_called_once_with(None)


def test_get_stats_avg_score_is_none_when_no_enriched(service: StatsService, mock_repo: MagicMock) -> None:
    mock_repo.get_avg_enrichment_score.return_value = None

    result = service.get_stats(db=None)

    assert result.avg_enrichment_score is None


def test_get_stats_passes_avg_score_from_repo_unchanged(service: StatsService, mock_repo: MagicMock) -> None:
    mock_repo.get_avg_enrichment_score.return_value = 73.4

    result = service.get_stats(db=None)

    assert result.avg_enrichment_score == pytest.approx(73.4, abs=0.01)
