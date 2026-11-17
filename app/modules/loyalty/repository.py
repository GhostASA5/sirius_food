from sqlalchemy.exc import IntegrityError

from app.models import LoyaltyAccount, LoyaltyTransaction, PromoCode, PromoCodeUsage, ProcessedEvent
from app.modules.loyalty.service import LoyaltyError


class LoyaltyRepository:
    def __init__(self, db):
        self.db = db

    def lock_promo(self, code):
        return self.db.query(PromoCode).filter_by(code=code).with_for_update().one_or_none()

    def has_usage(self, promo_id, user_id):
        return self.db.query(PromoCodeUsage).filter_by(promo_id=promo_id, user_id=user_id).first() is not None

    def record_usage(self, promo, order):
        promo.current_uses += 1
        self.db.add(PromoCodeUsage(order_id=order.id, promo_id=promo.id, user_id=order.user_id))

    def restore_promo(self, order_id):
        key = f"restore_promo_order_{order_id}"
        if self.db.get(ProcessedEvent, (key, "promo_restore")) is not None:
            return False
        usage = self.db.get(PromoCodeUsage, order_id)
        if usage is None:
            return False
        promo = self.db.query(PromoCode).filter_by(id=usage.promo_id).with_for_update().one()
        promo.current_uses -= 1
        self.db.delete(usage)
        self.db.add(ProcessedEvent(id=key, consumer="promo_restore"))
        return True

    def account(self, user_id, create=False):
        account = self.db.query(LoyaltyAccount).filter_by(user_id=user_id).one_or_none()
        if account is None and create:
            account = LoyaltyAccount(user_id=user_id)
            self.db.add(account)
            self.db.flush()
        return account

    def transaction(self, key):
        return self.db.query(LoyaltyTransaction).filter_by(idempotency_key=key).one_or_none()

    def add_transaction(self, account_id, order_id, kind, amount, key):
        self.db.add(LoyaltyTransaction(
            account_id=account_id, order_id=order_id, amount=amount,
            type=kind, idempotency_key=key,
        ))

    def create_promo(self, data):
        promo = PromoCode(**data)
        self.db.add(promo)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise LoyaltyError("Промокод с таким кодом уже существует", 409) from exc
        return promo.code

    def expire(self, now):
        count = self.db.query(PromoCode).filter(
            PromoCode.is_active.is_(True), PromoCode.valid_until <= now
        ).update({PromoCode.is_active: False})
        self.db.commit()
        return count

    def commit(self):
        self.db.commit()
