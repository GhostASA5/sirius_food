import json
import time
from uuid import uuid4

import httpx

from app.core.jwt import create_access_token
from app.database import SessionLocal
from app.models import MenuItem, Role, User


def main():
    cid = "demo-" + uuid4().hex[:12]
    with SessionLocal() as db:
        student = db.query(Role).filter_by(name="student").one()
        courier_role = db.query(Role).filter_by(name="courier").one()
        buyer = User(email=f"{cid}@example.com", role_id=student.id, balance=1000)
        courier = User(email=f"{cid}-courier@example.com", role_id=courier_role.id)
        item = db.query(MenuItem).filter(MenuItem.is_available.is_(True), MenuItem.price < 1000).first()
        if item is None:
            raise RuntimeError("Для демонстрации нужно доступное блюдо дешевле 1000")
        item_id = item.id
        db.add_all([buyer, courier])
        db.commit()
        token = create_access_token(buyer.id)
    headers = {"Authorization": f"Bearer {token}", "X-Correlation-ID": cid}
    with httpx.Client(base_url="http://localhost:8000", timeout=15) as client:
        response = client.post("/orders/create", json={"item_id": item_id, "quantity": 1}, headers=headers)
        response.raise_for_status()
        order_id = response.json()["order_id"]
        assert response.headers["X-Correlation-ID"] == cid
        response = client.post(f"/orders/{order_id}/pay", headers=headers)
        response.raise_for_status()
    print(json.dumps({"correlation_id": cid, "order_id": order_id}))


if __name__ == "__main__":
    main()
