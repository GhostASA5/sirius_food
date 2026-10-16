from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.repository import AuthRepository
from app.modules.auth.service import AuthError, AuthService


router = APIRouter()


class LoginSchema(BaseModel):
    email: EmailStr
    password: str


class RefreshSchema(BaseModel):
    refresh_token: str


@router.post("/login")
def login(payload: LoginSchema, db: Session = Depends(get_db)):
    try:
        return AuthService(AuthRepository(db)).login(str(payload.email), payload.password)
    except AuthError as exc:
        raise HTTPException(401, str(exc)) from exc


@router.post("/refresh")
def refresh(payload: RefreshSchema, db: Session = Depends(get_db)):
    try:
        return AuthService(AuthRepository(db)).refresh(payload.refresh_token)
    except AuthError as exc:
        raise HTTPException(401, str(exc)) from exc
