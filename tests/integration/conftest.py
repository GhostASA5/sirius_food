import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

os.environ.setdefault("SECRET_KEY", "integration-test-secret-at-least-32-characters")
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from app.core.jwt import create_access_token
from app.database import get_db
from app.main import app
from app.models import MenuItem, Role, User
from tests.fakes import FakeCache


@pytest.fixture(scope="session")
def postgres():
    with PostgresContainer("postgres:15") as container:
        url = container.get_connection_url()
        env = {**os.environ, "DATABASE_URL": url,
               "SECRET_KEY": "integration-test-secret-at-least-32-characters"}
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=Path(__file__).resolve().parents[2], env=env, check=True,
        )
        yield url


@pytest.fixture
def db(postgres):
    engine = create_engine(postgres)
    with engine.connect() as connection:
        transaction = connection.begin()
        factory = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
        with factory() as session:
            yield session
        transaction.rollback()
    engine.dispose()


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr("app.modules.menu.repository.get_redis_client", FakeCache)
    monkeypatch.setattr("app.modules.orders.router.CeleryOrderNotifications", Mock)
    role = db.query(Role).filter_by(name="student").one()
    buyer = User(email="integration@example.com", role_id=role.id, balance=1000)
    item = MenuItem(name="Сырники интеграционные", price=150, is_available=True)
    db.add_all([buyer, item])
    db.commit()
    headers = {"Authorization": f"Bearer {create_access_token(buyer.id)}"}

    def override():
        yield db

    old = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app) as http:
            yield http, headers, buyer.id, item.id
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old)
