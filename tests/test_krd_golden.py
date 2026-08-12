"""
Golden-value tests for backend.app.core_finance.krd (B4-KRD).

所有期望常数均为独立手算黄金值：不使用被测函数的任何输出作为期望值。
重要口径声明：当前实现只是把“市值权重 × 修正久期”按到期桶聚合，没有逐节点
bump-and-reprice。**这不是标准 KRD，标准化待业务裁决。**
手算用三条相互独立的数学路径交叉核对（差异 < 1e-26，Decimal 28 位上下文）：

  M1 一般闭式:   D_p = (1+y)/y - [1+y+n(c-y)] / [c((1+y)^n - 1) + y]
  M2 平价债闭式: D_p = (1+y)/y * (1 - (1+y)^(-n))          （c=y 时与 M1 等价）
  M3 现金流表:   D_p = Σ t·CF_t·v^t / Σ CF_t·v^t,  v = 1/(1+y)

符号约定（与实现口径一致，但数值全部独立推导）：
  f      = 付息频率（每年次数）
  c      = 每期票息率 = coupon_rate / f
  y      = 每期收益率 = ytm / f
  n      = 期数 = round(years_to_maturity × f)   （半进位取偶）
  D_p    = Macaulay 久期（以期数计）
  D      = Macaulay 久期（年）= D_p / f，再 quantize 到 0.0001（HALF_UP）
  D_mod  = 修正久期 = D / (1 + y)                （quantize 后的 D 参与除法，本身不再 quantize）
  DV01   = face_value × D_mod / 10000            （元/bp，不 quantize）
  KRD[b] = Σ_{券∈桶 b} weight × D_mod            （weight = 市值/组合总市值）

三个标准场景（report_date = 2026-01-01，半年付息 f=2，票息=YTM 即平价债）：

┌────────────┬──────────────┬──────────────┬──────────────┐
│            │ BOND_5Y      │ BOND_2Y      │ BOND_10Y     │
│            │ 3% / 3%      │ 2.5% / 2.5%  │ 3.5% / 3.5%  │
├────────────┼──────────────┼──────────────┼──────────────┤
│ 到期日      │ 2031-01-01   │ 2028-01-01   │ 2036-01-01   │
│ 剩余天数    │ 1826         │ 730          │ 3652         │
│ years=天/365│ 5.00273973…  │ 2（精确）     │ 10.00547945… │
│ n=round(×2) │ 10           │ 4            │ 20           │
│ c = y      │ 0.015        │ 0.0125       │ 0.0175       │
│ (1+y)^n    │ 1.16054083…  │ 1.05094534…  │ 1.41477820…  │
│ D_p（期）   │ 9.36051732…  │ 3.92653371…  │ 17.04605673… │
│ D 原始（年）│ 4.68025866…  │ 1.96326685…  │ 8.52302836…  │
│ D quantized│ 4.6803       │ 1.9633       │ 8.5230       │
│ D_mod      │ 4.61113300…  │ 1.93906173…  │ 8.37641278…  │
│ DV01(面1e6)│ 461.1133…    │ 193.9062…    │ 837.6413…    │
└────────────┴──────────────┴──────────────┴──────────────┘

逐步手算细节见各测试 docstring。容差与实现内 quantize 精度对齐：
Macaulay 久期是 quantize("0.0001") 的决定性输出，用精确相等；修正久期/KRD
用 1e-4 容差；DV01 因 face=1e6 将修正久期放大 100 倍，容差 0.01。
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

    手算（平价债闭式 M2，独立于实现）：
      剩余天数: 2026-01-01→2031-01-01 = 365+365+366(2028闰)+365+365 = 1826
      years = 1826/365 = 5.00273973…;  n = round(5.00273973…×2) = round(10.0055) = 10
      y = c = 0.03/2 = 0.015
      (1.015)^10 逐步平方:
        1.015^2  = 1.030225                （精确）
        1.015^4  = 1.030225^2 = 1.061363550625        （精确）
        1.015^8  = 1.061363550625^2 = 1.126492586595933789602216391
        1.015^10 = 1.015^8 × 1.015^2 = 1.160540825025150090088369141
      (1.015)^-10 = 1/1.16054082502515… = 0.861667231722…
      1 - (1.015)^-10 = 0.138332768278…
      (1+y)/y = 1.015/0.015 = 67.66666666…
      D_p = 67.6666667 × 0.1383327683 = 9.360517320132…（期）
      D 原始 = 9.360517320132…/2 = 4.680258660066…（年）
      D = quantize(4.6802586601, 0.0001, HALF_UP) = 4.6803
        （弃掉部分 0.0000586601 > 0.00005 → 进位）
      D_mod = 4.6803/1.015 = 46803/10150 = 4.611133004926108…
      DV01 = 1,000,000 × 4.611133004926…/10,000 = 461.1133004926…
    """

    def test_macaulay_duration_golden(self):
        metrics = build_krd_position_metrics([BOND_5Y], report_date=REPORT_DATE)
        assert metrics[0]["duration"] == Decimal("4.6803")

    def test_modified_duration_golden(self):
        metrics = build_krd_position_metrics([BOND_5Y], report_date=REPORT_DATE)
        assert abs(metrics[0]["modified_duration"] - Decimal("4.61113300")) < Decimal("0.0001")

    def test_dv01_golden(self):
        metrics = build_krd_position_metrics([BOND_5Y], report_date=REPORT_DATE)
        assert abs(metrics[0]["dv01"] - Decimal("461.1133")) < Decimal("0.01")

    def test_krd_5y_bucket_golden(self):
        """单债组合 weight=1 → KRD[5Y] = 1 × D_mod = 4.61113300…；其余桶为 0。"""
        result = compute_krd_by_tenor([BOND_5Y], report_date=REPORT_DATE)
        by_tenor = {r["tenor"]: r["krd"] for r in result}
        assert abs(by_tenor["5Y"] - Decimal("4.61113300")) < Decimal("0.0001")
        assert all(value == Decimal("0") for tenor, value in by_tenor.items() if tenor != "5Y")

    def test_krd_bucket_dv01_golden(self):
        result = compute_krd_by_tenor([BOND_5Y], report_date=REPORT_DATE)
        by_tenor = {r["tenor"]: r["dv01"] for r in result}
        assert abs(by_tenor["5Y"] - Decimal("461.1133")) < Decimal("0.01")


