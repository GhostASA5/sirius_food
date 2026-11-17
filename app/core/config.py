from decimal import Decimal
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SECRET_KEY: str
    DATABASE_URL: str = "postgresql://sirius:sirius@localhost:5432/sirius_food"
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    SIMULATE_EMAIL_FAILURES: bool = False
    DELIVERY_GRPC_TARGET: str = "localhost:50051"
    RABBITMQ_URL: str = "amqp://sirius:sirius@localhost:5672/"
    ELASTICSEARCH_URL: str = "http://localhost:9200"
    LOYALTY_SILVER: Decimal = Decimal("100")
    LOYALTY_GOLD: Decimal = Decimal("500")
    DEBUG: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if len(settings.SECRET_KEY) < 32:
        raise ValueError("SECRET_KEY must contain at least 32 characters")
    if not Decimal("0") < settings.LOYALTY_SILVER < settings.LOYALTY_GOLD:
        raise ValueError("Пороги лояльности должны удовлетворять 0 < SILVER < GOLD")
    return settings
