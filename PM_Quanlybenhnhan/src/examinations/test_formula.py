"""Tests for the department-field formula evaluator."""

from __future__ import annotations

from django.test import SimpleTestCase

from examinations.formula_evaluator import evaluate_computed_fields, evaluate_formula
from examinations.models import _to_decimal, is_blank_value


class FormulaEvaluatorTests(SimpleTestCase):
    def test_bmi_admin_example(self) -> None:
        result = evaluate_formula(
            "{weight} / (({height} / 100) ^ 2)",
            {"weight": 70, "height": 170},
        )
        self.assertAlmostEqual(result, 24.22145328719723, places=5)

    def test_leading_equals_sign(self) -> None:
        self.assertEqual(evaluate_formula("={a}+{b}", {"a": 2, "b": 3}), 5.0)

    def test_if_quoted_vietnamese(self) -> None:
        formula = 'IF({bmi}<18.5, "Gầy", IF({bmi}<25, "Bình thường", "Thừa cân"))'
        self.assertEqual(evaluate_formula(formula, {"bmi": 22}), "Bình thường")
        self.assertEqual(evaluate_formula(formula, {"bmi": 17}), "Gầy")
        self.assertEqual(evaluate_formula(formula, {"bmi": 27}), "Thừa cân")

    def test_if_with_space_and_lowercase(self) -> None:
        self.assertEqual(evaluate_formula("if ( {x} > 1, 1, 0 )", {"x": 5}), 1.0)
        self.assertEqual(evaluate_formula("if ( {x} > 1, 1, 0 )", {"x": 0}), 0.0)

    def test_if_unquoted_vietnamese_is_not_zero(self) -> None:
        self.assertEqual(
            evaluate_formula("IF({x}>1, Cao, Thap)", {"x": 2}),
            "Cao",
        )

    def test_missing_field_is_zero(self) -> None:
        self.assertEqual(evaluate_formula("{missing}+1", {}), 1.0)

    def test_computed_fields_resolve_dependencies_out_of_order(self) -> None:
        fields = [
            {
                "key": "classif",
                "order": 1,
                "formula": 'IF({bmi}<25, "Bình thường", "Cao")',
            },
            {
                "key": "bmi",
                "order": 2,
                "formula": "{weight} / (({height} / 100) ^ 2)",
            },
        ]
        result = evaluate_computed_fields(
            fields, {"weight": 70, "height": 170}
        )
        self.assertAlmostEqual(result["bmi"], 24.22)
        self.assertEqual(result["classif"], "Bình thường")


class ComputedValueStorageTests(SimpleTestCase):
    def test_computed_numeric_result_stored_as_number(self) -> None:
        self.assertEqual(_to_decimal(24.22, "computed"), 24.22)
        self.assertEqual(_to_decimal("24.22", "computed"), 24.22)

    def test_computed_text_result_not_coerced(self) -> None:
        self.assertIsNone(_to_decimal("Bình thường", "computed"))


class BlankValueTests(SimpleTestCase):
    def test_none_and_whitespace_and_null_are_blank(self) -> None:
        for value in (None, "", "  ", "null", "NULL", "N/A", "-", "None"):
            self.assertTrue(is_blank_value(value), msg=repr(value))

    def test_zero_and_real_values_are_not_blank(self) -> None:
        for value in (0, 0.0, "0", 12, "12.5", "bình thường"):
            self.assertFalse(is_blank_value(value), msg=repr(value))
