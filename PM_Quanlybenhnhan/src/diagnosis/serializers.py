"""Diagnosis app serializers."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from diagnosis.models import DiagnosisKeyword


@extend_schema_serializer(component_name="DiagnosisKeyword")
class DiagnosisKeywordSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiagnosisKeyword
        fields = [
            "id",
            "keyword",
            "disease_name",
            "conclusion_template",
            "classification",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ImportKeywordsUploadSerializer(serializers.Serializer):
    file = serializers.FileField(
        help_text="Benh-TuVan 001.xlsx file to import"
    )
    mode = serializers.ChoiceField(
        choices=[("append", "Append new records"), ("replace", "Replace all existing")],
        default="append",
        required=False,
    )
