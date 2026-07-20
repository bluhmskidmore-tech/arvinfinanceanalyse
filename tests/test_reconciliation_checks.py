# 2026-07-19 审计 余额 M-4：reconciliation_checks 全 float 且缺键当 0。
# 修复口径：Decimal 比较 + 缺键/None/NaN 显式标记 missing（breached=True，透出 missing_keys），
# 不得再出现"双侧缺键 0 vs 0 假平"。输出展示值保持 float 兼容既有 payload。
from __future__ import annotations

from decimal import Decimal

from backend.app.core_finance.reconciliation_checks import (
    completeness_check,
    pnl_vs_ledger_diff,
    position_vs_ledger_diff,
)


def _row(checks: list[dict], dimension: str) -> dict:
    return next(row for row in checks if row["dimension"] == dimension)


def test_position_vs_ledger_diff_uses_decimal_comparison_at_threshold_boundary():
    checks = position_vs_ledger_diff(
        {"total_assets": Decimal("100.00"), "total_liabilities": Decimal("40.00"), "net_assets": Decimal("60.00")},
        {"total_assets": Decimal("100.01"), "total_liabilities": Decimal("40.00"), "net_assets": Decimal("60.005")},
        threshold_yuan=Decimal("0.01"),
    )

    assets = _row(checks, "total_assets")
    assert assets["breached"] is True  # |diff| == threshold 应命中（Decimal 精确比较）
    assert assets["diff"] == -0.01
    assert assets["missing_keys"] == []

    net = _row(checks, "net_assets")
    assert net["breached"] is False  # 0.005 < 0.01
    assert net["missing_keys"] == []


def test_position_vs_ledger_diff_marks_missing_keys_instead_of_zero():
    checks = position_vs_ledger_diff(
        {"total_assets": Decimal("100"), "total_liabilities": Decimal("40")},
        {"total_assets": Decimal("100")},
        threshold_yuan=Decimal("0.01"),
    )

    liabilities = _row(checks, "total_liabilities")
    assert liabilities["missing_keys"] == ["ledger"]
    assert liabilities["breached"] is True
    assert liabilities["diff"] is None
    assert liabilities["ledger_value"] is None
    assert liabilities["position_value"] == 40.0

    # 回归：双侧同时缺键时旧实现按 0 vs 0 判 diff=0 假平；现在必须显式 breached。
    net = _row(checks, "net_assets")
    assert net["missing_keys"] == ["position", "ledger"]
    assert net["breached"] is True
    assert net["diff"] is None


def test_position_vs_ledger_diff_treats_nan_as_missing():
    checks = position_vs_ledger_diff(
        {"total_assets": Decimal("NaN"), "total_liabilities": Decimal("40"), "net_assets": Decimal("60")},
        {"total_assets": Decimal("100"), "total_liabilities": Decimal("40"), "net_assets": Decimal("60")},
    )

    assets = _row(checks, "total_assets")
    assert assets["missing_keys"] == ["position"]
    assert assets["breached"] is True


def test_pnl_vs_ledger_diff_decimal_and_missing():
    ok = pnl_vs_ledger_diff(Decimal("123.456"), Decimal("123.450"), threshold_yuan=Decimal("0.01"))
    assert ok["breached"] is False
    assert ok["diff"] == 0.006
    assert ok["missing_keys"] == []

    missing = pnl_vs_ledger_diff(None, Decimal("1"))
    assert missing["missing_keys"] == ["pnl_total"]
    assert missing["breached"] is True
    assert missing["diff"] is None


def test_completeness_check_decimal_and_missing():
    ok = completeness_check(Decimal("7"), Decimal("7"), threshold_yuan=Decimal("0.01"))
    assert ok == {
        "product_category_total": 7.0,
        "pnl_total": 7.0,
        "diff": 0.0,
        "breached": False,
        "missing_keys": [],
    }

    missing = completeness_check(Decimal("7"), None)
    assert missing["missing_keys"] == ["pnl_total"]
    assert missing["breached"] is True
    assert missing["diff"] is None
