import json
from pathlib import Path

import pytest
from pact import Pact, Verifier, match

from app.core.event_handlers import handle_kitchen
from app.models import KitchenOrder, OutboxEvent
from tests.integration.conftest import postgres, db, client


@pytest.fixture
def contract(client, db, tmp_path):
    http, headers, user_id, item_id = client
    response = http.post("/orders/create", json={"item_id": item_id, "quantity": 1}, headers=headers)
    order_id = response.json()["order_id"]
    assert http.post(f"/orders/{order_id}/pay", headers=headers).status_code == 200
    payload = json.loads(db.query(OutboxEvent).filter_by(routing_key="order.paid").one().payload)
    pact = Pact("kitchen", "orders").with_specification("V4")
    pact.upon_receiving("OrderPaid", "Async").with_body({
        "event_id": match.str(payload["event_id"]),
        "order_id": match.int(order_id),
        "total": match.number(150.0),
        "currency": "RUB",
    }, content_type="application/json")

    def consume(body, metadata):
        assert handle_kitchen(db, json.loads(body))
        assert db.query(KitchenOrder).filter_by(order_id=order_id).count() == 1

    pact.verify(consume, "Async")
    pact.write_file(tmp_path, overwrite=True)
    return next(tmp_path.glob("*.json")), payload


def test_provider_matches_kitchen_contract(contract):
    path, payload = contract
    Verifier("orders").add_source(path).message_handler(
        {"OrderPaid": {"contents": json.dumps(payload).encode(),
                       "metadata": {"contentType": "application/json"},
                       "content_type": "application/json"}}
    ).verify()


def test_renaming_total_breaks_contract(contract):
    path, payload = contract
    payload.pop("total")
    with pytest.raises(RuntimeError):
        Verifier("orders").add_source(path).message_handler(
            {"OrderPaid": {"contents": json.dumps(payload).encode(),
                           "metadata": {"contentType": "application/json"},
                           "content_type": "application/json"}}
        ).verify()
