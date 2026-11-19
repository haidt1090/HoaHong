"""
Tests for Phase 2 — Sprint 4: Department & Template Engine (v3 — DepartmentField).

Covers:
- Department, DepartmentTemplate, DepartmentField, ExamPackage models + seed data
- DepartmentField as table rows (indexed, searchable)
- Department / Template / Package CRUD APIs + role gating
- Template versioning
- Template render endpoint (serialized fields_config shape unchanged)
- Nested package department binding + template/department mismatch guard
"""

from __future__ import annotations

from datetime import date

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError as DjangoValidationError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from examinations.models import (
    Department,
    DepartmentField,
    DepartmentResult,
    DepartmentTemplate,
    Examination,
    ExamPackage,
    ExamPackageDepartment,
)

User = get_user_model()


def _make_user(role: str, **kwargs) -> User:
    email = kwargs.pop("email", f"{role}@exam.test")
    return User.objects.create_user(
        email=email,
        password="TestPass123!",
        full_name=f"Test {role.title()}",
        role=role,
        **kwargs,
    )


def _field_entries() -> list[dict]:
    """Sample DepartmentField payloads (matching the serializer)."""
    return [
        {
            "key": "hemoglobin",
            "label": "Huyết sắc tố",
            "field_type": "number",
            "unit": "g/dL",
            "required": True,
            "order": 1,
            "normal_range_min": 12,
            "normal_range_max": 16,
            "default_price": 50000,
            "test_category": "blood",
        },
        {
            "key": "note",
            "label": "Ghi chú",
            "field_type": "textarea",
            "order": 2,
        },
    ]


def _resolve_nr(entry, key):
    """Resolve normal_range min/max from legacy dict or direct keys."""
    nr = entry.get("normal_range")
    if isinstance(nr, dict):
        return nr.get(key)
    return entry.get(f"normal_range_{key}")


def _create_template(dept, name, entries=None, **kwargs):
    """Create a DepartmentTemplate and its DepartmentField rows."""
    entries = entries or _field_entries()
    template = DepartmentTemplate.objects.create(department=dept, name=name, **kwargs)
    DepartmentField.objects.bulk_create(
        [
            DepartmentField(
                template=template,
                key=e["key"],
                label=e["label"],
                field_type=e["field_type"],
                unit=e.get("unit", ""),
                required=e.get("required", False),
                order=e.get("order", 0),
                normal_range_min=_resolve_nr(e, "min"),
                normal_range_max=_resolve_nr(e, "max"),
                default_value=e.get("default_value", ""),
                default_price=e.get("default_price", 0),
                test_category=e.get("test_category", ""),
                options=e.get("options", []),
            )
            for e in entries
        ]
    )
    return template


# ---------------------------------------------------------------------------
# Model + seed tests
# ---------------------------------------------------------------------------


class DepartmentSeedTests(APITestCase):
    def test_default_departments_seeded(self) -> None:
        codes = set(Department.objects.values_list("code", flat=True))
        for code in ("kham_lam_sang", "xet_nghiem", "x_quang", "sieu_am"):
            self.assertIn(code, codes)

    def test_clinical_vs_paraclinical_categories(self) -> None:
        clinical = Department.objects.get(code="kham_lam_sang")
        lab = Department.objects.get(code="xet_nghiem")
        self.assertEqual(clinical.category, "clinical")
        self.assertEqual(lab.category, "para_clinical")


class DepartmentFieldModelTests(APITestCase):
    def setUp(self) -> None:
        self.dept = Department.objects.get(code="xet_nghiem")

    def test_fields_stored_as_rows(self) -> None:
        tpl = _create_template(self.dept, "Mẫu", _field_entries())
        self.assertEqual(tpl.fields.count(), 2)
        self.assertEqual(tpl.fields_config[0]["key"], "hemoglobin")

    def test_unique_key_per_template_constraint(self) -> None:
        from django.db import IntegrityError

        tpl = _create_template(self.dept, "Mẫu")
        DepartmentField.objects.create(
            template=tpl, key="dup", label="D", field_type="text"
        )
        with self.assertRaises(IntegrityError):
            DepartmentField.objects.create(
                template=tpl, key="dup", label="E", field_type="text"
            )

    def test_indexes_present(self) -> None:
        _create_template(self.dept, "Mẫu")
        # key index allows efficient lookup
        qs = DepartmentField.objects.filter(key="hemoglobin")
        self.assertEqual(qs.count(), 1)

    def test_as_config_output_matches_legacy_shape(self) -> None:
        tpl = _create_template(self.dept, "Mẫu", _field_entries())
        config = tpl.fields_config
        self.assertEqual(config[0]["key"], "hemoglobin")
        self.assertEqual(config[0]["type"], "number")  # field_type → type
        self.assertNotIn("field_type", config[0])  # not exposed


