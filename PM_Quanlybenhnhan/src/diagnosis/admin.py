"""Diagnosis app admin registration."""

from __future__ import annotations

from django.contrib import admin

from diagnosis.models import DiagnosisKeyword


@admin.register(DiagnosisKeyword)
class DiagnosisKeywordAdmin(admin.ModelAdmin):
    list_display = ["keyword", "disease_name", "classification", "is_active"]
    list_filter = ["classification", "is_active"]
    search_fields = ["keyword", "conclusion_template", "disease_name"]
    ordering = ["keyword"]
