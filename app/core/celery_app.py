from celery import Celery
from kombu import Exchange, Queue

from app.core.config import get_settings
from celery.signals import before_task_publish, task_prerun, task_postrun
from celery.signals import after_setup_logger
from app.core.observability import headers as context_headers, message_context
from app.core.observability import configure_worker_logging

after_setup_logger.connect(configure_worker_logging, weak=False)


settings = get_settings()


@before_task_publish.connect
def propagate_task(headers=None, **kwargs):
    if headers is not None:
        headers.update(context_headers())


@task_prerun.connect
def enter_task(task=None, **kwargs):
    task.observability_context = message_context(task.request.headers or {}, "Celery.consume")
    task.observability_context.__enter__()


@task_postrun.connect
def exit_task(task=None, **kwargs):
    context = getattr(task, "observability_context", None)
    if context is not None:
        context.__exit__(None, None, None)
celery_app = Celery(
    "sirius_food",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.orders", "app.tasks.loyalty"],
)
celery_app.conf.update(
    worker_hijack_root_logger=False,
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
