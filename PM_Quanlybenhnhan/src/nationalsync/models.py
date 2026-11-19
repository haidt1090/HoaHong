"""
National Health Portal (CSDLKSK) data sync models — Phase 8, Sprint 16.

``SyncConfig`` is a singleton holding the connection settings for the EMRHUB
Trục dữ liệu Bộ Y tế API. ``SyncJob`` tracks one asynchronous push of
examination data (KHAMSUCKHOE XML) to the national portal.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models, transaction

from accounts.storage import PrivateSignatureStorage
from core.models import BaseModel


def facility_signature_upload_to(instance: models.Model, filename: str) -> str:
    """One PNG for the whole facility."""
    del instance, filename
    return "facility.png"


class SyncConfig(BaseModel):
    """Per-environment connection configuration for the EMRHUB national sync API.

    One row per environment (``sandbox`` / ``production``) so the admin can
    configure both and switch between them at sync time. Secrets (``password``,
    ``private_key``) are stored here but must never be logged or serialized
    back to the client.
    """

    ENV_SANDBOX = "sandbox"
    ENV_PRODUCTION = "production"

    ENVIRONMENT_CHOICES = [
        (ENV_SANDBOX, "Sandbox"),
        (ENV_PRODUCTION, "Production"),
    ]

    ENV_API_BASE_URLS = {
        ENV_SANDBOX: "https://api-sandbox.emrhub.vn",
        ENV_PRODUCTION: "https://api.emrhub.vn",
    }

    environment = models.CharField(
        max_length=20,
        choices=ENVIRONMENT_CHOICES,
        unique=True,
        help_text="Môi trường liên thông (mỗi môi trường 1 bản cấu hình riêng).",
    )
    # Blank means "derive from environment"; set it to override manually.
    api_base_url = models.CharField(
        max_length=255,
        blank=True,
        help_text="Bỏ trống để tự suy từ môi trường.",
    )
    username = models.CharField(
        max_length=255, blank=True, help_text="Tài khoản liên thông"
    )
    password = models.CharField(
        max_length=255, blank=True, help_text="Mật khẩu (lưu bí mật)"
    )
    facility_code = models.CharField(
        max_length=20,
        blank=True,
        help_text="MA_CSKCB (mã cơ sở khám chữa bệnh, 5 số) dùng trong XML2.",
    )
    sender_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Mã định danh CSKCB (GTIN), ví dụ 8934285091236",
    )
    receiver_id = models.CharField(max_length=50, default="TTYQG")
    version = models.CharField(
        max_length=20, default="1.0.6", help_text="Phiên bản Trục"
    )
    private_key = models.TextField(blank=True, help_text="RSA private key (PEM)")
    public_key = models.TextField(blank=True, help_text="RSA public key (PEM)")
    is_active = models.BooleanField(default=False, help_text="Bật/tắt đồng bộ")

    class Meta:
        verbose_name = "Sync config"
        verbose_name_plural = "Sync config"

    def __str__(self) -> str:
        return f"National sync ({self.get_environment_display()})"

    @classmethod
    def load(cls, environment: str | None = None) -> SyncConfig:
        """Return the config for ``environment`` (or a fresh unsaved default).

        When ``environment`` is omitted, returns the first stored config (for
        backward compatibility); callers should prefer passing an explicit
        environment.
        """
        if environment:
            return cls.objects.filter(environment=environment).first() or cls(
                environment=environment
            )
        return cls.objects.first() or cls(environment=cls.ENV_SANDBOX)

    @property
    def effective_api_base_url(self) -> str:
        base = self.api_base_url.strip() or self.ENV_API_BASE_URLS.get(
            self.environment, self.ENV_API_BASE_URLS[self.ENV_SANDBOX]
        )
        if not base.startswith(("http://", "https://")):
            base = f"https://{base}"
        return base.rstrip("/")

    @property
    def is_configured(self) -> bool:
        return bool(
            self.username.strip()
            and self.password.strip()
            and self.sender_id.strip()
            and self.private_key.strip()
        )


class FacilitySignature(models.Model):
    """Singleton chữ ký cơ sở khám, ghi vào ``CKS_BENH_VIEN`` khi đồng bộ.

    Empty image and empty base64 mean the tag stays blank.
    """

    signature_image = models.ImageField(
        upload_to=facility_signature_upload_to,
        storage=PrivateSignatureStorage(),
        blank=True,
        null=True,
        help_text="Ảnh chữ ký PNG của bệnh viện. Khi đồng bộ được chuyển thành base64.",
    )
    signature_base64 = models.TextField(
        blank=True,
        help_text="Chữ ký bệnh viện dạng base64 khi không lưu file ảnh.",
    )

    class Meta:
        verbose_name = "Chữ ký bệnh viện"
        verbose_name_plural = "Chữ ký bệnh viện"

    def save(self, *args: object, **kwargs: object) -> None:
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> FacilitySignature:
        """Return the singleton row, creating it when an admin first saves."""
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj


class SyncMappingVersion(BaseModel):
    """One uploaded XML schema and the mappings configured against it.

    Sync uses the single row with ``is_default``. Uploading a file stores
    the extracted tags, not the original XML (signature images make those
    files very large).
    """

    name = models.CharField(max_length=120)
    is_default = models.BooleanField(default=False)
    source_filename = models.CharField(max_length=255, blank=True)
    extracted_fields = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Version mapping XML"
        verbose_name_plural = "Version mapping XML"
        constraints = [
            models.UniqueConstraint(
                fields=["is_default"],
                condition=models.Q(is_default=True),
                name="unique_default_sync_mapping_version",
            ),
        ]

    def __str__(self) -> str:
        mark = " (mặc định)" if self.is_default else ""
        return f"{self.name}{mark}"

    def activate(self) -> None:
        """Make this the only version used when building sync XML."""
        with transaction.atomic():
            type(self).objects.filter(is_default=True).exclude(pk=self.pk).update(
                is_default=False
            )
            self.is_default = True
            self.save(update_fields=["is_default", "updated_at"])


class SyncFieldMapping(BaseModel):
    """Admin map from a department column key to one national XML target.

    The link is the column ``key`` string, not a ``DepartmentField`` row.
    Replacing a department template keeps the mapping as long as the key
    stays. ``alias_keys`` covers a previous key still stored on old exams.
    """

    BLOCK_XML7 = "xml7"
    BLOCK_XML9 = "xml9"
    BLOCK_XML10 = "xml10"
    BLOCK_XML11 = "xml11"

    BLOCK_CHOICES = [
        (BLOCK_XML7, "XML7 — Khám lâm sàng"),
        (BLOCK_XML9, "XML9 — Tiền sử"),
        (BLOCK_XML10, "XML10 — Thể lực"),
        (BLOCK_XML11, "XML11 — Cận lâm sàng"),
    ]

    version = models.ForeignKey(
        SyncMappingVersion,
        on_delete=models.CASCADE,
        related_name="mappings",
    )
    block = models.CharField(max_length=8, choices=BLOCK_CHOICES)
    xml_tag = models.CharField(
        max_length=64,
        blank=True,
        help_text="Thẻ XML7/XML9/XML10, ví dụ CHIEU_CAO. Để trống với cận lâm sàng.",
    )
    department = models.ForeignKey(
        "examinations.Department",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sync_field_mappings",
    )
    field_key = models.CharField(
        max_length=100,
        help_text="Khóa cột trên mẫu khoa (DepartmentField.key).",
    )
    alias_keys = models.JSONField(
        default=list,
        blank=True,
        help_text="Khóa cũ vẫn còn trong lượt khám đã lưu.",
    )
    ma_dich_vu = models.CharField(
        max_length=32,
        blank=True,
        help_text="XML11 MA_DICH_VU.",
    )
    ma_chi_so = models.CharField(
        max_length=32,
        blank=True,
        help_text="XML11 MA_CHI_SO.",
    )

    class Meta:
        ordering = ["block", "xml_tag", "field_key"]
        verbose_name = "Mapping trường XML"
        verbose_name_plural = "Mapping trường XML"
        constraints = [
            models.UniqueConstraint(
                fields=["version", "xml_tag"],
                condition=~models.Q(xml_tag=""),
                name="unique_sync_xml_tag",
            ),
            models.UniqueConstraint(
                fields=["version", "department", "field_key"],
                name="unique_sync_department_field_key",
            ),
        ]

    def __str__(self) -> str:
        target = self.xml_tag or self.ma_chi_so or self.block
        return f"{target} ← {self.field_key}"

    def clean(self) -> None:
        from django.core.exceptions import ValidationError

        self.field_key = (self.field_key or "").strip()
        self.xml_tag = (self.xml_tag or "").strip()
        self.ma_dich_vu = (self.ma_dich_vu or "").strip()
        self.ma_chi_so = (self.ma_chi_so or "").strip()
        aliases: list[str] = []
        for item in self.alias_keys or []:
            text = str(item).strip()
            if text and text != self.field_key and text not in aliases:
                aliases.append(text)
        self.alias_keys = aliases

        errors: dict[str, str] = {}
        if self.version_id is None:
            errors["version"] = "Chọn version mapping."
        if not self.field_key:
            errors["field_key"] = "Nhập khóa cột."
        if self.department_id is None:
            errors["department"] = "Chọn khoa."
        catalog = self.version.extracted_fields if self.version_id else []
        if self.block == self.BLOCK_XML11:
            self.xml_tag = ""
            if not self.ma_chi_so:
                errors["ma_chi_so"] = "Nhập MA_CHI_SO."
            allowed = {
                (item.get("ma_dich_vu", ""), item.get("ma_chi_so", ""))
                for item in catalog
                if item.get("block") == self.BLOCK_XML11
            }
            pair = (self.ma_dich_vu, self.ma_chi_so)
            if self.ma_chi_so and pair not in allowed:
                errors["ma_chi_so"] = "Chỉ số không có trong version XML này."
        else:
            allowed_tags = {
                item.get("tag")
                for item in catalog
                if item.get("block") == self.block and item.get("tag")
            }
            if self.xml_tag not in allowed_tags:
                errors["xml_tag"] = "Thẻ XML không có trong version này."
            self.ma_dich_vu = ""
            self.ma_chi_so = ""
        if errors:
            raise ValidationError(errors)

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class SyncJob(BaseModel):
    """One push job of examination data to the national portal."""

    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Chờ xử lý"),
        (STATUS_PROCESSING, "Đang xử lý"),
        (STATUS_DONE, "Hoàn thành"),
        (STATUS_FAILED, "Thất bại"),
    ]

    SCOPE_COMPANY = "company"
    SCOPE_PATIENT = "patient"

    SCOPE_CHOICES = [
        (SCOPE_COMPANY, "Công ty"),
        (SCOPE_PATIENT, "Bệnh nhân lẻ"),
    ]

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    environment = models.CharField(
        max_length=20,
        choices=SyncConfig.ENVIRONMENT_CHOICES,
        blank=True,
        help_text="Môi trường dùng cho lần đồng bộ này.",
    )
    scope_type = models.CharField(max_length=20, choices=SCOPE_CHOICES)
    company = models.ForeignKey(
        "accounts.Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="national_sync_jobs",
    )
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="national_sync_jobs",
    )
    examination = models.ForeignKey(
        "examinations.Examination",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="national_sync_jobs",
        help_text="Khi set: chỉ đồng bộ một lượt khám (không phải cả phạm vi).",
    )
    examination_count = models.PositiveIntegerField(default=0)
    success_count = models.PositiveIntegerField(
        default=0, help_text="Số lượt khám đẩy thành công trong job này."
    )
    failed_count = models.PositiveIntegerField(
        default=0, help_text="Số lượt khám đẩy thất bại trong job này."
    )
    skipped_count = models.PositiveIntegerField(
        default=0,
        help_text="Số lượt đã đồng bộ thành công trước đó (bỏ qua khi sync tất cả).",
    )
    synced_examination_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="UUID các lượt khám đẩy thành công (để bỏ qua lần sau).",
    )
    response = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    cks_nguoi_ket_luan = models.TextField(
        blank=True,
        help_text="JSON map of exam id to Base64(XML Signature) for CKS_BENH_VIEN. CKS_NGUOI_KET_LUAN stays empty.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="national_sync_jobs",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["scope_type"]),
        ]

    def __str__(self) -> str:
        scope = (
            self.company.name
            if self.company
            else (self.patient.full_name if self.patient else "-")
        )
        return f"{scope} ({self.status})"
