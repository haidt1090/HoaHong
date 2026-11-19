from __future__ import annotations

from django.db import models
from simple_history.models import HistoricalRecords

from accounts.models import Company
from core.models import BaseModel


class Patient(BaseModel):
    """
    A person registered for health examinations, optionally under a company.

    - With company: ``company`` + ``employee_code`` required; identity via
      UniqueConstraint on (company, employee_code) when company IS NOT NULL.
    - Without company (cá nhân): ``company = NULL``; identified by ``cccd``
      or ``phone``; no employee_code enforced.

    Soft-deletion: ``is_active=False`` preserves historical examination data.
    """

    GENDER_CHOICES = [
        ("M", "Nam"),
        ("F", "Nữ"),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="patients",
    )
    employee_code = models.CharField(max_length=50, blank=True)
    full_name = models.CharField(max_length=255)
    dob = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=1, choices=GENDER_CHOICES, null=True, blank=True)

    # Vietnamese national ID (Căn cước công dân)
    cccd = models.CharField(max_length=20, blank=True)
    cccd_issued_date = models.DateField(null=True, blank=True)
    cccd_issued_place = models.CharField(max_length=255, blank=True)

    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    department = models.CharField(max_length=255, blank=True)
    start_date = models.DateField(null=True, blank=True, help_text="Ngày vào")

    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    # embedding VectorField added in Sprint 8

    history = HistoricalRecords()

    class Meta:
        ordering = ["full_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "employee_code"],
                condition=models.Q(company__isnull=False),
                name="unique_employee_per_company",
            )
        ]
        indexes = [
            models.Index(fields=["full_name"]),
            models.Index(fields=["employee_code"]),
            models.Index(fields=["cccd"]),
        ]

    def __str__(self) -> str:
        if self.employee_code:
            return f"{self.full_name} ({self.employee_code})"
        return self.full_name
