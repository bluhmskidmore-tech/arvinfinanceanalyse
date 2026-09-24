# ARCHIVED 2026-08-12（C5 脚本盘点批次 1 归档）：随 ../run_batch3_stock_strategy_research.py 一并移出 tests/。
# pytest 不再收集（pytest.ini testpaths 仅 tests/、backend/tests/）；归档件冻结、不保证可运行，仅作追溯。
import duckdb
import pytest

import scripts.run_batch3_stock_strategy_research as batch3_research
from backend.app.core_finance.livermore_stock_candidates import FORMULA_VERSION
from backend.app.core_finance.portfolio_backtest import PortfolioBacktestResult, run_portfolio_backtest
from scripts.run_batch3_stock_strategy_research import (
    _adjustment_factor_table_diagnostics,
    _adjustment_factor_blockers,
    _adjustment_gap_sensitivity,
    _amount_like_source_columns,
    _a_share_constraint_diagnostics,
    _canonical_liquidity_status,
    _canonical_path_rows,
    _canonical_quality_summary_rows,
    _canonical_trade_rows,
    _classify_data_readiness,
    _cluster_bootstrap_by_period,
    _data_quality_go_blockers,
    _equity_exposure_coverage,
    _gate_fallback_split_decision,
    _gate_supplement_mapping_assessment,
    _gate_trading_calendar_validation,
    _hold_exit_recommendation,
    _liquidity_readiness,
    _liquidity_scaled_thresholds,
    _liquidity_source_lineage_diagnostics,
    _liquidity_unit_hypothesis,
    _macro_history_readiness,
    _next_tradable_open,
    _path_exit_candidate_rules,
    _path_engine_tieout_rows,
    _post_data_fix_blockers,
    _run_path_exit_portfolio_variant,
    _risk_budget_optimization_rows,
    _risk_budget_optimization_decision,
    _risk_budget_recommendation,
    _simulate_hold_exit_rule,
    _simulations_by_rule,
    _write_gate_repair_report,
    _write_gate_repair_v3_report,
    _write_csv,
    _write_exit_report,
    _write_liquidity_unit_report,
    _write_risk_budget_optimization_report,
    write_batch3_summary,
    simulate_hold_progress_exits,
)


def _path_row(
    trade_date: str,
    *,
    open_price: float | None,
    close_price: float,
    basis: str = "adjusted",
    halted: bool = False,
    limit_down: bool = False,
) -> dict[str, object]:
    if basis == "raw_fallback_missing_adj_factor":
        return {
            "trade_date": trade_date,
            "open": open_price,
            "close": close_price,
            "adj_open": 999.0 if open_price is not None else None,
            "adj_close": 999.0,
            "path_price_basis": basis,
            "halted": halted,
            "limit_down": limit_down,
        }
    return {
        "trade_date": trade_date,
        "open": open_price,
        "close": close_price,
        "adj_open": open_price,
        "adj_close": close_price,
        "path_price_basis": basis,
        "halted": halted,
        "limit_down": limit_down,
    }


def _source_row() -> dict[str, object]:
    return {
        "stock_code": "000001.SZ",
        "signal_date": "2026-06-01",
        "entry_date": "2026-06-02",
        "exit_date_20d": "2026-06-30",
        "signal_kind": "stock_candidate",
        "market_state": "HOT",
    }


def _execution_row(
    stock_code: str,
    *,
    ema10: float | None,
    market_state: str = "HOT",
    rank: int = 1,
) -> dict[str, object]:
    return {
        "signal_date": "2026-06-01",
        "stock_code": stock_code,
        "stock_name": stock_code,
        "signal_kind": "stock_candidate",
        "candidate_rank": rank,
        "market_state": market_state,
        "entry_date": "2026-06-02",
        "entry_price": 10.0,
        "entry_executable": True,
        "ema10": ema10,
        "exit_date_5d": "2026-06-03",
        "return_5d_net_adj": 0.0,
        "daily_amount": 300_000_000.0,
    }


def _twenty_day_path(
    *,
    trigger_exit_open: float = 9.0,
    later_close: float = 100.0,
) -> list[dict[str, object]]:
    rows = []
    for day in range(1, 21):
        date = f"2026-06-{day + 1:02d}"
        open_price = 10.0
        close_price = 10.0
        if day == 3:
            close_price = 9.5
        if day == 4:
            open_price = trigger_exit_open
            close_price = later_close
        rows.append(_path_row(date, open_price=open_price, close_price=close_price))
    return rows


def test_hold_exit_rule_uses_day_k_close_and_next_tradable_open() -> None:
    path = [
        _path_row("2026-06-02", open_price=10.0, close_price=10.0),
        _path_row("2026-06-03", open_price=10.0, close_price=10.0),
        _path_row("2026-06-04", open_price=10.0, close_price=9.5),
        _path_row("2026-06-05", open_price=9.0, close_price=100.0),
    ]

    row = _simulate_hold_exit_rule(
        _source_row(),
        path,
        10.0,
        scheduled_return=0.20,
        rule={"name": "day3_underwater_exit", "day": 3, "action": "exit", "predicate": lambda value: value < -0.03},
    )

    assert row["triggered"] is True
    assert row["overlay_applied"] is True
    assert row["exit_date"] == "2026-06-05"
    assert row["exit_price"] == pytest.approx(9.0)
    # gross -0.10 netted multiplicatively: (1 - 0.10) * (1 - 0.0041) - 1 = -0.10369
    assert row["rule_return_net"] == pytest.approx(-0.10369)


def test_hold_exit_rule_records_missing_next_open_without_skipping_forward() -> None:
    path = [
        _path_row("2026-06-02", open_price=10.0, close_price=10.0),
        _path_row("2026-06-03", open_price=10.0, close_price=10.0),
        _path_row("2026-06-04", open_price=10.0, close_price=9.5),
        _path_row("2026-06-05", open_price=None, close_price=80.0),
        _path_row("2026-06-08", open_price=9.0, close_price=9.0),
    ]

    row = _simulate_hold_exit_rule(
        _source_row(),
        path,
        10.0,
        scheduled_return=0.20,
        rule={"name": "day3_underwater_exit", "day": 3, "action": "exit", "predicate": lambda value: value < -0.03},
    )

    assert row["triggered"] is True
    assert row["missing_exit"] is True
    assert row["missing_reason"] == "missing_next_open_price"
    assert row["exit_date"] == "2026-06-30"


