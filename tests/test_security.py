import os

os.environ.setdefault("SECRET_KEY", "test-secret-that-has-at-least-32-characters")
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from unittest.mock import Mock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.jwt import create_access_token
from app.core.security import hash_password, verify_password
from app.database import Base, get_db
from app.main import app
from app.models import Delivery, MenuItem, Order, Role, User
from tests.fakes import FakeCache


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("app.modules.menu.repository.get_redis_client", FakeCache)
    monkeypatch.setattr("app.modules.orders.router.CeleryOrderNotifications", Mock)
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as db:
        roles = {name: Role(name=name) for name in ("student", "cook", "courier", "admin")}
        db.add_all(roles.values())
        db.flush()
        users = {
            name: User(
                email=f"{name}@example.com", password_hash=hash_password("password123"),
                role_id=roles[role].id, balance=100.0, is_blocked=False,
            )
            for name, role in (("alice", "student"), ("bob", "student"),
                               ("chef", "cook"), ("driver", "courier"), ("boss", "admin"))
        }
        db.add_all(users.values())
        db.add(MenuItem(name="Soup", price=20.0, is_available=True))
        db.commit()
        for user in users.values():
            db.refresh(user)
        ids = {name: user.id for name, user in users.items()}

    def override_db():
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client, session_factory, ids
    app.dependency_overrides.clear()
    engine.dispose()


def auth(user_id):
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def test_missing_token_is_401(client):
    http, _, _ = client
    assert http.post("/orders/create", json={"item_id": 1, "quantity": 1}).status_code == 401


def test_wrong_role_is_403(client):
    http, _, ids = client
    response = http.get("/orders/kitchen/orders", headers=auth(ids["alice"]))
    assert response.status_code == 403
    response = http.post("/menu/items", json={"name": "Tea", "price": 10}, headers=auth(ids["alice"]))
    assert response.status_code == 403


def test_other_student_cannot_cancel_order(client):
    http, session_factory, ids = client
    with session_factory() as db:
        order = Order(user_id=ids["alice"], item_id=1, quantity=1, status="processing")
        db.add(order)
        db.commit()
        order_id = order.id
    response = http.post(f"/orders/{order_id}/cancel", headers=auth(ids["bob"]))
    assert response.status_code == 403


def test_courier_cannot_view_other_delivery(client):
    http, session_factory, ids = client
    with session_factory() as db:
        order = Order(user_id=ids["alice"], item_id=1, quantity=1, status="paid")
        db.add(order)
        db.flush()
        delivery = Delivery(order_id=order.id, courier_id=ids["driver"], status="in_progress")
        db.add(delivery)
        db.commit()
        delivery_id = delivery.id
    assert http.get(f"/delivery/{delivery_id}", headers=auth(ids["bob"])).status_code == 403
    assert http.get(f"/delivery/{delivery_id}", headers=auth(ids["driver"])).status_code == 200


def test_registration_hashes_password_and_login_works(client):
    http, session_factory, _ = client
    response = http.post(
        "/users/register", json={"email": "new@example.com", "password": "secret123"}
    )
    assert response.status_code == 200
    with session_factory() as db:
        user = db.query(User).filter(User.email == "new@example.com").one()
        assert user.password_hash != "secret123"
        assert verify_password("secret123", user.password_hash)
    login = http.post("/auth/login", json={"email": "new@example.com", "password": "secret123"})
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"


def test_refresh_token_cannot_be_used_as_access_token(client):
    http, _, _ = client
    login = http.post("/auth/login", json={"email": "alice@example.com", "password": "password123"})
    refresh = login.json()["refresh_token"]
    response = http.post(
        "/orders/create", json={"item_id": 1, "quantity": 1},
        headers={"Authorization": f"Bearer {refresh}"},
    )
    assert response.status_code == 401


def test_order_uses_authenticated_user_and_debits_balance(client):
    http, session_factory, ids = client
    response = http.post(
        "/orders/create", json={"item_id": 1, "quantity": 2}, headers=auth(ids["alice"])
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    with session_factory() as db:
        order = db.query(Order).filter(Order.id == response.json()["order_id"]).one()
        user = db.query(User).filter(User.id == ids["alice"]).one()
        assert order.user_id == ids["alice"]
        assert user.balance == 60.0


def test_refresh_returns_new_access_token(client):
    http, _, _ = client
    login = http.post("/auth/login", json={"email": "alice@example.com", "password": "password123"})
    assert login.status_code == 200
    refreshed = http.post("/auth/refresh", json={"refresh_token": login.json()["refresh_token"]})
    assert refreshed.status_code == 200
    assert refreshed.json()["token_type"] == "bearer"


def test_cook_can_update_menu_and_view_kitchen(client):
    http, _, ids = client
    created = http.post(
        "/menu/items", json={"name": "Tea", "price": 10}, headers=auth(ids["chef"])
    )
    assert created.status_code == 200
    updated = http.patch(
        f"/menu/items/{created.json()['item_id']}",
        json={"price": 12}, headers=auth(ids["chef"]),
    )
    assert updated.status_code == 200
    assert http.get("/orders/kitchen/orders", headers=auth(ids["chef"])).status_code == 200


def test_delivery_workflow_checks_role_and_courier_ownership(client):
    http, session_factory, ids = client
    with session_factory() as db:
        order = Order(user_id=ids["alice"], item_id=1, quantity=1, status="paid")
        db.add(order)
        db.commit()
        order_id = order.id
    assigned = http.post(
        "/delivery/assign", json={"order_id": order_id, "courier_id": ids["driver"]},
        headers=auth(ids["boss"]),
    )
    assert assigned.status_code == 200
    delivery_id = assigned.json()["delivery_id"]
    assert len(http.get("/delivery/mine", headers=auth(ids["driver"])).json()) == 1
    assert http.patch(
        f"/delivery/{delivery_id}/complete", headers=auth(ids["alice"])
    ).status_code == 403
    assert http.patch(
        f"/delivery/{delivery_id}/complete", headers=auth(ids["driver"])
    ).status_code == 200


def test_user_cannot_top_up_another_balance(client):
    http, _, ids = client
    assert http.post(
        f"/users/{ids['bob']}/topup?amount=10", headers=auth(ids["alice"])
    ).status_code == 403


def test_admin_has_role_and_object_permissions(client):
    http, session_factory, ids = client
    admin_headers = auth(ids["boss"])
    assert http.get("/orders/kitchen/orders", headers=admin_headers).status_code == 200
    assert http.post(
        "/orders/create", json={"item_id": 1, "quantity": 1}, headers=admin_headers
    ).status_code == 200
    assert http.post(
        f"/users/{ids['bob']}/topup?amount=10", headers=admin_headers
    ).status_code == 200
    with session_factory() as db:
        foreign_order = Order(user_id=ids["alice"], item_id=1, quantity=1, status="processing")
        delivery_order = Order(user_id=ids["alice"], item_id=1, quantity=1, status="paid")
        db.add_all([foreign_order, delivery_order])
        db.flush()
        delivery = Delivery(
            order_id=delivery_order.id, courier_id=ids["driver"], status="in_progress"
        )
        db.add(delivery)
        db.commit()
        order_id = foreign_order.id
        delivery_id = delivery.id
    assert http.post(f"/orders/{order_id}/cancel", headers=admin_headers).status_code == 200
    assert http.patch(
        f"/delivery/{delivery_id}/complete", headers=admin_headers
    ).status_code == 200
