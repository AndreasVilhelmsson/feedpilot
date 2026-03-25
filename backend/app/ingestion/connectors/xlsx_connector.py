"""Excel connector for FeedPilot ingestion pipeline.

Reads raw .xlsx bytes and yields rows as dictionaries,
matching the same contract as csv_connector.read_csv().
"""

from datetime import datetime
from io import BytesIO
from typing import Any

import openpyxl


def _coerce_to_str(value: Any) -> str:
    """Coerce a cell value to a clean string.

    Handles None, int, float, datetime and generic str.
    Floats that are whole numbers are returned without decimals.

    Args:
        value: Raw cell value from openpyxl.

    Returns:
        String representation; empty string for None.
    """
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value).strip()


def read_xlsx(contents: bytes) -> tuple[list[str], list[dict[str, Any]]]:
    """Decode and parse .xlsx bytes into headers and rows.

    Reads the active worksheet. The first non-empty row is
    treated as the header row. Completely empty rows are skipped.
    All cell values are coerced to str via _coerce_to_str().

    Args:
        contents: Raw .xlsx file bytes.

    Returns:
        A tuple of (headers, rows) where headers is a list
        of column names and rows is a list of raw dicts.

    Raises:
        ValueError: If the file has no headers or no data rows.
    """
    wb = openpyxl.load_workbook(BytesIO(contents), read_only=True, data_only=True)
    ws = wb.active

    rows_iter = ws.iter_rows(values_only=True)

    header_row = next(rows_iter, None)
    if not header_row or all(v is None for v in header_row):
        raise ValueError("Excel-filen saknar kolumnrubriker.")

    headers: list[str] = [
        str(h).strip() for h in header_row if h is not None
    ]

    rows: list[dict[str, Any]] = []
    for row in rows_iter:
        if all(v is None for v in row):
            continue
        row_dict: dict[str, str] = {
            header: _coerce_to_str(row[idx] if idx < len(row) else None)
            for idx, header in enumerate(headers)
        }
        rows.append(row_dict)

    wb.close()

    if not rows:
        raise ValueError("Excel-filen innehåller inga produktrader.")

    return headers, rows
