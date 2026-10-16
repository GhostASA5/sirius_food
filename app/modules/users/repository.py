from sqlalchemy.orm import Session

from app.models import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str):
        return self.db.query(User).filter(User.email == email).first()

    def get_by_id(self, user_id: int):
        return self.db.query(User).filter(User.id == user_id).first()

    def create(self, email: str, phone: str | None):
        user = User(email=email, phone=phone, balance=0.0, is_blocked=False)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def save(self, user):
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
