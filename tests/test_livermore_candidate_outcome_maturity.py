from __future__ import annotations

import json

import duckdb
import pytest


def _seed_candidate_history(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table livermore_candidate_history (
          snapshot_as_of_date varchar,
          stock_code varchar,
          stock_name varchar,
          candidate_rank integer,
          selection_close double,
          forward_trade_date_1d varchar,
          forward_trade_date_5d varchar,
          forward_trade_date_10d varchar,
          forward_trade_date_20d varchar,
          return_1d double,
          return_5d double,
          return_10d double,
          return_20d double,
          return_1d_adj double,
          return_5d_adj double,
          return_10d_adj double,
          return_20d_adj double,
          ex_div_in_window boolean,
          data_status varchar,
          formula_version varchar,
          source_version varchar,
          vendor_version varchar,
          rule_version varchar,
          run_id varchar,
          signal_kind varchar,
          theme_key varchar,
          signal_evidence_json varchar
        )
        """
    )
    conn.execute(
        """
        insert into livermore_candidate_history values (
          '2026-01-01', '000001.SZ', 'Frozen candidate', 3, 100.0,
          '2026-01-02', null, null, null,
          0.777, null, null, null,
          0.888, null, null, null,
          null, 'pending', 'fv_signal', 'sv_signal', 'vv_signal', 'rv_signal', 'run_signal',
          'factor_screen', 'theme:frozen',
          '{"signal":{"why":"keep"},"adjustment_evidence":{"legacy":"keep","signal_adj_factor":9.0,"forward_adj_factors":{"20d":9.0},"adj_factor_missing_horizons":["20d"],"adj_factor_missing":true},"outcome_maturity":{"legacy":"keep"}}'
        )
        """
    )


def _seed_observations_and_factors(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar,
          stock_code varchar,
          close_value double,
          tradestatus varchar
        )
        """
    )
    conn.executemany(
        "insert into choice_stock_daily_observation values (?, '000001.SZ', ?, 'Trading')",
        [(f"2026-01-{day:02d}", 99.0 + day) for day in range(2, 22)],
    )
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
    conn.executemany(
        "insert into stock_adjustment_factor values ('000001.SZ', ?, 1.0, 'sv_adj', 'run_adj')",
        [("2026-01-01",), *( (f"2026-01-{day:02d}",) for day in range(2, 7) )],
    )


