import asyncio
import json
import os
from uuid import uuid4

os.environ.setdefault("SECRET_KEY", "test-secret-that-has-at-least-32-characters")
os.environ.setdefault("DATABASE_URL", "sqlite://")

import aio_pika
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.event_handlers import handle_compensation, handle_delivery, handle_kitchen
from app.core.rabbitmq import DLX_NAME
from app.database import Base
from app.models import Delivery, KitchenOrder, MenuItem, Order, OutboxEvent, ProcessedEvent, Role, User
from app.modules.orders.repository import OrderRepository
from app.modules.orders.service import OrderError, OrderService
from app.workers import consumer


@pytest.fixture
def db_factory():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        student = Role(name="student")
        courier = Role(name="courier")
        db.add_all((student, courier))
        db.flush()
        db.add(User(email="buyer@example.com", role_id=student.id, balance=100))
        db.add(User(email="courier@example.com", role_id=courier.id, balance=0))
        db.add(MenuItem(name="Food", price=20, is_available=True))
        db.commit()
    yield factory
    engine.dispose()


def _paid_order(factory):
    with factory() as db:
        user = db.query(User).filter_by(email="buyer@example.com").one()
        order_id = OrderService(OrderRepository(db)).create_order(user.id, 1, 1)
        OrderService(OrderRepository(db)).pay_order(order_id, user.id)
        event = db.query(OutboxEvent).filter_by(routing_key="order.paid").one()
        return order_id, json.loads(event.payload)


def test_paid_event_reaches_both_handlers_once(db_factory):
    order_id, payload = _paid_order(db_factory)
    with db_factory() as db:
        with pytest.raises(OrderError):
            OrderService(OrderRepository(db)).pay_order(order_id, 999)
        with pytest.raises(OrderError):
            OrderService(OrderRepository(db)).pay_order(order_id, 1)
        assert db.query(OutboxEvent).filter_by(routing_key="order.paid").count() == 1
        assert handle_kitchen(db, payload)
        assert not handle_kitchen(db, payload)
        assert handle_delivery(db, payload)
        assert not handle_delivery(db, payload)
        assert [order.id for order in OrderRepository(db).get_kitchen_orders()] == [order_id]
        assert db.query(KitchenOrder).filter_by(order_id=order_id).count() == 1
        assert db.query(Delivery).filter_by(order_id=order_id).count() == 1
        assert db.query(ProcessedEvent).filter_by(id=payload["event_id"]).count() == 2


def test_saga_refunds_only_once_without_courier(db_factory):
    order_id, payload = _paid_order(db_factory)
    with db_factory() as db:
        courier = db.query(User).filter_by(email="courier@example.com").one()
        courier.is_blocked = True
        db.commit()
        assert handle_kitchen(db, payload)
        assert not handle_delivery(db, payload)
        failure = db.query(OutboxEvent).filter_by(routing_key="delivery.failed").one()
        failed_payload = json.loads(failure.payload)
        assert handle_compensation(db, failed_payload)
        assert not handle_compensation(db, failed_payload)
        second_failure = {**failed_payload, "event_id": str(uuid4())}
        assert not handle_compensation(db, second_failure)
        assert db.get(Order, order_id).status == "cancelled"
        assert db.query(User).filter_by(email="buyer@example.com").one().balance == 100
        assert db.query(KitchenOrder).filter_by(order_id=order_id).one().status == "cancelled"
        assert db.query(OutboxEvent).filter_by(routing_key="order.cancelled").count() == 1


def test_rabbitmq_consumer_and_dlq(db_factory, monkeypatch):
    monkeypatch.setattr(consumer, "SessionLocal", db_factory)
    order_id, payload = _paid_order(db_factory)

    async def scenario():
        try:
            connection = await aio_pika.connect_robust(
                "amqp://sirius:sirius@localhost:5672/", timeout=3
            )
        except (OSError, asyncio.TimeoutError):
            if os.environ.get("CI") == "true":
                raise
            pytest.skip("Локальный RabbitMQ недоступен")
        name = f"test_events_{uuid4().hex}"
        try:
            channel = await connection.channel()
            dlx = await channel.declare_exchange(
                DLX_NAME, aio_pika.ExchangeType.DIRECT, durable=True
            )
            dlq = await channel.declare_queue(f"{name}_dlq", auto_delete=True)
            await dlq.bind(dlx, routing_key=name)
            queue = await channel.declare_queue(
                name, auto_delete=True,
                arguments={"x-dead-letter-exchange": DLX_NAME,
                           "x-dead-letter-routing-key": name},
            )
            for body in (json.dumps(payload).encode(), json.dumps(payload).encode(), b"not-json"):
                await channel.default_exchange.publish(
                    aio_pika.Message(body=body), routing_key=name
                )
                message = await queue.get(timeout=3)
                await consumer.process_message(message, "kitchen", channel)
            dead = None
            for _ in range(30):
                dead = await dlq.get(fail=False, timeout=3)
                if dead is not None:
                    break
                await asyncio.sleep(0.1)
            assert dead is not None
            assert dead.body == b"not-json"
            await dead.ack()
            await queue.delete()
            await dlq.delete()
        finally:
            await connection.close()

    asyncio.run(scenario())
    with db_factory() as db:
        assert db.query(KitchenOrder).filter_by(order_id=order_id).count() == 1
