"""Shared pagination classes for DRF views."""

from __future__ import annotations

from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    """Page-based pagination with a client-adjustable page size."""

    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200
