from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class HealthCheckTests(APITestCase):
    def test_healthcheck_returns_ok(self) -> None:
        response = self.client.get(reverse("api-health"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {"status": "ok", "db": "ok", "redis": "ok"},
        )
