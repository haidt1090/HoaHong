from __future__ import annotations

from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from patients.models import Patient


@admin.register(Patient)
class PatientAdmin(SimpleHistoryAdmin):
    list_display = (
        "full_name",
        "employee_code",
        "company",
        "gender",
        "dob",
        "is_active",
    )
    list_filter = ("is_active", "gender", "company")
    search_fields = ("full_name", "employee_code", "cccd", "phone")
    autocomplete_fields = ("company",)
    ordering = ("full_name",)
