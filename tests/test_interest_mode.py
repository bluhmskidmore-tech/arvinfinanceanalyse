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


def test_numeric_month_phrases_currently_fall_back_to_annual():
    """钉住"3个月"/"6个月"当前的实际归宿，而不仅是"不是 monthly"。

    TODO(interest-mode-numeric-tenor): 若后续能取证 ``interest_mode`` 真实出现
    "3个月"/"6个月" 这类取值（表示季付/半年付而非期限），应改判为
    quarterly / semi-annual 并把本用例翻成正向断言。取证结论（2026-08）：
    ``docs/data_contracts.md`` 只声明 ``interest_mode varchar`` 未枚举取值；
    ``docs/calc_rules.md`` 的付息频率口径只列 annual / semi-annual / quarterly /
    bullet；仓库内实际出现的取值为 annual/semi-annual/quarterly/bullet/monthly/
    fixed/floating/固定/半年付息/年付 等，未见 "3个月"/"6个月"。在取证之前保持
    unknown -> annual 回退，避免把期限词误当付息频率。
    """
    mod = _module()

    assert mod.classify_interest_payment_frequency("3个月") == "unknown"
    assert mod.classify_interest_payment_frequency("6个月") == "unknown"
    assert mod.resolve_interest_payment_frequency("3个月") == ("annual", True)
    assert mod.resolve_interest_payment_frequency("6个月") == ("annual", True)
    assert mod.coupon_frequency_per_year("3个月") == 1
    assert mod.coupon_interval_months("6个月") == 12


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


def test_legacy_rate_style_values_are_disclosed_like_any_other_fallback(caplog):
    """"固定"/"浮动" 的年付回退必须与未知取值一样被披露。

    这两个取值只声明利率风格、同样推不出付息频率，但曾被
    ``classify_interest_rate_style`` 认出后豁免告警。正式表
    ``fact_formal_*`` 里 1750/1750 行 ``fallback_used=True`` 全部落在这条分支，
    豁免等于让 100% 的回退看起来像"没有回退"（2026-08 审计）。
    """
    import logging

    mod = _module()

    with caplog.at_level(logging.WARNING):
        assert mod.resolve_interest_payment_frequency("固定") == ("annual", True)
        assert mod.resolve_interest_payment_frequency("浮动利率") == ("annual", True)

    disclosures = [
        record for record in caplog.records if "fell back to annual" in record.getMessage()
    ]
    assert len(disclosures) == 2
    assert all(record.levelno == logging.WARNING for record in disclosures)
    # 披露里带上被识别出的利率风格，便于运维区分"遗留风格值"与"真正未知值"。
    assert "rate_style=fixed" in disclosures[0].getMessage()
    assert "rate_style=floating" in disclosures[1].getMessage()


def test_rate_style_fallback_disclosure_is_deduplicated_per_process(caplog):
    """去重仍然生效：1750 行同一取值只刷一条，避免日志洪泛淹没披露。"""
    import logging

    mod = _module()

    with caplog.at_level(logging.WARNING):
        for _ in range(5):
            assert mod.resolve_interest_payment_frequency("固定") == ("annual", True)
        # 同一进程内不同取值各披露一次。
        for _ in range(5):
            assert mod.resolve_interest_payment_frequency("浮动") == ("annual", True)

    assert len([r for r in caplog.records if "fell back to annual" in r.getMessage()]) == 2


def test_empty_interest_mode_fallback_is_disclosed_once(caplog):
    """空/None 的付息频率同样是回退，不能因为"没有字面量"就静默。"""
    import logging

    mod = _module()

    with caplog.at_level(logging.WARNING):
        assert mod.resolve_interest_payment_frequency(None) == ("annual", True)
        assert mod.resolve_interest_payment_frequency("") == ("annual", True)
        assert mod.resolve_interest_payment_frequency("   ") == ("annual", True)

    assert len([r for r in caplog.records if "fell back to annual" in r.getMessage()]) == 1


def test_recognized_frequencies_never_emit_a_fallback_disclosure(caplog):
    """反向保险：能识别的付息频率不得产生噪声告警，否则披露会被稀释。"""
    import logging

    mod = _module()

    with caplog.at_level(logging.WARNING):
        for value in ("年付息", "半年付息", "季付息", "按月付息", "到期一次还本付息"):
            frequency, used_fallback = mod.resolve_interest_payment_frequency(value)
            assert used_fallback is False
            assert frequency != "unknown"

    assert not [r for r in caplog.records if "fell back to annual" in r.getMessage()]


def test_classify_interest_rate_style_distinguishes_fixed_and_floating():
    mod = _module()

    assert mod.classify_interest_rate_style("固定计息") == "fixed"
    assert mod.classify_interest_rate_style("浮动利率") == "floating"
    assert mod.classify_interest_rate_style("半年付息") == "unknown"
