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
from app.schemas.canonical import CanonicalProduct


class IngestionService:
    """Orchestrates the full product feed ingestion pipeline."""

    def _canonical_to_model(self, canonical: CanonicalProduct) -> Product:
        """Convert a CanonicalProduct to a SQLAlchemy Product instance.

        All structured sub-fields (brand, color, material, size, gender)
        are merged into the product's attributes JSON column.

        Args:
            canonical: Validated CanonicalProduct from the pipeline.

        Returns:
            Unsaved Product ORM instance ready for database insertion.
        """
        attributes: dict[str, Any] = {
            k: v
            for k, v in {
                "brand": canonical.brand,
                "color": canonical.color,
                "material": canonical.material,
                "size": canonical.size,
                "size_system": canonical.size_system,
                "gender": canonical.gender,
                **canonical.extra_attributes,
            }.items()
            if v is not None
        }

        return Product(
            sku_id=canonical.sku_id,
            title=canonical.title,
            description=canonical.description,
            category=canonical.category,
            price=canonical.price,
            attributes=attributes,
            raw_data=canonical.raw_data,
            feed_source=canonical.feed_source,
            detected_source=canonical.detected_source,
            quality_warnings=canonical.quality_warnings,
        )

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
            try:
                canonical: CanonicalProduct = mapper.transform_row(row)
            except ValueError as exc:
                skipped += 1
                all_warnings.append({
                    "sku_id": "UNKNOWN",
                    "warnings": [{
                        "field": "sku_id",
                        "severity": "high",
                        "message": str(exc),
                    }],
                })
                continue

            canonical.feed_source = feed_source
            canonical = normalize_row(canonical)
            canonical = validate_row(canonical)

            if canonical.quality_warnings:
                all_warnings.append({
                    "sku_id": canonical.sku_id,
                    "warnings": canonical.quality_warnings,
                })

            existing = (
                db.query(Product)
                .filter_by(sku_id=canonical.sku_id)
                .first()
            )

            if existing:
                product = self._canonical_to_model(canonical)
                for field in (
                    "title", "description", "category", "price",
                    "attributes", "raw_data", "feed_source",
                    "detected_source", "quality_warnings",
                ):
                    setattr(existing, field, getattr(product, field))
                updated += 1
            else:
                db.add(self._canonical_to_model(canonical))
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
