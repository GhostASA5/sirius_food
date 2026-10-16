from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SECRET_KEY: str
    DATABASE_URL: str = "postgresql://sirius:sirius@localhost:5432/sirius_food"
    DEBUG: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if len(settings.SECRET_KEY) < 32:
        raise ValueError("SECRET_KEY must contain at least 32 characters")
    return settings
