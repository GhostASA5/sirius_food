import asyncio
import json
import logging
from datetime import datetime, timezone

from app.core.rabbitmq import declare_topology, open_channel, publish_event
from app.database import SessionLocal
from app.models import OutboxEvent
from app.core.observability import message_context


LOG = logging.getLogger(__name__)


async def publish_pending(limit=100):
    connection, channel = await open_channel()
    published = 0
    try:
        await declare_topology(channel)
        with SessionLocal() as db:
            events = (
                db.query(OutboxEvent)
                .filter(OutboxEvent.published_at.is_(None))
                .order_by(OutboxEvent.id)
                .with_for_update(skip_locked=True)
                .limit(limit).all()
            )
            for event in events:
                try:
                    with message_context(json.loads(event.context or "{}"), "Outbox.publish"):
                        await publish_event(
                            channel, event.routing_key, json.loads(event.payload), event.event_id
                        )
                except Exception:
                    db.rollback()
                    raise
                event.published_at = datetime.now(timezone.utc)
                db.commit()
                published += 1
    finally:
        await connection.close()
    return published


async def main():
    while True:
        try:
            count = await publish_pending()
            if count:
                LOG.info("Опубликовано событий: %s", count)
        except Exception:
            LOG.exception("Публикация outbox не удалась; повтор через 2 секунды")
        await asyncio.sleep(2)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
