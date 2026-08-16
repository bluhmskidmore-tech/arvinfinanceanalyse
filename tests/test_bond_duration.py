"""
Unit tests for bond_duration.py — Macaulay duration, modified duration, convexity.

W-fi-2026-08：``compute_macaulay_duration`` 已改为委托
``bond_analytics.common``（逐期贴现、ROUND_CEILING 取期数、首期按残期定位），
不再自带整期闭合公式。本文件原先只有 ``> 0`` / ``<= years`` 之类的性质断言，
在修复前后**同样通过**，对该 bug 毫无拦截力；故下列用例改为钉死精确值，并补充
碎期路径与两条实现的口径一致性用例。

期望值不取自被测实现，而由独立教科书参考（浮点直算 / Decimal(prec=60) 直算 /
几何级数闭合式 / 由 dP/dy 数值导数反推，四路交叉一致）算出，详见
tests/test_bond_duration_goldens.py 文件头的说明。容差 1e-9 仅吸收期望值书写截断。
"""
import logging
from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance.bond_analytics.common import (
    DURATION_TERM_MATURITY_UNAVAILABLE,
    DURATION_TERM_NO_REMAINING_TERM,
    DURATION_UNAVAILABLE,
    MISSING_MATURITY_RULE_ID,
    estimate_convexity,
)
from backend.app.core_finance.bond_analytics.common import (
    compute_macaulay_duration as shared_compute_macaulay_duration,
)
from backend.app.core_finance.bond_duration import (
    _estimate_macaulay_duration_years,
    compute_macaulay_duration,
    estimate_convexity_bond,
    estimate_duration,
    estimate_duration_with_status,
    infer_accounting_class,
    modified_duration_from_macaulay,
)

TOL = Decimal("1E-9")


