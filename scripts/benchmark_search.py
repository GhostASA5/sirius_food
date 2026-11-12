import json
from statistics import mean
from time import perf_counter

from sqlalchemy import func

from app.database import SessionLocal
from app.models import MenuItem
from app.modules.search.repository import SearchRepository


def measured(fn, count=100):
    fn()
    samples = []
    for _ in range(count):
        start = perf_counter()
        fn()
        samples.append((perf_counter() - start) * 1000)
    samples.sort()
    return {"mean_ms": round(mean(samples), 3), "p95_ms": round(samples[int(count * 0.95) - 1], 3)}


def main():
    query = "string"
    with SessionLocal() as db:
        def sql_search():
            pattern = f"%{query}%"
            return db.query(MenuItem).filter(
                MenuItem.is_available.is_(True),
                func.lower(MenuItem.name).like(pattern),
            ).all()

        sql_result = measured(sql_search)
        count = db.query(MenuItem).count()
    repository = SearchRepository()
    try:
        es_result = measured(lambda: repository.search(query, None, None, None, 1, 20))
    finally:
        repository.close()
    print(json.dumps({"query": query, "menu_items": count,
                      "iterations": 100, "sql_like": sql_result,
                      "elasticsearch": es_result}, ensure_ascii=False))


if __name__ == "__main__":
    main()
