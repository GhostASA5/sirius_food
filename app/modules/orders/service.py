from decimal import Decimal
from typing import Protocol
from uuid import uuid4

from app.modules.loyalty.service import LoyaltyService, ZERO, money


class OrderRepositoryPort(Protocol):
    def get_user_by_id(self, user_id: int): ...
    def get_menu_item_by_id(self, item_id: int): ...
    loyalty: object
    def place_order(self, user, item, quantity, amount, promo) -> int: ...
    def get_order_for_update(self, order_id: int): ...
    def save_paid_with_event(self, order, event_id, amount): ...
    def prepare_cancellation(self, order): ...
    def commit(self): ...
    def get_kitchen_orders(self): ...


class OrderNotificationsPort(Protocol):
    def enqueue_order_created(self, order_id: int, email: str, phone: str | None): ...


class OrderError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class OrderService:
    def __init__(
        self, repository: OrderRepositoryPort,
        notifications: OrderNotificationsPort | None = None,
    ):
        self.repository = repository
        self.notifications = notifications

    def create_order(self, user_id: int, item_id: int, quantity: int,
                     promo_code: str | None = None) -> int:
        if quantity <= 0:
            raise OrderError("Количество должно быть больше нуля")
        user = self.repository.get_user_by_id(user_id)
        if user is None:
            raise OrderError("Пользователь не найден", 404)
        item = self.repository.get_menu_item_by_id(item_id)
        if item is None:
            raise OrderError("Блюдо не найдено", 404)
        if not item.is_available:
            raise OrderError("Блюдо недоступно")
        amount = money(Decimal(str(item.price)) * quantity)
        promo = None
        if promo_code is not None:
            amount, promo = LoyaltyService(self.repository.loyalty).apply_promo(
                promo_code, user_id, amount
            )
        if money(user.balance) < amount:
            raise OrderError("Недостаточно средств на балансе студента")
        order_id = self.repository.place_order(user, item, quantity, amount, promo)
        if self.notifications is not None:
            self.notifications.enqueue_order_created(order_id, user.email, user.phone)
        return order_id

    def cancel_order(self, order_id: int, current_user_id: int, actor_role: str = "student") -> None:
        order = self.repository.get_order_for_update(order_id)
        if order is None:
            raise OrderError("Order not found", 404)
        if actor_role != "admin" and order.user_id != current_user_id:
            raise OrderError("Access denied", 403)
        if order.status in ("cancelled", "delivered"):
            raise OrderError("Order cannot be cancelled")
        self.repository.prepare_cancellation(order)
        self.repository.commit()

    def pay_order(self, order_id: int, current_user_id: int, actor_role: str = "student",
                  points: Decimal = ZERO) -> None:
        order = self.repository.get_order_for_update(order_id)
        if order is None:
            raise OrderError("Заказ не найден", 404)
        if actor_role != "admin" and order.user_id != current_user_id:
            raise OrderError("Access denied", 403)
        if order.status != "processing":
            raise OrderError("Оплатить можно только заказ в обработке")
        amount = money(order.total_amount if order.total_amount is not None
                       else Decimal(str(order.item.price)) * order.quantity)
        if points != ZERO:
            user = self.repository.get_user_by_id(order.user_id)
            if user is None:
                raise OrderError("Пользователь не найден", 404)
            LoyaltyService(self.repository.loyalty).spend(order, amount, points)
            user.balance = float(money(user.balance) + points)
            amount -= points
        self.repository.save_paid_with_event(order, str(uuid4()), amount)

    def get_kitchen_orders(self) -> list[dict]:
        return [
            {"id": order.id, "user_id": order.user_id, "item_id": order.item_id,
             "quantity": order.quantity, "status": order.status}
            for order in self.repository.get_kitchen_orders()
        ]