class TestComputeMacaulayDuration:
    """Test Macaulay duration (delegated cash-flow discounting)."""

    def test_standard_coupon_bond(self):
        """Standard coupon bond with positive yield — 5 whole annual periods.

        整期券，退化为经典年金式；参考值 4.620322347961272709…
        """
        years = Decimal("5.0")
        coupon = Decimal("0.04")  # 4%
        ytm = Decimal("0.05")  # 5%
        frequency = 1

        duration = compute_macaulay_duration(years, coupon, ytm, frequency)

        assert abs(duration - Decimal("4.620322347961")) <= TOL
        assert duration < years  # Duration < maturity for coupon bonds

    def test_zero_coupon_bond(self):
        """Zero coupon bond: duration = maturity.

        新实现无 ``coupon <= 0`` 特判：零票息令前 N−1 笔现金流为 0，只剩到期一笔，
        Σt·PV/ΣPV 自动约去贴现因子，精确等于剩余年限。
        """
        years = Decimal("10.0")
        coupon = Decimal("0.0")
        ytm = Decimal("0.05")
        frequency = 1

        duration = compute_macaulay_duration(years, coupon, ytm, frequency)

        assert duration == years

    def test_matured_bond(self):
        """Bond at maturity: duration = 0."""
        years = Decimal("0.0")
        coupon = Decimal("0.04")
        ytm = Decimal("0.05")
        frequency = 1

        duration = compute_macaulay_duration(years, coupon, ytm, frequency)

        assert duration == Decimal("0")

    def test_short_maturity_bond(self):
        """Single remaining cash flow: duration = maturity.

        旧实现靠 ``years <= 0.25 → return years`` 的特判命中；该特判已删除。
        新实现下 N = ceil(0.1 × 1) = 1，只剩到期一笔现金流，Σt·PV/ΣPV = t，
        自然精确等于剩余年限——结论相同但不再依赖魔数门槛。
        """
        years = Decimal("0.1")
        coupon = Decimal("0.04")
        ytm = Decimal("0.05")
        frequency = 1

        duration = compute_macaulay_duration(years, coupon, ytm, frequency)

        assert duration == years

    def test_near_zero_yield(self):
        """Near-zero but positive yield: real discounting, not a heuristic.

        旧实现在 ytm <= 1e-4 时走启发式因子式
        ``years × (1 − c·years / (2(1 + c·years)))`` = 4.583333，
        与 y→0 的真实极限 Σt·CF/ΣCF = (0.04×15 + 5)/(0.04×5 + 1) = 4.666667
        相差 0.083 年。新实现逐期贴现得 4.666622220324，正确收敛到该极限。
        （该分支内的 ``_FLOOR = 0.1`` 下限已证明是不可达死代码：因子
        1 − x/(2(1+x)) 在 x = c·years ≥ 0 上单调递减、下确界 0.5，永不低于 0.1。）
        """
        years = Decimal("5.0")
        coupon = Decimal("0.04")
        ytm = Decimal("0.00005")  # Very low yield
        frequency = 1

        duration = compute_macaulay_duration(years, coupon, ytm, frequency)

        assert abs(duration - Decimal("4.666622220324")) <= TOL
        # y→0 极限的上界；启发式的 4.583333 会落在下方
        assert Decimal("4.6") < duration < Decimal("4.6666667")

    def test_negative_yield(self):
        """Negative yield: fall back to remaining years (shared caliber).

        统一到 ``common`` 口径：ytm <= 0 不做贴现，直接返回剩余年限
        （负利率下贴现因子 > 1，闭合式与逐期式都不再有金融意义）。
        旧实现此处会落进 ytm <= 1e-4 的启发式分支，返回 4.5833。
        """
        years = Decimal("5.0")
        coupon = Decimal("0.04")
        ytm = Decimal("-0.01")
        frequency = 1

        duration = compute_macaulay_duration(years, coupon, ytm, frequency)

        assert duration == years

    def test_semiannual_frequency(self):
        """Bond with semiannual coupon payments — 10 whole半年期."""
        years = Decimal("5.0")
        coupon = Decimal("0.04")
        ytm = Decimal("0.05")
        frequency = 2

        duration = compute_macaulay_duration(years, coupon, ytm, frequency)

        assert abs(duration - Decimal("4.569507732462")) <= TOL
        assert duration < years

    def test_invalid_frequency_falls_back_to_annual(self):
        """Invalid coupon frequency should not mask duration fallback with NameError.

        ``frequency <= 0 → 1`` 的归一化是本模块**刻意保留**的本地行为：共享实现对
        freq <= 0 会直接返回剩余年限（期数算成 0），而本函数的既有契约是退化为年付。
        """
        years = Decimal("5.0")
        coupon = Decimal("0.04")
        ytm = Decimal("0.05")

        duration = compute_macaulay_duration(years, coupon, ytm, 0)
        annual_duration = compute_macaulay_duration(years, coupon, ytm, 1)

        assert duration == annual_duration
        assert abs(duration - Decimal("4.620322347961")) <= TOL

    def test_duration_decreases_with_higher_yield(self):
        """Duration decreases as yield increases (inverse relationship)."""
        years = Decimal("10.0")
        coupon = Decimal("0.05")
        frequency = 1

        duration_low_yield = compute_macaulay_duration(years, coupon, Decimal("0.03"), frequency)
        duration_high_yield = compute_macaulay_duration(years, coupon, Decimal("0.07"), frequency)

        assert abs(duration_low_yield - Decimal("8.271702728837")) <= TOL
        assert abs(duration_high_yield - Decimal("7.935107005611")) <= TOL
        assert duration_low_yield > duration_high_yield