def test_next_tradable_open_skips_halts_and_limit_down_only() -> None:
    path = [
        _path_row("2026-06-02", open_price=10.0, close_price=10.0),
        _path_row("2026-06-03", open_price=10.0, close_price=10.0, halted=True),
        _path_row("2026-06-04", open_price=9.9, close_price=9.5, limit_down=True),
        _path_row("2026-06-05", open_price=None, close_price=8.0),
        _path_row("2026-06-08", open_price=9.0, close_price=9.0),
    ]

    row = _next_tradable_open(path, 1)

    assert row is not None
    assert row["trade_date"] == "2026-06-05"


def test_hold_exit_rule_keeps_raw_fallback_basis_consistent() -> None:
    path = [
        _path_row("2026-06-02", open_price=10.0, close_price=10.0, basis="raw_fallback_missing_adj_factor"),
        _path_row("2026-06-03", open_price=10.0, close_price=10.0, basis="raw_fallback_missing_adj_factor"),
        _path_row("2026-06-04", open_price=10.0, close_price=9.5, basis="raw_fallback_missing_adj_factor"),
        _path_row("2026-06-05", open_price=9.0, close_price=9.2, basis="raw_fallback_missing_adj_factor"),
    ]

    row = _simulate_hold_exit_rule(
        _source_row(),
        path,
        10.0,
        scheduled_return=0.20,
        rule={"name": "day3_underwater_exit", "day": 3, "action": "exit", "predicate": lambda value: value < -0.03},
    )

    assert row["triggered"] is True
    assert row["exit_price"] == pytest.approx(9.0)
    assert row["rule_return_net"] == pytest.approx(-0.10369)


def test_winner_diagnostic_does_not_require_open_or_enter_portfolio_comparison() -> None:
    path = [
        _path_row("2026-06-02", open_price=10.0, close_price=10.0),
        _path_row("2026-06-03", open_price=10.0, close_price=10.0),
        _path_row("2026-06-04", open_price=10.0, close_price=10.0),
        _path_row("2026-06-05", open_price=10.0, close_price=10.0),
        _path_row("2026-06-08", open_price=10.0, close_price=10.6),
        _path_row("2026-06-09", open_price=None, close_price=1.0),
    ]

    row = _simulate_hold_exit_rule(
        _source_row(),
        path,
        10.0,
        scheduled_return=0.20,
        rule={"name": "day5_winner_gt5_diagnostic", "day": 5, "action": "diagnostic", "predicate": lambda value: value > 0.05},
    )

    assert row["triggered"] is True
    assert row["portfolio_applicable"] is False
    assert row["rule_return_net"] == pytest.approx(0.20)
    assert row["missing_exit"] is False
    assert sorted({str(item.get("rule")) for item in [row] if item.get("portfolio_applicable")}) == []


def test_macro_history_blocks_without_composite_sources_and_liquidity_all_fail_not_ready() -> None:
    conn = duckdb.connect(":memory:")
    try:
        macro = _macro_history_readiness(conn, tables=set())
    finally:
        conn.close()
    liquidity = _liquidity_readiness(
        [
            {"daily_amount": 1_000_000.0},
            {"daily_amount": 5_000_000.0},
        ]
    )

    assert macro["status"] == "blocked"
    assert liquidity["status"] == "blocked"
    assert all(row["pass_count"] == 0 for row in liquidity["thresholds"])


def test_data_readiness_classification_blocks_macro_and_all_fail_liquidity() -> None:
    decision = _classify_data_readiness(
        exposure={"fallback_ratio": 0.25},
        macro={"status": "blocked"},
        positions={"sample_count": 6},
        price_path={"missing_adjustment_factor_ratio": 0.1},
        liquidity={
            "status": "blocked",
            "daily_amount_coverage_ratio": 1.0,
            "thresholds": [{"pass_count": 0, "missing_count": 0}],
        },
    )

    assert decision["status"] == "blocked"
    assert "gate exposure fallback ratio 25.00% is above 10%" in decision["blockers"]
    assert "macro composite history is missing or lacks required fields" in decision["blockers"]
    assert "liquidity thresholds have no passing known rows" in decision["blockers"]


def test_data_readiness_allows_zero_gate_fallback_but_blocks_zero_liquidity_coverage() -> None:
    decision = _classify_data_readiness(
        exposure={"fallback_ratio": 0.0},
        macro={"status": "ready"},
        positions={"sample_count": 30},
        price_path={"missing_adjustment_factor_ratio": 0.0},
        liquidity={
            "status": "ready",
            "daily_amount_coverage_ratio": 0.0,
            "thresholds": [{"pass_count": 1, "missing_count": 0}],
        },
    )

    assert decision["status"] == "blocked"
    assert "daily_amount is unavailable for all loaded execution rows" in decision["blockers"]
    assert not any("gate exposure fallback ratio" in blocker for blocker in decision["blockers"])


def test_gate_supplement_mapping_requires_explicit_exposure_field() -> None:
    assessment = _gate_supplement_mapping_assessment(
        {"trade_date", "breadth_5d", "limit_up_quality_ok", "source_version", "rule_version"}
    )

    assert assessment["usable_as_exposure_history"] is False
    assert assessment["exposure_fields"] == []
    assert assessment["supplement_only_fields"] == ["breadth_5d", "limit_up_quality_ok"]


def test_post_data_fix_blockers_do_not_treat_zero_gate_fallback_as_missing() -> None:
    blockers = _post_data_fix_blockers(
        gate_payload={
            "status": "ready",
            "calendar_day_exposure": {"fallback_ratio": 0.0},
            "trading_day_exposure": {"fallback_ratio": 0.0},
            "trading_calendar_validation": {"status": "ready", "true_trading_day_missing_count": 0},
            "blockers": [],
        },
        liquidity_payload={
            "status": "ready",
            "unit_status": "confirmed",
            "liquidity": {"thresholds": [{"pass_count": 1}]},
            "blockers": [],
        },
        adjustment_payload={
            "status": "ready",
            "price_path_adjustment": {"missing_adjustment_factor_rows": 0},
            "clean_subset_share": 0.80,
            "blockers": [],
        },
    )

    assert blockers == []


