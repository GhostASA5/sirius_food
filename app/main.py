from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from app.core.observability import CorrelationMiddleware
from app.modules.observability.router import router as observability_router

from app.core.config import get_settings
from app.database import get_db
from app.modules.auth.router import router as auth_router
from app.modules.delivery.router import router as delivery_router
from app.modules.menu.router import router as menu_router
from app.modules.menu.repository import MenuRepository
from app.modules.orders.router import router as orders_router
from app.modules.users.router import router as users_router
from app.modules.search.router import router as search_router
from app.modules.loyalty.router import router as loyalty_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    provider = app.dependency_overrides.get(get_db, get_db)
    db_generator = provider()
    try:
        MenuRepository(next(db_generator)).warm_all()
    finally:
        db_generator.close()
    yield


app = FastAPI(
    title="Sirius.Food API",
    docs_url="/docs" if get_settings().DEBUG else None,
    redoc_url=None,
    lifespan=lifespan,
)
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(users_router, prefix="/users", tags=["users"])
app.include_router(menu_router, prefix="/menu", tags=["menu"])
app.include_router(orders_router, prefix="/orders", tags=["orders"])
app.include_router(delivery_router, prefix="/delivery", tags=["delivery"])
app.include_router(search_router, prefix="/search", tags=["search"])
app.include_router(loyalty_router)
app.include_router(observability_router)
app.add_middleware(CorrelationMiddleware)
Instrumentator(excluded_handlers=["/metrics"]).instrument(app).expose(app)
FastAPIInstrumentor.instrument_app(app, excluded_urls="/metrics")
