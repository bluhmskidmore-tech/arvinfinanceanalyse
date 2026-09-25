import logging
from datetime import date, timedelta
from decimal import ROUND_CEILING, Decimal, localcontext

import duckdb
import pytest

from backend.app.core_finance.bond_analytics.engine import compute_bond_analytics_rows
from backend.app.core_finance.bond_duration import compute_macaulay_duration
from backend.app.core_finance.cashflow_projection import compute_duration_gap
from backend.app.repositories.bond_analytics_repo import (
    _ANALYTICS_COLUMNS,
    FACT_TABLE,
    BondAnalyticsRepository,
)

_STATUS_COLUMNS = (
    "coupon_rate_input_status",
    "ytm_input_status",
    "duration_quality_flag",
)

_COLUMN_TYPES = {
    "report_date": "DATE",
    "instrument_code": "VARCHAR",
    "instrument_name": "VARCHAR",
    "portfolio_name": "VARCHAR",
    "cost_center": "VARCHAR",
    "asset_class_raw": "VARCHAR",
    "asset_class_std": "VARCHAR",
    "bond_type": "VARCHAR",
    "issuer_name": "VARCHAR",
    "industry_name": "VARCHAR",
    "rating": "VARCHAR",
    "accounting_class": "VARCHAR",
    "accounting_rule_id": "VARCHAR",
    "currency_code": "VARCHAR",
    "face_value": "DECIMAL(18, 6)",
    "market_value_native": "DECIMAL(18, 6)",
    "market_value": "DECIMAL(18, 6)",
    "amortized_cost": "DECIMAL(18, 6)",
    "accrued_interest": "DECIMAL(18, 6)",
    "coupon_rate": "DECIMAL(18, 8)",
    "interest_mode": "VARCHAR",
    "interest_payment_frequency": "VARCHAR",
    "interest_payment_frequency_fallback_used": "BOOLEAN",
    "interest_rate_style": "VARCHAR",
    "ytm": "DECIMAL(18, 8)",
    "value_date": "DATE",
    "maturity_date": "DATE",
    "next_call_date": "DATE",
    "years_to_maturity": "DECIMAL(18, 8)",
    "tenor_bucket": "VARCHAR",
    "macaulay_duration": "DECIMAL(18, 8)",
    "modified_duration": "DECIMAL(18, 8)",
    "convexity": "DECIMAL(18, 8)",
    "dv01": "DECIMAL(18, 8)",
    "is_credit": "BOOLEAN",
    "spread_dv01": "DECIMAL(18, 8)",
    "source_version": "VARCHAR",
    "rule_version": "VARCHAR",
    "ingest_batch_id": "VARCHAR",
    "trace_id": "VARCHAR",
}


def _record(report_date: date, instrument_code: str, market_value: str) -> dict[str, object]:
    return {
        "report_date": report_date,
        "instrument_code": instrument_code,
        "instrument_name": f"Synthetic {instrument_code}",
        "portfolio_name": "Synthetic Portfolio",
        "cost_center": "Synthetic Cost Center",
        "asset_class_raw": "国债",
        "asset_class_std": "rate",
        "bond_type": "government bond",
        "issuer_name": "Synthetic Issuer",
        "industry_name": "Synthetic Industry",
        "rating": "AAA",
        "accounting_class": "AC",
        "accounting_rule_id": "R001",
        "currency_code": "CNY",
        "face_value": Decimal("100"),
        "market_value_native": Decimal(market_value),
        "market_value": Decimal(market_value),
        "amortized_cost": Decimal("100"),
        "accrued_interest": Decimal("0.25"),
        "coupon_rate": Decimal("0.03"),
        "interest_mode": "annual",
        "interest_payment_frequency": "annual",
        "interest_payment_frequency_fallback_used": False,
        "interest_rate_style": "fixed",
        "ytm": Decimal("0.025"),
        "value_date": report_date,
        "maturity_date": None,
        "next_call_date": None,
        "years_to_maturity": Decimal("10"),
        "tenor_bucket": "10Y",
        "macaulay_duration": Decimal("0"),
        "modified_duration": Decimal("0"),
        "convexity": Decimal("0"),
        "dv01": Decimal("0"),
        "is_credit": False,
        "spread_dv01": Decimal("0"),
        "source_version": "synthetic-source-v1",
        "rule_version": "synthetic-rule-v1",
        "ingest_batch_id": "synthetic-batch-v1",
        "trace_id": f"synthetic-trace-{instrument_code}",
    }


