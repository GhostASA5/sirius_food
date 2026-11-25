import os

os.environ.setdefault("SECRET_KEY", "test-secret-that-has-at-least-32-characters")
os.environ.setdefault("DATABASE_URL", "sqlite://")
