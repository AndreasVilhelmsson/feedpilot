"""Database engine and session management for FeedPilot.

Uses SQLAlchemy 2.0 with connection pooling.
Sessions are managed via FastAPI dependency injection.
"""

from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import get_settings
from app.models.product import Base

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)


def create_tables() -> None:
    """Create all tables if they do not exist.

    Called once on application startup.
    """
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and ensure it is closed.

    Used as a FastAPI dependency via Depends(get_db).

    Yields:
        An active SQLAlchemy Session.
    """
    SessionLocal = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
    )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()