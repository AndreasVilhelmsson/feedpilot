from fastapi import APIRouter
from app.core.config import get_settings

router = APIRouter()

@router.get("/health")
def health_check():
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version
    }