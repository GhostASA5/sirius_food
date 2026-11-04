import json
import time

from celery import Task
from redis.exceptions import RedisError

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.redis import get_redis_client


class DeadLetterTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        payload = json.dumps(
            {"task": self.name, "task_id": task_id, "args": args, "error": str(exc)},
            ensure_ascii=False,
        )
        try:
            get_redis_client().lpush("dlq", payload)
        except RedisError:
            pass
        super().on_failure(exc, task_id, args, kwargs, einfo)


def run_once(kind: str, order_id: int, work):
    cache = get_redis_client()
    key = f"order_task:{kind}:{order_id}"
    if not cache.set(key, "processing", nx=True, ex=3600):
        return f"{kind} already processed or in progress for order {order_id}"
    try:
        result = work()
        cache.setex(key, 3600, "done")
        return result
    except Exception:
        cache.delete(key)
        raise


task_options = {
    "base": DeadLetterTask,
    "autoretry_for": (Exception,),
    "retry_backoff": True,
    "retry_backoff_max": 600,
    "retry_jitter": True,
    "max_retries": 3,
}


@celery_app.task(**task_options)
def generate_order_pdf(order_id: int) -> str:
    def work():
        time.sleep(2)
        return f"PDF generated for order {order_id}"

    return run_once("pdf", order_id, work)


@celery_app.task(**task_options)
def send_order_email(order_id: int, email: str) -> str:
    def work():
        time.sleep(1)
        if get_settings().SIMULATE_EMAIL_FAILURES and order_id % 5 == 0:
            raise RuntimeError("Email service unavailable")
        return f"Email sent to {email} for order {order_id}"

    return run_once("email", order_id, work)


@celery_app.task(**task_options)
def send_order_sms(order_id: int, phone: str | None) -> str:
    def work():
        if phone is None:
            return f"SMS skipped for order {order_id}: no phone"
        time.sleep(1)
        return f"SMS sent to {phone} for order {order_id}"

    return run_once("sms", order_id, work)
