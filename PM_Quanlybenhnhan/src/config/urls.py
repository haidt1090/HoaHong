from __future__ import annotations

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from core.views import HealthCheckView
from reports.public_views import public_result_view

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("patients.urls")),
    # reports must precede examinations: examinations registers
    # "templates" -> DepartmentTemplateViewSet, whose detail route
    # /api/templates/{pk}/ would otherwise swallow the report-template
    # aliases /api/templates/report/ and /api/templates/department/.
    path("api/", include("reports.urls")),
    path("api/", include("examinations.urls")),
    path("api/diagnosis/", include("diagnosis.urls")),
    path("api/sync/", include("nationalsync.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("__debug__/", include("debug_toolbar.urls")),
    path("api/health/", HealthCheckView.as_view(), name="api-health"),
    path("ket-qua/<uuid:exam_id>/", public_result_view, name="public-result"),
]
