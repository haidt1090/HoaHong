"""Diagnosis models — Phase 3, Sprint 7-8."""

from __future__ import annotations

from django.db import models

from core.models import BaseModel


class DiagnosisKeyword(BaseModel):
    """A symptom/finding keyword mapped to a disease name for diagnosis.

    Each keyword maps to:
    - ``disease_name`` (tên bệnh — the "Bệnh mắc" text shown in reports)
    - ``conclusion_template`` (tư vấn)
    - ``classification`` (phân loại bệnh mắc → work fitness)

    There is no separate DiseaseCode entity — the diagnosis engine matches
    findings text against keywords and derives everything directly.
    """

    # Phân loại sức khỏe — Loại I → V (1 → 5)
    CLASSIFICATION_GOOD = 1    # Loại I — rất tốt (bình thường)
    CLASSIFICATION_MILD = 2    # Loại II — tốt (nhẹ)
    CLASSIFICATION_DISEASE = 3 # Loại III — trung bình (bệnh mắc)
    CLASSIFICATION_POOR = 4    # Loại IV — kém
    CLASSIFICATION_UNFIT = 5   # Loại V — rất kém (không đủ điều kiện lao động)

    CLASSIFICATION_CHOICES = [
        (CLASSIFICATION_GOOD, "1"),
        (CLASSIFICATION_MILD, "2"),
        (CLASSIFICATION_DISEASE, "3"),
        (CLASSIFICATION_POOR, "4"),
        (CLASSIFICATION_UNFIT, "5"),
    ]

    keyword = models.TextField(help_text="Symptom or finding pattern to match")
    disease_name = models.TextField(
        blank=True,
        help_text="Tên bệnh (Bệnh mắc) — shown in reports when this keyword matches",
    )
    conclusion_template = models.TextField(
        blank=True,
        help_text="Tư vấn — conclusion text to output when this keyword matches",
    )
    classification = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        choices=CLASSIFICATION_CHOICES,
        help_text="Phân loại sức khỏe 1-5 (Loại I→V)",
    )
    is_active = models.BooleanField(default=True)
    embedding = models.JSONField(
        null=True,
        blank=True,
        default=None,
        help_text="384d embedding vector — populated in Sprint 8 via Celery task",
    )

    class Meta:
        ordering = ["keyword"]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["classification"]),
        ]
        verbose_name = "Diagnosis Keyword"
        verbose_name_plural = "Diagnosis Keywords"

    def __str__(self) -> str:
        return f"{self.keyword[:80]} → {self.disease_name[:40]}"