def _create_analytics_db(path, *, with_status_columns: bool) -> None:
    assert set(_ANALYTICS_COLUMNS) == set(_COLUMN_TYPES)
    physical_columns: list[str] = []
    for column in _ANALYTICS_COLUMNS:
        physical_columns.append(column)
        if column == "ytm" and with_status_columns:
            physical_columns.extend(_STATUS_COLUMNS)

    status_types = {column: "VARCHAR" for column in _STATUS_COLUMNS}
    column_ddl = ", ".join(
        f'"{column}" {(_COLUMN_TYPES | status_types)[column]}'
        for column in physical_columns
    )
    conn = duckdb.connect(str(path))
    try:
        conn.execute(f'CREATE TABLE {FACT_TABLE} ({column_ddl})')
        records = (
            _record(date(2026, 6, 30), "SYNTH-A", "101.25"),
            _record(date(2026, 9, 30), "SYNTH-B", "202.50"),
        )
        records[1]["maturity_date"] = date(2026, 9, 30)
        placeholders = ", ".join("?" for _ in physical_columns)
        column_names = ", ".join(f'"{column}"' for column in physical_columns)
        insert_sql = f"INSERT INTO {FACT_TABLE} ({column_names}) VALUES ({placeholders})"
        for index, record in enumerate(records):
            if with_status_columns:
                record.update(
                    coupon_rate_input_status="observed",
                    ytm_input_status="missing" if index == 0 else "observed",
                    duration_quality_flag=(
                        "maturity_unavailable" if index == 0 else "no_remaining_term"
                    ),
                )
            conn.execute(insert_sql, [record[column] for column in physical_columns])
    finally:
        conn.close()


@pytest.mark.parametrize(
    "with_status_columns",
    [False, True],
    ids=["legacy-schema", "status-schema"],
)
def test_repository_maps_single_and_batch_rows_for_legacy_and_status_schemas(
    tmp_path, with_status_columns: bool
) -> None:
    database_name = "status-schema.duckdb" if with_status_columns else "legacy-schema.duckdb"
    database = tmp_path / database_name
    _create_analytics_db(database, with_status_columns=with_status_columns)
    repository = BondAnalyticsRepository(path=str(database))

    single = repository.fetch_bond_analytics_rows(report_date="2026-06-30")
    assert len(single) == 1
    row = single[0]
    ytm_index = _ANALYTICS_COLUMNS.index("ytm") + 1
    expected_single_columns = (
        _ANALYTICS_COLUMNS[:ytm_index]
        + _STATUS_COLUMNS
        + _ANALYTICS_COLUMNS[ytm_index:]
    )
    assert tuple(row) == expected_single_columns
    assert row["instrument_code"] == "SYNTH-A"
    assert row["market_value"] == Decimal("101.250000")
    assert row["ytm"] == Decimal("0.02500000")
    assert row["value_date"] == date(2026, 6, 30)
    assert row["maturity_date"] is None
    assert row["macaulay_duration"] == Decimal("0.00000000")
    if with_status_columns:
        assert row["coupon_rate_input_status"] == "observed"
        assert row["ytm_input_status"] == "missing"
        assert row["duration_quality_flag"] == "maturity_unavailable"
    else:
        assert all(row[column] is None for column in _STATUS_COLUMNS)

    batch = repository.fetch_bond_analytics_rows_for_dates(
        report_dates=["2026-09-30", "2026-06-30", "2026-09-30"]
    )
    assert list(batch) == ["2026-09-30", "2026-06-30"]
    assert tuple(batch["2026-06-30"][0]) == _ANALYTICS_COLUMNS
    assert tuple(batch["2026-09-30"][0]) == _ANALYTICS_COLUMNS
    assert batch["2026-06-30"][0]["instrument_code"] == "SYNTH-A"
    assert batch["2026-06-30"][0]["ytm"] == Decimal("0.02500000")
    assert batch["2026-06-30"][0]["maturity_date"] is None
    assert batch["2026-06-30"][0]["macaulay_duration"] == Decimal("0.00000000")
    assert batch["2026-09-30"][0]["instrument_code"] == "SYNTH-B"
    assert batch["2026-09-30"][0]["market_value"] == Decimal("202.500000")
    assert batch["2026-09-30"][0]["maturity_date"] == date(2026, 9, 30)
    assert batch["2026-09-30"][0]["macaulay_duration"] == Decimal("0.00000000")


