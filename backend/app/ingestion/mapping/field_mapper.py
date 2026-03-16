"""Field mapper for FeedPilot ingestion pipeline.

Applies a schema mapping to transform raw source rows
into FeedPilot's canonical internal format.
"""

from typing import Any
from app.ingestion.mapping.schema_registry import (
    get_schema,
    detect_source,
    CANONICAL_FIELDS,
)


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

    def transform_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Transform a single raw row to canonical format.

        Args:
            row: Raw row with source-specific field names.

        Returns:
            Row with canonical field names and an
            'attributes' dict for unmapped fields.

        Raises:
            RuntimeError: If fit() has not been called first.
        """
        if self._mapping is None:
            raise RuntimeError(
                "FieldMapper must be fitted before transforming rows. "
                "Call fit(headers) first."
            )

        canonical: dict[str, Any] = {field: None for field in CANONICAL_FIELDS}
        mapped_source_keys: set[str] = set()

        for source_key, value in row.items():
            canonical_key = self._mapping.get(source_key)
            if canonical_key:
                canonical[canonical_key] = value
                mapped_source_keys.add(source_key)

        # Unmapped fields become attributes
        canonical["attributes"] = {
            k: v for k, v in row.items()
            if k not in mapped_source_keys
        }

        # Always preserve raw data for traceability
        canonical["raw_data"] = dict(row)

        return canonical

    @property
    def source(self) -> str | None:
        """Return the detected or configured source system."""
        return self._source