def test_post_data_fix_blockers_downgrade_calendar_gap_when_trading_days_validate() -> None:
    blockers = _post_data_fix_blockers(
        gate_payload={
            "status": "ready",
            "calendar_day_exposure": {"fallback_ratio": 0.34},
            "trading_day_exposure": {"fallback_ratio": 0.0},
            "trading_calendar_validation": {
                "status": "ready",
                "true_trading_day_missing_count": 0,
                "classification": "non_trading_dates_only",
            },
            "blockers": [],
        },
        liquidity_payload={
            "status": "ready",
            "unit_status": "confirmed",
            "liquidity": {"thresholds": [{"pass_count": 1}]},
            "blockers": [],
        },
        adjustment_payload={
            "status": "ready",
            "price_path_adjustment": {"missing_adjustment_factor_rows": 0},
            "clean_subset_share": 0.80,
            "blockers": [],
        },
    )

    assert blockers == []


def test_post_data_fix_blockers_keep_true_trading_day_gap_hard_blocker() -> None:
    blockers = _post_data_fix_blockers(
        gate_payload={
            "status": "blocked",
            "calendar_day_exposure": {"fallback_ratio": 0.34},
            "trading_day_exposure": {"fallback_ratio": 0.0},
            "trading_calendar_validation": {
                "status": "ready",
                "true_trading_day_missing_count": 1,
                "classification": "contains_true_trading_day_missing_dates",
            },
            "blockers": [],
        },
        liquidity_payload={
            "status": "ready",
            "unit_status": "confirmed",
            "liquidity": {"thresholds": [{"pass_count": 1}]},
            "blockers": [],
        },
        adjustment_payload={
            "status": "ready",
            "price_path_adjustment": {"missing_adjustment_factor_rows": 0},
            "clean_subset_share": 0.80,
            "blockers": [],
        },
    )

    assert "true trading-day gate exposure missing count must be zero" in blockers


def test_liquidity_scale_hypotheses_preserve_zero_pass_counts() -> None:
    rows = [{"daily_amount": 200_000.0}, {"daily_amount": None}]
    scaled = _liquidity_scaled_thresholds(rows)

    raw_20m = next(row for row in scaled if row["scale"] == "raw" and row["threshold"] == 20_000_000.0)
    x1000_200m = next(row for row in scaled if row["scale"] == "x1000" and row["threshold"] == 200_000_000.0)
    assert raw_20m["pass_count"] == 0
    assert raw_20m["fail_count"] == 1
    assert raw_20m["missing_count"] == 1
    assert x1000_200m["pass_count"] == 1
    assert _liquidity_unit_hypothesis(0.1) == "consistent_with_scaled_amount_and_lot_volume"


