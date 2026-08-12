# 2026-08 审计 NaN 防线（P1+P2）：
# - 正式 PnL 链 pnl._coerce_decimal / pnl_source_service._to_decimal 对 NaN/Inf/坏字符串
#   必须 fail-loud，禁止 Decimal("NaN") 静默流入事实行并污染 × fx_rate 求和；
# - 负债分析兼容链 liability_analytics_compat.to_decimal 宽松归 0（沿用共享
#   decimal_utils.to_decimal 语义），不得让 NaN 透传进 defaultdict 聚合。
from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.core_finance.liability_analytics_compat import to_decimal as compat_to_decimal
from backend.app.core_finance.pnl import _coerce_decimal, normalize_fi_pnl_records
from backend.app.services.pnl_source_service import _to_decimal

NON_FINITE_INPUTS = [
    float("nan"),
    float("inf"),
    float("-inf"),
    Decimal("NaN"),
    Decimal("Infinity"),
    Decimal("-Infinity"),
    # "nan"/"inf" 字符串能被 Decimal 构造成功，必须同样设防。
    "nan",
    "inf",
]


# ---------------------------------------------------------------------------
# 正式链 1：pnl._coerce_decimal（fail-loud）
# ---------------------------------------------------------------------------


def test_pnl_coerce_decimal_keeps_clean_inputs_unchanged():
    assert _coerce_decimal(Decimal("12.5")) == Decimal("12.5")
    assert _coerce_decimal("-3.25") == Decimal("-3.25")
    assert _coerce_decimal(100) == Decimal("100")
    assert _coerce_decimal(1.5) == Decimal("1.5")
    assert _coerce_decimal(Decimal("0")) == Decimal("0")


@pytest.mark.parametrize("bad", NON_FINITE_INPUTS)
def test_pnl_coerce_decimal_rejects_non_finite(bad):
    with pytest.raises(ValueError):
        _coerce_decimal(bad)


def test_pnl_coerce_decimal_rejects_none_with_clear_error():
    # 旧实现 None 抛晦涩的 InvalidOperation；新实现抛清晰 TypeError（无调用方依赖 None→0）。
    with pytest.raises(TypeError):
        _coerce_decimal(None)


def test_pnl_coerce_decimal_rejects_bad_string_with_value_context():
    with pytest.raises(ValueError, match="abc"):
        _coerce_decimal("abc")


def test_normalize_fi_pnl_records_fails_loud_on_nan_amount():
    # 端到端：NaN 进入正式事实行构建（fair_value_change_516）必须抛错，
    # 而不是构造 Decimal("NaN") 后经 × fx_rate 求和静默污染 total_pnl。
    row = {
        "report_date": "2025-12-31",
        "instrument_code": "240001.IB",
        "portfolio_name": "FI Desk",
        "cost_center": "CC100",
        "invest_type_raw": "交易性金融资产",
        "asset_class": "国债",
        "interest_income_514": Decimal("10.00"),
        "fair_value_change_516": float("nan"),
        "currency_basis": "CNY",
    }
    with pytest.raises(ValueError):
        normalize_fi_pnl_records([row])


def test_normalize_fi_pnl_records_clean_row_unchanged():
    # 干净输入零回归：金额与 total_pnl 与旧实现完全一致。
    [record] = normalize_fi_pnl_records(
        [
            {
                "report_date": "2025-12-31",
                "instrument_code": "240001.IB",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "invest_type_raw": "交易性金融资产",
                "asset_class": "国债",
                "interest_income_514": Decimal("10.00"),
                "fair_value_change_516": Decimal("-3.25"),
                "capital_gain_517": Decimal("1.75"),
                "manual_adjustment": Decimal("0.50"),
                "currency_basis": "CNY",
            }
        ]
    )
    assert record.interest_income_514 == Decimal("10.00")
    assert record.fair_value_change_516 == Decimal("-3.25")
    assert record.capital_gain_517 == Decimal("1.75")
    assert record.manual_adjustment == Decimal("0.50")
    assert record.total_pnl == Decimal("9.00")


# ---------------------------------------------------------------------------
# 正式链 2：pnl_source_service._to_decimal（空单元格归 0 + 其余 fail-loud）
# ---------------------------------------------------------------------------


def test_pnl_source_to_decimal_keeps_empty_cell_zero_semantics():
    # 调用点（金额/AMOUNT 回退、空单元格）显式依赖 None/"" → 0，必须保留。
    assert _to_decimal(None) == Decimal("0")
    assert _to_decimal("") == Decimal("0")


def test_pnl_source_to_decimal_keeps_clean_inputs_unchanged():
    assert _to_decimal("12.5") == Decimal("12.5")
    assert _to_decimal(-3.25) == Decimal("-3.25")
    assert _to_decimal(Decimal("7")) == Decimal("7")
    assert _to_decimal(0) == Decimal("0")


@pytest.mark.parametrize("bad", NON_FINITE_INPUTS)
def test_pnl_source_to_decimal_rejects_non_finite(bad):
    with pytest.raises(ValueError):
        _to_decimal(bad)


def test_pnl_source_to_decimal_rejects_bad_string_with_value_context():
    with pytest.raises(ValueError, match="abc"):
        _to_decimal("abc")


# ---------------------------------------------------------------------------
# 分析链：liability_analytics_compat.to_decimal（宽松归 0，不透传 NaN）
# ---------------------------------------------------------------------------


def test_liability_compat_to_decimal_keeps_empty_and_clean_semantics():
    assert compat_to_decimal(None) == Decimal("0")
    assert compat_to_decimal("") == Decimal("0")
    assert compat_to_decimal("2.5") == Decimal("2.5")
    assert compat_to_decimal(Decimal("3.75")) == Decimal("3.75")
    assert compat_to_decimal(100) == Decimal("100")


@pytest.mark.parametrize("bad", [*NON_FINITE_INPUTS, "abc"])
def test_liability_compat_to_decimal_coerces_bad_inputs_to_finite_zero(bad):
    # 旧实现：NaN/Inf 透传、坏字符串抛未捕获 InvalidOperation；
    # 新实现沿用共享宽松版：归 0（共享版记一次性告警）。
    result = compat_to_decimal(bad)
    assert result.is_finite()
    assert result == Decimal("0")


def test_liability_compat_to_decimal_nan_no_longer_poisons_aggregation():
    # P2 缺陷复现：defaultdict 累加场景，单个 NaN 不得污染整体聚合。
    total = Decimal("0")
    for value in (Decimal("100"), float("nan"), "50"):
        total += compat_to_decimal(value)
    assert total == Decimal("150")
