from fastapi import APIRouter, Depends, HTTPException, Query

from app.modules.search.repository import SearchRepository, SearchUnavailable
from app.modules.search.service import SearchService


router = APIRouter()


def get_search_repository():
    repository = SearchRepository()
    try:
        yield repository
    finally:
        repository.close()


@router.get("/suggest")
def suggest(q: str = Query(min_length=2), repository: SearchRepository = Depends(get_search_repository)):
    try:
        return {"suggestions": SearchService(repository).suggest(q.strip())}
    except SearchUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@router.get("")
def search(
    q: str = "", category: str | None = None,
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    page: int = Query(default=1, ge=1), size: int = Query(default=20, ge=1, le=100),
    repository: SearchRepository = Depends(get_search_repository),
):
    try:
        return SearchService(repository).search(q.strip(), category, min_price, max_price, page, size)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except SearchUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
