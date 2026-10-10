"""短端桶（ON / 3M / 6M）归并的黄金对照：backend/app/core_finance/krd.py。

背景：``attribution_core.get_tenor_bucket`` 会产出 ON/7D/1M/3M/6M，而
``KRD_TENORS`` 自 1Y 起。归并前这些持仓在 ``compute_krd_by_tenor`` 里被静默
``continue`` 丢弃，但 ``weight`` 分母仍含全部持仓 → Σ KRD < 组合修正久期且无披露；
"平行"情景对短端冲击恒为 0。tests/test_krd_golden.py 的三只券均 ≥2Y，覆盖不到该路径。

归并口径对齐生产路径 ``risk_tensor.KRD_BUCKET_FALLBACK``（就近映射到受支持桶，
其中 6M -> krd_1y 已是既有生产口径），其余 <1Y 桶按同一规则同归 1Y。

实现口径（决定本文件期望值，全部独立推算，不取被测函数输出）：

- 剩余年限 = (maturity - report).days / 365（ACT/365F）。
- ``bond_duration.compute_macaulay_duration`` 委托 ``bond_analytics.common``：
  本组报告日、到期日均明确；现金流按到期日向前逐半年或逐年确定真实票息日，
  报告日当天已付票息不再计入。报告日严格在票息网格时用 k/f 年，其他日期用
  票息日距报告日的 ACT/365F 年数，不以等间隔碎期代替真实日期。
  PV_k = CF_k / (1+ytm/f)^(t_k·f)，MacD = Σt_k·PV_k / ΣPV_k，**不量化**。
- D_mod = MacD / (1 + ytm/f)，不量化。
- 凸性 = 标准现金流二阶导 Σ t_k(t_k + 1/f)·PV_k / ΣPV_k / (1 + ytm/f)²（单笔现金流时
  退化为闭式解 t(t + 1/f)/(1 + ytm/f)²）。
- KRD[桶] = Σ weight × D_mod；桶 DV01 = Σ face × D_mod / 10000。

旧整期闭式会把 6M 券当成恰好一个半年期，给出 0.5000；其后等间隔碎期口径
给出 0.5926108374…，第一笔票息仍被放在 36.5 天。当前有日期路径按真实 38 天
付息，独立黄金值为 0.5926724537…；ON / 3M 各只有一笔到期现金流，数值不变。

四只券（report_date = 2026-01-01，各市值/面值 1,000,000 → weight 恒为 0.25）：

┌────────┬───────────┬──────┬──────────┬─────────┬──────────────────────────┐
│ 券      │ 到期日     │ 天数  │ years    │ 票息/YTM │ MacD → D_mod             │
├────────┼───────────┼──────┼──────────┼─────────┼──────────────────────────┤
│ ON     │2026-01-03 │    2 │ 2/365    │2%/2% f=1│ 2/365 → 20/3723          │
│ 3M     │2026-03-15 │   73 │ 0.2 精确 │2.5% f=2 │ 0.2 → 16/81              │
│ 6M     │2026-08-08 │  219 │ 0.6 精确 │3% f=2   │ 0.59267245… → 0.58391374…│
│ 2Y     │2028-01-01 │  730 │ 2 精确   │2.5% f=2 │ 1.96326685… → 1.93902899…│
└────────┴───────────┴──────┴──────────┴─────────┴──────────────────────────┘

逐项推算：

- ON：years = 2/365 = 0.005479452054…，2026-01-03 是唯一未来票息日，
  只剩到期一笔现金流 ⇒ MacD = years（Σt·PV/ΣPV 中贴现因子完全约去，精确等式）。
  D_mod = (2/365)/1.02 = 20/3723 = 0.005372011818426…（新旧同值）
- 3M：years = 73/365 = 0.2（精确），2026-03-15 是唯一未来票息日，同样只剩一笔。
  MacD = 0.2；D_mod = 0.2/1.0125 = 16/81 = 0.197530864197530864…（新旧同值）
- 6M：真实付息日为 2026-02-08 / 2026-08-08，报告日 2026-01-01，
  两笔现金流为第 38 天的 0.015 与第 219 天的 1.015（每单位面值）。
    PV₁ = 0.015 / 1.015^(76/365)，PV₂ = 1.015 / 1.015^(438/365)
    MacD = (38·PV₁ + 219·PV₂) / (365·(PV₁+PV₂))
         = 0.5926724537715512392516086952
  D_mod = MacD/1.015 = 0.5839137475581785608390233450
  **独立闭式交叉验证**：令 q=PV₁/PV₂=(3/203)·(203/200)^(362/365)，则
  MacD=(38q+219)/(365·(1+q))，两种计算在 60 位 Decimal 精度下一致。
  这比旧等间隔碎期答案高 0.0000616163 年，差额源于 38 天与 36.5 天的时点差。
  整期旧值 0.5000 则漏掉第一笔票息，偏离真实答案约 0.093 年。
- 2Y：沿用 tests/test_krd_golden.py 独立推算的平价债黄金值
  MacD = 1.963266853705303128663388787（整期，与经典年金式差 1.1e-14），
  D_mod = 1.939028991313879633247791395

桶层期望（weight 恒 0.25，ON/3M/6M 三只全部归并进 1Y 桶）：

  Σ 短端 D_mod = 20/3723 + 16/81 + 0.5839137475581785608390233450
               = 0.7868166235741354255737553910
  KRD[1Y] = 0.25 × Σ 短端 = 0.1967041558935338563934388478
  KRD[2Y] = 0.25 × 1.939028991313879633247791395 = 0.4847572478284699083119478488
  Σ KRD   = 0.6814614037220037647053866962 = 组合修正久期 Σ weight × D_mod（恒等）
  DV01[1Y]= 100 × Σ 短端 = 78.68166235741354255737553910
  1Y 桶市值权重 = 0.75（三只短端券）

容差：实现返回 Decimal 全精度，常数按全精度书写；D_mod / KRD 量级 O(1) 取 1e-18，
DV01 量级 O(10²) 取 1e-16，情景损益量级 O(10²) 取 1e-6
（旧口径为 1e-10 / 1e-8，本次一并收紧）。
Σ KRD 恒等式用 1e-24（Decimal 28 位上下文的重结合噪声下限，非口径容差）。
"""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance.krd import (
    KRD_SHORT_END_BUCKET_MERGE,
    KRD_TENORS,
    STANDARD_KRD_SCENARIOS,
    _aggregate_krd_buckets,
    build_krd_position_metrics,
    compute_curve_scenario,
    compute_krd_by_tenor,
    compute_krd_curve_risk,
)
from backend.app.core_finance.risk_tensor import KRD_BUCKET_FALLBACK

