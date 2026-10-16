from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.modules.orders.service import OrderError, OrderService
from app.modules.users.service import UserError, UserService


def test_create_order_without_database():
    repository = Mock()
    repository.get_user_by_id.return_value = SimpleNamespace(id=1, balance=100)
    repository.get_menu_item_by_id.return_value = SimpleNamespace(id=2, price=20, is_available=True)
    repository.place_order.return_value = 7
    assert OrderService(repository).create_order(1, 2, 2) == 7
    repository.place_order.assert_called_once()


def test_order_rejects_insufficient_balance_without_database():
    repository = Mock()
    repository.get_user_by_id.return_value = SimpleNamespace(id=1, balance=10)
    repository.get_menu_item_by_id.return_value = SimpleNamespace(id=2, price=20, is_available=True)
    with pytest.raises(OrderError, match="Недостаточно средств"):
        OrderService(repository).create_order(1, 2, 1)
    repository.place_order.assert_not_called()


def test_user_topup_rejects_blocked_user_without_database():
    repository = Mock()
    repository.get_by_id.return_value = SimpleNamespace(id=1, balance=0, is_blocked=True)
    with pytest.raises(UserError, match="заблокирован"):
        UserService(repository).top_up_balance(1, 100)
    repository.save.assert_not_called()
