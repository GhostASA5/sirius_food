from typing import Protocol


class OrderRepositoryPort(Protocol):
    def get_user_by_id(self, user_id: int): ...
    def get_menu_item_by_id(self, item_id: int): ...
    def place_order(self, user, item, quantity: int) -> int: ...
    def get_order(self, order_id: int): ...
    def save(self, order): ...
    def get_kitchen_orders(self): ...


class OrderError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class OrderService:
    def __init__(self, repository: OrderRepositoryPort):
        self.repository = repository

    def create_order(self, user_id: int, item_id: int, quantity: int) -> int:
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
        if user.balance < item.price * quantity:
            raise OrderError("Недостаточно средств на балансе студента")
        return self.repository.place_order(user, item, quantity)

    def cancel_order(self, order_id: int, current_user_id: int) -> None:
        order = self.repository.get_order(order_id)
        if order is None:
            raise OrderError("Order not found", 404)
        if order.user_id != current_user_id:
            raise OrderError("Access denied", 403)
        if order.status in ("cancelled", "delivered"):
            raise OrderError("Order cannot be cancelled")
        order.status = "cancelled"
        self.repository.save(order)

    def get_kitchen_orders(self) -> list[dict]:
        return [
            {"id": order.id, "user_id": order.user_id, "item_id": order.item_id,
             "quantity": order.quantity, "status": order.status}
            for order in self.repository.get_kitchen_orders()
        ]
