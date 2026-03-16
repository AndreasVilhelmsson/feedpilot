"""Analyze router for FeedPilot.

Receives HTTP requests and delegates all logic
to AnalyzeService. No business logic lives here.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.analyze import AnalyzeRequest, AnalyzeResponse
from app.services.analyze_service import AnalyzeService, get_analyze_service

router = APIRouter(
    prefix="/analyze",
    tags=["analyze"],
)


@router.post(
    "",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Analysera en fråga om produktdata",
    description="Skickar en fråga till Claude och returnerar ett strukturerat svar.",
)
async def analyze(
    request: AnalyzeRequest,
    service: AnalyzeService = Depends(get_analyze_service),
) -> AnalyzeResponse:
    """Accept a question and return an AI-generated analysis.

    Args:
        request: Validated request body containing the question.
        service: Injected AnalyzeService instance.

    Returns:
        Claude's answer with token usage statistics.

    Raises:
        HTTPException: 500 if the AI call fails.
    """
    try:
        result = await service.analyze_question(request.question)
        return AnalyzeResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI-anropet misslyckades: {exc}",
        ) from exc