import asyncio
import json
import logging

import aio_pika

from app.core.event_handlers import handle_compensation, handle_delivery, handle_kitchen
from app.core.rabbitmq import declare_topology, open_channel
from app.database import SessionLocal
from app.core.observability import message_context, capture_error
from app.modules.loyalty.events import handle_earn, handle_loyalty_cancellation, handle_promo_cancellation


LOG = logging.getLogger(__name__)
HANDLERS = {
    "kitchen": handle_kitchen,
    "delivery": handle_delivery,
    "compensation": handle_compensation,
    "loyalty_earn": handle_earn,
    "loyalty_cancel": handle_loyalty_cancellation,
    "promo_restore": handle_promo_cancellation,
}
MAX_RETRIES = 3


async def process_message(message, kind, channel):
    with message_context(message.headers, f"{kind}.consume") as span:
        span.set_attribute("messaging.destination.name", f"{kind}_queue")
        await _process_message(message, kind, channel)


async def _process_message(message, kind, channel):
    try:
        payload = json.loads(message.body)
        if not isinstance(payload, dict):
            raise ValueError("Событие должно быть объектом JSON")
        with SessionLocal() as db:
            result = HANDLERS[kind](db, payload)
        LOG.info("order_received", extra={"order_id": payload["order_id"], "consumer": kind, "processed": result})
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        LOG.warning("Сообщение отправлено в DLQ: %s", exc)
        await message.reject(requeue=False)
        return
    except Exception as exc:
        capture_error(exc)
        LOG.exception("Ошибка обработки события %s", kind)
        retries = int(message.headers.get("x-retries", 0))
        if retries >= MAX_RETRIES:
            await message.reject(requeue=False)
            return
        retry = aio_pika.Message(
            body=message.body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
            headers={**message.headers, "x-retries": retries + 1},
        )
        try:
            await channel.default_exchange.publish(retry, routing_key=f"{kind}_queue")
        except Exception:
            await message.nack(requeue=True)
            return
        await message.ack()
        return
    await message.ack()


async def run_consumer(kind):
    connection, channel = await open_channel()
    try:
        await declare_topology(channel)
        queue = await channel.get_queue(f"{kind}_queue")
        await queue.consume(lambda message: process_message(message, kind, channel))
        LOG.info("Ожидание сообщений в %s_queue", kind)
        await asyncio.Future()
    finally:
        await connection.close()
