from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from examinations.views import (
    DepartmentImportViewSet,
    DepartmentTemplateViewSet,
    DepartmentViewSet,
    ExaminationViewSet,
    ExamPackageViewSet,
    ExportJobViewSet,
    ImportJobViewSet,
)

app_name = "examinations"

router = DefaultRouter()
router.register("departments", DepartmentViewSet, basename="department")
router.register("templates", DepartmentTemplateViewSet, basename="template")
router.register("packages", ExamPackageViewSet, basename="package")
router.register("examinations", ExaminationViewSet, basename="examination")
router.register("import", ImportJobViewSet, basename="import-job")
router.register("export", ExportJobViewSet, basename="export-job")

urlpatterns = router.urls + [
    path(
        "examinations/import/<uuid:department_id>/",
        DepartmentImportViewSet.as_view({"post": "create"}),
        name="department-import",
    ),
]
