from pathlib import Path

import duckdb
import pytest

from backend.app.services.macro_vendor_service import (
    choice_macro_formal_envelope,
    choice_macro_latest_envelope,
    load_choice_macro_latest_payload,
)

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_market_data,
]


def _write_choice_term_spread_fixture(
    duckdb_path: Path,
    rows: list[tuple[str, str, str, float, str, str]],
) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.executemany(
            "insert into fact_choice_macro_daily values (?, ?, ?, ?, 'daily', ?, 'sv', 'vv', 'rv', ?, 'run')",
            rows,
        )
    finally:
        conn.close()


def _write_formal_treasury_curve_fixture(
    duckdb_path: Path,
    rows: list[tuple[str, str, float]],
) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_yield_curve_daily (
              trade_date varchar,
              curve_type varchar,
              tenor varchar,
              rate_pct decimal(18,8),
              vendor_name varchar,
              vendor_version varchar,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        conn.executemany(
            """
            insert into fact_formal_yield_curve_daily values
              (?, 'treasury', ?, ?, 'akshare', 'vv_formal', 'sv_formal', 'rv_formal')
            """,
            rows,
        )
    finally:
        conn.close()


def test_choice_macro_latest_derives_same_date_term_spreads_in_bp(tmp_path: Path):
    duckdb_path = tmp_path / "macro-derived-spreads.duckdb"
    _write_choice_term_spread_fixture(
        duckdb_path,
        [
            ("EMM00166458", "China treasury yield 1Y", "2026-04-10", 2.55, "%", "ok"),
            ("EMM00588704", "China treasury yield 2Y", "2026-04-10", 2.70, "%", "ok"),
            ("EMM00166462", "China treasury yield 5Y", "2026-04-10", 2.90, "%", "ok"),
            ("EMM00166466", "China treasury yield 10Y", "2026-04-10", 3.20, "%", "ok"),
        ],
    )

    payload = load_choice_macro_latest_payload(str(duckdb_path))

    assert payload.derived_spreads == pytest.approx(
        {
            "term_spread_10y_1y": 65.0,
            "term_spread_10y_2y": 50.0,
            "term_spread_10y_5y": 30.0,
        }
    )

    envelope = choice_macro_latest_envelope(str(duckdb_path))
    assert envelope["result_meta"]["basis"] == "analytical"
    assert envelope["result_meta"]["formal_use_allowed"] is False
    assert envelope["result_meta"]["rule_version"] == "rv_choice_macro_latest_derived_spreads_v1"


def test_choice_macro_latest_keeps_missing_term_spread_legs_null(tmp_path: Path):
    duckdb_path = tmp_path / "macro-derived-spreads-missing.duckdb"
    _write_choice_term_spread_fixture(
        duckdb_path,
        [
            ("EMM00166458", "China treasury yield 1Y", "2026-04-10", 2.55, "pct", "warning"),
            ("EMM00166466", "China treasury yield 10Y", "2026-04-10", 3.20, "pct", "warning"),
        ],
    )

    payload = load_choice_macro_latest_payload(str(duckdb_path))

    assert payload.derived_spreads["term_spread_10y_1y"] == pytest.approx(65.0)
    assert payload.derived_spreads["term_spread_10y_2y"] is None
    assert payload.derived_spreads["term_spread_10y_5y"] is None


def test_choice_macro_latest_does_not_mix_dates_or_stale_yield_legs(tmp_path: Path):
    duckdb_path = tmp_path / "macro-derived-spreads-unusable.duckdb"
    _write_choice_term_spread_fixture(
        duckdb_path,
        [
            ("EMM00166458", "China treasury yield 1Y", "2026-04-09", 2.55, "%", "ok"),
            ("EMM00588704", "China treasury yield 2Y", "2026-04-10", 2.70, "%", "stale"),
            ("EMM00166462", "China treasury yield 5Y", "2026-04-10", 2.90, "%", "error"),
            ("EMM00166466", "China treasury yield 10Y", "2026-04-10", 3.20, "%", "ok"),
        ],
    )

    payload = load_choice_macro_latest_payload(str(duckdb_path))

    assert payload.derived_spreads == {
        "term_spread_10y_1y": None,
        "term_spread_10y_2y": None,
        "term_spread_10y_5y": None,
    }


def test_market_data_rates_rederives_spreads_after_formal_curve_merge(tmp_path: Path):
    duckdb_path = tmp_path / "market-data-rates-derived-spreads.duckdb"
    _write_choice_term_spread_fixture(
        duckdb_path,
        [
            ("EMM00166458", "China treasury yield 1Y", "2026-04-10", 2.55, "%", "ok"),
            ("EMM00588704", "China treasury yield 2Y", "2026-04-10", 2.70, "%", "ok"),
            ("EMM00166462", "China treasury yield 5Y", "2026-04-10", 2.90, "%", "ok"),
            ("EMM00166466", "China treasury yield 10Y", "2026-04-10", 3.20, "%", "ok"),
        ],
    )
    _write_formal_treasury_curve_fixture(
        duckdb_path,
        [
            ("2026-04-11", "1Y", 2.50),
            ("2026-04-11", "2Y", 2.65),
            ("2026-04-11", "5Y", 2.85),
            ("2026-04-11", "10Y", 3.30),
        ],
    )

    envelope = choice_macro_formal_envelope(str(duckdb_path))

    assert envelope["result_meta"]["result_kind"] == "market_data.rates"
    assert envelope["result_meta"]["basis"] == "formal"
    assert envelope["result_meta"]["formal_use_allowed"] is True
    assert envelope["result"]["derived_spreads"] == pytest.approx(
        {
            "term_spread_10y_1y": 80.0,
            "term_spread_10y_2y": 65.0,
            "term_spread_10y_5y": 45.0,
        }
    )


def test_market_data_rates_does_not_preserve_spreads_after_partial_formal_update(
    tmp_path: Path,
):
    duckdb_path = tmp_path / "market-data-rates-partial-formal-curve.duckdb"
    _write_choice_term_spread_fixture(
        duckdb_path,
        [
            ("EMM00166458", "China treasury yield 1Y", "2026-04-10", 2.55, "%", "ok"),
            ("EMM00588704", "China treasury yield 2Y", "2026-04-10", 2.70, "%", "ok"),
            ("EMM00166462", "China treasury yield 5Y", "2026-04-10", 2.90, "%", "ok"),
            ("EMM00166466", "China treasury yield 10Y", "2026-04-10", 3.20, "%", "ok"),
        ],
    )
    _write_formal_treasury_curve_fixture(
        duckdb_path,
        [("2026-04-11", "10Y", 3.30)],
    )

    envelope = choice_macro_formal_envelope(str(duckdb_path))

    assert envelope["result"]["derived_spreads"] == {
        "term_spread_10y_1y": None,
        "term_spread_10y_2y": None,
        "term_spread_10y_5y": None,
    }
