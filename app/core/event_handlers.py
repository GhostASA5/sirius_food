import json
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from app.models import Delivery, KitchenOrder, Order, OutboxEvent, ProcessedEvent, Role, User


def _event(payload):
    event_id = payload["event_id"]
    order_id = payload["order_id"]
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("Некорректный event_id")
    if not isinstance(order_id, int) or order_id <= 0:
        raise ValueError("Некорректный order_id")
    return event_id, order_id


def _processed(db, consumer, event_id):
    return db.get(ProcessedEvent, (event_id, consumer)) is not None


def _mark(db, consumer, event_id):
    db.add(ProcessedEvent(id=event_id, consumer=consumer))


def _commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise


def handle_kitchen(db, payload):
    event_id, order_id = _event(payload)
    if _processed(db, "kitchen", event_id):
        return False
    order = db.get(Order, order_id)
    if order is None:
        raise ValueError("Заказ не найден")
    if order.status != "paid":
        _mark(db, "kitchen", event_id)
        _commit(db)
        return False
    if db.query(KitchenOrder).filter_by(order_id=order_id).first() is None:
        db.add(KitchenOrder(order_id=order_id, status="pending"))
    _mark(db, "kitchen", event_id)
    _commit(db)
    return True


def handle_delivery(db, payload):
    event_id, order_id = _event(payload)
    if _processed(db, "delivery", event_id):
        return False
    order = db.query(Order).filter_by(id=order_id).with_for_update().first()
    if order is None:
        raise ValueError("Заказ не найден")
    if order.status != "paid" or db.query(Delivery).filter_by(order_id=order_id).first():
        _mark(db, "delivery", event_id)
        _commit(db)
        return False
    courier_role = db.query(Role).filter_by(name="courier").one()
    active = db.query(Delivery.courier_id).filter_by(status="in_progress")
    courier = (
        db.query(User).filter(
            User.role_id == courier_role.id,
            User.is_blocked.is_(False),
            ~User.id.in_(active),
        ).order_by(User.id).with_for_update(skip_locked=True).first()
    )
    if courier is None:
        failure_id = str(uuid4())
        failed = {
            "event_id": failure_id, "order_id": order_id,
            "amount": payload["amount"], "reason": "no_courier",
        }
        db.add(OutboxEvent(
            event_id=failure_id, routing_key="delivery.failed", payload=json.dumps(failed)
        ))
    else:
        db.add(Delivery(order_id=order_id, courier_id=courier.id, status="in_progress"))
    _mark(db, "delivery", event_id)
    _commit(db)
    return courier is not None


def handle_compensation(db, payload):
    event_id, order_id = _event(payload)
    if _processed(db, "compensation", event_id):
        return False
    order = db.query(Order).filter_by(id=order_id).with_for_update().first()
    if order is None:
        raise ValueError("Заказ не найден")
    if order.status == "paid":
        user = db.query(User).filter_by(id=order.user_id).with_for_update().one()
        amount = order.total_amount if order.total_amount is not None else payload["amount"]
        user.balance += amount
        order.status = "cancelled"
        kitchen_order = db.query(KitchenOrder).filter_by(order_id=order_id).first()
        if kitchen_order is not None:
            kitchen_order.status = "cancelled"
        cancelled_id = str(uuid4())
        cancelled = {"event_id": cancelled_id, "order_id": order_id, "amount": amount}
        db.add(OutboxEvent(
            event_id=cancelled_id, routing_key="order.cancelled",
            payload=json.dumps(cancelled),
        ))
        compensated = True
    else:
        compensated = False
    _mark(db, "compensation", event_id)
    _commit(db)
    return compensated
