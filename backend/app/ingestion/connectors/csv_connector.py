"""CSV connector for FeedPilot ingestion pipeline.

Reads raw CSV bytes and yields rows as dictionaries.
Handles encoding detection and BOM stripping.
"""

import csv
import io
from typing import Any


def read_csv(contents: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    """Decode and parse CSV bytes into headers and rows.

    Tries UTF-8 first, falls back to latin-1 for legacy feeds.
    Strips BOM characters from headers automatically.

    Args:
        contents: Raw CSV file bytes.

    Returns:
        A tuple of (headers, rows) where headers is a list
        of column names and rows is a list of raw dicts.

    Raises:
        ValueError: If the file has no headers or no rows.
    """
    try:
        decoded = contents.decode("utf-8-sig")
    except UnicodeDecodeError:
        decoded = contents.decode("latin-1")

    reader = csv.DictReader(io.StringIO(decoded))

    if not reader.fieldnames:
        raise ValueError("CSV-filen saknar kolumnrubriker.")

    headers = [h.strip() for h in reader.fieldnames]
    rows = [
        {k.strip(): v.strip() if isinstance(v, str) else v
         for k, v in row.items()}
        for row in reader
    ]

    if not rows:
        raise ValueError("CSV-filen innehåller inga produktrader.")

    return headers, rows