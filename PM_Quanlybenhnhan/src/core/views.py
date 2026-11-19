from __future__ import annotations

from typing import Any

from django.core.cache import cache
from django.db import connections
from django.db.utils import OperationalError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    authentication_classes: list[Any] = []
    permission_classes: list[Any] = []

    def get(self, request, *args, **kwargs):
        db_status = "ok"
        redis_status = "ok"
        http_status = status.HTTP_200_OK

        try:
            with connections["default"].cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except OperationalError:
            db_status = "error"
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE

        try:
            cache.set("healthcheck", "ok", timeout=5)
            if cache.get("healthcheck") != "ok":
                raise ConnectionError
        except Exception:
            redis_status = "error"
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE

        return Response(
            {
                "status": "ok" if http_status == status.HTTP_200_OK else "degraded",
                "db": db_status,
                "redis": redis_status,
            },
            status=http_status,
        )
