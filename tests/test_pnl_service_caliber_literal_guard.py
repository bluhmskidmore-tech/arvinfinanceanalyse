# 复核发现：pnl_service.py 中 nonstd 514/516/517 分组曾用裸 "516"/"517" 字符串
# 字面量参与比较，未经 LEDGER_PNL_ACCOUNT_PREFIXES 常量锁定，也没有
# `# Human: caliber-subject_514_516_517_merge-justified` 标记。core_finance/pnl.py
# 对同一三段科目已统一改用常量索引；本测试钉住 pnl_service.py 不再出现裸字面量比较。
from __future__ import annotations

import ast
from pathlib import Path

PNL_SERVICE_PATH = Path(__file__).resolve().parents[1] / "backend" / "app" / "services" / "pnl_service.py"

_BARE_CALIBER_LITERALS = {"516", "517"}


def _bare_literal_compare_line_numbers(source: str) -> list[int]:
    """Line numbers of ``... == "516"`` / ``... == "517"`` comparisons.

    Walks the AST rather than grepping so that the check is immune to the
    literal appearing inside a string that merely mentions it (e.g. an
    identifier like ``fair_value_change_516``), and only flags an actual
    equality comparison against the bare journal-type code.
    """
    tree = ast.parse(source)
    hits: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        operands = [node.left, *node.comparators]
        ops = node.ops
        for op, left, right in zip(ops, operands[:-1], operands[1:]):
            if not isinstance(op, ast.Eq):
                continue
            for side in (left, right):
                if (
                    isinstance(side, ast.Constant)
                    and isinstance(side.value, str)
                    and side.value in _BARE_CALIBER_LITERALS
                ):
                    hits.append(node.lineno)
    return hits


def test_pnl_service_has_no_bare_516_517_journal_type_literal_comparisons():
    source = PNL_SERVICE_PATH.read_text(encoding="utf-8")

    hits = _bare_literal_compare_line_numbers(source)

    assert hits == [], (
        "pnl_service.py 中发现裸 \"516\"/\"517\" journal_type 字面量比较（行号: "
        f"{hits}）；应改为引用 LEDGER_PNL_ACCOUNT_PREFIXES[1]/[2] 派生的模块级常量，"
        "与 backend/app/core_finance/pnl.py 的既有做法一致。"
    )
