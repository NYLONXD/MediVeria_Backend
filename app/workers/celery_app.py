from celery import Celery
from celery.signals import worker_process_init

from app.core.config import settings

celery_app = Celery(
    "mediveria",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_acks_late=True,            # don't lose a job if a worker crashes mid-task
    worker_prefetch_multiplier=1,   # one job at a time per worker — safer for medical data than batching
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    result_expires=3600,
    timezone="UTC",
    enable_utc=True,
)


@worker_process_init.connect
def _reset_db_engine_after_fork(**kwargs):
    """Celery's default (prefork) pool forks worker subprocesses. SQLAlchemy
    connections opened before the fork are unsafe to share across the
    parent/child boundary — without this, workers eventually throw random
    'connection already closed' errors under load. Disposing here forces
    each forked worker to open its own fresh connections."""
    from app.db.database import engine
    engine.dispose()


# Importing this registers the @celery_app.task functions defined there.
# Safe against the celery_app <-> tasks circular import: whichever module
# is imported first, task registration completes correctly because the
# @celery_app.task decorator only needs `celery_app` to exist (it does,
# by the time this line runs) — not for `tasks` to be fully loaded yet.
from app.workers import tasks  # noqa: E402,F401