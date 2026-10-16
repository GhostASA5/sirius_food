from typing import Protocol


class UserRepositoryPort(Protocol):
    def get_by_email(self, email: str): ...
    def get_by_id(self, user_id: int): ...
    def create(self, email: str, phone: str | None): ...
    def save(self, user): ...


class UserError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class UserService:
    def __init__(self, repository: UserRepositoryPort):
        self.repository = repository

    def register(self, email: str, phone: str | None = None):
        if self.repository.get_by_email(email) is not None:
            raise UserError("Пользователь с таким email уже зарегистрирован")
        return self.repository.create(email, phone)

    def top_up_balance(self, user_id: int, amount: float) -> float:
        user = self.repository.get_by_id(user_id)
        if user is None:
            raise UserError("Пользователь не найден", 404)
        if user.is_blocked:
            raise UserError("Пользователь заблокирован. Пополнение невозможно", 403)
        if amount > 50000:
            raise UserError("Максимальная сумма пополнения — 50000 рублей")
        user.balance += amount
        self.repository.save(user)
        return user.balance