def test_liquidity_source_lineage_confirms_pass_through_not_rmb_unit() -> None:
    conn = duckdb.connect(":memory:")
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              amount double,
              volume double,
              close_value double,
              field_keys_json varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into choice_stock_daily_observation values
            ('2026-06-02', '000001.SZ', 1000.0, 100.0, 10.0, '["daily_ohlcv_amount"]', 'sv_choice', 'vv_choice', 'rv_choice')
            """
        )
        lineage = _liquidity_source_lineage_diagnostics(
            conn,
            [{"entry_date": "2026-06-02", "exit_date_20d": "2026-06-02"}],
            {
                "trade_date",
                "stock_code",
                "amount",
                "volume",
                "close_value",
                "field_keys_json",
                "source_version",
                "vendor_version",
                "rule_version",
            },
        )
    finally:
        conn.close()

    assert lineage["status"] == "ready"
    assert lineage["canonical_field_status"] == "daily_amount_rmb_unconfirmed"
    assert lineage["source_versions"] == [{"value": "sv_choice", "count": 1}]
    assert "pass-through" in lineage["local_evidence_conclusion"]


def test_adjustment_factor_table_diagnostics_identifies_absent_path_dates() -> None:
    conn = duckdb.connect(":memory:")
    try:
        conn.execute(
            """
            create table stock_adjustment_factor (
              stock_code varchar,
              trade_date varchar,
              adj_factor double,
              source_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into stock_adjustment_factor values
            ('000001.SZ', '2026-06-02', 1.0, 'sv', 'run')
            """
        )
        diagnostics = _adjustment_factor_table_diagnostics(
            conn,
            {
                "000001.SZ|2026-06-02": [
                    {"trade_date": "2026-06-02", "adj_factor_missing": False},
                    {"trade_date": "2026-06-03", "adj_factor_missing": True},
                ]
            },
        )
    finally:
        conn.close()

    assert diagnostics["status"] == "ready"
    assert diagnostics["date_count"] == 1
    assert diagnostics["missing_path_date_count"] == 1
    assert diagnostics["missing_path_dates_absent_from_adj_table"] == 1
    assert diagnostics["top_missing_path_dates"] == [{"trade_date": "2026-06-03", "missing_rows": 1}]


def test_equity_exposure_coverage_reports_trading_day_fallback_ratio() -> None:
    coverage = _equity_exposure_coverage(
        "fixed_20d_equal",
        [
            {"date": "2026-06-02", "exposure_basis": "per_date_actual"},
            {"date": "2026-06-03", "exposure_basis": "state_max_fallback"},
            {"date": "2026-06-04", "exposure_basis": "state_max_fallback"},
        ],
    )

    assert coverage["status"] == "blocked"
    assert coverage["per_date_actual_days"] == 1
    assert coverage["state_max_fallback_days"] == 2
    assert coverage["fallback_ratio"] == pytest.approx(2 / 3)
    assert coverage["fallback_date_ranges"] == [{"start": "2026-06-03", "end": "2026-06-04", "days": 2}]


def test_gate_trading_calendar_validation_classifies_non_trading_calendar_gaps() -> None:
    conn = duckdb.connect(":memory:")
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
        conn.execute(
            """
            insert into fact_choice_macro_daily values
            ('CA.CSI300', 'CSI300', '2026-06-02', 100.0, 'daily', 'index', 'sv', 'vv', 'rv_gate', 'ok', 'run'),
            ('CA.CSI300', 'CSI300', '2026-06-03', 101.0, 'daily', 'index', 'sv', 'vv', 'rv_gate', 'ok', 'run')
            """
        )
        validation = _gate_trading_calendar_validation(
            conn,
            {
                "missing_dates": ["2026-06-01", "2026-06-06", "2026-06-07"],
                "missing_date_ranges": [],
            },
            start_date="2026-06-01",
            end_date="2026-06-07",
        )
    finally:
        conn.close()

    assert validation["status"] == "ready"
    assert validation["classification"] == "non_trading_dates_only"
    assert validation["true_trading_day_missing_count"] == 0
    assert validation["calendar_missing_weekend_count"] == 2
    assert validation["calendar_missing_weekday_non_trading_count"] == 1
    assert validation["trading_day_sources"][0]["rule_versions"] == [{"value": "rv_gate", "count": 2}]


def test_gate_repair_v3_report_splits_calendar_and_trading_day_fallback(tmp_path) -> None:
    report = tmp_path / "gate-v3.md"
    _write_gate_repair_v3_report(
        report,
        {
            "status": "ready",
            "repair_result": "trading_day_repaired_calendar_pipeline_warning",
            "date_window": {"start": "2026-06-01", "end": "2026-06-07"},
            "calendar_day_exposure": {
                "date_count": 7,
                "persisted_rows": 0,
                "replayed_rows": 2,
                "fallback_rows": 5,
                "fallback_ratio": 5 / 7,
            },
            "trading_day_exposure": {
                "equity_curve_days": 2,
                "per_date_actual_days": 2,
                "state_max_fallback_days": 0,
                "fallback_ratio": 0.0,
            },
            "trading_calendar_validation": {
                "true_trading_day_total": 2,
                "true_trading_day_missing_count": 0,
                "true_trading_day_missing_ratio": 0.0,
                "classification": "non_trading_dates_only",
                "calendar_missing_total": 5,
                "calendar_missing_not_trading_day_count": 5,
                "calendar_missing_weekend_count": 2,
                "calendar_missing_weekday_non_trading_count": 3,
                "trading_day_sources": [],
                "replayed_exposure_lineage": {"benchmark_series_id": "CA.CSI300"},
            },
            "source_diagnostics": {"persisted_exposure_tables": []},
            "warnings": ["calendar-day fallback remains a pipeline coverage warning"],
            "blockers": [],
        },
    )

    content = report.read_text(encoding="utf-8")
    assert "calendar_gate_fallback_ratio" in content
    assert "trading_day_gate_fallback_ratio" in content
    assert "true_trading_day_missing_count: 0" in content
    assert "pipeline warnings" in content


def test_gate_repair_report_labels_synthetic_exposure_baseline_as_control(tmp_path) -> None:
    report = tmp_path / "gate.md"
    _write_gate_repair_report(
        report,
        {
            "status": "blocked",
            "target": "fallback ratio < 10%",
            "explanation": "calendar vs trading-day",
            "calendar_day_exposure": {
                "date_count": 2,
                "persisted_rows": 1,
                "replayed_rows": 0,
                "fallback_rows": 1,
                "fallback_ratio": 0.5,
                "missing_dates_total": 1,
                "source_counts": {"missing": 1, "persisted:market_gate": 1},
                "missing_date_ranges": [{"start": "2026-06-03", "end": "2026-06-03", "days": 1}],
            },
            "trading_day_exposure": [
                _equity_exposure_coverage(
                    "fixed_20d_exposure_matched_to_risk_0p005",
                    [{"date": "2026-06-03", "exposure_basis": "state_max_fallback"}],
                )
            ],
        },
    )

    content = report.read_text(encoding="utf-8")
    assert "Synthetic exposure-matched baselines remain controls only" in content


def test_liquidity_unit_unverified_report_remains_blocked(tmp_path) -> None:
    report = tmp_path / "liquidity.md"
    liquidity = _liquidity_readiness(
        [
            {"daily_amount": 1_000_000.0},
            {"daily_amount": 17_000_000.0},
        ]
    )
    _write_liquidity_unit_report(
        report,
        {
            "status": "blocked",
            "unit_status": "unverified",
            "liquidity": liquidity,
            "thresholds_all_fail": True,
            "interpretation": "unit must be confirmed",
        },
    )

    content = report.read_text(encoding="utf-8")
    assert liquidity["status"] == "blocked"
    assert "unit_status: unverified" in content
    assert "keep this report blocked until the upstream unit is explicitly confirmed" in content


def test_month_cluster_bootstrap_reports_cluster_count() -> None:
    fixed = PortfolioBacktestResult(
        variant="fixed_20d",
        horizon="20d",
        equity_curve=[
            {"date": "2026-01-02", "net_value": 100.0},
            {"date": "2026-01-03", "net_value": 101.0},
            {"date": "2026-02-02", "net_value": 102.0},
            {"date": "2026-02-03", "net_value": 103.0},
        ],
        trades=[],
        metrics={},
        skip_counts={},
    )
    risk = PortfolioBacktestResult(
        variant="risk_budget",
        horizon="20d",
        equity_curve=[
            {"date": "2026-01-02", "net_value": 100.0},
            {"date": "2026-01-03", "net_value": 102.0},
            {"date": "2026-02-02", "net_value": 103.0},
            {"date": "2026-02-03", "net_value": 105.0},
        ],
        trades=[],
        metrics={},
        skip_counts={},
    )

    result = _cluster_bootstrap_by_period(fixed, risk, period="month", iterations=20)

    assert result["status"] == "ready"
    assert result["cluster_count"] == 2
    assert result["p10_increment"] is not None


def test_risk_budget_recommendation_uses_actual_0p01_variant_key_for_concentration() -> None:
    recommendation = _risk_budget_recommendation(
        [
            {
                "variant": "fixed_20d_equal",
                "cumulative_return": 0.02,
                "max_drawdown": 0.53,
            },
            {
                "variant": "risk_budget_rpt_0p005",
                "cumulative_return": 0.19,
                "max_drawdown": 0.14,
                "daily_sharpe": 1.14,
                "max_single_name_weight": 0.16,
                "fallback_exposure_ratio": 0.0,
                "liquidity_200m_pass_count": 5,
            },
            {
                "variant": "risk_budget_rpt_0p01",
                "cumulative_return": 0.38,
                "max_drawdown": 0.268,
                "max_single_name_weight": 0.302,
            },
        ],
        {"p10_increment": 0.01},
        {"selected_risk_per_trade": 0.003},
    )

    assert recommendation["risk_budget_0p010_too_concentrated"] is True
    assert recommendation["criteria"]["fallback_ratio_below_10pct"] is True


def test_path_exit_candidate_rules_accept_exact_zero_non_worse_deltas() -> None:
    candidates = _path_exit_candidate_rules(
        [
            {
                "rule": "day3_underwater_reduce_half",
                "fixed_20d_return_delta": 0.0,
                "fixed_20d_mdd_delta": 0.0,
                "risk_0p005_return_delta": 0.0,
                "risk_0p005_mdd_delta": 0.0,
            }
        ]
    )

    assert candidates == ["day3_underwater_reduce_half"]


def test_path_mode_exit_uses_trigger_next_open_without_future_rebound() -> None:
    execution = [_execution_row("000001.SZ", ema10=9.0)]
    price_paths = {"000001.SZ|2026-06-02": _twenty_day_path(trigger_exit_open=9.0, later_close=100.0)}
    simulations = simulate_hold_progress_exits(execution, price_paths)
    sim_by_rule = _simulations_by_rule(simulations)

    result = _run_path_exit_portfolio_variant(
        execution,
        [{"trade_date": "2026-06-02", "market_state": "HOT"}],
        [{"trade_date": "2026-06-02", "exposure": 1.0}],
        price_paths,
        sim_by_rule,
        rule="day3_underwater_exit",
        sizing="equal_weight",
        risk_per_trade=None,
        initial_capital=100.0,
        max_positions=1,
    )

    assert result["position_rows"][0]["date"] == "2026-06-05"
    assert result["position_rows"][0]["exit_price"] == pytest.approx(9.0)
    assert result["position_rows"][0]["return_net"] == pytest.approx(-0.10369)


def test_path_mode_report_baselines_tie_out_to_portfolio_engine() -> None:
    first = _execution_row("000001.SZ", ema10=9.0, rank=1)
    second = {
        **_execution_row("000002.SZ", ema10=9.0, rank=1),
        "signal_date": "2026-06-20",
        "entry_date": "2026-06-21",
    }
    price_paths = {
        "000001.SZ|2026-06-02": _twenty_day_path(),
        "000002.SZ|2026-06-21": [
            _path_row(f"2026-06-{day:02d}", open_price=10.0, close_price=10.0)
            for day in range(21, 31)
        ]
        + [
            _path_row(f"2026-07-{day:02d}", open_price=10.0, close_price=10.0)
            for day in range(1, 12)
        ],
    }

    rows = _path_engine_tieout_rows(
        [first, second],
        [
            {"trade_date": "2026-06-02", "market_state": "HOT"},
            {"trade_date": "2026-06-21", "market_state": "HOT"},
        ],
        [
            {"trade_date": "2026-06-02", "exposure": 1.0},
            {"trade_date": "2026-06-21", "exposure": 1.0},
        ],
        price_paths,
        initial_capital=100.0,
        max_positions=1,
    )

    assert {row["variant"] for row in rows} == {"fixed_20d", "risk_0p005", "risk_0p010"}
    assert all(row["cumulative_return_delta"] == pytest.approx(0.0) for row in rows)
    assert all(row["max_drawdown_delta"] == pytest.approx(0.0) for row in rows)


def test_adjustment_gap_sensitivity_excludes_missing_adj_paths() -> None:
    execution = [_execution_row("000001.SZ", ema10=9.0)]
    price_paths = {"000001.SZ|2026-06-02": _twenty_day_path()}

    result = _adjustment_gap_sensitivity(
        execution,
        [{"trade_date": "2026-06-02", "market_state": "HOT"}],
        [{"trade_date": "2026-06-02", "exposure": 1.0}],
        price_paths,
        initial_capital=100.0,
        max_positions=1,
    )

    assert result["status"] == "ready"
    assert result["clean_execution_row_count"] == 1
    assert "risk_0p005_still_beats_fixed_20d" in result


def test_hold_exit_recommendation_rejects_position_candidates_when_portfolio_worsens() -> None:
    recommendation = _hold_exit_recommendation(
        [
            {
                "rule": "day5_no_progress_reduce_half",
                "baseline_p5": -0.20,
                "rule_p5": -0.12,
                "baseline_p10": -0.18,
                "rule_p10": -0.10,
                "winner_damage": 0.02,
                "fixed_20d_return_delta": -0.15,
                "fixed_20d_mdd_delta": 0.08,
                "risk_0p005_return_delta": -0.06,
                "risk_0p005_mdd_delta": 0.02,
            }
        ],
        [],
        portfolio_engine_mode="horizon_diagnostic",
    )

    assert recommendation["no_progress_exit"] == "research_only"
    assert recommendation["candidate_rules"] == []
    assert recommendation["position_level_candidate_rules"] == ["day5_no_progress_reduce_half"]
    assert recommendation["portfolio_rejected_rules"] == ["day5_no_progress_reduce_half"]
    assert recommendation["mode_consistent_with_risk_report"] is False


def test_hold_exit_recommendation_accepts_exact_zero_portfolio_non_worse() -> None:
    recommendation = _hold_exit_recommendation(
        [
            {
                "rule": "day3_underwater_reduce_half",
                "baseline_p5": -0.20,
                "rule_p5": -0.12,
                "baseline_p10": -0.18,
                "rule_p10": -0.10,
                "winner_damage": 0.02,
                "fixed_20d_return_delta": 0.0,
                "fixed_20d_mdd_delta": 0.0,
                "risk_0p005_return_delta": 0.0,
                "risk_0p005_mdd_delta": 0.0,
            }
        ],
        [],
        portfolio_engine_mode="path",
    )

    assert recommendation["candidate_rules"] == ["day3_underwater_reduce_half"]
    assert recommendation["portfolio_rejected_rules"] == []


def test_batch3_summary_keeps_no_go_when_data_is_blocked_even_if_subreport_has_candidate(tmp_path) -> None:
    report = tmp_path / "summary.md"
    payload = write_batch3_summary(
        report_path=report,
        data_payload={
            "status": "blocked",
            "blockers": ["macro missing"],
            "gate_exposure": {"fallback_ratio": 0.82},
            "macro_history": {"status": "blocked"},
            "liquidity": {"thresholds": []},
        },
        risk_payload={
            "status": "research_only",
            "recommendation": {"risk_budget_0p005": "candidate_for_further_paper_trading"},
        },
        exit_payload={
            "status": "research_only",
            "recommendation": {"no_progress_exit": "candidate_for_further_paper_trading"},
        },
        entry_payload={"status": "research_only"},
    )

    content = report.read_text(encoding="utf-8")
    assert payload["risk_budget_0p005_go_no_go"] == "no-go"
    assert payload["no_progress_exit_go_no_go"] == "no-go"
    assert "- risk_budget_0.005: no-go" in content
    assert "- no-progress exit: no-go" in content


def test_exit_report_marks_horizon_portfolio_comparison_diagnostic_only(tmp_path) -> None:
    report = tmp_path / "exit.md"
    _write_exit_report(
        report,
        {
            "status": "research_only",
            "signal_kind": "stock_candidate",
            "evaluated_position_rule_rows": 1,
            "portfolio_engine_mode": "horizon_diagnostic",
            "portfolio_comparison_scope": "diagnostic_only_not_comparable_to_path_mode_risk_report",
            "position_level_csv": "positions.csv",
            "portfolio_level_csv": "portfolio.csv",
            "rule_rows": [],
            "residual_rows": [],
            "portfolio_rows": [],
            "recommendation": {"no_progress_exit": "research_only"},
        },
    )

    content = report.read_text(encoding="utf-8")
    assert "portfolio_engine_mode: horizon_diagnostic" in content
    assert "diagnostic-only" in content


def test_risk_budget_handles_stop_fallback_single_name_and_exposure_caps() -> None:
    result = run_portfolio_backtest(
        [
            _execution_row("000001.SZ", ema10=None, rank=1, market_state="WARM"),
            _execution_row("000002.SZ", ema10=10.0, rank=2, market_state="WARM"),
            _execution_row("000003.SZ", ema10=-1.0, rank=3, market_state="WARM"),
        ],
        [{"trade_date": "2026-06-02", "market_state": "WARM"}],
        variant="fixed_5d",
        initial_capital=100.0,
        max_positions=5,
        exposure_by_market_state={"WARM": (0.3,)},
        sizing="risk_budget",
        risk_per_trade=0.10,
        single_name_cap=0.20,
        fallback_stop_distance_pct=0.08,
    )

    buys = [row for row in result.trades if row["action"] == "buy"]
    assert buys[0]["amount"] == pytest.approx(20.0)
    assert buys[0]["stop_ref_fallback"] is True
    assert buys[1]["amount"] == pytest.approx(10.0)
    assert buys[1]["exposure_cap_clipped"] is True
    assert result.skip_counts["exposure_cap_skip"] == 1


def test_batch3_script_does_not_change_live_formula_version() -> None:
    assert FORMULA_VERSION == "rv_livermore_stock_candidates_bundle_v7"


def test_gate_fallback_split_uses_trading_day_ratio_for_strategy_gate() -> None:
    decision = _gate_fallback_split_decision(
        {"fallback_ratio": 0.342229},
        {"fallback_ratio": 0.0},
        {"status": "ready", "true_trading_day_missing_count": 0},
    )

    assert decision["path_simulation_status"] == "ready"
    assert decision["calendar_pipeline_status"] == "research_only"
    assert decision["trading_day_exposure_fallback_ratio"] == 0.0
    assert decision["blockers"] == []

    blocked = _gate_fallback_split_decision(
        {"fallback_ratio": 0.0},
        {"fallback_ratio": 0.000001},
        {"status": "ready", "true_trading_day_missing_count": 0},
    )
    assert blocked["path_simulation_status"] == "blocked"
    assert "trading-day exposure fallback ratio is above 0" in blocked["blockers"]


def test_liquidity_canonical_status_does_not_auto_select_unit_multiplier() -> None:
    status = _canonical_liquidity_status(
        {"canonical_field_status": "daily_amount_rmb_unconfirmed"},
        {"unit_hypothesis": "consistent_with_scaled_amount_and_lot_volume"},
    )

    assert status["status"] == "blocked"
    assert status["multiplier"] is None
    assert "vendor unit contract is missing" in status["reason"]


def test_adjustment_factor_go_gate_blocks_missing_gt_2pct_and_biased_clean_subset() -> None:
    blockers = _adjustment_factor_blockers(0.175922, 0.112591)

    assert "adjustment factor missing ratio is above 2%" in blockers
    assert "clean adjustment subset share is below 70%; promotion evidence would be sample-biased" in blockers


def test_data_quality_go_blockers_accept_exact_zero_gate_but_block_liquidity_and_adjustment() -> None:
    blockers = _data_quality_go_blockers(
        {"path_simulation_gate": {"trading_day_exposure_fallback_ratio": 0.0}},
        {"canonical_status": "blocked"},
        {"price_path_adjustment": {"missing_adjustment_factor_ratio": 0.03}},
    )

    assert "trading-day gate fallback > 0" not in blockers
    assert "liquidity canonical RMB amount is not verified" in blockers
    assert "adjustment factor missing ratio > 2%" in blockers


def test_risk_budget_optimization_never_promotes_0p010_or_concentrated_rows() -> None:
    decision = _risk_budget_optimization_decision(
        [
            {
                "risk_per_trade": 0.010,
                "diagnostic_only": True,
                "hard_fail": False,
                "max_single_name_weight": 0.10,
                "robust_utility": 99.0,
            },
            {
                "risk_per_trade": 0.005,
                "diagnostic_only": False,
                "hard_fail": True,
                "max_single_name_weight": 0.21,
                "robust_utility": 10.0,
            },
            {
                "risk_per_trade": 0.003,
                "diagnostic_only": False,
                "hard_fail": False,
                "max_single_name_weight": 0.12,
                "robust_utility": 1.0,
            },
        ],
        gate_payload={"path_simulation_gate": {"trading_day_exposure_fallback_ratio": 0.0}},
        liquidity_payload={"canonical_status": "ready"},
        adjustment_payload={"price_path_adjustment": {"missing_adjustment_factor_ratio": 0.0}},
        daily_bootstrap={"p10_increment": 0.0},
        month_bootstrap={"p10_increment": 0.0},
        walk_forward={"selected_risk_per_trade": 0.003},
    )

    assert decision["risk_0p010_candidate_allowed"] is False
    assert decision["best_research_candidate"]["risk_per_trade"] == 0.003
    assert all((row.get("risk_per_trade") != 0.010) for row in decision["candidate_list"])


def test_report_csv_writer_emits_required_position_columns(tmp_path) -> None:
    out = tmp_path / "positions.csv"
    _write_csv(
        out,
        [
            {
                "stock_code": "000001.SZ",
                "entry_date": "2026-06-02",
                "rule": "day3_underwater_exit",
                "planned_exit_date": "2026-06-30",
                "exit_date": "2026-06-05",
                "missing_exit": False,
                "residual_return_after_trigger": 0.10,
            }
        ],
    )

    header = out.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert "stock_code" in header
    assert "planned_exit_date" in header
    assert "exit_date" in header
    assert "residual_return_after_trigger" in header


def test_canonical_path_rows_flag_gate_exposure_and_horizon_gaps() -> None:
    source = _execution_row("000001.SZ", ema10=9.0)
    source["exit_date_20d"] = "2026-06-03"
    source["return_20d_net_adj"] = 0.01
    path_row = _path_row("2026-06-04", open_price=10.0, close_price=9.8)
    path_row.update({"amount": 1_000_000.0, "volume": 100_000.0})
    loaded = {
        "execution_rows": [source],
        "price_paths": {"000001.SZ|2026-06-02": [path_row]},
        "exposure_rows": [],
        "market_state_rows": [{"trade_date": "2026-06-04", "market_state": "HOT"}],
    }

    rows = _canonical_path_rows(
        loaded,
        {"path_simulation_gate": {"trading_day_exposure_fallback_ratio": 0.0}},
        {"canonical_status": "blocked"},
    )

    assert rows[0]["gate_exposure"] is None
    assert rows[0]["beyond_planned_exit"] is True
    assert rows[0]["exposure_window_missing"] is True
    assert "gate_exposure_missing" in rows[0]["data_quality_flags"]
    assert "beyond_planned_exit" in rows[0]["data_quality_flags"]
    assert rows[0]["raw_daily_amount"] == 1_000_000.0
    assert rows[0]["implied_amount_multiplier_diagnostic"] != "insufficient_raw_amount_volume_close"


def test_canonical_trade_rows_compute_exit_price_and_lineage_from_path() -> None:
    source = _execution_row("000001.SZ", ema10=9.0)
    source["exit_date_20d"] = "2026-06-30"
    source["return_20d_net_adj"] = None
    source["exit_price_20d"] = None
    loaded = {
        "execution_rows": [source],
        "price_paths": {"000001.SZ|2026-06-02": _twenty_day_path(later_close=11.0)},
        "exposure_rows": [{"trade_date": "2026-06-02", "exposure": 0.5}],
        "market_state_rows": [],
    }

    rows = _canonical_trade_rows(
        loaded,
        {"path_simulation_gate": {"trading_day_exposure_fallback_ratio": 0.0}},
        {"canonical_status": "blocked"},
        {"price_path_adjustment": {"missing_adjustment_factor_ratio": 0.0}},
    )

    assert rows[0]["exit_price_adjusted"] is not None
    assert rows[0]["exit_price_adjusted_lineage"] == "computed_from_path_horizon_20d"
    assert rows[0]["return_20d_net_adj"] is not None
    assert rows[0]["return_20d_net_adj_lineage"] == "computed_from_path_horizon_20d"
    assert rows[0]["incomplete_horizon"] is False
    assert rows[0]["position_weight"] == pytest.approx(0.1)
    assert rows[0]["stop_distance"] == pytest.approx(0.1)


def test_canonical_quality_summary_reports_null_ratios_and_denominator_scopes() -> None:
    source = _execution_row("000001.SZ", ema10=9.0)
    source["exit_date_20d"] = "2026-06-03"
    path = [
        {**_path_row("2026-06-02", open_price=10.0, close_price=10.0), "adj_factor_missing": False},
        {**_path_row("2026-06-03", open_price=10.0, close_price=9.9), "adj_factor_missing": True},
        {**_path_row("2026-06-04", open_price=10.0, close_price=9.8), "adj_factor_missing": True},
    ]
    loaded = {
        "execution_rows": [source],
        "price_paths": {"000001.SZ|2026-06-02": path},
    }
    path_rows = [
        {
            "daily_amount_rmb_canonical": None,
            "gate_exposure": None,
            "position_weight": None,
            "stop_distance": 0.1,
            "volatility_regime": None,
            "adjustment_factor_missing": False,
            "within_planned_horizon": True,
        },
        {
            "daily_amount_rmb_canonical": None,
            "gate_exposure": None,
            "position_weight": None,
            "stop_distance": 0.1,
            "volatility_regime": None,
            "adjustment_factor_missing": True,
            "within_planned_horizon": True,
        },
        {
            "daily_amount_rmb_canonical": None,
            "gate_exposure": None,
            "position_weight": None,
            "stop_distance": 0.1,
            "volatility_regime": None,
            "adjustment_factor_missing": True,
            "within_planned_horizon": False,
        },
    ]
    trade_rows = [
        {
            "daily_amount_rmb_canonical": None,
            "gate_exposure": None,
            "position_weight": None,
            "stop_distance": 0.1,
            "exit_price_adjusted": 10.0,
            "return_20d_net_adj": 0.0,
        }
    ]

    summary = _canonical_quality_summary_rows(
        loaded,
        path_rows,
        trade_rows,
        {"path_simulation_gate": {"trading_day_exposure_fallback_ratio": 0.0, "path_simulation_status": "ready"}},
        {"canonical_status": "blocked", "status": "blocked"},
        {"status": "blocked", "price_path_adjustment": {"missing_adjustment_factor_ratio": 2 / 3}},
    )
    by_metric = {row["metric"]: row for row in summary}

    assert by_metric["paths_daily_amount_rmb_canonical_null_ratio"]["value"] == 1.0
    assert by_metric["paths_gate_exposure_null_ratio"]["status"] == "blocked"
    assert by_metric["canonical_path_rows"]["value"] == 3
    assert by_metric["canonical_missing_adjustment_factor_rows"]["value"] == 2
    assert by_metric["within_horizon_missing_adjustment_factor_rows"]["value"] == 1


def test_amount_like_source_columns_returns_real_non_null_counts() -> None:
    conn = duckdb.connect(":memory:")
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
                amount double,
                turnover double,
                stock_code varchar
            )
            """
        )
        conn.execute("insert into choice_stock_daily_observation values (1.0, null, 'A'), (2.0, 3.0, 'B'), (null, null, 'C')")

        rows = _amount_like_source_columns(conn)
    finally:
        conn.close()

    by_column = {row["column"]: row for row in rows if row["table"] == "choice_stock_daily_observation"}
    assert by_column["amount"]["non_null_count"] == 2
    assert by_column["turnover"]["non_null_count"] == 1
    assert by_column["amount"]["scan_status"] == "scanned"