class TestFractionalPeriodRegression:
    """W-fi-2026-08：非整数期限的回归护栏。

    旧实现按 ``to_integral_value()`` 四舍五入取期数，整数年份正确、非整数年份崩坏；
    生产入口的剩余年限恒为"剩余天数/365"，几乎永远非整数。整期用例（上面那些）
    在修复前后同值，拦不住这个 bug，必须由本组用例把碎期路径钉死。
    """

    # (剩余天数, 票息, ytm, 付息频率, 正确 Macaulay, 旧错误实现给出的值)
    CASES = [
        (547, "0.03", "0.03", 1, "1.469503923394", "1.00000"),
        (912, "0.03", "0.03", 1, "2.412099832528", "1.97090"),
        (1600, "0.03", "0.03", 1, "4.100660046646", "3.82860"),
        (1600, "0.0325", "0.028", 2, "4.109385813813", None),
    ]

    @pytest.mark.parametrize("days,coupon,ytm,freq,expected,legacy", CASES)
    def test_fractional_period_duration(self, days, coupon, ytm, freq, expected, legacy):
        years = Decimal(str(days)) / Decimal("365")
        mac = compute_macaulay_duration(
            years, Decimal(coupon), Decimal(ytm), frequency=freq
        )
        assert abs(mac - Decimal(expected)) <= TOL, (
            f"days={days} c={coupon} ytm={ytm} f={freq}: {mac} != {expected}"
        )
        if legacy is not None:
            assert abs(mac - Decimal(legacy)) > Decimal("0.05"), (
                f"days={days} 久期回到了整期取整口径的旧值 {legacy}"
            )

    @staticmethod
    def _in_stub_merge_window(days: int, freq: int) -> bool:
        """剩余期数的小数部分 ∈ (0, 0.01]，即共享实现会把尾数并入上一期的那些天。"""
        raw = Decimal(str(days)) / Decimal("365") * Decimal(str(freq))
        full = int(raw)
        return full > 0 and Decimal("0") < raw - Decimal(str(full)) <= Decimal("0.01")

    @pytest.mark.parametrize("freq", [1, 2])
    def test_duration_is_monotonic_in_remaining_days(self, freq):
        """久期必须随剩余天数单调不减（尾数归并窗口除外）。

        整期取整会制造锯齿：期数在 N 与 N+1 之间跳变时久期忽上忽下（1.4986 年的债
        算成 1.0000、1.5014 年的债算成 1.4695），本用例直接拦截这种非单调性——这是
        比单点黄金值更强的形状约束。

        已知例外（共享实现的既有行为，不在本次修复范围内）：剩余期数小数部分
        ∈ (0, 0.01] 时会触发尾数归并，等价于把一笔"即将支付"的票息按除息处理。
        跨越该阈值会真实地增减一笔近在眼前的现金流，价格跳约一个票息、时间权重
        几乎不变，久期因而不连续（29Y 年付券最大跳 0.56 年）。该窗口只覆盖约
        0.8% 的剩余天数；窗口之外单调性严格成立，故此处跳过窗口及其相邻天。
        """
        prev: Decimal | None = None
        prev_days: int | None = None
        for days in range(200, 10951):
            if any(
                self._in_stub_merge_window(d, freq) for d in (days - 1, days, days + 1)
            ):
                prev, prev_days = None, None  # 在不连续点处断开比较链
                continue
            mac = compute_macaulay_duration(
                Decimal(str(days)) / Decimal("365"),
                Decimal("0.03"),
                Decimal("0.03"),
                frequency=freq,
            )
            if prev is not None:
                assert mac >= prev, (
                    f"freq={freq} 久期在 days={prev_days}->{days} 处回落：{prev} -> {mac}"
                )
            prev, prev_days = mac, days


