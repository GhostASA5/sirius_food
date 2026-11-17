from datetime import datetime, timezone
import logging

from app.core.celery_app import celery_app
from app.database import SessionLocal
from app.modules.loyalty.repository import LoyaltyRepository


LOG = logging.getLogger(__name__)


@celery_app.task(name="loyalty.expire_promos")
def expire_promos():
    with SessionLocal() as db:
        count = LoyaltyRepository(db).expire(datetime.now(timezone.utc))
    LOG.info("Деактивировано истёкших промокодов: %s", count)
    return count
