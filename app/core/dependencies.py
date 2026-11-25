from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session, joinedload

from app.core.jwt import decode_token
from app.database import get_db
from app.models import User
import sentry_sdk


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(401, "Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    try:
        user_id = int(decode_token(credentials.credentials, "access")["sub"])
    except (JWTError, ValueError, KeyError) as exc:
        raise HTTPException(401, "Invalid token", headers={"WWW-Authenticate": "Bearer"}) from exc
    try:
        user = db.query(User).options(joinedload(User.role)).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(401, "User not found", headers={"WWW-Authenticate": "Bearer"})
        if user.is_blocked:
            raise HTTPException(403, "User is blocked")
        sentry_sdk.set_user({"id": str(user.id)})
        db.expunge(user.role)
        db.expunge(user)
        return user
    finally:
        db.rollback()


def require_role(*allowed_roles: str):
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.name != "admin" and current_user.role.name not in allowed_roles:
            raise HTTPException(403, "Access denied")
        return current_user

    return checker