class TestSharedCaliberParity:
    """bond_duration 与 bond_analytics.common 必须给出**逐位相同**的久期。

    这是本次修复的核心不变量：engine 路径（/bond-analytics、DV01、KRD）与
    Campisi 归因路径（/pnl-attribution）读同一批持仓，久期必须一致，否则组合
    加权修正久期会再次出现 −9% 量级的分叉。
    """

    @pytest.mark.parametrize("freq", [1, 2])
    @pytest.mark.parametrize(
        "coupon,ytm",
        [("0.03", "0.03"), ("0.0325", "0.028"), ("0.06", "0.09"), ("0.005", "0.0005")],
    )
    def test_matches_shared_implementation(self, freq, coupon, ytm):
        for days in range(31, 10951, 197):
            years = Decimal(str(days)) / Decimal("365")
            mine = compute_macaulay_duration(
                years, Decimal(coupon), Decimal(ytm), frequency=freq
            )
            shared = shared_compute_macaulay_duration(
                coupon_rate=Decimal(coupon),
                ytm=Decimal(ytm),
                years_to_maturity=years,
                coupon_frequency=freq,
            )
            assert mine == shared, (
                f"days={days} c={coupon} ytm={ytm} f={freq}: "
                f"bond_duration={mine} common={shared}"
            )

    def test_delegation_uses_keyword_arguments(self):
        """两个函数的位置参数顺序**相反**，位置传参会静默算出另一种错误结果。

        bond_duration: (years, coupon, ytm, frequency)
        common:        (coupon, ytm, years, coupon_frequency)
        若委托时误用位置传参，1.4986 年 / 3% / 3% 的债会得到 0.05 而不是 1.4695。
        """
        years = Decimal("547") / Decimal("365")
        coupon, ytm = Decimal("0.03"), Decimal("0.05")

        correct = shared_compute_macaulay_duration(
            coupon_rate=coupon, ytm=ytm, years_to_maturity=years, coupon_frequency=1
        )
        swapped = shared_compute_macaulay_duration(years, coupon, ytm, 1)

        assert correct != swapped, "用例失效：该输入下位置/关键字传参恰好同值"
        assert compute_macaulay_duration(years, coupon, ytm, 1) == correct


class TestModifiedDuration:
    """Test modified duration = Macaulay / (1 + y/freq)."""

    def test_standard_conversion(self):
        """Standard Macaulay to modified duration conversion."""
        macaulay = Decimal("4.5")
        ytm = Decimal("0.05")
        frequency = 1

        modified = modified_duration_from_macaulay(macaulay, ytm, frequency)

        expected = macaulay / (Decimal("1") + ytm / Decimal("1"))
        assert abs(modified - expected) < Decimal("0.0001")

    def test_semiannual_frequency(self):
        """Modified duration with semiannual frequency."""
        macaulay = Decimal("4.5")
        ytm = Decimal("0.06")
        frequency = 2

        modified = modified_duration_from_macaulay(macaulay, ytm, frequency)

        expected = macaulay / (Decimal("1") + ytm / Decimal("2"))
        assert abs(modified - expected) < Decimal("0.0001")

    def test_zero_yield(self):
        """Zero yield: modified = Macaulay."""
        macaulay = Decimal("5.0")
        ytm = Decimal("0.0")
        frequency = 1

        modified = modified_duration_from_macaulay(macaulay, ytm, frequency)

        assert modified == macaulay

    def test_negative_yield(self):
        """Negative yield: fallback to Macaulay."""
        macaulay = Decimal("5.0")
        ytm = Decimal("-0.02")
        frequency = 1

        modified = modified_duration_from_macaulay(macaulay, ytm, frequency)

        assert modified == macaulay

    def test_invalid_frequency_returns_macaulay(self):
        """Invalid coupon frequency should fail closed to Macaulay duration."""
        macaulay = Decimal("5.0")
        ytm = Decimal("0.05")

        modified = modified_duration_from_macaulay(macaulay, ytm, 0)

        assert modified == macaulay

    def test_wind_override(self):
        """Wind modified duration overrides calculation."""
        macaulay = Decimal("5.0")
        ytm = Decimal("0.05")
        frequency = 1
        wind_mod_dur = Decimal("4.2")

        modified = modified_duration_from_macaulay(macaulay, ytm, frequency, wind_mod_dur)

        assert modified == wind_mod_dur

    def test_mod_dur_less_than_macaulay(self):
        """修正久期应小于麦考利久期（正利率）"""
        mac = Decimal("5.0")
        mod = modified_duration_from_macaulay(mac, Decimal("0.03"), 2, wind_mod_dur=None)
        assert mod < mac


