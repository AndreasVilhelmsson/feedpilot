"""Shared pytest fixtures for FeedPilot tests.

conftest.py is automatically loaded by pytest and
makes fixtures available across all test files.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
from app.main import app
from app.services.analyze_service import AnalyzeService, get_analyze_service

MOCK_AI_RESPONSE = {
    "answer": "Skor B har högst returgrad med 45 returer. Rekommendation: se över produktbeskrivningen.",
    "input_tokens": 120,
    "output_tokens": 80,
    "total_tokens": 200,
}

MOCK_PRODUCT_DATA = [
    {"sku": "SKU-001", "name": "Skor A", "returns": 12, "sales": 100},
    {"sku": "SKU-002", "name": "Skor B", "returns": 45, "sales": 100},
    {"sku": "SKU-003", "name": "Jacka A", "returns": 5, "sales": 80},
]


@pytest.fixture
def mock_analyze_service() -> AsyncMock:
    """Return a mock AnalyzeService that never calls Claude API."""
    mock = AsyncMock(spec=AnalyzeService)
    mock.analyze_question.return_value = MOCK_AI_RESPONSE
    return mock


@pytest.fixture
def client(mock_analyze_service: AsyncMock) -> TestClient:
    """Return a TestClient with AnalyzeService mocked out.

    This means no real Claude API calls are made during tests.
    """
    app.dependency_overrides[get_analyze_service] = lambda: mock_analyze_service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()