from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.modules.orders.service import OrderError, OrderService
from app.tasks import orders
from tests.fakes import FakeCache


def test_service_dispatches_after_saving_order():
    repository = Mock()
    repository.get_user_by_id.return_value = SimpleNamespace(
        id=1, balance=100, email="a@example.com", phone="1234567890"
    )
    repository.get_menu_item_by_id.return_value = SimpleNamespace(
        id=2, price=10, is_available=True
    )
    repository.place_order.return_value = 7
    notifications = Mock()
    assert OrderService(repository, notifications).create_order(1, 2, 1) == 7
    notifications.enqueue_order_created.assert_called_once_with(7, "a@example.com", "1234567890")


def test_service_does_not_dispatch_on_invalid_order():
    repository = Mock()
    repository.get_user_by_id.return_value = None
    notifications = Mock()
    with pytest.raises(OrderError):
        OrderService(repository, notifications).create_order(1, 2, 1)
    notifications.enqueue_order_created.assert_not_called()


def test_task_is_idempotent(monkeypatch):
    cache = FakeCache()
    monkeypatch.setattr(orders, "get_redis_client", lambda: cache)
    calls = []

    def work():
        calls.append(1)
        return "done"

    assert orders.run_once("pdf", 10, work) == "done"
    assert "already processed" in orders.run_once("pdf", 10, work)
    assert len(calls) == 1
    assert cache.ttls["order_task:pdf:10"] == 3600


def test_failed_task_releases_idempotency_key(monkeypatch):
    cache = FakeCache()
    monkeypatch.setattr(orders, "get_redis_client", lambda: cache)

    def fail():
        raise RuntimeError("temporary")

    with pytest.raises(RuntimeError):
        orders.run_once("email", 11, fail)
    assert "order_task:email:11" not in cache.data
    assert orders.run_once("email", 11, lambda: "sent") == "sent"


def test_exhausted_retries_write_to_dlq(monkeypatch):
    cache = FakeCache()
    monkeypatch.setattr(orders, "get_redis_client", lambda: cache)
    monkeypatch.setattr(orders.time, "sleep", lambda _: None)
    monkeypatch.setattr(
        orders, "get_settings", lambda: SimpleNamespace(SIMULATE_EMAIL_FAILURES=True)
    )
    result = orders.send_order_email.apply(args=(10, "test@example.com"), throw=False)
    assert result.failed()
    assert len(cache.data["dlq"]) == 1
    assert "send_order_email" in cache.data["dlq"][0]
