from concurrent import futures
from app.core.grpc_observability import CorrelationInterceptor
from time import sleep

import grpc
from jose import JWTError

import delivery_pb2
import delivery_pb2_grpc
from app.core.jwt import decode_token
from app.database import SessionLocal
from app.models import User
from delivery_service.repository import DeliveryRepository
from delivery_service.service import DeliveryError, DeliveryService


def _actor(context, db):
    metadata = dict(context.invocation_metadata())
    authorization = metadata.get("authorization", "")
    if not authorization.startswith("Bearer "):
        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Access token required")
    try:
        user_id = int(decode_token(authorization[7:], "access")["sub"])
    except (JWTError, ValueError, KeyError):
        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid access token")
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        context.abort(grpc.StatusCode.UNAUTHENTICATED, "User not found")
    if user.is_blocked:
        context.abort(grpc.StatusCode.PERMISSION_DENIED, "User is blocked")
    return user


def _abort_domain_error(context, exc: DeliveryError):
    code = {
        400: grpc.StatusCode.INVALID_ARGUMENT,
        403: grpc.StatusCode.PERMISSION_DENIED,
        404: grpc.StatusCode.NOT_FOUND,
    }.get(exc.status_code, grpc.StatusCode.INTERNAL)
    context.abort(code, str(exc))


def _response(data: dict):
    return delivery_pb2.GetDeliveryResponse(
        **{**data, "courier_id": data["courier_id"] or 0}
    )


class DeliveryServicer(delivery_pb2_grpc.DeliveryServiceServicer):
    def AssignCourier(self, request, context):
        with SessionLocal() as db:
            actor = _actor(context, db)
            if actor.role.name != "admin":
                context.abort(grpc.StatusCode.PERMISSION_DENIED, "Access denied")
            try:
                delivery_id = DeliveryService(DeliveryRepository(db)).assign(
                    request.order_id, request.courier_id
                )
            except DeliveryError as exc:
                _abort_domain_error(context, exc)
            return delivery_pb2.AssignCourierResponse(
                delivery_id=delivery_id, status="in_progress"
            )

    def CompleteDelivery(self, request, context):
        with SessionLocal() as db:
            actor = _actor(context, db)
            if actor.role.name not in ("courier", "admin"):
                context.abort(grpc.StatusCode.PERMISSION_DENIED, "Access denied")
            try:
                DeliveryService(DeliveryRepository(db)).complete(
                    request.delivery_id, actor.id, actor.role.name
                )
            except DeliveryError as exc:
                _abort_domain_error(context, exc)
            return delivery_pb2.CompleteDeliveryResponse(status="success")

    def GetDelivery(self, request, context):
        with SessionLocal() as db:
            actor = _actor(context, db)
            service = DeliveryService(DeliveryRepository(db))
            try:
                if request.delivery_id > 0:
                    data = service.get_delivery(request.delivery_id, actor.id, actor.role.name)
                elif request.order_id > 0:
                    data = service.get_delivery_by_order(
                        request.order_id, actor.id, actor.role.name
                    )
                else:
                    context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Delivery ID required")
            except DeliveryError as exc:
                _abort_domain_error(context, exc)
            return _response(data)

    def ListMyDeliveries(self, request, context):
        with SessionLocal() as db:
            actor = _actor(context, db)
            if actor.role.name not in ("courier", "admin"):
                context.abort(grpc.StatusCode.PERMISSION_DENIED, "Access denied")
            data = DeliveryService(DeliveryRepository(db)).list_my_deliveries(actor.id)
            return delivery_pb2.ListMyDeliveriesResponse(
                deliveries=[_response(item) for item in data]
            )

    def TrackDelivery(self, request, context):
        with SessionLocal() as db:
            actor = _actor(context, db)
            try:
                data = DeliveryService(DeliveryRepository(db)).get_delivery(
                    request.delivery_id, actor.id, actor.role.name
                )
            except DeliveryError as exc:
                _abort_domain_error(context, exc)
        statuses = (
            ("in_progress", "on_the_way", "delivered")
            if data["status"] == "in_progress" else (data["status"],)
        )
        for index, status in enumerate(statuses):
            if not context.is_active():
                return
            if index:
                sleep(2)
            yield delivery_pb2.DeliveryStatus(delivery_id=request.delivery_id, status=status)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10), interceptors=[CorrelationInterceptor()])
    delivery_pb2_grpc.add_DeliveryServiceServicer_to_server(DeliveryServicer(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
