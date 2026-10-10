"""基本面打分缺失因子的诊断透传（方案 b：不补分，只解释为什么没有分）。"""

from backend.app.core_finance.livermore_stock_candidates import (
    _apply_fundamental_overlay,
    _fundamental_missing_inputs,
)


def test_missing_inputs_listed_for_loss_making_row() -> None:
    row = {"pe": None, "pb": 100.24, "ps": 18.39, "roe": None, "gross_margin": 0.074}
    assert _fundamental_missing_inputs(row) == ["pe", "roe"]


def test_missing_inputs_empty_when_all_required_present() -> None:
    row = {"pe": 12.0, "pb": 2.0, "ps": 3.0, "roe": 0.11, "gross_margin": 0.25}
    assert _fundamental_missing_inputs(row) == []


def test_overlay_annotates_missing_rows_without_scoring() -> None:
    items = [
        {"stock_code": "A", "pe": None, "pb": 2.0, "ps": 3.0, "roe": None, "gross_margin": 0.2},
        {"stock_code": "B", "pe": 10.0, "pb": 2.0, "ps": 3.0, "roe": 0.1, "gross_margin": 0.2},
    ]
    out, meta = _apply_fundamental_overlay(items, market_state="NORMAL")
    by_code = {str(row["stock_code"]): row for row in out}

    # 缺因子行：不打分、显式 None、列出缺失因子；仍在结果里不消失。
    assert by_code["A"]["factor_score"] is None
    assert by_code["A"]["factor_missing_inputs"] == ["pe", "roe"]
    # 完整行：正常打分，不携带缺失诊断。
    assert by_code["B"]["factor_score"] is not None
    assert "factor_missing_inputs" not in by_code["B"]
    assert meta["status"] == "applied"
