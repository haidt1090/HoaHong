from __future__ import annotations

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from reports.views import (
    DepartmentReportTemplateViewSet,
    ReportTemplateViewSet,
    ReportViewSet,
)

app_name = "reports"

router = DefaultRouter()
router.register("reports", ReportViewSet, basename="report")
# NOTE: mounted as /api/report-templates/ and /api/department-report-templates/
# rather than the /api/templates/report/ shape in the sprint doc, because
# examinations.urls already registers "templates" -> DepartmentTemplateViewSet.
# A nested "report" segment would be swallowed by that router's detail route
# (/api/templates/{pk}/) since DRF's default pk regex matches any non-slash.
router.register("report-templates", ReportTemplateViewSet, basename="report-template")
router.register(
    "department-report-templates",
    DepartmentReportTemplateViewSet,
    basename="department-report-template",
)

urlpatterns = [
    path("", include(router.urls)),
    # Aliases matching the sprint spec's /api/templates/... paths. These work
    # because config.urls includes reports.urls *before* examinations.urls,
    # whose /api/templates/{pk}/ detail route would otherwise match "report"
    # and "department" as primary keys.
    path(
        "templates/report/",
        ReportTemplateViewSet.as_view({"get": "list", "post": "create"}),
        name="report-template-alias-list",
    ),
    path(
        "templates/report/<uuid:pk>/",
        ReportTemplateViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="report-template-alias-detail",
    ),
    path(
        "templates/department/",
        DepartmentReportTemplateViewSet.as_view({"get": "list", "post": "create"}),
        name="department-report-template-alias-list",
    ),
    path(
        "templates/department/<uuid:pk>/",
        DepartmentReportTemplateViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="department-report-template-alias-detail",
    ),
]
