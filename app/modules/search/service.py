class SearchService:
    def __init__(self, repository):
        self.repository = repository

    def search(self, query, category, min_price, max_price, page, size):
        if min_price is not None and max_price is not None and min_price > max_price:
            raise ValueError("min_price больше max_price")
        return self.repository.search(query, category, min_price, max_price, page, size)

    def suggest(self, query):
        return self.repository.suggest(query)
