from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    phone: str | None = None


class UserResponse(BaseModel):
    id: int
    email: str
    balance: float

    model_config = ConfigDict(from_attributes=True)


class MenuItemCreate(BaseModel):
    name: str
    price: float
    category_id: int | None = None
    description: str | None = None


class MenuItemUpdate(BaseModel):
    name: str | None = None
    price: float | None = None
    is_available: bool | None = None
    category_id: int | None = None
    description: str | None = None


class MenuCategoryCreate(BaseModel):
    name: str


class OrderCreate(BaseModel):
    item_id: int
    quantity: int
    promo_code: str | None = Field(default=None, min_length=1, max_length=64)


class OrderPay(BaseModel):
    points: Decimal = Field(default=Decimal("0.00"), ge=0, max_digits=16, decimal_places=2)


class DeliveryAssign(BaseModel):
    order_id: int
    courier_id: int
