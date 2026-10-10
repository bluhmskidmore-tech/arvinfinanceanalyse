"""API 层禁止出现金融公式 token 的边界守卫。

扫描前会剥离 import 语句以及经 import 绑定进来的名字（如 ``KRDAttributionEnvelope``）：
schema 类型名只是被引用的类型，不是在 API 层实现的公式，按原文匹配会产生误报
（2026-09-02 系统审计 A1）。文件无法解析时回退到全文扫描（fail-closed）。
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "backend" / "app" / "api"
FORBIDDEN_TOKENS = (
    "DV01",
    "KRD",
    "CS01",
    "convexity",
    "FVTPL",
    "FVOCI",
    "债券月均金额",
    "formal PnL",
)


def _strip_imported_names(text: str) -> str:
    """删掉 import 语句所在行，并把 import 绑定的标识符（含 ``as`` 别名）整词移除。

    只剥离通过 import 引入的名字：schema 类型名不是 API 层实现的公式（2026-09-02 系统审计 A1）。
    源码无法解析时原样返回，让后续 token 扫描按全文进行（fail-closed）。
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text

    bound_names: set[str] = set()
    import_line_ranges: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        end_lineno = node.end_lineno if node.end_lineno is not None else node.lineno
        import_line_ranges.append((node.lineno, end_lineno))
        for alias in node.names:
            if alias.name == "*":
                continue
            bound = alias.asname if alias.asname is not None else alias.name.split(".")[0]
            bound_names.add(bound)

    lines = text.splitlines()
    skip_lines: set[int] = set()
    for start, end in import_line_ranges:
        skip_lines.update(range(start, end + 1))
    remaining = "\n".join(
        line for lineno, line in enumerate(lines, start=1) if lineno not in skip_lines
    )

    if bound_names:
        pattern = re.compile(
            r"\b(?:" + "|".join(re.escape(name) for name in sorted(bound_names, key=len, reverse=True)) + r")\b"
        )
        remaining = pattern.sub("", remaining)
    return remaining


def find_forbidden_tokens(text: str) -> list[str]:
    """返回源码（剥离 import 名后）中命中的禁用 token 列表。"""
    scannable = _strip_imported_names(text)
    return [token for token in FORBIDDEN_TOKENS if token in scannable]


def test_api_layer_does_not_contain_finance_formula_tokens():
    if not API_DIR.exists():
        raise AssertionError(f"Missing API directory: {API_DIR}")

    py_files = list(API_DIR.rglob("*.py"))
    assert py_files, "Expected at least one Python file under backend/app/api"

    violations: list[str] = []
    for path in py_files:
        text = path.read_text(encoding="utf-8")
        for token in find_forbidden_tokens(text):
            violations.append(f"{path}: {token}")

    assert not violations, "Finance logic leaked into API layer:\n" + "\n".join(violations)


def test_finance_token_guard_still_detects_formula_after_import_stripping():
    """自检：剥离导入名后公式 token 仍被检出；仅有 schema 类型名的导入不再误报。"""
    # 词表匹配区分大小写，公式变量沿用词表写法 "DV01"。
    leaking_source = (
        "from x import KRDAttributionEnvelope\n"
        "\n"
        "def handler(market_value: float) -> float:\n"
        "    total_DV01 = market_value * 0.0001\n"
        "    return total_DV01\n"
    )
    assert "DV01" in find_forbidden_tokens(leaking_source)
    assert "KRD" not in find_forbidden_tokens(leaking_source)

    import_only_source = (
        "from backend.app.schemas.pnl_attribution import KRDAttributionEnvelope\n"
        "\n"
        "def handler() -> KRDAttributionEnvelope:\n"
        "    return KRDAttributionEnvelope()\n"
    )
    assert find_forbidden_tokens(import_only_source) == []

    # 未经 import 绑定、直接在 API 层出现的 KRD 名字仍然算泄漏。
    local_definition_source = "class KRDAttributionEnvelope:\n    pass\n"
    assert "KRD" in find_forbidden_tokens(local_definition_source)

    # 无法解析时回退到全文扫描，不能因为语法错误而放行。
    broken_source = "from x import KRDAttributionEnvelope\ndef (:\n"
    assert "KRD" in find_forbidden_tokens(broken_source)


def test_finance_token_guard_has_expected_coverage():
    """Sanity check: the denylist stays meaningful as new terms are added upstream."""
    assert len(FORBIDDEN_TOKENS) >= 6
    assert all(isinstance(t, str) and t.strip() for t in FORBIDDEN_TOKENS)
