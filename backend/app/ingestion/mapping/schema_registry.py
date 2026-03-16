"""Schema registry for known e-commerce feed formats.

Each entry defines how a source system's field names
map to FeedPilot's internal canonical field names.

Adding support for a new source system means adding
one entry here — nothing else needs to change.
"""

from typing import Any

# FeedPilot's internal canonical field names.
# All source systems are normalized to these.
CANONICAL_FIELDS = [
    "sku_id",
    "title",
    "description",
    "category",
    "price",
    "attributes",
]

# Known schema mappings per source system.
# key = source field name, value = canonical field name
SCHEMA_REGISTRY: dict[str, dict[str, str]] = {
    "shopify": {
        "Variant SKU": "sku_id",
        "Title": "title",
        "Body (HTML)": "description",
        "Type": "category",
        "Variant Price": "price",
    },
    "woocommerce": {
        "SKU": "sku_id",
        "Name": "title",
        "Description": "description",
        "Categories": "category",
        "Regular price": "price",
    },
    "google_shopping": {
        "id": "sku_id",
        "item_group_id": "attributes",
        "image_link": "attributes",
        "availability": "attributes",
        "condition": "attributes",
        "google_product_category": "category",
    },
    "akeneo": {
        "sku": "sku_id",
        "label-en_US": "title",
        "description-en_US-ecommerce": "description",
        "categories": "category",
        "price-EUR": "price",
    },
    "generic_csv": {
        "sku": "sku_id",
        "sku_id": "sku_id",
        "product_id": "sku_id",
        "id": "sku_id",
        "article_number": "sku_id",
        "title": "title",
        "name": "title",
        "product_name": "title",
        "product_title": "title",
        "description": "description",
        "body_html": "description",
        "long_description": "description",
        "desc": "description",
        "category": "category",
        "product_type": "category",
        "type": "category",
        "kategori": "category",
        "price": "price",
        "regular_price": "price",
        "sale_price": "price",
        "pris": "price",
    },
}


def get_schema(source: str) -> dict[str, str]:
    """Return the field mapping for a known source system.

    Args:
        source: Source system identifier, e.g. 'shopify'.

    Returns:
        Dict mapping source field names to canonical names.
        Falls back to generic_csv if source is unknown.
    """
    return SCHEMA_REGISTRY.get(source, SCHEMA_REGISTRY["generic_csv"])


def detect_source(headers: list[str]) -> str:
    """Auto-detect the source system from CSV column headers.

    Scores each known schema by how many of its fields
    are present in the headers. Requires a minimum of 2
    matching fields to avoid false positives.

    Args:
        headers: List of column names from the CSV file.

    Returns:
        Best matching source system identifier,
        falls back to generic_csv if no strong match found.
    """
    headers_lower = {h.lower().strip() for h in headers}
    best_source = "generic_csv"
    best_score = 0
    MIN_SCORE = 3

    for source, mapping in SCHEMA_REGISTRY.items():
        if source == "generic_csv":
            continue
        source_fields = {k.lower().strip() for k in mapping.keys()}
        score = len(headers_lower & source_fields)
        if score > best_score and score >= MIN_SCORE:
            best_score = score
            best_source = source

    return best_source


def list_supported_sources() -> list[str]:
    """Return all registered source system identifiers.

    Returns:
        List of supported source system names.
    """
    return list(SCHEMA_REGISTRY.keys())