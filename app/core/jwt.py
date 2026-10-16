from datetime import datetime, timedelta, timezone
from uuid import uuid4

from jose import jwt

from app.core.config import get_settings


ALGORITHM = "HS256"


def create_token(user_id: int, token_type: str, lifetime: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + lifetime,
        "jti": uuid4().hex,
    }
    return jwt.encode(payload, get_settings().SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user_id: int) -> str:
    return create_token(user_id, "access", timedelta(minutes=15))


def create_refresh_token(user_id: int) -> str:
    return create_token(user_id, "refresh", timedelta(days=7))


def decode_token(token: str, expected_type: str) -> dict:
    payload = jwt.decode(token, get_settings().SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") != expected_type or not payload.get("sub"):
        raise ValueError("Invalid token type or subject")
    return payload
