"""Tests for the official company-summary stats engine (tables + charts + tags)."""

from __future__ import annotations

from django.test import override_settings

from examinations.models import (
    DepartmentField,
    DepartmentFieldAbnormal,
    DepartmentResult,
)
from reports.charts import pie_chart_svg
from reports.models import DepartmentReportTemplate, ReportTemplate, ReportTemplateItem
from reports.render import build_context, render_fragment, render_report
from reports.report_builder import build_report_dataset
from reports.stats import build_company_stats
from reports.test_dynamic_templates import CLINIC, ReportTemplateTestBase


@override_settings(CLINIC_INFO=CLINIC)
class CompanyStatsTests(ReportTemplateTestBase):
    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        wbc = DepartmentField.objects.get(template=cls.tpl_blood, key="wbc")
        DepartmentFieldAbnormal.objects.create(
            field=wbc, direction="high", label="Bạch cầu tăng"
        )
        hbg = DepartmentField.objects.get(template=cls.tpl_blood, key="hbg")
        DepartmentFieldAbnormal.objects.create(
            field=hbg, direction="low", label="Theo dõi thiếu máu"
        )
        cls.exam1.classification = 2
        cls.exam1.save(update_fields=["classification"])
        cls.exam2.classification = 3
        cls.exam2.save(update_fields=["classification"])
        urine = DepartmentResult.objects.get(
            examination=cls.exam1, template=cls.tpl_urine
        )
        urine._sync_values({"pro": "Dương tính"})
        urine.save()

    def test_demographics_and_classification_split_by_gender(self) -> None:
        stats = build_company_stats(build_report_dataset(self.cep))
        self.assertEqual(stats.total, 2)
        self.assertEqual(stats.male, 1)
        self.assertEqual(stats.female, 1)
        self.assertEqual(stats.male_pct, 50.0)
        labels = {row.label: row for row in stats.classifications}
        self.assertEqual(labels["Sức khỏe loại II"].male, 1)
        self.assertEqual(labels["Sức khỏe loại II"].female, 0)
        self.assertEqual(labels["Sức khỏe loại III"].female, 1)
        self.assertEqual(labels["Sức khỏe loại III"].count, 1)

    def test_groups_follow_package_slots_and_count_people(self) -> None:
        stats = build_company_stats(build_report_dataset(self.cep))
        by_name = {g.name: g for g in stats.groups}
        self.assertIn("XN máu", by_name)
        self.assertIn("XN nước tiểu", by_name)
        self.assertIn("Nội tổng quát", by_name)

        blood = by_name["XN máu"]
        self.assertEqual(blood.kind, "range")
        self.assertEqual(blood.examined, 2)
        self.assertEqual(blood.abnormal, 2)
        self.assertEqual(
            {d.name for d in blood.diseases}, {"Bạch cầu tăng", "Theo dõi thiếu máu"}
        )
        self.assertTrue(all(d.count == 1 for d in blood.diseases))

        clinical = by_name["Nội tổng quát"]
        self.assertEqual(clinical.examined, 2)
        self.assertEqual(clinical.abnormal, 0)
        self.assertEqual(clinical.diseases, [])

        urine = by_name["XN nước tiểu"]
        self.assertEqual(urine.kind, "serology")
        self.assertEqual(urine.examined, 1)
        self.assertEqual(urine.abnormal, 1)
        self.assertEqual(urine.diseases[0].name, "Protein niệu")

    def test_tags_render_tables_and_charts(self) -> None:
        ds = build_report_dataset(self.cep)
        context = build_context(ds)
        html = render_fragment(
            "{% gender_table %}{% classification_table %}"
            "{% group_overview_table %}{% narrative_bullets %}",
            context,
        )
        self.assertIn("CBCNV Nam", html)
        self.assertIn("Sức khỏe loại II", html)
        self.assertIn("XN máu", html)
        self.assertIn("Số lượng khám", html)
        self.assertIn(
            "data-chart", render_fragment("{% classification_chart %}", context)
        )

    def test_per_department_composite_renders_one_block_per_slot(self) -> None:
        cover = DepartmentReportTemplate.objects.create(
            name="Cover stats",
            body_html="<h1>Bìa</h1>{% gender_table %}",
        )
        per_dept = DepartmentReportTemplate.objects.create(
            name="Per slot",
            body_html="<h2>{{ department.template_name }}</h2>{% dept_summary %}",
            config={"iterate_departments": True},
        )
        closing = DepartmentReportTemplate.objects.create(
            name="Closing",
            body_html="{% narrative_bullets %}",
        )
        template = ReportTemplate.objects.create(
            name="Official summary",
            report_type="company_summary",
            body_type=ReportTemplate.BODY_DEPARTMENT_TEMPLATES,
            body_config={"per_patient": False, "per_department": True},
        )
        for order, dept_tpl in enumerate((cover, per_dept, closing)):
            ReportTemplateItem.objects.create(
                report_template=template,
                department_template=dept_tpl,
                order=order,
            )
        html = render_report(template, build_report_dataset(self.cep))
        self.assertEqual(html.count("<h1>Bìa</h1>"), 1)
        self.assertEqual(html.count("<h2>XN máu</h2>"), 1)
        self.assertEqual(html.count("<h2>XN nước tiểu</h2>"), 1)
        self.assertEqual(html.count("<h2>Nội tổng quát</h2>"), 1)
        self.assertIn("Số lượng khám", html)

    def test_seeded_summary_cover_matches_official_sections(self) -> None:
        from reports.management.commands.seed_report_templates import (
            BODY_DEPT_SUMMARY,
            BODY_SUMMARY_COVER,
        )

        cover = DepartmentReportTemplate.objects.create(
            name="Official cover seeded",
            body_html=BODY_SUMMARY_COVER,
        )
        per_dept = DepartmentReportTemplate.objects.create(
            name="Official per dept seeded",
            body_html=BODY_DEPT_SUMMARY,
            config={"iterate_departments": True},
        )
        template = ReportTemplate.objects.create(
            name="Official summary seeded",
            report_type="company_summary",
            body_type=ReportTemplate.BODY_DEPARTMENT_TEMPLATES,
            body_config={"per_patient": False, "per_department": True},
        )
        for order, dept_tpl in enumerate((cover, per_dept)):
            ReportTemplateItem.objects.create(
                report_template=template,
                department_template=dept_tpl,
                order=order,
            )
        html = render_report(template, build_report_dataset(self.cep))
        self.assertIn("I. TÌNH HÌNH SỨC KHỎE CHUNG", html)
        self.assertIn("Bảng 1.1: Số CBNV đăng ký khám", html)
        self.assertIn("II. BẢNG PHÂN LOẠI SỨC KHỎE", html)
        self.assertIn("Bảng 2.1: Bảng phân loại sức khỏe của CBNV", html)
        self.assertIn("III. TÌNH HÌNH BỆNH TẬT", html)
        self.assertIn(
            "Bảng 3.0: Tỷ lệ bình thường và bất thường theo từng nhóm khám", html
        )
        self.assertIn("Biểu đồ thể hiện tỉ lệ phân loại sức khỏe CBNV", html)
        self.assertIn("Biểu đồ thể hiện tỷ lệ theo từng nhóm bệnh", html)
        self.assertIn("Bảng 3.2: Phân loại bệnh lý XN máu", html)
        self.assertIn("data-chart", html)
        self.assertIn("Tổng số người khám", html)

        from reports.tasks import (
            COMPANY_SUMMARY_EXCEL_COLUMNS,
            _html_document_to_excel,
        )

        _raw, chart_specs = _html_document_to_excel(
            html, layout_columns=COMPANY_SUMMARY_EXCEL_COLUMNS
        )
        self.assertIn(12, [spec["start_col"] for spec in chart_specs])
        self.assertIn(11, [spec["start_col"] for spec in chart_specs])
        self.assertIn(10, [spec["start_col"] for spec in chart_specs])

    def test_seeded_summary_uses_configurable_excel_grid(self) -> None:
        from reports.management.commands.seed_report_templates import (
            BODY_DEPT_SUMMARY,
            BODY_SUMMARY_COVER,
        )

        self.assertIn('data-column="4" data-width="8"', BODY_SUMMARY_COVER)
        self.assertIn('data-column="12" data-width="4"', BODY_SUMMARY_COVER)
        self.assertIn("{% classification_table %}", BODY_SUMMARY_COVER)
        self.assertIn("{% classification_chart %}", BODY_SUMMARY_COVER)
        self.assertIn('data-column="1" data-width="9"', BODY_DEPT_SUMMARY)
        self.assertIn('data-column="10" data-width="6"', BODY_DEPT_SUMMARY)
        self.assertNotIn("summary-split", BODY_SUMMARY_COVER)
        self.assertNotIn("summary-split", BODY_DEPT_SUMMARY)

    def test_pie_chart_survives_a_single_slice(self) -> None:
        svg = pie_chart_svg([("Tất cả", 100)], "Full")
        self.assertIn("<svg", svg)
        self.assertIn("circle", svg)


