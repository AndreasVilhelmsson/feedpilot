"""Data quality validators for FeedPilot ingestion pipeline.

Validates a CanonicalProduct and appends structured quality warnings.
Does not raise exceptions — never blocks ingestion.
The goal is to flag problems, not stop the pipeline.
"""

import re

from app.schemas.canonical import CanonicalProduct

TITLE_MIN_LENGTH: int = 10
TITLE_MAX_LENGTH: int = 200
DESCRIPTION_MIN_LENGTH: int = 20

VALID_SIZE_SYSTEMS: frozenset[str] = frozenset({"EU", "US", "UK", "INT"})
VALID_EAN_LENGTHS: frozenset[int] = frozenset({8, 13})


def _warn(
    warnings: list[dict[str, str]],
    field: str,
    severity: str,
    message: str,
) -> None:
    """Append a structured warning entry to the warnings list.

    Args:
        warnings: Mutable list to append to.
        field: The problematic field name.
        severity: 'high', 'medium' or 'low'.
        message: Human-readable description of the issue.
    """
    warnings.append({"field": field, "severity": severity, "message": message})


def validate_row(product: CanonicalProduct) -> CanonicalProduct:
    """Validate a CanonicalProduct and attach quality warnings.

    Existing warnings on the product are preserved; new ones are appended.

    Args:
        product: Normalised CanonicalProduct from the normalizer.

    Returns:
        CanonicalProduct with quality_warnings updated in place.
    """
    warnings: list[dict[str, str]] = list(product.quality_warnings)

    # --- SKU ---
    if not product.sku_id:
        _warn(warnings, "sku_id", "high", "SKU saknas — raden kan inte importeras.")

    # --- Title ---
    title = product.title
    if not title:
        _warn(warnings, "title", "high", "Produkttitel saknas.")
    elif len(title) < TITLE_MIN_LENGTH:
        _warn(
            warnings,
            "title",
            "high",
            f"Titeln är för kort ({len(title)} tecken). Minimum {TITLE_MIN_LENGTH} tecken.",
        )
    elif len(title) > TITLE_MAX_LENGTH:
        _warn(
            warnings,
            "title",
            "medium",
            f"Titeln är för lång ({len(title)} tecken). Maximum {TITLE_MAX_LENGTH} tecken.",
        )

    # --- Description ---
    description = product.description
    if not description:
        _warn(warnings, "description", "high", "Produktbeskrivning saknas.")
    elif len(description) < DESCRIPTION_MIN_LENGTH:
        _warn(
            warnings,
            "description",
            "medium",
            f"Beskrivningen är för kort ({len(description)} tecken).",
        )

    # --- Category ---
    if not product.category:
        _warn(warnings, "category", "medium", "Kategori saknas.")

    # --- Price ---
    if product.price is None:
        _warn(warnings, "price", "low", "Pris saknas eller kunde inte tolkas.")
    elif product.price <= 0:
        _warn(
            warnings,
            "price",
            "medium",
            f"Priset måste vara ett positivt tal (fick {product.price}).",
        )

    # --- EAN ---
    if product.ean is not None:
        ean = product.ean.strip()
        if not re.fullmatch(r"\d+", ean):
            _warn(warnings, "ean", "medium", "EAN får bara innehålla siffror.")
        elif len(ean) not in VALID_EAN_LENGTHS:
            _warn(
                warnings,
                "ean",
                "medium",
                f"EAN måste vara 8 eller 13 siffror (fick {len(ean)}).",
            )

    # --- Dimensions ---
    if product.dimensions is not None:
        dims = product.dimensions
        for dim_name, dim_value in [
            ("width", dims.width),
            ("depth", dims.depth),
            ("height", dims.height),
        ]:
            if dim_value is not None and dim_value <= 0:
                _warn(
                    warnings,
                    f"dimensions.{dim_name}",
                    "medium",
                    f"Dimensionen {dim_name} måste vara > 0 (fick {dim_value}).",
                )

    # --- Size system ---
    if product.size_system is not None and product.size_system not in VALID_SIZE_SYSTEMS:
        _warn(
            warnings,
            "size_system",
            "low",
            f"Okänt storlekssystem '{product.size_system}'. Giltiga: {', '.join(sorted(VALID_SIZE_SYSTEMS))}.",
        )

    product.quality_warnings = warnings
    return product
