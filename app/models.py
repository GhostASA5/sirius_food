from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False)
    phone = Column(String, nullable=True)
    balance = Column(Float, default=0.0)
    is_blocked = Column(Boolean, default=False)
    password_hash = Column(String, nullable=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    role = relationship("Role")


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token_hash = Column(String, unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)


class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    is_available = Column(Boolean, default=True)
    category_id = Column(Integer, ForeignKey("menu_categories.id"), nullable=True)
    category = relationship("MenuCategory")


class MenuCategory(Base):
    __tablename__ = "menu_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    item_id = Column(Integer, ForeignKey("menu_items.id"))
    quantity = Column(Integer, nullable=False)
    total_amount = Column(Float, nullable=True)
    status = Column(String, default="processing")
    user = relationship("User")
    item = relationship("MenuItem")


class Delivery(Base):
    __tablename__ = "deliveries"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    courier_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String, default="pending")
    order = relationship("Order")
    courier = relationship("User")


class KitchenOrder(Base):
    __tablename__ = "kitchen_orders"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, unique=True)
    status = Column(String, nullable=False, default="pending")


class ProcessedEvent(Base):
    __tablename__ = "processed_events"

    id = Column(String(36), primary_key=True)
    consumer = Column(String(50), primary_key=True)


class OutboxEvent(Base):
    __tablename__ = "outbox"

    id = Column(Integer, primary_key=True)
    event_id = Column(String(36), nullable=False, unique=True)
    routing_key = Column(String(100), nullable=False)
    payload = Column(String, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
