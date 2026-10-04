from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module

CASHFLOW_PROJECTION_READ_HEADERS = {
    "X-User-Id": "cashflow-projection-read-user",
    "X-User-Role": "viewer",
}


def _grant_cashflow_projection_read_scope(tmp_path, monkeypatch, *, user_id: str = "*") -> None:
    sqlite_path = tmp_path / "cashflow-projection-read-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    repo_module = load_module(
        "backend.app.repositories.user_scope_repo",
        "backend/app/repositories/user_scope_repo.py",
    )
    repo_module.UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}").grant_scope(
        user_id=user_id,
        role=None,
        resource="cashflow_projection",
        action="read",
    )


def _core_module():
    return load_module(
        "backend.app.core_finance.cashflow_projection",
        "backend/app/core_finance/cashflow_projection.py",
    )


def test_bond_cashflow_projection_basic():
    module = _core_module()

    events = module.project_bond_cashflows(
        [
            {
                "instrument_code": "BOND-001",
                "instrument_name": "Alpha Bond",
                "maturity_date": date(2026, 7, 15),
                "face_value": Decimal("100"),
                "coupon_rate": Decimal("6.0"),
                "interest_mode": "semi annual",
                "currency_code": "CNY",
            },
            {
                "instrument_code": "BOND-OLD",
                "instrument_name": "Expired Bond",
                "maturity_date": date(2025, 12, 31),
                "face_value": Decimal("50"),
                "coupon_rate": Decimal("5.0"),
                "interest_mode": "annual",
                "currency_code": "CNY",
            },
        ],
        report_date=date(2026, 1, 14),
        horizon_months=12,
    )

    assert [
        (event.event_type, event.event_date.isoformat(), event.amount)
        for event in events
    ] == [
        ("coupon", "2026-01-15", Decimal("3")),
        ("coupon", "2026-07-15", Decimal("3")),
        ("principal", "2026-07-15", Decimal("100")),
    ]


def test_bond_cashflow_projection_treats_bullet_as_maturity_only_coupon():
    module = _core_module()

    events = module.project_bond_cashflows(
        [
            {
                "instrument_code": "BOND-BULLET",
                "instrument_name": "Bullet Bond",
                "maturity_date": date(2027, 7, 15),
                "face_value": Decimal("100"),
                "coupon_rate": Decimal("6.0"),
                "interest_mode": "bullet",
                "currency_code": "CNY",
            }
        ],
        report_date=date(2026, 1, 14),
        horizon_months=24,
    )

    assert [
        (event.event_type, event.event_date.isoformat(), event.amount)
        for event in events
    ] == [
        ("coupon", "2027-07-15", Decimal("6")),
        ("principal", "2027-07-15", Decimal("100")),
    ]


def test_bullet_bond_with_value_date_projects_full_maturity_coupon():
    module = _core_module()

    events = module.project_bond_cashflows(
        [
            {
                "instrument_code": "BOND-BULLET-3Y",
                "instrument_name": "Three Year Bullet Bond",
                "value_date": date(2024, 7, 15),
                "maturity_date": date(2027, 7, 15),
                "face_value": Decimal("100"),
                "coupon_rate": Decimal("6.0"),
                "interest_mode": "bullet",
                "currency_code": "CNY",
            }
        ],
        report_date=date(2026, 1, 14),
        horizon_months=24,
    )

    assert [
        (event.event_type, event.event_date.isoformat(), event.amount)
        for event in events
    ] == [
        ("coupon", "2027-07-15", Decimal("18.00")),
        ("principal", "2027-07-15", Decimal("100")),
    ]


def test_liability_cashflow_projection():
    module = _core_module()

    events = module.project_liability_cashflows(
        [
            {
                "position_id": "TYW-001",
                "counterparty_name": "Bank A",
                "position_side": "liability",
                "maturity_date": date(2026, 1, 31),
                "principal_amount": Decimal("365"),
                "funding_cost_rate": Decimal("10.0"),
                "currency_code": "CNY",
            }
        ],
        report_date=date(2026, 1, 1),
        horizon_months=12,
    )

    assert [
        (event.event_type, event.event_date.isoformat(), event.amount)
        for event in events
    ] == [
        ("funding_cost", "2026-01-31", Decimal("-3.0")),
        ("maturity", "2026-01-31", Decimal("-365")),
    ]


def test_interbank_percent_funding_rate_is_normalized():
    module = _core_module()

    events = module.project_tyw_cashflows(
        [
            {
                "position_id": "TYW-PCT",
                "counterparty_name": "Bank A",
                "position_scope": "asset",
                "maturity_date": date(2026, 1, 31),
                "principal_amount": Decimal("365"),
                "funding_cost_rate": Decimal("10.0"),
                "currency_code": "CNY",
            }
        ],
        report_date=date(2026, 1, 1),
        horizon_months=12,
    )

    assert [
        (event.event_type, event.event_date.isoformat(), event.amount)
        for event in events
    ] == [
        ("funding_income", "2026-01-31", Decimal("3.0")),
        ("maturity", "2026-01-31", Decimal("365")),
    ]


def test_interbank_low_percent_funding_rate_is_normalized():
    module = _core_module()

    events = module.project_tyw_cashflows(
        [
            {
                "position_id": "TYW-LOW-PCT",
                "counterparty_name": "Bank A",
                "position_scope": "asset",
                "maturity_date": date(2026, 1, 31),
                "principal_amount": Decimal("365"),
                "funding_cost_rate": Decimal("0.8"),
                "currency_code": "CNY",
            }
        ],
        report_date=date(2026, 1, 1),
        horizon_months=12,
    )

    assert [
        (event.event_type, event.event_date.isoformat(), event.amount)
        for event in events
    ] == [
        ("funding_income", "2026-01-31", Decimal("0.24")),
        ("maturity", "2026-01-31", Decimal("365")),
    ]


def test_scope_recognizes_non_mojibake_chinese_asset_and_liability_labels():
    module = _core_module()

    assert module._row_scope({"position_scope": "资产"}) == "asset"
    assert module._row_scope({"position_scope": "负债"}) == "liability"
    assert module._row_scope({"position_scope": "璧勪骇"}) == "asset"


def test_monthly_bucket_aggregation():
    module = _core_module()

    buckets = module.build_monthly_buckets(
        [
            module.CashflowEvent(
                event_date=date(2026, 1, 20),
                event_type="coupon",
                instrument_code="A1",
                instrument_name="Asset A1",
                side="asset",
                amount=Decimal("100"),
                currency_code="CNY",
            ),
            module.CashflowEvent(
                event_date=date(2026, 1, 25),
                event_type="funding_cost",
                instrument_code="L1",
                instrument_name="Liability L1",
                side="liability",
                amount=Decimal("-20"),
                currency_code="CNY",
            ),
            module.CashflowEvent(
                event_date=date(2026, 2, 10),
                event_type="principal",
                instrument_code="A2",
                instrument_name="Asset A2",
                side="asset",
                amount=Decimal("50"),
                currency_code="CNY",
            ),
            module.CashflowEvent(
                event_date=date(2026, 2, 15),
                event_type="maturity",
                instrument_code="L2",
                instrument_name="Liability L2",
                side="liability",
                amount=Decimal("-30"),
                currency_code="CNY",
            ),
        ],
        report_date=date(2026, 1, 15),
        horizon_months=2,
    )

    # horizon_end = 2026-03-15：事件纳入到 3/15，桶必须覆盖 2026-03 这个
    # 部分月（修复前只建 horizon_months=2 个桶，3 月事件被静默丢弃）。
    assert [(bucket.year_month, bucket.net_cashflow, bucket.cumulative_net) for bucket in buckets] == [
        ("2026-01", Decimal("80"), Decimal("80")),
        ("2026-02", Decimal("20"), Decimal("100")),
        ("2026-03", Decimal("0"), Decimal("100")),
    ]

    assert buckets[0].asset_inflow == Decimal("100")
    assert buckets[0].liability_outflow == Decimal("20")
    assert buckets[1].asset_inflow == Decimal("50")
    assert buckets[1].liability_outflow == Decimal("30")


