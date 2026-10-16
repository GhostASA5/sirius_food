from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.orders.repository import OrderRepository
from app.modules.orders.service import OrderError, OrderService
from app.schemas import OrderCreate

router = APIRouter()


@router.post("/create")
def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    if payload.quantity <= 0:
        raise HTTPException(400, "Количество должно быть больше нуля")
    try:
        order_id = OrderService(OrderRepository(db)).create_order(
            payload.user_id, payload.item_id, payload.quantity
        )
    except OrderError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    return {"status": "success", "order_id": order_id}
