"""Images router for FeedPilot.

Receives HTTP requests for multimodal product image analysis and
delegates all logic to ImageAnalysisService. No business logic here.

Routes:
    POST /images/analyze-url      — analyse a publicly accessible image URL
    POST /images/analyze-upload/{sku_id} — analyse an uploaded image file
"""

import base64

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.image_analysis import ImageAnalysisRequest, ImageAnalysisResponse
from app.services.image_analysis_service import (
    ALLOWED_MEDIA_TYPES,
    ImageAnalysisService,
    get_image_analysis_service,
)

router = APIRouter(
    prefix="/images",
    tags=["images"],
)

_EXTENSION_TO_MEDIA_TYPE: dict[str, str] = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
    "avif": "image/avif",
}


@router.post(
    "/analyze-url",
    response_model=ImageAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analysera produktbild via URL",
    description=(
        "Hämtar bilden från den angivna URL:en, analyserar den med Claude Vision "
        "och returnerar detekterade attribut, bildkvalitetsproblem och "
        "enrichment-förslag för angivet SKU."
    ),
)
def analyze_url(
    request: ImageAnalysisRequest,
    service: ImageAnalysisService = Depends(get_image_analysis_service),
    db: Session = Depends(get_db),
) -> ImageAnalysisResponse:
    """Fetch an image by URL and return a structured analysis.

    Args:
        request: Validated request containing image URL and product SKU.
        service: Injected ImageAnalysisService instance.
        db: Injected database session.

    Returns:
        ImageAnalysisResponse with attributes, quality issues and suggestions.

    Raises:
        HTTPException: 400 if the image is too large or has unsupported type.
        HTTPException: 502 if the image URL cannot be reached.
        HTTPException: 500 if the AI analysis fails.
    """
    try:
        return service.analyze_from_url(
            url=str(request.url),
            sku_id=request.sku_id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        # Covers httpx.HTTPError and AI/parse failures
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bildanalys misslyckades: {exc}",
        ) from exc


@router.post(
    "/analyze-upload/{sku_id}",
    response_model=ImageAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analysera uppladdad produktbild",
    description=(
        "Tar emot en uppladdad bildfil (JPEG, PNG, WebP eller GIF), "
        "analyserar den med Claude Vision och returnerar enrichment-förslag "
        "för angivet SKU. Max filstorlek: 5 MB."
    ),
)
async def analyze_upload(
    sku_id: str,
    file: UploadFile = File(...),
    service: ImageAnalysisService = Depends(get_image_analysis_service),
    db: Session = Depends(get_db),
) -> ImageAnalysisResponse:
    """Accept an uploaded image file and return a structured analysis.

    Args:
        sku_id: Product SKU path parameter.
        file: The uploaded image file.
        service: Injected ImageAnalysisService instance.
        db: Injected database session.

    Returns:
        ImageAnalysisResponse with attributes, quality issues and suggestions.

    Raises:
        HTTPException: 400 if the file type is not supported or too large.
        HTTPException: 500 if the AI analysis fails.
    """
    content_type = file.content_type or ""
    media_type = content_type.split(";")[0].strip()

    # Fall back to extension-based detection if content_type is missing
    if media_type not in ALLOWED_MEDIA_TYPES and file.filename:
        ext = file.filename.rsplit(".", 1)[-1].lower()
        media_type = _EXTENSION_TO_MEDIA_TYPE.get(ext, media_type)

    if media_type not in ALLOWED_MEDIA_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Filtypen '{media_type}' stöds inte. "
                f"Tillåtna typer: jpeg, png, webp, gif."
            ),
        )

    image_bytes = await file.read()

    try:
        return service.analyze_from_upload(
            image_bytes=image_bytes,
            media_type=media_type,
            sku_id=sku_id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bildanalys misslyckades: {exc}",
        ) from exc
