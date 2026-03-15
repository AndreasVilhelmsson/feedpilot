"""Tests for the analyze endpoint and AnalyzeService.

Covers three levels:
- Unit tests: AnalyzeService in isolation
- API tests: HTTP behavior via TestClient
- Edge cases: invalid input, error handling
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.services.analyze_service import AnalyzeService


class TestAnalyzeService:
    """Unit tests for AnalyzeService — no HTTP, no real Claude calls."""

    @pytest.mark.asyncio
    async def test_analyze_question_returns_expected_keys(self) -> None:
        """Service should return dict with answer and token counts."""
        mock_response = {
            "answer": "Skor B har högst returgrad.",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
        }
        with patch("app.services.analyze_service.ask_claude", return_value=mock_response):
            service = AnalyzeService()
            result = await service.analyze_question(
                "Vilka produkter har högst returgrad?"
            )

        assert "answer" in result
        assert "total_tokens" in result
        assert result["total_tokens"] == 150

    @pytest.mark.asyncio
    async def test_analyze_question_passes_system_prompt(self) -> None:
        """Service should always inject the FeedPilot system prompt."""
        with patch("app.services.analyze_service.ask_claude") as mock_claude:
            mock_claude.return_value = {
                "answer": "svar",
                "input_tokens": 10,
                "output_tokens": 10,
                "total_tokens": 20,
            }
            service = AnalyzeService()
            await service.analyze_question("testfråga")

        _, kwargs = mock_claude.call_args
        assert "system" in kwargs
        assert "FeedPilot" in kwargs["system"]


class TestAnalyzeEndpoint:
    """API tests for POST /api/v1/analyze — tests HTTP behavior."""

    def test_analyze_returns_200_with_valid_question(
        self, client: TestClient
    ) -> None:
        """Valid question should return 200 with answer."""
        response = client.post(
            "/api/v1/analyze",
            json={"question": "Vilka produkter har högst returgrad?"},
        )
        assert response.status_code == 200
        assert "answer" in response.json()

    def test_analyze_returns_token_usage(self, client: TestClient) -> None:
        """Response should always include token usage for cost tracking."""
        response = client.post(
            "/api/v1/analyze",
            json={"question": "Vilka produkter har högst returgrad?"},
        )
        data = response.json()
        assert data["input_tokens"] == 120
        assert data["output_tokens"] == 80
        assert data["total_tokens"] == 200

    def test_analyze_rejects_too_short_question(self, client: TestClient) -> None:
        """Questions under 10 chars should return 422 validation error."""
        response = client.post(
            "/api/v1/analyze",
            json={"question": "kort"},
        )
        assert response.status_code == 422

    def test_analyze_rejects_missing_question(self, client: TestClient) -> None:
        """Missing question field should return 422 validation error."""
        response = client.post("/api/v1/analyze", json={})
        assert response.status_code == 422

    def test_analyze_returns_500_when_service_fails(
        self, client: TestClient, mock_analyze_service: AsyncMock
    ) -> None:
        """If Claude API fails, endpoint should return 500."""
        mock_analyze_service.analyze_question.side_effect = Exception(
            "Claude API nere"
        )
        response = client.post(
            "/api/v1/analyze",
            json={"question": "Vilka produkter har högst returgrad?"},
        )
        assert response.status_code == 500