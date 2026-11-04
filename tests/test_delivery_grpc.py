import grpc
import pytest
from fastapi import Request

import delivery_pb2
import delivery_pb2_grpc
from app.core.jwt import create_access_token
from app.models import Delivery, Order
from app.modules.delivery.grpc_client import DeliveryClientError, DeliveryGrpcClient
from app.modules.delivery.router import get_delivery_client
from tests.test_security import client


def test_grpc_requires_access_token(client):
    http, _, _ = client
    with grpc.insecure_channel(http.app.state.test_grpc_target) as channel:
        stub = delivery_pb2_grpc.DeliveryServiceStub(channel)
        with pytest.raises(grpc.RpcError) as error:
            stub.GetDelivery(delivery_pb2.GetDeliveryRequest(delivery_id=1), timeout=2)
        assert error.value.code() == grpc.StatusCode.UNAUTHENTICATED


def test_stream_tracks_delivery_statuses(client):
    http, session_factory, ids = client
    with session_factory() as db:
        order = Order(user_id=ids["alice"], item_id=1, quantity=1, status="paid")
        db.add(order)
        db.flush()
        delivery = Delivery(order_id=order.id, courier_id=ids["driver"], status="in_progress")
        db.add(delivery)
        db.commit()
        delivery_id = delivery.id
        order_id = order.id
    grpc_client = DeliveryGrpcClient(
        create_access_token(ids["alice"]), http.app.state.test_grpc_target
    )
    try:
        assert grpc_client.get_delivery_by_order(order_id)["id"] == delivery_id
        states = [entry["status"] for entry in grpc_client.track_delivery(delivery_id)]
    finally:
        grpc_client.close()
    assert states == ["in_progress", "on_the_way", "delivered"]


def test_client_maps_service_unavailable_to_503():
    client = DeliveryGrpcClient("invalid", "127.0.0.1:1")
    try:
        with pytest.raises(DeliveryClientError) as error:
            client.get_delivery(1)
        assert error.value.status_code == 503
    finally:
        client.close()


def test_http_returns_503_when_grpc_service_is_unavailable(client):
    http, _, ids = client

    def unavailable_client(request: Request):
        token = request.headers.get("authorization", "").partition(" ")[2]
        grpc_client = DeliveryGrpcClient(token, "127.0.0.1:1")
        try:
            yield grpc_client
        finally:
            grpc_client.close()

    http.app.dependency_overrides[get_delivery_client] = unavailable_client
    response = http.get(
        "/delivery/1",
        headers={"Authorization": f"Bearer {create_access_token(ids['alice'])}"},
    )
    assert response.status_code == 503