REPORT_DATE = date(2026, 1, 1)

TOL_DURATION = Decimal("1E-18")
TOL_DV01 = Decimal("1E-16")
TOL_PNL = Decimal("1E-6")
TOL_CLOSURE = Decimal("1E-24")

# 独立推算的黄金常数（推导与交叉验证见模块 docstring）
MAC_6M = Decimal("0.5926724537715512392516086952")
DMOD_ON = Decimal("0.005372011818426000537201181842")   # = 20/3723
DMOD_3M = Decimal("0.1975308641975308641975308642")     # = 16/81
DMOD_6M = Decimal("0.5839137475581785608390233450")
DMOD_2Y = Decimal("1.939028991313879633247791395")
DMOD_SHORT_END_SUM = DMOD_ON + DMOD_3M + DMOD_6M


def _make_bond(
    bond_code: str,
    coupon_rate: str,
    ytm: str,
    maturity_date: date,
    coupon_frequency: int,
    sub_type: str,
) -> dict:
    return {
        "bond_code": bond_code,
        "market_value": Decimal("1000000"),
        "face_value": Decimal("1000000"),
        "coupon_rate": Decimal(coupon_rate),
        "yield_to_maturity": Decimal(ytm),
        "maturity_date": maturity_date,
        "report_date": REPORT_DATE,
        "sub_type": sub_type,
        "asset_class": "交易性金融资产",
        "coupon_frequency": coupon_frequency,
    }