def test_outcome_maturity_only_fills_null_outcomes_up_to_evaluation_date_and_is_idempotent(tmp_path) -> None:
    from backend.app.tasks.livermore_candidate_outcome_maturity import (
        mature_livermore_candidate_outcomes,
    )

    db_path = tmp_path / "maturity.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_candidate_history(conn)
        _seed_observations_and_factors(conn)
        frozen_before = conn.execute(
            """
            select snapshot_as_of_date, stock_code, stock_name, candidate_rank, selection_close,
                   formula_version, source_version, vendor_version, rule_version, run_id,
                   signal_kind, theme_key
            from livermore_candidate_history
            """
        ).fetchone()
    finally:
        conn.close()

    first = mature_livermore_candidate_outcomes(
        str(db_path),
        evaluation_as_of_date="2026-01-06",
    )

    assert first["status"] == "completed"
    assert first["evaluation_as_of_date"] == "2026-01-06"
    assert first["updated_row_count"] == 1
    assert first["horizons"]["5d"]["counts"]["complete"] == 1
    assert first["horizons"]["20d"]["counts"]["natural_pending"] == 1

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        frozen_after = conn.execute(
            """
            select snapshot_as_of_date, stock_code, stock_name, candidate_rank, selection_close,
                   formula_version, source_version, vendor_version, rule_version, run_id,
                   signal_kind, theme_key
            from livermore_candidate_history
            """
        ).fetchone()
        outcome_after_first = conn.execute(
            """
            select forward_trade_date_1d, forward_trade_date_5d,
                   forward_trade_date_10d, forward_trade_date_20d,
                   return_1d, return_5d, return_10d, return_20d,
                   return_1d_adj, return_5d_adj, return_10d_adj, return_20d_adj,
                   ex_div_in_window, data_status, signal_evidence_json
            from livermore_candidate_history
            """
        ).fetchone()
    finally:
        conn.close()

    assert frozen_after == frozen_before
    assert outcome_after_first is not None
    assert outcome_after_first[:4] == ("2026-01-02", "2026-01-06", None, None)
    assert outcome_after_first[4] == pytest.approx(0.777)
    assert outcome_after_first[5] == pytest.approx(0.05)
    assert outcome_after_first[6:8] == (None, None)
    assert outcome_after_first[8] == pytest.approx(0.888)
    assert outcome_after_first[9] == pytest.approx(0.05)
    assert outcome_after_first[10:12] == (None, None)
    assert outcome_after_first[12] is None
    assert outcome_after_first[13] == "pending"
    evidence = json.loads(str(outcome_after_first[14]))
    assert evidence["signal"] == {"why": "keep"}
    assert evidence["adjustment_evidence"]["legacy"] == "keep"
    assert evidence["adjustment_evidence"]["signal_adj_factor"] == 9.0
    assert evidence["adjustment_evidence"]["forward_adj_factors"]["20d"] == 9.0
    assert evidence["adjustment_evidence"]["adj_factor_missing_horizons"] == ["20d"]
    assert evidence["adjustment_evidence"]["adj_factor_missing"] is True
    assert evidence["outcome_maturity"] == {"legacy": "keep"}
    assert len(evidence["outcome_maturity_audit"]) == 1
    first_audit = evidence["outcome_maturity_audit"][0]
    assert first_audit["evaluation_as_of_date"] == "2026-01-06"
    assert first_audit["current_adjustment_state"]["missing_horizons"] == []
    assert first_audit["current_adjustment_state"]["ex_div_complete"] is False

    second = mature_livermore_candidate_outcomes(
        str(db_path),
        evaluation_as_of_date="2026-01-06",
    )
    assert second["updated_row_count"] == 0

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        outcome_after_second = conn.execute(
            """
            select forward_trade_date_1d, forward_trade_date_5d,
                   forward_trade_date_10d, forward_trade_date_20d,
                   return_1d, return_5d, return_10d, return_20d,
                   return_1d_adj, return_5d_adj, return_10d_adj, return_20d_adj,
                   ex_div_in_window, data_status, signal_evidence_json
            from livermore_candidate_history
            """
        ).fetchone()
    finally:
        conn.close()
    assert outcome_after_second == outcome_after_first

    third = mature_livermore_candidate_outcomes(
        str(db_path),
        evaluation_as_of_date="2026-01-11",
    )
    assert third["updated_row_count"] == 1
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        evidence_after_third = json.loads(
            str(
                conn.execute(
                    "select signal_evidence_json from livermore_candidate_history"
                ).fetchone()[0]
            )
        )
    finally:
        conn.close()
    assert evidence_after_third["outcome_maturity"] == {"legacy": "keep"}
    assert evidence_after_third["adjustment_evidence"]["adj_factor_missing_horizons"] == ["20d"]
    assert evidence_after_third["adjustment_evidence"]["adj_factor_missing"] is True
    audits = evidence_after_third["outcome_maturity_audit"]
    assert [item["evaluation_as_of_date"] for item in audits] == ["2026-01-06", "2026-01-11"]
    assert audits[0] == first_audit
    assert audits[-1]["current_adjustment_state"]["missing_horizons"] == ["10d"]

    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.executemany(
            "insert into stock_adjustment_factor values ('000001.SZ', ?, 1.0, 'sv_adj_complete', 'run_adj_complete')",
            [(f"2026-01-{day:02d}",) for day in range(7, 22)],
        )
    finally:
        conn.close()
    fourth = mature_livermore_candidate_outcomes(
        str(db_path),
        evaluation_as_of_date="2026-01-21",
    )
    assert fourth["status"] == "completed"
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        ex_div, evidence_text = conn.execute(
            "select ex_div_in_window, signal_evidence_json from livermore_candidate_history"
        ).fetchone()
    finally:
        conn.close()
    evidence_after_fourth = json.loads(str(evidence_text))
    assert evidence_after_fourth["adjustment_evidence"] == evidence["adjustment_evidence"]
    latest_adjustment_state = evidence_after_fourth["outcome_maturity_audit"][-1][
        "current_adjustment_state"
    ]
    assert latest_adjustment_state["missing_horizons"] == []
    assert latest_adjustment_state["adjusted_return_complete_horizons"] == [
        "1d",
        "5d",
        "10d",
        "20d",
    ]
    assert latest_adjustment_state["ex_div_complete"] is True
    assert latest_adjustment_state["ex_div_in_window"] is False
    assert ex_div is False


