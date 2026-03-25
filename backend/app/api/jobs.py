"""Jobs router for FeedPilot.

Provides endpoints for querying the status of background
worker jobs queued via the ARQ async pipeline.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.job import Job
from app.schemas.job import JobResponse

router = APIRouter(
    prefix="/jobs",
    tags=["jobs"],
)


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    status_code=status.HTTP_200_OK,
    summary="Hämta status för ett bakgrundsjobb",
    description=(
        "Returnerar aktuell status, progress och tidsstämplar "
        "för ett specifikt jobb. Polla detta endpoint för att "
        "följa ett asynkront jobb i realtid."
    ),
)
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
) -> JobResponse:
    """Return the current status of a background job.

    Args:
        job_id: UUID of the job to look up.
        db: Injected database session.

    Returns:
        JobResponse with status, progress counters and timing.

    Raises:
        HTTPException: 404 if no job with the given ID exists.
    """
    job = db.query(Job).filter_by(id=job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Jobb '{job_id}' hittades inte.",
        )
    return JobResponse.model_validate(job)
