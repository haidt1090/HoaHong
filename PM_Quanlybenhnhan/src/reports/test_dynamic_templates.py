"""
Tests for Sprint 9a — Dynamic report template engine.

Covers:
  * ReportDataset construction (nesting, abnormal detection, duplicate depts)
  * BodyBuilder dispatch + each coded body function
  * The render engine, its template sandbox, and document assembly
  * Template CRUD/preview API + permissions
  * generate_report_task: template path vs. legacy Excel fallback
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Company, CompanyExamPackage, User
from examinations.models import (
    Department,
    DepartmentField,
    DepartmentResult,
    DepartmentTemplate,
    Examination,
    ExamPackage,
    ExamPackageDepartment,
)
from patients.models import Patient
from reports.body_builder import BodyBuilder, UnknownBodyType
from reports.models import (
    DepartmentReportTemplate,
    Report,
    ReportTemplate,
    ReportTemplateItem,
)
from reports.render import (
    TemplateRenderError,
    build_context,
    build_department_context,
    build_document,
    render_fragment,
    render_report,
)
from reports.report_builder import build_report_dataset

CLINIC = {
    "name": "PHÒNG KHÁM TEST",
    "address": "123 Đường Test",
    "phone": "0900000000",
    "email": "",
    "website": "",
}


class ReportTemplateTestBase(TestCase):
    """Builds a small but realistic package: 2 departments, one duplicated."""

    @classmethod
    def setUpTestData(cls) -> None:
        cls.company = Company.objects.create(name="Công ty ABC", code="ABC")
        cls.admin = User.objects.create_user(
            email="admin9a@x.com", password="pw", role="admin", full_name="Admin"
        )
        cls.nurse = User.objects.create_user(
            email="nurse9a@x.com", password="pw", role="nurse", full_name="Nurse"
        )

        cls.parent = Department.objects.create(name="Cận lâm sàng", code="CLS")
        cls.lab = Department.objects.create(
            name="Xét nghiệm", code="XN", parent=cls.parent, category="para_clinical"
        )
        cls.clinical = Department.objects.create(
            name="Khám lâm sàng", code="LS", category="clinical"
        )

        # Two templates on the SAME department (Sprint 4a duplicate binding).
        cls.tpl_blood = DepartmentTemplate.objects.create(
            department=cls.lab, name="XN máu"
        )
        DepartmentField.objects.create(
            template=cls.tpl_blood,
            key="hbg",
            label="Hemoglobin",
            field_type="number",
            unit="g/dL",
            normal_range_min=Decimal("12.0"),
            normal_range_max=Decimal("16.0"),
            order=0,
            default_price=Decimal("50000"),
            test_category="huyet_hoc",
        )
        DepartmentField.objects.create(
            template=cls.tpl_blood,
            key="wbc",
            label="Bạch cầu",
            field_type="number",
            unit="10^9/L",
            normal_range_min=Decimal("4.0"),
            normal_range_max=Decimal("10.0"),
            order=1,
            default_price=Decimal("30000"),
            test_category="huyet_hoc",
        )
        cls.tpl_urine = DepartmentTemplate.objects.create(
            department=cls.lab, name="XN nước tiểu"
        )
        DepartmentField.objects.create(
            template=cls.tpl_urine,
            key="pro",
            label="Protein niệu",
            field_type="text",
            order=0,
            default_price=Decimal("20000"),
        )
        cls.tpl_clinical = DepartmentTemplate.objects.create(
            department=cls.clinical, name="Nội tổng quát"
        )
        DepartmentField.objects.create(
            template=cls.tpl_clinical,
            key="mach",
            label="Mạch",
            field_type="number",
            unit="lần/phút",
            normal_range_min=Decimal("60"),
            normal_range_max=Decimal("100"),
            order=0,
            default_price=Decimal("10000"),
        )

        cls.package = ExamPackage.objects.create(
            name="KSK định kỳ", exam_type="periodic"
        )
        ExamPackageDepartment.objects.create(
            exam_package=cls.package,
            department=cls.clinical,
            template=cls.tpl_clinical,
            order=0,
        )
        ExamPackageDepartment.objects.create(
            exam_package=cls.package,
            department=cls.lab,
            template=cls.tpl_blood,
            order=1,
        )
        ExamPackageDepartment.objects.create(
            exam_package=cls.package,
            department=cls.lab,
            template=cls.tpl_urine,
            order=2,
        )

        cls.cep = CompanyExamPackage.objects.create(
            company=cls.company,
            exam_package=cls.package,
            pricing_mode="per_field",
            total_employees=2,
        )

        # Patient 1 — one abnormal value (wbc high), one normal.
        cls.p1 = Patient.objects.create(
            company=cls.company,
            employee_code="NV001",
            full_name="Nguyễn Văn An",
            dob=date(1990, 5, 20),
            gender="M",
            department="Sản xuất",
            cccd="079090000001",
        )
        cls.exam1 = Examination.objects.create(
            patient=cls.p1,
            company_exam_package=cls.cep,
            exam_package=cls.package,
            exam_type="periodic",
            exam_date=date(2026, 5, 26),
            conclusion="Loại II\nTheo dõi",
            consultation="Uống nhiều nước",
            work_fitness="fit",
        )
        cls._fill(cls.exam1, cls.clinical, cls.tpl_clinical, {"mach": 78})
        cls._fill(cls.exam1, cls.lab, cls.tpl_blood, {"hbg": 13.5, "wbc": 12.5})
        cls._fill(cls.exam1, cls.lab, cls.tpl_urine, {"pro": "Âm tính"})

        # Patient 2 — hbg below range.
        cls.p2 = Patient.objects.create(
            company=cls.company,
            employee_code="NV002",
            full_name="Trần Thị Bình",
            dob=date(1995, 2, 10),
            gender="F",
            department="Kế toán",
            cccd="079090000002",
        )
        cls.exam2 = Examination.objects.create(
            patient=cls.p2,
            company_exam_package=cls.cep,
            exam_package=cls.package,
            exam_type="periodic",
            exam_date=date(2026, 5, 27),
            conclusion="Loại III",
            work_fitness="unfit",
        )
        cls._fill(cls.exam2, cls.clinical, cls.tpl_clinical, {"mach": 88})
        cls._fill(cls.exam2, cls.lab, cls.tpl_blood, {"hbg": 9.0, "wbc": 6.0})

    @staticmethod
    def _fill(exam, department, template, data) -> DepartmentResult:
        result, _ = DepartmentResult.objects.get_or_create(
            examination=exam,
            department=department,
            template=template,
            defaults={"template_snapshot": template.fields_config},
        )
        result._sync_values(data)
        result.save()
        return result


@override_settings(CLINIC_INFO=CLINIC)
class ReportDatasetTests(ReportTemplateTestBase):
    def test_dataset_nests_results_per_department(self):
        ds = build_report_dataset(self.cep)

        self.assertEqual(ds.total_employees, 2)
        self.assertEqual(len(ds.departments), 3)

        p1 = ds.patients[0]  # ordered by full_name → "Nguyễn Văn An"
        self.assertEqual(p1.ho_ten, "Nguyễn Văn An")
        # Same department bound twice must produce two separate blocks.
        lab_blocks = p1.departments_for(str(self.lab.id))
        self.assertEqual(len(lab_blocks), 2)
        names = sorted(b.template_name for b in lab_blocks)
        self.assertEqual(names, ["XN máu", "XN nước tiểu"])

    def test_field_keys_do_not_collide_across_departments(self):
        """The flat legacy row namespace collides; the nested one must not."""
        ds = build_report_dataset(self.cep)
        p1 = ds.patients[0]
        blood = next(d for d in p1.departments if d.template_name == "XN máu")
        urine = next(d for d in p1.departments if d.template_name == "XN nước tiểu")
        self.assertEqual([f.key for f in blood.fields], ["hbg", "wbc"])
        self.assertEqual([f.key for f in urine.fields], ["pro"])

    def test_abnormal_detection_high_and_low(self):
        ds = build_report_dataset(self.cep)
        p1, p2 = ds.patients[0], ds.patients[1]

        wbc = next(f for d in p1.departments for f in d.fields if f.key == "wbc")
        self.assertTrue(wbc.is_abnormal)
        self.assertEqual(wbc.abnormal_direction, "high")

        hbg1 = next(f for d in p1.departments for f in d.fields if f.key == "hbg")
        self.assertFalse(hbg1.is_abnormal)

        hbg2 = next(f for d in p2.departments for f in d.fields if f.key == "hbg")
        self.assertTrue(hbg2.is_abnormal)
        self.assertEqual(hbg2.abnormal_direction, "low")

    def test_non_numeric_value_is_never_abnormal(self):
        ds = build_report_dataset(self.cep)
        pro = next(
            f for d in ds.patients[0].departments for f in d.fields if f.key == "pro"
        )
        self.assertEqual(pro.value, "Bình thường")
        self.assertFalse(pro.is_abnormal)

    def test_numbers_render_without_trailing_zeros(self):
        ds = build_report_dataset(self.cep)
        mach = next(
            f for d in ds.patients[0].departments for f in d.fields if f.key == "mach"
        )
        self.assertEqual(mach.value, "78")

    def test_missing_value_marked_empty(self):
        ds = build_report_dataset(self.cep)
        p2 = ds.patients[1]
        # p2 has no urine result at all.
        self.assertEqual(len(p2.departments_for(str(self.lab.id))), 1)

    def test_exam_date_is_display_only(self):
        # ``exam_date`` is a display label only — it does NOT filter patients.
        ds = build_report_dataset(self.cep, exam_date="2026-05-26")
        self.assertEqual(ds.exam_date, "2026-05-26")
        self.assertEqual(ds.total_employees, 2)

    def test_field_metadata_carried_through(self):
        ds = build_report_dataset(self.cep)
        hbg = next(
            f for d in ds.patients[0].departments for f in d.fields if f.key == "hbg"
        )
        self.assertEqual(hbg.label, "Hemoglobin")
        self.assertEqual(hbg.unit, "g/dL")
        self.assertEqual(hbg.normal_range, "12 - 16")
        self.assertEqual(hbg.display, "13.5 g/dL")

    def test_abnormal_count_and_helpers(self):
        ds = build_report_dataset(self.cep)
        self.assertEqual(ds.patients[0].abnormal_count, 1)
        blood = next(
            d for d in ds.patients[0].departments if d.template_name == "XN máu"
        )
        self.assertTrue(blood.has_abnormal)
        self.assertEqual(len(blood.abnormal_fields), 1)
        self.assertEqual(blood.field("hbg").value, "13.5")

    def test_resolve_diagnosis_uses_stored_values(self):
        from reports.report_builder import _resolve_diagnosis

        exam = self.exam1
        exam.work_fitness = "fit"
        exam.consultation = "Tư vấn thủ công"
        exam.save()
        classification, wf, benh_mac, tu_van = _resolve_diagnosis(exam)
        self.assertEqual(wf, "fit")
        self.assertEqual(tu_van, "Tư vấn thủ công")

    def test_resolve_diagnosis_derives_on_the_fly_without_persisting(self):
        from diagnosis.models import DiagnosisKeyword
        from examinations.models import DepartmentFieldAbnormal, Examination
        from reports.report_builder import _resolve_diagnosis

        # Reset exam2 to a clean unconcluded state.
        self.exam2.work_fitness = "pending"
        self.exam2.consultation = ""
        self.exam2.disease = ""
        self.exam2.save()

        DiagnosisKeyword.objects.create(
            keyword="hemoglobin thấp",
            disease_name="Bệnh suy diễn",
            conclusion_template="Tư vấn suy diễn",
            classification=DiagnosisKeyword.CLASSIFICATION_UNFIT,
            is_active=True,
        )
        # Attach a "low" abnormal label to the hbg field.
        DepartmentFieldAbnormal.objects.create(
            field=self.tpl_blood.fields.get(key="hbg"),
            direction="low",
            label="Hemoglobin thấp",
        )
        # Re-snapshot the department result so template_snapshot picks up the
        # abnormal definition.
        DepartmentResult.objects.filter(
            examination=self.exam2, template=self.tpl_blood
        ).update(template_snapshot=self.tpl_blood.fields_config)

        exam = Examination.objects.get(id=self.exam2.id)
        classification, wf, benh_mac, tu_van = _resolve_diagnosis(exam)
        self.assertEqual(classification, 5)
        self.assertEqual(wf, "unfit")
        self.assertIn("Bệnh suy diễn", benh_mac)
        self.assertIn("Tư vấn suy diễn", tu_van)
        # Must NOT persist.
        exam.refresh_from_db()
        self.assertEqual(exam.work_fitness, "pending")
        self.assertEqual(exam.disease, "")
        self.assertEqual(exam.consultation, "")


@override_settings(CLINIC_INFO=CLINIC)
class RenderEngineTests(ReportTemplateTestBase):
    def test_render_fragment_resolves_variables(self):
        ds = build_report_dataset(self.cep)
        context = build_context(ds)
        html = render_fragment("{{ clinic_name }} — {{ company.name }}", context)
        self.assertEqual(html, "PHÒNG KHÁM TEST — Công ty ABC")

    def test_context_exposes_documented_shortcodes(self):
        ds = build_report_dataset(self.cep)
        context = build_context(ds)
        for key in (
            "clinic_name",
            "clinic_address",
            "clinic_phone",
            "company",
            "exam_date",
            "report_date",
            "total_employees",
            "patients",
        ):
            self.assertIn(key, context)
        self.assertEqual(context["total_employees"], 2)

    def test_result_table_tag_renders_table(self):
        """``{% result_table %}`` is a builtin tag callable from body_html."""
        ds = build_report_dataset(self.cep)
        patient = ds.patients[0]
        context = build_department_context(
            patient, patient.departments[0], build_context(ds)
        )
        html = render_fragment("{% result_table %}", context)
        self.assertIn("Danh mục khám", html)
        self.assertIn("Khoảng tham chiếu", html)
        self.assertIn("abnormal", html)  # one of the seeded values is abnormal

    def test_result_table_tag_no_patient_renders_empty(self):
        html = render_fragment("A{% result_table %}B", {})
        self.assertEqual(html, "AB")

    def test_company_summary_table_tag_renders_flat_table(self):
        ds = build_report_dataset(self.cep)
        context = build_context(ds)
        html = render_fragment("{% company_summary_table %}", context)
        self.assertIn("<table", html)
        self.assertIn("STT", html)
        self.assertIn("Mã NV", html)
        self.assertIn("Kết luận", html)
        # One row per employee (plus header) — dataset has 2 employees.
        self.assertGreater(html.count("<tr>"), 2)

    def test_autoescaping_is_on(self):
        ds = build_report_dataset(self.cep)
        self.company.name = "<script>alert(1)</script>"
        context = build_context(ds)
        context["company"] = self.company
        html = render_fragment("{{ company.name }}", context)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_sandbox_blocks_include_tag(self):
        with self.assertRaises(TemplateRenderError) as ctx:
            render_fragment('{% include "admin/base.html" %}', {})
        self.assertIn("include", str(ctx.exception).lower())

    def test_sandbox_blocks_load_and_extends_and_debug(self):
        for source in (
            "{% load static %}",
            '{% extends "base.html" %}',
            "{% debug %}",
            '{% ssi "/etc/passwd" %}',
        ):
            with self.assertRaises(TemplateRenderError):
                render_fragment(source, {})

    def test_syntax_error_is_reported_with_label(self):
        with self.assertRaises(TemplateRenderError) as ctx:
            render_fragment("{% for x in %}", {}, label="header")
        self.assertIn("header", str(ctx.exception))

    def test_sandbox_does_not_mutate_global_tag_libraries(self):
        """
        Regression: the sandbox used to pop tags off ``defaulttags.register``,
        which ``import_library`` returns as a process-wide singleton. That
        removed {% extends %}/{% load %} from *every* engine, breaking the
        Django admin.
        """
        from django.template import defaulttags, loader_tags

        # Build the sandbox first so any mutation would already have happened.
        with self.assertRaises(TemplateRenderError):
            render_fragment("{% load static %}", {})

        for tag in ("load", "debug"):
            self.assertIn(tag, defaulttags.register.tags)
        for tag in ("extends", "include"):
            self.assertIn(tag, loader_tags.register.tags)

        # A normal Django template using the blocked tags must still compile
        # and render through the project engine.
        from django.template import Context, Template

        rendered = Template("{% load static %}{% if 1 %}ok{% endif %}").render(
            Context({})
        )
        self.assertEqual(rendered, "ok")

    def test_normal_engine_still_renders_admin_templates(self):
        from django.template.loader import render_to_string

        html = render_to_string("admin/base.html", {})
        self.assertIn("</html>", html.lower())

    def test_build_document_embeds_page_size_and_css(self):
        html = build_document(
            "<p>H</p>",
            "<p>B</p>",
            "<p>F</p>",
            page_size="A3 landscape",
            extra_css=".x{color:red}",
        )
        self.assertIn("size: A3 landscape;", html)
        self.assertIn(".x{color:red}", html)
        self.assertIn("<p>B</p>", html)
        # CSS with literal % and {} must survive verbatim.
        self.assertIn("width: 100%", html)

    def test_render_report_composes_body_without_html_letterhead(self):
        template = ReportTemplate.objects.create(
            name="T1",
            report_type="clinical_detail",
            body_type=ReportTemplate.BODY_CLINICAL_DETAIL_TABLE,
        )
        ds = build_report_dataset(self.cep)
        html = render_report(template, ds)
        self.assertIn("Nguyễn Văn An", html)
        self.assertIn("report-body", html)
        # Letterhead is Excel-only — HTML export has no header/footer fragments.
        self.assertNotIn('class="report-header"', html)
        self.assertNotIn('class="report-footer"', html)

    def test_department_templates_body_renders_per_patient(self):
        dept_tpl = DepartmentReportTemplate.objects.create(
            name="Máu",
            department=self.lab,
            body_html="<b>{{ patient.ho_ten }}</b>"
            "{% for field in fields %}<i>{{ field.label }}={{ field.value }}</i>{% endfor %}",
        )
        template = ReportTemplate.objects.create(
            name="Composite",
            report_type="clinical_detail",
            body_type=ReportTemplate.BODY_DEPARTMENT_TEMPLATES,
        )
        ReportTemplateItem.objects.create(
            report_template=template,
            department_template=dept_tpl,
            department=self.lab,
            exam_template=self.tpl_blood,
            order=0,
        )
        ds = build_report_dataset(self.cep)
        html = render_report(template, ds)

        self.assertIn("Nguyễn Văn An", html)
        self.assertIn("Hemoglobin=13.5", html)
        # exam_template pin must exclude the urine result.
        self.assertNotIn("Protein niệu", html)

    def test_item_without_exam_template_renders_all_matching_departments(self):
        dept_tpl = DepartmentReportTemplate.objects.create(
            name="Mọi XN",
            department=self.lab,
            body_html="{% for field in fields %}[{{ field.label }}]{% endfor %}",
        )
        template = ReportTemplate.objects.create(
            name="Composite2",
            report_type="clinical_detail",
            body_type=ReportTemplate.BODY_DEPARTMENT_TEMPLATES,
        )
        ReportTemplateItem.objects.create(
            report_template=template, department_template=dept_tpl, order=0
        )
        html = render_report(template, build_report_dataset(self.cep))
        self.assertIn("[Hemoglobin]", html)
        self.assertIn("[Protein niệu]", html)

    def test_company_summary_in_department_template_not_duplicated(self):
        """Report-level tags must not repeat once per employee (Excel duplication)."""
        dept_tpl = DepartmentReportTemplate.objects.create(
            name="Tổng hợp CT",
            body_html=(
                "{% company_summary_table show_normal_range=True "
                "highlight_abnormal=False %}"
            ),
        )
        template = ReportTemplate.objects.create(
            name="Summary composite",
            report_type="clinical_detail",
            body_type=ReportTemplate.BODY_DEPARTMENT_TEMPLATES,
            # Omit per_patient — auto False for report-level-only bodies.
        )
        ReportTemplateItem.objects.create(
            report_template=template, department_template=dept_tpl, order=0
        )
        ds = build_report_dataset(self.cep)
        html = render_report(template, ds)

        # Two employees in fixture → table must still appear only once.
        self.assertEqual(html.count("<table"), 1)
        self.assertEqual(html.count("Nguyễn Văn An"), 1)

        # Even if caller forces per_patient=True, the tag still renders once.
        template.body_config = {"per_patient": True}
        template.save(update_fields=["body_config"])
        html_forced = render_report(template, ds)
        self.assertEqual(html_forced.count("<table"), 1)
        self.assertEqual(html_forced.count("Nguyễn Văn An"), 1)


@override_settings(CLINIC_INFO=CLINIC)
class BodyBuilderTests(ReportTemplateTestBase):
    def setUp(self) -> None:
        self.ds = build_report_dataset(self.cep)
        self.context = build_context(self.ds)

    def test_unknown_body_type_raises(self):
        with self.assertRaises(UnknownBodyType):
            BodyBuilder.render("nope", self.ds)

    def test_registry_covers_all_model_choices(self):
        choices = {v for v, _ in ReportTemplate.BODY_TYPE_CHOICES}
        self.assertEqual(choices, set(BodyBuilder.REGISTRY))

    def test_clinical_detail_table_marks_abnormal_cells(self):
        html = BodyBuilder.render(
            "clinical_detail_table",
            self.ds,
            {"highlight_abnormal": True},
            self.context,
        )
        self.assertIn('class="abnormal"', html)
        self.assertIn("Nguyễn Văn An", html)
        self.assertIn("Hemoglobin", html)

    def test_clinical_detail_table_can_disable_highlight(self):
        html = BodyBuilder.render(
            "clinical_detail_table",
            self.ds,
            {"highlight_abnormal": False},
            self.context,
        )
        self.assertNotIn('class="abnormal"', html)

    def test_blood_test_table_respects_column_config(self):
        html = BodyBuilder.render(
            "clinical_detail_blood_test",
            self.ds,
            {"columns": ["hbg"], "show_normal_range": True},
            self.context,
        )
        self.assertIn("Hemoglobin", html)
        self.assertNotIn("Bạch cầu", html)
        self.assertIn("12 - 16", html)

    def test_blood_test_table_filters_by_test_category(self):
        html = BodyBuilder.render(
            "clinical_detail_blood_test",
            self.ds,
            {"test_category": "huyet_hoc"},
            self.context,
        )
        self.assertIn("Hemoglobin", html)
        self.assertIn("Bạch cầu", html)
        self.assertNotIn("Protein niệu", html)

    def test_blood_test_table_reports_no_match(self):
        html = BodyBuilder.render(
            "clinical_detail_blood_test",
            self.ds,
            {"columns": ["khong_ton_tai"]},
            self.context,
        )
        self.assertIn("Không có chỉ số", html)

    def test_summary_stats_counts_gender_and_classification(self):
        html = BodyBuilder.render("summary_stats", self.ds, {}, self.context)
        self.assertIn("Tổng số nhân viên", html)
        self.assertIn("Phân loại sức khỏe", html)
        self.assertIn("Đủ điều kiện lao động", html)
        self.assertIn("Không đủ điều kiện lao động", html)

    def test_cost_breakdown_per_field(self):
        html = BodyBuilder.render("cost_breakdown", self.ds, {}, self.context)
        self.assertIn("TỔNG CỘNG", html)
        self.assertIn("Hemoglobin", html)

    def test_cost_breakdown_package_total_mode(self):
        self.cep.pricing_mode = "package_total"
        self.cep.save()
        self.package.default_package_price = Decimal("500000")
        self.package.save()
        ds = build_report_dataset(self.cep)
        html = BodyBuilder.render("cost_breakdown", ds, {}, build_context(ds))
        self.assertIn("Đơn giá trọn gói", html)
        self.assertIn("1.000.000", html)  # 500k x 2 employees

    def test_html_is_escaped_in_table_bodies(self):
        self.p1.full_name = "<script>x</script>"
        self.p1.save()
        ds = build_report_dataset(self.cep)
        html = BodyBuilder.render("clinical_detail_table", ds, {}, build_context(ds))
        self.assertNotIn("<script>", html)

    # -- template-override path (body_html) -----------------------------------

    def test_template_override_renders_instead_of_fallback(self):
        """When body_html is set, it wins over the Python builder."""
        ds = build_report_dataset(self.cep)
        probe = "TEMPLATE_PROBE_9a"
        html = BodyBuilder.render(
            "clinical_detail_table",
            ds,
            {},
            {},
            body_html=f"<div>{probe}</div>",
        )
        self.assertIn(probe, html)

    def test_blank_body_html_uses_python_fallback(self):
        """Empty body_html must produce the same output as the legacy path."""
        ds = build_report_dataset(self.cep)
        fallback = BodyBuilder.render("clinical_detail_table", ds, {}, {})
        via = BodyBuilder.render("clinical_detail_table", ds, {}, {}, body_html="")
        self.assertEqual(fallback, via)
        self.assertIn("report-table", via)

    def test_department_templates_ignores_body_html(self):
        body_html = "<p>IGNORED_marker</p>"
        html = BodyBuilder.render(
            "department_templates",
            build_report_dataset(self.cep),
            {},
            {},
            body_html=body_html,
        )
        self.assertNotIn("IGNORED_marker", html)

    @staticmethod
    def _tpl(body_type, source):
        return BodyBuilder.render(
            body_type,
            build_report_dataset(CompanyExamPackage.objects.get(company__code="ABC")),
            {},
            {},
            body_html=source,
        )

    def test_ctx_clinical_detail_table_provides_d_header_and_d_rows(self):
        html = self._tpl(
            "clinical_detail_table",
            "{% if d_header %}{{ d_rows.0.cells.0.text }}{% endif %}",
        )
        self.assertIn("1", html)  # stt of first patient

    def test_ctx_blood_test_provides_d_columns_and_d_rows(self):
        html = self._tpl(
            "clinical_detail_blood_test",
            "{% if d_columns %}{{ d_rows.0.ho_ten }}{% endif %}",
        )
        self.assertIn("Nguyễn", html)

    def test_ctx_summary_stats_provides_s_total_and_s_classifications(self):
        html = self._tpl(
            "summary_stats",
            "{% if s_total %}{{ s_total }}-{{ s_classifications.0.label }}{% endif %}",
        )
        self.assertIn("2", html)  # 2 patients in test data

    def test_ctx_cost_breakdown_provides_c_mode(self):
        html = self._tpl("cost_breakdown", "{% if c_mode %}{{ c_mode }}{% endif %}")
        self.assertIn("per_field", html)

    def test_template_autoescapes_user_data(self):
        self.p1.full_name = "<script>alert(1)</script>"
        self.p1.save()
        html = BodyBuilder.render(
            "clinical_detail_table",
            build_report_dataset(self.cep),
            {},
            {},
            body_html="{% for row in d_rows %}{{ row.cells.3.text }}{% endfor %}",
        )
        self.assertNotIn("<script>", html)

    def test_template_blocks_dangerous_tags(self):
        for source in [
            '{% include "admin/base.html" %}',
            "{% load static %}",
            '{% extends "admin/base.html" %}',
        ]:
            with self.assertRaises(TemplateRenderError):
                BodyBuilder.render(
                    "summary_stats",
                    build_report_dataset(self.cep),
                    {},
                    {},
                    body_html=source,
                )


@override_settings(CLINIC_INFO=CLINIC)
class ReportTemplateModelTests(ReportTemplateTestBase):
    def test_only_one_default_per_report_type(self):
        a = ReportTemplate.objects.create(
            name="A", report_type="clinical_detail", is_default=True
        )
        b = ReportTemplate.objects.create(
            name="B", report_type="clinical_detail", is_default=True
        )
        a.refresh_from_db()
        self.assertFalse(a.is_default)
        self.assertTrue(b.is_default)

    def test_default_is_scoped_per_report_type(self):
        a = ReportTemplate.objects.create(
            name="A", report_type="clinical_detail", is_default=True
        )
        ReportTemplate.objects.create(name="B", report_type="cost", is_default=True)
        a.refresh_from_db()
        self.assertTrue(a.is_default)

    def test_item_resolves_department_from_template(self):
        dept_tpl = DepartmentReportTemplate.objects.create(
            name="X", department=self.lab, body_html=""
        )
        template = ReportTemplate.objects.create(
            name="C", report_type="clinical_detail"
        )
        item = ReportTemplateItem.objects.create(
            report_template=template, department_template=dept_tpl
        )
        self.assertEqual(item.resolved_department_id, self.lab.id)

    def test_item_rejects_exam_template_from_other_department(self):
        from django.core.exceptions import ValidationError

        dept_tpl = DepartmentReportTemplate.objects.create(
            name="Y", department=self.lab, body_html=""
        )
        template = ReportTemplate.objects.create(
            name="D", report_type="clinical_detail"
        )
        item = ReportTemplateItem(
            report_template=template,
            department_template=dept_tpl,
            exam_template=self.tpl_clinical,  # belongs to `clinical`, not `lab`
        )
        with self.assertRaises(ValidationError):
            item.clean()


@override_settings(CLINIC_INFO=CLINIC)
class OrphanedItemGuardTests(ReportTemplateTestBase):
    """
    Attaching department templates to a body_type that ignores them used to
    fail silently: rows saved, body rendered without them, no warning.
    """

    def setUp(self) -> None:
        self.dept_tpl = DepartmentReportTemplate.objects.create(
            name="Probe", department=self.lab, body_html="<i>PROBE_MARKER</i>"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def _template(self, body_type, with_item=True):
        t = ReportTemplate.objects.create(
            name=f"T-{body_type}", report_type="clinical_detail", body_type=body_type
        )
        if with_item:
            ReportTemplateItem.objects.create(
                report_template=t, department_template=self.dept_tpl, order=0
            )
        return t

    # -- model helper ------------------------------------------------------

    def test_orphaned_count_zero_for_department_templates(self):
        t = self._template(ReportTemplate.BODY_DEPARTMENT_TEMPLATES)
        self.assertTrue(t.uses_department_templates)
        self.assertEqual(t.orphaned_item_count(), 0)
        self.assertFalse(t.has_orphaned_items)

    def test_orphaned_count_flags_other_body_types(self):
        t = self._template(ReportTemplate.BODY_CLINICAL_DETAIL_TABLE)
        self.assertFalse(t.uses_department_templates)
        self.assertEqual(t.orphaned_item_count(), 1)
        self.assertTrue(t.has_orphaned_items)

    def test_orphaned_count_zero_when_no_items(self):
        t = self._template(ReportTemplate.BODY_SUMMARY_STATS, with_item=False)
        self.assertEqual(t.orphaned_item_count(), 0)

    def test_orphaned_count_safe_on_unsaved_instance(self):
        self.assertEqual(ReportTemplate().orphaned_item_count(), 0)

    # -- the underlying behaviour being guarded ----------------------------

    def test_items_really_are_dropped_by_other_body_types(self):
        ds = build_report_dataset(self.cep)
        rendered = self._template(ReportTemplate.BODY_DEPARTMENT_TEMPLATES)
        ignored = self._template(ReportTemplate.BODY_CLINICAL_DETAIL_TABLE)
        self.assertIn("PROBE_MARKER", render_report(rendered, ds))
        self.assertNotIn("PROBE_MARKER", render_report(ignored, ds))

    def test_render_logs_warning_for_orphaned_items(self):
        t = self._template(ReportTemplate.BODY_CLINICAL_DETAIL_TABLE)
        with self.assertLogs("reports.render", level="WARNING") as logs:
            render_report(t, build_report_dataset(self.cep))
        self.assertTrue(
            any("does not render" in line for line in logs.output), logs.output
        )

    def test_render_does_not_warn_when_consistent(self):
        t = self._template(ReportTemplate.BODY_DEPARTMENT_TEMPLATES)
        with self.assertNoLogs("reports.render", level="WARNING"):
            render_report(t, build_report_dataset(self.cep))

    # -- API guard --------------------------------------------------------

    def test_api_rejects_items_on_wrong_body_type(self):
        resp = self.client.post(
            "/api/report-templates/",
            {
                "name": "API mismatch",
                "report_type": "clinical_detail",
                "body_type": "clinical_detail_table",
                "items": [{"department_template": str(self.dept_tpl.id), "order": 0}],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("items", resp.data)
        self.assertFalse(ReportTemplate.objects.filter(name="API mismatch").exists())

    def test_api_allows_items_on_department_templates(self):
        resp = self.client.post(
            "/api/report-templates/",
            {
                "name": "API ok",
                "report_type": "clinical_detail",
                "body_type": "department_templates",
                "items": [{"department_template": str(self.dept_tpl.id), "order": 0}],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(ReportTemplate.objects.get(name="API ok").items.count(), 1)

    def test_api_rejects_switching_body_type_away_with_items_present(self):
        t = self._template(ReportTemplate.BODY_DEPARTMENT_TEMPLATES)
        resp = self.client.patch(
            f"/api/report-templates/{t.id}/",
            {"body_type": "summary_stats"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("body_type", resp.data)
        t.refresh_from_db()
        self.assertEqual(t.body_type, ReportTemplate.BODY_DEPARTMENT_TEMPLATES)

    def test_api_allows_switching_body_type_after_clearing_items(self):
        t = self._template(ReportTemplate.BODY_DEPARTMENT_TEMPLATES)
        resp = self.client.patch(
            f"/api/report-templates/{t.id}/",
            {"body_type": "summary_stats", "items": []},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        t.refresh_from_db()
        self.assertEqual(t.body_type, "summary_stats")
        self.assertEqual(t.items.count(), 0)

    def test_api_allows_body_type_change_when_no_items(self):
        t = self._template(ReportTemplate.BODY_DEPARTMENT_TEMPLATES, with_item=False)
        resp = self.client.patch(
            f"/api/report-templates/{t.id}/",
            {"body_type": "cost_breakdown"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)

    def test_api_rejects_body_html_on_department_templates(self):
        """body_html is only rendered by coded types, not department_templates."""
        t = self._template(ReportTemplate.BODY_DEPARTMENT_TEMPLATES)
        resp = self.client.patch(
            f"/api/report-templates/{t.id}/",
            {"body_html": "<p>WASTED</p>"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("body_html", resp.data)
        t.refresh_from_db()
        self.assertEqual(t.body_html, "")

    def test_api_allows_body_html_on_coded_body_type(self):
        """body_html is accepted for non-department_templates body types."""
        t = self._template(ReportTemplate.BODY_CLINICAL_DETAIL_TABLE, with_item=False)
        resp = self.client.patch(
            f"/api/report-templates/{t.id}/",
            {"body_html": "<p>VALID</p>"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        t.refresh_from_db()
        self.assertEqual(t.body_html, "<p>VALID</p>")

    def test_wastes_body_html_flags_misconfiguration(self):
        t = self._template(ReportTemplate.BODY_DEPARTMENT_TEMPLATES)
        self.assertFalse(t.wastes_body_html)
        t.body_html = "<p>x</p>"
        t.save()
        self.assertTrue(t.wastes_body_html)

    def test_admin_help_warns_about_wasted_body_html(self):
        dept_tpl = DepartmentReportTemplate.objects.create(
            name="W", department=self.lab, body_html=""
        )
        t = ReportTemplate.objects.create(
            name="Wasted",
            report_type="clinical_detail",
            body_type=ReportTemplate.BODY_DEPARTMENT_TEMPLATES,
            body_html="<p>CONTENT_THAT_WILL_BE_IGNORED</p>",
        )
        ReportTemplateItem.objects.create(
            report_template=t, department_template=dept_tpl, order=0
        )
        html = (
            self._admin_client()
            .get(f"/admin/reports/reporttemplate/{t.id}/change/")
            .content.decode()
        )
        self.assertIn("KHÔNG xuất hiện", html)
        self.assertIn("CONTENT_THAT_WILL_BE_IGNORED", html)
        t.delete()

    def test_api_forwards_exam_template_on_items(self):
        """Regression: _sync_items used to drop exam_template silently."""
        resp = self.client.post(
            "/api/report-templates/",
            {
                "name": "API pin",
                "report_type": "clinical_detail",
                "body_type": "department_templates",
                "items": [
                    {
                        "department_template": str(self.dept_tpl.id),
                        "department": str(self.lab.id),
                        "exam_template": str(self.tpl_blood.id),
                        "order": 0,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        item = ReportTemplate.objects.get(name="API pin").items.get()
        self.assertEqual(item.exam_template_id, self.tpl_blood.id)

    # -- admin guard ------------------------------------------------------

    def _admin_payload(self, body_type, dept_template_id=""):
        """Minimal management-form payload for the ReportTemplate change view."""
        return {
            "name": "Admin probe",
            "description": "",
            "report_type": "clinical_detail",
            "body_type": body_type,
            "body_config": "{}",
            "extra_css": "",
            "page_size": ReportTemplate.PAGE_A4_PORTRAIT,
            "is_default": "",
            "is_active": "on",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-id": "",
            "items-0-report_template": "",
            "items-0-department_template": dept_template_id,
            "items-0-department": "",
            "items-0-exam_template": "",
            "items-0-order": "0",
        }

    def test_admin_form_rejects_items_on_wrong_body_type(self):
        self.admin.is_staff = True
        self.admin.is_superuser = True
        self.admin.save()
        client = APIClient()
        client.force_login(self.admin)

        resp = client.post(
            "/admin/reports/reporttemplate/add/",
            self._admin_payload("clinical_detail_table", str(self.dept_tpl.id)),
        )
        # Re-renders the form with the error rather than redirecting on success.
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(ReportTemplate.objects.filter(name="Admin probe").exists())

    def test_admin_form_accepts_items_on_department_templates(self):
        self.admin.is_staff = True
        self.admin.is_superuser = True
        self.admin.save()
        client = APIClient()
        client.force_login(self.admin)

        resp = client.post(
            "/admin/reports/reporttemplate/add/",
            self._admin_payload("department_templates", str(self.dept_tpl.id)),
        )
        self.assertEqual(resp.status_code, 302, getattr(resp, "content", b"")[:600])
        self.assertEqual(
            ReportTemplate.objects.get(name="Admin probe").items.count(), 1
        )

    def test_admin_form_accepts_other_body_type_without_items(self):
        self.admin.is_staff = True
        self.admin.is_superuser = True
        self.admin.save()
        client = APIClient()
        client.force_login(self.admin)

        resp = client.post(
            "/admin/reports/reporttemplate/add/",
            self._admin_payload("summary_stats", ""),
        )
        self.assertEqual(resp.status_code, 302, getattr(resp, "content", b"")[:600])
        self.assertTrue(ReportTemplate.objects.filter(name="Admin probe").exists())

    def test_admin_changelist_flags_orphaned_items(self):
        self.admin.is_staff = True
        self.admin.is_superuser = True
        self.admin.save()
        self._template(ReportTemplate.BODY_CLINICAL_DETAIL_TABLE)
        client = APIClient()
        client.force_login(self.admin)
        resp = client.get("/admin/reports/reporttemplate/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("khoa bị bỏ qua", resp.content.decode())

    def test_admin_preview_shows_warning_banner(self):
        self.admin.is_staff = True
        self.admin.is_superuser = True
        self.admin.save()
        t = self._template(ReportTemplate.BODY_CLINICAL_DETAIL_TABLE)
        client = APIClient()
        client.force_login(self.admin)
        resp = client.get(f"/admin/reports/reporttemplate/{t.id}/preview/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("template khoa không được render", resp.content.decode())

    def _admin_client(self):
        self.admin.is_staff = True
        self.admin.is_superuser = True
        self.admin.save()
        client = APIClient()
        client.force_login(self.admin)
        return client

    def test_admin_change_form_shows_body_type_above_letterhead(self):
        """
        body_type decides whether the items inline renders, so it must sit in
        the first fieldset above the letterhead uploads.
        """
        t = self._template(ReportTemplate.BODY_DEPARTMENT_TEMPLATES)
        html = (
            self._admin_client()
            .get(f"/admin/reports/reporttemplate/{t.id}/change/")
            .content.decode()
        )

        body_type_at = html.find('id="id_body_type"')
        header_at = html.find('id="id_header_xlsx"')
        footer_at = html.find('id="id_footer_xlsx"')

        self.assertNotEqual(body_type_at, -1, "body_type field missing from form")
        self.assertNotEqual(header_at, -1, "header_xlsx field missing from form")
        self.assertNotEqual(footer_at, -1, "footer_xlsx field missing from form")
        self.assertLess(body_type_at, header_at)
        self.assertLess(body_type_at, footer_at)

    def test_admin_change_form_renders_inline_before_layout(self):
        """
        The Report template items inline sits above the layout fieldset so it
        is reachable without scrolling past the letterhead uploads.
        Django only renders inlines after ALL fieldsets, so the change form
        template splits the fieldset loop around the inline.
        """
        t = self._template(ReportTemplate.BODY_DEPARTMENT_TEMPLATES)
        html = (
            self._admin_client()
            .get(f"/admin/reports/reporttemplate/{t.id}/change/")
            .content.decode()
        )

        inline_at = html.find("items-TOTAL_FORMS")
        layout_at = html.find(">Bố cục<")
        header_at = html.find('id="id_header_xlsx"')

        self.assertNotEqual(inline_at, -1, "items inline missing from form")
        self.assertNotEqual(layout_at, -1, "layout fieldset missing")
        self.assertNotEqual(header_at, -1, "header fieldset missing")
        # Header/footer are above the inline, layout is below it.
        self.assertLess(header_at, inline_at, "header must come before inline")
        self.assertLess(inline_at, layout_at, "inline must come before layout")

    def test_admin_change_form_inline_rows_are_editable(self):
        """The inline must render its add button and per-row widgets."""
        t = self._template(ReportTemplate.BODY_DEPARTMENT_TEMPLATES)
        html = (
            self._admin_client()
            .get(f"/admin/reports/reporttemplate/{t.id}/change/")
            .content.decode()
        )

        self.assertIn("Add another", html)
        self.assertIn("items-0-department_template", html)
        self.assertIn("items-0-order", html)

    def test_admin_change_form_lists_all_body_type_options(self):
        t = self._template(ReportTemplate.BODY_DEPARTMENT_TEMPLATES)
        html = (
            self._admin_client()
            .get(f"/admin/reports/reporttemplate/{t.id}/change/")
            .content.decode()
        )
        for value, _label in ReportTemplate.BODY_TYPE_CHOICES:
            self.assertIn(f'value="{value}"', html)

    def test_admin_help_row_reports_attached_count(self):
        t = self._template(ReportTemplate.BODY_DEPARTMENT_TEMPLATES)
        html = (
            self._admin_client()
            .get(f"/admin/reports/reporttemplate/{t.id}/change/")
            .content.decode()
        )
        self.assertIn("Đang ghép", html)
        self.assertIn("Report template items", html)

    def test_admin_help_row_warns_on_mismatch(self):
        t = self._template(ReportTemplate.BODY_CLINICAL_DETAIL_TABLE)
        html = (
            self._admin_client()
            .get(f"/admin/reports/reporttemplate/{t.id}/change/")
            .content.decode()
        )
        self.assertIn("KHÔNG xuất hiện trong báo cáo", html)

    def test_admin_add_form_renders_body_type_hint(self):
        html = (
            self._admin_client()
            .get("/admin/reports/reporttemplate/add/")
            .content.decode()
        )
        self.assertIn('id="id_body_type"', html)
        self.assertIn("Ghép template theo khoa", html)


@override_settings(CLINIC_INFO=CLINIC)
class TemplateAPITests(ReportTemplateTestBase):
    def setUp(self) -> None:
        self.client = APIClient()

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def test_admin_can_create_report_template(self):
        self._auth(self.admin)
        resp = self.client.post(
            "/api/report-templates/",
            {
                "name": "API tạo",
                "report_type": "clinical_detail",
                "body_type": "clinical_detail_table",
                "body_config": {"highlight_abnormal": True},
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(ReportTemplate.objects.filter(name="API tạo").exists())

    def test_nurse_cannot_create_but_can_list(self):
        self._auth(self.nurse)
        self.assertEqual(
            self.client.get("/api/report-templates/").status_code, status.HTTP_200_OK
        )
        resp = self.client.post(
            "/api/report-templates/",
            {"name": "Nope", "report_type": "clinical_detail"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_invalid_body_html_syntax_rejected(self):
        self._auth(self.admin)
        resp = self.client.post(
            "/api/report-templates/",
            {
                "name": "Bad",
                "report_type": "clinical_detail",
                "body_html": "{% for x in %}",
                "body_type": "clinical_detail_table",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("body_html", resp.data)

    def test_blocked_tag_rejected_by_api(self):
        self._auth(self.admin)
        resp = self.client.post(
            "/api/report-templates/",
            {
                "name": "Bad2",
                "report_type": "clinical_detail",
                "body_html": '{% include "admin/base.html" %}',
                "body_type": "clinical_detail_table",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_body_type_rejected(self):
        self._auth(self.admin)
        resp = self.client.post(
            "/api/report-templates/",
            {"name": "Bad3", "report_type": "clinical_detail", "body_type": "zzz"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_variables_endpoint_lists_shortcodes(self):
        self._auth(self.admin)
        resp = self.client.get("/api/report-templates/variables/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("groups", resp.data)
        tokens = [v["token"] for g in resp.data["groups"] for v in g["variables"]]
        self.assertIn("{{ clinic_name }}", tokens)
        self.assertIn("{{ field.is_abnormal }}", tokens)

    def test_preview_with_sample_data(self):
        self._auth(self.admin)
        template = ReportTemplate.objects.create(
            name="P",
            report_type="clinical_detail",
            body_type="clinical_detail_table",
            body_html="<h1>{{ company.name }}</h1>",
        )
        resp = self.client.post(
            f"/api/report-templates/{template.id}/preview/",
            {"output_format": "html"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("CÔNG TY MẪU ABC", resp.content.decode())

    def test_preview_with_real_data(self):
        self._auth(self.admin)
        template = ReportTemplate.objects.create(
            name="P2",
            report_type="clinical_detail",
            body_type="clinical_detail_table",
        )
        resp = self.client.post(
            f"/api/report-templates/{template.id}/preview/",
            {
                "company_id": str(self.company.id),
                "exam_package_id": str(self.package.id),
                "output_format": "html",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        body = resp.content.decode()
        self.assertIn("Nguyễn Văn An", body)

    def test_preview_accepts_unsaved_body_override(self):
        self._auth(self.admin)
        template = ReportTemplate.objects.create(
            name="P3",
            report_type="clinical_detail",
            body_type="clinical_detail_table",
            body_html="",
        )
        resp = self.client.post(
            f"/api/report-templates/{template.id}/preview/",
            {"body_html": "<h9>CHUA LUU</h9>", "output_format": "html"},
            format="json",
        )
        self.assertIn("<h9>CHUA LUU</h9>", resp.content.decode())
        template.refresh_from_db()
        self.assertEqual(template.body_html, "")

    def test_department_template_preview(self):
        self._auth(self.admin)
        dept_tpl = DepartmentReportTemplate.objects.create(
            name="DT", department=self.lab, body_html="<u>{{ department.name }}</u>"
        )
        resp = self.client.post(
            f"/api/department-report-templates/{dept_tpl.id}/preview/",
            {
                "company_id": str(self.company.id),
                "exam_package_id": str(self.package.id),
                "output_format": "html",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("<u>Xét nghiệm</u>", resp.content.decode())

    def test_spec_alias_routes_resolve(self):
        """/api/templates/report/ must not be shadowed by DepartmentTemplateViewSet."""
        self._auth(self.admin)
        resp = self.client.get("/api/templates/report/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        resp = self.client.get("/api/templates/department/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_examinations_templates_route_still_works(self):
        self._auth(self.admin)
        resp = self.client.get("/api/templates/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


@override_settings(CLINIC_INFO=CLINIC, CELERY_TASK_ALWAYS_EAGER=True)
class GenerateReportTests(ReportTemplateTestBase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def _run(self, **kwargs) -> Report:
        from reports.tasks import generate_report_task

        report = Report.objects.create(
            company=self.company,
            parameters={
                "exam_package_id": str(self.package.id),
                "exam_date": None,
            },
            created_by=self.admin,
            **kwargs,
        )
        generate_report_task(str(report.id))
        report.refresh_from_db()
        return report

    def test_template_path_produces_html(self):
        template = ReportTemplate.objects.create(
            name="HTML",
            report_type="clinical_detail",
            body_type="clinical_detail_table",
            body_html="<p>{{ company.name }}</p>",
        )
        report = self._run(
            report_type="clinical_detail", output_format="html", template=template
        )
        self.assertEqual(report.status, Report.STATUS_DONE, report.error_message)
        self.assertTrue(report.file.name.endswith(".html"))
        with report.file.open("rb") as fh:
            body = fh.read().decode("utf-8")
        self.assertIn("Công ty ABC", body)
        self.assertNotIn('class="report-header"', body)

    def test_legacy_excel_fallback_without_template(self):
        report = self._run(
            report_type="clinical_detail", output_format="xlsx", template=None
        )
        self.assertEqual(report.status, Report.STATUS_DONE, report.error_message)
        self.assertTrue(report.file.name.endswith(".xlsx"))
        self.assertIsNone(report.template)

    def test_html_without_template_fails_with_clear_message(self):
        report = self._run(
            report_type="clinical_detail", output_format="html", template=None
        )
        self.assertEqual(report.status, Report.STATUS_FAILED)
        self.assertIn("template", report.error_message.lower())

    def test_filename_is_ascii_safe(self):
        template = ReportTemplate.objects.create(
            name="F", report_type="clinical_detail", body_type="clinical_detail_table"
        )
        report = self._run(
            report_type="clinical_detail", output_format="html", template=template
        )
        self.assertTrue(report.file.name.isascii())

    def test_generate_endpoint_accepts_template_id(self):
        template = ReportTemplate.objects.create(
            name="Via API",
            report_type="clinical_detail",
            body_type="clinical_detail_table",
        )
        resp = self.client.post(
            "/api/reports/generate/",
            {
                "company_id": str(self.company.id),
                "exam_package_id": str(self.package.id),
                "report_type": "clinical_detail",
                "output_format": "html",
                "template_id": str(template.id),
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["template"], template.id)

    def test_generate_endpoint_falls_back_to_default_template(self):
        template = ReportTemplate.objects.create(
            name="Default",
            report_type="clinical_detail",
            body_type="clinical_detail_table",
            is_default=True,
        )
        resp = self.client.post(
            "/api/reports/generate/",
            {
                "company_id": str(self.company.id),
                "exam_package_id": str(self.package.id),
                "report_type": "clinical_detail",
                "output_format": "html",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data["template"], template.id)

    def test_excel_output_never_auto_selects_a_template(self):
        ReportTemplate.objects.create(
            name="Default2",
            report_type="clinical_detail",
            body_type="clinical_detail_table",
            is_default=True,
        )
        resp = self.client.post(
            "/api/reports/generate/",
            {
                "company_id": str(self.company.id),
                "exam_package_id": str(self.package.id),
                "report_type": "clinical_detail",
                "output_format": "xlsx",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIsNone(resp.data["template"])

    def test_excel_with_explicit_template_is_accepted(self):
        template = ReportTemplate.objects.create(
            name="X", report_type="clinical_detail", body_type="clinical_detail_table"
        )
        resp = self.client.post(
            "/api/reports/generate/",
            {
                "company_id": str(self.company.id),
                "exam_package_id": str(self.package.id),
                "report_type": "clinical_detail",
                "output_format": "xlsx",
                "template_id": str(template.id),
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_html_output_requires_a_template(self):
        resp = self.client.post(
            "/api/reports/generate/",
            {
                "company_id": str(self.company.id),
                "exam_package_id": str(self.package.id),
                "report_type": "clinical_detail",
                "output_format": "html",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_excel_company_summary_auto_selects_default_template(self):
        template = ReportTemplate.objects.create(
            name="Default summary",
            report_type="company_summary",
            body_type="summary_stats",
            is_default=True,
        )
        resp = self.client.post(
            "/api/reports/generate/",
            {
                "company_id": str(self.company.id),
                "exam_package_id": str(self.package.id),
                "report_type": "company_summary",
                "output_format": "xlsx",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data["template"], template.id)

    def test_excel_company_summary_without_template_returns_400(self):
        resp = self.client.post(
            "/api/reports/generate/",
            {
                "company_id": str(self.company.id),
                "exam_package_id": str(self.package.id),
                "report_type": "company_summary",
                "output_format": "xlsx",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("template", resp.data["error"].lower())

    def test_generate_enqueues_after_commit(self):
        from unittest.mock import patch

        with patch("reports.tasks.generate_report_task.delay") as delay:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                resp = self.client.post(
                    "/api/reports/generate/",
                    {
                        "company_id": str(self.company.id),
                        "exam_package_id": str(self.package.id),
                        "report_type": "clinical_detail",
                        "output_format": "xlsx",
                    },
                    format="json",
                )
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
            delay.assert_not_called()
            self.assertEqual(len(callbacks), 1)
            callbacks[0]()
            delay.assert_called_once_with(resp.data["id"])

    def test_missing_report_is_skipped(self):
        import uuid

        from reports.tasks import generate_report_task

        generate_report_task(str(uuid.uuid4()))


class SeedCommandTests(ReportTemplateTestBase):
    def test_seed_creates_templates_and_is_idempotent(self):
        from io import StringIO

        from django.core.management import call_command

        call_command("seed_report_templates", stdout=StringIO())
        first = ReportTemplate.objects.count()
        self.assertGreater(first, 0)
        self.assertTrue(
            DepartmentReportTemplate.objects.filter(name="Bảng XN máu dọc").exists()
        )

        call_command("seed_report_templates", stdout=StringIO())
        self.assertEqual(ReportTemplate.objects.count(), first)

    def test_seeded_templates_render(self):
        from io import StringIO

        from django.core.management import call_command

        call_command("seed_report_templates", stdout=StringIO())
        ds = build_report_dataset(self.cep)
        for template in ReportTemplate.objects.all():
            with self.subTest(template=template.name):
                html = render_report(template, ds)
                self.assertIn("<!DOCTYPE html>", html)


@override_settings(CLINIC_INFO=CLINIC, CELERY_TASK_ALWAYS_EAGER=True)
class ExcelLetterheadMergeTests(ReportTemplateTestBase):
    """Static .xlsx header/footer merge into generated Excel reports."""

    def setUp(self) -> None:
        import tempfile

        from django.test import override_settings

        self._media = tempfile.mkdtemp()
        self._settings_cm = override_settings(MEDIA_ROOT=self._media)
        self._settings_cm.enable()
        self.addCleanup(self._settings_cm.disable)

    def _xlsx_content(self, fill) -> "ContentFile":
        from io import BytesIO

        from django.core.files.base import ContentFile
        from openpyxl import Workbook

        wb = Workbook()
        fill(wb.active)
        buf = BytesIO()
        wb.save(buf)
        return ContentFile(buf.getvalue(), name="fragment.xlsx")

    def test_apply_letterhead_copies_cells_styles_and_merges(self):
        import tempfile
        from pathlib import Path

        from openpyxl import Workbook, load_workbook
        from openpyxl.styles import Alignment, Font

        from reports.xlsx_letterhead import apply_letterhead

        def build_header(ws):
            ws["A1"] = "HEADER CLINIC"
            ws["A1"].font = Font(bold=True, size=16)
            ws.merge_cells("A1:C1")
            ws["A1"].alignment = Alignment(horizontal="center")
            ws["A2"] = "Sub line"

        def build_footer(ws):
            ws["A1"] = "FOOTER SIGN"
            ws["A1"].font = Font(italic=True)

        with tempfile.TemporaryDirectory() as tmp:
            header_path = Path(tmp) / "header.xlsx"
            footer_path = Path(tmp) / "footer.xlsx"
            hw = Workbook()
            build_header(hw.active)
            hw.save(header_path)
            fw = Workbook()
            build_footer(fw.active)
            fw.save(footer_path)

            body = Workbook()
            body.active["A1"] = "BODY_START"
            body.active["A2"] = "BODY_END"
            merged_wb = apply_letterhead(body, header_path, footer_path)
            ws = merged_wb.active

            self.assertEqual(ws["A1"].value, "HEADER CLINIC")
            self.assertTrue(ws["A1"].font.bold)
            self.assertEqual(ws["A2"].value, "Sub line")
            # blank separator then body
            self.assertEqual(ws["A4"].value, "BODY_START")
            self.assertEqual(ws["A5"].value, "BODY_END")
            # footer after blank row
            self.assertEqual(ws["A7"].value, "FOOTER SIGN")
            self.assertTrue(ws["A7"].font.italic)
            merged = {str(r) for r in ws.merged_cells.ranges}
            self.assertIn("A1:C1", merged)

            # Round-trip save/load preserves values
            out = Path(tmp) / "out.xlsx"
            merged_wb.save(out)
            loaded = load_workbook(out)
            self.assertEqual(loaded.active["A1"].value, "HEADER CLINIC")
            self.assertEqual(loaded.active["A7"].value, "FOOTER SIGN")

    def test_apply_letterhead_honors_header_gap_rows(self):
        import tempfile
        from pathlib import Path

        from openpyxl import Workbook

        from reports.xlsx_letterhead import apply_letterhead

        with tempfile.TemporaryDirectory() as tmp:
            header_path = Path(tmp) / "header.xlsx"
            hw = Workbook()
            hw.active["A1"] = "H1"
            hw.active["A2"] = "H2"
            hw.save(header_path)

            body = Workbook()
            body.active["A1"] = "BODY"
            merged = apply_letterhead(body, header_path, None, header_gap_rows=3)
            ws = merged.active
            # header rows 1-2, then 3 blank → body at row 6
            self.assertEqual(ws["A1"].value, "H1")
            self.assertEqual(ws["A2"].value, "H2")
            self.assertIsNone(ws["A3"].value)
            self.assertIsNone(ws["A4"].value)
            self.assertIsNone(ws["A5"].value)
            self.assertEqual(ws["A6"].value, "BODY")

    def test_parse_excel_header_gap_from_html(self):
        from reports.tasks import (
            DEFAULT_EXCEL_HEADER_GAP_ROWS,
            _letterhead_body_start,
            _parse_excel_header_gap,
        )

        self.assertEqual(_parse_excel_header_gap(""), DEFAULT_EXCEL_HEADER_GAP_ROWS)
        self.assertEqual(_parse_excel_header_gap("<p>hi</p>"), 1)
        self.assertEqual(
            _parse_excel_header_gap('<div data-excel-header-gap="9"></div>'),
            9,
        )
        self.assertEqual(
            _parse_excel_header_gap("<div data-excel-header-gap=0></div>"),
            0,
        )
        self.assertEqual(_letterhead_body_start(2, 1), 4)
        self.assertEqual(_letterhead_body_start(2, 9), 12)
        self.assertEqual(_letterhead_body_start(0, 9), 1)
    def test_apply_letterhead_preserves_header_column_widths(self):
        import tempfile
        from pathlib import Path

        from openpyxl import Workbook
        from openpyxl.utils import get_column_letter

        from reports.xlsx_letterhead import apply_letterhead

        with tempfile.TemporaryDirectory() as tmp:
            header_path = Path(tmp) / "header_w.xlsx"
            hw = Workbook()
            hw.active["A1"] = "H"
            hw.active.merge_cells("A1:C1")
            for i, width in enumerate((11.5, 22.0, 33.0), start=1):
                hw.active.column_dimensions[get_column_letter(i)].width = width
            hw.save(header_path)

            body = Workbook()
            for i in range(1, 6):
                body.active.column_dimensions[get_column_letter(i)].width = 14
            body.active["A1"] = "BODY"
            merged_wb = apply_letterhead(body, header_path, None)
            for i, width in enumerate((11.5, 22.0, 33.0), start=1):
                self.assertAlmostEqual(
                    merged_wb.active.column_dimensions[get_column_letter(i)].width,
                    width,
                    places=4,
                )

    def test_real_summary_header_keeps_two_cell_logo_anchor(self):
        """Uploaded summary header logo/frame must stay TwoCellAnchor after merge."""
        from pathlib import Path

        from openpyxl import Workbook, load_workbook
        from openpyxl.drawing.spreadsheet_drawing import TwoCellAnchor
        from openpyxl.utils import get_column_letter

        from reports.xlsx_letterhead import apply_letterhead

        header_path = Path("documents/sumamry-report-header.xlsx")
        if not header_path.is_file():
            self.skipTest("documents/sumamry-report-header.xlsx not present")

        src = load_workbook(header_path).active
        self.assertTrue(src._images)
        src_anchor = src._images[0].anchor
        self.assertIsInstance(src_anchor, TwoCellAnchor)

        body = Workbook()
        body.active["A1"] = "BODY"
        for i in range(1, 16):
            body.active.column_dimensions[get_column_letter(i)].width = 14
        merged = apply_letterhead(body, header_path, None)
        ws = merged.active
        self.assertTrue(ws._images)
        dest_anchor = ws._images[0].anchor
        self.assertIsInstance(dest_anchor, TwoCellAnchor)
        self.assertEqual(dest_anchor._from.col, src_anchor._from.col)
        self.assertEqual(dest_anchor._from.row, src_anchor._from.row)
        self.assertEqual(dest_anchor.to.col, src_anchor.to.col)
        self.assertEqual(dest_anchor.to.row, src_anchor.to.row)
        self.assertEqual(dest_anchor._from.colOff, src_anchor._from.colOff)
        self.assertEqual(dest_anchor.to.colOff, src_anchor.to.colOff)
        # Body equal widths must not overwrite header column widths.
        self.assertAlmostEqual(ws.column_dimensions["A"].width, 13.0, places=4)
        self.assertEqual(ws["C3"].value, src["C3"].value)

    def test_restore_letterhead_drawings_keeps_group_shapes(self):
        """Grouped frame shapes must survive openpyxl save via zip restore."""
        import zipfile
        from io import BytesIO
        from pathlib import Path

        from openpyxl import Workbook, load_workbook
        from openpyxl.utils import get_column_letter

        from reports.xlsx_letterhead import (
            apply_letterhead,
            restore_letterhead_drawings,
        )

        header_path = Path("documents/sumamry-report-header.xlsx")
        if not header_path.is_file():
            self.skipTest("documents/sumamry-report-header.xlsx not present")

        with zipfile.ZipFile(header_path) as z:
            original_size = z.getinfo("xl/drawings/drawing1.xml").file_size
            original_drawing = z.read("xl/drawings/drawing1.xml")
        self.assertGreater(original_size, 50_000)
        self.assertIn(b"grpSp", original_drawing)

        body = Workbook()
        body.active["A1"] = "BODY"
        for i in range(1, 16):
            body.active.column_dimensions[get_column_letter(i)].width = 14
        merged = apply_letterhead(body, header_path, None)
        buf = BytesIO()
        merged.save(buf)
        raw = restore_letterhead_drawings(buf.getvalue(), header_path)

        with zipfile.ZipFile(BytesIO(raw)) as z:
            restored = z.read("xl/drawings/drawing1.xml")
            self.assertEqual(len(restored), original_size)
            self.assertIn(b"grpSp", restored)
            # Sheet/styles untouched — fonts still load.
            wb2 = load_workbook(BytesIO(raw))
            self.assertEqual(wb2.active["C3"].font.name, "Times New Roman")
            self.assertEqual(wb2.active["C3"].alignment.horizontal, "center")
            self.assertEqual(wb2.active["C4"].font.size, 14.0)

    def test_generate_report_xlsx_merges_uploaded_letterhead(self):
        from openpyxl import load_workbook
        from openpyxl.styles import Font

        from reports.tasks import generate_report_task

        def fill_header(ws):
            ws["A1"] = "LH_HEADER"
            ws["A1"].font = Font(bold=True)

        def fill_footer(ws):
            ws["A1"] = "LH_FOOTER"

        template = ReportTemplate.objects.create(
            name="LH",
            report_type="clinical_detail",
            body_type=ReportTemplate.BODY_CLINICAL_DETAIL_TABLE,
        )
        template.header_xlsx.save(
            "header.xlsx", self._xlsx_content(fill_header), save=True
        )
        template.footer_xlsx.save(
            "footer.xlsx", self._xlsx_content(fill_footer), save=True
        )

        report = Report.objects.create(
            company=self.company,
            report_type="clinical_detail",
            output_format="xlsx",
            template=template,
            parameters={
                "exam_package_id": str(self.package.id),
                "exam_date": None,
            },
            created_by=self.admin,
        )
        generate_report_task(str(report.id))
        report.refresh_from_db()
        self.assertEqual(report.status, Report.STATUS_DONE, report.error_message)

        with report.file.open("rb") as fh:
            wb = load_workbook(fh)
        ws = wb.active
        self.assertEqual(ws["A1"].value, "LH_HEADER")
        self.assertTrue(ws["A1"].font.bold)
        # Footer is the last non-empty value in column A
        last_val = None
        for row in ws.iter_rows(min_col=1, max_col=1, values_only=True):
            if row[0] is not None:
                last_val = row[0]
        self.assertEqual(last_val, "LH_FOOTER")


class TemplateGuideAdminTests(ReportTemplateTestBase):
    def _staff(self):
        self.admin.is_staff = True
        self.admin.is_superuser = True
        self.admin.save()
        client = APIClient()
        client.force_login(self.admin)
        return client

    def test_guide_page_lists_tags_and_variables(self):
        resp = self._staff().get("/admin/reports/reporttemplate/huong-dan/")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn("{% gender_table %}", body)
        self.assertIn("{% dept_chart", body)
        self.assertIn("{{ clinic_name }}", body)
        self.assertIn("{{ stats.total }}", body)
        self.assertIn("Hướng dẫn mã template", body)
        self.assertIn("Thẻ HTML dùng trong template báo cáo", body)
        self.assertIn("Thuộc tính HTML được hỗ trợ", body)
        self.assertIn("Giới hạn khi chuyển HTML sang Excel", body)
        self.assertIn("&lt;table&gt;…&lt;/table&gt;", body)
        self.assertIn("data-column", body)
        self.assertIn("data-width", body)
        self.assertIn("data-row-height", body)
        self.assertIn("Chiều cao hàng Excel", body)
        self.assertIn("data-row-height=&quot;36&quot;", body)
        self.assertIn("data-excel-header-gap", body)
        self.assertIn("Khoảng cách dưới letterhead Excel", body)
        self.assertIn("data-excel-header-gap=&quot;9&quot;", body)
        self.assertIn("data-excel-gap", body)
        self.assertIn("Cách dòng trong body Excel", body)
        self.assertIn("Không lồng table trong table", body)

    def test_guide_appears_on_admin_index(self):
        resp = self._staff().get("/admin/")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn("Hướng dẫn mã template", body)
        self.assertIn("/admin/reports/reporttemplate/huong-dan/", body)

    def test_department_picker_omits_report_level_tags(self):
        from reports.shortcodes import variable_groups_for

        tokens = [
            item["token"]
            for group in variable_groups_for(department=True)
            for item in group["variables"]
        ]
        self.assertIn("{% result_table %}", tokens)
        self.assertIn("{% dept_summary %}", tokens)
        self.assertNotIn("{% gender_table %}", tokens)
        self.assertNotIn("{% narrative_bullets %}", tokens)
