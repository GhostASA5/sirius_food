from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_role
from app.database import get_db
from app.models import User
from app.modules.loyalty.repository import LoyaltyRepository
from app.modules.loyalty.service import LoyaltyError, LoyaltyService


router = APIRouter(tags=["loyalty"])


class PromoCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    discount_type: Literal["percent", "fixed"]
    discount_value: Decimal = Field(gt=0, max_digits=16, decimal_places=2)
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    max_uses: int = Field(gt=0, le=2_147_483_647)
    min_order_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=16, decimal_places=2)
    once_per_user: bool = True


class PromoStatus(BaseModel):
    is_active: bool


@router.post("/promos", status_code=201, dependencies=[Depends(require_role("admin"))])
def create_promo(payload: PromoCreate, db: Session = Depends(get_db)):
    try:
        return {"code": LoyaltyService(LoyaltyRepository(db)).create_promo(payload.model_dump())}
    except LoyaltyError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@router.patch("/promos/{code}", dependencies=[Depends(require_role("admin"))])
def set_active(code: str, payload: PromoStatus, db: Session = Depends(get_db)):
    try:
        LoyaltyService(LoyaltyRepository(db)).set_active(code, payload.is_active)
    except LoyaltyError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    return {"is_active": payload.is_active}


@router.get("/loyalty/me")
def my_loyalty(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return LoyaltyService(LoyaltyRepository(db)).summary(user.id)