# 2 天到期（ON 桶：0 <= years < 0.01）
BOND_ON = _make_bond("B_ON", "0.0200", "0.0200", date(2026, 1, 3), 1, "同业存单")
# 73 天到期（3M 桶：0.12 <= years < 0.30）
BOND_3M = _make_bond("B_3M", "0.0250", "0.0250", date(2026, 3, 15), 2, "超短融")
# 219 天到期（6M 桶：0.30 <= years < 0.75）
BOND_6M = _make_bond("B_6M", "0.0300", "0.0300", date(2026, 8, 8), 2, "短期融资券")
# 730 天到期（2Y 桶，原生受支持）
BOND_2Y = _make_bond("B_2Y", "0.0250", "0.0250", date(2028, 1, 1), 2, "国债")

SHORT_END_PORTFOLIO = [BOND_ON, BOND_3M, BOND_6M, BOND_2Y]


class TestShortEndBucketAssignment:
    """先锁定 fixture 真的落在 ON / 3M / 6M 桶，否则后续断言失去意义。"""

    def test_raw_tenor_buckets(self):
        metrics = build_krd_position_metrics(SHORT_END_PORTFOLIO, report_date=REPORT_DATE)
        assert [m["tenor_bucket"] for m in metrics] == ["ON", "3M", "6M", "2Y"]

    def test_day_counts_are_pinned(self):
        assert (date(2026, 1, 3) - REPORT_DATE).days == 2
        assert (date(2026, 3, 15) - REPORT_DATE).days == 73
        assert (date(2026, 2, 8) - REPORT_DATE).days == 38
        assert (date(2026, 8, 8) - REPORT_DATE).days == 219

    def test_merge_map_matches_risk_tensor_caliber(self):
        """归并口径必须与生产路径 risk_tensor 一致，不得另造一套。

        risk_tensor 的 6M 归并目标是 ``krd_1y`` 字段名，本模块用桶标签 ``1Y``；
        其余 <1Y 桶按同一"就近映射到受支持桶"规则同归 1Y。
        """
        assert KRD_BUCKET_FALLBACK["6M"] == "krd_1y"
        assert KRD_SHORT_END_BUCKET_MERGE["6M"] == "1Y"
        assert set(KRD_SHORT_END_BUCKET_MERGE) == {"ON", "7D", "1M", "3M", "6M"}
        assert set(KRD_SHORT_END_BUCKET_MERGE.values()) == {"1Y"}
        # 归并目标必须是本模块受支持的桶
        assert set(KRD_SHORT_END_BUCKET_MERGE.values()) <= set(KRD_TENORS)


class TestShortEndPositionMetricsGolden:
    """逐券修正久期黄金值（手算见模块 docstring）。"""

    def test_modified_duration_golden(self):
        metrics = build_krd_position_metrics(SHORT_END_PORTFOLIO, report_date=REPORT_DATE)
        by_code = {m["bond_code"]: m for m in metrics}

        # ON / 3M 只剩到期一笔现金流 → MacD 精确等于剩余年限
        assert by_code["B_ON"]["duration"] == Decimal("2") / Decimal("365")
        assert by_code["B_3M"]["duration"] == Decimal("0.2")
        # 6M 有两笔（38/365 年的票息 + 219/365 年的到期）；旧整期口径漏掉第一笔。
        assert abs(by_code["B_6M"]["duration"] - MAC_6M) < TOL_DURATION

        assert abs(by_code["B_ON"]["modified_duration"] - DMOD_ON) < TOL_DURATION
        assert abs(by_code["B_3M"]["modified_duration"] - DMOD_3M) < TOL_DURATION
        assert abs(by_code["B_6M"]["modified_duration"] - DMOD_6M) < TOL_DURATION

    def test_six_month_bond_prices_both_remaining_cashflows(self):
        """6M 券必须体现两笔现金流，而不是退化成"恰好剩一个完整半年期"。

        真实付息日 2026-02-08 / 2026-08-08，结算日 2026-01-01 时确有两笔。
        独立手算见模块 docstring；本例同时拒绝旧等间隔碎期的 36.5 天时点
        和旧整期口径漏掉第一笔票息的 0.5000。
        """
        metrics = build_krd_position_metrics([BOND_6M], report_date=REPORT_DATE)
        mac = metrics[0]["duration"]

        assert abs(mac - MAC_6M) < TOL_DURATION, (
            f"6M 久期 {mac} 偏离真实日历答案 {MAC_6M}"
        )
        assert mac > Decimal("0.55"), f"6M 久期 {mac} 退回整期口径的 0.5000"