def test_monthly_buckets_keep_events_between_last_full_month_and_horizon_end():
    """report 日非月初时，最后完整桶月末到 horizon_end 之间的事件不得丢弃。

    report=2026-01-15、horizon=2 → horizon_end=2026-03-15：3/10 的事件在
    horizon 内，修复前因为桶只建到 2026-02 而被 ``continue`` 静默吞掉；
    3/16 的事件在 horizon 外，必须仍被拒绝。
    """
    module = _core_module()

    def _event(day: date, amount: str) -> object:
        return module.CashflowEvent(
            event_date=day,
            event_type="coupon",
            instrument_code="A1",
            instrument_name="Asset A1",
            side="asset",
            amount=Decimal(amount),
            currency_code="CNY",
        )

    buckets = module.build_monthly_buckets(
        [_event(date(2026, 3, 10), "70"), _event(date(2026, 3, 16), "999")],
        report_date=date(2026, 1, 15),
        horizon_months=2,
    )

    by_month = {bucket.year_month: bucket for bucket in buckets}
    assert list(by_month) == ["2026-01", "2026-02", "2026-03"]
    assert by_month["2026-03"].asset_inflow == Decimal("70")
    assert by_month["2026-03"].cumulative_net == Decimal("70")


def test_monthly_buckets_cover_horizon_end_on_first_of_month_report():
    """report 日是月初时 horizon_end 恰落在第 N+1 个日历月的 1 号，
    当天到期的事件同样必须有桶可归。"""
    module = _core_module()

    buckets = module.build_monthly_buckets(
        [
            module.CashflowEvent(
                event_date=date(2026, 3, 1),
                event_type="principal",
                instrument_code="A1",
                instrument_name="Asset A1",
                side="asset",
                amount=Decimal("40"),
                currency_code="CNY",
            )
        ],
        report_date=date(2026, 1, 1),
        horizon_months=2,
    )

    by_month = {bucket.year_month: bucket for bucket in buckets}
    assert list(by_month) == ["2026-01", "2026-02", "2026-03"]
    assert by_month["2026-03"].asset_inflow == Decimal("40")


def test_duration_gap_calculation_uses_full_scope_term_proxy():
    module = _core_module()

    result = module.compute_duration_gap(
        zqtz_rows=[
            {
                "instrument_code": "BOND-001",
                "instrument_name": "Bond 1",
                "position_scope": "asset",
                "maturity_date": date(2028, 1, 1),
                "face_value_amount": Decimal("100"),
                "market_value_amount": Decimal("100"),
                "coupon_rate": Decimal("5.0"),
                "macaulay_duration": Decimal("1.8"),
                "interest_mode": "annual",
                "currency_code": "CNY",
            },
            {
                "instrument_code": "BOND-002",
                "instrument_name": "Bond 2",
                "position_scope": "liability",
                "maturity_date": date(2027, 1, 1),
                "face_value_amount": Decimal("50"),
                "market_value_amount": Decimal("50"),
                "coupon_rate": Decimal("4.0"),
                "interest_mode": "annual",
                "currency_code": "CNY",
            },
        ],
        tyw_rows=[
            {
                "position_id": "TYW-ASSET-001",
                "counterparty_name": "Bank Asset",
                "position_scope": "asset",
                "maturity_date": date(2026, 7, 1),
                "principal_amount": Decimal("100"),
                "funding_cost_rate": Decimal("3.0"),
                "currency_code": "CNY",
            },
            {
                "position_id": "TYW-LIAB-001",
                "counterparty_name": "Bank Liability",
                "position_scope": "liability",
                "maturity_date": date(2028, 1, 1),
                "principal_amount": Decimal("100"),
                "funding_cost_rate": Decimal("3.0"),
                "currency_code": "CNY",
            },
        ],
        report_date=date(2026, 1, 1),
        horizon_months=24,
    )

    assert result.asset_weighted_duration == Decimal("1.147945205479452054794520548")
    assert result.liability_weighted_duration == Decimal("1.666666666666666666666666667")
    assert result.total_asset_market_value == Decimal("200")
    assert result.total_liability_value == Decimal("150")
    # Full duration coverage: nothing excluded, coverage == 1 on both sides, so the
    # honest caliber must reproduce the textbook full-balance result exactly.
    assert result.asset_duration_covered_balance == Decimal("200")
    assert result.liability_duration_covered_balance == Decimal("150")
    assert result.asset_excluded_balance == Decimal("0")
    assert result.liability_excluded_balance == Decimal("0")
    assert result.asset_duration_coverage_ratio == Decimal("1")
    assert result.liability_duration_coverage_ratio == Decimal("1")
    # Honest caliber: DD_A = Σ(D_i * balance_i) over covered rows; DGAP uses the
    # duration-covered leverage (here L_cov/A_cov == 150/200); D_E = (DD_A - DD_L)/E.
    days_tyw_asset = Decimal((date(2026, 7, 1) - date(2026, 1, 1)).days)
    days_bond_liab = Decimal((date(2027, 1, 1) - date(2026, 1, 1)).days)
    days_tyw_liab = Decimal((date(2028, 1, 1) - date(2026, 1, 1)).days)
    asset_dollar_duration = Decimal("1.8") * Decimal("100") + (days_tyw_asset / Decimal("365")) * Decimal("100")
    liability_dollar_duration = (
        (days_bond_liab / Decimal("365")) * Decimal("50") + (days_tyw_liab / Decimal("365")) * Decimal("100")
    )
    equity = Decimal("200") - Decimal("150")
    expected_gap = result.asset_weighted_duration - (
        Decimal("150") / Decimal("200")
    ) * result.liability_weighted_duration
    expected_equity_duration = (asset_dollar_duration - liability_dollar_duration) / equity
    assert result.duration_gap == expected_gap
    assert result.modified_duration_gap == expected_gap
    assert result.equity_duration == expected_equity_duration
    # Sign convention: rates up 1bp -> equity value change = -(DD_A - DD_L) * 1bp
    assert result.rate_sensitivity_1bp == -((asset_dollar_duration - liability_dollar_duration) * Decimal("0.0001"))
    assert any("remaining-term proxy" in warning for warning in result.warnings)


def test_duration_gap_warns_when_missing_maturity_excludes_rows():
    module = _core_module()

    result = module.compute_duration_gap(
        zqtz_rows=[
            {
                "instrument_code": "BOND-001",
                "instrument_name": "Bond 1",
                "position_scope": "asset",
                "maturity_date": date(2030, 1, 1),
                "face_value_amount": Decimal("300"),
                "market_value_amount": Decimal("300"),
                "coupon_rate": Decimal("4.0"),
                "macaulay_duration": Decimal("3.2"),
                "interest_mode": "annual",
                "currency_code": "CNY",
            },
        ],
        tyw_rows=[
            {
                "position_id": "TYW-001",
                "counterparty_name": "Bank A",
                "position_scope": "liability",
                "maturity_date": None,
                "principal_amount": Decimal("100"),
                "funding_cost_rate": Decimal("3.0"),
                "currency_code": "CNY",
            },
            {
                "position_id": "TYW-002",
                "counterparty_name": "Bank B",
                "position_scope": "liability",
                "maturity_date": date(2028, 1, 1),
                "principal_amount": Decimal("100"),
                "funding_cost_rate": Decimal("3.0"),
                "currency_code": "CNY",
            },
        ],
        report_date=date(2026, 1, 1),
        horizon_months=24,
    )

    assert result.asset_weighted_duration == Decimal("3.2")
    assert result.liability_weighted_duration == Decimal("2")
    assert result.total_asset_market_value == Decimal("300")
    assert result.total_liability_value == Decimal("200")
    # Honest caliber: the 100 liability lacking maturity is NOT assigned the covered
    # average duration; it is disclosed as excluded_balance with coverage 0.5.
    assert result.asset_duration_covered_balance == Decimal("300")
    assert result.liability_duration_covered_balance == Decimal("100")
    assert result.asset_excluded_balance == Decimal("0")
    assert result.liability_excluded_balance == Decimal("100")
    assert result.asset_duration_coverage_ratio == Decimal("1")
    assert result.liability_duration_coverage_ratio == Decimal("0.5")
    # Gap leverage now uses the duration-covered liability base (100/300), not 200/300.
    assert result.duration_gap == Decimal("3.2") - (Decimal("100") / Decimal("300")) * Decimal("2")
    assert result.modified_duration_gap == result.duration_gap
    # DD_A - DD_L = 3.2*300 - 2*100 = 760; D_E = 760/100 = 7.6.
    assert result.equity_duration == Decimal("7.6")
    assert result.rate_sensitivity_1bp == Decimal("-0.076")
    # Regression guard: the old average-duration extrapolation reported 5.6 / -0.0560.
    assert result.equity_duration != Decimal("5.6")
    assert result.rate_sensitivity_1bp != Decimal("-0.0560")
    assert any("missing maturity information" in warning for warning in result.warnings)
    assert any("does not extrapolate" in warning for warning in result.warnings)


