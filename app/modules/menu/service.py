from typing import Protocol


class MenuRepositoryPort(Protocol):
    def get_by_id(self, item_id: int): ...
    def get_by_name(self, name: str): ...
    def create(self, name: str, price: float): ...
    def save(self, item): ...


class MenuError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class MenuService:
    def __init__(self, repository: MenuRepositoryPort):
        self.repository = repository

    def create(self, name: str, price: float) -> int:
        if self.repository.get_by_name(name) is not None:
            raise MenuError("Блюдо с таким названием уже существует")
        return self.repository.create(name, price).id

    def update(self, item_id: int, changes: dict) -> int:
        item = self.repository.get_by_id(item_id)
        if item is None:
            raise MenuError("Блюдо не найдено", 404)
        if "name" in changes and changes["name"] is not None:
            existing = self.repository.get_by_name(changes["name"])
            if existing is not None and existing.id != item_id:
                raise MenuError("Блюдо с таким названием уже существует")
        for key, value in changes.items():
            if value is not None:
                setattr(item, key, value)
        self.repository.save(item)
        return item.id
