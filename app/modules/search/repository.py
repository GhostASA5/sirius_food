import httpx

from app.core.config import get_settings


INDEX = "menu"
MAPPING = {
    "settings": {
        "analysis": {
            "filter": {"prefix_filter": {"type": "edge_ngram", "min_gram": 2, "max_gram": 20}},
            "analyzer": {
                "prefix_index": {"tokenizer": "standard", "filter": ["lowercase", "prefix_filter"]},
                "prefix_search": {"tokenizer": "standard", "filter": ["lowercase"]},
            },
        }
    },
    "mappings": {"properties": {
        "name": {"type": "text", "analyzer": "russian", "fields": {
            "keyword": {"type": "keyword"},
            "suggest": {"type": "text", "analyzer": "prefix_index", "search_analyzer": "prefix_search"},
        }},
        "description": {"type": "text", "analyzer": "russian"},
        "category": {"type": "keyword"},
        "category_id": {"type": "integer"},
        "price": {"type": "float"},
        "is_available": {"type": "boolean"},
    }},
}


class SearchUnavailable(Exception):
    pass


class SearchRepository:
    def __init__(self, client=None):
        self.client = client or httpx.Client(base_url=get_settings().ELASTICSEARCH_URL, timeout=5)
        self.owns_client = client is None

    def close(self):
        if self.owns_client:
            self.client.close()

    def _request(self, method, path, **kwargs):
        try:
            response = self.client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SearchUnavailable("Поисковый сервис недоступен") from exc

    def ensure_index(self):
        response = self.client.get(f"/{INDEX}")
        if response.status_code == 404:
            self._request("PUT", f"/{INDEX}", json=MAPPING)
        else:
            try:
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise SearchUnavailable("Поисковый сервис недоступен") from exc

    @staticmethod
    def document(item):
        return {
            "name": item.name,
            "description": item.description or "",
            "category": item.category.name if item.category else None,
            "category_id": item.category_id,
            "price": item.price,
            "is_available": item.is_available,
        }

    def index_item(self, item):
        self._request("PUT", f"/{INDEX}/_doc/{item.id}", json=self.document(item))

    def search(self, query, category, min_price, max_price, page, size):
        filters = [{"term": {"is_available": True}}]
        if category:
            filters.append({"term": {"category": category}})
        price = {}
        if min_price is not None:
            price["gte"] = min_price
        if max_price is not None:
            price["lte"] = max_price
        if price:
            filters.append({"range": {"price": price}})
        if query:
            relevance = {"bool": {"should": [
                {"term": {"name.keyword": {"value": query, "boost": 20}}},
                {"match_phrase": {"name": {"query": query, "boost": 8}}},
                {"multi_match": {"query": query, "fields": ["name^5", "description^2"],
                                 "fuzziness": "AUTO"}},
            ], "minimum_should_match": 1}}
        else:
            relevance = {"match_all": {}}
        body = {
            "from": (page - 1) * size, "size": size,
            "query": {"bool": {"must": [relevance], "filter": filters}},
            "aggs": {
                "categories": {"terms": {"field": "category", "size": 50}},
                "price_ranges": {"range": {"field": "price", "ranges": [
                    {"to": 200}, {"from": 200, "to": 500}, {"from": 500},
                ]}},
            },
        }
        data = self._request("POST", f"/{INDEX}/_search", json=body)
        return {
            "total": data["hits"]["total"]["value"],
            "page": page, "size": size,
            "items": [{"id": int(hit["_id"]), "score": hit.get("_score"), **hit["_source"]}
                      for hit in data["hits"]["hits"]],
            "facets": {
                "categories": [{"name": bucket["key"], "count": bucket["doc_count"]}
                               for bucket in data["aggregations"]["categories"]["buckets"]],
                "price_ranges": [{"from": bucket.get("from"), "to": bucket.get("to"),
                                  "count": bucket["doc_count"]}
                                 for bucket in data["aggregations"]["price_ranges"]["buckets"]],
            },
        }

    def suggest(self, query):
        body = {"size": 10, "_source": ["name"], "query": {"bool": {
            "must": [{"match": {"name.suggest": {"query": query, "operator": "and"}}}],
            "filter": [{"term": {"is_available": True}}],
        }}}
        data = self._request("POST", f"/{INDEX}/_search", json=body)
        return list(dict.fromkeys(hit["_source"]["name"] for hit in data["hits"]["hits"]))[:10]
