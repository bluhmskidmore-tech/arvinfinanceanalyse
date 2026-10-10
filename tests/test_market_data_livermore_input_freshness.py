from __future__ import annotations

from datetime import date, timedelta

import duckdb

from backend.app.repositories.choice_stock_adapter import ChoiceStockReadiness
from backend.app.services.market_data_livermore_service import (
    INPUT_FRESHNESS_DEGRADED_DIAGNOSTIC_CODE,
    INPUT_FRESHNESS_LOOK_AHEAD_STATUS,
    _cycle_input_row_issue,
    _assess_input_freshness,
    _CycleInputEvidence,
    _load_cycle_input_evidence,
    _merge_input_freshness_into_data_gaps,
    livermore_strategy_envelope,
)

import pytest

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]



def _seed_broad_index_history(conn: duckdb.DuckDBPyConnection, *, start: date, days: int) -> None:
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
    rows = []
    for offset in range(days):
        trade_date = (start + timedelta(days=offset)).isoformat()
        rows.append(
            (
                "CA.CSI300",
                "沪深300指数收盘价",
                trade_date,
                3200.0 + offset * 8,
                "daily",
                "index",
                "sv_choice_macro_csi300",
                "vv_tushare_csi300",
                "rv_choice_macro_public_history_v1",
                "ok",
                f"choice_macro_refresh:{trade_date}",
            )
        )
    conn.executemany(
        "insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def _seed_macro_cycle_series(
    conn: duckdb.DuckDBPyConnection,
    *,
    pe_date: str,
    cn10y_date: str,
    pmi_date: str,
    sf_dates: tuple[str, str],
) -> None:
    conn.executemany(
        "insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("CA.CSI300_PE", "CSI300 PE", pe_date, 14.5, "daily", "x", "sv_pe", "vv_pe", "rv", "ok", "run-pe"),
            ("EMM00166466", "China 10Y yield", cn10y_date, 2.1, "daily", "%", "sv_y", "vv_y", "rv", "ok", "run-y"),
            (
                "M0017126",
                "Manufacturing PMI",
                pmi_date,
                51.2,
                "monthly",
                "index",
                "backfill_macro_v1",
                "vv_backfill_macro_nbs_pmi_release_20260710_204801316c86ecf8_e6c278bdb0d88252",
                "rv",
                "ok",
                "backfill_macro_v1:20260401T120000Z",
            ),
            (
                "M5525763",
                "Social financing YoY",
                sf_dates[0],
                8.4,
                "monthly",
                "%",
                "backfill_macro_v1",
                "vv_sf",
                "rv",
                "ok",
                "backfill_macro_v1:20260401T120000Z",
            ),
            (
                "M5525763",
                "Social financing YoY",
                sf_dates[1],
                9.1,
                "monthly",
                "%",
                "backfill_macro_v1",
                "vv_sf",
                "rv",
                "ok",
                "backfill_macro_v1:20260401T120000Z",
            ),
        ],
    )


