"""Data normalizer for FeedPilot ingestion pipeline.

Converts raw mapped rows into clean, typed Python objects
ready for database persistence.
"""

from typing import Any


def normalize_price(value: Any) -> float | None:
    """Parse a price value to float, handling currency symbols.

    Args:
        value: Raw price value, e.g. '1 299,00 kr' or '12.99'.

    Returns:
        Float price or None if unparseable.
    """
    if value is None:
        return None
    cleaned = (
        str(value)
        .replace("kr", "")
        .replace("$", "")
        .replace("€", "")
        .replace(" ", "")
        .replace(",", ".")
        .strip()
    )
    try:
        return float(cleaned)
    except ValueError:
        return None


def normalize_sku(value: Any) -> str | None:
    """Normalize a SKU value to a clean string.

    Args:
        value: Raw SKU value.

    Returns:
        Uppercase stripped SKU string or None if empty.
    """
    if not value:
        return None
    return str(value).strip().upper()


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Apply type normalization to a canonically mapped row.

    Args:
        row: Row with canonical field names from FieldMapper.

    Returns:
        Row with normalized Python types.
    """
    return {
        **row,
        "sku_id": normalize_sku(row.get("sku_id")),
        "title": str(row["title"]).strip() if row.get("title") else None,
        "description": str(row["description"]).strip() if row.get("description") else None,
        "category": str(row["category"]).strip() if row.get("category") else None,
        "price": normalize_price(row.get("price")),
    }