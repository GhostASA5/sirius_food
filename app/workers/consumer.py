import asyncio
import json
import logging

import aio_pika

from app.core.config import get_settings
from app.core.event_handlers import handle_compensation, handle_delivery, handle_kitchen
from app.core.rabbitmq import EXCHANGE_NAME, declare_topology, open_channel
from app.database import SessionLocal


LOG = logging.getLogger(__name__)
HANDLERS = {
    "kitchen": handle_kitchen,
    "delivery": handle_delivery,
    "compensation": handle_compensation,
}
MAX_RETRIES = 3


async def process_message(message, kind, channel):
    try:
        payload = json.loads(message.body)
        if not isinstance(payload, dict):
            raise ValueError("Событие должно быть объектом JSON")
        with SessionLocal() as db:
            result = HANDLERS[kind](db, payload)
        LOG.info("%s: заказ %s, обработано: %s", kind, payload["order_id"], result)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        LOG.warning("Сообщение отправлено в DLQ: %s", exc)
        await message.reject(requeue=False)
        return
    except Exception:
        LOG.exception("Ошибка обработки события %s", kind)
        retries = int(message.headers.get("x-retries", 0))
        if retries >= MAX_RETRIES:
            await message.reject(requeue=False)
            return
        retry = aio_pika.Message(
            body=message.body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
            headers={"x-retries": retries + 1},
        )
        try:
            exchange = await channel.get_exchange(EXCHANGE_NAME)
            await exchange.publish(retry, routing_key=(
                "delivery.failed" if kind == "compensation" else "order.paid"
            ))
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
