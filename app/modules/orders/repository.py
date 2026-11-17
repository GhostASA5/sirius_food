import json
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import Delivery, KitchenOrder, MenuItem, Order, OutboxEvent, User
from app.modules.loyalty.repository import LoyaltyRepository
from app.modules.loyalty.service import money


class OrderRepository:
    def __init__(self, db: Session):
        self.db = db
        self.loyalty = LoyaltyRepository(db)

    def get_user_by_id(self, user_id: int):
        return self.db.query(User).filter(User.id == user_id).populate_existing().with_for_update().first()

    def get_menu_item_by_id(self, item_id: int):
        return self.db.query(MenuItem).filter(MenuItem.id == item_id).first()

    def place_order(self, user, item, quantity: int, amount: Decimal, promo) -> int:
        order = Order(
            user_id=user.id, item_id=item.id, quantity=quantity,
            total_amount=amount, status="processing",
        )
        user.balance = float(money(user.balance) - amount)
        try:
            self.db.add(user)
            self.db.add(order)
            if promo is not None:
                self.db.flush()
                self.loyalty.record_usage(promo, order)
            self.db.commit()
            self.db.refresh(order)
        except Exception:
            self.db.rollback()
            raise
        return order.id

    def get_order(self, order_id: int):
        return self.db.query(Order).filter(Order.id == order_id).first()

    def get_order_for_update(self, order_id: int):
        return self.db.query(Order).filter(Order.id == order_id).with_for_update().first()

    def save_paid_with_event(self, order, event_id: str, amount: Decimal):
        order.status = "paid"
        order.total_amount = amount
        self._event(order, event_id, "order.paid", amount)
        self.db.commit()

    def _event(self, order, event_id, routing_key, amount):
        payload = {
            "event_id": event_id,
            "order_id": order.id,
            "customer_id": order.user_id,
            "amount": float(amount),
        }
        self.db.add(OutboxEvent(
            event_id=event_id, routing_key=routing_key, payload=json.dumps(payload)
        ))

    def prepare_cancellation(self, order, fallback_amount=None):
        amount = order.total_amount
        if amount is None:
            amount = fallback_amount if fallback_amount is not None else Decimal(str(order.item.price)) * order.quantity
        amount = money(amount)
        user = self.get_user_by_id(order.user_id)
        if user is not None:
            user.balance = float(money(user.balance) + amount)
        order.status = "cancelled"
        for model in (KitchenOrder, Delivery):
            record = self.db.query(model).filter_by(order_id=order.id).first()
            if record is not None:
                record.status = "cancelled"
        self._event(order, str(uuid4()), "order.cancelled", amount)

    def commit(self):
        self.db.commit()

    def get_kitchen_orders(self):
        return (
            self.db.query(Order).join(KitchenOrder, KitchenOrder.order_id == Order.id)
            .filter(KitchenOrder.status == "pending").all()
        )
