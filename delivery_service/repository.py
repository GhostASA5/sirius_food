from sqlalchemy.orm import Session

from app.models import Delivery, Order, User


class DeliveryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_order(self, order_id: int):
        return self.db.query(Order).filter(Order.id == order_id).first()

    def get_user(self, user_id: int):
        return self.db.query(User).filter(User.id == user_id).first()

    def get_active_by_courier(self, courier_id: int):
        return self.db.query(Delivery).filter(
            Delivery.courier_id == courier_id, Delivery.status == "in_progress"
        ).first()

    def create(self, order_id: int, courier_id: int):
        delivery = Delivery(order_id=order_id, courier_id=courier_id, status="in_progress")
        self.db.add(delivery)
        self.db.commit()
        self.db.refresh(delivery)
        return delivery

    def get_delivery(self, delivery_id: int):
        return self.db.query(Delivery).filter(Delivery.id == delivery_id).first()

    def get_delivery_by_order(self, order_id: int):
        return self.db.query(Delivery).filter(Delivery.order_id == order_id).first()

    def save_completed(self, delivery, order):
        self.db.add(delivery)
        if order is not None:
            self.db.add(order)
        self.db.commit()

    def list_by_courier(self, courier_id: int):
        return self.db.query(Delivery).filter(Delivery.courier_id == courier_id).all()
