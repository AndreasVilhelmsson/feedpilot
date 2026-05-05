"""Tests for the image analysis service."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.core.image import _convert_avif_to_jpeg
from app.services.image_analysis_service import _parse_response


def test_parse_response_clamps_numeric_fields() -> None:
    """Out-of-range AI values should be normalized before response validation."""
    parsed = {
        "detected_attributes": {"color": "svart"},
        "quality_issues": ["Bilden är suddig"],
        "suggested_enrichments": [
            {
                "field": "title",
                "current_value": None,
                "suggested_value": "Svart sko",
                "reasoning": "Bilden visar en svart sko",
            }
        ],
        "image_quality_score": 999,
        "overall_confidence": 1.7,
        "reasoning": "Test",
    }

    result = _parse_response(parsed, "SHOE-002", 123)

    assert result.image_quality_score == 100
    assert result.overall_confidence == 1.0
    assert result.quality_issues == ["Bilden är suddig"]
    assert result.total_tokens == 123


def test_convert_avif_to_jpeg_raises_value_error_on_decode_failure() -> None:
    """Broken AVIF input should surface as a controlled validation error."""
    failed_process = SimpleNamespace(returncode=1, stderr=b"bad avif")
    with patch("app.core.image.subprocess.run", return_value=failed_process):
        with pytest.raises(ValueError, match="ffmpeg AVIF conversion failed"):
            _convert_avif_to_jpeg(b"not-an-avif")
