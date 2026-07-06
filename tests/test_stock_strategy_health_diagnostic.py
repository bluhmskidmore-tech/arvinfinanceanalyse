from __future__ import annotations

from pathlib import Path

import duckdb

from tests.helpers import load_module


def _load_module():
    return load_module(
        "scripts.stock_strategy_health_diagnostic",
        "scripts/stock_strategy_health_diagnostic.py",
    )


def _create_db(path: Path) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(str(path), read_only=False)
    conn.execute(
        """
        create table livermore_candidate_history (
          snapshot_as_of_date varchar,
          stock_code varchar,
          stock_name varchar,
          candidate_rank integer,
          signal_kind varchar,
          market_state varchar,
          return_5d double,
          return_20d double,
          data_status varchar
        )
        """
    )
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar,
          stock_code varchar,
          close_value double,
          volume double,
          source_version varchar,
          vendor_version varchar
        )
        """
    )
    return conn


def _create_execution_history_table(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table livermore_candidate_execution_history (
          signal_date varchar,
          stock_code varchar,
          signal_kind varchar,
          market_state varchar,
          entry_executable boolean,
          return_5d_net_adj double,
          return_20d_net_adj double
        )
        """
    )


def _create_position_table(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table livermore_position_snapshot (
          as_of_date varchar,
          stock_code varchar,
          stock_name varchar,
          entry_cost double,
          bars_since_entry integer,
          entry_date varchar,
          position_quantity double,
          position_status varchar,
          source_version varchar,
          vendor_version varchar
        )
        """
    )


def _create_factor_coverage_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table choice_stock_factor_snapshot (
          as_of_date varchar,
          stock_code varchar
        )
        """
    )
    conn.execute(
        """
        create table choice_stock_universe (
          as_of_date varchar,
          stock_code varchar
        )
        """
    )


def _seed_candidate(
    conn: duckdb.DuckDBPyConnection,
    *,
    snapshot_date: str,
    code: str,
    signal_kind: str = "stock_candidate",
    market_state: str = "WARM",
    return_5d: float | None = 0.02,
    return_20d: float | None = 0.01,
    data_status: str = "complete",
) -> None:
    conn.execute(
        """
        insert into livermore_candidate_history values
        (?, ?, ?, 1, ?, ?, ?, ?, ?)
        """,
        [
            snapshot_date,
            code,
            code,
            signal_kind,
            market_state,
            return_5d,
            return_20d,
            data_status,
        ],
    )