def test_duration_gap_excludes_asset_without_duration_from_dollar_duration():
    module = _core_module()

    result = module.compute_duration_gap(
        zqtz_rows=[
            {
                "instrument_code": "BOND-DUR",
                "instrument_name": "Bond with duration",
                "position_scope": "asset",
                "maturity_date": date(2030, 1, 1),
                "market_value_amount": Decimal("100"),
                "macaulay_duration": Decimal("4"),
                "interest_mode": "annual",
                "currency_code": "CNY",
            },
            {
                "instrument_code": "BOND-NODUR",
                "instrument_name": "Asset missing duration",
                "position_scope": "asset",
                "maturity_date": None,
                "market_value_amount": Decimal("100"),
                "interest_mode": "annual",
                "currency_code": "CNY",
            },
        ],
        tyw_rows=[
            {
                "position_id": "TYW-LIAB",
                "counterparty_name": "Bank",
                "position_scope": "liability",
                "maturity_date": date(2027, 1, 1),
                "principal_amount": Decimal("100"),
                "funding_cost_rate": Decimal("3.0"),
                "currency_code": "CNY",
            },
        ],
        report_date=date(2026, 1, 1),
        horizon_months=24,
    )

    # 200 of asset balance, only 100 carries duration.
    assert result.total_asset_market_value == Decimal("200")
    assert result.asset_duration_covered_balance == Decimal("100")
    assert result.asset_excluded_balance == Decimal("100")
    assert result.asset_duration_coverage_ratio == Decimal("0.5")
    assert result.asset_weighted_duration == Decimal("4")
    assert result.liability_excluded_balance == Decimal("0")

    liability_duration = Decimal((date(2027, 1, 1) - date(2026, 1, 1)).days) / Decimal("365")
    assert result.liability_weighted_duration == liability_duration

    # Honest DD gap uses the covered asset balance only: 4*100 - D_L*100. The old
    # caliber applied D_A=4 to the full 200 (=> 800), inflating equity duration.
    equity = Decimal("200") - Decimal("100")
    expected_equity_dollar_duration = Decimal("4") * Decimal("100") - liability_duration * Decimal("100")
    assert result.equity_duration == expected_equity_dollar_duration / equity
    assert result.rate_sensitivity_1bp == -(expected_equity_dollar_duration * Decimal("0.0001"))
    # Gap leverage uses covered asset base (100), not the full 200.
    assert result.duration_gap == Decimal("4") - (Decimal("100") / Decimal("100")) * liability_duration
    assert result.duration_gap != Decimal("4") - (Decimal("100") / Decimal("200")) * liability_duration
    assert any("does not extrapolate" in warning for warning in result.warnings)


def test_duration_gap_excludes_maturity_unavailable_zero_without_term_fallback():
    module = _core_module()

    result = module.compute_duration_gap(
        zqtz_rows=[
            {
                "instrument_code": "BOND-DURATION",
                "position_scope": "asset",
                "maturity_date": date(2031, 1, 1),
                "market_value_amount": Decimal("100"),
                "macaulay_duration": Decimal("5"),
            },
            {
                # The formal analytics fact encodes missing maturity as the
                # DURATION_UNAVAILABLE(0) sentinel. A balance-row date must not
                # turn it into a remaining-term duration proxy.
                "instrument_code": "FUND-NO-MATURITY",
                "position_scope": "asset",
                "maturity_date": date(2031, 1, 1),
                "market_value_amount": Decimal("100"),
                "macaulay_duration": Decimal("0"),
                "duration_quality_flag": "maturity_unavailable",
            },
        ],
        tyw_rows=[],
        report_date=date(2026, 1, 1),
    )

    assert result.total_asset_market_value == Decimal("200")
    assert result.asset_duration_covered_balance == Decimal("100")
    assert result.asset_excluded_balance == Decimal("100")
    assert result.asset_duration_coverage_ratio == Decimal("0.5")
    assert result.asset_weighted_duration == Decimal("5")
    assert any("FUND-NO-MATURITY missing duration information" in warning for warning in result.warnings)


def test_duration_gap_retains_real_matured_zero_duration_in_coverage():
    module = _core_module()

    result = module.compute_duration_gap(
        zqtz_rows=[
            {
                "instrument_code": "MATURED-OUTSTANDING",
                "position_scope": "asset",
                "maturity_date": date(2025, 12, 31),
                "market_value_amount": Decimal("100"),
                "macaulay_duration": Decimal("0"),
                "duration_quality_flag": "no_remaining_term",
            }
        ],
        tyw_rows=[],
        report_date=date(2026, 1, 1),
    )

    assert result.asset_duration_covered_balance == Decimal("100")
    assert result.asset_excluded_balance == Decimal("0")
    assert result.asset_weighted_duration == Decimal("0")
    assert result.duration_gap == Decimal("0")


def test_duration_gap_keeps_1bp_sensitivity_when_equity_is_zero():
    module = _core_module()

    result = module.compute_duration_gap(
        zqtz_rows=[
            {
                "instrument_code": "ASSET-DURATION",
                "position_scope": "asset",
                "maturity_date": date(2031, 1, 1),
                "market_value_amount": Decimal("100"),
                "macaulay_duration": Decimal("2"),
            },
            {
                "instrument_code": "LIABILITY-DURATION",
                "position_scope": "liability",
                "maturity_date": date(2027, 1, 1),
                "market_value_amount": Decimal("100"),
            },
        ],
        tyw_rows=[],
        report_date=date(2026, 1, 1),
    )

    liability_duration = Decimal((date(2027, 1, 1) - date(2026, 1, 1)).days) / Decimal("365")
    expected_dollar_duration = Decimal("2") * Decimal("100") - liability_duration * Decimal("100")
    assert result.equity_duration is None
    assert result.rate_sensitivity_1bp == -(expected_dollar_duration * Decimal("0.0001"))
    assert result.rate_sensitivity_1bp != Decimal("0")
    assert any("equity duration is unavailable" in warning.lower() for warning in result.warnings)


def test_duration_gap_zero_assets_returns_unavailable_metrics():
    module = _core_module()

    result = module.compute_duration_gap(
        zqtz_rows=[
            {
                "instrument_code": "BOND-LIAB",
                "instrument_name": "Issued bond",
                "position_scope": "liability",
                "maturity_date": date(2028, 1, 1),
                "market_value_amount": Decimal("500"),
                "coupon_rate": Decimal("3.0"),
                "interest_mode": "annual",
                "currency_code": "CNY",
            },
        ],
        tyw_rows=[],
        report_date=date(2026, 1, 1),
        horizon_months=24,
    )

    assert result.total_asset_market_value == Decimal("0")
    assert result.total_liability_value == Decimal("500")
    # Asset denominator is zero -> duration-gap family is unavailable (None), never a
    # misleading -liability_duration value.
    assert result.asset_weighted_duration is None
    assert result.duration_gap is None
    assert result.modified_duration_gap is None
    assert result.equity_duration is None
    assert result.rate_sensitivity_1bp is None
    assert result.reinvestment_risk_12m is None
    assert result.asset_duration_coverage_ratio is None
    # Liability duration is still observable and disclosed.
    liability_duration = Decimal((date(2028, 1, 1) - date(2026, 1, 1)).days) / Decimal("365")
    assert result.liability_weighted_duration == liability_duration
    assert result.liability_duration_covered_balance == Decimal("500")
    assert any("unavailable" in warning for warning in result.warnings)


