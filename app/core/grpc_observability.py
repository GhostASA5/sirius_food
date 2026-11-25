import grpc
import logging

from app.core.observability import message_context


class CorrelationInterceptor(grpc.ServerInterceptor):
    def intercept_service(self, continuation, details):
        handler = continuation(details)
        if handler is None:
            return None
        carrier = dict(details.invocation_metadata)
        carrier["X-Correlation-ID"] = carrier.pop("x-correlation-id", "")
        if handler.unary_unary:
            def unary(request, context):
                with message_context(carrier, details.method):
                    logging.getLogger(__name__).info("grpc_request")
                    return handler.unary_unary(request, context)
            return grpc.unary_unary_rpc_method_handler(
                unary, request_deserializer=handler.request_deserializer,
                response_serializer=handler.response_serializer,
            )
        if handler.unary_stream:
            def stream(request, context):
                with message_context(carrier, details.method):
                    yield from handler.unary_stream(request, context)
            return grpc.unary_stream_rpc_method_handler(
                stream, request_deserializer=handler.request_deserializer,
                response_serializer=handler.response_serializer,
            )
        return handler
