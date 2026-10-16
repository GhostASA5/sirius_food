from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Protocol

from jose import JWTError

from app.core.jwt import create_access_token, create_refresh_token, decode_token
from app.core.security import verify_password


class AuthRepositoryPort(Protocol):
    def get_by_email(self, email: str): ...
    def get_by_id(self, user_id: int): ...
    def save_refresh_token(self, user_id: int, token_hash: str, expires_at: datetime): ...
    def get_refresh_token(self, token_hash: str): ...


class AuthError(Exception):
    pass


class AuthService:
    def __init__(self, repository: AuthRepositoryPort):
        self.repository = repository

    def login(self, email: str, password: str) -> dict:
        user = self.repository.get_by_email(email)
        if user is None or not user.password_hash or not verify_password(password, user.password_hash):
            raise AuthError("Invalid credentials")
        if user.is_blocked:
            raise AuthError("Invalid credentials")
        return self._tokens(user.id)

    def refresh(self, refresh_token: str) -> dict:
        try:
            payload = decode_token(refresh_token, "refresh")
            user_id = int(payload["sub"])
        except (JWTError, ValueError, KeyError) as exc:
            raise AuthError("Invalid refresh token") from exc
        token_hash = sha256(refresh_token.encode()).hexdigest()
        stored = self.repository.get_refresh_token(token_hash)
        user = self.repository.get_by_id(user_id)
        expires_at = stored.expires_at if stored is not None else None
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if (
            stored is None
            or stored.user_id != user_id
            or stored.is_revoked
            or expires_at < datetime.now(timezone.utc)
            or user is None
            or user.is_blocked
        ):
            raise AuthError("Invalid refresh token")
        return {"access_token": create_access_token(user_id), "token_type": "bearer"}

    def _tokens(self, user_id: int) -> dict:
        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token(user_id)
        self.repository.save_refresh_token(
            user_id,
            sha256(refresh_token.encode()).hexdigest(),
            datetime.now(timezone.utc) + timedelta(days=7),
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }
