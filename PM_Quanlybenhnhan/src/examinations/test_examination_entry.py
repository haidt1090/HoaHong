"""
Tests for Phase 2 — Sprint 5: Examination Entry.

Covers:
- Examination creation auto-spawns one DepartmentResult per package department
- template_snapshot freezes the template's fields_config at creation time
- Department-level write locking (Nurse=clinical, LabTech=para_clinical)
- Doctor writes conclusion + drives the status workflow
- Status workflow enforcement (draft → completed → confirmed)
- form/ endpoint returns departments + snapshots + editable flags
- Delete only allowed for draft exams
- Snapshot integrity: template update does not change existing exam
"""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Company, StaffAssignment
from examinations.models import (
    Department,
    DepartmentField,
    DepartmentTemplate,
    Examination,
    ExamPackage,
    ExamPackageDepartment,
)
from patients.models import Patient

User = get_user_model()


def _make_user(role: str, **kwargs) -> User:
    email = kwargs.pop("email", f"{role}@entry.test")
    return User.objects.create_user(
        email=email,
        password="TestPass123!",
        full_name=f"Test {role.title()}",
        role=role,
        **kwargs,
    )


def _field_entries() -> list[dict]:
    return [
        {
            "key": "hemoglobin",
            "label": "Huyết sắc tố",
            "field_type": "number",
            "order": 1,
        },
        {"key": "note", "label": "Ghi chú", "field_type": "textarea", "order": 2},
    ]


def _expected_snapshot() -> list[dict]:
    """Return the legacy fields_config shape expected in template_snapshot."""
    return [
        {
            "key": "hemoglobin",
            "label": "Huyết sắc tố",
            "type": "number",
            "order": 1,
            "required": False,
        },
        {
            "key": "note",
            "label": "Ghi chú",
            "type": "textarea",
            "order": 2,
            "required": False,
        },
    ]


def _resolve_nr(entry, key):
    nr = entry.get("normal_range")
    if isinstance(nr, dict):
        return nr.get(key)
    return entry.get(f"normal_range_{key}")


def _create_template(dept, name, entries=None):
    entries = entries or _field_entries()
    template = DepartmentTemplate.objects.create(department=dept, name=name)
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


