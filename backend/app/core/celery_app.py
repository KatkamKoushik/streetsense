import asyncio
import logging
from celery import Celery
from celery.schedules import crontab
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.db.repositories import TelemetryRepository

logger = logging.getLogger("streetsense.celery")

celery_app = Celery(
    "streetsense",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    beat_schedule={
        "purge-expired-telemetry-daily": {
            "task": "app.core.celery_app.purge_expired_telemetry",
            "schedule": crontab(hour=3, minute=0),  # Run daily at 03:00 UTC
        },
    }
)


@celery_app.task(name="app.core.celery_app.purge_expired_telemetry")
def purge_expired_telemetry(retention_days: int = None):
    """
    Background worker task to enforce privacy retention policy (Checklist 43-B002).
    Purges raw sensor snapshots and fine-grained location records older than retention threshold.
    """
    days = retention_days or settings.DATA_RETENTION_DAYS
    logger.info(f"Executing retention policy purge for records older than {days} days...")

    async def _purge():
        async with AsyncSessionLocal() as session:
            repo = TelemetryRepository(session)
            purged_count = await repo.purge_expired_records(days)
            logger.info(f"Retention purge complete: purged {purged_count} expired records.")
            return purged_count

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(_purge())).result()
    else:
        return asyncio.run(_purge())


@celery_app.task(name="app.core.celery_app.health_ping")
def health_ping():
    """Worker liveness verification task."""
    return {"status": "ok", "service": "streetsense-celery-worker"}
