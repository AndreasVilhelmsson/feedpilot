"""Pydantic schemas for FeedPilot job tracking API.

Defines request and response shapes for GET /jobs/{job_id}
and the EnqueueResponse returned when a job is queued.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobResponse(BaseModel):
    """Response schema for a single job status query."""

    id: str
    job_type: str
    status: str
    total: int
    processed: int
    failed: int
    progress_pct: float
    estimated_seconds_remaining: int | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class EnqueueResponse(BaseModel):
    """Response returned when an async job is successfully queued."""

    job_id: str
    status: str = "queued"
    message: str
