"""
Golden-value tests for backend.app.core_finance.krd (B4-KRD).

所有期望常数均为独立推算的黄金值：不使用被测函数的任何输出作为期望值。
重要口径声明：当前实现只是把"市值权重 × 修正久期"按到期桶聚合，没有逐节点
bump-and-reprice。**这不是标准 KRD，标准化待业务裁决。**

W-fi-2026-08 口径修正（本文件常数随之重算）
--------------------------------------------------------------------------
``bond_duration.compute_macaulay_duration`` 原先是**整期**闭合公式，期数按
``to_integral_value()``（ROUND_HALF_EVEN）四舍五入，结果再 quantize 到 1e-4。
由于剩余年限恒为"剩余天数/365"、几乎从不是整数，非整期券被系统性错误定价。
现已改为委托 ``bond_analytics.common``：ROUND_CEILING 取期数、首期按残期定位、
逐期贴现、**不再量化**。本文件的常数按新口径全部重算：

  · BOND_5Y / BOND_2Y 落在整期（或尾数被归并回整期），**久期数值未变**，
    变的只是不再 quantize，故期望值从 4 位小数改为全精度；
  · BOND_10Y 的 2 个闰日仅造成 ACT/365 与真实半年付息日历的 2 天漂移，按
    ±7 天日历容差归并为 20 个整期，避免虚构第 21 笔票息；
  · 一切 D_mod / DV01 / KRD 常数都是上述久期的下游，随之重算。

期望值来源与交叉验证
--------------------------------------------------------------------------
久期常数由一份不导入任何 MOSS 代码的教科书参考实现算出，该参考用四条互相独立
的路径求解并要求彼此一致（浮点逐笔求和 / Decimal(prec=60) 逐笔求和 / 几何级数
闭合式 / 由价格函数中心差分反推 MacD = −(1+y)/P·dP/dy）。整期券另与经典年金式

    D_p = (1+y)/y − [1+y+n(c−y)] / [c((1+y)^n − 1) + y]

对照，BOND_5Y 差 3.5e-14、BOND_2Y 差 1.1e-14 —— 即新实现在整期情形下退化为
教科书闭合式，是旧实现的严格推广。详见 tests/test_bond_duration_goldens.py 文件头。

符号约定：
  f      = 付息频率（每年次数）；c = coupon_rate/f；y = ytm/f
  n      = ceil(years × f)，若距最近整期对应日数 ≤7 天则并回该整期
  D      = Macaulay 久期（年）= Σt·CF_t·(1+y)^(−t·f) / Σ CF_t·(1+y)^(−t·f)，不量化
  D_mod  = D / (1 + y)
  DV01   = face_value × D_mod / 10000            （元/bp）
  KRD[b] = Σ_{券∈桶 b} weight × D_mod            （weight = 市值/组合总市值）

三个标准场景（report_date = 2026-01-01，半年付息 f=2，票息=YTM 即平价债）：

┌──────────────┬───────────────┬───────────────┬───────────────┐
│              │ BOND_5Y       │ BOND_2Y       │ BOND_10Y      │
│              │ 3% / 3%       │ 2.5% / 2.5%   │ 3.5% / 3.5%   │
├──────────────┼───────────────┼───────────────┼───────────────┤
│ 到期日        │ 2031-01-01    │ 2028-01-01    │ 2036-01-01    │
│ 剩余天数      │ 1826          │ 730           │ 3652          │
│ years=天/365 │ 5.00273973…   │ 2（精确）      │ 10.00547945…  │
│ years×f      │ 10.0054795    │ 4（精确）      │ 20.0109589    │
│ 日历漂移      │ 1 天           │ 0 天           │ 2 天           │
│              │ → 并回 10 期   │ → 4 期        │ → 并回 20 期   │
│ D（年）       │ 4.68025866…   │ 1.96326685…   │ 8.52302836…   │
│ D_mod        │ 4.61109228…   │ 1.93902899…   │ 8.37644065…   │
│ DV01(面1e6)  │ 461.109228…   │ 193.902899…   │ 837.644065…   │
│ 缺陷值 D      │ 同值           │ 同值           │ 8.38192010…   │
└──────────────┴───────────────┴───────────────┴───────────────┘

容差：实现返回 Decimal 全精度（28 位上下文），常数按全精度书写，久期量级取
1e-18、DV01 量级（×100）取 1e-16 —— 比旧口径（quantize 1e-4）严格若干数量级。
封闭恒等式沿用 1e-24 / 1e-22（Decimal 重结合噪声下限，非口径容差）。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.core_finance.krd import (
    build_krd_position_metrics,
    compute_krd_by_tenor,
    compute_krd_curve_risk,
)
from backend.app.core_finance.risk_tensor import KRD_BUCKET_FALLBACK, _aggregate_krd_values

REPORT_DATE = date(2026, 1, 1)

TOL_DUR = Decimal("1E-18")
TOL_DV01 = Decimal("1E-16")

# --- 独立推算的久期黄金值（见文件头交叉验证说明）---
MAC_5Y = Decimal("4.680258660066125452949021729")
MAC_2Y = Decimal("1.963266853705303128663388787")
MAC_10Y = Decimal("8.523028363791687542432425516")

DMOD_5Y = Decimal("4.611092275927217195023666728")
DMOD_2Y = Decimal("1.939028991313879633247791395")
DMOD_10Y = Decimal("8.376440652375122891825479623")


def _make_bond(
    bond_code: str,
    market_value: str,
    coupon_rate: str,
    ytm: str,
    maturity_date: date,
    face_value: str | None = None,
) -> dict:
    return {
        "bond_code": bond_code,
        "market_value": Decimal(market_value),
        "face_value": Decimal(face_value) if face_value is not None else Decimal(market_value),
        "coupon_rate": Decimal(coupon_rate),
        "yield_to_maturity": Decimal(ytm),
        "maturity_date": maturity_date,
        "report_date": REPORT_DATE,
        "sub_type": "国债",
        "asset_class": "交易性金融资产",
        "coupon_frequency": 2,
    }


BOND_5Y = _make_bond("B5Y", "1000000", "0.0300", "0.0300", date(2031, 1, 1))
BOND_2Y = _make_bond("B2Y", "1000000", "0.0250", "0.0250", date(2028, 1, 1))
BOND_10Y = _make_bond("B10Y", "1000000", "0.0350", "0.0350", date(2036, 1, 1))


class TestGoldenBond5Y:
    """5Y 平价债（3% 票息 / 3% YTM / 半年付 / 面值 1,000,000）。

    剩余天数: 2026-01-01→2031-01-01 = 365+365+366(2028闰)+365+365 = 1826
    years = 1826/365 = 5.00273973…；years×2 = 10.0054795，小数部分 0.0054795
    ≤ 0.01 → 尾数并回整期：n = 10，现金流末期落在 5.0 年整。
    因此本券**退化为整期券**，可用平价债闭式独立求解：
      y = c = 0.03/2 = 0.015
      1.015^2  = 1.030225                              （精确）
      1.015^4  = 1.030225^2 = 1.061363550625           （精确）
      1.015^8  = 1.061363550625^2 = 1.126492586595933789602216391
      1.015^10 = 1.015^8 × 1.015^2 = 1.160540825025150090088369141
      1.015^-10 = 0.861667231722…；1 − 1.015^-10 = 0.138332768278…
      (1+y)/y = 1.015/0.015 = 67.66666666…
      D_p = 67.6666667 × 0.1383327683 = 9.360517320132…（期）
      D   = 9.360517320132…/2 = 4.680258660066125452949021729（年）
    与旧口径同值（旧值 quantize 后为 4.6803）；本次只是不再量化。
      D_mod = D/1.015 = 4.611092275927…
      DV01  = 1,000,000 × D_mod/10,000 = 461.109227592…
    """

    def test_macaulay_duration_golden(self):
        metrics = build_krd_position_metrics([BOND_5Y], report_date=REPORT_DATE)
        assert abs(metrics[0]["duration"] - MAC_5Y) < TOL_DUR

    def test_modified_duration_golden(self):
        metrics = build_krd_position_metrics([BOND_5Y], report_date=REPORT_DATE)
        assert abs(metrics[0]["modified_duration"] - DMOD_5Y) < TOL_DUR

    def test_dv01_golden(self):
        metrics = build_krd_position_metrics([BOND_5Y], report_date=REPORT_DATE)
        assert abs(metrics[0]["dv01"] - Decimal("100") * DMOD_5Y) < TOL_DV01

    def test_krd_5y_bucket_golden(self):
        """单债组合 weight=1 → KRD[5Y] = 1 × D_mod；其余桶为 0。"""
        result = compute_krd_by_tenor([BOND_5Y], report_date=REPORT_DATE)
        by_tenor = {r["tenor"]: r["krd"] for r in result}
        assert abs(by_tenor["5Y"] - DMOD_5Y) < TOL_DUR
        assert all(value == Decimal("0") for tenor, value in by_tenor.items() if tenor != "5Y")

    def test_krd_bucket_dv01_golden(self):
        result = compute_krd_by_tenor([BOND_5Y], report_date=REPORT_DATE)
        by_tenor = {r["tenor"]: r["dv01"] for r in result}
        assert abs(by_tenor["5Y"] - Decimal("100") * DMOD_5Y) < TOL_DV01


class TestGoldenBond2Y:
    """2Y 平价债（2.5% 票息 / 2.5% YTM / 半年付 / 面值 1,000,000）。

    剩余天数: 2026-01-01→2028-01-01 = 365+365 = 730；years = 730/365 = 2（精确）
    years×2 = 4（精确整期，无残端）→ n = 4，平价债闭式：
      y = c = 0.025/2 = 0.0125
      1.0125^2 = 1.02515625                          （精确）
      1.0125^4 = 1.02515625^2 = 1.0509453369140625   （精确）
      1.0125^-4 = 0.951524275217…；1 − 1.0125^-4 = 0.048475724783…
      (1+y)/y = 1.0125/0.0125 = 81（精确）
      D_p = 81 × 0.0484757248 = 3.926533707411…（期）
      D   = 3.926533707411…/2 = 1.963266853705303128663388787（年）
    与旧口径同值（旧值 quantize 后为 1.9633）。
      D_mod = D/1.0125 = 1.939028991314…
    """

    def test_macaulay_duration_golden(self):
        metrics = build_krd_position_metrics([BOND_2Y], report_date=REPORT_DATE)
        assert abs(metrics[0]["duration"] - MAC_2Y) < TOL_DUR

    def test_modified_duration_golden(self):
        metrics = build_krd_position_metrics([BOND_2Y], report_date=REPORT_DATE)
        assert abs(metrics[0]["modified_duration"] - DMOD_2Y) < TOL_DUR


class TestGoldenBond10Y:
    """10Y 平价债（3.5% 票息 / 3.5% YTM / 半年付 / 面值 1,000,000）。

    剩余天数: 2026-01-01→2036-01-01 = 8×365 + 2×366(2028、2032闰) = 3652
      years   = 3652/365 = 10.00547945…
      距 20 个半年整期仅 2 天，落入 ±7 天日历容差 → n = 20。
    报告日恰为付息日，真实计划只剩 20 笔现金流。独立 Decimal(prec=60) 逐笔贴现与
    平价债闭式一致：
      D = 8.523028363791687542432425516（年）
      D_mod = D/1.0175 = 8.376440652375122891825479623
      DV01 = 1,000,000 × D_mod/10,000 = 837.644065237512289…
    缺陷旧值 D=8.381920104429917… 来自虚构的 2 天残端票息，低估 0.141108259362 年。
    """

    def test_macaulay_duration_golden(self):
        metrics = build_krd_position_metrics([BOND_10Y], report_date=REPORT_DATE)
        assert abs(metrics[0]["duration"] - MAC_10Y) < TOL_DUR

    def test_modified_duration_golden(self):
        metrics = build_krd_position_metrics([BOND_10Y], report_date=REPORT_DATE)
        assert abs(metrics[0]["modified_duration"] - DMOD_10Y) < TOL_DUR

    def test_leapday_drift_is_absorbed_by_calendar_tolerance(self):
        """2 个闰日是整期日历漂移，不得被建模成额外残端票息。"""
        whole_period_answer = Decimal("8.523028363791687542432425516")
        metrics = build_krd_position_metrics([BOND_10Y], report_date=REPORT_DATE)
        gap = metrics[0]["duration"] - whole_period_answer
        assert abs(gap) < TOL_DUR


class TestGoldenMixedPortfolioKrd:
    """[BOND_2Y, BOND_10Y] 组合，各市值 1,000,000 → weight 各 0.5。

    复用上面两只债独立推算的 D_mod：
      KRD[2Y]  = 0.5 × 1.939028991314… = 0.969514495657…
      KRD[10Y] = 0.5 × 8.376440652375… = 4.188220326188…
      桶 DV01（ΣDV01，不乘 weight）：
      DV01[2Y]  = 1,000,000 × 1.939028991314…/10,000 = 193.902899131…
      DV01[10Y] = 1,000,000 × 8.376440652375…/10,000 = 837.644065238…
    """

    def test_krd_2y_bucket_golden(self):
        result = compute_krd_by_tenor([BOND_2Y, BOND_10Y], report_date=REPORT_DATE)
        by_tenor = {r["tenor"]: r["krd"] for r in result}
        assert abs(by_tenor["2Y"] - DMOD_2Y / Decimal("2")) < TOL_DUR

    def test_krd_10y_bucket_golden(self):
        result = compute_krd_by_tenor([BOND_2Y, BOND_10Y], report_date=REPORT_DATE)
        by_tenor = {r["tenor"]: r["krd"] for r in result}
        assert abs(by_tenor["10Y"] - DMOD_10Y / Decimal("2")) < TOL_DUR

    def test_bucket_dv01_golden(self):
        result = compute_krd_by_tenor([BOND_2Y, BOND_10Y], report_date=REPORT_DATE)
        by_tenor = {r["tenor"]: r["dv01"] for r in result}
        assert abs(by_tenor["2Y"] - Decimal("100") * DMOD_2Y) < TOL_DV01
        assert abs(by_tenor["10Y"] - Decimal("100") * DMOD_10Y) < TOL_DV01


class TestGoldenKrdClosureAndBoundaries:
    """锁定当前"到期桶久期贡献"语义；这不是标准 KRD，标准化待业务裁决。"""

    def test_bucket_sums_close_to_portfolio_duration_and_dv01(self):
        """两券等市值组合的封闭关系（期望值只由上文独立推算的 D_mod 常数推导）。

        组合修正久期 = 0.5×D_mod(2Y) + 0.5×D_mod(10Y)
        因两券 face=market=1,000,000：
        组合 DV01 = Σ(face×D_mod/10000) = 100×[D_mod(2Y)+D_mod(10Y)]。
        本用例检验的是桶聚合机制（权重、分桶、求和）是否封闭，久期本身由
        TestGoldenBond2Y / TestGoldenBond10Y 独立把关。
        """
        expected_duration = (DMOD_2Y + DMOD_10Y) / Decimal("2")
        expected_dv01 = Decimal("100") * (DMOD_2Y + DMOD_10Y)

        result = compute_krd_curve_risk(
            [BOND_2Y, BOND_10Y],
            report_date=REPORT_DATE,
            scenarios=[],
        )
        krd_sum = sum((row["krd"] for row in result["krd_buckets"]), Decimal("0"))
        bucket_dv01_sum = sum(
            (row["dv01"] for row in result["krd_buckets"]),
            Decimal("0"),
        )

        assert abs(result["portfolio_modified_duration"] - expected_duration) < Decimal("1E-24")
        assert abs(krd_sum - expected_duration) < Decimal("1E-24")
        assert abs(result["portfolio_dv01"] - expected_dv01) < Decimal("1E-22")
        assert abs(bucket_dv01_sum - expected_dv01) < Decimal("1E-22")

    def test_non_standard_2y_tenor_uses_risk_tensor_nearest_bucket_fallback(self):
        """迁移链路把 krd.py 的 2Y 桶映射到 risk tensor 的 3Y 桶。

        ``krd.py`` 自身保留 2Y；下游正式 risk tensor 只支持
        1Y/3Y/5Y/7Y/10Y/30Y，因此当前 ``KRD_BUCKET_FALLBACK`` 规定
        2Y→krd_3y。BOND_2Y 的 DV01 = 100 × D_mod(2Y)。
        """
        expected_dv01 = Decimal("100") * DMOD_2Y
        krd_rows = compute_krd_by_tenor([BOND_2Y], report_date=REPORT_DATE)
        warnings: list[str] = []
        tensor_buckets = _aggregate_krd_values(
            [
                {"tenor_bucket": row["tenor"], "dv01": row["dv01"]}
                for row in krd_rows
            ],
            warnings,
        )

        assert KRD_BUCKET_FALLBACK["2Y"] == "krd_3y"
        assert abs(tensor_buckets["krd_3y"] - expected_dv01) < Decimal("1E-22")
        assert all(
            value == Decimal("0")
            for field, value in tensor_buckets.items()
            if field != "krd_3y"
        )
        assert warnings == ["Non-standard tenor buckets remapped to nearest KRD bucket: 2Y"]

    def test_empty_portfolio_is_exactly_zero(self):
        result = compute_krd_curve_risk([], report_date=REPORT_DATE, scenarios=[])

        assert result["position_metrics"] == []
        assert result["total_market_value"] == Decimal("0")
        assert result["portfolio_duration"] == Decimal("0")
        assert result["portfolio_modified_duration"] == Decimal("0")
        assert result["portfolio_dv01"] == Decimal("0")
        assert result["portfolio_convexity"] == Decimal("0")
        assert result["by_asset_class"] == []
        assert result["scenarios"] == []
        assert [row["tenor"] for row in result["krd_buckets"]] == [
            "1Y",
            "2Y",
            "3Y",
            "5Y",
            "7Y",
            "10Y",
            "15Y",
            "20Y",
            "30Y",
        ]
        assert all(
            row["krd"] == row["dv01"] == row["market_value_weight"] == Decimal("0")
            for row in result["krd_buckets"]
        )