class TestInferAccountingClass:
    """会计分类推断（从 backend/tests 迁入）。"""

    def test_ac_from_amortized_cost(self):
        assert infer_accounting_class("摊余成本债权投资") == "AC"

    def test_ac_from_bare_amortized(self):
        assert infer_accounting_class("摊余") == "AC"

    def test_oci_from_fvoci(self):
        assert infer_accounting_class("其他债权投资OCI") == "OCI"

    def test_oci_from_available_for_sale(self):
        assert infer_accounting_class("可供出售金融资产") == "OCI"

    def test_tpl_from_trading(self):
        assert infer_accounting_class("交易性金融资产") == "TPL"

    def test_none_returns_tpl(self):
        assert infer_accounting_class(None) == "TPL"

    def test_empty_string_returns_tpl(self):
        assert infer_accounting_class("") == "TPL"

    def test_unknown_returns_tpl(self):
        assert infer_accounting_class("未知资产类别XYZ") == "TPL"


class TestConvexity:
    """Test convexity estimation."""

    def test_positive_convexity(self):
        """Standard bond has positive convexity；口径与 common.estimate_convexity 同源。"""
        duration = Decimal("5.0")
        ytm = Decimal("0.05")
        frequency = 2

        convexity = estimate_convexity_bond(duration, ytm, coupon_frequency=frequency)

        assert convexity > Decimal("0")
        assert convexity == estimate_convexity(duration, ytm, coupon_frequency=frequency)

    def test_zero_yield(self):
        """Zero yield: W-fi-2026-08 P4 起不再特判 ``D²``。

        标准式退化为单笔现金流闭式解 ``D(D + 1/f)/(1+y/f)²``，``y=0`` 时即
        ``5 × (5 + 0.5) = 27.5``（旧实现给 ``D² = 25``，且在 ``y=0`` 处跳变 ``D``）。
        """
        duration = Decimal("5.0")
        ytm = Decimal("0.0")
        frequency = 2

        convexity = estimate_convexity_bond(duration, ytm, coupon_frequency=frequency)

        assert convexity == Decimal("27.50")

    def test_negative_yield(self):
        """Negative yield: 同一条标准式，``5 × 5.5 / (1 − 0.005)²``。"""
        duration = Decimal("5.0")
        ytm = Decimal("-0.01")
        frequency = 2

        convexity = estimate_convexity_bond(duration, ytm, coupon_frequency=frequency)

        expected = Decimal("27.5") / (Decimal("0.995") ** 2)
        assert convexity == expected
        assert convexity > Decimal("27.5")

    def test_wind_override(self):
        """Wind convexity overrides calculation."""
        duration = Decimal("5.0")
        ytm = Decimal("0.05")
        frequency = 2
        wind_convexity = Decimal("30.0")

        convexity = estimate_convexity_bond(duration, ytm, wind_convexity, frequency)

        assert convexity == wind_convexity

    def test_annual_frequency(self):
        """Convexity with annual frequency."""
        duration = Decimal("5.0")
        ytm = Decimal("0.05")
        frequency = 1

        convexity = estimate_convexity_bond(duration, ytm, coupon_frequency=frequency)

        assert convexity > Decimal("0")


