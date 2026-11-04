import json
from collections.abc import Callable

from redis.exceptions import LockError, RedisError
from sqlalchemy.orm import Session

from app.core.redis import get_redis_client
from app.models import MenuCategory, MenuItem


class MenuRepository:
    def __init__(self, db: Session, cache=None):
        self.db = db
        self.cache = cache if cache is not None else get_redis_client()

    def _cached(self, key: str, ttl: int, load: Callable):
        try:
            cached = self.cache.get(key)
            if cached is not None:
                return json.loads(cached)
            with self.cache.lock(f"{key}:lock", timeout=30, blocking_timeout=30):
                cached = self.cache.get(key)
                if cached is not None:
                    return json.loads(cached)
                value = load()
                self.cache.setex(key, ttl, json.dumps(value, ensure_ascii=False))
                return value
        except (RedisError, LockError, json.JSONDecodeError):
            return load()

    def _invalidate(self, *keys: str) -> None:
        try:
            self.cache.delete(*keys)
        except RedisError:
            pass

    @staticmethod
    def _item_data(item: MenuItem) -> dict:
        return {
            "id": item.id,
            "name": item.name,
            "price": item.price,
            "is_available": item.is_available,
            "category_id": item.category_id,
        }

    def get_all(self) -> list[dict]:
        return self._cached(
            "menu:all",
            300,
            lambda: [
                self._item_data(item)
                for item in self.db.query(MenuItem).order_by(MenuItem.id).all()
            ],
        )

    def warm_all(self) -> None:
        self.get_all()

    def get_category_with_items(self, category_id: int) -> dict | None:
        def load():
            category = self.get_category(category_id)
            if category is None:
                return None
            items = self.db.query(MenuItem).filter(
                MenuItem.category_id == category_id
            ).order_by(MenuItem.id).all()
            return {
                "id": category.id,
                "name": category.name,
                "items": [self._item_data(item) for item in items],
            }

        return self._cached(f"menu:category:{category_id}", 600, load)

    def get_by_id(self, item_id: int):
        return self.db.query(MenuItem).filter(MenuItem.id == item_id).first()

    def get_category(self, category_id: int):
        return self.db.query(MenuCategory).filter(MenuCategory.id == category_id).first()

    def get_category_by_name(self, name: str):
        return self.db.query(MenuCategory).filter(MenuCategory.name == name).first()

    def create_category(self, name: str):
        category = MenuCategory(name=name)
        self.db.add(category)
        self.db.commit()
        self.db.refresh(category)
        self._invalidate(f"menu:category:{category.id}")
        return category

    def get_by_name(self, name: str):
        return self.db.query(MenuItem).filter(MenuItem.name == name).first()

    def create(self, name: str, price: float, category_id: int | None = None):
        item = MenuItem(name=name, price=price, is_available=True, category_id=category_id)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        keys = ["menu:all"]
        if category_id is not None:
            keys.append(f"menu:category:{category_id}")
        self._invalidate(*keys)
        return item

    def save(self, item, previous_category_id: int | None = None):
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        keys = ["menu:all"]
        for category_id in {item.category_id, previous_category_id}:
            if category_id is not None:
                keys.append(f"menu:category:{category_id}")
        self._invalidate(*keys)