def _manual_annual_duration(
    years_to_maturity: Decimal,
    coupon_rate: Decimal,
    effective_ytm: Decimal,
    payment_times: tuple[Decimal, ...] | None = None,
) -> Decimal:
    if payment_times is None:
        periods = int(years_to_maturity.to_integral_value(rounding=ROUND_CEILING))
        first_payment_time = years_to_maturity - Decimal(periods - 1)
        payment_times = tuple(first_payment_time + Decimal(index) for index in range(periods))
    discount_base = Decimal("1") + effective_ytm
    price = Decimal("0")
    weighted_pv = Decimal("0")
    periods = len(payment_times)
    for index, payment_time in enumerate(payment_times):
        cashflow = coupon_rate if index < periods - 1 else coupon_rate + Decimal("1")
        present_value = cashflow / (discount_base**payment_time)
        price += present_value
        weighted_pv += payment_time * present_value
    return weighted_pv / price


@pytest.mark.parametrize(
    ("maturity_days", "ytm_value"),
    [
        (3650, None),
        (3650, Decimal("0")),
        (3650, Decimal("4")),
        (820, None),
        (820, Decimal("0")),
        (820, Decimal("4")),
        (731, None),
        (731, Decimal("0")),
        (731, Decimal("4")),
        (732, None),
        (732, Decimal("0")),
        (732, Decimal("4")),
    ],
    ids=[
        "ordinary-missing",
        "ordinary-zero",
        "ordinary-positive",
        "stub-missing",
        "stub-zero",
        "stub-positive",
        "near-grid-731-missing",
        "near-grid-731-zero",
        "near-grid-731-positive",
        "near-grid-732-missing",
        "near-grid-732-zero",
        "near-grid-732-positive",
    ],
)
def test_engine_missing_zero_and_positive_yields_preserve_base_duration_math(
    maturity_days: int,
    ytm_value: Decimal | None,
) -> None:
    report_date = date(2026, 1, 1)
    maturity_date = report_date + timedelta(days=maturity_days)
    snapshot = {
        "report_date": report_date,
        "instrument_code": "SYNTH-ENGINE",
        "instrument_name": "Synthetic annual coupon bond",
        "asset_class": "国债",
        "bond_type": "government bond",
        "account_category": "AC",
        "accounting_basis": "AC",
        "currency_code": "CNY",
        "face_value_native": Decimal("100"),
        "market_value_native": Decimal("100"),
        "amortized_cost_native": Decimal("100"),
        "accrued_interest_native": Decimal("0"),
        # Snapshot rates use percentage units; engine output is normalized.
        "coupon_rate": Decimal("3"),
        "interest_mode": "annual",
        "ytm_value": ytm_value,
        "maturity_date": maturity_date,
    }

    # Compare to the fixed 89a baseline contract: the engine passes missing YTM
    # through its existing par fallback, and observed zero takes that same math.
    with localcontext() as context:
        context.prec = 40
        row = compute_bond_analytics_rows([snapshot], report_date)[0]
        years_to_maturity = Decimal(maturity_days) / Decimal("365")
        if ytm_value is None or ytm_value == Decimal("0"):
            effective_yield = Decimal("0.03")
        else:
            effective_yield = ytm_value / Decimal("100")
        if maturity_days in (731, 732):
            payment_times = (Decimal("1"), Decimal("2"))
        else:
            payment_times = None
        expected_duration = _manual_annual_duration(
            years_to_maturity,
            Decimal("0.03"),
            effective_yield,
            payment_times,
        )

    assert row.years_to_maturity == years_to_maturity
    assert row.interest_payment_frequency == "annual"
    assert abs(row.macaulay_duration - expected_duration) < Decimal("1e-30")
    if ytm_value is None:
        assert row.ytm is None
        assert row.ytm_input_status == "missing"
        assert row.duration_quality_flag == "ytm_par_fallback"
    else:
        assert row.ytm == ytm_value / Decimal("100")
        assert row.ytm_input_status == "observed"
        assert row.duration_quality_flag == (
            "ytm_par_fallback" if ytm_value == Decimal("0") else "observed"
        )


