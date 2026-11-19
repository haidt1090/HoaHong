from __future__ import annotations

from django_filters import rest_framework as filters

from patients.models import Patient


class PatientFilter(filters.FilterSet):
    """Structured filters for the patient list endpoint."""

    company = filters.UUIDFilter(field_name="company_id")
    company_code = filters.CharFilter(field_name="company__code", lookup_expr="iexact")
    department = filters.CharFilter(field_name="department", lookup_expr="icontains")
    gender = filters.ChoiceFilter(choices=Patient.GENDER_CHOICES)
    is_active = filters.BooleanFilter(field_name="is_active")
    start_date_after = filters.DateFilter(field_name="start_date", lookup_expr="gte")
    start_date_before = filters.DateFilter(field_name="start_date", lookup_expr="lte")
    has_company = filters.BooleanFilter(method="filter_has_company")

    class Meta:
        model = Patient
        fields = [
            "company",
            "company_code",
            "department",
            "gender",
            "is_active",
            "has_company",
        ]

    def filter_has_company(self, queryset, name, value):
        if value is True:
            return queryset.filter(company_id__isnull=False)
        if value is False:
            return queryset.filter(company_id__isnull=True)
        return queryset
