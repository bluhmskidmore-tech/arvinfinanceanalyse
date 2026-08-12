"""B4-duration 黄金对照：bond_duration 五只标准券的手算 golden 测试。

被测实现（只读，不修改）：backend/app/core_finance/bond_duration.py

实现要点（决定本文件期望值与容差的口径）：

- ``compute_macaulay_duration(years, coupon, ytm, frequency)`` 为整期闭合公式，
  记每期收益率 y = ytm/frequency、每期票息 c = coupon/frequency、
  整期数 N = to_integral_value(years * frequency)：

      MacD(期) = (1+y)/y - [(1+y) + N*(c-y)] / [c*((1+y)^N - 1) + y]
      MacD(年) = MacD(期) / frequency

  正常路径结果做 ``quantize(Decimal("0.0001"), ROUND_HALF_UP)``（1e-4 量化）；
  零息券（coupon <= 0）直接返回剩余年限，不量化。

- ``estimate_duration`` / ``_estimate_macaulay_duration_years`` 的剩余年限
  = (maturity - report).days / 365，即 ACT/365F；整期数按 Decimal 默认上下文
  ROUND_HALF_EVEN 取整。实现不做应计利息扣减，也不做碎期（stub）精确折现，
  即把债券近似成"恰好剩 N 个完整付息期"。

- ``modified_duration_from_macaulay(mac, ytm, frequency)``
  = mac / (1 + ytm/frequency)，不量化。

容差约定（与实现内部 1e-4 量化精度对齐，禁止 1e-8 级容差）：

- 标准券（券1~券4）：TOL_STD = 5e-4。
- 碎期券（券5）：叠加 ACT/365F 年化与整期取整近似，单独放宽至 TOL_FRAC = 1e-3，
  day-count 约定见券5 docstring。

全部黄金值均独立手算：按闭合公式逐步代入（中间量写在各测试注释中），
并对券2/券4 用现金流逐笔折现做过交叉核对；不使用被测实现的输出作为期望值。
"""
from datetime import date
from decimal import Decimal

from backend.app.core_finance.bond_duration import (
    compute_macaulay_duration,
    estimate_duration,
    modified_duration_from_macaulay,
)

TOL_STD = Decimal("0.0005")  # 标准券：对齐实现 quantize(1e-4) 精度
TOL_FRAC = Decimal("0.001")  # 碎期券：ACT/365F + 整期取整近似，单独放宽


def _assert_close(actual: Decimal, expected: Decimal, tol: Decimal, label: str) -> None:
    assert abs(actual - expected) <= tol, (
        f"{label}: actual={actual}, expected={expected}, tol={tol}"
    )