def test_outcome_maturity_promotes_legacy_pending_only_after_every_horizon_completes(tmp_path) -> None:
    from backend.app.tasks.livermore_candidate_outcome_maturity import (
        mature_livermore_candidate_outcomes,
    )

    db_path = tmp_path / "maturity-complete.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_candidate_history(conn)
        _seed_observations_and_factors(conn)
        conn.executemany(
            "insert into stock_adjustment_factor values ('000001.SZ', ?, 1.0, 'sv_adj', 'run_adj')",
            [(f"2026-01-{day:02d}",) for day in range(7, 22)],
        )
    finally:
        conn.close()

    result = mature_livermore_candidate_outcomes(
        str(db_path),
        evaluation_as_of_date="2026-01-21",
    )

    assert result["horizons"]["20d"]["counts"]["complete"] == 1
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute(
            """
            select data_status, return_20d, return_20d_adj, ex_div_in_window
            from livermore_candidate_history
            """
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row[0] == "complete"
    assert row[1] == pytest.approx(0.2)
    assert row[2] == pytest.approx(0.2)
    assert row[3] is False


def test_outcome_maturity_marks_ex_div_true_after_a_factor_change_is_observed(tmp_path) -> None:
    from backend.app.tasks.livermore_candidate_outcome_maturity import (
        mature_livermore_candidate_outcomes,
    )

    db_path = tmp_path / "maturity-ex-div.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_candidate_history(conn)
        _seed_observations_and_factors(conn)
        conn.executemany(
            "insert into stock_adjustment_factor values ('000001.SZ', ?, ?, 'sv_adj', 'run_adj')",
            [
                (f"2026-01-{day:02d}", 1.0 if day < 12 else 1.2)
                for day in range(7, 22)
            ],
        )
    finally:
        conn.close()

    mature_livermore_candidate_outcomes(
        str(db_path),
        evaluation_as_of_date="2026-01-21",
    )

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        ex_div_in_window = conn.execute(
            "select ex_div_in_window from livermore_candidate_history"
        ).fetchone()[0]
    finally:
        conn.close()
    assert ex_div_in_window is True


@pytest.mark.parametrize(
    ("evidence_json", "issue_suffix"),
    [
        ("not-json", "invalid_signal_evidence_json"),
        ('{"outcome_maturity_audit":{"bad":true}}', "invalid_outcome_maturity_audit"),
    ],
)
def test_outcome_maturity_blocks_all_row_updates_when_evidence_is_unsafe(
    tmp_path,
    evidence_json: str,
    issue_suffix: str,
) -> None:
    from backend.app.tasks.livermore_candidate_outcome_maturity import (
        mature_livermore_candidate_outcomes,
    )

    db_path = tmp_path / f"maturity-blocked-{issue_suffix}.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_candidate_history(conn)
        _seed_observations_and_factors(conn)
        conn.execute(
            "update livermore_candidate_history set signal_evidence_json = ?",
            [evidence_json],
        )
        before = conn.execute("select * from livermore_candidate_history").fetchone()
        row_id = conn.execute("select rowid from livermore_candidate_history").fetchone()[0]
    finally:
        conn.close()

    result = mature_livermore_candidate_outcomes(
        str(db_path),
        evaluation_as_of_date="2026-01-06",
    )

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        after = conn.execute("select * from livermore_candidate_history").fetchone()
    finally:
        conn.close()
    assert after == before
    assert result["status"] == "partial"
    assert result["updated_row_count"] == 0
    assert result["blocked_row_count"] == 1
    assert result["blocked_rows"] == [
        {
            "rowid": row_id,
            "issue": f"2026-01-01:000001.SZ:{issue_suffix}",
        }
    ]


def test_outcome_maturity_lineage_lists_only_tables_that_exist(tmp_path) -> None:
    from backend.app.tasks.livermore_candidate_outcome_maturity import (
        mature_livermore_candidate_outcomes,
    )

    db_path = tmp_path / "maturity-no-adjustment-table.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_candidate_history(conn)
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              close_value double,
              tradestatus varchar
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, '000001.SZ', ?, 'Trading')",
            [(f"2026-01-{day:02d}", 99.0 + day) for day in range(2, 7)],
        )
    finally:
        conn.close()

    result = mature_livermore_candidate_outcomes(
        str(db_path),
        evaluation_as_of_date="2026-01-06",
    )
    assert result["horizons"]["5d"]["counts"]["raw_matured_adjustment_missing"] == 1

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        evidence_json = conn.execute(
            "select signal_evidence_json from livermore_candidate_history"
        ).fetchone()
    finally:
        conn.close()
    assert evidence_json is not None
    maturity = json.loads(str(evidence_json[0]))["outcome_maturity_audit"][0]
    assert maturity["source_tables"] == {
        "actual_used": [
            "livermore_candidate_history",
            "choice_stock_daily_observation",
        ],
        "table_present": [
            "livermore_candidate_history",
            "choice_stock_daily_observation",
        ],
    }


