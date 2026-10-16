from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MenuItem
from app.schemas import MenuItemCreate, MenuItemUpdate

router = APIRouter()


@router.post("/items")
def create_menu_item(payload: MenuItemCreate, db: Session = Depends(get_db)):
    if payload.price <= 0:
        raise HTTPException(400, "Цена должна быть положительной")
    if len(payload.name) < 2:
        raise HTTPException(400, "Название блюда слишком короткое")
    if db.query(MenuItem).filter(MenuItem.name == payload.name).first():
        raise HTTPException(400, "Блюдо с таким названием уже существует")
    item = MenuItem(name=payload.name, price=payload.price, is_available=True)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"status": "success", "item_id": item.id}


@router.patch("/items/{item_id}")
def update_menu_item(item_id: int, payload: MenuItemUpdate, db: Session = Depends(get_db)):
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if item is None:
        raise HTTPException(404, "Блюдо не найдено")
    if payload.price is not None and payload.price <= 0:
        raise HTTPException(400, "Цена должна быть положительной")
    for field in ("name", "price", "is_available"):
        value = getattr(payload, field)
        if value is not None:
            setattr(item, field, value)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"status": "success", "item_id": item.id}