class DepartmentFieldGenderOverrideTests(APITestCase):
    """Gender-specific normal range + step-based random seeding."""

    def setUp(self) -> None:
        self.dept = Department.objects.get(code="xet_nghiem")
        self.tpl = DepartmentTemplate.objects.create(
            department=self.dept, name="Mẫu"
        )
        self.field = DepartmentField.objects.create(
            template=self.tpl,
            key="hr",
            label="Nhịp tim",
            field_type="number",
            normal_range_min=60,
            normal_range_max=100,
            default_value="80",
            gender_overrides={
                "M": {"min": 130, "max": 160, "step": 5},
                "F": {"min": 120, "max": 135, "step": 5},
            },
        )

    def test_resolve_normal_range_gender_specific(self) -> None:
        self.assertEqual(self.field.resolve_normal_range("M"), (130.0, 160.0))
        self.assertEqual(self.field.resolve_normal_range("F"), (120.0, 135.0))

    def test_resolve_normal_range_fallback(self) -> None:
        self.assertEqual(self.field.resolve_normal_range(None), (60.0, 100.0))

    def test_resolve_default_value_is_field_level_only(self) -> None:
        self.assertEqual(self.field.resolve_default_value("M"), "80")
        self.assertEqual(self.field.resolve_default_value("F"), "80")
        self.assertEqual(self.field.resolve_default_value(None), "80")

    def test_as_config_includes_gender_overrides(self) -> None:
        config = self.tpl.fields_config[0]
        self.assertIn("gender_overrides", config)
        self.assertEqual(config["gender_overrides"]["M"]["min"], 130)
        self.assertEqual(config["gender_overrides"]["M"]["step"], 5)


