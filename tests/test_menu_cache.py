from concurrent.futures import ThreadPoolExecutor
from time import sleep

from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.database import Base
from app.models import MenuCategory, MenuItem
from app.modules.menu.repository import MenuRepository
from tests.fakes import FakeCache


def test_cache_hit_and_invalidation_after_create():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    cache = FakeCache()
    queries = []

    def count_menu_queries(_conn, _cursor, statement, _parameters, _context, _executemany):
        if "FROM menu_items ORDER BY menu_items.id" in statement:
            queries.append(statement)

    event.listen(engine, "before_cursor_execute", count_menu_queries)
    with Session(engine) as db:
        repository = MenuRepository(db, cache)
        assert repository.get_all() == []
        assert cache.ttls["menu:all"] == 300
        assert repository.get_all() == []
        assert len(queries) == 1
        repository.create("Soup", 20)
        assert repository.get_all()[0]["name"] == "Soup"
        assert len(queries) == 2
    engine.dispose()


def test_category_cache_and_invalidation_after_update():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    cache = FakeCache()
    with Session(engine) as db:
        repository = MenuRepository(db, cache)
        category = repository.create_category("Lunch")
        item = repository.create("Soup", 20, category.id)
        data = repository.get_category_with_items(category.id)
        assert data["items"][0]["name"] == "Soup"
        assert cache.ttls[f"menu:category:{category.id}"] == 600
        item.price = 25
        repository.save(item, category.id)
        assert repository.get_category_with_items(category.id)["items"][0]["price"] == 25
    engine.dispose()


def test_stampede_uses_one_loader():
    cache = FakeCache()
    repository = MenuRepository(object(), cache)
    loads = []

    def load():
        loads.append(1)
        sleep(0.05)
        return [{"id": 1}]

    with ThreadPoolExecutor(max_workers=20) as pool:
        result = list(pool.map(lambda _: repository._cached("menu:all", 300, load), range(20)))
    assert len(loads) == 1
    assert all(value == [{"id": 1}] for value in result)


def test_redis_failure_falls_back_to_database():
    class BrokenCache(FakeCache):
        def get(self, key):
            raise RedisConnectionError("down")

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(MenuItem(name="Tea", price=10, is_available=True))
        db.commit()
        assert MenuRepository(db, BrokenCache()).get_all()[0]["name"] == "Tea"
    engine.dispose()
