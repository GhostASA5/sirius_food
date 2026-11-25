from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.database import get_db
from app.modules.menu.repository import MenuRepository
from app.modules.menu.service import MenuError, MenuService
from app.schemas import MenuCategoryCreate, MenuItemCreate, MenuItemUpdate

router = APIRouter()


@router.get("/items")
def list_menu_items(db: Session = Depends(get_db)):
    return MenuService(MenuRepository(db)).get_all()


@router.get("/items/{item_id}")
def get_menu_item(
    item_id: Annotated[int, Path(ge=1, le=2147483647)],
    db: Session = Depends(get_db),
):
    try:
        return MenuService(MenuRepository(db)).get_item(item_id)
    except MenuError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@router.post("/categories", dependencies=[Depends(require_role("admin", "cook"))])
def create_menu_category(payload: MenuCategoryCreate, db: Session = Depends(get_db)):
    if len(payload.name) < 2:
        raise HTTPException(400, "Название категории слишком короткое")
    try:
        category_id = MenuService(MenuRepository(db)).create_category(payload.name)
    except MenuError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    return {"status": "success", "category_id": category_id}


@router.get("/categories/{category_id}")
def get_menu_category(category_id: int, db: Session = Depends(get_db)):
    try:
        return MenuService(MenuRepository(db)).get_category_with_items(category_id)
    except MenuError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@router.post("/items", dependencies=[Depends(require_role("admin", "cook"))])
def create_menu_item(payload: MenuItemCreate, db: Session = Depends(get_db)):
    if payload.price <= 0:
        raise HTTPException(400, "Цена должна быть положительной")
    if len(payload.name) < 2:
        raise HTTPException(400, "Название блюда слишком короткое")
    try:
        item_id = MenuService(MenuRepository(db)).create(
            payload.name, payload.price, payload.category_id, payload.description
        )
    except MenuError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    return {"status": "success", "item_id": item_id}


@router.patch("/items/{item_id}", dependencies=[Depends(require_role("admin", "cook"))])
def update_menu_item(item_id: int, payload: MenuItemUpdate, db: Session = Depends(get_db)):
    if payload.price is not None and payload.price <= 0:
        raise HTTPException(400, "Цена должна быть положительной")
    try:
        updated_id = MenuService(MenuRepository(db)).update(
            item_id, payload.model_dump(exclude_unset=True)
        )
    except MenuError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    return {"status": "success", "item_id": updated_id}
