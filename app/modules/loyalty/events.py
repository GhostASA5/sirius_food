from app.core.config import get_settings
from app.models import Order, User
from app.modules.loyalty.repository import LoyaltyRepository
from app.modules.loyalty.service import LoyaltyService, money


def _lock_order(db, payload):
    order = db.query(Order).filter_by(id=payload["order_id"]).with_for_update().one_or_none()
    if order is None:
        raise ValueError("Заказ не найден")
    return order


def _loyalty_service(db, order):
    db.query(User).filter_by(id=order.user_id).with_for_update().one()
    settings = get_settings()
    return LoyaltyService(LoyaltyRepository(db), settings.LOYALTY_SILVER, settings.LOYALTY_GOLD)


def handle_earn(db, payload):
    order = _lock_order(db, payload)
    service = _loyalty_service(db, order)
    amount = order.total_amount if order.total_amount is not None else payload["amount"]
    changed = service.earn(order, money(amount))
    db.commit()
    return changed


def handle_loyalty_cancellation(db, payload):
    order = _lock_order(db, payload)
    changed = _loyalty_service(db, order).compensate(order)
    db.commit()
    return changed


def handle_promo_cancellation(db, payload):
    order = _lock_order(db, payload)
    if order.status != "cancelled":
        return False
    changed = LoyaltyRepository(db).restore_promo(order.id)
    db.commit()
    return changed
