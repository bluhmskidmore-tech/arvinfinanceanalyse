"""A5-2 正式链 float 首批 Decimal 化——锁值测试。

在把以下两条正式链路径从 float 运算改为全程 Decimal 之前，先锁定当前数值：

1. ``backend/app/core_finance/campisi.py``
   - 曲线插值 Δ：``benchmark_yield_change_decimal``（改造前：float 相减/除 100 再
     ``Decimal(str(...))`` 回转）
   - 信用利差 Δ：``credit_spread_change_decimal``（改造前：float BP 差 / 10000.0）
   - 组合级 ``campisi_attribution`` totals（真实量级三券组合）
2. ``backend/app/services/risk_scenario_stress_service.py``
   - 利率/信用/流动性冲击损益路径（改造前：``shock_bp = 10.0`` float 字面量、
     ``_numeric_raw -> float``、``-dv01 * shock_bp`` float 乘法）

锁值容差远小于展示精度（yuan 2dp、pct 1–2dp、bp 0dp），同时锁定 display 字符串本身；
若改造引起超出展示精度的数值漂移，这些断言会显式失败而非静默通过。
``_capture_exact()`` 供改造前后全精度对比使用（非测试项）。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from backend.app.core_finance.campisi import (
    benchmark_yield_change_decimal,
    campisi_attribution,
    credit_spread_change_decimal,
)
from backend.app.services.risk_scenario_stress_service import (
    _credit_scenario,
    _liquidity_scenario,
    _rate_scenario,
    _scenario_summary,
)

# ---------------------------------------------------------------------------
# Campisi 真实形状 fixture：6 期限国债百分数曲线 + 3 档信用利差（BP）
# ---------------------------------------------------------------------------

MARKET_START: dict[str, float] = {
    "treasury_1y": 1.42,
    "treasury_3y": 1.58,
    "treasury_5y": 1.68,
    "treasury_7y": 1.81,
    "treasury_10y": 1.91,
    "treasury_30y": 2.19,
    "credit_spread_aaa_3y": 55.32,
    "credit_spread_aa_plus_3y": 68.47,
    "credit_spread_aa_3y": 92.1,
}

MARKET_END: dict[str, float] = {
    "treasury_1y": 1.47,
    "treasury_3y": 1.64,
    "treasury_5y": 1.76,
    "treasury_7y": 1.87,
    "treasury_10y": 1.99,
    "treasury_30y": 2.26,
    "credit_spread_aaa_3y": 58.71,
    "credit_spread_aa_plus_3y": 66.2,
    "credit_spread_aa_3y": 95.3,
}

START_DATE = date(2026, 6, 30)
END_DATE = date(2026, 7, 31)

# 覆盖：左端 clamp（0.6）、样条内点（2.4/4.7/8.3/12.0）、结点（5.0）、右端（30.0）
BENCH_MATURITIES = (0.6, 2.4, 4.7, 5.0, 8.3, 12.0, 30.0)


def _positions() -> list[dict[str, Any]]:
    return [
        {
            "bond_code": "GOV_2031",
            "market_value_start": 101_234_567.89,
            "market_value_end": 101_876_543.21,
            "face_value_start": 100_000_000.0,
            "coupon_rate_start": 0.0268,
            "yield_to_maturity_start": 0.0195,
            "asset_class_start": "国债",
            "maturity_date_start": date(2031, 3, 15),
            "accrued_interest_start": 1_234_567.89,
            "accrued_interest_end": 1_901_234.56,
        },
        {
            "bond_code": "AAA_2029",
            "market_value_start": 50_987_654.32,
            "market_value_end": 50_765_432.10,
            "face_value_start": 50_000_000.0,
            "coupon_rate_start": 0.0345,
            "yield_to_maturity_start": 0.0312,
            "asset_class_start": "AAA 信用债",
            "maturity_date_start": date(2029, 6, 20),
            "accrued_interest_start": 654_321.09,
            "accrued_interest_end": 876_543.21,
        },
        {
            "bond_code": "CT_2027",
            "market_value_start": 30_456_789.01,
            "market_value_end": 30_567_890.12,
            "face_value_start": 30_000_000.0,
            "coupon_rate_start": 0.0421,
            "yield_to_maturity_start": 0.0398,
            "asset_class_start": "城投债",
            "maturity_date_start": date(2027, 9, 10),
            "accrued_interest_start": 345_678.90,
            "accrued_interest_end": 456_789.01,
        },
    ]


# ---------------------------------------------------------------------------
# 情景压力真实形状 fixture：物化风险张量 result 中的 Numeric dump 片段
# ---------------------------------------------------------------------------

def _tensor_result() -> dict[str, Any]:
    return {
        "regulatory_dv01": {"raw": 125_432.7891, "unit": "dv01"},
        "cs01": {"raw": 98_765.4321, "unit": "dv01"},
        "asset_cashflow_30d": {"raw": 2_345_678_901.23, "unit": "yuan"},
        "liability_cashflow_30d": {"raw": 1_987_654_321.98, "unit": "yuan"},
        "liquidity_gap_30d": {"raw": 358_024_579.25, "unit": "yuan"},
        "total_market_value": {"raw": 45_678_901_234.56, "unit": "yuan"},
    }


# ---------------------------------------------------------------------------
# 改造前锁定值（2026-08-12 捕获自 float 实现；容差远小于展示精度）
# ---------------------------------------------------------------------------

_BENCH_LOCK: dict[str, Decimal] = {
    "0.6": Decimal("0.0005000000000000004"),
    "2.4": Decimal("0.0005486185999999993"),
    "4.7": Decimal("0.0007941386000000005"),
    "5.0": Decimal("0.0008000000000000007"),
    "8.3": Decimal("0.0006115314000000005"),
    "12.0": Decimal("0.0010062738999999988"),
    "30.0": Decimal("0.0006999999999999984"),
}

_SPREAD_LOCK: dict[str, Decimal] = {
    "AAA": Decimal("0.00033900000000000005"),
    "AA+": Decimal("-0.0002269999999999996"),
    "AA": Decimal("0.0003200000000000003"),
    "GOV": Decimal("0"),
}

# ---------------------------------------------------------------------------
# W-fi-2026-08 P2 重锁：treasury/spread_effect 的口径依据
# ---------------------------------------------------------------------------
# 这批值 pin 的是**逐期现金流贴现久期**，不是旧的整期闭合式久期。完整口径：
#
#   剩余期限 = 剩余自然日 / 365（ACT/365）
#   付息计划 = 半年付，n = ceil(剩余期限 × 2) 期；末期落在剩余期限当天，其余按
#              1/2 年回推，因此首期是一段短残期（≤0.01 期的尾数并入上一期）
#   贴现     = (1 + ytm/2) ^ (t × 2)
#   Macaulay = Σ t·PV(t) / Σ PV(t)；修正久期 = Macaulay / (1 + ytm/2)
#   Δy       = 国债曲线自然三次样条（1/3/5/7/10/30Y 节点，百分数保留 8 位小数）
#              在该券剩余期限上的期末期初之差 / 100
#   treasury_effect = −修正久期 × Δy × 期初市值；spread_effect 同式换 Δ利差
#
# 旧锁（−441,588.75 / GOV_2031 −340,435.15）错在久期一项：旧实现把期数四舍五入成
# 整数，等于把债券重定价成一只整期债——
#   GOV_2031  剩余 1719d = 4.7096y → 旧口径按 9 期（4.50y）定价，修正久期 4.2322 vs 正确 4.3855（+3.62%）
#   AAA_2029  剩余 1086d = 2.9753y → 旧口径按 6 期（3.00y）定价，修正久期 2.8322 vs 正确 2.8079（−0.86%）
#   CT_2027   剩余  437d = 1.1973y → 旧口径按 2 期（1.00y）定价，修正久期 0.9704 vs 正确 1.1438（+17.87%）
#
# 2026-08-13 重算方式（这些数是独立推出来的，不是从被测代码输出抄回来的）：另写一份
# **不 import 任何 MOSS 代码**的教科书参考实现，同一个值用互相独立的多条路径求——
# 样条走三条（矩量式 + 通用高斯消元 / 4(n−1) 系数全量线性方程组 + 通用高斯消元 /
# scipy CubicSpline(bc_type="natural")），久期走五条（float 逐期贴现、Decimal prec=60
# 逐期贴现、几何级数闭合式的 float 与 Decimal 版、prec=60 价格函数中心差分反推修正
# 久期——最后一条同时独立验证了 Macaulay→修正久期的除法）。核对结果：
#   * 独立值与代码输出逐券逐字段 |diff| = 0（不是"落在容差内"，是完全一致）；
#   * 独立样条复现了本文件 2026-08-12 就锁定、且久期修复未触及的 _BENCH_LOCK 七个 Δy
#     （|diff| < 1.6e-18），说明 Δy 这条腿也不是拿今天的代码倒推的；
#   * 把同一份独立 Δy/市值配上旧的整期闭合式久期，能把旧锁那六个数复现到 3.5e-10 元，
#     反证两版锁值之差确实只来自久期口径，其余输入逐字段未动。
# income_return / total_return / market_value_start 与旧锁完全一致（久期不进入这三项）。

# 上述口径直接产出的修正久期。单独锁一遍，是为了让"利率效应差了几万元"能被读成
# "久期从 X 年变成 Y 年"——CNY 数字看不出口径回退，久期看得出。
_MOD_DURATION_LOCK: dict[str, float] = {
    "GOV_2031": 4.385538577546118,
    "AAA_2029": 2.8078906842612144,
    "CT_2027": 1.1438419445777561,
}

_TOTALS_LOCK: dict[str, float] = {
    "income_return": 481391.7808219178,
    "treasury_effect": -455841.9380529043,
    "spread_effect": -40625.700618696654,
    "selection_effect": 1027321.8486716009,
    "total_return": 1012245.9908219178,
    "market_value_start": 182679011.22,
}

_BY_BOND_LOCK: dict[str, dict[str, float]] = {
    "GOV_2031": {
        "income_return": 227616.43835616438,
        "treasury_effect": -352766.6212843688,
        "spread_effect": 0.0,
        "selection_effect": 994741.9412843687,
        "total_return": 869591.7583561643,
    },
    "AAA_2029": {
        "income_return": 146506.84931506848,
        "treasury_effect": -85516.62254818487,
        "spread_effect": -48533.87049675862,
        "selection_effect": -88171.72695505651,
        "total_return": -75715.3706849315,
    },
    "CT_2027": {
        "income_return": 107268.49315068492,
        "treasury_effect": -17558.694220350662,
        "spread_effect": 7908.169878061973,
        "selection_effect": 120751.63434228869,
        "total_return": 218369.60315068494,
    },
}

# Δ 为小数收益率（~5e-4 量级），展示端最细也只到 bp 两位（1e-6 小数）；1e-12 远小于展示精度。
_TOL_DELTA = Decimal("1e-12")
# 金额展示精度 2dp（四舍五入阈值 5e-3）；1e-4 远小于阈值，同时容纳 float→Decimal 的 ~1e-7 级修正。
_TOL_YUAN = 1e-4
_TOL_RATIO = 1e-12
# 久期展示精度 4dp；1e-12 远小于阈值，而口径回退（整期闭合式）的偏差是 0.02–0.17 年，
# 差六个数量级，不存在"容差把口径变化吃掉"的风险。
_TOL_DURATION = 1e-12


class TestCampisiDecimalLock:
    def test_benchmark_curve_delta_locked(self) -> None:
        for m_str, expected in _BENCH_LOCK.items():
            got = benchmark_yield_change_decimal(MARKET_START, MARKET_END, float(m_str))
            assert abs(got - expected) < _TOL_DELTA, (m_str, str(got))

    def test_credit_spread_delta_locked(self) -> None:
        for rating, expected in _SPREAD_LOCK.items():
            got = credit_spread_change_decimal(MARKET_START, MARKET_END, rating)
            assert abs(got - expected) < _TOL_DELTA, (rating, str(got))

    def test_campisi_mod_duration_locked(self) -> None:
        """锁住驱动 treasury/spread_effect 的修正久期本身。

        这两个效应是 −修正久期 × Δ × 市值，久期是其中唯一会随口径漂移的因子；
        单锁 CNY 金额时，一次久期口径回退只会表现为一个对不上的大数，看不出成因。
        """
        result = campisi_attribution(_positions(), MARKET_START, MARKET_END, START_DATE, END_DATE)
        rows = {r["bond_code"]: r for r in result.by_bond}
        for code, expected in _MOD_DURATION_LOCK.items():
            assert rows[code]["mod_duration"] == pytest.approx(expected, abs=_TOL_DURATION), code

    def test_campisi_attribution_totals_locked(self) -> None:
        result = campisi_attribution(_positions(), MARKET_START, MARKET_END, START_DATE, END_DATE)
        assert result.num_days == 31
        for key, expected in _TOTALS_LOCK.items():
            assert result.totals[key] == pytest.approx(expected, abs=_TOL_YUAN), key

    def test_campisi_attribution_by_bond_locked(self) -> None:
        result = campisi_attribution(_positions(), MARKET_START, MARKET_END, START_DATE, END_DATE)
        rows = {r["bond_code"]: r for r in result.by_bond}
        assert set(rows) == set(_BY_BOND_LOCK)
        for code, expected_fields in _BY_BOND_LOCK.items():
            for key, expected in expected_fields.items():
                assert rows[code][key] == pytest.approx(expected, abs=_TOL_YUAN), (code, key)


class TestScenarioStressDecimalLock:
    def test_rate_scenario_locked(self) -> None:
        row = _rate_scenario(_tensor_result())
        assert row["estimated_impact"]["raw"] == pytest.approx(-1254327.891, abs=_TOL_YUAN)
        assert row["estimated_impact"]["display"] == "-1,254,327.89"
        assert row["shock"]["raw"] == pytest.approx(10.0)
        assert row["shock"]["display"] == "+10 bp"
        assert row["data_status"] == "available"

    def test_credit_scenario_locked(self) -> None:
        row = _credit_scenario(_tensor_result())
        assert row["estimated_impact"]["raw"] == pytest.approx(-987654.321, abs=_TOL_YUAN)
        assert row["estimated_impact"]["display"] == "-987,654.32"
        assert row["shock"]["raw"] == pytest.approx(10.0)
        assert row["shock"]["display"] == "+10 bp"

    def test_liquidity_scenario_locked(self) -> None:
        row = _liquidity_scenario(_tensor_result())
        assert row["estimated_impact"]["raw"] == pytest.approx(-433333322.321, abs=_TOL_YUAN)
        assert row["estimated_impact"]["display"] == "-433,333,322.32"
        assert row["shock"]["raw"] == pytest.approx(0.1)
        assert row["shock"]["display"] == "+10.0%"
        assert row["baseline_value"]["raw"] == pytest.approx(358024579.25, abs=_TOL_YUAN)
        assert row["baseline_value"]["display"] == "+358,024,579.25"
        assert row["stressed_value"]["raw"] == pytest.approx(-75308743.071, abs=_TOL_YUAN)
        assert row["stressed_value"]["display"] == "-75,308,743.07"
        assert row["baseline_ratio"]["raw"] == pytest.approx(0.007837854448633799, abs=_TOL_RATIO)
        assert row["baseline_ratio"]["display"] == "+0.8%"
        assert row["stressed_ratio"]["raw"] == pytest.approx(-0.0016486548720664575, abs=_TOL_RATIO)
        assert row["stressed_ratio"]["display"] == "-0.2%"
        assert row["data_status"] == "available"

    def test_summary_worst_locked(self) -> None:
        tensor = _tensor_result()
        rows = [_rate_scenario(tensor), _credit_scenario(tensor), _liquidity_scenario(tensor)]
        summary = _scenario_summary(rows)
        assert summary["worst_scenario_key"] == "liquidity_30d_cashflow_10pct"
        assert summary["worst_estimated_impact"]["raw"] == pytest.approx(-433333322.321, abs=_TOL_YUAN)
        assert summary["worst_estimated_impact"]["display"] == "-433,333,322.32"
        assert summary["available_count"] == 3


def _capture_exact() -> dict[str, Any]:
    """改造前/后全精度捕获（repr / Decimal str），供数值差异量化对比。"""
    bench = {
        str(m): str(benchmark_yield_change_decimal(MARKET_START, MARKET_END, m))
        for m in BENCH_MATURITIES
    }
    spreads = {
        r: str(credit_spread_change_decimal(MARKET_START, MARKET_END, r))
        for r in ("AAA", "AA+", "AA", "GOV")
    }
    result = campisi_attribution(_positions(), MARKET_START, MARKET_END, START_DATE, END_DATE)
    totals = {k: repr(v) for k, v in result.totals.items()}
    by_bond = {
        r["bond_code"]: {
            k: repr(r[k])
            for k in ("income_return", "treasury_effect", "spread_effect", "selection_effect", "total_return")
        }
        for r in result.by_bond
    }
    tensor = _tensor_result()
    rate = _rate_scenario(tensor)
    credit = _credit_scenario(tensor)
    liq = _liquidity_scenario(tensor)
    summary = _scenario_summary([rate, credit, liq])
    scen = {
        "rate_impact": (repr(rate["estimated_impact"]["raw"]), rate["estimated_impact"]["display"]),
        "rate_shock": (repr(rate["shock"]["raw"]), rate["shock"]["display"]),
        "credit_impact": (repr(credit["estimated_impact"]["raw"]), credit["estimated_impact"]["display"]),
        "credit_shock": (repr(credit["shock"]["raw"]), credit["shock"]["display"]),
        "liq_impact": (repr(liq["estimated_impact"]["raw"]), liq["estimated_impact"]["display"]),
        "liq_shock": (repr(liq["shock"]["raw"]), liq["shock"]["display"]),
        "liq_baseline": (repr(liq["baseline_value"]["raw"]), liq["baseline_value"]["display"]),
        "liq_stressed": (repr(liq["stressed_value"]["raw"]), liq["stressed_value"]["display"]),
        "liq_baseline_ratio": (repr(liq["baseline_ratio"]["raw"]), liq["baseline_ratio"]["display"]),
        "liq_stressed_ratio": (repr(liq["stressed_ratio"]["raw"]), liq["stressed_ratio"]["display"]),
        "worst": (
            repr(summary["worst_estimated_impact"]["raw"]),
            summary["worst_estimated_impact"]["display"],
            summary["worst_scenario_key"],
        ),
    }
    return {"bench": bench, "spreads": spreads, "totals": totals, "by_bond": by_bond, "scenario": scen}


if __name__ == "__main__":  # pragma: no cover - manual capture entry
    import json

    print(json.dumps(_capture_exact(), ensure_ascii=False, indent=1))
