"""Pagination for the catalog API.

Choice: PageNumberPagination (offset-style ``?page=2``), documented in
docs/ARCHITECTURE.md. Simple, stable URLs, works well with filters and search;
cursor-based pagination would only matter for very large, frequently-updating
feeds, which product listings are not.
"""

from rest_framework.pagination import PageNumberPagination


class CatalogPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
