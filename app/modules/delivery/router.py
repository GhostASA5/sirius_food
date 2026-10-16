from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Delivery, Order, User
from app.schemas import DeliveryAssign

router = APIRouter()


@router.post("/assign")
def assign_courier(payload: DeliveryAssign, db: Session = Depends(get_db)):
    order = db.query(Order).filter(Order.id == payload.order_id).first()
    if order is None:
        raise HTTPException(404, "Заказ не найден")
    if order.status != "paid":
        raise HTTPException(400, "Курьера можно назначить только на оплаченный заказ")
    courier = db.query(User).filter(User.id == payload.courier_id).first()
    if courier is None:
        raise HTTPException(404, "Курьер не найден")
    if courier.is_blocked:
        raise HTTPException(403, "Курьер заблокирован и не может быть назначен")
    active = db.query(Delivery).filter(
        Delivery.courier_id == payload.courier_id, Delivery.status == "in_progress"
    ).first()
    if active:
        raise HTTPException(400, "У курьера уже есть активная доставка")
    delivery = Delivery(order_id=payload.order_id, courier_id=payload.courier_id, status="in_progress")
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return {"status": "success", "delivery_id": delivery.id}


@router.patch("/{delivery_id}/complete")
def complete_delivery(delivery_id: int, db: Session = Depends(get_db)):
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if delivery is None:
        raise HTTPException(404, "Доставка не найдена")
    if delivery.status == "completed":
        raise HTTPException(400, "Доставка уже завершена")
    if delivery.status == "cancelled":
        raise HTTPException(400, "Отменённую доставку нельзя завершить")
    delivery.status = "completed"
    order = db.query(Order).filter(Order.id == delivery.order_id).first()
    if order:
        order.status = "delivered"
        db.add(order)
    db.add(delivery)
    db.commit()
    return {"status": "success"}
