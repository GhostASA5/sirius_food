from sqlalchemy.orm import Session

from app.models import MenuItem


class MenuRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, item_id: int):
        return self.db.query(MenuItem).filter(MenuItem.id == item_id).first()

    def get_by_name(self, name: str):
        return self.db.query(MenuItem).filter(MenuItem.name == name).first()

    def create(self, name: str, price: float):
        item = MenuItem(name=name, price=price, is_available=True)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def save(self, item):
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
