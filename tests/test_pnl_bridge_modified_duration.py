from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import duckdb
import pytest

from backend.app.core_finance.pnl_bridge import _modified_duration

REPORT = date(2025, 12, 31)
MATURITY = date(2030, 12, 31)


def _balance_row(**overrides: object) -> dict:
    row: dict = {
        "report_date": REPORT,
        "instrument_code": "240001.IB",
        "maturity_date": MATURITY,
        # 落库口径为百分数：2.38 表示 2.38%（fact_formal_zqtz_balance_daily）
        "coupon_rate": Decimal("2.38"),
        "ytm_value": Decimal("2.38"),
    }
    row.update(overrides)
    return row


def test_fallback_normalizes_percent_coupon_and_ytm_to_decimal():
    """回退路径必须把百分数口径归一为小数，否则 5 年期券久期塌缩到 0.4 年。"""
    duration = _modified_duration(report_date=REPORT, row=_balance_row())

    # 票息=收益率的 5 年平价券：Macaulay≈4.77，修正久期≈4.77/1.0238≈4.66
    assert float(duration) == pytest.approx(4.6619, abs=1e-3)
    # 未归一（2.38 当作 238%）时结果约 0.42，此断言锁死塌缩回归
    assert duration > Decimal("2")
    assert Decimal("4") < duration < Decimal("5")


def test_fallback_distinguishes_observed_zero_ytm_from_missing():
    observed = _modified_duration(report_date=REPORT, row=_balance_row(coupon_rate=Decimal("3"), ytm_value=Decimal("0")))
    missing = _modified_duration(report_date=REPORT, row=_balance_row(coupon_rate=Decimal("3"), ytm_value=None))
    par = _modified_duration(report_date=REPORT, row=_balance_row(coupon_rate=Decimal("3"), ytm_value=Decimal("3")))
    assert observed > missing
    assert missing == par


def test_fallback_uses_years_to_maturity_when_rates_are_dirty():
    """脏利率（>20% 视为脏数据）按 0 处理，久期回退为剩余年限，不静默放大。"""
    duration = _modified_duration(
        report_date=REPORT,
        row=_balance_row(coupon_rate=Decimal("20720.93"), ytm_value=Decimal("20720.93")),
    )

    # (2030-12-31 - 2025-12-31) = 1826 天 / 365 ≈ 5.0027 年
    assert float(duration) == pytest.approx(5.0027, abs=1e-3)


def test_materialized_modified_duration_still_wins_over_fallback():
    """余额行若携带物化修正久期，仍直接采用，不进入归一回退路径。"""
    duration = _modified_duration(
        report_date=REPORT,
        row=_balance_row(modified_duration="3.75"),
    )

    assert duration == Decimal("3.75")


def test_missing_maturity_date_returns_zero():
    duration = _modified_duration(report_date=REPORT, row=_balance_row(maturity_date=None))

    assert duration == Decimal("0")


