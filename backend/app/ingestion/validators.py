"""Data quality validators for FeedPilot ingestion pipeline.

Validates normalized product rows and returns structured
quality warnings — does not raise exceptions, never blocks ingestion.
The goal is to flag problems, not stop the pipeline.
"""

from typing import Any


TITLE_MIN_LENGTH = 10
TITLE_MAX_LENGTH = 200
DESCRIPTION_MIN_LENGTH = 20


def validate_row(row: dict[str, Any]) -> list[dict[str, str]]:
    """Validate a normalized product row and return quality warnings.

    Args:
        row: Normalized product row with canonical field names.

    Returns:
        List of warning dicts with keys:
            field: The problematic field name.
            severity: 'high', 'medium' or 'low'.
            message: Human-readable description of the issue.
    """
    warnings: list[dict[str, str]] = []

    if not row.get("sku_id"):
        warnings.append({
            "field": "sku_id",
            "severity": "high",
            "message": "SKU saknas — raden kan inte importeras.",
        })

    title = row.get("title")
    if not title:
        warnings.append({
            "field": "title",
            "severity": "high",
            "message": "Produkttitel saknas.",
        })
    elif len(title) < TITLE_MIN_LENGTH:
        warnings.append({
            "field": "title",
            "severity": "high",
            "message": f"Titeln är för kort ({len(title)} tecken). Minimum {TITLE_MIN_LENGTH} tecken.",
        })
    elif len(title) > TITLE_MAX_LENGTH:
        warnings.append({
            "field": "title",
            "severity": "medium",
            "message": f"Titeln är för lång ({len(title)} tecken). Maximum {TITLE_MAX_LENGTH} tecken.",
        })

    description = row.get("description")
    if not description:
        warnings.append({
            "field": "description",
            "severity": "high",
            "message": "Produktbeskrivning saknas.",
        })
    elif len(description) < DESCRIPTION_MIN_LENGTH:
        warnings.append({
            "field": "description",
            "severity": "medium",
            "message": f"Beskrivningen är för kort ({len(description)} tecken).",
        })

    if not row.get("category"):
        warnings.append({
            "field": "category",
            "severity": "medium",
            "message": "Kategori saknas.",
        })

    if row.get("price") is None:
        warnings.append({
            "field": "price",
            "severity": "low",
            "message": "Pris saknas eller kunde inte tolkas.",
        })

    return warnings