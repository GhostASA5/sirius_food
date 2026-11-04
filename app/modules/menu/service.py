from typing import Protocol


class MenuRepositoryPort(Protocol):
    def get_by_id(self, item_id: int): ...
    def get_all(self): ...
    def get_category(self, category_id: int): ...
    def get_category_by_name(self, name: str): ...
    def create_category(self, name: str): ...
    def get_by_name(self, name: str): ...
    def create(self, name: str, price: float, category_id: int | None): ...
    def save(self, item): ...


class MenuError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class MenuService:
    def __init__(self, repository: MenuRepositoryPort):
        self.repository = repository

    def get_all(self) -> list[dict]:
        return [self._item_data(item) for item in self.repository.get_all()]

    def create_category(self, name: str) -> int:
        if self.repository.get_category_by_name(name) is not None:
            raise MenuError("Категория с таким названием уже существует")
        return self.repository.create_category(name).id

    def create(self, name: str, price: float, category_id: int | None = None) -> int:
        if self.repository.get_by_name(name) is not None:
            raise MenuError("Блюдо с таким названием уже существует")
        self._check_category(category_id)
        return self.repository.create(name, price, category_id).id

    def update(self, item_id: int, changes: dict) -> int:
        item = self.repository.get_by_id(item_id)
        if item is None:
            raise MenuError("Блюдо не найдено", 404)
        if "name" in changes and changes["name"] is not None:
            existing = self.repository.get_by_name(changes["name"])
            if existing is not None and existing.id != item_id:
                raise MenuError("Блюдо с таким названием уже существует")
        if "category_id" in changes:
            self._check_category(changes["category_id"])
        for key, value in changes.items():
            if value is not None:
                setattr(item, key, value)
        self.repository.save(item)
        return item.id

    def _check_category(self, category_id: int | None) -> None:
        if category_id is not None and self.repository.get_category(category_id) is None:
            raise MenuError("Категория не найдена", 404)

    @staticmethod
    def _item_data(item) -> dict:
        return {
            "id": item.id, "name": item.name, "price": item.price,
            "is_available": item.is_available, "category_id": item.category_id,
        }