def test_tywl_demand_positions_without_maturity_use_one_month_proxy():
    module = _core_module()

    result = module.compute_duration_gap(
        zqtz_rows=[],
        tyw_rows=[
            {
                "position_id": "TYW-ASSET-001",
                "product_type": "存放同业",
                "counterparty_name": "Bank Asset",
                "position_scope": "asset",
                "maturity_date": None,
                "principal_amount": Decimal("100"),
                "funding_cost_rate": Decimal("3.0"),
                "currency_code": "CNY",
            },
            {
                "position_id": "TYW-LIAB-001",
                "product_type": "同业存放",
                "counterparty_name": "Bank Liability",
                "position_scope": "liability",
                "maturity_date": None,
                "principal_amount": Decimal("100"),
                "funding_cost_rate": Decimal("3.0"),
                "currency_code": "CNY",
            },
        ],
        report_date=date(2026, 1, 1),
        horizon_months=24,
    )

    one_month_proxy = Decimal("31") / Decimal("365")
    assert result.asset_weighted_duration == one_month_proxy
    assert result.liability_weighted_duration == one_month_proxy
    assert result.duration_gap == Decimal("0")
    assert result.modified_duration_gap == Decimal("0")
    assert all("missing maturity information" not in warning for warning in result.warnings)


def test_tywl_demand_positions_without_maturity_project_into_next_month():
    module = _core_module()

    cashflows = module.project_tyw_cashflows(
        [
            {
                "position_id": "TYW-ASSET-001",
                "product_type": "存放同业",
                "counterparty_name": "Bank Asset",
                "position_scope": "asset",
                "maturity_date": None,
                "principal_amount": Decimal("100"),
                "funding_cost_rate": Decimal("3.0"),
                "currency_code": "CNY",
            },
            {
                "position_id": "TYW-LIAB-001",
                "product_type": "同业存放",
                "counterparty_name": "Bank Liability",
                "position_scope": "liability",
                "maturity_date": None,
                "principal_amount": Decimal("80"),
                "funding_cost_rate": Decimal("3.0"),
                "currency_code": "CNY",
            },
        ],
        report_date=date(2026, 1, 1),
        horizon_months=2,
    )

    assert [(event.event_type, event.event_date.isoformat(), event.side, event.amount) for event in cashflows] == [
        ("funding_cost", "2026-02-01", "liability", Decimal("-0.2038356164383561643835616438")),
        ("funding_income", "2026-02-01", "asset", Decimal("0.2547945205479452054794520548")),
        ("maturity", "2026-02-01", "asset", Decimal("100")),
        ("maturity", "2026-02-01", "liability", Decimal("-80")),
    ]


def test_reinvestment_risk_ratio():
    module = _core_module()

    result = module.compute_duration_gap(
        zqtz_rows=[
            {
                "instrument_code": "BOND-NEAR",
                "instrument_name": "Near Maturity",
                "position_scope": "asset",
                "maturity_date": date(2026, 6, 1),
                "face_value_amount": Decimal("100"),
                "market_value_amount": Decimal("100"),
                "coupon_rate": Decimal("3.0"),
                "interest_mode": "骞翠粯",
                "currency_code": "CNY",
            },
            {
                "instrument_code": "BOND-LONG",
                "instrument_name": "Long Bond",
                "position_scope": "asset",
                "maturity_date": date(2028, 1, 1),
                "face_value_amount": Decimal("300"),
                "market_value_amount": Decimal("300"),
                "coupon_rate": Decimal("5.0"),
                "interest_mode": "骞翠粯",
                "currency_code": "CNY",
            },
        ],
        tyw_rows=[],
        report_date=date(2026, 1, 1),
        horizon_months=24,
    )

    assert result.reinvestment_risk_12m == Decimal("0.25")