def test_outcome_maturity_records_actual_mixed_version_lineage_and_hash(tmp_path) -> None:
    from backend.app.tasks.livermore_candidate_outcome_maturity import (
        mature_livermore_candidate_outcomes,
    )

    db_path = tmp_path / "maturity-lineage.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_candidate_history(conn)
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              close_value double,
              tradestatus varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, '000001.SZ', ?, 'Trading', ?, ?, ?, ?)",
            [
                ("2026-01-02", 101.0, "sv_obs_a", "vv_obs_a", "rv_obs", "run_obs_a"),
                ("2026-01-03", 102.0, "sv_obs_a", "vv_obs_a", "rv_obs", "run_obs_a"),
                ("2026-01-04", 103.0, "sv_obs_a", "vv_obs_a", "rv_obs", "run_obs_a"),
                ("2026-01-05", 104.0, "sv_obs_a", "vv_obs_a", "rv_obs", "run_obs_a"),
                ("2026-01-06", 105.0, "sv_obs_b", "vv_obs_b", "rv_obs", "run_obs_b"),
            ],
        )
        conn.execute(
            """
            create table stock_adjustment_factor (
              stock_code varchar,
              trade_date varchar,
              adj_factor double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.executemany(
            "insert into stock_adjustment_factor values ('000001.SZ', ?, 1.0, ?, ?, ?, ?)",
            [
                ("2026-01-01", "sv_factor_signal", "vv_factor", "rv_factor", "run_factor_signal"),
                ("2026-01-02", "sv_factor_1d", "vv_factor", "rv_factor", "run_factor_1d"),
                ("2026-01-06", "sv_factor_5d", "vv_factor", "rv_factor", "run_factor_5d"),
            ],
        )
    finally:
        conn.close()

    mature_livermore_candidate_outcomes(
        str(db_path),
        evaluation_as_of_date="2026-01-06",
    )

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        evidence_text = conn.execute(
            "select signal_evidence_json from livermore_candidate_history"
        ).fetchone()[0]
    finally:
        conn.close()
    audit = json.loads(str(evidence_text))["outcome_maturity_audit"][-1]
    assert audit["source_tables"] == {
        "actual_used": [
            "livermore_candidate_history",
            "choice_stock_daily_observation",
            "stock_adjustment_factor",
        ],
        "table_present": [
            "livermore_candidate_history",
            "choice_stock_daily_observation",
            "stock_adjustment_factor",
        ],
    }
    actual_used = audit["lineage"]["actual_used"]
    assert actual_used["target_observations"]["1d"] == {
        "source_version": "sv_obs_a",
        "vendor_version": "vv_obs_a",
        "rule_version": "rv_obs",
        "run_id": "run_obs_a",
    }
    assert actual_used["target_observations"]["5d"] == {
        "source_version": "sv_obs_b",
        "vendor_version": "vv_obs_b",
        "rule_version": "rv_obs",
        "run_id": "run_obs_b",
    }
    assert actual_used["adjustment_factors"]["signal"] == {
        "source_version": "sv_factor_signal",
        "vendor_version": "vv_factor",
        "rule_version": "rv_factor",
        "run_id": "run_factor_signal",
    }
    assert actual_used["adjustment_factors"]["targets"]["5d"] == {
        "source_version": "sv_factor_5d",
        "vendor_version": "vv_factor",
        "rule_version": "rv_factor",
        "run_id": "run_factor_5d",
    }
    assert audit["lineage"]["version_sets"] == {
        "source_version": [
            "sv_factor_1d",
            "sv_factor_5d",
            "sv_factor_signal",
            "sv_obs_a",
            "sv_obs_b",
        ],
        "vendor_version": ["vv_factor", "vv_obs_a", "vv_obs_b"],
        "rule_version": ["rv_factor", "rv_obs"],
        "run_id": [
            "run_factor_1d",
            "run_factor_5d",
            "run_factor_signal",
            "run_obs_a",
            "run_obs_b",
        ],
    }
    assert len(audit["lineage"]["lineage_hash"]) == 64


def test_candidate_history_api_reports_maturity_per_horizon_with_two_clock_diagnostics(tmp_path) -> None:
    from backend.app.services.livermore_candidate_history_service import (
        livermore_candidate_history_envelope,
    )

    db_path = tmp_path / "maturity-api.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar,
              candidate_rank integer,
              selection_close double,
              forward_trade_date_5d varchar,
              return_5d double,
              return_5d_adj double,
              data_status varchar,
              source_version varchar,
              vendor_version varchar,
              signal_evidence_json varchar
            )
            """
        )
        conn.executemany(
            "insert into livermore_candidate_history values (?, ?, ?, 100.0, ?, ?, ?, 'pending', 'sv', 'vv', '{}')",
            [
                ("2026-01-01", "000001.SZ", 1, "2026-01-06", 0.05, 0.05),
                ("2026-01-01", "000002.SZ", 2, "2026-01-06", 0.04, None),
                ("2026-01-01", "000003.SZ", 3, None, None, None),
                ("2026-01-01", "000004.SZ", 4, None, None, None),
            ],
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              close_value double,
              tradestatus varchar
            )
            """
        )
        rows: list[tuple[str, str, float | None, str]] = []
        for stock_code in ("000001.SZ", "000002.SZ"):
            rows.extend(
                (f"2026-01-{day:02d}", stock_code, 99.0 + day, "Trading")
                for day in range(2, 7)
            )
        rows.append(("2026-01-02", "000003.SZ", 101.0, "Trading"))
        rows.extend(
            (f"2026-01-{day:02d}", "000003.SZ", None, "Suspended")
            for day in range(3, 7)
        )
        conn.executemany("insert into choice_stock_daily_observation values (?, ?, ?, ?)", rows)
    finally:
        conn.close()

    envelope = livermore_candidate_history_envelope(
        duckdb_path=str(db_path),
        stock_code=None,
        snapshot_from="2026-01-01",
        snapshot_to="2026-01-10",
        limit=10,
        evaluation_as_of_date="2026-01-06",
    )

    assert envelope["result_meta"]["cache_version"] == "cv_livermore_candidate_history_v2"
    result = envelope["result"]
    assert result["evaluation_as_of_date"] == "2026-01-06"
    items = {item["stock_code"]: item for item in result["items"]}
    assert items["000001.SZ"]["forward_maturity"]["horizons"]["5d"]["status"] == "complete"
    assert (
        items["000002.SZ"]["forward_maturity"]["horizons"]["5d"]["status"]
        == "raw_matured_adjustment_missing"
    )
    assert items["000003.SZ"]["forward_maturity"]["horizons"]["5d"]["status"] == "partial_halt"
    assert items["000004.SZ"]["forward_maturity"]["horizons"]["5d"]["status"] == "matured_missing_bar"
    assert all(
        item["forward_maturity"]["horizons"]["20d"]["status"] == "natural_pending"
        for item in items.values()
    )

    maturity_summary = result["summary"]["forward_maturity"]
    assert maturity_summary["evaluation_as_of_date"] == "2026-01-06"
    assert maturity_summary["horizons"]["5d"]["counts"] == {
        "natural_pending": 0,
        "complete": 1,
        "matured_missing_bar": 1,
        "raw_matured_adjustment_missing": 1,
        "partial_halt": 1,
    }
    assert maturity_summary["horizons"]["5d"]["latest_mature_snapshot_date"] == "2026-01-01"
    assert maturity_summary["horizons"]["20d"]["latest_pending_snapshot_date"] == "2026-01-01"

    limited = livermore_candidate_history_envelope(
        duckdb_path=str(db_path),
        stock_code=None,
        snapshot_from="2026-01-01",
        snapshot_to="2026-01-01",
        limit=2,
        evaluation_as_of_date="2026-01-06",
    )["result"]["summary"]["forward_maturity"]
    assert limited["scope"] == "returned_slice"
    assert limited["row_count"] == 2
    assert limited["horizons"]["5d"]["counts"]["matured_missing_bar"] == 0
    assert limited["all_filtered"]["scope"] == "all_filtered"
    assert limited["all_filtered"]["row_count"] == 4
    assert limited["all_filtered"]["horizons"]["5d"]["counts"] == {
        "natural_pending": 0,
        "complete": 1,
        "matured_missing_bar": 1,
        "raw_matured_adjustment_missing": 1,
        "partial_halt": 1,
    }


def test_outcome_maturity_does_not_compute_from_a_conflicting_stored_target_date(tmp_path) -> None:
    from backend.app.tasks.livermore_candidate_outcome_maturity import (
        mature_livermore_candidate_outcomes,
    )

    db_path = tmp_path / "maturity-conflicting-target.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_candidate_history(conn)
        _seed_observations_and_factors(conn)
        conn.execute(
            """
            update livermore_candidate_history
            set forward_trade_date_5d = '2026-01-05'
            """
        )
    finally:
        conn.close()

    result = mature_livermore_candidate_outcomes(
        str(db_path),
        evaluation_as_of_date="2026-01-06",
    )

    assert result["horizons"]["5d"]["counts"]["matured_missing_bar"] == 1
    assert "2026-01-01:000001.SZ:5d:stored_target_conflict" in result["issues"]
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute(
            """
            select forward_trade_date_5d, return_5d, return_5d_adj
            from livermore_candidate_history
            """
        ).fetchone()
    finally:
        conn.close()
    assert row == ("2026-01-05", None, None)


def test_outcome_maturity_updates_duplicate_candidate_identities_by_physical_row(tmp_path) -> None:
    from backend.app.tasks.livermore_candidate_outcome_maturity import (
        mature_livermore_candidate_outcomes,
    )

    db_path = tmp_path / "maturity-duplicate-identities.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_candidate_history(conn)
        _seed_observations_and_factors(conn)
        conn.execute("insert into livermore_candidate_history select * from livermore_candidate_history")
        conn.execute(
            """
            update livermore_candidate_history
            set forward_trade_date_5d = '2026-01-06', return_5d = 0.999, return_5d_adj = 0.999
            where rowid = (select max(rowid) from livermore_candidate_history)
            """
        )
    finally:
        conn.close()

    mature_livermore_candidate_outcomes(
        str(db_path),
        evaluation_as_of_date="2026-01-06",
    )

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select snapshot_as_of_date, stock_code, signal_kind, candidate_rank,
                   forward_trade_date_5d, return_5d, return_5d_adj
            from livermore_candidate_history
            order by return_5d
            """
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 2
    assert rows[0][:4] == rows[1][:4]
    assert rows[0][4] == rows[1][4] == "2026-01-06"
    assert rows[0][5:] == pytest.approx((0.05, 0.05))
    assert rows[1][5:] == pytest.approx((0.999, 0.999))


