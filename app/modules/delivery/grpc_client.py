import grpc

import delivery_pb2
import delivery_pb2_grpc
from app.core.config import get_settings
from app.core.observability import headers


class DeliveryClientError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def _raise_rpc_error(exc: grpc.RpcError):
    status_code = {
        grpc.StatusCode.INVALID_ARGUMENT: 400,
        grpc.StatusCode.UNAUTHENTICATED: 401,
        grpc.StatusCode.PERMISSION_DENIED: 403,
        grpc.StatusCode.NOT_FOUND: 404,
        grpc.StatusCode.DEADLINE_EXCEEDED: 504,
        grpc.StatusCode.UNAVAILABLE: 503,
    }.get(exc.code(), 502)
    raise DeliveryClientError(exc.details() or "Delivery service error", status_code) from exc


class DeliveryGrpcClient:
    def __init__(self, token: str, target: str | None = None):
        self.channel = grpc.insecure_channel(target or get_settings().DELIVERY_GRPC_TARGET)
        self.stub = delivery_pb2_grpc.DeliveryServiceStub(self.channel)
        self.metadata = (("authorization", f"Bearer {token}"),) + tuple(
            (key.lower(), value) for key, value in headers().items()
        )

    def close(self):
        self.channel.close()

    @staticmethod
    def _data(response) -> dict:
        return {
            "id": response.id,
            "order_id": response.order_id,
            "courier_id": response.courier_id or None,
            "status": response.status,
        }

    def assign_courier(self, order_id: int, courier_id: int) -> int:
        try:
            response = self.stub.AssignCourier(
                delivery_pb2.AssignCourierRequest(order_id=order_id, courier_id=courier_id),
                timeout=5, metadata=self.metadata,
            )
            return response.delivery_id
        except grpc.RpcError as exc:
            _raise_rpc_error(exc)

    def complete_delivery(self, delivery_id: int) -> None:
        try:
            self.stub.CompleteDelivery(
                delivery_pb2.CompleteDeliveryRequest(delivery_id=delivery_id),
                timeout=5, metadata=self.metadata,
            )
        except grpc.RpcError as exc:
            _raise_rpc_error(exc)

    def get_delivery(self, delivery_id: int) -> dict:
        try:
            response = self.stub.GetDelivery(
                delivery_pb2.GetDeliveryRequest(delivery_id=delivery_id),
                timeout=5, metadata=self.metadata,
            )
            return self._data(response)
        except grpc.RpcError as exc:
            _raise_rpc_error(exc)

    def get_delivery_by_order(self, order_id: int) -> dict:
        try:
            response = self.stub.GetDelivery(
                delivery_pb2.GetDeliveryRequest(order_id=order_id),
                timeout=5, metadata=self.metadata,
            )
            return self._data(response)
        except grpc.RpcError as exc:
            _raise_rpc_error(exc)

    def list_my_deliveries(self) -> list[dict]:
        try:
            response = self.stub.ListMyDeliveries(
                delivery_pb2.ListMyDeliveriesRequest(),
                timeout=5, metadata=self.metadata,
            )
            return [self._data(item) for item in response.deliveries]
        except grpc.RpcError as exc:
            _raise_rpc_error(exc)

    def track_delivery(self, delivery_id: int):
        try:
            stream = self.stub.TrackDelivery(
                delivery_pb2.TrackDeliveryRequest(delivery_id=delivery_id),
                timeout=10, metadata=self.metadata,
            )
            for status in stream:
                yield {"delivery_id": status.delivery_id, "status": status.status}
        except grpc.RpcError as exc:
            _raise_rpc_error(exc)
