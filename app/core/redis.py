from functools import lru_cache

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import get_settings


@lru_cache
def get_redis_client() -> Redis:
    return Redis.from_url(
        get_settings().REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=0.3,
        socket_timeout=0.5,
    )


def check_redis_connection() -> bool:
    try:
        return bool(get_redis_client().ping())
    except RedisError:
        return False