def _seed_stock_daily_observation(conn: duckdb.DuckDBPyConnection, *, trade_dates: list[str]) -> None:
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar,
          stock_code varchar,
          close_value double,
          turn double,
          source_version varchar,
          vendor_version varchar,
          rule_version varchar,
          run_id varchar
        )
        """
    )
    conn.executemany(
        "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (trade_date, "000001.SZ", 10.0 + offset, 1.1, "sv_obs", "vv_obs", "rv_obs", "run-obs")
            for offset, trade_date in enumerate(trade_dates)
        ],
    )


def _seed_factor_snapshot(conn: duckdb.DuckDBPyConnection, *, as_of_dates: list[str]) -> None:
    conn.execute(
        """
        create table if not exists choice_stock_factor_snapshot (
          as_of_date varchar,
          stock_code varchar,
          pe double,
          pb double,
          ps double,
          roe double,
          gross_margin double,
          three_month_return double,
          twelve_month_return double,
          volatility double,
          dividend_yield double,
          industry varchar
        )
        """
    )
    conn.executemany(
        "insert into choice_stock_factor_snapshot values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (as_of_date, f"60000{i}.SH", 10.0 + i, 1.1, 0.8, 0.08, 0.25, 0.01, 0.05, 0.18, 0.01, "电子")
            for as_of_date in as_of_dates
            for i in range(1, 4)
        ],
    )


def _ready_choice_stock_readiness() -> ChoiceStockReadiness:
    return ChoiceStockReadiness(
        ready=True,
        status="ready",
        catalog_path="unit-test-choice-stock-catalog.json",
        missing_input_families=[],
        unconfirmed_fields=[],
        optional_input_status={},
        message="Choice stock catalog is confirmed for unit tests.",
    )


def _load_production_shaped_monthly_freshness_case(
    tmp_path,
    *,
    pmi_trade_date: str,
) -> tuple[dict[str, object], _CycleInputEvidence]:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        # 65 daily closes ending 2026-07-13 establish the strategy evaluation date.
        _seed_broad_index_history(conn, start=date(2026, 5, 10), days=65)
        _seed_macro_cycle_series(
            conn,
            pe_date="2026-07-13",
            cn10y_date="2026-07-13",
            pmi_date=pmi_trade_date,
            sf_dates=("2026-04-01", "2026-05-01"),
        )
        # Production backfill records one conservative materialization date for the batch.
        conn.execute(
            """
            update fact_choice_macro_daily
            set run_id = 'backfill_macro_v1:20260713T120000Z'
            where series_id in ('M0017126', 'M5525763')
            """
        )
        _seed_stock_daily_observation(conn, trade_dates=["2026-07-12", "2026-07-13"])
        _seed_factor_snapshot(conn, as_of_dates=["2026-07-13"])
    finally:
        conn.close()

    evidence = _load_cycle_input_evidence(
        duckdb_path=str(duckdb_path),
        as_of_date=date(2026, 7, 13),
    )
    envelope = livermore_strategy_envelope(duckdb_path=str(duckdb_path))
    return envelope, evidence


def test_fresh_inputs_keep_quality_flag_and_attach_freshness_fields(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        # 65 daily closes ending 2026-04-06 -> WARM gate, quality_flag ok baseline.
        _seed_broad_index_history(conn, start=date(2026, 2, 1), days=65)
        _seed_macro_cycle_series(
            conn,
            pe_date="2026-04-06",
            cn10y_date="2026-04-06",
            pmi_date="2026-03-31",
            sf_dates=("2026-02-28", "2026-03-31"),
        )
        _seed_stock_daily_observation(conn, trade_dates=["2026-04-05", "2026-04-06"])
        _seed_factor_snapshot(conn, as_of_dates=["2026-04-06"])
    finally:
        conn.close()

    envelope = livermore_strategy_envelope(duckdb_path=str(duckdb_path))

    assert envelope["result_meta"]["quality_flag"] == "ok"
    result = envelope["result"]
    assert result["market_gate"]["state"] == "WARM"
    gap_by_family = {row["input_family"]: row for row in result["data_gaps"]}
    assert gap_by_family["PMI"]["tier"] == "fresh"
    assert gap_by_family["PMI"]["business_date"] == "2026-03-31"
    assert gap_by_family["PMI"]["age_days"] == 6
    assert gap_by_family["credit_impulse"]["tier"] == "fresh"
    assert gap_by_family["price_spread"]["tier"] == "fresh"
    assert gap_by_family["turnover_persistence"]["tier"] == "fresh"
    assert gap_by_family["turnover_persistence"]["input"] == "choice_stock_daily_observation"
    assert gap_by_family["valuation_percentile_history"]["tier"] == "fresh"
    assert gap_by_family["valuation_percentile_history"]["input"] == "choice_stock_factor_snapshot"
    assert not [row for row in result["data_gaps"] if row["status"] == INPUT_FRESHNESS_LOOK_AHEAD_STATUS]
    assert not [
        row for row in result["diagnostics"] if row["code"] == INPUT_FRESHNESS_DEGRADED_DIAGNOSTIC_CODE
    ]


def test_monthly_macro_freshness_uses_statistical_period_end_and_preserves_raw_lineage(tmp_path) -> None:
    envelope, evidence = _load_production_shaped_monthly_freshness_case(
        tmp_path,
        pmi_trade_date="2026-05-01",
    )

    assert evidence.macro_snapshot is not None
    assert evidence.macro_snapshot.lineage["pmi"]["trade_date"] == "2026-05-01"
    assert evidence.macro_snapshot.lineage["credit_impulse"]["current_reference_date"] == "2026-05-01"
    assert evidence.vendor_versions == (
        "vv_pe",
        "vv_y",
        "vv_backfill_macro_nbs_pmi_release_20260710_204801316c86ecf8_e6c278bdb0d88252",
        "vv_sf",
    )

    result = envelope["result"]
    gap_by_family = {row["input_family"]: row for row in result["data_gaps"]}
    assert gap_by_family["PMI"]["business_date"] == "2026-05-31"
    assert gap_by_family["PMI"]["age_days"] == 43
    assert gap_by_family["PMI"]["tier"] == "fresh"
    assert gap_by_family["credit_impulse"]["business_date"] == "2026-05-31"
    assert gap_by_family["credit_impulse"]["age_days"] == 43
    assert gap_by_family["credit_impulse"]["tier"] == "fresh"

    macro_components = {
        row["input_family"]: row for row in result["market_gate"]["macro_context"]["components"]
    }
    assert macro_components["PMI"]["business_date"] == "2026-05-31"
    assert macro_components["PMI"]["age_days"] == 43
    assert macro_components["PMI"]["tier"] == "fresh"
    assert result["cycle_rotation_framework"]["macro_layer"]["vendor_versions"] == list(
        evidence.vendor_versions
    )
    assert envelope["result_meta"]["quality_flag"] == "ok"
    assert "vv_backfill_macro_nbs_pmi_release" in envelope["result_meta"]["vendor_version"]


def test_old_monthly_macro_period_remains_expired_after_period_end_normalization(tmp_path) -> None:
    envelope, evidence = _load_production_shaped_monthly_freshness_case(
        tmp_path,
        pmi_trade_date="2026-01-01",
    )

    assert evidence.macro_snapshot is not None
    assert evidence.macro_snapshot.lineage["pmi"]["trade_date"] == "2026-01-01"

    result = envelope["result"]
    gap_by_family = {row["input_family"]: row for row in result["data_gaps"]}
    assert gap_by_family["PMI"]["business_date"] == "2026-01-31"
    assert gap_by_family["PMI"]["age_days"] == 163
    assert gap_by_family["PMI"]["tier"] == "expired"
    assert envelope["result_meta"]["quality_flag"] == "warning"


def test_lagging_macro_series_degrades_quality_flag_with_note_and_gap(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        _seed_broad_index_history(conn, start=date(2026, 2, 1), days=65)
        # PMI lands 60 calendar days before the resolved trade_date 2026-04-06 -> monthly stale.
        _seed_macro_cycle_series(
            conn,
            pe_date="2026-04-06",
            cn10y_date="2026-04-06",
            pmi_date="2026-02-05",
            sf_dates=("2026-02-28", "2026-03-31"),
        )
        _seed_stock_daily_observation(conn, trade_dates=["2026-04-05", "2026-04-06"])
        _seed_factor_snapshot(conn, as_of_dates=["2026-04-06"])
    finally:
        conn.close()

    envelope = livermore_strategy_envelope(duckdb_path=str(duckdb_path))

    assert envelope["result_meta"]["quality_flag"] == "warning"
    result = envelope["result"]
    assert result["market_gate"]["state"] == "WARM"
    gap_by_family = {row["input_family"]: row for row in result["data_gaps"]}
    assert gap_by_family["PMI"]["tier"] == "stale"
    assert gap_by_family["PMI"]["business_date"] == "2026-02-05"
    assert gap_by_family["PMI"]["age_days"] == 60
    freshness_notes = [
        row for row in result["diagnostics"] if row["code"] == INPUT_FRESHNESS_DEGRADED_DIAGNOSTIC_CODE
    ]
    assert len(freshness_notes) == 1
    assert freshness_notes[0]["severity"] == "warning"
    assert freshness_notes[0]["input_family"] == "PMI"
    assert freshness_notes[0]["message"] == "宏观输入 M0017126 数据滞后 60 天（stale），信号质量降级"
    # Other inputs stay fresh, so no additional degradation entries appear.
    assert gap_by_family["credit_impulse"]["tier"] == "fresh"
    assert gap_by_family["turnover_persistence"]["tier"] == "fresh"
    assert gap_by_family["valuation_percentile_history"]["tier"] == "fresh"


def test_negative_age_days_marks_look_ahead_in_data_gaps() -> None:
    evidence = _CycleInputEvidence(
        input_business_dates=(("PMI", "M0017126", "monthly", "2026-04-10"),),
    )
    input_freshness = _assess_input_freshness(
        cycle_input_evidence=evidence,
        as_of_date=date(2026, 4, 6),
    )
    assert input_freshness[0]["age_days"] == -4

    data_gaps: list[dict[str, object]] = [
        {"input_family": "PMI", "status": "ready", "evidence": "PMI ready"}
    ]
    _merge_input_freshness_into_data_gaps(data_gaps=data_gaps, input_freshness=input_freshness)

    look_ahead = [row for row in data_gaps if row["status"] == INPUT_FRESHNESS_LOOK_AHEAD_STATUS]
    assert len(look_ahead) == 1
    assert look_ahead[0]["input_family"] == "PMI"
    assert look_ahead[0]["input"] == "M0017126"
    assert look_ahead[0]["business_date"] == "2026-04-10"
    assert look_ahead[0]["age_days"] == -4
    assert "look-ahead" in str(look_ahead[0]["evidence"])


def test_monthly_materialization_run_after_evaluation_date_is_rejected() -> None:
    issue = _cycle_input_row_issue(
        series_id="M0017126",
        trade_date="2026-05-01",
        frequency="monthly",
        unit="index",
        quality_flag="ok",
        source_version="backfill_macro_v1",
        run_id="backfill_macro_v1:20260713T120000Z",
        as_of_date=date(2026, 7, 10),
    )

    assert issue == "M0017126 availability date 2026-07-13 is after evaluation date 2026-07-10."


def test_historical_as_of_does_not_use_future_factor_snapshot(tmp_path) -> None:
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        # Broad index runs past the requested date so the replay is genuinely historical.
        _seed_broad_index_history(conn, start=date(2026, 2, 1), days=79)
        # Factor snapshots exist both before (2026-04-03) and after (2026-04-20) the request.
        _seed_factor_snapshot(conn, as_of_dates=["2026-04-03", "2026-04-20"])
    finally:
        conn.close()

    envelope = livermore_strategy_envelope(
        duckdb_path=str(duckdb_path),
        as_of_date="2026-04-06",
        stock_readiness=_ready_choice_stock_readiness(),
    )

    result = envelope["result"]
    assert result["as_of_date"] == "2026-04-06"
    # The factor screen must bind to the latest snapshot on or before the trade_date.
    assert result["factor_screen_candidates"]["factor_snapshot_as_of_date"] == "2026-04-03"
    gap_by_family = {row["input_family"]: row for row in result["data_gaps"]}
    assert gap_by_family["valuation_percentile_history"]["business_date"] == "2026-04-03"
    assert gap_by_family["valuation_percentile_history"]["age_days"] == 3
    assert not [row for row in result["data_gaps"] if row["status"] == INPUT_FRESHNESS_LOOK_AHEAD_STATUS]
