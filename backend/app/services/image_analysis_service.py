"""Business logic for FeedPilot multimodal image analysis.

Orchestrates the image analysis pipeline:
  1. Fetch image bytes (from URL or direct upload)
  2. Validate size and media type
  3. Base64-encode the image
  4. Retrieve existing product data to give Claude context
  5. Call Claude Vision via ask_claude_vision()
  6. Parse and return a structured ImageAnalysisResponse
"""

import json

import httpx
from sqlalchemy.orm import Session

from app.core.ai import ask_claude_vision
from app.models.product import Product
from app.prompts.prompt_manager import get_prompt
from app.repositories.product_repository import (
    ProductRepository,
    get_product_repository,
)
from app.schemas.image_analysis import ImageAnalysisResponse, SuggestedEnrichment

PROMPT_NAME = "image_analysis_v4"
MAX_IMAGE_SIZE_MB = 5
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024

ALLOWED_MEDIA_TYPES: frozenset[str] = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/gif", "image/avif"}
)


def _coerce_int(value: object, default: int) -> int:
    """Best-effort integer conversion for model output."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_float(value: object, default: float) -> float:
    """Best-effort float conversion for model output."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: int | float, lower: int | float, upper: int | float) -> int | float:
    """Clamp a numeric value to a closed interval."""
    return max(lower, min(upper, value))


def _extract_json(text: str) -> dict:
    """Extract and parse the first JSON object from model output.

    Args:
        text: Raw model output string.

    Returns:
        Parsed dict from the JSON object.

    Raises:
        RuntimeError: If no JSON object boundaries are found.
        json.JSONDecodeError: If the extracted text is still malformed JSON.
    """
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise RuntimeError(
            f"Claude returnerade inget JSON-objekt. Svar: {text[:200]!r}"
        )
    json_str = text[start:end]
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        cleaned = json_str.replace("\n", " ").replace("\r", " ").replace("\t", " ")
        return json.loads(cleaned)


def _build_image_prompt(product: Product | None) -> str:
    """Build the Claude user message that pairs with the image.

    Embeds existing product data so Claude knows what is already
    captured and can focus suggestions on genuinely missing fields.

    Args:
        product: The parent Product ORM instance, or None if not found.

    Returns:
        A text prompt string describing the analysis task.
    """
    if product is None:
        product_context = "Ingen befintlig produktdata tillgänglig."
    else:
        product_context = (
            f"Titel: {product.title or 'saknas'}\n"
            f"Kategori: {product.category or 'saknas'}\n"
            f"Beskrivning: {product.description or 'saknas'}\n"
            f"Attribut: {json.dumps(product.attributes or {}, ensure_ascii=False)}"
        )

    return (
        "Analysera denna produktbild för e-commerce enrichment.\n\n"
        f"Befintlig produktdata:\n{product_context}\n\n"
        "Identifiera visuella attribut, bedöm bildkvalitet och föreslå "
        "konkreta förbättringar av produktdatan baserade enbart på vad "
        "du faktiskt kan se i bilden."
    )


def _parse_response(
    parsed: dict, sku_id: str, total_tokens: int
) -> ImageAnalysisResponse:
    """Map Claude's parsed JSON dict to an ImageAnalysisResponse.

    Args:
        parsed: Dict from _extract_json().
        sku_id: The product SKU this analysis belongs to.
        total_tokens: Token count from the AI response.

    Returns:
        Populated ImageAnalysisResponse instance.
    """
    raw_enrichments = parsed.get("suggested_enrichments") or []
    if not isinstance(raw_enrichments, list):
        raw_enrichments = []

    enrichments = [SuggestedEnrichment(**e) for e in raw_enrichments if isinstance(e, dict)]

    raw_quality_issues = parsed.get("quality_issues") or []
    if not isinstance(raw_quality_issues, list):
        raw_quality_issues = []
    quality_issues = [str(issue) for issue in raw_quality_issues]

    raw_detected_attributes = parsed.get("detected_attributes") or {}
    if not isinstance(raw_detected_attributes, dict):
        raw_detected_attributes = {}

    image_quality_score = _clamp(
        _coerce_int(parsed.get("image_quality_score", 0), 0),
        0,
        100,
    )
    overall_confidence = _clamp(
        _coerce_float(parsed.get("overall_confidence", 0.0), 0.0),
        0.0,
        1.0,
    )

    return ImageAnalysisResponse(
        sku_id=sku_id,
        detected_attributes=raw_detected_attributes,
        quality_issues=quality_issues,
        suggested_enrichments=enrichments,
        image_quality_score=image_quality_score,
        overall_confidence=overall_confidence,
        reasoning=parsed.get("reasoning", ""),
        total_tokens=total_tokens,
    )