class TestEstimateMacaulayDurationYears:
    """Test duration estimation from dates."""

    def test_standard_bond(self):
        """Standard bond with maturity in future."""
        maturity = date(2030, 12, 31)
        report = date(2026, 4, 17)
        coupon = Decimal("0.04")
        ytm = Decimal("0.05")

        duration = _estimate_macaulay_duration_years(maturity, report, coupon, ytm)

        assert duration > Decimal("0")
        years_to_maturity = Decimal((maturity - report).days) / Decimal("365")
        assert duration <= years_to_maturity

    def test_matured_bond(self):
        """Bond past maturity: duration = 0."""
        maturity = date(2020, 12, 31)
        report = date(2026, 4, 17)
        coupon = Decimal("0.04")
        ytm = Decimal("0.05")

        duration = _estimate_macaulay_duration_years(maturity, report, coupon, ytm)

        assert duration == Decimal("0")

    def test_zero_coupon_no_ytm(self):
        """Zero coupon bond without YTM: duration = maturity."""
        maturity = date(2030, 12, 31)
        report = date(2026, 4, 17)
        coupon = Decimal("0.0")
        ytm = None

        duration = _estimate_macaulay_duration_years(maturity, report, coupon, ytm)

        years_to_maturity = Decimal((maturity - report).days) / Decimal("365")
        assert duration == years_to_maturity

    def test_no_ytm_uses_coupon_as_yield(self):
        """No YTM provided: use coupon rate as yield."""
        maturity = date(2030, 12, 31)
        report = date(2026, 4, 17)
        coupon = Decimal("0.04")
        ytm = None

        duration = _estimate_macaulay_duration_years(maturity, report, coupon, ytm)

        assert duration > Decimal("0")


