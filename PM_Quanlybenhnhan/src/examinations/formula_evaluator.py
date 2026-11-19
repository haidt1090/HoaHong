"""Formula evaluator for computed fields — mirrors frontend formula.ts logic.

Syntax:
    - Field references: {field_key}
    - Basic math: + - * / ^ ( )
    - Conditional: IF(condition, true_value, false_value)
        - Comparisons: < > <= >= = !=
"""

from __future__ import annotations

import math
import re
from decimal import Decimal
from typing import Any

_IF_HEAD = re.compile(r"^IF\s*\(", re.IGNORECASE)
_MATH_CHARS = re.compile(r"[{}+\-*/^()]")


def evaluate_formula(formula: str, data: dict[str, Any]) -> Any:
    """Evaluate a formula expression against a data context."""
    if not formula or not formula.strip():
        return None

    text = formula.strip()
    if text.startswith("="):
        text = text[1:].strip()

    match = _IF_HEAD.match(text)
    if match:
        return _evaluate_if_body(text[match.end() :], data)

    return _evaluate_expression(text, data)


def evaluate_computed_fields(
    fields_config: list[dict[str, Any]],
    data: dict[str, Any],
    gender: str | None = None,
) -> dict[str, Any]:
    """Evaluate all formula fields, including those that depend on each other."""
    from examinations.field_scope import should_seed_field

    updated = dict(data)
    formula_fields = sorted(
        [
            f
            for f in fields_config
            if f.get("formula") and f.get("key") and should_seed_field(f, gender)
        ],
        key=lambda f: f.get("order") or 0,
    )
    if not formula_fields:
        return updated

    for _ in range(len(formula_fields)):
        changed = False
        for field in formula_fields:
            result = _normalize_formula_result(
                evaluate_formula(field["formula"], updated)
            )
            key = field["key"]
            if updated.get(key) != result:
                updated[key] = result
                changed = True
        if not changed:
            break
    return updated


def _normalize_formula_result(result: Any) -> Any:
    if isinstance(result, float):
        if math.isnan(result) or math.isinf(result):
            return 0.0
        return round(result, 2)
    if isinstance(result, Decimal):
        return float(round(result, 2))
    return result


def _evaluate_expression(expr: str, data: dict[str, Any]) -> float:
    """Evaluate a mathematical expression with field references."""
    resolved = _resolve_fields(expr, data)
    return _parse_math(resolved)


def _resolve_fields(expr: str, data: dict[str, Any]) -> str:
    """Replace {field_key} with numeric values from data."""

    def _replacer(match: re.Match) -> str:
        key = match.group(1).strip()
        val = data.get(key)
        if val is None or val == "":
            return "0"
        try:
            return str(float(val))
        except (ValueError, TypeError):
            return "0"

    return re.sub(r"\{([^}]+)\}", _replacer, expr)


def _parse_math(expr: str) -> float:
    """Recursive-descent parser for + - * / ^ ( ) and numbers."""
    tokens = _tokenize(expr)
    if not tokens:
        return 0.0
    result, _ = _expr(tokens, 0)
    return result


def _tokenize(expr: str) -> list[tuple[str, str]]:
    """Tokenize a math expression."""
    tokens: list[tuple[str, str]] = []
    i = 0
    while i < len(expr):
        ch = expr[i]
        if ch.isspace():
            i += 1
            continue
        if ch in "+-*/^()":
            tokens.append(("op", ch))
            i += 1
            continue
        if ch.isdigit() or ch == ".":
            num = ""
            while i < len(expr) and (expr[i].isdigit() or expr[i] == "."):
                num += expr[i]
                i += 1
            tokens.append(("num", num))
            continue
        i += 1
    return tokens


def _expr(tokens: list[tuple[str, str]], pos: int) -> tuple[float, int]:
    """Parse addition/subtraction."""
    left, pos = _term(tokens, pos)
    while pos < len(tokens):
        tp, val = tokens[pos]
        if tp == "op" and val == "+":
            right, pos = _term(tokens, pos + 1)
            left += right
        elif tp == "op" and val == "-":
            right, pos = _term(tokens, pos + 1)
            left -= right
        else:
            break
    return left, pos


def _term(tokens: list[tuple[str, str]], pos: int) -> tuple[float, int]:
    """Parse multiplication/division."""
    left, pos = _power(tokens, pos)
    while pos < len(tokens):
        tp, val = tokens[pos]
        if tp == "op" and val == "*":
            right, pos = _power(tokens, pos + 1)
            left *= right
        elif tp == "op" and val == "/":
            right, pos = _power(tokens, pos + 1)
            left = left / right if right != 0 else 0.0
        else:
            break
    return left, pos


