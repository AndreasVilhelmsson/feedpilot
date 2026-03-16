"""Business logic for product feed ingestion.

Orchestrates the full ingestion pipeline:
connector → mapping → normalization → validation → persistence.
"""

from typing import Any
from sqlalchemy.orm import Session
from app.ingestion.connectors.csv_connector import read_csv
from app.ingestion.mapping.field_mapper import FieldMapper
from app.ingestion.normalizer import normalize_row
from app.ingestion.validators import validate_row
from app.models.product import Product


class IngestionService:
    """Orchestrates the full product feed ingestion pipeline."""

    def ingest_csv(
        self,
        contents: bytes,
        feed_source: str,
        db: Session,
    ) -> dict[str, Any]:
        """Parse, map, normalize, validate and persist a CSV feed.

        Args:
            contents: Raw CSV file bytes.
            feed_source: Name of the source system, e.g. 'shopify'.
            db: Active database session.

        Returns:
            Ingestion statistics and quality warnings:
                total: Total rows processed.
                created: New products created.
                updated: Existing products updated.
                skipped: Rows skipped due to missing SKU.
                detected_source: Auto-detected source system.
                warnings: List of data quality warnings.
        """
        headers, rows = read_csv(contents)

        mapper = FieldMapper(
            source=feed_source if feed_source != "auto" else None
        )
        detected_source = mapper.fit(headers)

        created = updated = skipped = 0
        all_warnings: list[dict] = []

        for row in rows:
            mapped = mapper.transform_row(row)
            normalized = normalize_row(mapped)
            warnings = validate_row(normalized)

            sku_id = normalized.get("sku_id")
            if not sku_id:
                skipped += 1
                continue

            if warnings:
                all_warnings.append({
                    "sku_id": sku_id,
                    "warnings": warnings,
                })

            product_data = {
                "sku_id": sku_id,
                "title": normalized.get("title"),
                "description": normalized.get("description"),
                "category": normalized.get("category"),
                "price": normalized.get("price"),
                "attributes": normalized.get("attributes"),
                "raw_data": normalized.get("raw_data"),
                "feed_source": feed_source,
                "detected_source": detected_source,
                "quality_warnings": warnings,
            }

            existing = (
                db.query(Product)
                .filter_by(sku_id=sku_id)
                .first()
            )

            if existing:
                for field, value in product_data.items():
                    setattr(existing, field, value)
                updated += 1
            else:
                db.add(Product(**product_data))
                created += 1

        db.commit()

        return {
            "total": len(rows),
            "created": created,
            "updated": updated,
            "skipped": skipped,
            "detected_source": detected_source,
            "warnings": all_warnings,
        }


def get_ingestion_service() -> IngestionService:
    """Dependency injection factory for IngestionService.

    Returns:
        A ready-to-use IngestionService instance.
    """
    return IngestionService()