import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.jwt import create_access_token
from app.database import SessionLocal
from app.models import MenuItem, PromoCode, Role, User


def main():
    run_id = uuid4().hex
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        role = db.query(Role).filter_by(name="student").one()
        users = [
            User(email=f"load-{run_id}-{index}@example.com", balance=100, role_id=role.id)
            for index in range(1000)
        ]
        item = MenuItem(name=f"Тест нагрузки {run_id}", price=100, is_available=True)
        promo = PromoCode(
            code=f"LOAD-{run_id.upper()}", discount_type="fixed", discount_value=1,
            valid_from=now, valid_until=now + timedelta(hours=1),
            max_uses=1, min_order_amount=0,
        )
        db.add_all([item, promo, *users])
        db.flush()
        fixture = {
            "promo_code": promo.code, "item_id": item.id,
            "tokens": [create_access_token(user.id) for user in users],
        }
        db.commit()
    print(json.dumps(fixture))


if __name__ == "__main__":
    main()