class TestGoldenBond2Y:
    """2Y 平价债（2.5% 票息 / 2.5% YTM / 半年付 / 面值 1,000,000）。

    手算（平价债闭式 M2）：
      剩余天数: 2026-01-01→2028-01-01 = 365+365 = 730;  years = 730/365 = 2（精确）
      n = 2×2 = 4;  y = c = 0.025/2 = 0.0125
      (1.0125)^4 逐步平方:
        1.0125^2 = 1.02515625                          （精确）
        1.0125^4 = 1.02515625^2 = 1.0509453369140625   （精确）
      (1.0125)^-4 = 1/1.0509453369140625 = 0.951524275217…
      1 - (1.0125)^-4 = 0.048475724783…
      (1+y)/y = 1.0125/0.0125 = 81（精确）
      D_p = 81 × 0.0484757248 = 3.926533707411…（期）
      D 原始 = 3.926533707411…/2 = 1.963266853706…（年）
      D = quantize(1.9632668537, 0.0001, HALF_UP) = 1.9633
        （弃掉部分 0.0000668537 > 0.00005 → 进位）
      D_mod = 1.9633/1.0125 = 19633/10125 = 1.939061728395…
    """

    def test_macaulay_duration_golden(self):
        metrics = build_krd_position_metrics([BOND_2Y], report_date=REPORT_DATE)
        assert metrics[0]["duration"] == Decimal("1.9633")

    def test_modified_duration_golden(self):
        metrics = build_krd_position_metrics([BOND_2Y], report_date=REPORT_DATE)
        assert abs(metrics[0]["modified_duration"] - Decimal("1.93906173")) < Decimal("0.0001")