def test_outcome_maturity_loads_only_candidate_windows_and_required_factor_keys(tmp_path) -> None:
    from backend.app.tasks.livermore_candidate_outcome_maturity import (
        mature_livermore_candidate_outcomes,
    )

    db_path = tmp_path / "maturity-bounded-load.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_candidate_history(conn)
        _seed_observations_and_factors(conn)
        conn.execute("insert into livermore_candidate_history select * from livermore_candidate_history")
        conn.executemany(
            "insert into stock_adjustment_factor values ('000001.SZ', ?, 1.0, 'sv_adj', 'run_adj')",
            [(f"2026-01-{day:02d}",) for day in range(7, 22)],
        )
        unrelated_observations = [
            (f"U{stock_index:05d}.SZ", f"2026-01-{day:02d}", 20.0 + day)
            for stock_index in range(200)
            for day in range(2, 22)
        ]
        conn.executemany(
            """
            insert into choice_stock_daily_observation
            (stock_code, trade_date, close_value, tradestatus)
            values (?, ?, ?, 'Trading')
            """,
            unrelated_observations,
        )
        conn.executemany(
            "insert into stock_adjustment_factor values (?, ?, 1.0, 'sv_unrelated', 'run_unrelated')",
            [(stock_code, trade_date) for stock_code, trade_date, _ in unrelated_observations],
        )
    finally:
        conn.close()

    result = mature_livermore_candidate_outcomes(
        str(db_path),
        evaluation_as_of_date="2026-01-21",
    )

    assert result["candidate_row_count"] == 2
    assert result["loaded_observation_row_count"] == 40
    assert result["requested_factor_key_count"] == 5
    assert result["loaded_factor_row_count"] == 5
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select rowid, forward_trade_date_20d, return_20d_adj
            from livermore_candidate_history
            order by rowid
            """
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 2
    assert [row[1] for row in rows] == ["2026-01-21", "2026-01-21"]
    assert [row[2] for row in rows] == pytest.approx([0.2, 0.2])


def test_historical_evaluation_masks_future_outcomes_before_legacy_and_horizon_summaries(tmp_path) -> None:
    from backend.app.services.livermore_candidate_history_service import (
        livermore_candidate_history_envelope,
    )

    db_path = tmp_path / "maturity-cutoff-mask.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar,
              candidate_rank integer,
              selection_close double,
              forward_trade_date_1d varchar,
              forward_trade_date_5d varchar,
              return_1d double,
              return_5d double,
              return_1d_adj double,
              return_5d_adj double,
              data_status varchar,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into livermore_candidate_history values (
              '2026-01-01', '000001.SZ', 1, 100.0,
              '2026-01-02', '2026-01-10',
              0.01, 0.50, 0.01, 0.50,
              'complete', 'sv', 'vv'
            )
            """
        )
        conn.execute(
            """
            insert into livermore_candidate_history values (
              '2026-01-06', '000002.SZ', 2, 100.0,
              null, null, null, null, null, null,
              'pending', 'sv', 'vv'
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              close_value double,
              tradestatus varchar
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, '000001.SZ', ?, 'Trading')",
            [
                ("2026-01-02", 101.0),
                ("2026-01-03", 102.0),
                ("2026-01-04", 103.0),
                ("2026-01-05", 104.0),
                ("2026-01-10", 150.0),
            ],
        )
    finally:
        conn.close()

    envelope = livermore_candidate_history_envelope(
        duckdb_path=str(db_path),
        stock_code=None,
        snapshot_from="2026-01-01",
        snapshot_to="2026-01-10",
        limit=10,
        evaluation_as_of_date="2026-01-05",
    )

    result = envelope["result"]
    assert result["snapshot_to"] == "2026-01-10"
    assert result["effective_snapshot_to"] == "2026-01-05"
    assert len(result["items"]) == 1
    assert result["summary"]["forward_maturity"]["all_filtered"]["row_count"] == 1
    assert result["backtest_window_summary"]["snapshot_to"] == "2026-01-05"
    item = result["items"][0]
    assert item["forward_trade_date_1d"] == "2026-01-02"
    assert item["return_1d"] == pytest.approx(0.01)
    assert item["forward_trade_date_5d"] is None
    assert item["return_5d"] is None
    assert item["return_5d_adj"] is None
    assert item["forward_maturity"]["horizons"]["5d"]["status"] == "natural_pending"
    assert item["data_status"] == "pending"
    assert item["forward_coverage"] == "pending"

    summary = result["summary"]
    assert summary["complete_count"] == 0
    assert summary["pending_count"] == 1
    assert summary["avg_return_5d"] is None
    assert summary["horizon_stats"]["return_5d"]["available_count"] == 0
    assert result["backtest_window_summary"]["forward_coverage_row_counts"] == {
        "complete": 0,
        "pending": 1,
        "missing_bar": 0,
        "partial_halt": 0,
    }


def test_candidate_history_service_fail_closes_malformed_stored_dates_without_crashing(tmp_path) -> None:
    from backend.app.services.livermore_candidate_history_service import (
        livermore_candidate_history_envelope,
    )

    db_path = tmp_path / "maturity-malformed-dates.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar,
              candidate_rank integer,
              forward_trade_date_1d varchar,
              return_1d double,
              return_1d_adj double,
              data_status varchar,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into livermore_candidate_history values
            ('not-a-date', '000001.SZ', 1, 'also-not-a-date', 0.5, 0.5, 'complete', 'sv', 'vv')
            """
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              close_value double
            )
            """
        )
    finally:
        conn.close()

    envelope = livermore_candidate_history_envelope(
        duckdb_path=str(db_path),
        stock_code=None,
        snapshot_from=None,
        snapshot_to=None,
        limit=10,
        evaluation_as_of_date="2026-01-05",
    )

    assert envelope["result"]["items"] == []
    assert envelope["result"]["summary"]["forward_maturity"]["all_filtered"]["row_count"] == 0


def test_candidate_history_service_masks_nonfinite_stored_returns_even_when_target_is_verified(tmp_path) -> None:
    from backend.app.services.livermore_candidate_history_service import (
        livermore_candidate_history_envelope,
    )

    db_path = tmp_path / "maturity-nonfinite.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar,
              candidate_rank integer,
              forward_trade_date_1d varchar,
              return_1d double,
              return_1d_adj double,
              data_status varchar,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.executemany(
            "insert into livermore_candidate_history values (?, ?, ?, ?, ?, ?, 'complete', 'sv', 'vv')",
            [
                ("2026-01-01", "000001.SZ", 1, "2026-01-02", float("inf"), float("nan")),
                ("2026-01-01", "000002.SZ", 2, "2026-01-02", 0.01, float("inf")),
            ],
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              close_value double,
              tradestatus varchar
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values ('2026-01-02', ?, 101.0, 'Trading')",
            [("000001.SZ",), ("000002.SZ",)],
        )
    finally:
        conn.close()

    result = livermore_candidate_history_envelope(
        duckdb_path=str(db_path),
        stock_code=None,
        snapshot_from="2026-01-01",
        snapshot_to="2026-01-02",
        limit=10,
        evaluation_as_of_date="2026-01-02",
    )["result"]

    items = {item["stock_code"]: item for item in result["items"]}
    assert items["000001.SZ"]["return_1d"] is None
    assert items["000001.SZ"]["return_1d_adj"] is None
    assert items["000001.SZ"]["forward_maturity"]["horizons"]["1d"]["status"] == "matured_missing_bar"
    assert items["000002.SZ"]["return_1d"] == pytest.approx(0.01)
    assert items["000002.SZ"]["return_1d_adj"] is None
    assert (
        items["000002.SZ"]["forward_maturity"]["horizons"]["1d"]["status"]
        == "raw_matured_adjustment_missing"
    )


@pytest.mark.parametrize("observation_schema", [None, "trade_date varchar, stock_code varchar"])
def test_candidate_history_service_fail_closes_when_observation_source_is_unavailable(
    tmp_path,
    observation_schema: str | None,
) -> None:
    from backend.app.services.livermore_candidate_history_service import (
        livermore_candidate_history_envelope,
    )

    db_path = tmp_path / "maturity-source-unavailable.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar,
              candidate_rank integer,
              forward_trade_date_1d varchar,
              return_1d double,
              return_1d_adj double,
              data_status varchar,
              source_version varchar,
              vendor_version varchar
            )
            """
        )
        conn.execute(
            """
            insert into livermore_candidate_history values
            ('2026-01-01', '000001.SZ', 1, '2026-01-02', 0.01, 0.01, 'complete', 'sv', 'vv')
            """
        )
        if observation_schema is not None:
            conn.execute(f"create table choice_stock_daily_observation ({observation_schema})")
    finally:
        conn.close()

    envelope = livermore_candidate_history_envelope(
        duckdb_path=str(db_path),
        stock_code=None,
        snapshot_from="2026-01-01",
        snapshot_to="2026-01-05",
        limit=10,
        evaluation_as_of_date="2026-01-05",
    )

    assert envelope["result_meta"]["quality_flag"] == "warning"
    result = envelope["result"]
    item_maturity = result["items"][0]["forward_maturity"]
    assert item_maturity["source_status"] == "unavailable"
    assert item_maturity["classification_available"] is False
    assert all(
        horizon["status"] == "matured_missing_bar"
        and horizon["reason"] == "observation_source_unavailable"
        for horizon in item_maturity["horizons"].values()
    )
    returned_maturity = result["summary"]["forward_maturity"]
    assert returned_maturity["source_status"] == "unavailable"
    assert returned_maturity["classification_available"] is False
    assert returned_maturity["counts_authoritative"] is False
    assert returned_maturity["horizons"]["1d"]["counts_authoritative"] is False
    assert returned_maturity["horizons"]["1d"]["counts"]["natural_pending"] == 0
    assert returned_maturity["horizons"]["1d"]["counts"]["matured_missing_bar"] == 1
    all_filtered = returned_maturity["all_filtered"]
    assert all_filtered["source_status"] == "unavailable"
    assert all_filtered["classification_available"] is False
    assert all_filtered["counts_authoritative"] is False
    assert all_filtered["horizons"]["1d"]["counts_authoritative"] is False
    assert all_filtered["horizons"]["1d"]["counts"]["natural_pending"] == 0
    assert all_filtered["horizons"]["1d"]["counts"]["matured_missing_bar"] == 1


