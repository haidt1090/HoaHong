from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from accounts.managers import UserManager
from accounts.storage import PrivateSignatureStorage
from core.models import BaseModel


def doctor_signature_upload_to(instance: models.Model, filename: str) -> str:
    """Stable PNG path so replacing a signature overwrites the same file."""
    del filename
    return f"{instance.pk}.png"


class Company(BaseModel):
    """A client company whose employees are examined at the clinic."""

    name = models.CharField(max_length=255)
    # `code` is the public company_code used in patient lookup and search.
    code = models.CharField(max_length=50, unique=True)
    address = models.TextField(blank=True)
    tax_code = models.CharField(max_length=20, blank=True)
    contact_person = models.CharField(max_length=255, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    contact_email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Company"
        verbose_name_plural = "Companies"

    def __str__(self) -> str:
        return self.name


class User(AbstractUser):
    """Custom user model with email as login identifier and role support."""

    ROLE_CHOICES = [
        ("admin", "Quản trị viên"),
        ("doctor", "Bác sĩ"),
        ("nurse", "Điều dưỡng"),
        ("labtech", "Kỹ thuật viên"),
        ("company_admin", "Quản trị công ty"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    full_name = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    must_change_password = models.BooleanField(default=False)
    signature_image = models.ImageField(
        upload_to=doctor_signature_upload_to,
        storage=PrivateSignatureStorage(),
        blank=True,
        null=True,
        help_text="Ảnh chữ ký PNG của bác sĩ. Khi đồng bộ CSDLKSK được chuyển thành base64.",
    )
    signature_base64 = models.TextField(
        blank=True,
        help_text="Chữ ký số dạng base64 khi không lưu file ảnh.",
    )
    company = models.ForeignKey(
        Company,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="users",
    )

    # Remove username field from AbstractUser
    username = None
    first_name = None
    last_name = None

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    objects = UserManager()

    class Meta:
        ordering = ["email"]

    def __str__(self) -> str:
        return self.email

    @property
    def display_name(self) -> str:
        return self.full_name or self.email


class StaffAssignment(models.Model):
    """
    Optional assignment of clinical staff (Nurse/LabTech) to specific companies.

    Used to filter which patients/examinations a staff member can access.
    Sprint 2a — supports the permission matrix's "view_assigned" and
    "assigned (lab/xray/ultrasound only)" rules.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="staff_assignments",
        limit_choices_to={"role__in": ["nurse", "labtech"]},
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="staff_assignments",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["user", "company"]
        ordering = ["-assigned_at"]

    def __str__(self) -> str:
        return f"{self.user.email} → {self.company.name}"


class CompanyExamPackage(BaseModel):
    """
    Links a company to an exam package with company-specific pricing.

    Sprint 3 stub — full pricing implementation in Sprint 6a. As of Sprint 4
    ``exam_package`` is a real ForeignKey to ``examinations.ExamPackage``.
    """

    PRICING_MODES = [
        ("per_field", "Theo từng chỉ số"),
        ("package_total", "Theo giá trọn gói"),
    ]

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="exam_packages"
    )
    exam_package = models.ForeignKey(
        "examinations.ExamPackage",
        on_delete=models.PROTECT,
        related_name="company_packages",
    )
    pricing_mode = models.CharField(max_length=20, choices=PRICING_MODES)
    total_employees = models.PositiveIntegerField(
        default=0, help_text="Số lượng nhân viên được khám theo gói này"
    )
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )

    class Meta:
        unique_together = ["company", "exam_package"]
        ordering = ["-assigned_at"]

    def __str__(self) -> str:
        return f"{self.company.name} — {self.pricing_mode}"

    @property
    def total_cost(self):
        if not self.total_employees or not self.exam_package_id:
            return 0
        emp = int(self.total_employees)
        if self.pricing_mode == "package_total":
            price = self.exam_package.default_package_price or 0
            return emp * int(price)
        if self.pricing_mode == "per_field":
            total = 0
            for epd in self.exam_package.package_departments.select_related(
                "template"
            ).all():
                for field in epd.template.fields_config:
                    total += field.get("default_price", 0) or 0
            return emp * total
        return 0
