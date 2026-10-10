"""B4-duration 黄金对照：bond_duration 标准券的手算 golden 测试。

被测实现（只读，不修改）：backend/app/core_finance/bond_duration.py，其
``compute_macaulay_duration`` 委托 ``bond_analytics/common.py`` 的逐期贴现实现。

实现要点（决定本文件期望值与容差的口径）：

- 记 y = ytm/frequency（每期收益率）、c = coupon/frequency（每期票息）、
  T = 剩余年限 = (maturity - report).days / 365（ACT/365F）。
- 按 docs/calc_rules.md 的日期现金流规则：日期齐全且频率能够整除 12 时，按到期日
  锚定真实票息日。非付息日报告日使用各票息日至报告日的 ACT/365 年数；报告日恰在
  票息网格时才用 k/f 年。券5验证前者，不能再用等间隔年度网格作其正式期望。
- 无日期调用保留等间隔兼容口径：N = ceil(T * frequency)，首期为碎期；仅当
  T*frequency 在整期之后不超过 0.01 期时，向下归并这段小残期。
- 第 k 笔现金流（k = 1..N）：
      时间（年）  t_k 按上述日期或无日期规则独立确定
      贴现        PV_k = CF_k / (1 + y) ** (t_k * frequency)
      CF_k = c，末笔 CF_N = c + 1
      MacD(年) = Σ t_k·PV_k / Σ PV_k
  时间权重按年、贴现指数按期，两者一致，故 MacD 直接就是年数，无需再除 frequency。
- **不做量化**：返回 Decimal 全精度（默认 28 位上下文）。
  ``modified_duration_from_macaulay(mac, ytm, frequency)`` = mac / (1 + ytm/frequency)。

W-fi-2026-08 口径修正（本文件期望值随之重算）：
  旧实现用**整期**闭合公式，按 ``to_integral_value()`` 四舍五入取期数
  （"恰好剩 N 个完整付息期"）。而生产入口的剩余年限恒为"剩余天数/365"，几乎从不
  是整数，非整数年的债因此被系统性错误定价（1.4986 年的债按 1 年期算，差 −32%）。
  整期券（券1/券2/券4，T*frequency 恰为整数、w = 1）新旧口径**数值完全一致**，
  故这三只的期望值未变；当时的券5及券6/券7采用等间隔碎期。
  2026-09-05 正式规则增加日期现金流后，券5的有日期入口必须采用真实票息日；原来的
  等间隔期望保留在无日期入口，分别验证两种已明确的口径。

期望值来源与交叉验证（严禁把实现输出复制成期望值）：

1. 无日期等间隔期望由一份不导入任何 MOSS 代码的教科书参考实现算出，该参考同时用四条
   互相独立的路径求解并要求彼此一致：
     A 浮点逐笔现金流求和；
     B Decimal(prec=60) 逐笔求和（不同的算术库）；
     C 几何级数闭合式（无逐笔循环，由 Σvᵏ 与 Σk·vᵏ 解析求和）；
     D 由价格函数的中心差分（Richardson 外推）得 MacD = −(1+y)/P · dP/dy，
       该路全程不构造任何时间加权和。
2. 整期券另与经典年金闭合式
   ``D = (1+y)/y − [(1+y) + N(c−y)] / [c((1+y)^N − 1) + y]`` 对照，一致到 1e-14。
   这同时说明新实现在整期情形下**退化为**教科书闭合式，是旧实现的严格推广。
3. 券5有日期参考直接列出六个 06-14 / 12-14 票息日，以距报告日的天数除以 365
   确定时点，再以 Decimal(prec=60) 逐笔贴现，得到 2.5937323813055 年。
   等间隔时点得到 2.5940452867333 年。两者差异来自时间网格，不能通过放宽容差
   混为同一预期；也不能用已入期天数/本期天数替代正式 ACT/365 口径。

容差约定：实现已不再量化到 1e-4，故容差从旧口径的 5e-4 / 1e-3 收紧到 1e-9
（约束强度提高 5~6 个数量级）。期望值至少保留小数点后 12 位，1e-9 只用于吸收
末位书写截断，禁止为让测试通过而放宽。
"""
from datetime import date
from decimal import Decimal, localcontext

from backend.app.core_finance.bond_duration import (
    compute_macaulay_duration,
    estimate_duration,
    modified_duration_from_macaulay,
)

# 实现返回 Decimal 全精度（28 位上下文），期望值至少保留 12 位小数，
# 容差只需覆盖期望值自身的书写截断。
TOL = Decimal("1E-9")


