"""ARQ worker configuration for FeedPilot.

Defines Redis connection settings and the list of
registered task functions for the ARQ worker process.
"""

from arq.connections import RedisSettings

from app.core.config import get_settings
from app.workers.tasks import embed_all_task, enrich_bulk_task


def get_redis_settings() -> RedisSettings:
    """Return ARQ Redis connection settings from application config.

    Returns:
        RedisSettings configured from environment variables.
    """
    settings = get_settings()
    return RedisSettings(
        host=settings.redis_host,
        port=settings.redis_port,
    )


class WorkerSettings:
    """ARQ worker configuration."""

    functions = [enrich_bulk_task, embed_all_task]
    redis_settings = get_redis_settings()
    max_jobs = 10
    job_timeout = 3600  # 1 timme max per jobb
