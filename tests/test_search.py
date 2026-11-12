import os
import json

os.environ.setdefault("SECRET_KEY", "test-secret-that-has-at-least-32-characters")
os.environ.setdefault("DATABASE_URL", "sqlite://")

import httpx
import pytest

from app.modules.search.repository import SearchRepository
from app.modules.search.service import SearchService


def test_search_builds_filters_boosts_facets_and_pagination():
    captured = {}

    def handler(request):
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={
            "hits": {"total": {"value": 0}, "hits": []},
            "aggregations": {"categories": {"buckets": []},
                             "price_ranges": {"buckets": []}},
        })

    client = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://es")
    repository = SearchRepository(client)
    result = SearchService(repository).search("сырники", "Завтрак", 100, 300, 2, 10)
    assert result["page"] == 2
    assert captured["from"] == 10
    assert {"term": {"category": "Завтрак"}} in captured["query"]["bool"]["filter"]
    assert {"range": {"price": {"gte": 100, "lte": 300}}} in captured["query"]["bool"]["filter"]
    assert captured["query"]["bool"]["must"][0]["bool"]["should"][0]["term"]["name.keyword"]["boost"] == 20
    assert "categories" in captured["aggs"]
    assert "price_ranges" in captured["aggs"]
    client.close()


def test_invalid_price_range():
    with pytest.raises(ValueError):
        SearchService(None).search("", None, 300, 100, 1, 20)