def _assert_close(actual: Decimal, expected: Decimal, label: str, tol: Decimal = TOL) -> None:
    assert abs(actual - expected) <= tol, (
        f"{label}: actual={actual}, expected={expected}, tol={tol}"
    )


class TestBondDurationGoldens:
    """标准券的 Macaulay / 修正久期黄金对照（期望值全部独立推算并交叉验证）。"""

    def test_bond1_5y_annual_par(self):
        """券1：5Y 年付固息平价券（票息 4% = ytm 4%，frequency=1）——整期券。

        T*frequency = 5 恰为整数 ⇒ 首期残期 w = 1，退化为教科书年金式：
          c = y 时 numer = (1+y) + N·0 = 1+y，denom = y(1+y)^N，
          故 MacD = (1+y)/y · (1 − (1+y)^−N)
            (1+y)/y = 1.04/0.04 = 26
            1.04^5  = 1.2166529024（1.04²=1.0816, ⁴=1.16985856, ⁵=1.2166529024）
            1.04^−5 = 0.821927106...
            MacD    = 26 × (1 − 0.821927106...) = 4.629895224257（年）
          修正久期 = 4.629895224257 / 1.04 = 4.451822331016
        四路参考与经典年金式一致到 1e-14；新旧口径同值（整期）。
        """
        mac = compute_macaulay_duration(
            Decimal("5"), Decimal("0.04"), Decimal("0.04"), frequency=1
        )
        _assert_close(mac, Decimal("4.629895224257"), "券1 Macaulay")

        mod = modified_duration_from_macaulay(mac, Decimal("0.04"), coupon_frequency=1)
        _assert_close(mod, Decimal("4.451822331016"), "券1 修正久期")

    def test_bond2_10y_semiannual(self):
        """券2：10Y 半年付息券（票息 6%，ytm 5%，frequency=2）——整期券。

        c = 0.03/期，y = 0.025/期，N = 20，w = 1：
          (1+y)/y  = 41
          1.025^20 = 1.638616440290
            （1.025²=1.050625, ⁴=1.103812890625, ⁵=1.131408212890625,
              ¹⁰=(⁵)²=1.280084544...,  ²⁰=(¹⁰)²=1.638616440...）
          numer = 1.025 + 20×(0.03−0.025) = 1.125
          denom = 0.03×0.638616440... + 0.025 = 0.044158493...
          MacD(期) = 41 − 1.125/0.044158493... = 15.523587236486
          MacD(年) = 15.523587236486 / 2 = 7.761793618243
          修正久期 = 7.761793618243 / 1.025 = 7.572481578773
        """
        mac = compute_macaulay_duration(
            Decimal("10"), Decimal("0.06"), Decimal("0.05"), frequency=2
        )
        _assert_close(mac, Decimal("7.761793618243"), "券2 Macaulay")

        mod = modified_duration_from_macaulay(mac, Decimal("0.05"), coupon_frequency=2)
        _assert_close(mod, Decimal("7.572481578773"), "券2 修正久期")

    def test_bond3_1y_zero_coupon_discount(self):
        """券3：1Y 贴现券（零票息，ytm 2%，frequency=1）。

        零息券只有到期一笔现金流，MacD = Σt·PV/ΣPV = t = 1.0，与利率无关，
        且为**精确等式**（不是近似）：分子分母的 PV 完全约去。
        新实现无需 ``coupon <= 0`` 特判也能得到该结果——零票息使前 N−1 笔现金流
        为 0，自动只剩到期一笔。
          修正久期 = 1 / 1.02 = 0.980392156863
        """
        mac = compute_macaulay_duration(
            Decimal("1"), Decimal("0"), Decimal("0.02"), frequency=1
        )
        assert mac == Decimal("1"), f"零息券 Macaulay 应精确等于剩余年限，实际 {mac}"

        mod = modified_duration_from_macaulay(mac, Decimal("0.02"), coupon_frequency=1)
        _assert_close(mod, Decimal("0.980392156863"), "券3 修正久期")

    def test_bond4_30y_low_coupon(self):
        """券4：30Y 长久期低票息券（票息 2%，ytm 3%，frequency=1）——整期券。

        c = 0.02，y = 0.03，N = 30，w = 1：
          (1+y)/y = 34.333333333...
          1.03^30 = 2.427262471...
            （1.03⁵=1.159274074..., ¹⁰=(⁵)²=1.343916379...,
              ²⁰=(¹⁰)²=1.806111234..., ³⁰=²⁰×¹⁰=2.427262471...）
          numer = 1.03 + 30×(0.02−0.03) = 0.73
          denom = 0.02×1.427262471... + 0.03 = 0.058545249...
          MacD  = 34.333333333... − 0.73/0.058545249... = 21.864345547224
          修正久期 = 21.864345547224 / 1.03 = 21.227519948761
        """
        mac = compute_macaulay_duration(
            Decimal("30"), Decimal("0.02"), Decimal("0.03"), frequency=1
        )
        _assert_close(mac, Decimal("21.864345547224"), "券4 Macaulay")

        mod = modified_duration_from_macaulay(mac, Decimal("0.03"), coupon_frequency=1)
        _assert_close(mod, Decimal("21.227519948761"), "券4 修正久期")

    def test_bond5_fractional_period_settlement(self):
        """券5：碎期券——结算日在两付息日之间（半年付息，票息 4%，ytm 5%）。

        券面设定：到期日 2028-12-14，付息日按到期日锚定为每年 06-14 / 12-14；
        结算/报告日 2026-03-20 位于上一付息日 2025-12-14 与下一付息日 2026-06-14
        之间（已入期 96 天 / 本期 182 天），构成真实碎期。

        独立现金流表（每 1 面值，日期按券面约定显式列出）：
          付息日 = 2026-06-14, 2026-12-14, 2027-06-14,
                   2027-12-14, 2028-06-14, 2028-12-14
          天数 d = 86, 269, 451, 634, 817, 1000（均距报告日）
          CF     = 0.02, 0.02, 0.02, 0.02, 0.02, 1.02
          t = d/365，PV = CF / 1.025^(2t)，不调用生产排期或贴现函数。
          MacD = Σt·PV / ΣPV = 2.5937323813055001121004506456976577 年
          修正久期 = MacD / 1.025 = 2.5304706159078049874150738006806417 年

        原期望 2.594045286733 来自 T−(N−k)/2 的等间隔网格，仍由下一用例验证
        无日期兼容入口；其与本例的差额约 0.0003129054 年，不属于舍入误差。
        """
        maturity = date(2028, 12, 14)
        report = date(2026, 3, 20)
        # 锚定 ACT/365F 天数，防止日期 fixture 被无意改动
        assert (maturity - report).days == 1000
        payment_dates = [
            date(2026, 6, 14), date(2026, 12, 14), date(2027, 6, 14),
            date(2027, 12, 14), date(2028, 6, 14), date(2028, 12, 14),
        ]
        payment_days = [(payment - report).days for payment in payment_dates]
        assert payment_days == [86, 269, 451, 634, 817, 1000]
        expected_mac = Decimal("2.5937323813055001121004506456976577")
        expected_mod = Decimal("2.5304706159078049874150738006806417")
        with localcontext() as context:
            context.prec = 60
            times = [Decimal(days) / Decimal(365) for days in payment_days]
            cashflows = [Decimal("0.02")] * 5 + [Decimal("1.02")]
            present_values = [
                cf / Decimal("1.025") ** (2 * time)
                for cf, time in zip(cashflows, times)
            ]
            reference = sum(t * pv for t, pv in zip(times, present_values)) / sum(present_values)
            _assert_close(reference, expected_mac, "券5 独立日期现金流参考")
            _assert_close(reference / Decimal("1.025"), expected_mod, "券5 独立修正久期参考")

        mac = estimate_duration(
            maturity_date=maturity,
            report_date=report,
            coupon_rate=Decimal("0.04"),
            bond_code="230012.IB",
            ytm=Decimal("0.05"),
            coupon_frequency=2,
        )
        _assert_close(mac, expected_mac, "券5 Macaulay")

        mod = modified_duration_from_macaulay(mac, Decimal("0.05"), coupon_frequency=2)
        _assert_close(mod, expected_mod, "券5 修正久期")

    def test_bond5_without_dates_retains_equal_spacing_reference(self):
        """无日期兼容入口：T=1000/365，N=6，t_k=T−(6−k)/2。

        六笔现金流为 0.02 ×5、1.02，以 1.025^(2t) 贴现。
        独立参考的 MacD 为 2.5940452867332643535705831046253662 年，
        修正久期为 2.5307758894958676620200810776832841 年。
        保留原有数值，防止日期入口修正误改无日期兼容语义。
        """
        mac = compute_macaulay_duration(
            Decimal(1000) / Decimal(365), Decimal("0.04"), Decimal("0.05"), frequency=2
        )
        _assert_close(mac, Decimal("2.594045286733"), "券5 无日期 Macaulay")
        mod = modified_duration_from_macaulay(mac, Decimal("0.05"), coupon_frequency=2)
        _assert_close(mod, Decimal("2.530775889496"), "券5 无日期修正久期")

    def test_bond6_547_days_annual_regression(self):
        """券6：547 天年付券（票息 3% = ytm 3%）——W-fi-2026-08 的标志性回归用例。

        这是旧实现错得最狠的一档：T×1 = 1.4986301370 期，旧代码
        ``to_integral_value()`` 四舍五入到 **1** 期，直接把一只 1.5 年期的债按
        1 年期定价，返回 1.00000 年——低估 0.46950 年（−32%）。

        正确现金流（T = 547/365 = 1.4986301370，N = ceil = 2，w = 0.4986301370 期）：
          t₁ = 0.4986301370 年，CF = 0.03，贴现 (1.03)^0.4986301370
          t₂ = 1.4986301370 年，CF = 1.03，贴现 (1.03)^1.4986301370
          MacD = (t₁·PV₁ + t₂·PV₂) / (PV₁ + PV₂) = 1.469503923394（年）
          修正久期 = 1.469503923394 / 1.03 = 1.426702838247

        本用例存在的意义：整期券（券1/券2/券4）在新旧口径下同值，无法拦截该 bug；
        必须有一只 T×frequency 明显非整数的券把碎期路径钉死。
        """
        years = Decimal("547") / Decimal("365")
        mac = compute_macaulay_duration(
            years, Decimal("0.03"), Decimal("0.03"), frequency=1
        )
        _assert_close(mac, Decimal("1.469503923394"), "券6 Macaulay")

        # 旧口径会返回 1.00000；显式钉死这条下界，防止整期取整回潮。
        assert mac > Decimal("1.4"), (
            f"券6 久期 {mac} 退回整期取整口径（旧错误值为 1.00000）"
        )

        mod = modified_duration_from_macaulay(mac, Decimal("0.03"), coupon_frequency=1)
        _assert_close(mod, Decimal("1.426702838247"), "券6 修正久期")

    def test_bond7_1600_days_semiannual_regression(self):
        """券7：1600 天半年付券（票息 3.25%，ytm 2.80%）——碎期 + 溢价券。

        票息 ≠ ytm 且 frequency=2，覆盖券6（c = y、年付）未覆盖的组合。
          T = 1600/365 = 4.3835616438 年，T×2 = 8.7671232877
          ⇒ N = ceil = 9 期，w = 0.7671232877 期 = 0.3835616438 年
          c = 0.01625/期，y = 0.014/期
          9 笔现金流，t = 0.3835616 + k/2（k = 0..8），末笔 CF = 1.01625
          MacD = 4.109385813813（年）
          修正久期 = 4.109385813813 / 1.014 = 4.052648731571
        旧整期口径下 to_integral_value(8.7671) = 9 期、按"9 个完整半年期"
        （即 4.5 年期券）计算，与真实 4.3836 年期不符。
        """
        years = Decimal("1600") / Decimal("365")
        mac = compute_macaulay_duration(
            years, Decimal("0.0325"), Decimal("0.028"), frequency=2
        )
        _assert_close(mac, Decimal("4.109385813813"), "券7 Macaulay")

        mod = modified_duration_from_macaulay(mac, Decimal("0.028"), coupon_frequency=2)
        _assert_close(mod, Decimal("4.052648731571"), "券7 修正久期")

    def test_macaulay_never_exceeds_remaining_years(self):
        """结构性不变量：付息券的 Macaulay 久期不得超过剩余年限。

        旧实现靠 ``mac > years → return years`` 的护栏兜住整期取整向上取整时
        算出的超限值；护栏一触发就退回剩余年限，把错误伪装成"零息券"。
        新实现下该不等式应当**自然成立**，不依赖任何护栏。
        """
        for days in (91, 200, 365, 547, 912, 1600, 3650, 7300, 10950):
            years = Decimal(str(days)) / Decimal("365")
            for coupon, ytm, freq in (
                (Decimal("0.03"), Decimal("0.03"), 1),
                (Decimal("0.0325"), Decimal("0.028"), 2),
                (Decimal("0.06"), Decimal("0.09"), 2),
                (Decimal("0.005"), Decimal("0.0005"), 1),
            ):
                mac = compute_macaulay_duration(years, coupon, ytm, frequency=freq)
                assert Decimal("0") < mac <= years + Decimal("1E-20"), (
                    f"days={days} c={coupon} ytm={ytm} f={freq}: mac={mac} years={years}"
                )
