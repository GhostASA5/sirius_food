import json
from uuid import uuid4

from app.core.jwt import create_access_token
from app.database import SessionLocal
from app.models import MenuItem, Role, User


def main():
    suffix = uuid4().hex
    with SessionLocal() as db:
        role = db.query(Role).filter_by(name="student").one()
        item = MenuItem(name=f"Нагрузка ЛР10 {suffix}", price=1, is_available=True)
        users = [User(email=f"lab10-{suffix}-{index}@example.com", role_id=role.id,
                      balance=100000) for index in range(200)]
        db.add_all([item, *users])
        db.flush()
        data = {"item_id": item.id, "tokens": [create_access_token(user.id) for user in users]}
        db.commit()
    print(json.dumps(data))


if __name__ == "__main__":
    main()