@pytest.mark.parametrize("trade_status", ["Trading", "交易", "正常交易"])
def test_livermore_maturity_accepts_supported_trading_statuses(trade_status: str) -> None:
    from backend.app.services.livermore_candidate_history_service import (
        _maturity_is_trading_status,
    )
    from backend.app.tasks.livermore_candidate_outcome_maturity import _is_trading_status

    assert _is_trading_status(trade_status)
    assert _maturity_is_trading_status(trade_status)


def test_duplicate_observation_revisions_use_latest_row_consistently_across_maturity_views(
    tmp_path,
) -> None:
    from backend.app.services.livermore_candidate_history_service import (
        livermore_candidate_history_envelope,
    )
    from backend.app.tasks.livermore_candidate_outcome_maturity import (
        mature_livermore_candidate_outcomes,
    )

    db_path = tmp_path / "maturity-observation-revisions.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_candidate_history(conn)
        conn.execute(
            """
            update livermore_candidate_history
            set return_1d = 0.01, return_1d_adj = 0.01
            """
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              close_value double,
              tradestatus varchar
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?)",
            [
                ("2026-01-02", "000001.SZ", 101.0, "Trading"),
                ("2026-01-02", "000001.SZ", None, "Suspended"),
                ("2026-01-02", "000999.SZ", 10.0, "Trading"),
            ],
        )
    finally:
        conn.close()

    task_result = mature_livermore_candidate_outcomes(
        str(db_path),
        evaluation_as_of_date="2026-01-02",
    )
    assert task_result["horizons"]["1d"]["counts"]["partial_halt"] == 1
    assert task_result["horizons"]["1d"]["counts"]["complete"] == 0

    result = livermore_candidate_history_envelope(
        duckdb_path=str(db_path),
        stock_code="000001.SZ",
        snapshot_from="2026-01-01",
        snapshot_to="2026-01-02",
        limit=10,
        evaluation_as_of_date="2026-01-02",
    )["result"]

    returned = result["items"][0]["forward_maturity"]["horizons"]["1d"]
    assert returned["status"] == "partial_halt"
    assert returned["target_observation_verified"] is False
    assert result["items"][0]["forward_trade_date_1d"] is None
    all_filtered = result["summary"]["forward_maturity"]["all_filtered"]
    assert all_filtered["counts_authoritative"] is True
    assert all_filtered["horizons"]["1d"]["counts"]["partial_halt"] == 1
    assert all_filtered["horizons"]["1d"]["counts"]["complete"] == 0