def test_risk_budget_optimization_rows_cover_cap_and_exposure_cap_dimensions(monkeypatch) -> None:
    calls: list[tuple[float, float, str]] = []

    def fake_backtest(*args, **kwargs):
        risk = kwargs["risk_per_trade"]
        cap = kwargs["single_name_cap"]
        exposure_cap = "existing_gate" if kwargs.get("exposure_by_date") is None else "capped"
        calls.append((risk, cap, exposure_cap))
        return PortfolioBacktestResult(
            variant="fixed_20d",
            horizon="20d",
            equity_curve=[
                {"date": "2026-06-02", "net_value": 100.0},
                {"date": "2026-06-03", "net_value": 101.0},
            ],
            trades=[],
            metrics={
                "cumulative_return": 0.01,
                "cagr": 0.01,
                "max_drawdown": 0.0,
                "daily_sharpe": 1.0,
                "max_single_name_weight": cap,
                "annual_turnover": 1.0,
            },
            skip_counts={},
        )

    monkeypatch.setattr(batch3_research, "run_portfolio_backtest", fake_backtest)
    loaded = {
        "execution_rows": [_execution_row("000001.SZ", ema10=9.0)],
        "market_state_rows": [{"trade_date": "2026-06-02", "market_state": "HOT"}],
        "exposure_rows": [{"trade_date": "2026-06-02", "exposure": 0.75}],
        "price_paths": {"000001.SZ|2026-06-02": _twenty_day_path()},
    }

    rows = _risk_budget_optimization_rows(
        loaded,
        gate_payload={"path_simulation_gate": {"trading_day_exposure_fallback_ratio": 0.0}},
        liquidity_payload={"canonical_status": "ready"},
        adjustment_payload={"price_path_adjustment": {"missing_adjustment_factor_ratio": 0.0}},
        initial_capital=100.0,
        max_positions=5,
    )

    expected_count = (
        len(batch3_research.RISK_PER_TRADE_OPTIMIZATION_GRID)
        * len(batch3_research.SINGLE_NAME_CAP_OPTIMIZATION_GRID)
        * len(batch3_research.PORTFOLIO_EXPOSURE_CAP_GRID)
    )
    assert len(rows) == expected_count
    assert len(calls) == expected_count
    assert len({row["single_name_cap"] for row in rows}) > 1
    assert {"existing_gate", 0.5, 0.75, 1.0}.issubset({row["portfolio_exposure_cap"] for row in rows})
    assert all(row["portfolio_exposure_cap"] != 1.25 for row in rows)
    assert all(row["portfolio_exposure_cap_semantics"] == "downside_clamp_existing_gate" for row in rows)


