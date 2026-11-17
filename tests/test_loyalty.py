import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-that-has-at-least-32-characters")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.core.event_handlers import handle_compensation
from app.models import LoyaltyTransaction, Order, PromoCode, PromoCodeUsage, User
from app.modules.loyalty.events import handle_earn, handle_loyalty_cancellation, handle_promo_cancellation
from app.modules.loyalty.repository import LoyaltyRepository
from app.modules.loyalty.service import LoyaltyError
from app.modules.orders.repository import OrderRepository
from app.modules.orders.service import OrderError, OrderService
from tests.test_events import db_factory


def test_promo_points_and_saga(db_factory):
    now = datetime.now(timezone.utc)
    with db_factory() as db:
        db.add(PromoCode(
            code="ONE", discount_type="fixed", discount_value=Decimal("4"),
            valid_from=now - timedelta(hours=1), valid_until=now + timedelta(hours=1),
            max_uses=1, min_order_amount=Decimal("20"),
        ))
        db.commit()
        service = OrderService(OrderRepository(db))
        initial = service.create_order(1, 1, 3)
        service.pay_order(initial, 1)
        assert handle_earn(db, {"order_id": initial})
        assert not handle_earn(db, {"order_id": initial})
        order_id = service.create_order(1, 1, 1, "one")
        with pytest.raises(LoyaltyError, match="исчерпан"):
            service.create_order(1, 1, 1, "ONE")
        with pytest.raises(LoyaltyError, match="50%"):
            service.pay_order(order_id, 1, points=Decimal("8.01"))
        service.pay_order(order_id, 1, points=Decimal("1"))
        with pytest.raises(OrderError):
            service.pay_order(order_id, 1, points=Decimal("1"))
        assert db.get(Order, order_id).total_amount == Decimal("15.00")
        assert db.get(User, 1).balance == 25
        assert handle_earn(db, {"order_id": order_id})
        failure = {"order_id": order_id, "event_id": str(uuid4()), "amount": 15}
        assert handle_compensation(db, failure)
        assert not handle_compensation(db, failure)
        assert not handle_earn(db, {"order_id": order_id})
        for handler in (handle_loyalty_cancellation, handle_promo_cancellation):
            assert handler(db, failure)
            assert not handler(db, failure)
        assert db.get(User, 1).balance == 40
        promo = db.query(PromoCode).one()
        assert promo.current_uses == 0
        assert db.get(PromoCodeUsage, order_id) is None
        assert db.query(LoyaltyTransaction).filter_by(order_id=order_id).count() == 4
        assert LoyaltyRepository(db).account(1).balance == Decimal("1.80")
        next_order = service.create_order(1, 1, 1, "ONE")
        service.cancel_order(next_order, 1)
        assert not handle_earn(db, {"order_id": next_order})
        assert handle_promo_cancellation(db, {"order_id": next_order})
        assert db.get(User, 1).balance == 40


def test_expired_promo_is_rejected_before_beat_and_deactivated_by_job(db_factory):
    now = datetime.now(timezone.utc)
    with db_factory() as db:
        db.add(PromoCode(
            code="EXPIRED", discount_type="percent", discount_value=Decimal("10"),
            valid_from=now - timedelta(days=2), valid_until=now - timedelta(days=1),
            max_uses=1, min_order_amount=Decimal("0"),
        ))
        db.commit()
        with pytest.raises(LoyaltyError, match="вне срока"):
            OrderService(OrderRepository(db)).create_order(1, 1, 1, "EXPIRED")
        assert LoyaltyRepository(db).expire(now) == 1
        assert not db.query(PromoCode).one().is_active
        assert db.query(Order).count() == 0


def test_tier_progression_changes_rate_for_next_order(db_factory, monkeypatch):
    monkeypatch.setenv("LOYALTY_SILVER", "2")
    monkeypatch.setenv("LOYALTY_GOLD", "4")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        with db_factory() as db:
            db.get(User, 1).balance = 300
            db.commit()
            service = OrderService(OrderRepository(db))
            for tier, total in (("Silver", "2.40"), ("Gold", "6.40"), ("Gold", "12.00")):
                order = service.create_order(1, 1, 4)
                service.pay_order(order, 1)
                assert handle_earn(db, {"order_id": order})
                account = LoyaltyRepository(db).account(1)
                assert account.tier == tier
                assert account.total_earned == Decimal(total)
    finally:
        get_settings.cache_clear()
