import json
from decimal import Decimal

from app.models import Order, OutboxEvent, User


def test_order_is_saved_and_balance_debited(client, db):
    http, headers, user_id, item_id = client
    response = http.post("/orders/create", json={"item_id": item_id, "quantity": 2}, headers=headers)
    assert response.status_code == 200
    order = db.get(Order, response.json()["order_id"])
    assert order.user_id == user_id
    assert order.quantity == 2
    assert order.total_amount == Decimal("300.00")
    assert db.get(User, user_id).balance == 700
    response = http.post(f"/orders/{order.id}/pay", headers={**headers, "X-Correlation-ID": "integration"})
    assert response.status_code == 200
    event = db.query(OutboxEvent).filter_by(routing_key="order.paid").one()
    assert json.loads(event.payload)["order_id"] == order.id
    assert json.loads(event.context)["X-Correlation-ID"] == "integration"


def test_rejected_order_does_not_change_database(client, db):
    http, headers, user_id, item_id = client
    response = http.post("/orders/create", json={"item_id": item_id, "quantity": 100}, headers=headers)
    assert response.status_code == 400
    assert db.query(Order).count() == 0
    assert db.get(User, user_id).balance == 1000


def test_database_is_clean_for_next_test(client, db):
    assert db.query(Order).count() == 0
    assert db.query(OutboxEvent).count() == 0
