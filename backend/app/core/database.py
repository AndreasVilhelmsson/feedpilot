"""Database engine and session management for FeedPilot.

Uses SQLAlchemy 2.0 with connection pooling.
Sessions are managed via FastAPI dependency injection.
"""

from collections.abc import Generator
from sqlalchemy import create_engine, text
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

# Module-level session factory — used by both FastAPI (via get_db)
# and ARQ worker tasks that manage their own session lifecycle.
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def create_tables() -> None:
    """Create all tables and enable pgvector extension.

    Called once on application startup.
    """
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()

    from app.models.embedding import ProductEmbedding  # noqa: F401
    from app.models.analysis_result import AnalysisResult  # noqa: F401
    from app.models.variant import ProductVariant  # noqa: F401
    from app.models.customer_pim_config import CustomerPIMConfig  # noqa: F401
    from app.models.job import Job  # noqa: F401
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and ensure it is closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()