def _power(tokens: list[tuple[str, str]], pos: int) -> tuple[float, int]:
    """Parse exponentiation."""
    left, pos = _factor(tokens, pos)
    while pos < len(tokens):
        tp, val = tokens[pos]
        if tp == "op" and val == "^":
            right, pos = _factor(tokens, pos + 1)
            left = left**right
        else:
            break
    return left, pos


def _factor(tokens: list[tuple[str, str]], pos: int) -> tuple[float, int]:
    """Parse a number, parenthesized expression, or unary minus."""
    if pos >= len(tokens):
        return 0.0, pos
    tp, val = tokens[pos]
    if tp == "num":
        return float(val), pos + 1
    if tp == "op" and val == "(":
        result, pos = _expr(tokens, pos + 1)
        if pos < len(tokens) and tokens[pos] == ("op", ")"):
            pos += 1
        return result, pos
    if tp == "op" and val == "-":
        result, pos = _factor(tokens, pos + 1)
        return -result, pos
    return 0.0, pos + 1


def _evaluate_if_body(inner: str, data: dict[str, Any]) -> Any:
    """Evaluate IF arguments already stripped of the leading IF(."""
    args = _split_if_args(inner)
    if len(args) < 3:
        return None

    condition = args[0].strip()
    true_expr = args[1].strip()
    false_expr = args[2].strip() if len(args) >= 3 else '""'

    cond_result = _evaluate_condition(condition, data)
    return _coerce_if_branch(true_expr if cond_result else false_expr, data)


def _coerce_if_branch(result_expr: str, data: dict[str, Any]) -> Any:
    """Resolve an IF true/false branch: nested IF, quoted/plain string, or math."""
    stripped = result_expr.strip()
    if _IF_HEAD.match(stripped):
        return evaluate_formula(stripped, data)

    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in ('"', "'"):
        return stripped[1:-1]

    try:
        return float(stripped)
    except ValueError:
        pass

    # Unquoted Vietnamese labels (Bình thường) must not be parsed as math → 0.
    if "{" not in stripped and not _MATH_CHARS.search(stripped):
        return stripped

    return evaluate_formula(stripped, data)


def _evaluate_condition(condition: str, data: dict[str, Any]) -> bool:
    """Evaluate a comparison condition."""
    operators = [">=", "<=", "!=", "=", "<", ">"]
    for op in operators:
        idx = condition.find(op)
        if idx != -1:
            left_str = condition[:idx].strip()
            right_str = condition[idx + len(op) :].strip()
            left_val = _resolve_single(left_str, data)
            right_val = _resolve_single(right_str, data)

            if isinstance(left_val, str) and isinstance(right_val, str):
                if op == "=":
                    return left_val == right_val
                if op == "!=":
                    return left_val != right_val
                return False

            try:
                l_num = float(left_val) if left_val != "" else 0.0  # type: ignore[arg-type]
                r_num = float(right_val) if right_val != "" else 0.0  # type: ignore[arg-type]
            except (ValueError, TypeError):
                return False

            if op == "<":
                return l_num < r_num
            if op == ">":
                return l_num > r_num
            if op == "<=":
                return l_num <= r_num
            if op == ">=":
                return l_num >= r_num
            if op == "=":
                return l_num == r_num
            if op == "!=":
                return l_num != r_num

    return bool(_resolve_single(condition, data))


def _resolve_single(expr: str, data: dict[str, Any]) -> Any:
    """Resolve a single value: field reference, number, or string literal."""
    stripped = expr.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        key = stripped[1:-1]
        return data.get(key, 0)
    if stripped.startswith('"') and stripped.endswith('"'):
        return stripped[1:-1]
    if stripped.startswith("'") and stripped.endswith("'"):
        return stripped[1:-1]
    try:
        return float(stripped)
    except ValueError:
        pass
    return stripped


def _split_if_args(text: str) -> list[str]:
    """Split IF arguments by commas, respecting nested parentheses and quotes."""
    args: list[str] = []
    depth = 0
    in_quote = False
    quote_char = ""
    current = ""
    i = 0

    while i < len(text):
        ch = text[i]
        if in_quote:
            current += ch
            if ch == quote_char:
                in_quote = False
        elif ch in ('"', "'"):
            in_quote = True
            quote_char = ch
            current += ch
        elif ch == "(":
            depth += 1
            current += ch
        elif ch == ")":
            depth -= 1
            if depth < 0:
                break
            current += ch
        elif ch == "," and depth == 0:
            args.append(current)
            current = ""
        else:
            current += ch
        i += 1

    if current.strip():
        args.append(current)
    return args