@override_settings(CLINIC_INFO=CLINIC)
class AbnormalLabelDatasetTests(ReportTemplateTestBase):
    def test_abnormal_label_comes_from_field_definition(self) -> None:
        wbc = DepartmentField.objects.get(template=self.tpl_blood, key="wbc")
        DepartmentFieldAbnormal.objects.create(
            field=wbc, direction="high", label="Bạch cầu tăng"
        )
        ds = build_report_dataset(self.cep)
        blood = next(
            d
            for d in ds.patients[0].departments
            if d.template_id == str(self.tpl_blood.id)
        )
        wbc_field = blood.field("wbc")
        assert wbc_field is not None
        self.assertTrue(wbc_field.is_abnormal)
        self.assertEqual(wbc_field.abnormal_label, "Bạch cầu tăng")


@override_settings(CLINIC_INFO=CLINIC)
class CompanySummaryExcelLayoutTests(ReportTemplateTestBase):
    def test_html_to_excel_uses_fixed_15_columns_and_stretches_tables(self) -> None:
        from io import BytesIO

        from openpyxl import load_workbook

        from reports.tasks import COMPANY_SUMMARY_EXCEL_COLUMNS, _html_document_to_excel

        html = (
            "<html><body>"
            "<h2>BÁO CÁO TỔNG HỢP</h2>"
            "<table><thead><tr><th>Nội dung</th><th>Tổng số</th><th>Tỷ lệ</th></tr></thead>"
            "<tbody><tr><td>Nam</td><td>1</td><td>50</td></tr></tbody></table>"
            "</body></html>"
        )
        raw, _specs = _html_document_to_excel(
            html, layout_columns=COMPANY_SUMMARY_EXCEL_COLUMNS
        )
        ws = load_workbook(BytesIO(raw)).active

        # Title spans the full 15-column grid (A…O).
        title_merge = next(
            m for m in ws.merged_cells.ranges if m.min_row == 1 and m.min_col == 1
        )
        self.assertEqual(title_merge.max_col, 15)

        # 3-column table → spans 5+5+5 across A…O.
        self.assertEqual(ws.cell(2, 1).value, "Nội dung")
        self.assertEqual(ws.cell(2, 6).value, "Tổng số")
        self.assertEqual(ws.cell(2, 11).value, "Tỷ lệ")
        self.assertIn("A2:E2", {str(m) for m in ws.merged_cells.ranges})
        self.assertIn("F2:J2", {str(m) for m in ws.merged_cells.ranges})
        self.assertIn("K2:O2", {str(m) for m in ws.merged_cells.ranges})

    def test_html_to_excel_embeds_openpyxl_charts_from_data_chart(self) -> None:
        from html import escape
        from io import BytesIO
        import json

        from openpyxl import load_workbook
        from openpyxl.chart import BarChart, PieChart

        from reports.tasks import _html_document_to_excel, _parse_html_to_blocks

        pie = {
            "type": "pie",
            "title": "Phân loại sức khỏe",
            "items": [
                {"label": "Loại I", "value": 10},
                {"label": "Loại II", "value": 5},
            ],
        }
        bar = {
            "type": "bar",
            "title": "Giới tính",
            "items": [
                {"label": "Nam", "value": 12},
                {"label": "Nữ", "value": 8},
            ],
        }
        html = (
            "<html><body>"
            f'<figure class="report-chart" data-chart="{escape(json.dumps(pie, ensure_ascii=False), quote=True)}">'
            "<h4>Phân loại sức khỏe</h4>"
            '<div class="chart-body"><svg><path d="M0 0"/></svg></div>'
            "</figure>"
            f'<figure class="report-chart" data-chart="{escape(json.dumps(bar, ensure_ascii=False), quote=True)}">'
            "<h4>Giới tính</h4>"
            '<div class="chart-body"><svg></svg></div>'
            "</figure>"
            "</body></html>"
        )

        blocks = _parse_html_to_blocks(html)
        self.assertEqual([b["type"] for b in blocks], ["chart", "chart"])
        self.assertEqual(blocks[0]["payload"]["type"], "pie")
        self.assertEqual(blocks[1]["payload"]["type"], "bar")

        ws = load_workbook(BytesIO(_html_document_to_excel(html)[0])).active
        self.assertEqual(len(ws._charts), 2)
        self.assertIsInstance(ws._charts[0], PieChart)
        self.assertIsInstance(ws._charts[1], BarChart)
        self.assertEqual(ws._charts[0].title.tx.rich.p[0].r[0].t, "Phân loại sức khỏe")
        # Source data parked off-grid (col 20+) and hidden from the 15-col body.
        self.assertEqual(ws.cell(1, 20).value, "label")
        self.assertEqual(ws.cell(2, 20).value, "Loại I")
        self.assertEqual(ws.cell(2, 21).value, 10)

    def test_report_row_places_table_and_chart_side_by_side(self) -> None:
        import json
        from html import escape
        from io import BytesIO

        from openpyxl import load_workbook

        from reports.tasks import COMPANY_SUMMARY_EXCEL_COLUMNS, _html_document_to_excel

        chart = {
            "type": "pie",
            "title": "Phân loại sức khỏe",
            "items": [
                {"label": "Loại I", "value": 10},
                {"label": "Loại II", "value": 5},
            ],
        }
        html = (
            "<html><body><h2>Phân loại</h2>"
            '<div class="report-row">'
            '<div class="report-grid-item" data-column="4" data-width="8">'
            "<table><tr><th>Loại</th><th>Nam</th><th>Nữ</th><th>Tổng</th><th>Tỷ lệ</th></tr>"
            "<tr><td>I</td><td>5</td><td>5</td><td>10</td><td>66.7</td></tr></table>"
            "</div>"
            '<div class="report-grid-item" data-column="12" data-width="4">'
            f'<figure class="report-chart" data-chart="{escape(json.dumps(chart), quote=True)}">'
            '<div class="chart-body"></div></figure>'
            "</div></div>"
            "<p>Sau bố cục</p></body></html>"
        )

        raw, specs = _html_document_to_excel(
            html, layout_columns=COMPANY_SUMMARY_EXCEL_COLUMNS
        )
        ws = load_workbook(BytesIO(raw)).active

        self.assertEqual(ws.cell(2, 4).value, "Loại")
        self.assertEqual(ws.cell(2, 6).value, "Nam")
        self.assertIn("D2:E2", {str(m) for m in ws.merged_cells.ranges})
        self.assertEqual(len(ws._charts), 1)
        self.assertEqual(ws._charts[0].anchor._from.col, 11)
        self.assertEqual(ws._charts[0].anchor._from.row, 1)
        self.assertEqual(specs[0]["start_col"], 12)
        self.assertEqual(specs[0]["span"], 4)
        self.assertEqual(ws.cell(16, 1).value, "Sau bố cục")

    def test_report_row_rejects_overflow_and_overlap(self) -> None:
        from reports.tasks import COMPANY_SUMMARY_EXCEL_COLUMNS, _html_document_to_excel

        overflow = (
            '<div class="report-row">'
            '<div data-column="12" data-width="5"><table><tr><td>X</td></tr></table></div>'
            "</div>"
        )
        with self.assertRaisesRegex(ValueError, "vượt quá lưới 15"):
            _html_document_to_excel(
                overflow, layout_columns=COMPANY_SUMMARY_EXCEL_COLUMNS
            )

        overlap = (
            '<div class="report-row">'
            '<div data-column="4" data-width="8"><table><tr><td>A</td></tr></table></div>'
            '<div data-column="10" data-width="4"><table><tr><td>B</td></tr></table></div>'
            "</div>"
        )
        with self.assertRaisesRegex(ValueError, "chồng cột"):
            _html_document_to_excel(
                overlap, layout_columns=COMPANY_SUMMARY_EXCEL_COLUMNS
            )

        same_cell = (
            '<div class="report-row">'
            '<div class="report-grid-item" data-column="3" data-width="7">'
            "<p>Bảng 1.1</p></div>"
            '<div class="report-grid-item" data-column="3" data-width="7">'
            "<table><tr><td>Nam</td></tr></table></div>"
            "</div>"
        )
        with self.assertRaisesRegex(ValueError, "chồng cột"):
            _html_document_to_excel(
                same_cell, layout_columns=COMPANY_SUMMARY_EXCEL_COLUMNS
            )

    def test_html_to_excel_applies_row_height_from_tr_and_text(self) -> None:
        from io import BytesIO

        from openpyxl import load_workbook

        from reports.tasks import (
            _html_document_to_excel,
            _parse_html_to_blocks,
            _parse_row_height,
        )

        self.assertEqual(_parse_row_height({"data-row-height": "30"}), 30.0)
        self.assertEqual(_parse_row_height({"style": "height: 40px"}), 30.0)
        self.assertEqual(
            _parse_row_height({"style": "min-height: 22pt; color: red"}), 22.0
        )
        self.assertIsNone(_parse_row_height({"style": "height: 0pt"}))

        html = (
            "<html><body>"
            '<p style="height:18pt">Tiêu đề</p>'
            "<table>"
            '<tr style="height: 28pt"><th>A</th><th>B</th></tr>'
            '<tr data-row-height="36"><td>1</td><td>2</td></tr>'
            "</table>"
            "</body></html>"
        )
        blocks = _parse_html_to_blocks(html)
        self.assertEqual(blocks[0]["height"], 18.0)
        self.assertEqual(getattr(blocks[1]["rows"][0], "height"), 28.0)
        self.assertEqual(getattr(blocks[1]["rows"][1], "height"), 36.0)

        ws = load_workbook(BytesIO(_html_document_to_excel(html)[0])).active
        self.assertEqual(ws.row_dimensions[1].height, 18.0)
        self.assertEqual(ws.row_dimensions[2].height, 28.0)
        self.assertEqual(ws.row_dimensions[3].height, 36.0)

    def test_html_to_excel_applies_paragraph_font_outside_report_grid(self) -> None:
        """Standalone ``<p style>`` must keep font-size / bold / align, not only grid items."""
        from io import BytesIO

        from openpyxl import load_workbook

        from reports.tasks import _html_document_to_excel, _parse_html_to_blocks

        html = (
            "<html><body>"
            '<p data-row-height="22pt" style="font-size: 12pt;">Ninh Bình, 20/09/2026</p>'
            '<p data-row-height="22pt" style="font-weight: bold;">'
            "<strong>Kính gửi: CÔNG TY</strong></p>"
            '<p data-row-height="22pt" style="font-size: 12pt;">Kính thưa QUÝ CÔNG TY:</p>'
            '<div class="report-row">'
            '<div class="report-grid-item" data-column="8" data-width="7">'
            '<p style="font-weight: bold; text-align: center; font-size: 12pt;">'
            "<strong>Trân trọng kính chào</strong></p>"
            "</div></div>"
            "</body></html>"
        )
        blocks = _parse_html_to_blocks(html)
        self.assertEqual(blocks[0]["size"], 12)
        self.assertFalse(blocks[0]["bold"])
        self.assertEqual(blocks[1]["bold"], True)
        self.assertEqual(blocks[2]["size"], 12)
        self.assertEqual(blocks[3]["size"], 12)
        self.assertEqual(blocks[3]["bold"], True)
        self.assertEqual(blocks[3]["align"], "center")

        ws = load_workbook(BytesIO(_html_document_to_excel(html)[0])).active
        self.assertEqual(ws.cell(1, 1).value, "Ninh Bình, 20/09/2026")
        self.assertEqual(ws.cell(1, 1).font.size, 12)
        self.assertFalse(ws.cell(1, 1).font.bold)
        self.assertEqual(ws.cell(2, 1).font.bold, True)
        self.assertEqual(ws.cell(2, 1).font.size, 12)
        self.assertEqual(ws.cell(3, 1).font.size, 12)
        greeting = ws.cell(4, 8)
        self.assertEqual(greeting.value, "Trân trọng kính chào")
        self.assertEqual(greeting.font.size, 12)
        self.assertEqual(greeting.font.bold, True)
        self.assertEqual(greeting.alignment.horizontal, "center")

    def test_html_to_excel_inserts_data_excel_gap_rows(self) -> None:
        from io import BytesIO

        from openpyxl import load_workbook

        from reports.tasks import _html_document_to_excel, _parse_html_to_blocks

        html = (
            "<p>Trước</p>"
            '<div data-excel-gap="1"></div>'
            "<p>Sau div</p>"
            '<h2 data-excel-gap="2">II. PHÂN LOẠI</h2>'
        )
        blocks = _parse_html_to_blocks(html)
        types = [b["type"] for b in blocks]
        self.assertEqual(types, ["text", "gap", "text", "gap", "text"])
        self.assertEqual(blocks[1]["rows"], 1)
        self.assertEqual(blocks[3]["rows"], 2)

        ws = load_workbook(BytesIO(_html_document_to_excel(html)[0])).active
        self.assertEqual(ws.cell(1, 1).value, "Trước")
        self.assertIsNone(ws.cell(2, 1).value)
        self.assertEqual(ws.cell(3, 1).value, "Sau div")
        self.assertIsNone(ws.cell(4, 1).value)
        self.assertIsNone(ws.cell(5, 1).value)
        self.assertEqual(ws.cell(6, 1).value, "II. PHÂN LOẠI")

    def test_html_to_excel_defaults_table_font_size_to_12pt(self) -> None:
        from io import BytesIO

        from openpyxl import load_workbook

        from reports.tasks import _html_document_to_excel

        html = "<table><tr><th>Nội dung</th><th>Tổng</th></tr><tr><td>Nam</td><td>1</td></tr></table>"
        ws = load_workbook(BytesIO(_html_document_to_excel(html)[0])).active
        self.assertEqual(ws.cell(1, 1).font.size, 12)
        self.assertEqual(ws.cell(2, 1).font.size, 12)

    def test_charts_survive_letterhead_drawing_restore(self) -> None:
        """Letterhead restore must keep frames AND re-inject body charts."""
        import zipfile
        from html import escape
        from io import BytesIO
        import json
        from pathlib import Path

        from openpyxl import load_workbook

        from reports.tasks import _html_document_to_excel, _letterhead_body_start
        from reports.xlsx_letterhead import (
            apply_letterhead,
            embed_charts_preserving_drawings,
            fragment_row_count,
            restore_letterhead_drawings,
        )

        header_path = Path("media/report_templates/headers/sumamry-report-header.xlsx")
        if not header_path.is_file():
            header_path = Path("documents/sumamry-report-header.xlsx")
        self.assertTrue(header_path.is_file(), "letterhead sample missing")

        pie = {
            "type": "pie",
            "title": "Phân loại",
            "items": [
                {"label": "I", "value": 10},
                {"label": "II", "value": 5},
            ],
        }
        html = (
            "<html><body><h2>Body</h2>"
            f'<figure class="report-chart" data-chart="{escape(json.dumps(pie), quote=True)}">'
            '<h4>Phân loại</h4><div class="chart-body"></div></figure>'
            "</body></html>"
        )
        body_bytes, chart_specs = _html_document_to_excel(html)
        self.assertEqual(len(chart_specs), 1)

        header_rows = fragment_row_count(header_path)
        body_start = _letterhead_body_start(header_rows, 1)
        offset = body_start - 1

        wb = load_workbook(BytesIO(body_bytes))
        wb = apply_letterhead(wb, str(header_path), None)
        sheet_title = wb.worksheets[0].title
        out = BytesIO()
        wb.save(out)
        merged = out.getvalue()
        merged = restore_letterhead_drawings(merged, str(header_path))

        # After restore, charts are gone (drawing replaced by letterhead).
        with zipfile.ZipFile(BytesIO(merged)) as z:
            self.assertFalse(any(n.startswith("xl/charts/") for n in z.namelist()))
            # Sheet must actually reference the restored drawing — otherwise
            # Excel never shows frames or later-injected charts.
            rels_name = next(
                n
                for n in z.namelist()
                if n.startswith("xl/worksheets/_rels/") and n.endswith(".rels")
            )
            self.assertIn("relationships/drawing", z.read(rels_name).decode())
            self.assertIn("<drawing", z.read("xl/worksheets/sheet1.xml").decode())

        shifted = [
            {
                "payload": s["payload"],
                "start_row": s["start_row"] + offset,
            }
            for s in chart_specs
        ]
        final = embed_charts_preserving_drawings(
            merged, shifted, sheet_title=sheet_title
        )

        with zipfile.ZipFile(BytesIO(final)) as z:
            names = z.namelist()
            self.assertTrue(any(n.startswith("xl/charts/") for n in names))
            drawing = z.read("xl/drawings/drawing1.xml").decode()
            self.assertIn("graphicFrame", drawing)
            self.assertIn("chart", drawing)
            # Letterhead uses xdr: prefixes; injected from/col must match or
            # Excel silently drops the chart. ElementTree may add xmlns attrs
            # on the opening tag (``<xdr:oneCellAnchor xmlns:…>``).
            self.assertIn("xdr:oneCellAnchor", drawing)
            self.assertIn("<xdr:col>", drawing)
            self.assertNotRegex(drawing, r"<xdr:from>\s*<col>")
            # Letterhead frame/logo still present (grpSp or pic).
            self.assertTrue("grpSp" in drawing or "pic" in drawing)
            rels = z.read("xl/drawings/_rels/drawing1.xml.rels").decode()
            self.assertIn("relationships/chart", rels)
            self.assertIn("relationships/image", rels)
            sheet_rels = z.read(
                next(
                    n
                    for n in names
                    if n.startswith("xl/worksheets/_rels/") and n.endswith(".rels")
                )
            ).decode()
            self.assertIn("relationships/drawing", sheet_rels)
            self.assertIn("<drawing", z.read("xl/worksheets/sheet1.xml").decode())
            self.assertIn(
                "/xl/drawings/drawing1.xml", z.read("[Content_Types].xml").decode()
            )

        # Chart part is in the package and hooked up; openpyxl may still skip
        # it when the letterhead drawing contains grpSp / AlternateContent.

    def test_rewrite_chart_anchor_prefixes_from_children(self) -> None:
        from reports.xlsx_letterhead import _rewrite_chart_anchor

        fragment = (
            "<oneCellAnchor><from><col>0</col><colOff>0</colOff>"
            "<row>4</row><rowOff>0</rowOff></from>"
            '<ext cx="5040000" cy="2880000" />'
            "<graphicFrame><nvGraphicFramePr>"
            '<cNvPr id="1" name="Chart 1" /><cNvGraphicFramePr />'
            "</nvGraphicFramePr><xfrm />"
            '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/chart">'
            '<c:chart r:id="rId1" /></a:graphicData></a:graphic>'
            "</graphicFrame><clientData /></oneCellAnchor>"
        )
        out = _rewrite_chart_anchor(
            fragment, uses_xdr=True, new_rid="rId5", shape_id=42
        )
        self.assertIn("<xdr:from>", out)
        self.assertIn("<xdr:col>0</xdr:col>", out)
        self.assertIn("<xdr:row>4</xdr:row>", out)
        self.assertNotIn("<from><col>", out)
        self.assertIn('r:id="rId5"', out)
        self.assertIn('id="42"', out)
        self.assertIn("<a:off", out)

    def test_company_summary_export_preserves_header_widths(self) -> None:
        import tempfile
        from io import BytesIO

        from django.core.files.base import ContentFile
        from django.test import override_settings
        from openpyxl import Workbook, load_workbook
        from openpyxl.utils import get_column_letter

        from reports.models import Report
        from reports.tasks import generate_report_task

        media = tempfile.mkdtemp()
        with override_settings(MEDIA_ROOT=media):
            cover = DepartmentReportTemplate.objects.create(
                name="Cover xlsx",
                body_html="<h1>{{ company.name }}</h1>{% gender_table %}",
            )
            template = ReportTemplate.objects.create(
                name="Summary xlsx layout",
                report_type="company_summary",
                body_type=ReportTemplate.BODY_DEPARTMENT_TEMPLATES,
                body_config={"per_patient": False, "per_department": True},
            )
            ReportTemplateItem.objects.create(
                report_template=template, department_template=cover, order=0
            )

            header_wb = Workbook()
            hws = header_wb.active
            hws["A1"] = "HEADER"
            hws.merge_cells("A1:D1")
            header_widths = (10, 20, 30, 40)
            for i, width in enumerate(header_widths, start=1):
                hws.column_dimensions[get_column_letter(i)].width = width
            buf = BytesIO()
            header_wb.save(buf)
            template.header_xlsx.save(
                "header.xlsx", ContentFile(buf.getvalue()), save=True
            )

            report = Report.objects.create(
                company=self.company,
                report_type="company_summary",
                output_format="xlsx",
                template=template,
                parameters={"exam_package_id": str(self.package.id)},
                created_by=self.admin,
            )
            generate_report_task(str(report.id))
            report.refresh_from_db()
            self.assertEqual(report.status, Report.STATUS_DONE, report.error_message)

            with report.file.open("rb") as fh:
                ws = load_workbook(fh).active

            # Uploaded header widths must survive body merge (not equalized).
            for i, width in enumerate(header_widths, start=1):
                self.assertAlmostEqual(
                    ws.column_dimensions[get_column_letter(i)].width,
                    width,
                    places=4,
                )
            self.assertEqual(ws["A1"].value, "HEADER")
            # Body still stretches across the fixed 15-column grid.
            body_merges = [
                m
                for m in ws.merged_cells.ranges
                if m.min_row >= 3 and m.min_col == 1 and m.max_col == 15
            ]
            self.assertTrue(body_merges)
