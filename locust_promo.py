import json
import os
from collections import Counter
from pathlib import Path

import gevent
from gevent.event import Event
from locust import FastHttpUser, events, task
from locust.exception import StopUser


fixture = json.loads(Path(os.environ["PROMO_LOAD_FIXTURE"]).read_text(encoding="utf-8"))
tokens = iter(fixture["tokens"])
barrier = Event()
results = Counter()
started = 0


class PromoAttempt(FastHttpUser):
    @task
    def reserve_once(self):
        global started
        token = next(tokens)
        started += 1
        if started == len(fixture["tokens"]):
            barrier.set()
        barrier.wait()
        with self.client.post(
            "/orders/create",
            json={"item_id": fixture["item_id"], "quantity": 1, "promo_code": fixture["promo_code"]},
            headers={"Authorization": f"Bearer {token}"},
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                results["applied"] += 1
            elif response.status_code == 400 and response.json().get("detail") == "Промокод исчерпан":
                results["exhausted"] += 1
                response.success()
            else:
                results["unexpected"] += 1
                response.failure(f"Неожиданный ответ {response.status_code}")
        if sum(results.values()) == len(fixture["tokens"]):
            gevent.spawn(self.environment.runner.quit)
        raise StopUser()


@events.quitting.add_listener
def verify(environment, **kwargs):
    print(json.dumps(dict(results)))
    environment.process_exit_code = 0 if results == {"applied": 1, "exhausted": 999} else 1
