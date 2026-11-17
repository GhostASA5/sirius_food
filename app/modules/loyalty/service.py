from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP


CENT = Decimal("0.01")
ZERO = Decimal("0.00")
RATES = {"Bronze": Decimal("0.03"), "Silver": Decimal("0.05"), "Gold": Decimal("0.07")}
SILVER_THRESHOLD = Decimal("100")
GOLD_THRESHOLD = Decimal("500")


class LoyaltyError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def money(value):
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def utc(value):
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class LoyaltyService:
    def __init__(self, repository, silver=SILVER_THRESHOLD, gold=GOLD_THRESHOLD):
        self.repository = repository
        self.silver = silver
        self.gold = gold

    def apply_promo(self, code, user_id, amount):
        promo = self.repository.lock_promo(code.strip().upper())
        if promo is None or not promo.is_active:
            raise LoyaltyError("Промокод недоступен")
        now = datetime.now(timezone.utc)
        if not utc(promo.valid_from) <= now < utc(promo.valid_until):
            raise LoyaltyError("Промокод вне срока действия")
        if promo.current_uses >= promo.max_uses:
            raise LoyaltyError("Промокод исчерпан")
        if amount < promo.min_order_amount:
            raise LoyaltyError("Сумма заказа меньше минимальной для промокода")
        if promo.once_per_user and self.repository.has_usage(promo.id, user_id):
            raise LoyaltyError("Пользователь уже применял промокод")
        discount = promo.discount_value
        if promo.discount_type == "percent":
            discount = money(amount * discount / 100)
        return max(ZERO, amount - discount), promo

    def spend(self, order, amount, points):
        if points < ZERO or points != money(points):
            raise LoyaltyError("Укажите неотрицательную сумму с точностью до сотых")
        if points > amount / 2:
            raise LoyaltyError("Баллами можно оплатить не более 50% заказа после скидки")
        account = self.repository.account(order.user_id)
        if account is None or account.balance < points:
            raise LoyaltyError("Недостаточно баллов")
        self._record(account, order.id, "spend", -points, f"spend_order_{order.id}")

    def earn(self, order, amount):
        if order.status not in {"paid", "delivered"}:
            return False
        key = f"earn_order_{order.id}"
        if self.repository.transaction(key) is not None:
            return False
        account = self.repository.account(order.user_id, create=True)
        points = money(amount * RATES[account.tier])
        self._record(account, order.id, "earn", points, key)
        return True

    def compensate(self, order):
        if order.status != "cancelled":
            return False
        account = self.repository.account(order.user_id)
        if account is None:
            return False
        changed = False
        for source, kind, key in (
            ("spend", "refund", f"refund_order_{order.id}"),
            ("earn", "revoke", f"revoke_earn_order_{order.id}"),
        ):
            original = self.repository.transaction(f"{source}_order_{order.id}")
            if original is not None and self.repository.transaction(key) is None:
                self._record(account, order.id, kind, -original.amount, key)
                changed = True
        return changed

    def _record(self, account, order_id, kind, delta, key):
        account.balance += delta
        if kind in {"earn", "revoke"}:
            account.total_earned += delta
            if account.total_earned >= self.gold:
                account.tier = "Gold"
            elif account.total_earned >= self.silver:
                account.tier = "Silver"
            else:
                account.tier = "Bronze"
        self.repository.add_transaction(account.id, order_id, kind, delta, key)

    def create_promo(self, data):
        data = {**data, "code": data["code"].strip().upper()}
        if not data["code"]:
            raise LoyaltyError("Промокод не может быть пустым")
        if data["valid_from"] >= data["valid_until"]:
            raise LoyaltyError("Начало действия должно предшествовать окончанию")
        if data["discount_type"] == "percent" and data["discount_value"] > 100:
            raise LoyaltyError("Процент скидки не может превышать 100")
        return self.repository.create_promo(data)

    def set_active(self, code, is_active):
        promo = self.repository.lock_promo(code.strip().upper())
        if promo is None:
            raise LoyaltyError("Промокод не найден", 404)
        promo.is_active = is_active
        self.repository.commit()

    def summary(self, user_id):
        account = self.repository.account(user_id)
        return {
            "balance": account.balance if account else ZERO,
            "total_earned": account.total_earned if account else ZERO,
            "tier": account.tier if account else "Bronze",
        }
