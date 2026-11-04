from contextlib import contextmanager
from threading import Lock


class FakeCache:
    def __init__(self):
        self.data = {}
        self.ttls = {}
        self.locks = {}

    def get(self, key):
        return self.data.get(key)

    def setex(self, key, ttl, value):
        self.data[key] = value
        self.ttls[key] = ttl

    def delete(self, *keys):
        for key in keys:
            self.data.pop(key, None)
            self.ttls.pop(key, None)

    @contextmanager
    def lock(self, key, timeout=None, blocking_timeout=None):
        lock = self.locks.setdefault(key, Lock())
        lock.acquire()
        try:
            yield
        finally:
            lock.release()