class TestShortEndKrdSumIdentity:
    """Σ KRD 必须等于组合修正久期——归并前短端被丢弃会破坏该恒等式。"""

    def test_sum_krd_equals_portfolio_modified_duration(self):
        buckets = compute_krd_by_tenor(SHORT_END_PORTFOLIO, report_date=REPORT_DATE)
        metrics = build_krd_position_metrics(SHORT_END_PORTFOLIO, report_date=REPORT_DATE)

        krd_sum = sum((row["krd"] for row in buckets), Decimal("0"))
        portfolio_modified_duration = sum(
            (m["weight"] * m["modified_duration"] for m in metrics),
            Decimal("0"),
        )
        assert abs(krd_sum - portfolio_modified_duration) < TOL_CLOSURE

    def test_sum_krd_golden(self):
        buckets = compute_krd_by_tenor(SHORT_END_PORTFOLIO, report_date=REPORT_DATE)
        krd_sum = sum((row["krd"] for row in buckets), Decimal("0"))
        expected = (DMOD_SHORT_END_SUM + DMOD_2Y) / Decimal("4")
        assert abs(krd_sum - expected) < TOL_DURATION

    def test_short_end_krd_lands_in_1y_bucket_golden(self):
        buckets = compute_krd_by_tenor(SHORT_END_PORTFOLIO, report_date=REPORT_DATE)
        by_tenor = {row["tenor"]: row for row in buckets}

        assert abs(by_tenor["1Y"]["krd"] - DMOD_SHORT_END_SUM / Decimal("4")) < TOL_DURATION
        assert abs(by_tenor["2Y"]["krd"] - DMOD_2Y / Decimal("4")) < TOL_DURATION
        assert abs(by_tenor["1Y"]["dv01"] - Decimal("100") * DMOD_SHORT_END_SUM) < TOL_DV01
        assert by_tenor["1Y"]["market_value_weight"] == Decimal("0.75")

    def test_market_value_weights_sum_to_one(self):
        """归并前分母含全部持仓、分子漏掉短端 → 权重合计 < 1。"""
        buckets = compute_krd_by_tenor(SHORT_END_PORTFOLIO, report_date=REPORT_DATE)
        total_weight = sum((row["market_value_weight"] for row in buckets), Decimal("0"))
        assert total_weight == Decimal("1")


class TestShortEndBucketDisclosure:
    def test_merge_is_disclosed_in_payload(self):
        result = compute_krd_curve_risk(SHORT_END_PORTFOLIO, report_date=REPORT_DATE)
        disclosure = result["krd_bucket_disclosure"]

        assert disclosure["merged_buckets"] == {"3M": "1Y", "6M": "1Y", "ON": "1Y"}
        assert disclosure["merged_market_value"] == Decimal("3000000")
        assert disclosure["merged_position_count"] == 3
        assert disclosure["dropped_buckets"] == []
        assert disclosure["dropped_market_value"] == Decimal("0")
        assert disclosure["dropped_position_count"] == 0
        assert disclosure["dropped_market_value_weight"] == Decimal("0")
        assert disclosure["warnings"] == [
            "Short-end tenor buckets merged into nearest KRD bucket: 3M->1Y, 6M->1Y, ON->1Y"
        ]

    def test_unmergeable_bucket_is_dropped_with_warning_and_disclosure(self, caplog):
        """归并目标桶不存在时才允许丢弃，且必须 warning + 披露市值与行数。

        用不含 1Y 的自定义桶集合构造该分支：ON/3M/6M 的归并目标 1Y 不可用 →
        3 只短端券（合计 3,000,000，占组合 75%）被剔除，Σ KRD 相对组合修正
        久期的缺口即由该 75% 权重解释。
        """
        metrics = build_krd_position_metrics(SHORT_END_PORTFOLIO, report_date=REPORT_DATE)
        with caplog.at_level(logging.WARNING, logger="backend.app.core_finance.krd"):
            buckets, disclosure = _aggregate_krd_buckets(metrics, ("2Y", "3Y", "5Y"))

        assert disclosure["dropped_buckets"] == ["3M", "6M", "ON"]
        assert disclosure["dropped_market_value"] == Decimal("3000000")
        assert disclosure["dropped_position_count"] == 3
        assert disclosure["dropped_market_value_weight"] == Decimal("0.75")
        assert disclosure["merged_position_count"] == 0
        assert any("dropped buckets" in record.message for record in caplog.records)

        krd_sum = sum((row["krd"] for row in buckets), Decimal("0"))
        assert abs(krd_sum - DMOD_2Y / Decimal("4")) < TOL_DURATION