class TestGoldenBond10Y:
    """10Y 平价债（3.5% 票息 / 3.5% YTM / 半年付 / 面值 1,000,000）。

    手算（平价债闭式 M2）：
      剩余天数: 2026-01-01→2036-01-01 = 8×365 + 2×366(2028、2032闰) = 3652
      years = 3652/365 = 10.00547945…;  n = round(10.00547945…×2) = round(20.011) = 20
      y = c = 0.035/2 = 0.0175
      (1.0175)^20 逐步平方:
        1.0175^2  = 1.03530625                         （精确）
        1.0175^4  = 1.03530625^2 = 1.0718590312890625  （精确）
        1.0175^8  = 1.0718590312890625^2 = 1.148881783491329…
        1.0175^16 = 1.148881783491329…^2 = 1.319929349332943…
        1.0175^20 = 1.0175^16 × 1.0175^4 = 1.414778195755798…
      (1.0175)^-20 = 1/1.41477819575580… = 0.706824577167…
      1 - (1.0175)^-20 = 0.293175422833…
      (1+y)/y = 1.0175/0.0175 = 58.142857142857…
      D_p = 58.1428571 × 0.2931754228 = 17.046056727583…（期）
      D 原始 = 17.046056727583…/2 = 8.523028363792…（年）
      D = quantize(8.5230283638, 0.0001, HALF_UP) = 8.5230
        （弃掉部分 0.0000283638 < 0.00005 → 舍去）
      D_mod = 8.5230/1.0175 = 85230/10175 = 8.376412776413…
    """

    def test_macaulay_duration_golden(self):
        metrics = build_krd_position_metrics([BOND_10Y], report_date=REPORT_DATE)
        assert metrics[0]["duration"] == Decimal("8.5230")

    def test_modified_duration_golden(self):
        metrics = build_krd_position_metrics([BOND_10Y], report_date=REPORT_DATE)
        assert abs(metrics[0]["modified_duration"] - Decimal("8.37641278")) < Decimal("0.0001")


class TestGoldenMixedPortfolioKrd:
    """[BOND_2Y, BOND_10Y] 组合，各市值 1,000,000 → weight 各 0.5。

    手算（复用上面两只债的独立手算 D_mod）：
      KRD[2Y]  = 0.5 × 1.939061728395… = 0.969530864198…
      KRD[10Y] = 0.5 × 8.376412776413… = 4.188206388206…
      桶 DV01（ΣDV01，不乘 weight）：
      DV01[2Y]  = 1,000,000 × 1.939061728395…/10,000 = 193.9061728395…
      DV01[10Y] = 1,000,000 × 8.376412776413…/10,000 = 837.6412776413…
    """

    def test_krd_2y_bucket_golden(self):
        result = compute_krd_by_tenor([BOND_2Y, BOND_10Y], report_date=REPORT_DATE)
        by_tenor = {r["tenor"]: r["krd"] for r in result}
        assert abs(by_tenor["2Y"] - Decimal("0.96953086")) < Decimal("0.0001")

    def test_krd_10y_bucket_golden(self):
        result = compute_krd_by_tenor([BOND_2Y, BOND_10Y], report_date=REPORT_DATE)
        by_tenor = {r["tenor"]: r["krd"] for r in result}
        assert abs(by_tenor["10Y"] - Decimal("4.18820639")) < Decimal("0.0001")

    def test_bucket_dv01_golden(self):
        result = compute_krd_by_tenor([BOND_2Y, BOND_10Y], report_date=REPORT_DATE)
        by_tenor = {r["tenor"]: r["dv01"] for r in result}
        assert abs(by_tenor["2Y"] - Decimal("193.9062")) < Decimal("0.01")
        assert abs(by_tenor["10Y"] - Decimal("837.6413")) < Decimal("0.01")


class TestGoldenKrdClosureAndBoundaries:
    """锁定当前“到期桶久期贡献”语义；这不是标准 KRD，标准化待业务裁决。"""

    def test_bucket_sums_close_to_portfolio_duration_and_dv01(self):
        """两券等市值组合的封闭关系（期望值只由上文手算分数推导）。

        D_mod(2Y)  = 19633 / 10125
        D_mod(10Y) = 85230 / 10175
        组合修正久期 = 0.5×D_mod(2Y) + 0.5×D_mod(10Y)
        因两券 face=market=1,000,000：
        组合 DV01 = Σ(face×D_mod/10000) = 100×[D_mod(2Y)+D_mod(10Y)]。
        """
        dmod_2y = Decimal("19633") / Decimal("10125")
        dmod_10y = Decimal("85230") / Decimal("10175")
        expected_duration = (dmod_2y + dmod_10y) / Decimal("2")
        expected_dv01 = Decimal("100") * (dmod_2y + dmod_10y)

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
        2Y→krd_3y。BOND_2Y 的手算 DV01 = 100×19633/10125。
        """
        expected_dv01 = Decimal("100") * Decimal("19633") / Decimal("10125")
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
