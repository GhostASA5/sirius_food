from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.database import get_db
from app.models import User
from app.modules.orders.repository import OrderRepository
from app.modules.orders.service import OrderError, OrderService
from app.schemas import OrderCreate

router = APIRouter()


@router.post("/create")
def create_order(
    payload: OrderCreate, current_user: User = Depends(require_role("student")),
    db: Session = Depends(get_db),
):
    if payload.quantity <= 0:
        raise HTTPException(400, "Количество должно быть больше нуля")
    try:
        order_id = OrderService(OrderRepository(db)).create_order(
            current_user.id, payload.item_id, payload.quantity
        )
    except OrderError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    return {"status": "success", "order_id": order_id}


@router.get("/kitchen/orders")
def kitchen_orders(
    _current_user: User = Depends(require_role("cook")), db: Session = Depends(get_db)
):
    return OrderService(OrderRepository(db)).get_kitchen_orders()


@router.post("/{order_id}/cancel")
def cancel_order(
    order_id: int, current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        OrderService(OrderRepository(db)).cancel_order(
            order_id, current_user.id, current_user.role.name
        )
    except OrderError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    return {"status": "success"}
