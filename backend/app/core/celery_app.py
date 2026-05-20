from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "mint",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.sync_tasks", "app.tasks.budget_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_routes={"app.tasks.sync_tasks.*": {"queue": "sync"}},
    beat_schedule={
        "check-budgets-daily": {
            "task": "check_budgets",
            "schedule": crontab(hour=9, minute=0),
        },
    },
)
