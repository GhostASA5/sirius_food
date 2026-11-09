import json

from sqlalchemy.orm import Session

from app.models import KitchenOrder, MenuItem, Order, OutboxEvent, User


class OrderRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_id(self, user_id: int):
        return self.db.query(User).filter(User.id == user_id).first()

    def get_menu_item_by_id(self, item_id: int):
        return self.db.query(MenuItem).filter(MenuItem.id == item_id).first()

    def place_order(self, user, item, quantity: int) -> int:
        order = Order(
            user_id=user.id, item_id=item.id, quantity=quantity,
            total_amount=item.price * quantity, status="processing",
        )
        user.balance -= item.price * quantity
        try:
            self.db.add(user)
            self.db.add(order)
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

    def save_paid_with_event(self, order, event_id: str, amount: float):
        order.status = "paid"
        payload = {
            "event_id": event_id,
            "order_id": order.id,
            "customer_id": order.user_id,
            "amount": amount,
        }
        self.db.add(OutboxEvent(
            event_id=event_id, routing_key="order.paid", payload=json.dumps(payload)
        ))
        self.db.commit()

    def save(self, order):
        self.db.add(order)
        self.db.commit()

    def get_kitchen_orders(self):
        return (
            self.db.query(Order).join(KitchenOrder, KitchenOrder.order_id == Order.id)
            .filter(KitchenOrder.status == "pending").all()
        )
