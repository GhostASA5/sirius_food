from app.database import SessionLocal
from app.models import MenuItem
from app.modules.search.repository import SearchRepository


def main():
    repository = SearchRepository()
    try:
        repository.ensure_index()
        with SessionLocal() as db:
            for item in db.query(MenuItem).order_by(MenuItem.id).yield_per(100):
                repository.index_item(item)
    finally:
        repository.close()


if __name__ == "__main__":
    main()
