from sqlalchemy.orm import Session

from app.models import MenuCategory, MenuItem


class MenuRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, item_id: int):
        return self.db.query(MenuItem).filter(MenuItem.id == item_id).first()

    def get_all(self):
        return self.db.query(MenuItem).order_by(MenuItem.id).all()

    def get_category(self, category_id: int):
        return self.db.query(MenuCategory).filter(MenuCategory.id == category_id).first()

    def get_category_by_name(self, name: str):
        return self.db.query(MenuCategory).filter(MenuCategory.name == name).first()

    def create_category(self, name: str):
        category = MenuCategory(name=name)
        self.db.add(category)
        self.db.commit()
        self.db.refresh(category)
        return category

    def get_by_name(self, name: str):
        return self.db.query(MenuItem).filter(MenuItem.name == name).first()

    def create(self, name: str, price: float, category_id: int | None = None):
        item = MenuItem(name=name, price=price, is_available=True, category_id=category_id)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def save(self, item):
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
