from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.dependencies import get_current_user, require_role
from app.models import User
from app.modules.delivery.grpc_client import DeliveryClientError, DeliveryGrpcClient
from app.schemas import DeliveryAssign


router = APIRouter()


def get_delivery_client(request: Request):
    token = request.headers.get("authorization", "").partition(" ")[2]
    client = DeliveryGrpcClient(token)
    try:
        yield client
    finally:
        client.close()


@router.post("/assign")
def assign_courier(
    payload: DeliveryAssign,
    _current_user: User = Depends(require_role("admin")),
    client: DeliveryGrpcClient = Depends(get_delivery_client),
):
    try:
        delivery_id = client.assign_courier(payload.order_id, payload.courier_id)
    except DeliveryClientError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    return {"status": "success", "delivery_id": delivery_id}


@router.get("/mine")
def my_deliveries(
    _current_user: User = Depends(require_role("courier")),
    client: DeliveryGrpcClient = Depends(get_delivery_client),
):
    try:
        return client.list_my_deliveries()
    except DeliveryClientError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@router.get("/{delivery_id}")
def get_delivery(
    delivery_id: int,
    _current_user: User = Depends(get_current_user),
    client: DeliveryGrpcClient = Depends(get_delivery_client),
):
    try:
        return client.get_delivery(delivery_id)
    except DeliveryClientError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@router.patch("/{delivery_id}/complete")
def complete_delivery(
    delivery_id: int,
    _current_user: User = Depends(require_role("courier")),
    client: DeliveryGrpcClient = Depends(get_delivery_client),
):
    try:
        client.complete_delivery(delivery_id)
    except DeliveryClientError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    return {"status": "success"}
