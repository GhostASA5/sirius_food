from typing import Protocol


class DeliveryRepositoryPort(Protocol):
    def get_order(self, order_id: int): ...
    def get_user(self, user_id: int): ...
    def get_active_by_courier(self, courier_id: int): ...
    def create(self, order_id: int, courier_id: int): ...
    def get_delivery(self, delivery_id: int): ...
    def save_completed(self, delivery, order): ...
    def list_by_courier(self, courier_id: int): ...


class DeliveryError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class DeliveryService:
    def __init__(self, repository: DeliveryRepositoryPort):
        self.repository = repository

    def assign(self, order_id: int, courier_id: int) -> int:
        order = self.repository.get_order(order_id)
        if order is None:
            raise DeliveryError("Заказ не найден", 404)
        if order.status != "paid":
            raise DeliveryError("Курьера можно назначить только на оплаченный заказ")
        courier = self.repository.get_user(courier_id)
        if courier is None:
            raise DeliveryError("Курьер не найден", 404)
        if courier.is_blocked:
            raise DeliveryError("Курьер заблокирован и не может быть назначен", 403)
        if courier.role.name != "courier":
            raise DeliveryError("Пользователь не является курьером")
        if self.repository.get_active_by_courier(courier_id):
            raise DeliveryError("У курьера уже есть активная доставка")
        return self.repository.create(order_id, courier_id).id

    def complete(
        self, delivery_id: int, current_user_id: int, actor_role: str = "courier"
    ) -> None:
        delivery = self.repository.get_delivery(delivery_id)
        if delivery is None:
            raise DeliveryError("Доставка не найдена", 404)
        if actor_role != "admin" and delivery.courier_id != current_user_id:
            raise DeliveryError("Access denied", 403)
        if delivery.status == "completed":
            raise DeliveryError("Доставка уже завершена")
        if delivery.status == "cancelled":
            raise DeliveryError("Отменённую доставку нельзя завершить")
        delivery.status = "completed"
        order = self.repository.get_order(delivery.order_id)
        if order is not None:
            order.status = "delivered"
        self.repository.save_completed(delivery, order)

    def get_delivery(self, delivery_id: int, actor_id: int, actor_role: str) -> dict:
        delivery = self.repository.get_delivery(delivery_id)
        if delivery is None:
            raise DeliveryError("Доставка не найдена", 404)
        order = self.repository.get_order(delivery.order_id)
        allowed = actor_role == "admin" or (
            actor_role == "courier" and delivery.courier_id == actor_id
        ) or (actor_role == "student" and order is not None and order.user_id == actor_id)
        if not allowed:
            raise DeliveryError("Access denied", 403)
        return self._data(delivery)

    def list_my_deliveries(self, courier_id: int) -> list[dict]:
        return [self._data(item) for item in self.repository.list_by_courier(courier_id)]

    @staticmethod
    def _data(delivery) -> dict:
        return {
            "id": delivery.id, "order_id": delivery.order_id,
            "courier_id": delivery.courier_id, "status": delivery.status,
        }
