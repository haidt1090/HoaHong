from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from patients.views import (
    CompanyExamPackageViewSet,
    CompanyViewSet,
    PatientViewSet,
)

app_name = "patients"

router = DefaultRouter()
router.register("patients", PatientViewSet, basename="patient")
router.register("companies", CompanyViewSet, basename="company")

# Nested: /api/companies/{company_pk}/packages/
company_packages_router = DefaultRouter()
company_packages_router.register(
    "packages", CompanyExamPackageViewSet, basename="company-package"
)

urlpatterns = router.urls + [
    path(
        "companies/<uuid:company_pk>/",
        include(company_packages_router.urls),
    ),
]
