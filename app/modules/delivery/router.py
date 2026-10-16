from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.database import get_db
from app.models import User
from app.modules.delivery.repository import DeliveryRepository
from app.modules.delivery.service import DeliveryError, DeliveryService
from app.schemas import DeliveryAssign

router = APIRouter()


@router.post("/assign")
def assign_courier(
    payload: DeliveryAssign, _current_user: User = Depends(require_role("admin")),
    db: Session = Depends(get_db),
):
    try:
        delivery_id = DeliveryService(DeliveryRepository(db)).assign(
            payload.order_id, payload.courier_id
        )
    except DeliveryError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    return {"status": "success", "delivery_id": delivery_id}


@router.get("/mine")
def my_deliveries(
    current_user: User = Depends(require_role("courier")), db: Session = Depends(get_db)
):
    return DeliveryService(DeliveryRepository(db)).list_my_deliveries(current_user.id)


@router.get("/{delivery_id}")
def get_delivery(
    delivery_id: int, current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return DeliveryService(DeliveryRepository(db)).get_delivery(
            delivery_id, current_user.id, current_user.role.name
        )
    except DeliveryError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@router.patch("/{delivery_id}/complete")
def complete_delivery(
    delivery_id: int, current_user: User = Depends(require_role("courier")),
    db: Session = Depends(get_db),
):
    try:
        DeliveryService(DeliveryRepository(db)).complete(delivery_id, current_user.id)
    except DeliveryError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    return {"status": "success"}
