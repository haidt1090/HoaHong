"""
Tests for findings aggregation edge cases (Sprint 7).

Covers:
  * "Khỏe mạnh" (healthy) is skipped as a finding
  * Generic keywords must not match field LABELS (only values)
"""

from __future__ import annotations

from django.test import TestCase

from diagnosis.models import DiagnosisKeyword
from diagnosis.services import match_diagnosis


class FindingsAggregationTests(TestCase):
    def test_khoe_manh_is_skipped(self):
        # Simulate findings with "Khỏe mạnh" values.
        from diagnosis.services import _NORMAL_VALUES

        self.assertIn("khỏe mạnh", _NORMAL_VALUES)
        self.assertIn("khoe manh", _NORMAL_VALUES)

    def test_keyword_does_not_match_field_label(self):
        """A generic keyword must match values, not the field label."""
        # Keyword "Tật" → "Tiền sử tật ngón V tay phải"
        DiagnosisKeyword.objects.create(
            keyword="Tật",
            disease_name="Tiền sử tật ngón V tay phải",
            classification=2,
            is_active=True,
        )

        # Finding "Tiền sử bệnh, tật: Khỏe mạnh" — the LABEL contains "tật",
        # but the VALUE "Khỏe mạnh" does not. It must NOT match.
        findings = "Tiền sử bệnh, tật: Khỏe mạnh"
        matches = match_diagnosis(findings)
        self.assertEqual(matches, [])

    def test_keyword_matches_value(self):
        """The same keyword matches when the VALUE contains it."""
        DiagnosisKeyword.objects.create(
            keyword="tật ngón V",
            disease_name="Tiền sử tật ngón V tay phải",
            classification=2,
            is_active=True,
        )
        findings = "Tiền sử bệnh, tật: tật ngón V tay phải"
        matches = match_diagnosis(findings)
        self.assertTrue(
            any(m["disease_name"] == "Tiền sử tật ngón V tay phải" for m in matches)
        )

    def test_abnormal_label_still_matches(self):
        """Abnormal labels (no colon) still match keywords directly."""
        DiagnosisKeyword.objects.create(
            keyword="nhịp tim chậm",
            disease_name="Nhịp tim chậm",
            classification=1,
            is_active=True,
        )
        matches = match_diagnosis("Nhịp tim chậm")
        self.assertTrue(any(m["disease_name"] == "Nhịp tim chậm" for m in matches))