class ImageAnalysisService:
    """Orchestrates Claude Vision analysis for product images."""

    def __init__(self, product_repo: ProductRepository) -> None:
        """Initialise the service with a product repository.

        Args:
            product_repo: Data-access layer for product lookups.
        """
        self._repo = product_repo

    def analyze_from_url(
        self, url: str, sku_id: str, db: Session
    ) -> ImageAnalysisResponse:
        """Fetch an image by URL and run Claude Vision analysis.

        Args:
            url: Publicly accessible image URL.
            sku_id: SKU of the product to enrich.
            db: Active SQLAlchemy database session.

        Returns:
            ImageAnalysisResponse with detected attributes and suggestions.

        Raises:
            ValueError: If the product is not found, image exceeds the size
                limit, or the media type is not supported.
            httpx.HTTPError: If the image URL is unreachable.
            RuntimeError: If Claude returns no JSON object.
            json.JSONDecodeError: If the response is malformed JSON.
        """
        response = httpx.get(url, timeout=10, follow_redirects=True)
        response.raise_for_status()

        image_bytes = response.content
        if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            raise ValueError(
                f"Bilden är {len(image_bytes) // (1024 * 1024):.1f} MB — "
                f"max {MAX_IMAGE_SIZE_MB} MB tillåtet."
            )

        content_type = response.headers.get("content-type", "image/jpeg")
        media_type = content_type.split(";")[0].strip()
        if media_type not in ALLOWED_MEDIA_TYPES:
            raise ValueError(
                f"Media-typ '{media_type}' stöds inte. "
                f"Tillåtna typer: {sorted(ALLOWED_MEDIA_TYPES)}"
            )

        return self._run_analysis(image_bytes, media_type, sku_id, db)

    def analyze_from_upload(
        self,
        image_bytes: bytes,
        media_type: str,
        sku_id: str,
        db: Session,
    ) -> ImageAnalysisResponse:
        """Run Claude Vision analysis on an uploaded image.

        Args:
            image_bytes: Raw image bytes from the upload.
            media_type: MIME type, e.g. 'image/jpeg'.
            sku_id: SKU of the product to enrich.
            db: Active SQLAlchemy database session.

        Returns:
            ImageAnalysisResponse with detected attributes and suggestions.

        Raises:
            ValueError: If image exceeds the size limit or media type
                is not supported.
            RuntimeError: If Claude returns no JSON object.
            json.JSONDecodeError: If the response is malformed JSON.
        """
        if len(image_bytes) > MAX_IMAGE_SIZE_BYTES:
            raise ValueError(
                f"Uppladdad bild är {len(image_bytes) // (1024 * 1024):.1f} MB — "
                f"max {MAX_IMAGE_SIZE_MB} MB tillåtet."
            )

        if media_type not in ALLOWED_MEDIA_TYPES:
            raise ValueError(
                f"Media-typ '{media_type}' stöds inte. "
                f"Tillåtna typer: {sorted(ALLOWED_MEDIA_TYPES)}"
            )

        return self._run_analysis(image_bytes, media_type, sku_id, db)

    def _run_analysis(
        self,
        image_bytes: bytes,
        media_type: str,
        sku_id: str,
        db: Session,
    ) -> ImageAnalysisResponse:
        """Shared pipeline: encode → fetch product → call Claude → parse.

        Args:
            image_bytes: Raw image bytes.
            media_type: Validated MIME type string.
            sku_id: Product SKU for context lookup.
            db: Active database session.

        Returns:
            Populated ImageAnalysisResponse.
        """
        product = self._repo.get_by_sku(sku_id, db)

        prompt = _build_image_prompt(product)
        system = get_prompt(PROMPT_NAME)

        ai_response = ask_claude_vision(
            image_data=image_bytes,
            prompt=prompt,
            system=system,
        )

        parsed = _extract_json(ai_response["answer"])
        return _parse_response(parsed, sku_id, ai_response["total_tokens"])


def get_image_analysis_service() -> ImageAnalysisService:
    """Dependency injection factory for ImageAnalysisService.

    Returns:
        A ready-to-use ImageAnalysisService instance.
    """
    return ImageAnalysisService(product_repo=get_product_repository())
