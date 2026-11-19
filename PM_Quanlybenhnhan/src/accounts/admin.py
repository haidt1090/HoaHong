from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.models import Company, CompanyExamPackage, StaffAssignment, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    model = User
    list_display = ("email", "full_name", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email", "full_name", "phone")
    ordering = ("email",)
    filter_horizontal = ("groups", "user_permissions")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("full_name", "phone", "company")}),
        (
            "Chữ ký số",
            {"fields": ("signature_image", "signature_base64")},
        ),
        ("Role", {"fields": ("role", "must_change_password")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "role", "password1", "password2"),
            },
        ),
    )


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "created_at")
    search_fields = ("name", "code")


@admin.register(StaffAssignment)
class StaffAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "company", "assigned_at")
    list_filter = ("user__role",)
    search_fields = ("user__email", "company__name")


@admin.register(CompanyExamPackage)
class CompanyExamPackageAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "package_name",
        "pricing_mode",
        "package_price_display",
        "total_employees",
        "total_cost_display",
        "is_active",
    )
    list_filter = ("pricing_mode", "is_active")
    search_fields = ("company__name",)

    @admin.display(description="Tổng chi phí")
    def total_cost_display(self, obj):
        cost = obj.total_cost
        return f"{cost:,} VNĐ" if cost else "—"

    @admin.display(description="Gói khám")
    def package_name(self, obj):
        return obj.exam_package.name

    @admin.display(description="Giá gói/người")
    def package_price_display(self, obj):
        price = _package_per_person_price(obj)
        return f"{price:,} VNĐ" if price else "—"


def _package_per_person_price(obj):
    """Return the per-person price of the exam package."""
    if not obj.exam_package_id:
        return 0
    if obj.pricing_mode == "package_total":
        return obj.exam_package.default_package_price or 0
    if obj.pricing_mode == "per_field":
        total = 0
        for epd in obj.exam_package.package_departments.select_related(
            "template"
        ).all():
            for field in epd.template.fields_config:
                total += field.get("default_price", 0) or 0
        return total
    return 0