class ExaminationEntryTestBase(APITestCase):
    def setUp(self) -> None:
        self.admin = _make_user("admin")
        self.doctor = _make_user("doctor")
        self.nurse = _make_user("nurse")
        self.labtech = _make_user("labtech")

        self.company = Company.objects.create(name="Cty A", code="CTYA")
        # LabTech is scoped to assigned companies; grant access to this one.
        StaffAssignment.objects.create(user=self.labtech, company=self.company)
        self.patient = Patient.objects.create(
            company=self.company,
            employee_code="E001",
            full_name="Nguyễn Văn A",
            dob=date(1990, 1, 1),
            gender="M",
        )

        self.clinical = Department.objects.get(code="kham_lam_sang")
        self.lab = Department.objects.get(code="xet_nghiem")
        self.clinical_tpl = _create_template(self.clinical, "LS")
        self.lab_tpl = _create_template(self.lab, "XN")
        self.package = ExamPackage.objects.create(
            name="Gói định kỳ", exam_type="periodic"
        )
        ExamPackageDepartment.objects.create(
            exam_package=self.package,
            department=self.clinical,
            template=self.clinical_tpl,
            order=1,
        )
        ExamPackageDepartment.objects.create(
            exam_package=self.package,
            department=self.lab,
            template=self.lab_tpl,
            order=2,
        )

        self.list_url = reverse("examinations:examination-list")

    def _create_exam(self, user=None) -> Examination:
        self.client.force_authenticate(user or self.doctor)
        response = self.client.post(
            self.list_url,
            {
                "patient": str(self.patient.id),
                "exam_package": str(self.package.id),
                "exam_type": "periodic",
                "exam_date": "2026-07-01",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED, response.data
        return Examination.objects.get(id=response.data["id"])


# ---------------------------------------------------------------------------
# Creation + spawning + snapshot
# ---------------------------------------------------------------------------


class ExaminationCreateTests(ExaminationEntryTestBase):
    def test_create_spawns_one_result_per_department(self) -> None:
        exam = self._create_exam()
        self.assertEqual(exam.department_results.count(), 2)
        dept_ids = set(exam.department_results.values_list("department_id", flat=True))
        self.assertEqual(dept_ids, {self.clinical.id, self.lab.id})

    def test_snapshot_captures_fields_config(self) -> None:
        exam = self._create_exam()
        result = exam.department_results.get(department=self.clinical)
        self.assertEqual(result.template_snapshot, _expected_snapshot())

    def test_doctor_set_from_request(self) -> None:
        exam = self._create_exam(self.doctor)
        self.assertEqual(exam.doctor_id, self.doctor.id)

    def test_retrieve_returns_doctor_name(self) -> None:
        exam = self._create_exam(self.doctor)
        self.client.force_authenticate(self.admin)
        response = self.client.get(
            reverse("examinations:examination-detail", args=[exam.id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["doctor_name"], self.doctor.display_name)

        exam.doctor = None
        exam.save(update_fields=["doctor"])
        response = self.client.get(
            reverse("examinations:examination-detail", args=[exam.id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["doctor_name"], "")

    def test_create_defaults_to_draft(self) -> None:
        exam = self._create_exam()
        self.assertEqual(exam.status, "draft")

    def test_nurse_can_create_draft(self) -> None:
        exam = self._create_exam(self.nurse)
        self.assertEqual(exam.status, "draft")

    def test_labtech_cannot_create(self) -> None:
        self.client.force_authenticate(self.labtech)
        response = self.client.post(
            self.list_url,
            {
                "patient": str(self.patient.id),
                "exam_package": str(self.package.id),
                "exam_type": "periodic",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_without_package_rejected(self) -> None:
        self.client.force_authenticate(self.doctor)
        response = self.client.post(
            self.list_url,
            {"patient": str(self.patient.id), "exam_type": "periodic"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_snapshot_unchanged_after_template_update(self) -> None:
        exam = self._create_exam()
        # Bump the template version + change config
        self.client.force_authenticate(self.admin)
        self.client.patch(
            reverse("examinations:template-detail", args=[self.clinical_tpl.id]),
            {
                "fields": [
                    {"key": "new", "label": "Mới", "field_type": "text", "order": 1}
                ]
            },
            format="json",
        )
        result = exam.department_results.get(department=self.clinical)
        result.refresh_from_db()
        # The exam's frozen snapshot still holds the original config.
        self.assertEqual(result.template_snapshot, _expected_snapshot())


# ---------------------------------------------------------------------------
# Department data write locking
# ---------------------------------------------------------------------------


class DepartmentWriteLockTests(ExaminationEntryTestBase):
    def _dept_url(self, exam: Examination, dept: Department) -> str:
        return reverse("examinations:examination-department", args=[exam.id, dept.id])

    def test_nurse_can_write_clinical(self) -> None:
        exam = self._create_exam()
        self.client.force_authenticate(self.nurse)
        response = self.client.put(
            self._dept_url(exam, self.clinical),
            {"data": {"hemoglobin": 14}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        result = exam.department_results.get(department=self.clinical)
        self.assertEqual(result.data, {"hemoglobin": 14})

    def test_nurse_cannot_write_paraclinical(self) -> None:
        exam = self._create_exam()
        self.client.force_authenticate(self.nurse)
        response = self.client.put(
            self._dept_url(exam, self.lab),
            {"data": {"hemoglobin": 14}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_labtech_can_write_paraclinical(self) -> None:
        exam = self._create_exam()
        self.client.force_authenticate(self.labtech)
        response = self.client.put(
            self._dept_url(exam, self.lab),
            {"data": {"hemoglobin": 13}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

    def test_labtech_cannot_write_clinical(self) -> None:
        exam = self._create_exam()
        self.client.force_authenticate(self.labtech)
        response = self.client.put(
            self._dept_url(exam, self.clinical),
            {"data": {"hemoglobin": 13}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_can_write_any_department(self) -> None:
        exam = self._create_exam()
        self.client.force_authenticate(self.doctor)
        for dept in (self.clinical, self.lab):
            response = self.client.put(
                self._dept_url(exam, dept),
                {"data": {"hemoglobin": 15}},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

    def test_complete_marks_completed_by(self) -> None:
        exam = self._create_exam()
        self.client.force_authenticate(self.nurse)
        url = reverse(
            "examinations:examination-department-complete",
            args=[exam.id, self.clinical.id],
        )
        response = self.client.patch(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        result = exam.department_results.get(department=self.clinical)
        self.assertEqual(result.completed_by_id, self.nurse.id)
        self.assertIsNotNone(result.completed_at)


# ---------------------------------------------------------------------------
# Conclusion + status workflow
# ---------------------------------------------------------------------------


class WorkflowTests(ExaminationEntryTestBase):
    def _status_url(self, exam: Examination) -> str:
        return reverse("examinations:examination-status", args=[exam.id])

    def test_doctor_writes_conclusion(self) -> None:
        exam = self._create_exam()
        self.client.force_authenticate(self.doctor)
        response = self.client.patch(
            reverse("examinations:examination-detail", args=[exam.id]),
            {"conclusion": "Sức khỏe bình thường"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        exam.refresh_from_db()
        self.assertEqual(exam.conclusion, "Sức khỏe bình thường")

    def test_draft_to_completed_auto_when_all_departments_filled(self) -> None:
        exam = self._create_exam()

        # Fill clinical dept: all fields must be present
        self.client.force_authenticate(self.nurse)
        dept_url = reverse("examinations:examination-department", args=[exam.id, self.clinical.id])
        response = self.client.put(
            dept_url,
            {"data": {"hemoglobin": 14, "note": "Ổn"}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        exam.refresh_from_db()
        self.assertEqual(exam.status, "draft")  # Chưa đủ vì lab chưa có

        # Fill lab dept: all fields must be present
        self.client.force_authenticate(self.labtech)
        dept_url = reverse("examinations:examination-department", args=[exam.id, self.lab.id])
        response = self.client.put(
            dept_url,
            {"data": {"hemoglobin": 13, "note": "BT"}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        exam.refresh_from_db()
        self.assertEqual(exam.status, "completed")  # Tự động hoàn thành

    def test_manual_set_completed_rejected(self) -> None:
        exam = self._create_exam()
        self.client.force_authenticate(self.doctor)
        response = self.client.patch(
            self._status_url(exam), {"status": "completed"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        status_msg = response.data["status"]
        if isinstance(status_msg, list):
            status_msg = status_msg[0]
        self.assertIn("tự động", status_msg.lower())

    def test_completed_to_confirmed_by_doctor(self) -> None:
        exam = self._create_exam()
        exam.status = "completed"
        exam.save()
        self.client.force_authenticate(self.doctor)
        response = self.client.patch(
            self._status_url(exam), {"status": "confirmed"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        exam.refresh_from_db()
        self.assertEqual(exam.status, "confirmed")

    def test_draft_to_confirmed_rejected(self) -> None:
        exam = self._create_exam()
        self.client.force_authenticate(self.doctor)
        response = self.client.patch(
            self._status_url(exam), {"status": "confirmed"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_partial_department_data_keeps_draft(self) -> None:
        exam = self._create_exam()
        self.client.force_authenticate(self.nurse)
        # Fill only hemoglobin, leave note empty
        self.client.put(
            reverse("examinations:examination-department", args=[exam.id, self.clinical.id]),
            {"data": {"hemoglobin": 14}},
            format="json",
        )
        exam.refresh_from_db()
        self.assertEqual(exam.status, "draft")

    def test_clear_field_downgrades_to_draft(self) -> None:
        exam = self._create_exam()
        # Fill both departments fully → completed
        self.client.force_authenticate(self.nurse)
        self.client.put(
            reverse("examinations:examination-department", args=[exam.id, self.clinical.id]),
            {"data": {"hemoglobin": 14, "note": "Ổn"}},
            format="json",
        )
        self.client.force_authenticate(self.labtech)
        self.client.put(
            reverse("examinations:examination-department", args=[exam.id, self.lab.id]),
            {"data": {"hemoglobin": 13, "note": "BT"}},
            format="json",
        )
        exam.refresh_from_db()
        self.assertEqual(exam.status, "completed")

        # Clear a field → back to draft
        self.client.force_authenticate(self.nurse)
        self.client.put(
            reverse("examinations:examination-department", args=[exam.id, self.clinical.id]),
            {"data": {"hemoglobin": 14, "note": ""}},
            format="json",
        )
        exam.refresh_from_db()
        self.assertEqual(exam.status, "draft")

    def test_nurse_cannot_change_status(self) -> None:
        exam = self._create_exam()
        self.client.force_authenticate(self.nurse)
        response = self.client.patch(
            self._status_url(exam), {"status": "completed"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirmed_exam_immutable_for_doctor(self) -> None:
        exam = self._create_exam()
        exam.status = "confirmed"
        exam.save()
        self.client.force_authenticate(self.doctor)
        response = self.client.patch(
            reverse("examinations:examination-detail", args=[exam.id]),
            {"conclusion": "Sửa"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_reopen_confirmed(self) -> None:
        exam = self._create_exam()
        exam.status = "confirmed"
        exam.save()
        self.client.force_authenticate(self.admin)
        response = self.client.patch(
            self._status_url(exam), {"status": "completed"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)


# ---------------------------------------------------------------------------
# Delete rules
# ---------------------------------------------------------------------------


class ExaminationDeleteTests(ExaminationEntryTestBase):
    def test_draft_deletable_by_doctor(self) -> None:
        exam = self._create_exam()
        self.client.force_authenticate(self.doctor)
        response = self.client.delete(
            reverse("examinations:examination-detail", args=[exam.id])
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Examination.objects.filter(id=exam.id).exists())

    def test_confirmed_not_deletable(self) -> None:
        exam = self._create_exam()
        exam.status = "confirmed"
        exam.save()
        self.client.force_authenticate(self.doctor)
        response = self.client.delete(
            reverse("examinations:examination-detail", args=[exam.id])
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ---------------------------------------------------------------------------
# form/ endpoint
# ---------------------------------------------------------------------------


class ExaminationFormEndpointTests(ExaminationEntryTestBase):
    def test_form_returns_departments_with_editable_flags(self) -> None:
        exam = self._create_exam()
        self.client.force_authenticate(self.nurse)
        response = self.client.get(
            reverse("examinations:examination-form", args=[exam.id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        depts = {d["department"]["code"]: d for d in response.data["departments"]}
        self.assertEqual(len(depts), 2)
        self.assertTrue(depts["kham_lam_sang"]["editable"])
        self.assertFalse(depts["xet_nghiem"]["editable"])
        self.assertEqual(
            depts["kham_lam_sang"]["template_snapshot"], _expected_snapshot()
        )

    def test_form_returns_fields_table(self) -> None:
        exam = self._create_exam()
        self.client.force_authenticate(self.doctor)
        response = self.client.get(
            reverse("examinations:examination-form", args=[exam.id])
        )
        dept = response.data["departments"][0]
        self.assertIn("fields_table", dept)
        table = dept["fields_table"]
        self.assertEqual(len(table), 2)
        self.assertEqual(table[0]["key"], "hemoglobin")
        self.assertEqual(table[0]["label"], "Huyết sắc tố")
        self.assertIsNone(table[0]["value"])  # chưa nhập dữ liệu


# ---------------------------------------------------------------------------
# Table-format data input/output
# ---------------------------------------------------------------------------


class TableFormatTests(ExaminationEntryTestBase):
    def _dept_url(self, exam: Examination, dept: Department) -> str:
        return reverse("examinations:examination-department", args=[exam.id, dept.id])

    def test_put_returns_fields_table_in_response(self) -> None:
        exam = self._create_exam()
        self.client.force_authenticate(self.doctor)
        response = self.client.put(
            self._dept_url(exam, self.clinical),
            {"data": {"hemoglobin": 14, "note": "ổn"}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("fields_table", response.data)
        ft = response.data["fields_table"]
        self.assertEqual(ft[0]["key"], "hemoglobin")
        self.assertEqual(ft[0]["value"], 14)
        self.assertEqual(ft[1]["key"], "note")
        self.assertEqual(ft[1]["value"], "ổn")

    def test_put_accepts_fields_table_input(self) -> None:
        exam = self._create_exam()
        self.client.force_authenticate(self.doctor)
        response = self.client.put(
            self._dept_url(exam, self.clinical),
            {"fields_table": [{"key": "hemoglobin", "value": 15}]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = exam.department_results.get(department=self.clinical)
        self.assertEqual(result.data, {"hemoglobin": 15})

    def test_fields_table_input_takes_priority_over_data(self) -> None:
        exam = self._create_exam()
        self.client.force_authenticate(self.doctor)
        response = self.client.put(
            self._dept_url(exam, self.clinical),
            {
                "data": {"hemoglobin": 99},
                "fields_table": [{"key": "hemoglobin", "value": 12}],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = exam.department_results.get(department=self.clinical)
        self.assertEqual(result.data, {"hemoglobin": 12})

    def test_put_empty_data_does_not_invent_random_values(self) -> None:
        """A successful PUT with {} must not seed random in-range numbers.

        The data-entry UI can send an empty `data` object when InputNumber
        values have not been committed yet; inventing values made that look
        like a successful save of the clinician's input.
        """
        exam = self._create_exam()
        result = exam.department_results.get(department=self.clinical)
        snapshot = list(result.template_snapshot)
        snapshot[0]["normal_range"] = {"min": 12, "max": 16}
        result.template_snapshot = snapshot
        result.save(update_fields=["template_snapshot"])

        self.client.force_authenticate(self.doctor)
        response = self.client.put(
            self._dept_url(exam, self.clinical),
            {"data": {}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result.refresh_from_db()
        self.assertEqual(result.data, {})


# ---------------------------------------------------------------------------
# Full multi-role workflow (Definition of Done)
# ---------------------------------------------------------------------------


class FullWorkflowTests(ExaminationEntryTestBase):
    def test_full_flow_create_fill_complete_confirm(self) -> None:
        # 1. Nurse creates draft.
        exam = self._create_exam(self.nurse)

        # 2. Nurse fills clinical department (all 2 fields).
        self.client.force_authenticate(self.nurse)
        self.client.put(
            reverse(
                "examinations:examination-department", args=[exam.id, self.clinical.id]
            ),
            {"data": {"hemoglobin": 14, "note": "Ổn"}},
            format="json",
        )

        # 3. LabTech fills lab department (all 2 fields).
        self.client.force_authenticate(self.labtech)
        self.client.put(
            reverse("examinations:examination-department", args=[exam.id, self.lab.id]),
            {"data": {"hemoglobin": 13, "note": "BT"}},
            format="json",
        )

        # 4. Status auto-switches to completed after all departments are filled.
        exam.refresh_from_db()
        self.assertEqual(exam.status, "completed")

        # 5. Doctor writes conclusion.
        self.client.force_authenticate(self.doctor)
        self.client.patch(
            reverse("examinations:examination-detail", args=[exam.id]),
            {"conclusion": "Đủ sức khỏe"},
            format="json",
        )

        # 6. Doctor confirms.
        self.client.patch(
            reverse("examinations:examination-status", args=[exam.id]),
            {"status": "confirmed"},
            format="json",
        )

        exam.refresh_from_db()
        self.assertEqual(exam.status, "confirmed")
        self.assertEqual(exam.conclusion, "Đủ sức khỏe")
        clinical_result = exam.department_results.get(department=self.clinical)
        lab_result = exam.department_results.get(department=self.lab)
        self.assertEqual(clinical_result.data, {"hemoglobin": 14, "note": "Ổn"})
        self.assertEqual(lab_result.data, {"hemoglobin": 13, "note": "BT"})
