from __future__ import annotations

from collections import OrderedDict

from django.contrib.admin import AdminSite
from django.contrib.admin.apps import AdminConfig
from django.urls import NoReverseMatch, reverse


class CustomAdminConfig(AdminConfig):
    default_site = "core.admin.CustomAdminSite"


class CustomAdminSite(AdminSite):
    site_header = "Hospital Admin Portal"
    site_title = "Admin Portal"
    index_title = "Dashboard"

    # App labels → display names, ordered by prefix number
    APP_ORDER: dict[str, str] = {
        "accounts": "1. Tài khoản & Phân quyền",
        "patients": "2. Bệnh nhân & Công ty",
        "examinations": "3. Khám bệnh",
        "diagnosis": "4. Chẩn đoán",
        "reports": "5. Báo cáo",
        "core": "6. Hệ thống",
    }

    # Per-app model order (object_name → position prefix)
    MODEL_ORDER: dict[str, list[str]] = {
        "accounts": ["User", "Company", "StaffAssignment", "CompanyExamPackage"],
        "patients": ["Patient"],
        "examinations": [
            "Department",
            "DepartmentTemplate",
            "DepartmentField",
            "DepartmentFieldAbnormal",
            "ExamPackage",
            "Examination",
            "DepartmentResult",
            "ImportJob",
            "ExportJob",
        ],
        "diagnosis": ["DiagnosisKeyword"],
        "reports": [
            "DepartmentReportTemplate",
            "ReportTemplate",
            "Report",
            "EmployeeExamReport",
        ],
    }

    def get_app_list(self, request, app_label=None):
        app_dict = self._build_app_dict(request, app_label)

        ordered = OrderedDict()
        # Add apps in our defined order
        for app_name in self.APP_ORDER:
            if app_name in app_dict:
                ordered[app_name] = app_dict.pop(app_name)
        # Append remaining apps
        ordered.update(app_dict)

        app_list = []
        for app_label, app_info in ordered.items():
            app_info["name"] = self.APP_ORDER.get(app_label, app_info["name"])

            # Reorder models within this app
            model_order = self.MODEL_ORDER.get(app_label, [])
            models = app_info.get("models", [])
            if model_order and models:
                model_map = {m["object_name"]: m for m in models}
                ordered_models = []
                for obj_name in model_order:
                    if obj_name in model_map:
                        ordered_models.append(model_map.pop(obj_name))
                # Append any models not in the order list
                ordered_models.extend(model_map.values())
                app_info["models"] = ordered_models

            if app_label == "reports" and self._can_view_template_guide(request):
                guide = self._template_guide_model()
                if guide:
                    app_info["models"].insert(0, guide)

            app_list.append(app_info)

        return app_list

    @staticmethod
    def _can_view_template_guide(request) -> bool:
        user = request.user
        return bool(
            user.is_active
            and user.is_staff
            and (
                user.is_superuser
                or user.has_perm("reports.view_reporttemplate")
                or user.has_perm("reports.change_reporttemplate")
                or user.has_perm("reports.view_departmentreporttemplate")
                or user.has_perm("reports.change_departmentreporttemplate")
            )
        )

    def _template_guide_model(self) -> dict | None:
        try:
            url = reverse("admin:reports_template_guide")
        except NoReverseMatch:
            return None
        return {
            "name": "Hướng dẫn mã template",
            "object_name": "TemplateGuide",
            "perms": {"add": False, "change": True, "delete": False, "view": True},
            "admin_url": url,
            "add_url": None,
            "view_only": True,
        }
