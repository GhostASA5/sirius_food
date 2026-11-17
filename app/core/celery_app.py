from celery import Celery
from kombu import Exchange, Queue

from app.core.config import get_settings


settings = get_settings()
celery_app = Celery(
    "sirius_food",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.orders", "app.tasks.loyalty"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",
    task_queues=(
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("dlq", Exchange("dlq"), routing_key="dlq"),
    ),
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,
    beat_schedule={"expire-promos-hourly": {"task": "loyalty.expire_promos", "schedule": 3600}},
)
