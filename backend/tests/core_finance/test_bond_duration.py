"""Tests for bond_duration core calculations."""
from datetime import date
from decimal import Decimal

import pytest

from backend.app.core_finance.bond_duration import (
    estimate_duration,
    infer_accounting_class,
    modified_duration_from_macaulay,
)


class TestEstimateDuration:

    def test_normal_bond_duration_in_range(self):
        """正常债券久期应在合理范围内"""
        dur = estimate_duration(
            maturity_date=date(2027, 12, 31),
            report_date=date(2024, 1, 31),
            coupon_rate=Decimal("0.03"),
            ytm=Decimal("0.03"),
        )
        assert Decimal("1") < dur < Decimal("5")

    def test_none_maturity_returns_proxy(self):
        """到期日为 None 时返回代理值，不崩溃"""
        dur = estimate_duration(
            maturity_date=None,
            report_date=date(2024, 1, 31),
            coupon_rate=Decimal("0.03"),
        )
        assert dur >= Decimal("0")

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


class TestInferAccountingClass:

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


class TestModifiedDurationFromMacaulay:

    def test_basic_conversion(self):
        """修正久期 = 麦考利久期 / (1 + ytm/freq)"""
        mac = Decimal("3.0")
        ytm = Decimal("0.06")
        freq = 2
        mod = modified_duration_from_macaulay(mac, ytm, freq, wind_mod_dur=None)
        expected = mac / (1 + ytm / Decimal(str(freq)))
        assert abs(mod - expected) < Decimal("0.0001")

    def test_mod_dur_less_than_macaulay(self):
        """修正久期应小于麦考利久期（正利率）"""
        mac = Decimal("5.0")
        mod = modified_duration_from_macaulay(mac, Decimal("0.03"), 2, wind_mod_dur=None)
        assert mod < mac

    def test_zero_ytm_returns_macaulay_unchanged(self):
        """ytm=0 时修正久期应等于麦考利久期（不崩溃，不产生魔法数字）"""
        mac = Decimal("4.5")
        mod = modified_duration_from_macaulay(mac, Decimal("0"), 2, wind_mod_dur=None)
        assert mod == mac

    def test_negative_ytm_returns_macaulay_unchanged(self):
        """ytm<0 时修正久期应等于麦考利久期"""
        mac = Decimal("3.0")
        mod = modified_duration_from_macaulay(mac, Decimal("-0.005"), 2, wind_mod_dur=None)
        assert mod == mac

    def test_wind_override_used_when_provided(self):
        """wind_mod_dur 提供时应优先使用"""
        wind_val = Decimal("4.567")
        mod = modified_duration_from_macaulay(
            Decimal("5.0"), Decimal("0.03"), 2, wind_mod_dur=wind_val
        )
        assert mod == wind_val
