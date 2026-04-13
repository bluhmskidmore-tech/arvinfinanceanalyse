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


def test_resolve_interest_payment_frequency_preserves_legacy_fixed_fallback():
    mod = _module()

    assert mod.resolve_interest_payment_frequency("固定") == ("annual", True)
    assert mod.resolve_interest_payment_frequency("浮动利率") == ("annual", True)


def test_classify_interest_rate_style_distinguishes_fixed_and_floating():
    mod = _module()

    assert mod.classify_interest_rate_style("固定计息") == "fixed"
    assert mod.classify_interest_rate_style("浮动利率") == "floating"
    assert mod.classify_interest_rate_style("半年付息") == "unknown"