def test_cashflow_projection_read_surface_requires_explicit_read_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{(tmp_path / 'cashflow-projection-read-scope.db').as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    route_mod = load_module(
        "backend.app.api.routes.cashflow_projection",
        "backend/app/api/routes/cashflow_projection.py",
    )
    app = FastAPI()
    app.include_router(route_mod.router)
    client = TestClient(app)

    response = client.get(
        "/api/cashflow-projection",
        params={"report_date": "2026-01-01"},
        headers=CASHFLOW_PROJECTION_READ_HEADERS,
    )

    assert response.status_code == 403


def test_api_returns_envelope(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()

    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )

    def fake_fetch_zqtz_rows(self, *, report_date, position_scope="all", currency_basis="CNY"):
        assert report_date == "2026-01-01"
        assert position_scope == "all"
        assert currency_basis == "CNY"
        return [
            {
                "instrument_code": "BOND-001",
                "instrument_name": "Bond 1",
                "position_scope": "asset",
                "maturity_date": date(2026, 7, 1),
                "face_value_amount": Decimal("100"),
                "market_value_amount": Decimal("100"),
                "coupon_rate": Decimal("5.0"),
                "interest_mode": "骞翠粯",
                "currency_code": "CNY",
                "source_version": "sv_bond_1",
                "rule_version": "rv_bond_1",
                "ingest_batch_id": "ib_zqtz_1",
                "trace_id": "tr_zqtz_1",
            }
        ]

    def fake_fetch_tyw_rows(self, *, report_date, currency_basis="CNY"):
        assert report_date == "2026-01-01"
        assert currency_basis == "CNY"
        return [
            {
                "position_id": "TYW-001",
                "counterparty_name": "Bank A",
                "position_scope": "liability",
                "maturity_date": date(2026, 3, 1),
                "principal_amount": Decimal("80"),
                "funding_cost_rate": Decimal("3.0"),
                "currency_code": "CNY",
                "source_version": "sv_tyw_1",
                "rule_version": "rv_tyw_1",
                "trace_id": "tr_tyw_1",
            }
        ]

    def fake_fetch_analytics_rows(self, *, report_date, asset_class="all", accounting_class="all"):
        assert report_date == "2026-01-01"
        assert asset_class == "all"
        assert accounting_class == "all"
        return [
            {
                "instrument_code": "BOND-001",
                "portfolio_name": "",
                "cost_center": "",
                "currency_code": "CNY",
                "macaulay_duration": Decimal("1.25"),
                "duration_quality_flag": "observed",
                "source_version": "sv_bond_analytics_1",
                "rule_version": "rv_bond_analytics_formal_materialize_v6",
                "ingest_batch_id": "ib_analytics_1",
                "trace_id": "tr_analytics_1",
            }
        ]

    monkeypatch.setattr(
        service_mod.CashflowProjectionRepository,
        "fetch_formal_zqtz_rows",
        fake_fetch_zqtz_rows,
    )
    monkeypatch.setattr(
        service_mod.CashflowProjectionRepository,
        "fetch_formal_tyw_liability_rows",
        fake_fetch_tyw_rows,
    )
    monkeypatch.setattr(
        service_mod.BondAnalyticsRepository,
        "fetch_bond_analytics_rows",
        fake_fetch_analytics_rows,
    )

    route_mod = load_module(
        "backend.app.api.routes.cashflow_projection",
        "backend/app/api/routes/cashflow_projection.py",
    )
    _grant_cashflow_projection_read_scope(tmp_path, monkeypatch)
    app = FastAPI()
    app.include_router(route_mod.router)
    client = TestClient(app)
    response = client.get(
        "/api/cashflow-projection",
        params={"report_date": "2026-01-01"},
        headers=CASHFLOW_PROJECTION_READ_HEADERS,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["formal_use_allowed"] is False
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result_meta"]["scenario_flag"] is False
    assert payload["result_meta"]["result_kind"] == "cashflow_projection.overview"
    assert payload["result_meta"]["cache_version"] == "cv_cashflow_projection_read_v3"
    assert payload["result_meta"]["source_version"] == "sv_bond_1__sv_bond_analytics_1__sv_tyw_1"
    assert payload["result_meta"]["rule_version"] == (
        "rv_bond_1__rv_bond_analytics_formal_materialize_v6__rv_cashflow_projection_read_v3__rv_tyw_1"
    )
    assert payload["result_meta"]["source_surface"] == "cashflow"
    assert payload["result_meta"]["requested_report_date"] == "2026-01-01"
    assert payload["result_meta"]["resolved_report_date"] == "2026-01-01"
    assert payload["result_meta"]["as_of_date"] == "2026-01-01"
    assert payload["result_meta"]["date_basis"] == "cashflow_projection_report_date"
    assert payload["result_meta"]["filters_applied"] == {
        "report_date": "2026-01-01",
        "position_scope": "all",
        "currency_basis": "CNY",
    }
    assert payload["result_meta"]["tables_used"] == [
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
        "fact_formal_bond_analytics_daily",
    ]
    assert payload["result_meta"]["evidence_rows"] == 3
    assert payload["result"]["report_date"] == "2026-01-01"
    assert "duration_gap" in payload["result"]
    assert payload["result"]["duration_gap"]["unit"] == "years"
    assert payload["result"]["duration_gap"]["precision"] == 2
    assert payload["result"]["duration_gap"]["sign_aware"] is True
    assert payload["result"]["asset_duration"]["unit"] == "years"
    assert payload["result"]["asset_duration"]["precision"] == 2
    assert payload["result"]["asset_duration"]["sign_aware"] is False
    assert payload["result"]["liability_duration"]["unit"] == "years"
    assert payload["result"]["liability_duration"]["precision"] == 2
    assert payload["result"]["liability_duration"]["sign_aware"] is False
    assert payload["result"]["equity_duration"]["unit"] == "years"
    assert payload["result"]["equity_duration"]["precision"] == 2
    assert payload["result"]["equity_duration"]["sign_aware"] is True
    assert payload["result"]["rate_sensitivity_1bp"]["unit"] == "yuan"
    assert payload["result"]["reinvestment_risk_12m"]["unit"] == "pct"
    assert payload["result"]["asset_duration_covered_balance"] == {
        "raw": 100.0,
        "raw_text": "100",
        "unit": "yuan",
        "display": "100.00",
        "precision": 2,
        "sign_aware": False,
    }
    assert payload["result"]["asset_excluded_balance"]["raw"] == 0.0
    assert payload["result"]["asset_duration_coverage_ratio"]["raw"] == 1.0
    assert payload["result"]["asset_duration_coverage_ratio"]["unit"] == "pct"
    assert payload["result"]["input_lineage"] == [
        {
            "table_name": "fact_formal_zqtz_balance_daily",
            "row_count": 1,
            "source_versions": ["sv_bond_1"],
            "rule_versions": ["rv_bond_1"],
            "ingest_batch_ids": ["ib_zqtz_1"],
            "trace_ids": ["tr_zqtz_1"],
        },
        {
            "table_name": "fact_formal_tyw_balance_daily",
            "row_count": 1,
            "source_versions": ["sv_tyw_1"],
            "rule_versions": ["rv_tyw_1"],
            "ingest_batch_ids": [],
            "trace_ids": ["tr_tyw_1"],
        },
        {
            "table_name": "fact_formal_bond_analytics_daily",
            "row_count": 1,
            "source_versions": ["sv_bond_analytics_1"],
            "rule_versions": ["rv_bond_analytics_formal_materialize_v6"],
            "ingest_batch_ids": ["ib_analytics_1"],
            "trace_ids": ["tr_analytics_1"],
        },
    ]
    assert "monthly_buckets" in payload["result"]
    assert "top_maturing_assets_12m" in payload["result"]
    assert "computed_at" in payload["result"]

    get_settings.cache_clear()


@pytest.mark.parametrize(
    "stale_rule_version",
    ["rv_bond_analytics_formal_materialize_v4", "rv_bond_analytics_formal_materialize_v5"],
)
def test_service_rejects_explicit_stale_bond_analytics_rule(
    tmp_path, monkeypatch, stale_rule_version
):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()

    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )
    monkeypatch.setattr(
        service_mod.CashflowProjectionRepository,
        "fetch_formal_zqtz_rows",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        service_mod.CashflowProjectionRepository,
        "fetch_formal_tyw_liability_rows",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        service_mod.BondAnalyticsRepository,
        "fetch_bond_analytics_rows",
        lambda *_args, **_kwargs: [{"rule_version": stale_rule_version}],
    )

    with pytest.raises(RuntimeError) as exc_info:
        service_mod.get_cashflow_projection(date(2026, 1, 1))
    assert "expected rv_bond_analytics_formal_materialize_v6" in str(exc_info.value)
    assert f"got {stale_rule_version}" in str(exc_info.value)
    assert "Rematerialize required." in str(exc_info.value)

    get_settings.cache_clear()


def test_service_accepts_v6_bond_analytics_and_records_rule_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )
    key = {
        "instrument_code": "SYNTHETIC-V6-ANALYTICS",
        "portfolio_name": "P1",
        "cost_center": "C1",
        "currency_code": "CNY",
    }
    zqtz_row = {
        **key,
        "instrument_name": "Synthetic V6 bond",
        "position_scope": "asset",
        "maturity_date": date(2028, 1, 1),
        "face_value_amount": Decimal("100"),
        "market_value_amount": Decimal("100"),
        "coupon_rate": Decimal("3"),
        "interest_mode": "annual",
    }
    analytics_row = {
        **key,
        "macaulay_duration": Decimal("1.25"),
        "duration_quality_flag": "observed",
        "rule_version": "rv_bond_analytics_formal_materialize_v6",
    }
    monkeypatch.setattr(
        service_mod.CashflowProjectionRepository,
        "fetch_formal_zqtz_rows",
        lambda *_args, **_kwargs: [zqtz_row],
    )
    monkeypatch.setattr(
        service_mod.CashflowProjectionRepository,
        "fetch_formal_tyw_liability_rows",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        service_mod.BondAnalyticsRepository,
        "fetch_bond_analytics_rows",
        lambda *_args, **_kwargs: [analytics_row],
    )

    payload = service_mod.get_cashflow_projection(date(2026, 1, 1))

    assert payload["result"]["asset_duration"]["raw_text"] == "1.25"
    assert payload["result_meta"]["formal_use_allowed"] is False
    assert payload["result_meta"]["rule_version"] == (
        "rv_bond_analytics_formal_materialize_v6__rv_cashflow_projection_read_v3"
    )
    assert payload["result"]["input_lineage"][2] == {
        "table_name": "fact_formal_bond_analytics_daily",
        "row_count": 1,
        "source_versions": [],
        "rule_versions": ["rv_bond_analytics_formal_materialize_v6"],
        "ingest_batch_ids": [],
        "trace_ids": [],
    }
    get_settings.cache_clear()


