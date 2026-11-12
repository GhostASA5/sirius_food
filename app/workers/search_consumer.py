import asyncio
import json
import logging

import aio_pika

from app.core.rabbitmq import declare_topology, open_channel
from app.database import SessionLocal
from app.models import MenuItem
from app.modules.search.repository import SearchRepository


LOG = logging.getLogger(__name__)


async def process_message(message):
    try:
        payload = json.loads(message.body)
        item_id = int(payload["item_id"])
        if item_id <= 0:
            raise ValueError("Некорректный item_id")
    except (ValueError, KeyError, TypeError):
        await message.reject(requeue=False)
        return
    try:
        with SessionLocal() as db:
            item = db.get(MenuItem, item_id)
            if item is None:
                raise ValueError("Блюдо не найдено")
            repository = SearchRepository()
            try:
                repository.index_item(item)
            finally:
                repository.close()
        await message.ack()
    except Exception:
        LOG.exception("Индексация блюда %s не удалась", item_id)
        retries = int(message.headers.get("x-retries", 0))
        if retries >= 3:
            await message.reject(requeue=False)
        else:
            channel = message.channel
            retry = aio_pika.Message(
                body=message.body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                headers={"x-retries": retries + 1},
            )
            try:
                exchange = await channel.get_exchange("sirius_events")
                await exchange.publish(retry, routing_key="menu.item.changed")
                await message.ack()
            except Exception:
                await message.nack(requeue=True)


async def main():
    connection, channel = await open_channel()
    try:
        await declare_topology(channel)
        queue = await channel.get_queue("search_queue")
        await queue.consume(process_message)
        await asyncio.Future()
    finally:
        await connection.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
