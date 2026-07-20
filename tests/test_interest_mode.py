from __future__ import annotations

from tests.helpers import load_module


def _module():
    return load_module(
        "backend.app.core_finance.interest_mode",
        "backend/app/core_finance/interest_mode.py",
    )


def test_resolve_interest_payment_frequency_recognizes_supported_modes():
    mod = _module()

    assert mod.resolve_interest_payment_frequency("年付息") == ("annual", False)
    assert mod.resolve_interest_payment_frequency("半年付息") == ("semi-annual", False)
    assert mod.resolve_interest_payment_frequency("季付息") == ("quarterly", False)
    assert mod.resolve_interest_payment_frequency("到期一次还本付息") == ("bullet", False)


def test_resolve_interest_payment_frequency_recognizes_monthly_modes():
    mod = _module()

    assert mod.resolve_interest_payment_frequency("按月付息") == ("monthly", False)
    assert mod.resolve_interest_payment_frequency("每月付息") == ("monthly", False)
    assert mod.resolve_interest_payment_frequency("monthly") == ("monthly", False)
    assert mod.resolve_interest_payment_frequency("Monthly Coupon") == ("monthly", False)

    assert mod.coupon_frequency_per_year("按月付息") == 12
    assert mod.coupon_interval_months("按月付息") == 1
    assert mod.is_bullet_repayment("按月付息") is False


def test_numeric_month_phrases_are_not_misclassified_as_monthly():
    # "3个月"/"6个月" 是期限而非按月付息表述，不得落入 monthly 分支。
    mod = _module()

    assert mod.classify_interest_payment_frequency("3个月") != "monthly"
    assert mod.classify_interest_payment_frequency("6个月") != "monthly"


def test_resolve_interest_payment_frequency_preserves_legacy_fixed_fallback():
    mod = _module()

    assert mod.resolve_interest_payment_frequency("固定") == ("annual", True)
    assert mod.resolve_interest_payment_frequency("浮动利率") == ("annual", True)


def test_unknown_fallback_is_disclosed_once_via_warning(caplog):
    import logging

    mod = _module()

    with caplog.at_level(logging.WARNING):
        assert mod.resolve_interest_payment_frequency("神秘计息方式X") == ("annual", True)
        assert mod.resolve_interest_payment_frequency("神秘计息方式X") == ("annual", True)
    disclosures = [record for record in caplog.records if "神秘计息方式X" in record.getMessage()]
    assert len(disclosures) == 1
    assert disclosures[0].levelno == logging.WARNING


def test_legacy_rate_style_values_fall_back_without_warning(caplog):
    import logging

    mod = _module()

    with caplog.at_level(logging.WARNING):
        assert mod.resolve_interest_payment_frequency("固定") == ("annual", True)
        assert mod.resolve_interest_payment_frequency("浮动利率") == ("annual", True)
    assert not [record for record in caplog.records if "fell back to annual" in record.getMessage()]


def test_classify_interest_rate_style_distinguishes_fixed_and_floating():
    mod = _module()

    assert mod.classify_interest_rate_style("固定计息") == "fixed"
    assert mod.classify_interest_rate_style("浮动利率") == "floating"
    assert mod.classify_interest_rate_style("半年付息") == "unknown"
