from datetime import datetime

from sqlalchemy.orm import Session

from app.models import RefreshToken, User


class AuthRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str):
        return self.db.query(User).filter(User.email == email).first()

    def get_by_id(self, user_id: int):
        return self.db.query(User).filter(User.id == user_id).first()

    def save_refresh_token(self, user_id: int, token_hash: str, expires_at: datetime):
        self.db.add(RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at))
        self.db.commit()

    def get_refresh_token(self, token_hash: str):
        return self.db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