def test_service_response_preserves_lossless_raw_text(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()

    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )

    def fake_fetch_zqtz_rows(self, *, report_date, position_scope="all", currency_basis="CNY"):
        assert report_date == "2026-01-01"
        assert position_scope == "all"
        assert currency_basis == "CNY"
        return [
            {
                "instrument_code": "CF-BOND-001",
                "instrument_name": "Cashflow Bond",
                "portfolio_name": "P1",
                "cost_center": "C1",
                "position_scope": "asset",
                "maturity_date": date(2026, 6, 1),
                "face_value_amount": Decimal("100.00000001"),
                "market_value_amount": Decimal("99.99999999"),
                "coupon_rate": Decimal("5.0"),
                "interest_mode": "annual",
                "currency_code": "CNY",
                "source_version": "sv_cashflow_asset",
                "rule_version": "rv_cashflow_asset",
            }
        ]

    def fake_fetch_tyw_rows(self, *, report_date, currency_basis="CNY"):
        assert report_date == "2026-01-01"
        assert currency_basis == "CNY"
        return []

    monkeypatch.setattr(
        service_mod.CashflowProjectionRepository,
        "fetch_formal_zqtz_rows",
        fake_fetch_zqtz_rows,
    )
    monkeypatch.setattr(
        service_mod.CashflowProjectionRepository,
        "fetch_formal_tyw_liability_rows",
        fake_fetch_tyw_rows,
    )
    monkeypatch.setattr(
        service_mod.BondAnalyticsRepository,
        "fetch_bond_analytics_rows",
        lambda self, *, report_date, asset_class="all", accounting_class="all": [],
    )
    monkeypatch.setattr(
        service_mod,
        "compute_duration_gap",
        lambda **kwargs: SimpleNamespace(
            duration_gap=Decimal("0.05000001"),
            asset_weighted_duration=Decimal("3.50000001"),
            liability_weighted_duration=Decimal("1.50000001"),
            equity_duration=Decimal("-2.00000001"),
            rate_sensitivity_1bp=Decimal("-0.01000001"),
            reinvestment_risk_12m=Decimal("1.25000001"),
            asset_duration_covered_balance=Decimal("99.99999999"),
            liability_duration_covered_balance=Decimal("0"),
            asset_excluded_balance=Decimal("0"),
            liability_excluded_balance=Decimal("0"),
            asset_duration_coverage_ratio=Decimal("1"),
            liability_duration_coverage_ratio=None,
            monthly_buckets=[
                service_mod.MonthlyBucket(
                    year_month="2026-01",
                    asset_inflow=Decimal("100.00000001"),
                    liability_outflow=Decimal("100.00000002"),
                    net_cashflow=Decimal("-0.01000001"),
                    cumulative_net=Decimal("-0.01000001"),
                )
            ],
            warnings=[],
        ),
    )

    payload = service_mod.get_cashflow_projection(date(2026, 1, 1))
    result = payload["result"]

    assert result["duration_gap"]["raw_text"] == "0.05000001"
    assert result["asset_duration"]["raw_text"] == "3.50000001"
    assert result["liability_duration"]["raw_text"] == "1.50000001"
    assert result["equity_duration"]["raw_text"] == "-2.00000001"
    assert result["rate_sensitivity_1bp"]["raw_text"] == "-0.01000001"
    assert result["reinvestment_risk_12m"]["raw"] == 1.25000001
    assert result["reinvestment_risk_12m"]["raw_text"] == "1.25000001"
    assert result["reinvestment_risk_12m"]["display"] == "125.00%"
    assert result["monthly_buckets"][0]["net_cashflow"]["raw_text"] == "-0.01000001"
    assert result["monthly_buckets"][0]["asset_inflow"]["raw_text"] == "100.00000001"
    assert result["top_maturing_assets_12m"][0]["face_value"]["raw_text"] == "100.00000001"
    assert result["top_maturing_assets_12m"][0]["market_value"]["raw_text"] == "99.99999999"
    for field_name in (
        "floating_rate_proxy_market_value",
        "payment_frequency_fallback_market_value",
        "bullet_value_date_fallback_market_value",
    ):
        assert result[field_name]["raw_text"] is not None

    get_settings.cache_clear()


def test_api_prefers_materialized_asset_macaulay_duration(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()

    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )
    def fake_fetch_zqtz_rows(self, *, report_date, position_scope="all", currency_basis="CNY"):
        assert report_date == "2026-01-01"
        return [
            {
                "instrument_code": "BOND-001",
                "instrument_name": "Bond 1",
                "portfolio_name": "P1",
                "cost_center": "C1",
                "position_scope": "asset",
                "maturity_date": date(2031, 1, 1),
                "face_value_amount": Decimal("100"),
                "market_value_amount": Decimal("100"),
                "coupon_rate": Decimal("3.0"),
                "ytm_value": Decimal("3.5"),
                "interest_mode": "annual",
                "currency_code": "CNY",
                "source_version": "sv_zqtz_1",
                "rule_version": "rv_zqtz_1",
            }
        ]

    def fake_fetch_tyw_rows(self, *, report_date, currency_basis="CNY"):
        assert report_date == "2026-01-01"
        return []

    def fake_fetch_bond_analytics_rows(self, *, report_date, asset_class="all", accounting_class="all"):
        assert report_date == "2026-01-01"
        return [
            {
                "report_date": date(2026, 1, 1),
                "instrument_code": "BOND-001",
                "instrument_name": "Bond 1",
                "portfolio_name": "P1",
                "cost_center": "C1",
                "currency_code": "CNY",
                "maturity_date": date(2031, 1, 1),
                "coupon_rate": Decimal("0.03"),
                "ytm": Decimal("0.035"),
                "macaulay_duration": Decimal("1.25"),
            }
        ]

    monkeypatch.setattr(
        service_mod.CashflowProjectionRepository,
        "fetch_formal_zqtz_rows",
        fake_fetch_zqtz_rows,
    )
    monkeypatch.setattr(
        service_mod.CashflowProjectionRepository,
        "fetch_formal_tyw_liability_rows",
        fake_fetch_tyw_rows,
    )
    monkeypatch.setattr(
        service_mod.BondAnalyticsRepository,
        "fetch_bond_analytics_rows",
        fake_fetch_bond_analytics_rows,
    )

    route_mod = load_module(
        "backend.app.api.routes.cashflow_projection",
        "backend/app/api/routes/cashflow_projection.py",
    )
    _grant_cashflow_projection_read_scope(tmp_path, monkeypatch)
    app = FastAPI()
    app.include_router(route_mod.router)
    client = TestClient(app)
    response = client.get(
        "/api/cashflow-projection",
        params={"report_date": "2026-01-01"},
        headers=CASHFLOW_PROJECTION_READ_HEADERS,
    )

    assert response.status_code == 200
    payload = response.json()
    assert Decimal(str(payload["result"]["asset_duration"]["raw"])) == Decimal("1.25")

    get_settings.cache_clear()


def test_duration_fallback_uses_decimal_rates_and_semiannual_frequency():
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )
    bond_duration_mod = load_module(
        "backend.app.core_finance.bond_duration",
        "backend/app/core_finance/bond_duration.py",
    )
    row = {
        "report_date": date(2026, 1, 1),
        "maturity_date": date(2031, 1, 1),
        "instrument_code": "BOND-SEMI-001",
        "coupon_rate": Decimal("0.03"),
        "ytm": Decimal("0.035"),
        "interest_mode": "semi-annual",
        "macaulay_duration": None,
    }

    expected = bond_duration_mod.estimate_duration(
        date(2031, 1, 1),
        date(2026, 1, 1),
        coupon_rate=Decimal("0.03"),
        ytm=Decimal("0.035"),
        bond_code="BOND-SEMI-001",
        coupon_frequency=2,
    )

    assert service_mod._recompute_macaulay_duration(row) == expected


@pytest.mark.parametrize("interest_mode", ["annual", "bullet"])
@pytest.mark.parametrize(
    ("yield_fields", "effective_ytm"),
    [
        pytest.param({}, Decimal("0.03"), id="absent"),
        pytest.param({"ytm": None, "ytm_value": None}, Decimal("0.03"), id="null"),
        pytest.param({"ytm": "", "ytm_value": ""}, Decimal("0.03"), id="empty"),
        pytest.param({"ytm": " "}, Decimal("0.03"), id="whitespace"),
        pytest.param({"ytm": "not-a-yield"}, Decimal("0.03"), id="invalid-primary"),
        pytest.param({"ytm_value": "not-a-yield"}, Decimal("0.03"), id="invalid-alias"),
        pytest.param({"ytm": Decimal("NaN")}, Decimal("0.03"), id="nan"),
        pytest.param({"ytm": "Infinity"}, Decimal("0.03"), id="infinity"),
        pytest.param({"ytm_value": float("-inf")}, Decimal("0.03"), id="negative-infinity"),
        pytest.param({"ytm": Decimal("0")}, Decimal("0"), id="observed-zero"),
        pytest.param({"ytm": "0.03500001"}, Decimal("0.03500001"), id="observed-positive"),
        pytest.param({"ytm": Decimal("-0.01")}, Decimal("-0.01"), id="observed-negative"),
        pytest.param({"ytm": None, "ytm_value": "0"}, Decimal("0"), id="alias-zero"),
        pytest.param({"ytm": "", "ytm_value": "0.035"}, Decimal("0.035"), id="alias-positive"),
        pytest.param({"ytm_value": "-0.01"}, Decimal("-0.01"), id="alias-negative"),
        pytest.param(
            {"ytm": Decimal("0"), "ytm_value": Decimal("0.035")},
            Decimal("0"),
            id="primary-zero-precedes-alias",
        ),
    ],
)
def test_duration_fallback_distinguishes_missing_and_observed_yields(
    yield_fields, effective_ytm, interest_mode
):
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )
    row = {
        "report_date": date(2026, 1, 1),
        "maturity_date": date(2028, 1, 1),
        "instrument_code": "SYNTHETIC-YIELD-SEMANTICS",
        "coupon_rate": Decimal("0.03"),
        "interest_mode": interest_mode,
        **yield_fields,
    }

    if interest_mode == "bullet":
        expected = Decimal("2")
    else:
        # Independent two-cashflow PV weighting, with decimal annual rates.
        first_pv = Decimal("0.03") / (Decimal("1") + effective_ytm)
        final_pv = Decimal("1.03") / (Decimal("1") + effective_ytm) ** 2
        expected = (first_pv + Decimal("2") * final_pv) / (first_pv + final_pv)

    assert service_mod._recompute_macaulay_duration(row) == expected