def test_risk_budget_report_declares_grid_skip_when_blocked(tmp_path) -> None:
    out = tmp_path / "risk.md"
    _write_risk_budget_optimization_report(
        out,
        {
            "status": "blocked",
            "decision": {
                "recommendation": "blocked",
                "selected_walk_forward_risk_per_trade": None,
                "risk_0p010_candidate_allowed": False,
                "blockers": ["liquidity canonical RMB amount is not verified"],
            },
            "optimization_rows": [],
            "grid_execution_status": "skipped_until_data_blockers_clear",
            "grid_skip_reason": "full grid is not executed while data blockers remain",
            "required_grid_cell_count": 175,
            "required_risk_per_trade_grid": [0.003, 0.005],
            "required_single_name_cap_grid": [0.10, 0.125],
            "required_portfolio_exposure_cap_grid": ["existing_gate", 0.50],
            "live_strategy_changes": "none",
        },
    )

    content = out.read_text(encoding="utf-8")
    assert "grid_execution_status: skipped_until_data_blockers_clear" in content
    assert "required_single_name_cap_grid" in content
    assert "required_portfolio_exposure_cap_grid" in content


def test_a_share_constraint_diagnostics_do_not_mark_ready_while_execution_rules_are_incomplete() -> None:
    source = _execution_row("000001.SZ", ema10=9.0)
    source["stock_name"] = "ST Example"
    path = [
        _path_row("2026-06-02", open_price=10.0, close_price=10.0),
        _path_row("2026-06-03", open_price=9.0, close_price=8.8, limit_down=True),
    ]

    diagnostics = _a_share_constraint_diagnostics(
        [source],
        {"000001.SZ|2026-06-02": path},
        {"canonical_status": "blocked"},
    )

    assert diagnostics["execution_constraint_status"] != "ready"
    assert diagnostics["path_limit_down_count"] == 1
    assert diagnostics["st_or_special_treatment_trade_rows"] == 1
    assert diagnostics["capacity_status"] == "blocked"
    assert any("board-lot" in reason for reason in diagnostics["incomplete_reasons"])