def _cashflow_price_duration(
    report: date,
    maturity: date,
    coupon: float,
    ytm: float,
    frequency: int,
    *,
    bullet: bool = False,
) -> float:
    """Independent price-bump reference, with forward calendar enumeration.

    This does not call a production duration, cash-flow, or frequency helper.
    The coupon-date k/f convention and off-grid ACT/365 convention are the
    currently approved time bases; bullet has exactly one maturity cash flow.
    """
    if bullet or coupon == 0:
        years = (maturity - report).days / 365
        cashflows = [(years, 1 + coupon * years)]
    else:
        payments = []
        on_coupon_date = False
        for year in range(report.year, maturity.year + 1):
            for month in range(1, 13):
                months_left = (maturity.year - year) * 12 + maturity.month - month
                if months_left < 0 or months_left % (12 // frequency):
                    continue
                payment = date(year, month, min(maturity.day, monthrange(year, month)[1]))
                on_coupon_date |= payment == report
                if report < payment <= maturity:
                    payments.append(payment)
        cashflows = [
            (
                (index + 1) / frequency if on_coupon_date else (payment - report).days / 365,
                coupon / frequency + int(payment == maturity),
            )
            for index, payment in enumerate(payments)
        ]

    def price(yield_value: float) -> float:
        return sum(amount / (1 + yield_value / frequency) ** (years * frequency) for years, amount in cashflows)

    bump = 0.000001
    return -(price(ytm + bump) - price(ytm - bump)) / (2 * bump * price(ytm))


@pytest.mark.parametrize(
    "mode,frequency,bullet",
    [("annual", 1, False), ("半年付息", 2, False), ("季付", 4, False), ("每月付息", 12, False),
     ("到期一次还本付息", 1, True)],
)
@pytest.mark.parametrize("offset", [-1, 0, 1])
@pytest.mark.parametrize("ytm", [Decimal("3"), Decimal("-1")])
def test_fallback_uses_payment_mode_in_cashflows_and_discounting(mode, frequency, bullet, offset, ytm):
    report = date(2026, 9, 22) + timedelta(days=offset)
    maturity = date(2031, 9, 22)
    expected = _cashflow_price_duration(report, maturity, 0.04, float(ytm / 100), frequency, bullet=bullet)

    actual = _modified_duration(
        report_date=report,
        row=_balance_row(maturity_date=maturity, coupon_rate=Decimal("4"), ytm_value=ytm, interest_mode=mode),
    )

    assert float(actual) == pytest.approx(expected, abs=1e-7)


@pytest.mark.parametrize("mode", [None, "", "固定"])
def test_unknown_payment_mode_retains_annual_fallback(mode):
    actual = _modified_duration(report_date=REPORT, row=_balance_row(interest_mode=mode))
    expected = _cashflow_price_duration(REPORT, MATURITY, 0.0238, 0.0238, 1)
    assert float(actual) == pytest.approx(expected, abs=1e-7)


@pytest.mark.parametrize("mode", ["半年付息", "到期一次还本付息"])
def test_materialized_duration_wins_for_each_payment_mode(mode):
    assert _modified_duration(
        report_date=REPORT, row=_balance_row(interest_mode=mode, modified_duration=Decimal("3.75")),
    ) == Decimal("3.75")


@pytest.mark.parametrize("mode", ["半年付息", "到期一次还本付息"])
def test_matured_payment_mode_has_no_remaining_duration(mode):
    assert _modified_duration(
        report_date=REPORT, row=_balance_row(interest_mode=mode, maturity_date=REPORT),
    ) == Decimal("0")


@pytest.mark.parametrize("mode,frequency,bullet", [("半年付息", 2, False), ("到期一次还本付息", 1, True)])
def test_formal_bridge_repository_and_service_preserve_payment_mode(tmp_path, monkeypatch, mode, frequency, bullet):
    """Real formal-balance SQL and service calculation; synthetic PnL/curves/lineage."""
    from backend.app.repositories.balance_analysis_repo import (
        BalanceAnalysisRepository,
        ensure_balance_analysis_tables,
    )
    from backend.app.services import pnl_bridge_service as service

    report, maturity = date(2026, 9, 22), date(2031, 9, 22)
    expected_duration = _cashflow_price_duration(report, maturity, 0.04, 0.03, frequency, bullet=bullet)
    # 1 bp parallel yield increase on CNY 1 million: -Dmod * MV * 0.0001.
    expected_curve_pnl = Decimal(str(-expected_duration * 100))
    db_path = tmp_path / "payment-mode.duckdb"
    with duckdb.connect(str(db_path)) as conn:
        ensure_balance_analysis_tables(conn)
        conn.executemany(
            """
            insert into fact_formal_zqtz_balance_daily (
                report_date, instrument_code, instrument_name, portfolio_name, cost_center,
                accounting_basis, position_scope, currency_basis, currency_code,
                market_value_amount, accrued_interest_amount, coupon_rate, ytm_value,
                maturity_date, interest_mode, source_version, rule_version, ingest_batch_id, trace_id
            ) values (?, 'PAYMENT-MODE', '国债', 'BOOK', 'DESK', 'FVTPL', 'asset', 'CNY', 'CNY',
                      1000000, 0, 4, 3, '2031-09-22', ?, 'sv_test', 'rv_test', 'ib_test', 'tr_test')
            """,
            [("2026-08-31", mode), (report.isoformat(), mode)],
        )
    formal_rows = BalanceAnalysisRepository(str(db_path)).fetch_pnl_bridge_zqtz_balance_rows(report_date=report.isoformat())
    assert formal_rows[0]["interest_mode"] == mode
    assert "modified_duration" not in formal_rows[0]
    pnl = {
        "report_date": report.isoformat(), "instrument_code": "PAYMENT-MODE", "instrument_name": "国债",
        "portfolio_name": "BOOK", "cost_center": "DESK", "currency_basis": "CNY",
        "accounting_basis": "FVTPL", "interest_income_514": Decimal("0"),
        "fair_value_change_516": expected_curve_pnl, "capital_gain_517": Decimal("0"),
        "manual_adjustment": Decimal("0"), "total_pnl": expected_curve_pnl,
    }
    monkeypatch.setattr(service, "PnlRepository", lambda _: SimpleNamespace(
        list_formal_fi_report_dates=lambda: [report.isoformat()],
        fetch_formal_fi_rows=lambda _: [pnl],
    ))

    def curve_pair(**kwargs):
        if kwargs["curve_type"] != "treasury":
            return None, None
        return {
            "trade_date": report.isoformat(), "source_version": "sv_curve_current",
            "curve": {"1Y": Decimal("1.01"), "10Y": Decimal("1.01")},
            "_prior_snapshot": {
                "trade_date": "2026-08-31", "source_version": "sv_curve_prior",
                "curve": {"1Y": Decimal("1"), "10Y": Decimal("1")},
            },
        }, None

    monkeypatch.setattr(service, "_resolve_curve_pair_if_needed", curve_pair)
    monkeypatch.setattr(service, "_resolve_bridge_lineage", lambda **_: ({
        "source_version": "sv_test", "rule_version": "rv_test", "vendor_version": "vv_test",
    }, []))
    envelope = service.pnl_bridge_envelope(
        duckdb_path=str(db_path), governance_dir=str(tmp_path / "governance"), report_date=report.isoformat(),
    )

    row = envelope["result"]["rows"][0]
    assert float(row["treasury_curve"]["raw_text"]) == pytest.approx(float(expected_curve_pnl), abs=1e-5)
    assert float(envelope["result"]["summary"]["total_treasury_curve"]["raw_text"]) == pytest.approx(float(expected_curve_pnl), abs=1e-5)
    assert row["quality_flag"] == "ok"
