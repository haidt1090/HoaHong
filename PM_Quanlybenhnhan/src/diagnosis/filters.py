"""Diagnosis app filters."""

from __future__ import annotations

import django_filters

from diagnosis.models import DiagnosisKeyword


class DiagnosisKeywordFilter(django_filters.FilterSet):
    classification = django_filters.NumberFilter()
    is_active = django_filters.BooleanFilter()
    disease_name = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = DiagnosisKeyword
        fields = ["classification", "is_active", "disease_name"]