class TestEstimateDuration:
    """Test high-level duration estimation with fallbacks."""

    def test_sa_prefix_no_longer_short_circuits_to_quarter_year(self):
        """``SA`` 前缀不再短路成 0.25 年：有到期日就按到期日算（W-fi-2026-08 P2）。

        原实现假定 ``SA`` = 短融/超短融，无条件 ``return Decimal("0.25")``。实测这套账里
        57,115 行 ``SA`` 记录**到期日 0 行有值、票息 0 行非零、券名 100% 是纯 6 位数字**
        ——它们是公募基金与 ETF，不是短融。短路还排在到期日判断之前，即便补上真实到期日
        也会被 0.25 覆盖。
        """
        maturity = date(2026, 7, 17)
        report = date(2026, 4, 17)
        coupon = Decimal("0.03")

        with_prefix = estimate_duration(maturity, report, coupon, "SA123456")
        without_prefix = estimate_duration(maturity, report, coupon, "123456.IB")

        assert with_prefix != Decimal("0.25")
        assert with_prefix == without_prefix

    def test_scp_prefix_is_dead_code_and_behaves_like_any_other_code(self):
        """``SCP`` 前缀在本套账里 0 行匹配，不应再有专属分支（W-fi-2026-08 P2）。

        取证（只读副本 moss.duckdb.bak-20260812-1920-presnapshot，2026-08-12）::

            fact_formal_bond_analytics_daily  where instrument_code like 'SCP%'  -> 0 行
            zqtz_bond_daily_snapshot          where instrument_code like 'SCP%'  -> 0 行
            fact_formal_zqtz_balance_daily    where instrument_code like 'SCP%'  -> 0 行

        原 ``code.startswith("SCP")`` 分支从未被真实数据命中，是纯死代码；它唯一的作用
        是让读者以为这套账里有超短融特殊处理。
        """
        maturity = date(2026, 7, 17)
        report = date(2026, 4, 17)
        coupon = Decimal("0.03")

        assert estimate_duration(maturity, report, coupon, "SCP123456") == estimate_duration(
            maturity, report, coupon, "123456.IB"
        )

    def test_wind_metrics_override(self):
        """Wind metrics override calculation."""
        maturity = date(2030, 12, 31)
        report = date(2026, 4, 17)
        coupon = Decimal("0.04")
        bond_code = "123456.IB"
        wind_metrics = {"123456.IB": {"duration": Decimal("4.8")}}

        duration = estimate_duration(maturity, report, coupon, bond_code, wind_metrics=wind_metrics)

        assert duration == Decimal("4.8")

    def test_missing_maturity_returns_unavailable_marker(self):
        """缺到期日：返回 ``DURATION_UNAVAILABLE``（不可用标记），不再编 3.0 年代理久期。"""
        report = date(2026, 4, 17)
        coupon = Decimal("0.04")

        duration = estimate_duration(None, report, coupon, "123456.IB")

        assert duration == DURATION_UNAVAILABLE
        assert duration != Decimal("3.0")

    def test_missing_maturity_status_distinguishes_unavailable_from_matured(self):
        """状态入口把「久期不适用」与「已到期，久期真的是 0」分开——数值同为 0。"""
        report = date(2026, 4, 17)
        coupon = Decimal("0.04")

        no_maturity, no_maturity_status = estimate_duration_with_status(
            None, report, coupon, "123456.IB"
        )
        matured, matured_status = estimate_duration_with_status(
            date(2026, 1, 31), report, coupon, "123456.IB"
        )

        assert (no_maturity, no_maturity_status) == (None, DURATION_TERM_MATURITY_UNAVAILABLE)
        assert (matured, matured_status) == (Decimal("0"), DURATION_TERM_NO_REMAINING_TERM)
        # 兼容外壳把两者都折成 0，所以只看 estimate_duration 无法区分——这正是
        # estimate_duration_with_status 存在的理由。
        assert estimate_duration(None, report, coupon, "123456.IB") == estimate_duration(
            date(2026, 1, 31), report, coupon, "123456.IB"
        )

    def test_missing_maturity_emits_explicit_warning(self, caplog):
        """缺到期日必须显式告警并带 rule_id，不得静默返回占位值。"""
        with caplog.at_level(logging.WARNING):
            estimate_duration(None, date(2026, 4, 17), Decimal("0.04"), "SA0106070101")

        assert any(
            "SA0106070101" in record.message and MISSING_MATURITY_RULE_ID in record.message
            for record in caplog.records
        )

    def test_standard_bond_with_ytm(self):
        """Standard bond with YTM provided."""
        maturity = date(2030, 12, 31)
        report = date(2026, 4, 17)
        coupon = Decimal("0.04")
        bond_code = "123456.IB"
        ytm = Decimal("0.05")

        duration = estimate_duration(maturity, report, coupon, bond_code, ytm=ytm)

        assert duration > Decimal("0")
        years_to_maturity = Decimal((maturity - report).days) / Decimal("365")
        assert duration <= years_to_maturity

    def test_normal_bond_duration_in_range(self):
        """正常债券久期应在合理范围内"""
        dur = estimate_duration(
            maturity_date=date(2027, 12, 31),
            report_date=date(2024, 1, 31),
            coupon_rate=Decimal("0.03"),
            ytm=Decimal("0.03"),
        )
        assert Decimal("1") < dur < Decimal("5")

    def test_short_term_bond_low_duration(self):
        """短期债券久期应小于长期债券"""
        short = estimate_duration(
            maturity_date=date(2024, 6, 30),
            report_date=date(2024, 1, 31),
            coupon_rate=Decimal("0.03"),
            ytm=Decimal("0.03"),
        )
        long_ = estimate_duration(
            maturity_date=date(2034, 1, 31),
            report_date=date(2024, 1, 31),
            coupon_rate=Decimal("0.03"),
            ytm=Decimal("0.03"),
        )
        assert short < long_

    def test_zero_coupon_duration_equals_maturity(self):
        """零息债券久期应接近到期年限"""
        dur = estimate_duration(
            maturity_date=date(2029, 1, 31),
            report_date=date(2024, 1, 31),
            coupon_rate=Decimal("0"),
            ytm=Decimal("0.03"),
        )
        # 2024-01-31 到 2029-01-31 实际约 5.003 年（含闰年），允许 ±0.1
        assert Decimal("4.9") < dur < Decimal("5.1")

    def test_returns_decimal(self):
        dur = estimate_duration(
            maturity_date=date(2027, 12, 31),
            report_date=date(2024, 1, 31),
            coupon_rate=Decimal("0.03"),
        )
        assert isinstance(dur, Decimal)
