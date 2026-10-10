"""Independent calendar cash-flow checks around actual payment dates (no storage)."""
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend.app.core_finance import bond_duration
from backend.app.core_finance.bond_analytics import common
from backend.app.core_finance.bond_analytics.engine import compute_bond_analytics_rows
from backend.app.core_finance.bond_four_effects import compute_bond_six_effects
from backend.app.core_finance.krd import build_krd_position_metrics


def _reference(report: date, maturity: date, frequency: int) -> tuple[float, float, int]:
    # Enumerate months forward, independently of the production backwards schedule.
    interval = 12 // frequency
    payments = []
    report_is_coupon = False
    for year in range(report.year, maturity.year + 1):
        for month in range(1, 13):
            months_to_maturity = (maturity.year - year) * 12 + maturity.month - month
            if months_to_maturity < 0 or months_to_maturity % interval:
                continue
            payment = date(year, month, min(maturity.day, monthrange(year, month)[1]))
            report_is_coupon |= payment == report
            if report < payment <= maturity:
                payments.append(payment)
    # Preserve the established whole-period convention only on an actual coupon date.
    times = [
        (i + 1) / frequency if report_is_coupon else (payment - report).days / 365
        for i, payment in enumerate(payments)
    ]
    base = 1 + 0.03 / frequency
    present_values = [
        (0.03 / frequency + (1 if i == len(times) - 1 else 0)) / base ** (t * frequency)
        for i, t in enumerate(times)
    ]
    price = sum(present_values)
    duration = sum(t * pv for t, pv in zip(times, present_values)) / price
    convexity = sum(t * (t + 1 / frequency) * pv for t, pv in zip(times, present_values)) / price / base**2
    return duration, convexity, len(payments)


@pytest.mark.parametrize("frequency", [1, 2, 4])
@pytest.mark.parametrize("offset", [-1, 0, 1])
@pytest.mark.parametrize("coupon_day,maturity", [
    (date(2026, 3, 31), date(2056, 3, 31)),
    (date(2028, 2, 29), date(2056, 2, 29)),
    (date(2027, 2, 28), date(2056, 2, 29)),
])
def test_date_duration_keeps_every_future_coupon(coupon_day, maturity, offset, frequency):
    report = coupon_day + timedelta(days=offset)
    expected, _, count = _reference(report, maturity, frequency)
    if coupon_day == date(2026, 3, 31):
        assert count == 30 * frequency + (1 if offset < 0 else 0)
    for calculate in (common.estimate_duration, bond_duration.estimate_duration):
        actual = calculate(maturity, report, coupon_rate=Decimal("0.03"), ytm=Decimal("0.03"), coupon_frequency=frequency)
        assert float(actual) == pytest.approx(expected, abs=1e-10)


@pytest.mark.parametrize("frequency,mode", [(1, "annual"), (2, "半年付息"), (4, "季付")])
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_engine_krd_and_campisi_share_date_duration_and_convexity(frequency, mode, offset):
    report = date(2026, 3, 31) + timedelta(days=offset)
    maturity = date(2056, 3, 31)
    expected_duration, expected_convexity, _ = _reference(report, maturity, frequency)
    expected_modified = expected_duration / (1 + 0.03 / frequency)
    row = compute_bond_analytics_rows([{
        "report_date": report, "instrument_code": "DATE-COUPON", "currency_code": "CNY",
        "face_value_native": Decimal("100"), "market_value_native": Decimal("100"),
        "amortized_cost_native": Decimal("100"), "coupon_rate": Decimal("3"),
        "ytm_value": Decimal("3"), "maturity_date": maturity, "interest_mode": mode,
    }], report)[0]
    assert float(row.macaulay_duration) == pytest.approx(expected_duration, abs=1e-10)
    assert float(row.convexity) == pytest.approx(expected_convexity, abs=1e-9)
    position = {
        "bond_code": "DATE-COUPON", "market_value": Decimal("100"), "face_value": Decimal("100"),
        "coupon_rate": Decimal("0.03"), "yield_to_maturity": Decimal("0.03"),
        "maturity_date": maturity, "report_date": report, "coupon_frequency": frequency,
    }
    krd = build_krd_position_metrics([position], report_date=report)[0]
    assert float(krd["modified_duration"]) == pytest.approx(expected_modified, abs=1e-10)
    assert float(krd["convexity"]) == pytest.approx(expected_convexity, abs=1e-9)
    effects = compute_bond_six_effects({
        **position, "market_value_start": Decimal("100"), "market_value_end": Decimal("100"),
        "face_value_start": Decimal("100"), "asset_class_start": "FVOCI",
    }, 1, Decimal("0.01"), Decimal("0"), report, coupon_frequency=frequency)
    assert float(effects["mod_duration"]) == pytest.approx(expected_modified, abs=1e-10)
    assert float(effects["convexity_effect"]) == pytest.approx(0.005 * expected_convexity, abs=1e-10)


def test_date_less_long_tenor_does_not_claim_calendar_anniversary():
    # No dates: preserve the older small stub convention, not a growing leap-day window.
    years = Decimal("30") + Decimal("9") / Decimal("365")
    coupon = Decimal("0.03")
    actual = common.compute_macaulay_duration(coupon, coupon, years)
    times = [float(years - 30) + i for i in range(31)]
    pvs = [(0.03 + (1 if i == 30 else 0)) / 1.03**t for i, t in enumerate(times)]
    expected = sum(t * pv for t, pv in zip(times, pvs)) / sum(pvs)
    assert float(actual) == pytest.approx(expected, abs=1e-10)


def test_date_less_legacy_stub_does_not_snap_cashflow_past_maturity():
    years = Decimal("0.999")
    actual = common.compute_macaulay_duration(Decimal("0.03"), Decimal("0.03"), years)
    assert actual == years


@pytest.mark.parametrize("frequency", [5, 13])
def test_non_monthly_frequency_retains_existing_term_model(frequency):
    report, maturity = date(2026, 3, 30), date(2056, 3, 31)
    years = Decimal((maturity - report).days) / Decimal("365")
    args = (Decimal("0.03"), Decimal("0.03"), years, frequency)
    assert common.compute_macaulay_duration_and_convexity(
        *args, report_date=report, maturity_date=maturity,
    ) == common.compute_macaulay_duration_and_convexity(*args)


@pytest.mark.parametrize("frequency", [1, 2, 4, 12])
def test_legacy_stub_threshold_is_exact_in_period_units(frequency):
    for fraction, expected in [("-0.001", False), ("0", True), ("0.009999", True), ("0.01", True), ("0.010001", False)]:
        years = (Decimal("12") + Decimal(fraction)) / frequency
        assert common.whole_period_calendar_merge_applies(years, 12, frequency) is expected
