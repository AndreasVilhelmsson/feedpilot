"""SQLAlchemy job model for FeedPilot async pipeline.

Tracks status, progress and timing of background worker jobs.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text

from app.models.product import Base


class Job(Base):
    """Background job record for async pipeline operations.

    Stores job type, current status, progress counters and
    timing so the API can report progress to clients.
    """

    __tablename__ = "jobs"

    id: str = Column(String, primary_key=True)
    job_type: str = Column(String, nullable=False)
    status: str = Column(String, default="queued", nullable=False)
    total: int = Column(Integer, default=0)
    processed: int = Column(Integer, default=0)
    failed: int = Column(Integer, default=0)
    error: str | None = Column(Text, nullable=True)
    result: dict | None = Column(JSON, nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    started_at: datetime | None = Column(DateTime, nullable=True)
    completed_at: datetime | None = Column(DateTime, nullable=True)

    @property
    def progress_pct(self) -> float:
        """Calculate completion percentage.

        Returns:
            Progress as a float between 0.0 and 100.0.
        """
        if self.total == 0:
            return 0.0
        return round(self.processed / self.total * 100, 1)

    @property
    def estimated_seconds_remaining(self) -> int | None:
        """Estimate remaining seconds based on elapsed time and rate.

        Returns:
            Estimated seconds remaining, or None if not enough data.
        """
        if not self.started_at or self.processed == 0:
            return None
        elapsed = (datetime.utcnow() - self.started_at).seconds
        if elapsed == 0:
            return None
        rate = self.processed / elapsed
        remaining = self.total - self.processed
        return int(remaining / rate) if rate > 0 else None

    def __repr__(self) -> str:
        """Return string representation for debugging."""
        return f"<Job id={self.id} type={self.job_type} status={self.status}>"