class TestBondDurationGoldens:
    """五只标准券的 Macaulay / 修正久期黄金对照（期望值全部独立手算）。"""

    def test_bond1_5y_annual_par(self):
        """券1：5Y 年付固息平价券（票息 4% = ytm 4%，frequency=1）。

        手算过程（c = y = 0.04，N = 5）：
          c = y 时通用式化简：numer = (1+y) + N*0 = 1+y，
          denom = y*((1+y)^N - 1) + y = y*(1+y)^N，
          故 MacD = (1+y)/y * (1 - (1+y)^-N)。
            (1+y)/y  = 1.04 / 0.04 = 26
            1.04^5   = 1.2166529024（精确：1.04^2=1.0816, ^4=1.16985856, ^5=1.2166529024）
            1.04^-5  = 1 / 1.2166529024 = 0.8219271068
            MacD     = 26 * (1 - 0.8219271068) = 26 * 0.1780728932 = 4.6298952（年）
          实现量化到 1e-4 后为 4.6299。
          修正久期 = MacD / (1 + 0.04/1) = 4.6298952 / 1.04 = 4.4518223
        """
        mac = compute_macaulay_duration(
            Decimal("5"), Decimal("0.04"), Decimal("0.04"), frequency=1
        )
        _assert_close(mac, Decimal("4.6298952"), TOL_STD, "券1 Macaulay")

        mod = modified_duration_from_macaulay(mac, Decimal("0.04"), coupon_frequency=1)
        _assert_close(mod, Decimal("4.4518223"), TOL_STD, "券1 修正久期")

    def test_bond2_10y_semiannual(self):
        """券2：10Y 半年付息券（票息 6%，ytm 5%，frequency=2）。

        手算过程（c = 0.06/2 = 0.03/期，y = 0.05/2 = 0.025/期，N = 10*2 = 20）：
          (1+y)/y  = 1.025 / 0.025 = 41
          1.025^20 = 1.6386164403
            （1.025^2=1.050625, ^4=1.103812890625, ^5=1.131408212890625,
              ^10 = (^5)^2 = 1.2800845442, ^20 = (^10)^2 = 1.6386164403）
          numer = 1.025 + 20*(0.03-0.025) = 1.125
          denom = 0.03*(1.6386164403-1) + 0.025 = 0.0191584932 + 0.025 = 0.0441584932
          term2 = 1.125 / 0.0441584932 = 25.4764128
          MacD(期) = 41 - 25.4764128 = 15.5235872
          MacD(年) = 15.5235872 / 2 = 7.7617936 → 实现量化后 7.7618
          修正久期 = 7.7617936 / (1 + 0.05/2) = 7.7617936 / 1.025 = 7.5724815
        交叉核对（现金流直算，每 1 面值）：v = 1/1.025，v^20 = 0.6102709，
          Price = 0.03*15.5891624 + 0.6102709 = 1.0779458，
          Σ t*CF*v^t = 0.03*150.9388 + 20*0.6102709 = 16.7335828（期）
          → 16.7335828 / 1.0779458 = 15.523584 期 ≈ 15.5235872 ✓
        """
        mac = compute_macaulay_duration(
            Decimal("10"), Decimal("0.06"), Decimal("0.05"), frequency=2
        )
        _assert_close(mac, Decimal("7.7617936"), TOL_STD, "券2 Macaulay")

        mod = modified_duration_from_macaulay(mac, Decimal("0.05"), coupon_frequency=2)
        _assert_close(mod, Decimal("7.5724815"), TOL_STD, "券2 修正久期")

    def test_bond3_1y_zero_coupon_discount(self):
        """券3：1Y 贴现券（零票息，ytm 2%，frequency=1）。

        手算过程：
          零息券只有到期一笔现金流，时间权重恒为 1：
            MacD = 剩余年限 = 1.0000（精确恒等，与利率无关）
          实现路径：coupon_rate <= 0 → 直接返回 years_to_maturity（未量化）。
          修正久期 = 1.0 / (1 + 0.02/1) = 1 / 1.02 = 0.9803922（0.98039215686...）
        """
        mac = compute_macaulay_duration(
            Decimal("1"), Decimal("0"), Decimal("0.02"), frequency=1
        )
        _assert_close(mac, Decimal("1"), TOL_STD, "券3 Macaulay")

        mod = modified_duration_from_macaulay(mac, Decimal("0.02"), coupon_frequency=1)
        _assert_close(mod, Decimal("0.9803922"), TOL_STD, "券3 修正久期")

    def test_bond4_30y_low_coupon(self):
        """券4：30Y 长久期低票息券（票息 2%，ytm 3%，frequency=1）。

        手算过程（c = 0.02，y = 0.03，N = 30）：
          (1+y)/y = 1.03 / 0.03 = 34.3333333
          1.03^30 = 2.4272624711
            （1.03^5=1.1592740743, ^10 = (^5)^2 = 1.3439163794,
              ^20 = (^10)^2 = 1.8061112346, ^30 = ^20 * ^10 = 2.4272624711）
          numer = 1.03 + 30*(0.02-0.03) = 1.03 - 0.30 = 0.73
          denom = 0.02*(2.4272624711-1) + 0.03 = 0.0285452494 + 0.03 = 0.0585452494
          term2 = 0.73 / 0.0585452494 = 12.4689878
          MacD = 34.3333333 - 12.4689878 = 21.8643455 → 实现量化后 21.8643
          修正久期 = 21.8643455 / 1.03 = 21.2275199
        交叉核对（现金流直算，每 100 面值，粗算到 1e-3）：
          Price = 2*19.6004413 + 100*0.4119868 = 80.3996，
          Σ t*CF*v^t = 2*260.967 + 3000*0.4119868 = 1757.894
          → 1757.894 / 80.3996 = 21.864 ✓
        """
        mac = compute_macaulay_duration(
            Decimal("30"), Decimal("0.02"), Decimal("0.03"), frequency=1
        )
        _assert_close(mac, Decimal("21.8643455"), TOL_STD, "券4 Macaulay")

        mod = modified_duration_from_macaulay(mac, Decimal("0.03"), coupon_frequency=1)
        _assert_close(mod, Decimal("21.2275199"), TOL_STD, "券4 修正久期")

    def test_bond5_fractional_period_settlement(self):
        """券5：碎期券——结算日在两付息日之间（半年付息，票息 4%，ytm 5%）。

        券面设定：到期日 2028-12-14，付息日按到期日锚定为每年 06-14 / 12-14；
        结算/报告日 2026-03-20 位于上一付息日 2025-12-14 与下一付息日 2026-06-14
        之间（已入期 96 天 / 本期 182 天，约 0.53 期），构成真实碎期。

        实现的 day-count / 应计约定（本 golden 与实现保持一致，非市场碎期惯例）：
          - 剩余年限按 ACT/365F：(2028-12-14 − 2026-03-20) = 1000 天
            → years = 1000/365 = 2.7397260
          - 整期数 N = to_integral_value(years*2) = to_integral_value(5.4794521) = 5
            （Decimal 默认 ROUND_HALF_EVEN；5.4795 < 5.5，取整无歧义）
          - 不扣应计利息、不做碎期 stub 折现：按"恰好剩 5 个完整半年期"的
            整期闭合公式近似。
        手算过程（c = 0.04/2 = 0.02/期，y = 0.05/2 = 0.025/期，N = 5）：
          (1+y)/y = 41
          1.025^5 = 1.131408212890625（精确）
          numer = 1.025 + 5*(0.02-0.025) = 1.000
          denom = 0.02*0.131408212890625 + 0.025 = 0.0276281643
          term2 = 1 / 0.0276281643 = 36.1949491
          MacD(期) = 41 - 36.1949491 = 4.8050509 → MacD(年) = 2.4025254
          （实现的上限保护 mac > years 才回退为 years：2.4025 < 2.7397，不触发）
          实现量化后 2.4025。
          修正久期 = 2.4025254 / (1 + 0.05/2) = 2.4025254 / 1.025 = 2.3439273
        容差：碎期路径取 TOL_FRAC = 1e-3。
        """
        maturity = date(2028, 12, 14)
        report = date(2026, 3, 20)
        # 锚定 ACT/365F 天数，防止日期 fixture 被无意改动
        assert (maturity - report).days == 1000

        mac = estimate_duration(
            maturity_date=maturity,
            report_date=report,
            coupon_rate=Decimal("0.04"),
            bond_code="230012.IB",
            ytm=Decimal("0.05"),
            coupon_frequency=2,
        )
        _assert_close(mac, Decimal("2.4025254"), TOL_FRAC, "券5 Macaulay")

        mod = modified_duration_from_macaulay(mac, Decimal("0.05"), coupon_frequency=2)
        _assert_close(mod, Decimal("2.3439273"), TOL_FRAC, "券5 修正久期")