@pytest.mark.parametrize("duration", [Decimal("0"), Decimal("1.25000001")])
def test_attach_duration_prefers_valid_materialized_value_over_invalid_yield(
    duration, monkeypatch
):
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )
    key_fields = {
        "instrument_code": "SYNTHETIC-MATERIALIZED-DURATION",
        "portfolio_name": "P1",
        "cost_center": "C1",
        "currency_code": "CNY",
    }

    def unexpected_recompute(_row):
        pytest.fail("A valid materialized duration must not be recomputed.")

    monkeypatch.setattr(service_mod, "_recompute_macaulay_duration_with_assumption", unexpected_recompute)
    enriched = service_mod._attach_macaulay_duration(
        [{**key_fields, "position_scope": "asset"}],
        [{**key_fields, "macaulay_duration": duration, "ytm": "not-a-yield"}],
    )

    assert enriched[0]["macaulay_duration"] == duration


def test_attach_duration_preserves_par_fallback_quality_flag_after_recomputation():
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )
    key_fields = {
        "instrument_code": "SYNTHETIC-PAR-FALLBACK",
        "portfolio_name": "P1",
        "cost_center": "C1",
        "currency_code": "CNY",
    }
    analytics_row = {
        **key_fields,
        "report_date": date(2026, 1, 1),
        "maturity_date": date(2028, 1, 1),
        "coupon_rate": Decimal("0.03"),
        "interest_mode": "annual",
        "ytm": None,
        "macaulay_duration": None,
        "duration_quality_flag": "ytm_par_fallback",
    }

    enriched = service_mod._attach_macaulay_duration(
        [{**key_fields, "position_scope": "asset"}], [analytics_row]
    )

    assert enriched[0]["duration_quality_flag"] == "ytm_par_fallback"
    assert enriched[0]["macaulay_duration"] == Decimal("1.970873786407766990291262136")


def test_cashflow_par_recompute_without_source_flag_discloses_assumption(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(tmp_path / "moss.duckdb"))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )
    key = {
        "instrument_code": "SYNTHETIC-PAR-NO-FLAG",
        "portfolio_name": "P1",
        "cost_center": "C1",
        "currency_code": "CNY",
    }
    zqtz_row = {
        **key,
        "position_scope": "asset",
        "maturity_date": date(2028, 1, 1),
        "face_value_amount": Decimal("100"),
        "market_value_amount": Decimal("100"),
        "coupon_rate": Decimal("3"),
        "interest_mode": "annual",
    }
    analytics_row = {
        **key,
        "report_date": date(2026, 1, 1),
        "maturity_date": date(2028, 1, 1),
        "coupon_rate": Decimal("0.03"),
        "interest_mode": "annual",
        "ytm": None,
        "macaulay_duration": None,
    }
    monkeypatch.setattr(
        service_mod.CashflowProjectionRepository,
        "fetch_formal_zqtz_rows",
        lambda *_args, **_kwargs: [zqtz_row],
    )
    monkeypatch.setattr(
        service_mod.CashflowProjectionRepository,
        "fetch_formal_tyw_liability_rows",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        service_mod.BondAnalyticsRepository,
        "fetch_bond_analytics_rows",
        lambda *_args, **_kwargs: [analytics_row],
    )

    result = service_mod.get_cashflow_projection(date(2026, 1, 1))["result"]

    assert result["asset_duration"]["raw_text"] == "1.970873786407766990291262136"
    assert any("par assumption" in warning for warning in result["warnings"])
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("ytm", "materialized", "interest_mode", "uses_par"),
    [
        pytest.param(None, None, "annual", True, id="missing-annual"),
        pytest.param("invalid", None, "annual", True, id="dirty-annual"),
        pytest.param(Decimal("0"), None, "annual", False, id="observed-zero"),
        pytest.param(Decimal("-0.01"), None, "annual", False, id="observed-negative"),
        pytest.param(Decimal("0.035"), None, "annual", False, id="observed-positive"),
        pytest.param(None, Decimal("0"), "annual", False, id="materialized-zero"),
        pytest.param(None, Decimal("1.25"), "annual", False, id="materialized-positive"),
        pytest.param(None, Decimal("NaN"), "annual", True, id="invalid-materialized"),
        pytest.param(None, None, "bullet", True, id="missing-bullet"),
        pytest.param(Decimal("0"), None, "bullet", False, id="observed-zero-bullet"),
    ],
)
def test_par_duration_warning_tracks_used_yield_and_materialized_duration(
    ytm, materialized, interest_mode, uses_par
):
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )
    key = {
        "instrument_code": "SYNTHETIC-PAR-CASE",
        "portfolio_name": "P1",
        "cost_center": "C1",
        "currency_code": "CNY",
    }
    asset = {**key, "position_scope": "asset", "market_value_amount": Decimal("100")}
    analytics = {
        **key,
        "report_date": date(2026, 1, 1),
        "maturity_date": date(2028, 1, 1),
        "coupon_rate": Decimal("0.03"),
        "interest_mode": interest_mode,
        "ytm": ytm,
        "macaulay_duration": materialized,
    }
    original_asset, original_analytics = asset.copy(), analytics.copy()

    enriched = service_mod._attach_macaulay_duration([asset], [analytics])
    par_warnings = [
        warning
        for warning in service_mod._cashflow_projection_quality_disclosures(enriched)["warnings"]
        if "par assumption" in warning
    ]

    assert asset == original_asset
    assert analytics == original_analytics
    if uses_par:
        assert enriched[0]["_par_duration_assumption_used"] is True
    else:
        assert enriched[0]["_par_duration_assumption_used"] is False
    assert len(par_warnings) == int(uses_par)
    if uses_par:
        assert enriched[0]["duration_quality_flag"] == "ytm_par_fallback"
        assert "market_value=100" in par_warnings[0]
    elif materialized is not None and materialized.is_finite():
        assert enriched[0]["macaulay_duration"] == materialized