@pytest.mark.parametrize(
    "ytm",
    [Decimal("-1"), Decimal("-2")],
    ids=["zero-base", "negative-base"],
)
def test_wrapper_fails_closed_when_annual_discount_base_is_nonpositive(ytm, caplog) -> None:
    caplog.set_level(logging.ERROR, logger="backend.app.core_finance.bond_duration")
    duration = compute_macaulay_duration(
        Decimal("10"),
        Decimal("0.03"),
        ytm,
        frequency=1,
        preserve_observed_ytm=True,
    )
    default_duration = compute_macaulay_duration(
        Decimal("10"), Decimal("0.03"), ytm, frequency=1
    )
    # A nonpositive discount base is an explicit guard, not a caught exception.
    # Keep both paths numerically identical and verify no division error occurs.
    assert duration == default_duration == Decimal("10")
    assert not any(item.levelno >= logging.ERROR for item in caplog.records)


def test_wrapper_keeps_zero_yield_exception_logging_and_par_guards_for_infinite_coupon(
    caplog,
) -> None:
    caplog.set_level(logging.ERROR, logger="backend.app.core_finance.bond_duration")
    duration = compute_macaulay_duration(
        Decimal("2"),
        Decimal("Infinity"),
        Decimal("0"),
        frequency=1,
        preserve_observed_ytm=True,
    )
    assert duration == Decimal("2")
    assert any(
        "falling back to remaining years" in item.message
        for item in caplog.records
    )


def test_wrapper_distinguishes_legal_negative_yield_from_missing_yield() -> None:
    report_date = date(2026, 1, 1)
    maturity_date = report_date + timedelta(days=3650)
    years = Decimal("10")
    with localcontext() as context:
        context.prec = 40
        negative_duration = compute_macaulay_duration(
            years,
            Decimal("0.03"),
            Decimal("-0.01"),
            frequency=1,
            preserve_observed_ytm=True,
        )
        expected_negative = _manual_annual_duration(
            years,
            Decimal("0.03"),
            Decimal("-0.01"),
        )
        missing = compute_bond_analytics_rows(
            [
                {
                    "report_date": report_date,
                    "instrument_code": "SYNTH-MISSING-YTM",
                    "asset_class": "国债",
                    "account_category": "AC",
                    "accounting_basis": "AC",
                    "currency_code": "CNY",
                    "coupon_rate": Decimal("3"),
                    "interest_mode": "annual",
                    "ytm_value": None,
                    "maturity_date": maturity_date,
                }
            ],
            report_date,
        )[0]
        expected_missing = _manual_annual_duration(
            years,
            Decimal("0.03"),
            Decimal("0.03"),
        )
    assert abs(negative_duration - expected_negative) < Decimal("1e-30")
    assert abs(missing.macaulay_duration - expected_missing) < Decimal("1e-30")
    assert negative_duration > missing.macaulay_duration
    assert missing.ytm is None
    assert missing.ytm_input_status == "missing"
    assert missing.duration_quality_flag == "ytm_par_fallback"


@pytest.mark.parametrize(
    ("quality_flag", "expected_covered", "expected_duration"),
    [
        ("maturity_unavailable", Decimal("0"), None),
        ("no_remaining_term", Decimal("100"), Decimal("0")),
        ("observed", Decimal("100"), Decimal("0")),
    ],
)
def test_duration_coverage_distinguishes_unavailable_from_genuine_zero(
    quality_flag, expected_covered, expected_duration
) -> None:
    report_date = date(2026, 1, 1)
    result = compute_duration_gap(
        [
            {
                "instrument_code": "SYNTH-DURATION-STATE",
                "position_scope": "asset",
                "market_value_amount": Decimal("100"),
                "face_value_amount": Decimal("100"),
                "coupon_rate": Decimal("0"),
                "interest_mode": "annual",
                "maturity_date": (
                    report_date if quality_flag == "no_remaining_term" else date(2028, 1, 1)
                ),
                "macaulay_duration": Decimal("0"),
                "duration_quality_flag": quality_flag,
            }
        ],
        [],
        report_date,
    )
    assert result.total_asset_market_value == Decimal("100")
    assert result.asset_duration_covered_balance == expected_covered
    assert result.asset_excluded_balance == Decimal("100") - expected_covered
    assert result.asset_weighted_duration == expected_duration
    assert result.duration_gap == expected_duration
    assert any("missing duration information" in warning for warning in result.warnings) == (
        quality_flag == "maturity_unavailable"
    )
