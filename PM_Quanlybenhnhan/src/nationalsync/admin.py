"""National sync admin registration — Phase 8, Sprint 16."""

from __future__ import annotations

from django.contrib import admin
from django.http import HttpRequest

from nationalsync.models import (
    FacilitySignature,
    SyncConfig,
    SyncFieldMapping,
    SyncJob,
    SyncMappingVersion,
)


@admin.register(FacilitySignature)
class FacilitySignatureAdmin(admin.ModelAdmin):
    fields = ("signature_image", "signature_base64")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return not FacilitySignature.objects.exists()

    def has_delete_permission(self, request: HttpRequest, obj=None) -> bool:
        return False


@admin.register(SyncConfig)
class SyncConfigAdmin(admin.ModelAdmin):
    list_display = ("environment", "username", "sender_id", "is_active")
    fieldsets = (
        (
            "Kết nối",
            {
                "fields": (
                    "environment",
                    "api_base_url",
                    "username",
                    "password",
                    "facility_code",
                    "sender_id",
                    "receiver_id",
                    "version",
                    "is_active",
                )
            },
        ),
        (
            "Chữ ký số",
            {"fields": ("private_key", "public_key"), "classes": ("collapse",)},
        ),
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        # Two environments max — one config each.
        return SyncConfig.objects.count() < 2

    def has_delete_permission(self, request: HttpRequest, obj=None) -> bool:
        return False


@admin.register(SyncMappingVersion)
class SyncMappingVersionAdmin(admin.ModelAdmin):
    list_display = ("name", "is_default", "source_filename", "created_at")
    list_filter = ("is_default",)
    search_fields = ("name", "source_filename")
    readonly_fields = ("extracted_fields", "created_at", "updated_at")


@admin.register(SyncFieldMapping)
class SyncFieldMappingAdmin(admin.ModelAdmin):
    list_display = (
        "xml_tag",
        "block",
        "version",
        "department",
        "field_key",
        "ma_dich_vu",
        "ma_chi_so",
    )
    list_filter = ("version", "block", "department")
    search_fields = ("xml_tag", "field_key", "ma_chi_so", "department__name")
    autocomplete_fields = ("department",)


@admin.register(SyncJob)
class SyncJobAdmin(admin.ModelAdmin):
    list_display = (
        "status",
        "environment",
        "scope_type",
        "company",
        "patient",
        "examination",
        "examination_count",
        "created_by",
        "created_at",
    )
    list_filter = ("status", "scope_type", "environment")
    search_fields = ("company__name", "patient__full_name", "created_by__email")
    readonly_fields = (
        "status",
        "environment",
        "scope_type",
        "company",
        "patient",
        "examination",
        "examination_count",
        "response",
        "error_message",
        "created_by",
        "started_at",
        "completed_at",
        "created_at",
        "updated_at",
    )
    ordering = ("-created_at",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj=None) -> bool:
        return False