class GenderOverrideNormalizationTests(APITestCase):
    """Bounds typed as text in the admin must be stored as numbers."""

    def setUp(self) -> None:
        self.dept = Department.objects.get(code="xet_nghiem")
        self.tpl = DepartmentTemplate.objects.create(
            department=self.dept, name="Mẫu chuẩn hoá"
        )

    def _field(self, overrides) -> DepartmentField:
        return DepartmentField.objects.create(
            template=self.tpl,
            key="glu",
            label="Glucose",
            field_type="number",
            gender_overrides=overrides,
        )

    def test_string_bounds_are_stored_as_floats(self) -> None:
        field = self._field({"M": {"min": "4.5", "max": "6.3"}})
        field.refresh_from_db()
        self.assertEqual(field.gender_overrides["M"], {"min": 4.5, "max": 6.3})
        for bound in ("min", "max"):
            self.assertIsInstance(field.gender_overrides["M"][bound], float)

    def test_comma_alone_is_read_as_decimal_separator(self) -> None:
        field = self._field({"F": {"min": "1,5", "max": "2"}})
        self.assertEqual(field.gender_overrides["F"], {"min": 1.5, "max": 2.0})

    def test_comma_with_dot_is_a_thousands_separator(self) -> None:
        field = self._field({"M": {"min": "1,500.5", "max": "2000"}})
        self.assertEqual(field.gender_overrides["M"]["min"], 1500.5)
        self.assertEqual(field.gender_overrides["M"]["max"], 2000.0)

    def test_ambiguous_thousands_group_is_rejected_not_guessed(self) -> None:
        """"2,000" could be 2 or 2000 — guessing would store a wrong range."""
        with self.assertRaises(DjangoValidationError):
            self._field({"M": {"min": "2,000"}})

    def test_blank_bounds_are_dropped_and_legacy_default_stripped(self) -> None:
        field = self._field({"M": {"min": "", "max": "6.3", "default": " 5,5 "}})
        self.assertEqual(field.gender_overrides["M"], {"max": 6.3})

    def test_step_is_stored_as_float(self) -> None:
        field = self._field({"M": {"min": "3.5", "max": "7.5", "step": "0.2"}})
        self.assertEqual(
            field.gender_overrides["M"], {"min": 3.5, "max": 7.5, "step": 0.2}
        )

    def test_non_positive_step_is_rejected(self) -> None:
        with self.assertRaises(DjangoValidationError):
            self._field({"M": {"min": "1", "max": "2", "step": "0"}})

    def test_build_step_grid_example_range(self) -> None:
        from examinations.models import build_step_grid

        grid = build_step_grid(3.5, 7.5, 0.2)
        self.assertEqual(grid[0], 3.5)
        self.assertEqual(grid[-1], 7.5)
        self.assertEqual(len(grid), 21)
        self.assertEqual(grid[1], 3.7)

    def test_non_numeric_bound_is_rejected(self) -> None:
        with self.assertRaises(DjangoValidationError):
            self._field({"M": {"min": "abc"}})

    def test_min_greater_than_max_is_rejected(self) -> None:
        with self.assertRaises(DjangoValidationError):
            self._field({"M": {"min": "9", "max": "1"}})

    def test_unknown_gender_key_is_rejected(self) -> None:
        with self.assertRaises(DjangoValidationError):
            self._field({"X": {"min": "1"}})

    def test_resolve_normal_range_returns_floats_after_string_input(self) -> None:
        field = self._field({"M": {"min": "4.5", "max": "6.3"}})
        self.assertEqual(field.resolve_normal_range("M"), (4.5, 6.3))

    def test_api_rejects_non_numeric_bound(self) -> None:
        admin = _make_user("admin", email="govadmin@exam.test")
        self.client.force_authenticate(admin)
        resp = self.client.post(
            reverse("examinations:template-list"),
            {
                "department": str(self.dept.id),
                "name": "Qua API",
                "fields": [
                    {
                        "key": "glu",
                        "label": "Glucose",
                        "field_type": "number",
                        "gender_overrides": {"M": {"min": "abc"}},
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class SyncValuesDefaultSeedTests(APITestCase):
    """``_sync_values`` seeding of empty fields from template defaults."""

    def setUp(self) -> None:
        from accounts.models import Company
        from patients.models import Patient

        self.dept = Department.objects.get(code="xet_nghiem")
        self.tpl = DepartmentTemplate.objects.create(
            department=self.dept, name="Mẫu seed"
        )
        DepartmentField.objects.create(
            template=self.tpl,
            key="hr",
            label="Nhịp tim",
            field_type="number",
            normal_range_min=60,
            normal_range_max=100,
            default_value="80",
            gender_overrides={"F": {"min": 120, "max": 135, "step": 5}},
        )
        self.company = Company.objects.create(name="Cty", code="CTY_SEED")
        self.package = ExamPackage.objects.create(name="Gói", exam_type="periodic")
        ExamPackageDepartment.objects.create(
            exam_package=self.package,
            department=self.dept,
            template=self.tpl,
            order=1,
        )

        def _patient(code: str, gender: str | None) -> Patient:
            return Patient.objects.create(
                company=self.company,
                employee_code=code,
                full_name=f"NV {code}",
                dob=date.today(),
                gender=gender,
            )

        self.patient_no_gender = _patient("E00", None)
        self.patient_female = _patient("E02", "F")

    def _result_for(self, patient) -> DepartmentResult:
        exam = Examination.objects.create(
            patient=patient,
            exam_package=self.package,
            exam_type="periodic",
            exam_date=date.today(),
        )
        return DepartmentResult.objects.create(
            examination=exam,
            department=self.dept,
            template=self.tpl,
            template_snapshot=self.tpl.fields_config,
        )

    def test_empty_field_falls_back_to_base_default_value(self) -> None:
        """Regression: the snapshot stores the base default under
        ``default_value``; missing it used to seed a random in-range number."""
        result = self._result_for(self.patient_no_gender)
        result._sync_values({})
        self.assertEqual(result.data["hr"], 80.0)

    def test_gender_override_without_field_default_uses_step_grid(self) -> None:
        """Empty field + gender range + step → discrete random on the grid."""
        from examinations.models import build_step_grid

        field = self.tpl.fields.get(key="hr")
        field.default_value = ""
        field.save(update_fields=["default_value"])
        result = self._result_for(self.patient_female)
        # Refresh snapshot without default_value
        result.template_snapshot = self.tpl.fields_config
        result.save(update_fields=["template_snapshot"])

        grid = build_step_grid(120.0, 135.0, 5.0)
        for _ in range(20):
            result._sync_values({})
            self.assertIn(result.data["hr"], grid)

    def test_omitted_step_defaults_to_tenth(self) -> None:
        from examinations.models import DEFAULT_GENDER_OVERRIDE_STEP, build_step_grid

        field = self.tpl.fields.get(key="hr")
        field.default_value = ""
        field.gender_overrides = {"F": {"min": 120, "max": 121}}
        field.save(update_fields=["default_value", "gender_overrides"])
        result = self._result_for(self.patient_female)
        result.template_snapshot = self.tpl.fields_config
        result.save(update_fields=["template_snapshot"])

        grid = build_step_grid(120.0, 121.0, DEFAULT_GENDER_OVERRIDE_STEP)
        for _ in range(20):
            result._sync_values({})
            self.assertIn(result.data["hr"], grid)

    def test_supplied_value_is_not_overwritten_by_default(self) -> None:
        result = self._result_for(self.patient_no_gender)
        result._sync_values({"hr": 72})
        self.assertEqual(result.data["hr"], 72.0)

    def test_null_string_is_randomized_like_empty(self) -> None:
        field = self.tpl.fields.get(key="hr")
        field.default_value = ""
        field.save(update_fields=["default_value"])
        result = self._result_for(self.patient_no_gender)
        result.template_snapshot = self.tpl.fields_config
        result.save(update_fields=["template_snapshot"])
        result._sync_values({"hr": "null"}, randomize=True)
        val = result.data["hr"]
        self.assertGreaterEqual(float(val), 60.0)
        self.assertLessEqual(float(val), 100.0)

    def test_zero_is_kept_when_randomizing(self) -> None:
        result = self._result_for(self.patient_no_gender)
        result._sync_values({"hr": 0}, randomize=True)
        self.assertEqual(result.data["hr"], 0.0)


class TemplateVersioningModelTests(APITestCase):
    def setUp(self) -> None:
        self.dept = Department.objects.get(code="xet_nghiem")

    def test_version_starts_at_one(self) -> None:
        template = _create_template(self.dept, "Mẫu XN")
        self.assertEqual(template.version, 1)


# ---------------------------------------------------------------------------
# Template API validation tests (payload uses ``fields`` key)
# ---------------------------------------------------------------------------


class FieldsConfigValidationTests(APITestCase):
    def setUp(self) -> None:
        self.admin = _make_user("admin")
        self.dept = Department.objects.get(code="xet_nghiem")
        self.client.force_authenticate(self.admin)
        self.url = reverse("examinations:template-list")

    def _payload(self, fields_data):
        return {"department": str(self.dept.id), "name": "Mẫu", "fields": fields_data}

    def test_valid_config_accepted(self) -> None:
        response = self.client.post(
            self.url, self._payload(_field_entries()), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_missing_required_key_rejected(self) -> None:
        response = self.client.post(
            self.url,
            self._payload([{"label": "X", "field_type": "number"}]),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_type_rejected(self) -> None:
        response = self.client.post(
            self.url,
            self._payload([{"key": "x", "label": "X", "field_type": "rocket"}]),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_key_rejected(self) -> None:
        fields = [
            {"key": "x", "label": "A", "field_type": "number"},
            {"key": "x", "label": "B", "field_type": "text"},
        ]
        response = self.client.post(self.url, self._payload(fields), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_select_without_options_rejected(self) -> None:
        fields = [{"key": "x", "label": "A", "field_type": "select"}]
        response = self.client.post(self.url, self._payload(fields), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_list_config_rejected(self) -> None:
        response = self.client.post(
            self.url,
            {"department": str(self.dept.id), "name": "Mẫu", "fields": {"key": "x"}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Department CRUD + role gating
# ---------------------------------------------------------------------------


class DepartmentApiTests(APITestCase):
    def setUp(self) -> None:
        self.admin = _make_user("admin")
        self.doctor = _make_user("doctor")
        self.nurse = _make_user("nurse")
        self.url = reverse("examinations:department-list")

    def test_admin_can_create_department(self) -> None:
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            self.url,
            {"name": "Da liễu", "code": "da_lieu", "category": "clinical"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_doctor_cannot_create_department(self) -> None:
        self.client.force_authenticate(self.doctor)
        response = self.client.post(
            self.url,
            {"name": "Da liễu", "code": "da_lieu", "category": "clinical"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_nurse_can_read_departments(self) -> None:
        self.client.force_authenticate(self.nurse)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_soft_delete_deactivates(self) -> None:
        self.client.force_authenticate(self.admin)
        dept = Department.objects.get(code="sieu_am")
        response = self.client.delete(
            reverse("examinations:department-detail", args=[dept.id])
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        dept.refresh_from_db()
        self.assertFalse(dept.is_active)


# ---------------------------------------------------------------------------
# Template CRUD + versioning + render
# ---------------------------------------------------------------------------


class TemplateApiTests(APITestCase):
    def setUp(self) -> None:
        self.admin = _make_user("admin")
        self.doctor = _make_user("doctor")
        self.labtech = _make_user("labtech")
        self.dept = Department.objects.get(code="xet_nghiem")
        self.url = reverse("examinations:template-list")

    def _create_template(self) -> DepartmentTemplate:
        return _create_template(self.dept, "Mẫu XN")

    def test_created_by_set_from_request(self) -> None:
        self.client.force_authenticate(self.doctor)
        response = self.client.post(
            self.url,
            {
                "department": str(self.dept.id),
                "name": "Mẫu",
                "fields": _field_entries(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        template = DepartmentTemplate.objects.get(id=response.data["id"])
        self.assertEqual(template.created_by, self.doctor)

    def test_labtech_cannot_create_template(self) -> None:
        self.client.force_authenticate(self.labtech)
        response = self.client.post(
            self.url,
            {
                "department": str(self.dept.id),
                "name": "Mẫu",
                "fields": _field_entries(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_increments_version(self) -> None:
        template = self._create_template()
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            reverse("examinations:template-detail", args=[template.id]),
            {"name": "Mẫu v2"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        template.refresh_from_db()
        self.assertEqual(template.version, 2)

    def test_render_endpoint_returns_fields_config(self) -> None:
        template = self._create_template()
        self.client.force_authenticate(self.labtech)
        response = self.client.get(
            reverse("examinations:template-render", args=[template.id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["fields_config"]), 2)
        self.assertEqual(response.data["version"], 1)

    def test_patch_fields_replaces_all(self) -> None:
        template = self._create_template()
        self.client.force_authenticate(self.admin)
        new_fields = [
            {"key": "only", "label": "Only", "field_type": "text", "order": 1}
        ]
        response = self.client.patch(
            reverse("examinations:template-detail", args=[template.id]),
            {"fields": new_fields},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        template.refresh_from_db()
        self.assertEqual(template.fields.count(), 1)
        self.assertEqual(template.fields.first().key, "only")


# ---------------------------------------------------------------------------
# ExamPackage nested departments
# ---------------------------------------------------------------------------


class ExamPackageApiTests(APITestCase):
    def setUp(self) -> None:
        self.admin = _make_user("admin")
        self.clinical = Department.objects.get(code="kham_lam_sang")
        self.lab = Department.objects.get(code="xet_nghiem")
        self.clinical_tpl = _create_template(self.clinical, "LS")
        self.lab_tpl = _create_template(self.lab, "XN")
        self.url = reverse("examinations:package-list")
        self.client.force_authenticate(self.admin)

    def _payload(self, **overrides) -> dict:
        payload = {
            "name": "Gói định kỳ 2026",
            "exam_type": "periodic",
            "package_departments": [
                {
                    "department": str(self.clinical.id),
                    "template": str(self.clinical_tpl.id),
                    "order": 1,
                },
                {
                    "department": str(self.lab.id),
                    "template": str(self.lab_tpl.id),
                    "order": 2,
                },
            ],
        }
        payload.update(overrides)
        return payload

    def test_create_package_with_departments(self) -> None:
        response = self.client.post(self.url, self._payload(), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        package = ExamPackage.objects.get(id=response.data["id"])
        self.assertEqual(package.package_departments.count(), 2)

    def test_template_department_mismatch_rejected(self) -> None:
        payload = self._payload(
            package_departments=[
                {
                    "department": str(self.clinical.id),
                    "template": str(self.lab_tpl.id),
                    "order": 1,
                }
            ]
        )
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_department_same_template_rejected(self) -> None:
        payload = self._payload(
            package_departments=[
                {
                    "department": str(self.clinical.id),
                    "template": str(self.clinical_tpl.id),
                    "order": 1,
                },
                {
                    "department": str(self.clinical.id),
                    "template": str(self.clinical_tpl.id),
                    "order": 2,
                },
            ]
        )
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_replaces_departments(self) -> None:
        create = self.client.post(self.url, self._payload(), format="json")
        package_id = create.data["id"]
        response = self.client.patch(
            reverse("examinations:package-detail", args=[package_id]),
            {
                "package_departments": [
                    {
                        "department": str(self.lab.id),
                        "template": str(self.lab_tpl.id),
                        "order": 1,
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        package = ExamPackage.objects.get(id=package_id)
        self.assertEqual(package.package_departments.count(), 1)
        self.assertEqual(package.package_departments.first().department_id, self.lab.id)

    def test_package_keeps_old_template_version_after_template_update(self) -> None:
        create = self.client.post(self.url, self._payload(), format="json")
        package_id = create.data["id"]
        bound = ExamPackageDepartment.objects.filter(
            exam_package_id=package_id, department=self.clinical
        ).first()
        self.assertIsNotNone(bound)
        self.assertEqual(bound.template.version, 1)

        self.client.patch(
            reverse("examinations:template-detail", args=[self.clinical_tpl.id]),
            {"name": "LS v2"},
            format="json",
        )
        self.clinical_tpl.refresh_from_db()
        self.assertEqual(self.clinical_tpl.version, 2)

        bound.refresh_from_db()
        self.assertEqual(bound.template_id, self.clinical_tpl.id)


# ---------------------------------------------------------------------------
# Group permission seeding for examinations models
# ---------------------------------------------------------------------------


class ExaminationsGroupPermissionsTests(APITestCase):
    def test_admin_group_has_department_crud(self) -> None:
        group = Group.objects.get(name="admin")
        perms = set(group.permissions.values_list("codename", flat=True))
        for action in ("add", "change", "delete", "view"):
            self.assertIn(f"{action}_department", perms)

    def test_doctor_group_has_view_exampackage(self) -> None:
        group = Group.objects.get(name="doctor")
        perms = set(group.permissions.values_list("codename", flat=True))
        self.assertIn("view_exampackage", perms)
        self.assertNotIn("add_exampackage", perms)


# ---------------------------------------------------------------------------
# Admin created_by handling
# ---------------------------------------------------------------------------


class DepartmentTemplateAdminCreatedByTests(APITestCase):
    def setUp(self) -> None:
        from django.contrib.admin.sites import AdminSite
        from examinations.admin import DepartmentTemplateAdmin

        self.admin_instance = DepartmentTemplateAdmin(DepartmentTemplate, AdminSite())
        self.dept = Department.objects.get(code="xet_nghiem")
        self.admin_user = _make_user("admin", email="creator@exam.test")
        self.other = _make_user("doctor", email="other@exam.test")

    def _request(self, user):
        from unittest.mock import MagicMock

        request = MagicMock()
        request.user = user
        return request

    def test_created_by_is_readonly(self) -> None:
        self.assertIn("created_by", self.admin_instance.readonly_fields)

    def test_created_by_set_on_create(self) -> None:
        template = DepartmentTemplate(department=self.dept, name="Mẫu")
        self.admin_instance.save_model(
            self._request(self.admin_user), template, form=None, change=False
        )
        template.refresh_from_db()
        self.assertEqual(template.created_by, self.admin_user)

    def test_created_by_preserved_on_edit(self) -> None:
        template = DepartmentTemplate.objects.create(
            department=self.dept, name="Mẫu", created_by=self.admin_user
        )
        template.name = "Mẫu sửa"
        self.admin_instance.save_model(
            self._request(self.other), template, form=None, change=True
        )
        template.refresh_from_db()
        self.assertEqual(template.created_by, self.admin_user)


# ---------------------------------------------------------------------------
# Admin ExamPackageDepartment inline: template must belong to the department
# ---------------------------------------------------------------------------


class ExamPackageDepartmentInlineFormTests(APITestCase):
    def setUp(self) -> None:
        from examinations.admin import ExamPackageDepartmentInlineForm

        self.form_class = ExamPackageDepartmentInlineForm
        self.clinical = Department.objects.get(code="kham_lam_sang")
        self.lab = Department.objects.get(code="xet_nghiem")
        self.package = ExamPackage.objects.create(name="Gói test", exam_type="periodic")
        self.clinical_tpl = _create_template(self.clinical, "LS", [])
        self.lab_tpl = _create_template(self.lab, "XN", [])

    def test_matching_template_accepted(self) -> None:
        form = self.form_class(
            data={
                "exam_package": str(self.package.id),
                "department": str(self.clinical.id),
                "template": str(self.clinical_tpl.id),
                "order": 1,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_mismatched_template_rejected(self) -> None:
        form = self.form_class(
            data={
                "exam_package": str(self.package.id),
                "department": str(self.clinical.id),
                "template": str(self.lab_tpl.id),
                "order": 1,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("template", form.errors)


# ---------------------------------------------------------------------------
# Admin DepartmentResult form: dynamic table from template_snapshot
# ---------------------------------------------------------------------------


class DepartmentResultAdminFormTests(APITestCase):
    def setUp(self) -> None:
        from accounts.models import Company
        from examinations.admin import DepartmentResultAdminForm
        from examinations.models import ExamPackage, ExamPackageDepartment
        from patients.models import Patient

        self.form_class = DepartmentResultAdminForm
        self.dept = Department.objects.get(code="xet_nghiem")
        self.tpl = _create_template(
            self.dept,
            "XN",
            [
                {
                    "key": "hb",
                    "label": "HB",
                    "field_type": "number",
                    "unit": "g/dL",
                    "order": 1,
                },
                {
                    "key": "note",
                    "label": "Ghi chú",
                    "field_type": "textarea",
                    "order": 2,
                },
            ],
        )
        company = Company.objects.create(name="Cty", code="CTY_T")
        patient = Patient.objects.create(
            company=company,
            employee_code="E01",
            full_name="Test",
            dob=date.today(),
            gender="M",
        )
        package = ExamPackage.objects.create(name="Gói", exam_type="periodic")
        ExamPackageDepartment.objects.create(
            exam_package=package, department=self.dept, template=self.tpl, order=1
        )
        user = User.objects.create_user(
            email="fa@t.com", password="x", full_name="F", role="doctor"
        )
        self.exam = Examination.objects.create(
            patient=patient,
            exam_package=package,
            exam_type="periodic",
            exam_date=date.today(),
            doctor=user,
        )
        self.result = DepartmentResult.objects.create(
            examination=self.exam,
            department=self.dept,
            template_snapshot=self.tpl.fields_config,
        )
        self.result._sync_values({"hb": 12})

    def test_dynamic_fields_generated(self) -> None:
        form = self.form_class(instance=self.result)
        self.assertIn("dr_field_hb", form.fields)
        self.assertIn("dr_field_note", form.fields)
        self.assertIsInstance(form.fields["dr_field_hb"], forms.FloatField)
        self.assertIsInstance(form.fields["dr_field_note"].widget, forms.Textarea)

    def test_initial_values_from_data(self) -> None:
        form = self.form_class(instance=self.result)
        self.assertEqual(form.fields["dr_field_hb"].initial, 12)

    def test_save_collects_values_into_data(self) -> None:
        data = {
            "version": 1,
            "examination": str(self.exam.id),
            "department": str(self.dept.id),
            "template_snapshot": self.tpl.fields_config,
            "dr_field_hb": "14.5",
            "dr_field_note": "bình thường",
        }
        form = self.form_class(data, instance=self.result)
        self.assertTrue(form.is_valid(), form.errors)
        result = form.save()
        result.refresh_from_db()
        self.assertEqual(result.data, {"hb": 14.5, "note": "bình thường"})

    def test_template_snapshot_disabled(self) -> None:
        form = self.form_class(instance=self.result)
        self.assertTrue(form.fields["template_snapshot"].disabled)
