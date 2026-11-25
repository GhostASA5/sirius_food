import json
import os

os.environ.setdefault("SECRET_KEY", "test-secret-that-has-at-least-32-characters")
os.environ.setdefault("DATABASE_URL", "sqlite://")

import sentry_sdk
from sentry_sdk.transport import Transport
from app.core.observability import capture_error, correlation_id
from tests.test_security import client, auth


def test_correlation_header_and_metrics(client):
    http, _, ids = client
    response = http.get("/menu/items", headers={"X-Correlation-ID": "demo-42"})
    assert response.headers["X-Correlation-ID"] == "demo-42"
    assert http.get("/menu/items").headers["X-Correlation-ID"]
    metrics = http.get("/metrics").text
    assert "http_requests_total" in metrics


def test_outbox_persists_http_context(client):
    http, factory, ids = client
    from app.models import OutboxEvent
    response = http.post("/orders/create", json={"item_id": 1, "quantity": 1},
                         headers={**auth(ids["alice"]), "X-Correlation-ID": "demo-outbox"})
    order_id = response.json()["order_id"]
    http.post(f"/orders/{order_id}/pay",
              headers={**auth(ids["alice"]), "X-Correlation-ID": "demo-outbox"})
    with factory() as db:
        event = db.query(OutboxEvent).filter_by(routing_key="order.paid").one()
        assert json.loads(event.context)["X-Correlation-ID"] == "demo-outbox"


def test_sentry_carries_correlation_without_external_network():
    events = []

    class MemoryTransport(Transport):
        def capture_envelope(self, envelope):
            for item in envelope.items:
                if item.type == "event":
                    events.append(item.payload.json)

    with sentry_sdk.init(dsn="http://key@localhost/1", transport=MemoryTransport):
        token = correlation_id.set("sentry-demo")
        try:
            capture_error(RuntimeError("Тест Sentry"))
            sentry_sdk.flush()
        finally:
            correlation_id.reset(token)
    assert events[0]["tags"]["correlation_id"] == "sentry-demo"
