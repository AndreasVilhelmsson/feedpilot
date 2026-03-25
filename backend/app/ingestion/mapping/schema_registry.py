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
    "brand",
    "category",
    "price",
    "color",
    "material",
    "size",
    "dimensions",
    "ean",
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
        "Vendor": "brand",
        "Option1 Value": "size",
        "Variant Barcode": "ean",
    },
    "woocommerce": {
        "SKU": "sku_id",
        "Name": "title",
        "Description": "description",
        "Categories": "category",
        "Regular price": "price",
        "Brands": "brand",
        "Color": "color",
        "Size": "size",
    },
    "google_shopping": {
        "id": "sku_id",
        "google_product_category": "category",
        "title": "title",
        "description": "description",
        "price": "price",
        "brand": "brand",
        "color": "color",
        "material": "material",
        "size": "size",
        "size_system": "size_system",
        "gtin": "ean",
        "shipping_weight": "dimensions",
    },
    "akeneo": {
        "sku": "sku_id",
        "label-en_US": "title",
        "description-en_US-ecommerce": "description",
        "categories": "category",
        "price-EUR": "price",
        "brand": "brand",
        "color": "color",
        "material": "material",
        "size": "size",
        "ean": "ean",
        "dimensions": "dimensions",
    },
    "generic_csv": {
        # Identification
        "sku": "sku_id",
        "sku_id": "sku_id",
        "product_id": "sku_id",
        "id": "sku_id",
        "article_number": "sku_id",
        "artikelnummer": "sku_id",
        # Title
        "title": "title",
        "name": "title",
        "product_name": "title",
        "product_title": "title",
        "produktnamn": "title",
        # Description
        "description": "description",
        "body_html": "description",
        "long_description": "description",
        "desc": "description",
        "beskrivning": "description",
        # Brand
        "brand": "brand",
        "brand_name": "brand",
        "manufacturer": "brand",
        "varumärke": "brand",
        "tillverkare": "brand",
        # Category
        "category": "category",
        "product_type": "category",
        "type": "category",
        "kategori": "category",
        # Price
        "price": "price",
        "regular_price": "price",
        "sale_price": "price",
        "pris": "price",
        # Color
        "color": "color",
        "colour": "color",
        "färg": "color",
        "color_name": "color",
        # Material
        "material": "material",
        "fabric": "material",
        "material_composition": "material",
        "tyg": "material",
        # Size
        "size": "size",
        "size_value": "size",
        "storlek": "size",
        "size_name": "size",
        # EAN / barcode
        "ean": "ean",
        "barcode": "ean",
        "gtin": "ean",
        "ean_code": "ean",
        "ean13": "ean",
        "streckkod": "ean",
        # Dimensions
        "dimensions": "dimensions",
        "dimension": "dimensions",
        "mått": "dimensions",
        "size_dimensions": "dimensions",
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


# At least one of these fields must be present for a source to be detected.
# Prevents generic feeds with common field names from matching specific schemas.
REQUIRED_FIELDS: dict[str, frozenset[str]] = {
    "shopify": frozenset({"variant sku", "body (html)", "variant price"}),
    "woocommerce": frozenset({"regular price", "brands"}),
    "google_shopping": frozenset({"google_product_category", "gtin", "size_system"}),
    "akeneo": frozenset({"label-en_us", "price-eur"}),
}


def detect_source(headers: list[str]) -> str:
    """Auto-detect the source system from CSV column headers.

    Scores each known schema by how many of its fields
    are present in the headers. Requires a minimum of 3
    matching fields and at least one source-specific required
    field to avoid false positives on generic feeds.

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
        required = REQUIRED_FIELDS.get(source, frozenset())
        if required and not (headers_lower & required):
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