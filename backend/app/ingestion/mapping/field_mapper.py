"""Field mapper for FeedPilot ingestion pipeline.

Applies a schema mapping to transform raw source rows
into FeedPilot's canonical CanonicalProduct format.
"""

import re
from typing import Any

from app.ingestion.mapping.schema_registry import (
    CANONICAL_FIELDS,
    detect_source,
    get_schema,
)
from app.ingestion.normalizer import normalize_price, normalize_sku
from app.schemas.canonical import CanonicalDimensions, CanonicalProduct

# Regex alternation for dimension separators
DIMENSION_SEPARATORS: str = r"[*xX/|]"

# Recognised size systems
SIZE_SYSTEMS: frozenset[str] = frozenset({"EU", "US", "UK", "INT"})

_SIZE_SYSTEMS_PATTERN: str = "|".join(SIZE_SYSTEMS)


def _parse_dimensions(raw: str) -> CanonicalDimensions | None:
    """Parse a dimension string into a CanonicalDimensions instance.

    Supported separators: ``*``, ``x``, ``X``, ``/``, ``|``.
    Example: ``"70*30*10"`` → ``CanonicalDimensions(width=70, depth=30, height=10)``.

    Args:
        raw: Raw dimension string from source data.

    Returns:
        CanonicalDimensions if at least three numbers are parsed, else None.
    """
    parts = re.split(DIMENSION_SEPARATORS, str(raw).strip())
    numbers: list[float] = []
    for part in parts:
        cleaned = part.strip().replace(",", ".")
        try:
            numbers.append(float(cleaned))
        except ValueError:
            continue

    if len(numbers) >= 3:
        return CanonicalDimensions(
            width=numbers[0],
            depth=numbers[1],
            height=numbers[2],
        )
    return None


def _parse_size(raw: str) -> tuple[str | None, str | None]:
    """Parse a size string into (size_value, size_system).

    Examples::

        "42EU" → ("42", "EU")
        "EU42" → ("42", "EU")
        "US10" → ("10", "US")
        "42"   → ("42", None)

    Args:
        raw: Raw size string from source data.

    Returns:
        Tuple of (size_value, size_system). size_system is None when
        no recognised system suffix is found.
    """
    raw = raw.strip()

    # Digits followed by system: "42EU"
    m = re.match(
        rf"^(\d+(?:[.,]\d+)?)\s*({_SIZE_SYSTEMS_PATTERN})$",
        raw,
        re.IGNORECASE,
    )
    if m:
        return m.group(1), m.group(2).upper()

    # System followed by digits: "EU42"
    m = re.match(
        rf"^({_SIZE_SYSTEMS_PATTERN})\s*(\d+(?:[.,]\d+)?)$",
        raw,
        re.IGNORECASE,
    )
    if m:
        return m.group(2), m.group(1).upper()

    # Pure number: "42"
    if re.match(r"^\d+(?:[.,]\d+)?$", raw):
        return raw, None

    # Return as-is, no system detected
    return raw, None


class FieldMapper:
    """Maps source-specific field names to canonical fields.

    Supports both explicit source declaration and
    automatic source detection from CSV headers.
    """

    def __init__(self, source: str | None = None) -> None:
        """Initialize the mapper with an optional source system.

        Args:
            source: Known source system identifier.
                    If None, auto-detection is used.
        """
        self._source = source
        self._mapping: dict[str, str] | None = None

    def fit(self, headers: list[str]) -> str:
        """Detect or confirm the source and load its mapping.

        Args:
            headers: Column names from the source file.

        Returns:
            The detected or confirmed source system name.
        """
        if self._source:
            source = self._source
        else:
            source = detect_source(headers)

        self._mapping = get_schema(source)
        self._source = source
        return source

    def transform_row(self, row: dict[str, Any]) -> CanonicalProduct:
        """Transform a single raw row to a CanonicalProduct.

        Applies the loaded schema mapping, parses dimensions and size,
        and stores all unmapped fields in extra_attributes.

        Args:
            row: Raw row with source-specific field names.

        Returns:
            CanonicalProduct with canonical fields populated and an
            extra_attributes dict for unmapped fields.

        Raises:
            RuntimeError: If fit() has not been called first.
        """
        if self._mapping is None:
            raise RuntimeError(
                "FieldMapper must be fitted before transforming rows. "
                "Call fit(headers) first."
            )

        mapped: dict[str, Any] = {}
        mapped_source_keys: set[str] = set()

        for source_key, value in row.items():
            canonical_key = self._mapping.get(source_key)
            if canonical_key and canonical_key in CANONICAL_FIELDS:
                mapped[canonical_key] = value
                mapped_source_keys.add(source_key)

        # Parse size string into (value, system)
        raw_size = mapped.get("size")
        size_value, size_system = (
            _parse_size(str(raw_size)) if raw_size is not None else (None, None)
        )

        # Parse dimension string into CanonicalDimensions
        raw_dimensions = mapped.get("dimensions")
        dimensions = (
            _parse_dimensions(str(raw_dimensions))
            if raw_dimensions is not None
            else None
        )

        extra_attributes: dict[str, str] = {
            k: str(v) for k, v in row.items() if k not in mapped_source_keys
        }

        raw_sku = normalize_sku(mapped.get("sku_id"))
        if not raw_sku:
            raise ValueError(
                f"Rad saknar sku_id — kan inte importeras. "
                f"Raw data (första 5 fält): "
                f"{dict(list(row.items())[:5])}"
            )

        return CanonicalProduct(
            sku_id=raw_sku,
            detected_source=self._source or "generic_csv",
            title=str(mapped["title"]).strip() if mapped.get("title") else None,
            description=str(mapped["description"]).strip() if mapped.get("description") else None,
            brand=str(mapped["brand"]).strip() if mapped.get("brand") else None,
            category=str(mapped["category"]).strip() if mapped.get("category") else None,
            price=normalize_price(mapped.get("price")),
            color=str(mapped["color"]).strip() if mapped.get("color") else None,
            material=str(mapped["material"]).strip() if mapped.get("material") else None,
            size=size_value,
            size_system=size_system,
            dimensions=dimensions,
            ean=str(mapped["ean"]).strip() if mapped.get("ean") else None,
            extra_attributes=extra_attributes,
            raw_data=dict(row),
        )

    @property
    def source(self) -> str | None:
        """Return the detected or configured source system."""
        return self._source
