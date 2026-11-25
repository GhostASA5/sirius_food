from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.dependencies import require_role

router = APIRouter()


@router.get("/observability/test-error", dependencies=[Depends(require_role("admin"))])
def test_error():
    if not get_settings().DEBUG:
        from fastapi import HTTPException
        raise HTTPException(404, "Not found")
    raise RuntimeError("Проверочная ошибка observability")