class TestParallelScenarioCoversShortEnd:
    """平行情景必须对短端持仓产生非零冲击。"""

    @pytest.mark.parametrize(
        "scenario_name",
        ["parallel_up_25bp", "parallel_up_50bp", "parallel_up_100bp", "parallel_down_25bp"],
    )
    def test_parallel_scenarios_use_all_key(self, scenario_name):
        scenario = next(s for s in STANDARD_KRD_SCENARIOS if s["name"] == scenario_name)
        assert set(scenario["shocks"]) == {"all"}

    def test_parallel_up_25bp_hits_short_end_only_portfolio_golden(self):
        """单只 3M 券（D_mod = 16/81，凸性 = t(t+1/f)/1.0125²）+25bp：

          利率效应 = -16/81 × 1,000,000 × 0.0025 = -493.827160493827…
          凸性     = 0.2×(0.2+0.5)/1.0125² = 0.14/1.02515625 = 0.136564548087…
          凸性效应 = 0.5 × 0.136564548087… × 1,000,000 × 0.0025² = 0.426764212772…
          ΔPnL     = -493.827160493827… + 0.426764212772… = -493.400396281055…

        归并/``all`` 语义修复前该值恒为 0（3M 不在 shocks 里）。
        golden 演进：P3 由 ``[D² + D(1+1/f)]/(1+y/f)²``（无出处）收敛到
        ``common.estimate_convexity``（-492.790733119951 → -493.095564700502）；
        P4 再由久期型近似 ``D(D+1)/(1+y/f)²`` 升级为标准现金流凸性
        （-493.095564700502 → -493.400396281055）。本券只有一笔现金流，两次变化
        全部来自分子：``t(t+1)`` → ``t(t+1/f)``，即修掉了 f=2 下对短端高估的 ``D/f``。
        """
        metrics = build_krd_position_metrics([BOND_3M], report_date=REPORT_DATE)
        scenario = next(s for s in STANDARD_KRD_SCENARIOS if s["name"] == "parallel_up_25bp")
        result = compute_curve_scenario(metrics, scenario)

        assert result["pnl_economic"] != Decimal("0")
        assert abs(result["pnl_economic"] - Decimal("-493.400396281055")) < TOL_PNL

    def test_parallel_down_flips_sign_for_short_end(self):
        metrics = build_krd_position_metrics([BOND_ON, BOND_3M, BOND_6M], report_date=REPORT_DATE)
        up = next(s for s in STANDARD_KRD_SCENARIOS if s["name"] == "parallel_up_25bp")
        down = next(s for s in STANDARD_KRD_SCENARIOS if s["name"] == "parallel_down_25bp")

        assert compute_curve_scenario(metrics, up)["pnl_economic"] < Decimal("0")
        assert compute_curve_scenario(metrics, down)["pnl_economic"] > Decimal("0")

    def test_bucketed_scenario_falls_back_to_merged_bucket(self):
        """陡峭化按逐桶给冲击：短端沿用归并桶（1Y = -25bp）而不是静默 0。"""
        metrics = build_krd_position_metrics([BOND_3M], report_date=REPORT_DATE)
        steepening = next(s for s in STANDARD_KRD_SCENARIOS if s["name"] == "steepening_50bp")
        result = compute_curve_scenario(metrics, steepening)

        assert steepening["shocks"]["1Y"] == -25
        assert result["pnl_economic"] > Decimal("0")
