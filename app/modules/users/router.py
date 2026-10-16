from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.users.repository import UserRepository
from app.modules.users.service import UserError, UserService
from app.schemas import UserCreate

router = APIRouter()


@router.post("/register")
def register_user(payload: UserCreate, db: Session = Depends(get_db)):
    if payload.phone and len(payload.phone) < 10:
        raise HTTPException(400, "Некорректный формат номера телефона")
    try:
        user = UserService(UserRepository(db)).register(str(payload.email), payload.phone)
    except UserError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    return {"status": "success", "user_id": user.id, "email": user.email}


@router.post("/{user_id}/topup")
def top_up_balance(user_id: int, amount: float, db: Session = Depends(get_db)):
    if amount <= 0:
        raise HTTPException(400, "Сумма пополнения должна быть положительной")
    try:
        balance = UserService(UserRepository(db)).top_up_balance(user_id, amount)
    except UserError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    return {"status": "success", "new_balance": balance}
