import json
import os
from pathlib import Path

from locust import FastHttpUser, between, task

fixture_path = os.getenv("LOAD_FIXTURE")
fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8")) if fixture_path else None
tokens = iter(fixture["tokens"]) if fixture else None


class SiriusUser(FastHttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        if fixture is None:
            raise RuntimeError("Укажите LOAD_FIXTURE, созданный scripts.prepare_lab10_load")
        self.headers = {"Authorization": f"Bearer {next(tokens)}"}
        self.item_id = fixture["item_id"]

    @task(7)
    def get_menu(self):
        self.client.get("/menu/items")

    @task(2)
    def get_item(self):
        self.client.get(f"/menu/items/{self.item_id}", name="/menu/items/{id}")

    @task(1)
    def create_order(self):
        self.client.post("/orders/create", json={"item_id": self.item_id, "quantity": 1},
                         headers=self.headers)
