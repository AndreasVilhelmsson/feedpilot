"""Variants router for FeedPilot.

Receives HTTP requests and delegates all logic to the appropriate
service or repository. No business logic lives here.

Routes (defined specific-before-dynamic to avoid path conflicts):
    POST /variants/ingest              — upsert a batch of variants
    POST /variants/enrich-all          — enrich all unenriched variants
    POST /variants/enrich/{variant_id} — enrich a single variant
    GET  /variants/{sku_id}            — list all variants for a product SKU
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.product import Product
from app.repositories.variant_repository import (
    VariantRepository,
    get_variant_repository,
)
from app.schemas.variant import (
    BulkVariantEnrichResponse,
    VariantCreateSchema,
    VariantEnrichResponse,
    VariantIngestResponse,
    VariantSchema,
)
from app.services.variant_enrichment_service import (
    VariantEnrichmentService,
    get_variant_enrichment_service,
)

router = APIRouter(
    prefix="/variants",
    tags=["variants"],
)


@router.post(
    "/ingest",
    response_model=VariantIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Importera produktvarianter",
    description=(
        "Tar emot en lista med varianter och upsertrar dem baserat på "
        "kombinationen förälder-SKU + färg + storlek. "
        "Returnerar antal skapade och uppdaterade varianter."
    ),
)
def ingest_variants(
    variants: list[VariantCreateSchema],
    db: Session = Depends(get_db),
    repo: VariantRepository = Depends(get_variant_repository),
) -> VariantIngestResponse:
    """Upsert a list of product variants into the database.

    Args:
        variants: List of validated VariantCreateSchema objects.
        db: Injected database session.
        repo: Injected VariantRepository.

    Returns:
        VariantIngestResponse with created/updated/total counts.

    Raises:
        HTTPException: 404 if a parent product SKU is not found.
        HTTPException: 500 if the upsert fails unexpectedly.
    """
    created = 0
    updated = 0

    try:
        for item in variants:
            product = (
                db.query(Product)
                .filter_by(sku_id=item.product_sku)
                .first()
            )
            if product is None:
                raise ValueError(
                    f"Förälderprodukten med sku_id='{item.product_sku}' "
                    f"hittades inte."
                )

            data = item.model_dump(exclude={"product_sku"})
            data["product_id"] = product.id

            _, was_created = repo.upsert(data, db)
            if was_created:
                created += 1
            else:
                updated += 1

        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Variant-ingest misslyckades: {exc}",
        ) from exc

    return VariantIngestResponse(
        created=created,
        updated=updated,
        total=created + updated,
    )


@router.post(
    "/enrich-all",
    response_model=BulkVariantEnrichResponse,
    status_code=status.HTTP_200_OK,
    summary="Enricha alla oenrichade varianter",
    description=(
        "Hämtar varianter där enriched_at IS NULL och kör SEO-enrichment "
        "pipeline upp till angiven gräns. Fel per variant samlas i 'errors'."
    ),
)
def enrich_all_variants(
    limit: int = Query(default=50, ge=1, le=200),
    service: VariantEnrichmentService = Depends(get_variant_enrichment_service),
    db: Session = Depends(get_db),
) -> BulkVariantEnrichResponse:
    """Enrich all unenriched variants up to the given limit.

    Args:
        limit: Maximum number of variants to process in this batch.
        service: Injected VariantEnrichmentService.
        db: Injected database session.

    Returns:
        BulkVariantEnrichResponse with processed count, results and errors.

    Raises:
        HTTPException: 500 if the batch call fails unexpectedly.
    """
    try:
        result = service.enrich_all_variants(db=db, limit=limit)
        return BulkVariantEnrichResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk variant enrichment misslyckades: {exc}",
        ) from exc


@router.post(
    "/enrich/{variant_id}",
    response_model=VariantEnrichResponse,
    status_code=status.HTTP_200_OK,
    summary="Enricha en specifik variant",
    description=(
        "Kör SEO-enrichment pipeline för varianten med givet ID: "
        "hämtar variant + förälderprodukten, anropar Claude med v3-prompten "
        "och sparar seo_title, seo_description, search_keywords och "
        "ai_search_snippet tillbaka på varianten."
    ),
)
def enrich_variant(
    variant_id: int,
    service: VariantEnrichmentService = Depends(get_variant_enrichment_service),
    db: Session = Depends(get_db),
) -> VariantEnrichResponse:
    """Enrich a single variant and return the SEO result.

    Args:
        variant_id: Primary key of the variant to enrich.
        service: Injected VariantEnrichmentService.
        db: Injected database session.

    Returns:
        VariantEnrichResponse with generated SEO copy and metadata.

    Raises:
        HTTPException: 404 if no variant with the given ID exists.
        HTTPException: 500 if the AI call or persistence fails.
    """
    try:
        result = service.enrich_variant(variant_id=variant_id, db=db)
        return VariantEnrichResponse(**result)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Claude returnerade ogiltig JSON: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Variant enrichment misslyckades: {exc}",
        ) from exc


@router.get(
    "/{sku_id}",
    response_model=list[VariantSchema],
    status_code=status.HTTP_200_OK,
    summary="Hämta alla varianter för ett produkt-SKU",
    description="Returnerar alla varianter kopplade till förälderprodukten med givet SKU.",
)
def get_variants_by_sku(
    sku_id: str,
    db: Session = Depends(get_db),
    repo: VariantRepository = Depends(get_variant_repository),
) -> list[VariantSchema]:
    """Return all variants for the product with the given SKU.

    Args:
        sku_id: The parent product's SKU identifier.
        db: Injected database session.
        repo: Injected VariantRepository.

    Returns:
        List of VariantSchema instances, possibly empty.

    Raises:
        HTTPException: 404 if no product with the given SKU exists.
    """
    product = db.query(Product).filter_by(sku_id=sku_id).first()
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produkt med sku_id='{sku_id}' hittades inte.",
        )

    variants = repo.get_by_product(product_id=product.id, db=db)
    return [VariantSchema.model_validate(v) for v in variants]