def test_par_duration_warning_respects_scope_coverage_and_existing_quality():
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )

    def pair(code, *, scope="asset", market_value=Decimal("100"), maturity=True, flag=None):
        key = {
            "instrument_code": code,
            "portfolio_name": "P1",
            "cost_center": "C1",
            "currency_code": "CNY",
        }
        asset = {
            **key,
            "position_scope": scope,
            "market_value": market_value,
            "market_value_amount": Decimal("100"),
        }
        analytics = {
            **key,
            "report_date": date(2026, 1, 1),
            "maturity_date": date(2028, 1, 1) if maturity else None,
            "coupon_rate": Decimal("0.03"),
            "interest_mode": "annual",
            "ytm": None,
            "macaulay_duration": None,
        }
        if flag is not None:
            analytics["duration_quality_flag"] = flag
        return asset, analytics

    cases = [
        pair("USED-PAR"),
        pair("ZERO-MARKET", market_value=Decimal("0")),
        pair("NEGATIVE-MARKET", market_value=Decimal("-5")),
        pair("LIABILITY", scope="liability"),
        pair("NO-MATURITY", maturity=False),
        pair("UNAVAILABLE", flag="maturity_unavailable"),
        pair("OTHER-QUALITY", flag="floating_rate_fixed_coupon_proxy"),
    ]
    matured_asset, matured_analytics = pair("MATURED")
    matured_analytics["maturity_date"] = date(2025, 12, 31)
    cases.append((matured_asset, matured_analytics))
    unmatched_asset, _ = pair("NO-MATCH")
    reused_asset, _ = pair("REUSED-INPUT")
    reused_asset["_par_duration_assumption_used"] = True
    rows = [asset for asset, _ in cases] + [unmatched_asset, reused_asset]
    analytics_rows = [analytics for _, analytics in cases]

    enriched = service_mod._attach_macaulay_duration(rows, analytics_rows)
    by_code = {row["instrument_code"]: row for row in enriched}
    par_warnings = [
        warning
        for warning in service_mod._cashflow_projection_quality_disclosures(enriched)["warnings"]
        if "par assumption" in warning
    ]

    assert len(par_warnings) == 1
    assert "2 asset rows with market_value=200" in par_warnings[0]
    assert by_code["OTHER-QUALITY"]["duration_quality_flag"] == "floating_rate_fixed_coupon_proxy"
    assert by_code["OTHER-QUALITY"]["_par_duration_assumption_used"] is True
    assert by_code["UNAVAILABLE"]["duration_quality_flag"] == "maturity_unavailable"
    assert by_code["UNAVAILABLE"]["_par_duration_assumption_used"] is False
    assert by_code["MATURED"]["_par_duration_assumption_used"] is False
    assert "macaulay_duration" not in by_code["NO-MATURITY"]
    assert "_par_duration_assumption_used" not in by_code["LIABILITY"]
    assert "_par_duration_assumption_used" not in by_code["NO-MATCH"]
    assert by_code["REUSED-INPUT"]["_par_duration_assumption_used"] is False
    assert reused_asset["_par_duration_assumption_used"] is True


def test_duration_fallback_uses_single_cashflow_path_for_bullet_bonds():
    """bullet（到期一次还本付息）唯一现金流在到期日：Macaulay 恒等于剩余年限。

    修复前该路径按年付多期贴现（coupon_frequency_per_year("bullet") == 1），
    把 Macaulay 拉向虚构的中途票息时点、低估久期；现与 bond_analytics.engine
    的 single_cashflow_at_maturity 口径对齐。
    """
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )
    bond_duration_mod = load_module(
        "backend.app.core_finance.bond_duration",
        "backend/app/core_finance/bond_duration.py",
    )
    report_date = date(2026, 1, 1)
    maturity_date = date(2031, 1, 1)
    row = {
        "report_date": report_date,
        "maturity_date": maturity_date,
        "instrument_code": "BOND-BULLET-001",
        "coupon_rate": Decimal("0.03"),
        "ytm": Decimal("0.035"),
        "interest_mode": "到期一次还本付息",
        "macaulay_duration": None,
    }

    expected_remaining_years = (
        Decimal((maturity_date - report_date).days) / Decimal("365")
    )
    legacy_annual_multi_period = bond_duration_mod.estimate_duration(
        maturity_date,
        report_date,
        coupon_rate=Decimal("0.03"),
        ytm=Decimal("0.035"),
        bond_code="BOND-BULLET-001",
        coupon_frequency=1,
    )

    assert service_mod._recompute_macaulay_duration(row) == expected_remaining_years
    assert legacy_annual_multi_period < expected_remaining_years


def test_cashflow_quality_discloses_non_preceding_bullet_value_dates():
    service_mod = load_module('backend.app.services.cashflow_projection_service', 'backend/app/services/cashflow_projection_service.py')
    maturity = date(2027, 1, 1)
    rows = [
        {'interest_mode': 'bullet', 'market_value': Decimal('50'), 'value_date': maturity, 'maturity_date': maturity},
        {'interest_mode': 'bullet', 'market_value': Decimal('70'), 'value_date': date(2027, 1, 2), 'maturity_date': maturity},
    ]
    disclosures = service_mod._cashflow_projection_quality_disclosures(rows)
    assert disclosures['bullet_value_date_fallback_count'] == 2
    assert disclosures['bullet_value_date_fallback_market_value'] == Decimal('120')
    assert any('one-year interest proxy' in warning for warning in disclosures['warnings'])


def test_cashflow_quality_disclosures_cover_frequency_floating_and_bullet_proxies():
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )
    rows = [
        {"interest_mode": "fixed", "market_value": Decimal("90"), "maturity_date": date(2027, 1, 1)},
        {"interest_mode": "floating", "market_value": Decimal("180"), "maturity_date": date(2027, 1, 1)},
        {"interest_mode": "fixed", "interest_payment_frequency": "semi-annual", "market_value": Decimal("70"), "maturity_date": date(2027, 1, 1)},
        {"interest_mode": "bullet", "market_value": Decimal("50"), "value_date": None, "maturity_date": date(2027, 1, 1)},
    ]

    disclosures = service_mod._cashflow_projection_quality_disclosures(rows)

    assert disclosures["payment_frequency_fallback_count"] == 2
    assert disclosures["payment_frequency_fallback_market_value"] == Decimal("270")
    assert disclosures["floating_rate_proxy_count"] == 1
    assert disclosures["floating_rate_proxy_market_value"] == Decimal("180")
    assert disclosures["bullet_value_date_fallback_count"] == 1
    assert disclosures["bullet_value_date_fallback_market_value"] == Decimal("50")


def test_attach_duration_treats_materialized_zero_as_valid():
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )
    key_fields = {
        "instrument_code": "MATURED-BOND",
        "portfolio_name": "P1",
        "cost_center": "C1",
        "currency_code": "CNY",
    }
    zqtz_row = {**key_fields, "position_scope": "asset"}
    analytics_row = {
        **key_fields,
        "macaulay_duration": Decimal("0"),
        "report_date": date(2026, 1, 1),
        "maturity_date": date(2031, 1, 1),
        "coupon_rate": Decimal("0.03"),
        "ytm": Decimal("0.035"),
        "interest_mode": "annual",
    }

    assert service_mod._attach_macaulay_duration([zqtz_row], [analytics_row])[0][
        "macaulay_duration"
    ] == Decimal("0")


def test_attach_duration_preserves_maturity_unavailable_quality_flag():
    service_mod = load_module(
        "backend.app.services.cashflow_projection_service",
        "backend/app/services/cashflow_projection_service.py",
    )
    key_fields = {
        "instrument_code": "FUND-NO-MATURITY",
        "portfolio_name": "P1",
        "cost_center": "C1",
        "currency_code": "CNY",
    }

    enriched = service_mod._attach_macaulay_duration(
        [{**key_fields, "position_scope": "asset", "maturity_date": date(2031, 1, 1)}],
        [
            {
                **key_fields,
                "macaulay_duration": Decimal("0"),
                "duration_quality_flag": "maturity_unavailable",
            }
        ],
    )

    assert enriched[0]["macaulay_duration"] == Decimal("0")
    assert enriched[0]["duration_quality_flag"] == "maturity_unavailable"


def test_coerce_decimal_non_finite_inputs_fall_back_to_zero():
    """审计发现（Medium）：_coerce_decimal 对金额转换未做 NaN/Inf 防护。

    修复后须与既有 None/"" 失败语义一致（归 0），覆盖 float NaN/Inf 与
    字符串 "nan"/"inf" 经 Decimal(str(...)) 解析后仍非有限的情形。
    """
    module = _core_module()

    assert module._coerce_decimal(float("nan")) == Decimal("0")
    assert module._coerce_decimal(float("inf")) == Decimal("0")
    assert module._coerce_decimal(float("-inf")) == Decimal("0")
    assert module._coerce_decimal("nan") == Decimal("0")
    assert module._coerce_decimal("inf") == Decimal("0")
    assert module._coerce_decimal(Decimal("NaN")) == Decimal("0")
    assert module._coerce_decimal(Decimal("Infinity")) == Decimal("0")


def test_coerce_decimal_finite_and_missing_inputs_unaffected():
    module = _core_module()

    assert module._coerce_decimal(None) == Decimal("0")
    assert module._coerce_decimal("") == Decimal("0")
    assert module._coerce_decimal("100.5") == Decimal("100.5")
    assert module._coerce_decimal(Decimal("42")) == Decimal("42")
