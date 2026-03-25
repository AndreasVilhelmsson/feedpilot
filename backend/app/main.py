"""FeedPilot API entry point."""

from fastapi import FastAPI
from app.core.config import get_settings
from app.core.database import create_tables
from app.api.health import router as health_router
from app.api.analyze import router as analyze_router
from app.api.ingest import router as ingest_router
from app.api.embeddings import router as embeddings_router
from app.api.search import router as search_router
from app.api.enrich import router as enrich_router
from app.api.variants import router as variants_router
from app.api.images import router as images_router
from app.api.jobs import router as jobs_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)


@app.on_event("startup")
async def startup() -> None:
    """Create database tables on startup."""
    create_tables()


app.include_router(health_router, prefix="/api/v1")
app.include_router(analyze_router, prefix="/api/v1")
app.include_router(ingest_router, prefix="/api/v1")
app.include_router(embeddings_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(enrich_router, prefix="/api/v1")
app.include_router(variants_router, prefix="/api/v1")
app.include_router(images_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")


@app.get("/")
async def root() -> dict[str, str]:
    """Return a simple liveness message."""
    return {"message": "FeedPilot API is running"}