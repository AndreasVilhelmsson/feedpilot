"""ARQ background task definitions for FeedPilot.

Each function is an ARQ task executed by the worker process.
Tasks update the Job record in the database as they progress
so the API can report real-time status to clients.
"""

from datetime import datetime

from app.core.database import SessionLocal
from app.models.job import Job


async def enrich_bulk_task(
    ctx: dict,
    job_id: str,
    limit: int = 100,
) -> dict:
    """Enrich a batch of products as an ARQ background task.

    Fetches up to `limit` unenriched products, runs the full
    enrichment pipeline on each, and writes Job progress to
    the database after every product.

    Args:
        ctx: ARQ worker context (provided by ARQ, not used directly).
        job_id: Database ID of the Job record to update.
        limit: Maximum number of products to enrich in this run.

    Returns:
        Dict with 'processed' count and list of per-product 'errors'.

    Raises:
        Exception: Re-raised after marking the job as failed.
    """
    db = SessionLocal()
    try:
        job = db.query(Job).filter_by(id=job_id).first()
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()

        from app.repositories.product_repository import ProductRepository
        repo = ProductRepository()
        products = repo.get_unenriched(db, limit=limit)

        job.total = len(products)
        db.commit()

        from app.services.enrichment_service import EnrichmentService
        service = EnrichmentService(product_repo=repo)

        results: list[dict] = []
        errors: list[dict] = []

        for product in products:
            try:
                result = service.enrich_product(product.sku_id, db)
                results.append(result)
                job.processed += 1
            except Exception as exc:
                errors.append({"sku_id": product.sku_id, "error": str(exc)})
                job.failed += 1
            db.commit()

        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.result = {"processed": len(results), "errors": errors}
        db.commit()

        return {"processed": len(results), "errors": errors}

    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        job.completed_at = datetime.utcnow()
        db.commit()
        raise
    finally:
        db.close()


async def embed_all_task(ctx: dict, job_id: str) -> dict:
    """Create embeddings for all products as an ARQ background task.

    Runs EmbeddingService.embed_all_products() and updates the
    Job record with final counts and status.

    Args:
        ctx: ARQ worker context (provided by ARQ, not used directly).
        job_id: Database ID of the Job record to update.

    Returns:
        Dict with 'products_processed' and 'chunks_created' counts.

    Raises:
        Exception: Re-raised after marking the job as failed.
    """
    db = SessionLocal()
    try:
        job = db.query(Job).filter_by(id=job_id).first()
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()

        from app.services.embedding_service import EmbeddingService
        service = EmbeddingService()
        result = service.embed_all_products(db=db)

        job.total = result["products_processed"]
        job.processed = result["products_processed"]
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.result = result
        db.commit()

        return result

    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        job.completed_at = datetime.utcnow()
        db.commit()
        raise
    finally:
        db.close()
