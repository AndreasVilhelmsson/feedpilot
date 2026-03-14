from fastapi import FastAPI
from app.core.config import get_settings
from app.api.health import router as health_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug
)

app.include_router(health_router, prefix="/api/v1")

@app.get("/")
def root():
    return {"message": "FeedPilot API is running"}

## Steg 4 — .env.example

