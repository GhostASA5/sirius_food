import json

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message

from app.core.config import get_settings


EXCHANGE_NAME = "sirius_events"
DLX_NAME = "dlx_exchange"


async def open_channel():
    connection = await aio_pika.connect_robust(get_settings().RABBITMQ_URL)
    channel = await connection.channel(publisher_confirms=True)
    await channel.set_qos(prefetch_count=10)
    return connection, channel


async def declare_topology(channel):
    exchange = await channel.declare_exchange(EXCHANGE_NAME, ExchangeType.TOPIC, durable=True)
    dlx = await channel.declare_exchange(DLX_NAME, ExchangeType.DIRECT, durable=True)
    for name, routing_key in (("kitchen", "order.paid"),
                              ("delivery", "order.paid"),
                              ("compensation", "delivery.failed")):
        dlq = await channel.declare_queue(f"{name}_dlq", durable=True)
        await dlq.bind(dlx, routing_key=f"{name}.dlq")
        queue = await channel.declare_queue(
            f"{name}_queue", durable=True,
            arguments={
                "x-dead-letter-exchange": DLX_NAME,
                "x-dead-letter-routing-key": f"{name}.dlq",
            },
        )
        await queue.bind(exchange, routing_key=routing_key)
    cancelled_queue = await channel.declare_queue("order_cancelled_queue", durable=True)
    await cancelled_queue.bind(exchange, routing_key="order.cancelled")


async def publish_event(channel, routing_key: str, payload: dict, event_id: str):
    exchange = await channel.declare_exchange(EXCHANGE_NAME, ExchangeType.TOPIC, durable=True)
    message = Message(
        body=json.dumps(payload).encode("utf-8"),
        message_id=event_id,
        delivery_mode=DeliveryMode.PERSISTENT,
        content_type="application/json",
    )
    await exchange.publish(message, routing_key=routing_key)