def _seed_execution_candidate(
    conn: duckdb.DuckDBPyConnection,
    *,
    signal_date: str,
    code: str,
    signal_kind: str = "stock_candidate",
    market_state: str = "WARM",
    entry_executable: bool = True,
    return_5d_net_adj: float | None = 0.02,
    return_20d_net_adj: float | None = 0.01,
) -> None:
    conn.execute(
        """
        insert into livermore_candidate_execution_history values
        (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            signal_date,
            code,
            signal_kind,
            market_state,
            entry_executable,
            return_5d_net_adj,
            return_20d_net_adj,
        ],
    )


def _seed_daily(conn: duckdb.DuckDBPyConnection, *, trade_date: str) -> None:
    conn.execute(
        """
        insert into choice_stock_daily_observation (trade_date, stock_code, close_value, volume)
        values (?, '000001.SZ', 10.0, 100.0)
        """,
        [trade_date],
    )


def test_health_report_defaults_to_execution_net_adjusted_basis(tmp_path: Path) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_db(db_path)
    try:
        _seed_daily(conn, trade_date="2026-06-12")
        _seed_candidate(conn, snapshot_date="2026-06-12", code="000001.SZ", return_5d=-0.50)
        _create_execution_history_table(conn)
        _seed_execution_candidate(conn, signal_date="2026-06-12", code="000001.SZ", return_5d_net_adj=0.08)
        _seed_execution_candidate(conn, signal_date="2026-06-12", code="000002.SZ", return_5d_net_adj=-0.02)
        _seed_execution_candidate(
            conn,
            signal_date="2026-06-12",
            code="000003.SZ",
            entry_executable=False,
            return_5d_net_adj=0.99,
        )
    finally:
        conn.close()

    report = module.build_stock_strategy_health_report(duckdb_path=db_path, as_of_date="2026-06-12")

    stats = report["performance_by_signal"]["stock_candidate"]["return_5d"]
    assert report["metric_basis"] == "net_next_open_adj"
    assert report["threshold_recalibration_due"] == "上线后20个交易日"
    assert report["performance_by_signal"]["stock_candidate"]["row_count"] == 2
    assert stats["count"] == 2
    assert stats["avg_return"] == 0.03
    assert stats["win_rate"] == 0.5


def test_health_report_legacy_basis_keeps_signal_close_forward_returns(tmp_path: Path) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_db(db_path)
    try:
        _seed_daily(conn, trade_date="2026-06-12")
        _seed_candidate(conn, snapshot_date="2026-06-12", code="000001.SZ", return_5d=-0.50)
        _create_execution_history_table(conn)
        _seed_execution_candidate(conn, signal_date="2026-06-12", code="000001.SZ", return_5d_net_adj=0.08)
    finally:
        conn.close()

    report = module.build_stock_strategy_health_report(
        duckdb_path=db_path,
        as_of_date="2026-06-12",
        legacy_basis=True,
    )

    stats = report["performance_by_signal"]["stock_candidate"]["return_5d"]
    assert report["metric_basis"] == "legacy_signal_close_forward"
    assert stats["count"] == 1
    assert stats["avg_return"] == -0.5
    assert stats["win_rate"] == 0.0


def test_health_report_surfaces_absent_stock_candidates_on_policy_active_date_and_overheat_drag(tmp_path: Path) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_db(db_path)
    try:
        for trade_date in ("2026-06-01", "2026-06-02", "2026-06-03", "2026-06-12"):
            _seed_daily(conn, trade_date=trade_date)
        _seed_candidate(conn, snapshot_date="2026-05-12", code="000001.SZ", return_5d=0.03)
        _seed_candidate(conn, snapshot_date="2026-05-12", code="000002.SZ", return_5d=-0.01)
        _seed_candidate(
            conn,
            snapshot_date="2026-05-12",
            code="000003.SZ",
            market_state="OVERHEAT",
            return_5d=-0.02,
            return_20d=-0.05,
        )
        _seed_candidate(
            conn,
            snapshot_date="2026-06-12",
            code="000004.SZ",
            signal_kind="factor_screen",
            market_state="WARM",
            return_5d=None,
            return_20d=None,
            data_status="pending",
        )
    finally:
        conn.close()

    report = module.build_stock_strategy_health_report(duckdb_path=db_path, as_of_date="2026-06-12")

    assert report["status"] == "blocked"
    assert report["data_freshness"]["choice_stock_daily_observation"]["max_date"] == "2026-06-12"
    assert report["data_freshness"]["stock_candidate_latest_date"] == "2026-05-12"
    assert report["performance_by_signal"]["stock_candidate"]["return_5d"]["win_rate"] == 1 / 3
    assert report["performance_by_market_state_signal"]["OVERHEAT"]["stock_candidate"]["return_5d"]["avg_return"] == -0.02
    assert "stock_candidate_absent_on_policy_active_date" in {finding["code"] for finding in report["findings"]}
    assert "overheat_stock_candidate_underperforms" in {finding["code"] for finding in report["findings"]}
    assert "factor_screen_coverage_below_primary_threshold" in {finding["code"] for finding in report["findings"]}


def test_health_report_does_not_treat_policy_inactive_overheat_as_stock_candidate_stale(tmp_path: Path) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_db(db_path)
    try:
        for trade_date in ("2026-06-01", "2026-06-02", "2026-06-03", "2026-06-12"):
            _seed_daily(conn, trade_date=trade_date)
        _seed_candidate(conn, snapshot_date="2026-05-12", code="000001.SZ", market_state="WARM")
        _seed_candidate(
            conn,
            snapshot_date="2026-06-12",
            code="000004.SZ",
            signal_kind="factor_screen",
            market_state="OVERHEAT",
            return_5d=None,
            return_20d=None,
            data_status="pending",
        )
    finally:
        conn.close()

    report = module.build_stock_strategy_health_report(duckdb_path=db_path, as_of_date="2026-06-12")

    codes = {finding["code"] for finding in report["findings"]}
    assert "stock_candidate_stale_vs_policy_active_date" not in codes
    assert report["data_freshness"]["stock_candidate_policy"]["latest_history_market_state"] == "OVERHEAT"
    assert report["data_freshness"]["stock_candidate_policy"]["latest_policy_active_history_date"] == "2026-05-12"


def test_health_report_includes_pretrade_readiness_before_position_rollforward(tmp_path: Path) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_db(db_path)
    try:
        _create_position_table(conn)
        _seed_daily(conn, trade_date="2026-05-29")
        _seed_candidate(
            conn,
            snapshot_date="2026-05-29",
            code="000001.SZ",
            signal_kind="factor_screen",
            market_state="OVERHEAT",
            return_5d=None,
            return_20d=None,
        )
    finally:
        conn.close()

    report = module.build_stock_strategy_health_report(duckdb_path=db_path, as_of_date="2026-06-12")

    assert report["pretrade_readiness"]["ready"] is False
    assert "choice_stock_inputs" in report["pretrade_readiness"]["missing"]
    assert "position_snapshot" in report["pretrade_readiness"]["missing"]
    codes = {finding["code"] for finding in report["findings"]}
    assert "position_rollforward_waits_for_choice_stock_inputs" in codes
    assert any("Do not roll forward" in action for action in report["recommended_next_actions"])
    assert not any(action.startswith("Land active Livermore position snapshots") for action in report["recommended_next_actions"])


def test_health_report_blocks_when_pretrade_readiness_check_fails(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_db(db_path)
    try:
        _seed_daily(conn, trade_date="2026-06-12")
        _seed_candidate(conn, snapshot_date="2026-06-12", code="000001.SZ")
    finally:
        conn.close()

    def fail_readiness(**_kwargs):
        raise RuntimeError("readiness exploded")

    monkeypatch.setattr(module, "inspect_livermore_daily_refresh_state", fail_readiness)

    report = module.build_stock_strategy_health_report(duckdb_path=db_path, as_of_date="2026-06-12")

    assert report["status"] == "blocked"
    assert report["pretrade_readiness"]["missing"] == ["pretrade_readiness_error"]
    assert "pretrade_readiness_error" in {finding["code"] for finding in report["findings"]}
    assert any("readiness check" in action for action in report["recommended_next_actions"])


def test_health_report_recommendation_uses_requested_as_of_date(tmp_path: Path) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_db(db_path)
    try:
        _create_position_table(conn)
        _seed_daily(conn, trade_date="2026-05-29")
        _seed_candidate(
            conn,
            snapshot_date="2026-05-29",
            code="000001.SZ",
            signal_kind="factor_screen",
            market_state="OVERHEAT",
            return_5d=None,
            return_20d=None,
        )
    finally:
        conn.close()

    report = module.build_stock_strategy_health_report(duckdb_path=db_path, as_of_date="2026-06-15")

    actions = report["recommended_next_actions"]
    assert any("2026-06-15 stock inputs" in action for action in actions)
    assert not any("6/12 stock inputs" in action for action in actions)


def test_health_report_does_not_recommend_rerun_when_policy_active_date_emits_no_stock_candidates(
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_db(db_path)
    try:
        _create_position_table(conn)
        _seed_daily(conn, trade_date="2026-06-12")
        _seed_candidate(conn, snapshot_date="2026-05-12", code="000001.SZ", market_state="WARM")
        _seed_candidate(
            conn,
            snapshot_date="2026-06-12",
            code="000004.SZ",
            signal_kind="factor_screen",
            market_state="HOT",
            return_5d=None,
            return_20d=None,
            data_status="pending",
        )
    finally:
        conn.close()

    report = module.build_stock_strategy_health_report(duckdb_path=db_path, as_of_date="2026-06-12")

    codes = {finding["code"] for finding in report["findings"]}
    assert "stock_candidate_absent_on_policy_active_date" in codes
    assert "stock_candidate_stale_vs_policy_active_date" not in codes
    assert not any(action.startswith("Rerun Livermore stock_candidate") for action in report["recommended_next_actions"])
    assert report["candidate_filter_diagnostic"]["status"] == "unavailable"


def test_health_report_marks_risk_exit_blocked_without_active_positions(tmp_path: Path) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_db(db_path)
    try:
        _seed_daily(conn, trade_date="2026-06-12")
        _seed_candidate(conn, snapshot_date="2026-06-12", code="000001.SZ")
    finally:
        conn.close()

    report = module.build_stock_strategy_health_report(duckdb_path=db_path, as_of_date="2026-06-12")

    assert report["risk_exit"]["status"] == "blocked"
    assert "livermore_position_snapshot" in report["risk_exit"]["reason"]
    assert "risk_exit_blocked" in {finding["code"] for finding in report["findings"]}


def test_health_report_includes_overheat_holding_context_counts(tmp_path: Path) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_db(db_path)
    try:
        _create_position_table(conn)
        for offset in range(25):
            _seed_daily(conn, trade_date=f"2026-06-{offset + 1:02d}")
        _seed_candidate(
            conn,
            snapshot_date="2026-06-21",
            code="000001.SZ",
            market_state="OVERHEAT",
        )
        conn.execute(
            """
            insert into livermore_position_snapshot (
              as_of_date,
              stock_code,
              stock_name,
              entry_cost,
              bars_since_entry,
              entry_date,
              position_quantity,
              position_status
            )
            values ('2026-06-21', '000001.SZ', 'Alpha', 10.0, 21, null, 1.0, 'ACTIVE')
            """
        )
    finally:
        conn.close()

    report = module.build_stock_strategy_health_report(duckdb_path=db_path, as_of_date="2026-06-21")

    context = report["overheat_holding_context"]
    assert context["status"] == "ready"
    assert context["market_state"] == "OVERHEAT"
    assert context["overheat_signal_detected"] is True
    assert context["active_holding_count"] == 1
    assert context["risk_exit_watch_count"] == 1
    assert context["risk_exit_triggered_count"] == 0


def test_health_report_flags_factor_screen_coverage_below_primary_threshold(tmp_path: Path) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_db(db_path)
    try:
        _seed_daily(conn, trade_date="2026-06-12")
        _seed_candidate(conn, snapshot_date="2026-06-12", code="000001.SZ")
        _create_factor_coverage_tables(conn)
        conn.executemany(
            "insert into choice_stock_factor_snapshot values (?, ?)",
            [("2026-06-12", "000001.SZ"), ("2026-06-12", "000002.SZ")],
        )
        conn.executemany(
            "insert into choice_stock_universe values (?, ?)",
            [("2026-06-12", f"00000{i}.SZ") for i in range(1, 11)],
        )
    finally:
        conn.close()

    report = module.build_stock_strategy_health_report(duckdb_path=db_path, as_of_date="2026-06-12")

    coverage = report["factor_screen_coverage"]
    assert coverage["status"] == "blocked"
    assert coverage["coverage_count"] == 2
    assert coverage["coverage_denominator"] == 10
    assert coverage["coverage_ratio"] == 0.2
    assert "factor_screen_coverage_below_primary_threshold" in {finding["code"] for finding in report["findings"]}


def test_health_report_blocks_stale_factor_screen_even_with_full_coverage(tmp_path: Path) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_db(db_path)
    try:
        for trade_date in ("2026-06-01", "2026-06-02", "2026-06-03", "2026-06-12"):
            _seed_daily(conn, trade_date=trade_date)
        _seed_candidate(conn, snapshot_date="2026-06-12", code="000001.SZ")
        _create_factor_coverage_tables(conn)
        conn.executemany(
            "insert into choice_stock_factor_snapshot values (?, ?)",
            [("2026-05-29", "000001.SZ"), ("2026-05-29", "000002.SZ")],
        )
        conn.executemany(
            "insert into choice_stock_universe values (?, ?)",
            [("2026-05-29", "000001.SZ"), ("2026-05-29", "000002.SZ")],
        )
    finally:
        conn.close()

    report = module.build_stock_strategy_health_report(duckdb_path=db_path, as_of_date="2026-06-12")

    coverage = report["factor_screen_coverage"]
    assert coverage["status"] == "blocked"
    assert coverage["lag_days"] == 4
    assert "factor_screen_stale_vs_requested" in {finding["code"] for finding in report["findings"]}


def test_health_report_uses_trading_days_for_factor_screen_freshness(tmp_path: Path) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_db(db_path)
    try:
        _seed_daily(conn, trade_date="2026-06-15")
        _seed_candidate(conn, snapshot_date="2026-06-15", code="000001.SZ")
        _create_factor_coverage_tables(conn)
        conn.executemany(
            "insert into choice_stock_factor_snapshot values (?, ?)",
            [("2026-06-12", "000001.SZ"), ("2026-06-12", "000002.SZ")],
        )
        conn.executemany(
            "insert into choice_stock_universe values (?, ?)",
            [("2026-06-12", "000001.SZ"), ("2026-06-12", "000002.SZ")],
        )
    finally:
        conn.close()

    report = module.build_stock_strategy_health_report(duckdb_path=db_path, as_of_date="2026-06-15")

    coverage = report["factor_screen_coverage"]
    assert coverage["status"] == "ready"
    assert coverage["lag_days"] == 1
    assert "factor_screen_stale_vs_requested" not in {finding["code"] for finding in report["findings"]}


def test_health_report_falls_back_to_calendar_lag_when_trading_window_is_empty(tmp_path: Path) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_db(db_path)
    try:
        _seed_daily(conn, trade_date="2026-06-01")
        _seed_candidate(conn, snapshot_date="2026-06-18", code="000001.SZ")
        _create_factor_coverage_tables(conn)
        conn.executemany(
            "insert into choice_stock_factor_snapshot values (?, ?)",
            [("2026-06-12", "000001.SZ"), ("2026-06-12", "000002.SZ")],
        )
        conn.executemany(
            "insert into choice_stock_universe values (?, ?)",
            [("2026-06-12", "000001.SZ"), ("2026-06-12", "000002.SZ")],
        )
    finally:
        conn.close()

    report = module.build_stock_strategy_health_report(duckdb_path=db_path, as_of_date="2026-06-18")

    coverage = report["factor_screen_coverage"]
    assert coverage["status"] == "blocked"
    assert coverage["lag_days"] == 6
    assert "factor_screen_stale_vs_requested" in {finding["code"] for finding in report["findings"]}


def test_candidate_filter_findings_recommend_primary_zero_output_blocker() -> None:
    module = _load_module()
    diagnostic = {
        "status": "ready",
        "final_candidate_count": 0,
        "funnel": [
            {"step": "close_strength>=0.99", "before": 6, "pass": 1, "fail_at_step": 5},
            {"step": "abnormal_turnover_1.2_to_2.4", "before": 1, "pass": 0, "fail_at_step": 1},
        ],
        "near_misses": [
            {
                "stock_code": "600869.SH",
                "stock_name": "Turnover Near Miss",
                "fail_reasons": ["abnormal_turnover"],
            }
        ],
    }

    findings = module._candidate_filter_findings(diagnostic)
    actions = module._recommended_next_actions(findings, as_of_date="2026-06-12")

    assert findings[0]["code"] == "stock_candidate_filter_zero_output"
    assert findings[0]["primary_blocker"] == "abnormal_turnover_1.2_to_2.4"
    assert "600869.SH" in findings[0]["message"]
    assert any("abnormal_turnover" in action and "2026-06-12" in action for action in actions)


def test_shadow_candidate_filter_findings_track_shadow_without_promoting() -> None:
    module = _load_module()
    official = {
        "status": "ready",
        "selection_policy": "exp3b",
        "final_candidate_count": 0,
    }
    shadow = {
        "status": "ready",
        "selection_policy": "exp3c_shadow",
        "final_candidate_count": 1,
        "candidate_items": [{"stock_code": "600869.SH", "stock_name": "Shadow Only"}],
        "near_misses": [
            {
                "stock_code": "688388.SH",
                "stock_name": "Still Blocked",
                "fail_reasons": ["close_strength"],
            }
        ],
    }

    findings = module._shadow_candidate_filter_findings(official, shadow)
    actions = module._recommended_next_actions(findings, as_of_date="2026-06-12")

    assert findings[0]["code"] == "stock_candidate_shadow_policy_delta"
    assert findings[0]["official_candidate_count"] == 0
    assert findings[0]["shadow_candidate_count"] == 1
    assert "600869.SH" in findings[0]["message"]
    assert any("exp3c_shadow" in action and "shadow" in action for action in actions)


def test_health_report_cli_prints_json(tmp_path: Path, capsys) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    conn = _create_db(db_path)
    try:
        _seed_daily(conn, trade_date="2026-06-12")
        _seed_candidate(conn, snapshot_date="2026-06-12", code="000001.SZ")
    finally:
        conn.close()

    exit_code = module.main(["--duckdb-path", str(db_path), "--as-of-date", "2026-06-12"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert '"status"' in captured.out
    assert "stock_candidate" in captured.out
