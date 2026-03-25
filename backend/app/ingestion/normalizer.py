"""Data normalizer for FeedPilot ingestion pipeline.

Converts CanonicalProduct fields into clean, typed Python values
ready for database persistence.
"""

from typing import Any

from app.schemas.canonical import CanonicalProduct

# Swedish → English color normalization
COLOR_MAP: dict[str, str] = {
    "svart": "black",
    "vit": "white",
    "blå": "blue",
    "mörkblå": "navy",
    "röd": "red",
    "grön": "green",
    "mörkgrön": "dark green",
    "grå": "grey",
    "brun": "brown",
    "beige": "beige",
}

# Gender keywords per canonical gender label
GENDER_KEYWORDS: dict[str, list[str]] = {
    "dam": ["dam", "kvinna", "women", "woman", "female"],
    "herr": ["herr", "man", "men", "male", "herre"],
    "barn": ["barn", "kids", "junior", "child", "pojke", "flicka"],
    "unisex": ["unisex"],
}


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
    """Normalize a SKU value to a clean uppercase string.

    Args:
        value: Raw SKU value.

    Returns:
        Uppercase stripped SKU string or None if empty.
    """
    if not value:
        return None
    return str(value).strip().upper()


def _detect_gender(title: str | None, category: str | None) -> str | None:
    """Detect product gender from title and category text.

    Args:
        title: Product title string.
        category: Product category string.

    Returns:
        Canonical gender label ('dam', 'herr', 'barn', 'unisex') or None.
    """
    text = " ".join(filter(None, [title, category])).lower()
    for gender, keywords in GENDER_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return gender
    return None


def _normalize_color(color: str | None) -> str | None:
    """Normalise a color value using COLOR_MAP.

    Args:
        color: Raw color string, possibly in Swedish.

    Returns:
        Normalised color string (English) or the original if not in map.
    """
    if not color:
        return color
    return COLOR_MAP.get(color.lower().strip(), color)


def normalize_row(product: CanonicalProduct) -> CanonicalProduct:
    """Apply type normalization and enrichment hints to a CanonicalProduct.

    Normalises SKU casing, color names and detects gender from
    title and category text.

    Args:
        product: Mapped CanonicalProduct from FieldMapper.

    Returns:
        CanonicalProduct with normalised field values.
    """
    product.sku_id = normalize_sku(product.sku_id) or product.sku_id
    product.color = _normalize_color(product.color)

    if product.gender is None:
        product.gender = _detect_gender(product.title, product.category)

    return product
