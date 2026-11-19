"""Diagnosis app URL routing."""

from __future__ import annotations

from rest_framework.routers import DefaultRouter

from diagnosis.views import DiagnosisKeywordViewSet

app_name = "diagnosis"

router = DefaultRouter()
router.register("keywords", DiagnosisKeywordViewSet, basename="keyword")

urlpatterns = router.urls
