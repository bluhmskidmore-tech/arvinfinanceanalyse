from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

import backend.app.tasks.livermore_candidate_history_materialize as materialize_task
from tests.helpers import load_module


def test_execution_gap_repair_exposes_a_public_task_entrypoint() -> None:
    repair = getattr(materialize_task, "repair_livermore_candidate_execution_gaps", None)

    assert callable(repair), "expected a public execution-gap repair task entrypoint"


def _seed_execution_database(db_path: Path) -> None:
    signal_date = date(2026, 1, 5)
    stocks = (
        ("000001.SZ", "Raw Gap", "stock_candidate", "fv_livermore_candidate_execution_dual_adjust_v4"),
        ("000002.SZ", "Pending", "stock_candidate", "fv_livermore_candidate_execution_dual_adjust_v4"),
        ("000003.SZ", "Stale Formula", "stock_candidate", "fv_livermore_candidate_forward_close_dual_adjust_v2"),
        ("000004.SZ", "Untouched Theme", "theme_breakout", "fv_livermore_candidate_forward_close_dual_adjust_v2"),
        ("000005.SZ", "Healthy", "stock_candidate", "fv_livermore_candidate_execution_dual_adjust_v4"),
    )
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              open_value double,
              close_value double,
              tradestatus varchar,
              highlimit double,
              lowlimit double
            )
            """
        )
        materialize_task.ensure_livermore_candidate_history_schema(conn)
        observation_rows: list[tuple[object, ...]] = []
        factor_rows: list[tuple[object, ...]] = []
        for stock_index, (stock_code, _name, _kind, _formula) in enumerate(stocks):
            base_price = 100.0 + stock_index * 10.0
            for offset in range(21):
                trade_date = (signal_date + timedelta(days=offset)).isoformat()
                price = base_price + offset
                observation_rows.append(
                    (trade_date, stock_code, price, price, "trading", price + 20.0, price - 20.0)
                )
                factor_rows.append((stock_code, trade_date, 1.0, "sv-test", "factor-run"))
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?)",
            observation_rows,
        )
        conn.executemany(
            """
            insert into stock_adjustment_factor
            (stock_code, trade_date, adj_factor, source_version, run_id)
            values (?, ?, ?, ?, ?)
            """,
            factor_rows,
        )

        execution_rows: list[dict[str, object]] = []
        for rank, (stock_code, stock_name, signal_kind, formula_version) in enumerate(stocks, start=1):
            computed = materialize_task._execution_returns_for_candidate(
                conn,
                stock_code=stock_code,
                snapshot_as_of_date=signal_date.isoformat(),
            )
            assert computed is not None
            row = {
                "signal_date": signal_date.isoformat(),
                "stock_code": stock_code,
                "stock_name": stock_name,
                "signal_kind": signal_kind,
                "candidate_rank": rank,
                "market_state": "HOT",
                **computed,
                "formula_version": formula_version,
                "run_id": f"original-{stock_code}",
            }
            if stock_code == "000001.SZ":
                row["return_20d_gross"] = None
                row["return_20d_net_adj"] = None
            elif stock_code == "000002.SZ":
                row["data_status"] = "pending"
            execution_rows.append(row)
        materialize_task._insert_execution_history_rows(conn, execution_rows)
        duplicate = dict(execution_rows[2])
        duplicate["run_id"] = "duplicate-stale-formula"
        materialize_task._insert_execution_history_rows(conn, [duplicate])
    finally:
        conn.close()


def _execution_rows(db_path: Path) -> list[tuple[object, ...]]:
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        return conn.execute(
            """
            select signal_date, stock_code, signal_kind, data_status, formula_version, run_id,
                   return_20d_net, return_20d_net_adj
            from livermore_candidate_execution_history
            order by stock_code, signal_kind, run_id
            """
        ).fetchall()
    finally:
        conn.close()


def test_execution_gap_repair_dry_run_is_read_only_and_previews_exact_union(tmp_path: Path) -> None:
    db_path = tmp_path / "execution-gaps.duckdb"
    _seed_execution_database(db_path)
    rows_before = _execution_rows(db_path)
    hash_before = hashlib.sha256(db_path.read_bytes()).hexdigest()

    result = materialize_task.repair_livermore_candidate_execution_gaps(
        str(db_path),
        dry_run=True,
    )

    assert result["status"] == "ok"
    assert result["mode"] == "dry_run"
    assert result["target_count"] == 3
    assert result["target_keys"] == [
        {"signal_date": "2026-01-05", "stock_code": "000001.SZ", "signal_kind": "stock_candidate"},
        {"signal_date": "2026-01-05", "stock_code": "000002.SZ", "signal_kind": "stock_candidate"},
        {"signal_date": "2026-01-05", "stock_code": "000003.SZ", "signal_kind": "stock_candidate"},
    ]
    targets = {target["key"]["stock_code"]: target for target in result["targets"]}
    assert targets["000001.SZ"]["reasons"] == ["raw_20d_without_adjusted_20d"]
    assert targets["000001.SZ"]["preview"]["return_20d_net_adj"] is not None
    assert targets["000002.SZ"]["reasons"] == ["pending_recomputes_complete"]
    assert targets["000002.SZ"]["preview"]["data_status"] == "complete"
    assert targets["000003.SZ"]["reasons"] == ["formula_version_stale"]
    assert targets["000003.SZ"]["preview"]["formula_version"] == materialize_task.EXECUTION_FORMULA_VERSION
    assert _execution_rows(db_path) == rows_before
    assert hashlib.sha256(db_path.read_bytes()).hexdigest() == hash_before


def test_execution_gap_repair_rejects_non_stock_candidate_signal_kind(tmp_path: Path) -> None:
    db_path = tmp_path / "execution-gaps.duckdb"
    _seed_execution_database(db_path)

    with pytest.raises(ValueError, match="stock_candidate"):
        materialize_task.repair_livermore_candidate_execution_gaps(
            str(db_path),
            dry_run=True,
            signal_kind="theme_breakout",
        )


def test_execution_gap_repair_live_requires_a_distinct_matching_backup(tmp_path: Path) -> None:
    db_path = tmp_path / "execution-gaps.duckdb"
    _seed_execution_database(db_path)
    rows_before = _execution_rows(db_path)
    hash_before = hashlib.sha256(db_path.read_bytes()).hexdigest()

    with pytest.raises(ValueError, match="target_backup_path"):
        materialize_task.repair_livermore_candidate_execution_gaps(
            str(db_path),
            dry_run=False,
        )
    with pytest.raises(ValueError, match="different"):
        materialize_task.repair_livermore_candidate_execution_gaps(
            str(db_path),
            dry_run=False,
            target_backup_path=str(db_path),
        )
    with pytest.raises(FileNotFoundError, match="Backup"):
        materialize_task.repair_livermore_candidate_execution_gaps(
            str(db_path),
            dry_run=False,
            target_backup_path=str(tmp_path / "missing-backup.duckdb"),
        )

    mismatched_backup = tmp_path / "mismatched-backup.duckdb"
    mismatched_backup.write_bytes(b"not the target database")
    with pytest.raises(ValueError, match="content hash"):
        materialize_task.repair_livermore_candidate_execution_gaps(
            str(db_path),
            dry_run=False,
            target_backup_path=str(mismatched_backup),
        )

    assert _execution_rows(db_path) == rows_before
    assert hashlib.sha256(db_path.read_bytes()).hexdigest() == hash_before


def test_execution_gap_repair_live_replaces_only_target_keys_and_then_is_noop(tmp_path: Path) -> None:
    db_path = tmp_path / "execution-gaps.duckdb"
    backup_path = tmp_path / "execution-gaps.backup.duckdb"
    _seed_execution_database(db_path)
    target_hash_before = hashlib.sha256(db_path.read_bytes()).hexdigest()
    shutil.copy2(db_path, backup_path)

    result = materialize_task.repair_livermore_candidate_execution_gaps(
        str(db_path),
        dry_run=False,
        target_backup_path=str(backup_path),
    )

    assert result["status"] == "ok"
    assert result["mode"] == "live"
    assert result["target_count"] == 3
    assert result["repaired_count"] == 3
    assert result["deleted_physical_row_count"] == 4
    assert result["unresolved_count"] == 0
    assert result["backup_verified"] is True
    assert result["target_sha256_before"] == target_hash_before
    assert result["backup_sha256"] == target_hash_before
    uuid.UUID(str(result["run_id"]).rsplit(":", 1)[1])

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select stock_code, stock_name, candidate_rank, market_state, signal_kind,
                   data_status, formula_version, run_id, return_20d_net_adj,
                   evidence_json, price_adjustment_mode, buy_cost_bps, sell_cost_bps,
                   slippage_bps, entry_date, exit_date_20d
            from livermore_candidate_execution_history
            order by stock_code, signal_kind
            """
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) == 5
    targeted = {row[0]: row for row in rows if row[0] in {"000001.SZ", "000002.SZ", "000003.SZ"}}
    assert {row[1] for row in targeted.values()} == {"Raw Gap", "Pending", "Stale Formula"}
    assert {row[2] for row in targeted.values()} == {1, 2, 3}
    assert {row[3] for row in targeted.values()} == {"HOT"}
    assert {row[5] for row in targeted.values()} == {"complete"}
    assert {row[6] for row in targeted.values()} == {materialize_task.EXECUTION_FORMULA_VERSION}
    assert {row[7] for row in targeted.values()} == {result["run_id"]}
    assert all(row[8] is not None for row in targeted.values())
    assert all(json.loads(row[9])["price_adjustment_mode"] == materialize_task.PRICE_ADJUSTMENT_MODE for row in targeted.values())
    assert {row[10] for row in targeted.values()} == {materialize_task.PRICE_ADJUSTMENT_MODE}
    assert {row[11] for row in targeted.values()} == {materialize_task.BUY_COST_RATE * 10000}
    assert {row[12] for row in targeted.values()} == {materialize_task.SELL_COST_RATE * 10000}
    assert {row[13] for row in targeted.values()} == {materialize_task.SLIPPAGE_RATE * 10000}
    assert {row[14] for row in targeted.values()} == {"2026-01-06"}
    assert {row[15] for row in targeted.values()} == {"2026-01-25"}
    untouched = {row[0]: row for row in rows if row[0] in {"000004.SZ", "000005.SZ"}}
    assert untouched["000004.SZ"][7] == "original-000004.SZ"
    assert untouched["000004.SZ"][6] == "fv_livermore_candidate_forward_close_dual_adjust_v2"
    assert untouched["000005.SZ"][7] == "original-000005.SZ"

    after = materialize_task.repair_livermore_candidate_execution_gaps(str(db_path), dry_run=True)
    assert after["status"] == "ok"
    assert after["signal_kind"] == "stock_candidate"
    assert after["target_count"] == 0
    assert after["targets"] == []


def test_execution_gap_repair_live_rolls_back_all_exact_deletes_when_insert_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "execution-gaps.duckdb"
    backup_path = tmp_path / "execution-gaps.backup.duckdb"
    _seed_execution_database(db_path)
    rows_before = _execution_rows(db_path)
    shutil.copy2(db_path, backup_path)
    original_acquire_lock = materialize_task.acquire_lock
    observed = {"lock_entered": False}

    @contextmanager
    def tracking_acquire_lock(definition, *, base_dir, **kwargs):
        with original_acquire_lock(definition, base_dir=base_dir, **kwargs) as lock_path:
            observed["lock_entered"] = True
            yield lock_path

    def failing_insert(conn, rows):
        assert observed["lock_entered"] is True
        assert len(rows) == 3
        raise RuntimeError("injected insert failure")

    monkeypatch.setattr(materialize_task, "acquire_lock", tracking_acquire_lock)
    monkeypatch.setattr(materialize_task, "_insert_execution_history_rows", failing_insert)

    with pytest.raises(RuntimeError, match="injected insert failure"):
        materialize_task.repair_livermore_candidate_execution_gaps(
            str(db_path),
            dry_run=False,
            target_backup_path=str(backup_path),
        )

    assert observed["lock_entered"] is True
    assert _execution_rows(db_path) == rows_before


def test_execution_gap_repair_live_rechecks_target_hash_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "execution-gaps.duckdb"
    backup_path = tmp_path / "execution-gaps.backup.duckdb"
    _seed_execution_database(db_path)
    rows_before = _execution_rows(db_path)
    shutil.copy2(db_path, backup_path)
    original_validate = materialize_task._validate_livermore_execution_gap_backup

    def drift_after_validation(duckdb_file: Path, *, target_backup_path: str | None) -> dict[str, object]:
        evidence = original_validate(duckdb_file, target_backup_path=target_backup_path)
        drift_conn = duckdb.connect(str(duckdb_file), read_only=False)
        try:
            drift_conn.execute("create table drift_marker as select 1 as drift_value")
        finally:
            drift_conn.close()
        return evidence

    monkeypatch.setattr(
        materialize_task,
        "_validate_livermore_execution_gap_backup",
        drift_after_validation,
    )

    with pytest.raises(RuntimeError, match="changed after backup verification"):
        materialize_task.repair_livermore_candidate_execution_gaps(
            str(db_path),
            dry_run=False,
            target_backup_path=str(backup_path),
        )

    assert _execution_rows(db_path) == rows_before


def test_execution_gap_repair_reports_partial_when_future_adjustment_factor_is_still_missing(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "execution-gaps.duckdb"
    backup_path = tmp_path / "execution-gaps.backup.duckdb"
    _seed_execution_database(db_path)
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            delete from stock_adjustment_factor
            where stock_code = '000001.SZ' and trade_date = '2026-01-25'
            """
        )
    finally:
        conn.close()
    shutil.copy2(db_path, backup_path)

    result = materialize_task.repair_livermore_candidate_execution_gaps(
        str(db_path),
        dry_run=False,
        target_backup_path=str(backup_path),
    )

    assert result["status"] == "partial"
    assert result["repaired_count"] == 3
    assert result["unresolved_count"] == 1
    raw_gap = next(target for target in result["targets"] if target["key"]["stock_code"] == "000001.SZ")
    assert raw_gap["remaining_reasons"] == ["raw_20d_without_adjusted_20d"]

    after = materialize_task.repair_livermore_candidate_execution_gaps(str(db_path), dry_run=True)
    assert after["status"] == "partial"
    assert after["target_count"] == 1
    assert after["targets"][0]["reasons"] == ["raw_20d_without_adjusted_20d"]


@pytest.mark.parametrize(
    "mode_args",
    [[], ["--dry-run"]],
    ids=["default-preview", "explicit-dry-run"],
)
def test_execution_gap_repair_cli_defaults_to_preview_and_emits_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mode_args: list[str],
) -> None:
    script = load_module(
        "scripts.repair_livermore_execution_gaps",
        "scripts/repair_livermore_execution_gaps.py",
    )
    db_path = tmp_path / "execution-gaps.duckdb"
    db_path.write_bytes(b"test")
    captured: dict[str, object] = {}

    def fake_repair(
        duckdb_path: str,
        *,
        dry_run: bool,
        target_backup_path: str | None,
        signal_kind: str,
    ) -> dict[str, object]:
        captured.update(
            duckdb_path=duckdb_path,
            dry_run=dry_run,
            target_backup_path=target_backup_path,
            signal_kind=signal_kind,
        )
        return {"status": "ok", "mode": "dry_run", "target_count": 2}

    monkeypatch.setattr(script, "repair_livermore_candidate_execution_gaps", fake_repair)

    exit_code = script.main(["--duckdb-path", str(db_path), *mode_args])

    assert exit_code == 0
    assert captured == {
        "duckdb_path": str(db_path.resolve()),
        "dry_run": True,
        "target_backup_path": None,
        "signal_kind": "stock_candidate",
    }
    assert json.loads(capsys.readouterr().out) == {
        "status": "ok",
        "mode": "dry_run",
        "target_count": 2,
    }


def test_execution_gap_repair_cli_partial_is_nonzero_and_emits_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = load_module(
        "scripts.repair_livermore_execution_gaps_partial",
        "scripts/repair_livermore_execution_gaps.py",
    )
    db_path = tmp_path / "execution-gaps.duckdb"
    backup_path = tmp_path / "execution-gaps.backup.duckdb"
    db_path.write_bytes(b"test")
    backup_path.write_bytes(b"test")
    monkeypatch.setattr(
        script,
        "repair_livermore_candidate_execution_gaps",
        lambda *args, **kwargs: {"status": "partial", "unresolved_count": 1},
    )

    exit_code = script.main(
        [
            "--duckdb-path",
            str(db_path),
            "--apply",
            "--target-backup-path",
            str(backup_path),
        ]
    )

    assert exit_code != 0
    assert json.loads(capsys.readouterr().out) == {"status": "partial", "unresolved_count": 1}


def test_execution_gap_repair_cli_rejects_non_stock_candidate_signal_kind(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    script = load_module(
        "scripts.repair_livermore_execution_gaps_reject_signal_kind",
        "scripts/repair_livermore_execution_gaps.py",
    )
    db_path = tmp_path / "execution-gaps.duckdb"
    db_path.write_bytes(b"test")
    called = {"repair": False}

    def fake_repair(*args, **kwargs) -> dict[str, object]:
        called["repair"] = True
        return {"status": "ok"}

    monkeypatch.setattr(script, "repair_livermore_candidate_execution_gaps", fake_repair)

    exit_code = script.main(
        [
            "--duckdb-path",
            str(db_path),
            "--signal-kind",
            "theme_breakout",
        ]
    )

    assert exit_code != 0
    assert called["repair"] is False
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "partial"
    assert payload["error_type"] == "ValueError"
    assert "stock_candidate" in payload["error"]


def test_execution_gap_repair_result_bounds_operator_preview_and_keeps_full_counts() -> None:
    targets: list[dict[str, object]] = []
    for index in range(55):
        reasons = ["formula_version_stale"]
        if index < 5:
            reasons.append("raw_20d_without_adjusted_20d")
        targets.append(
            {
                "key": {
                    "signal_date": "2026-01-05",
                    "stock_code": f"{index:06d}.SZ",
                    "signal_kind": "stock_candidate",
                },
                "reasons": reasons,
                "physical_row_count": 2 if index < 5 else 1,
                "current": {},
                "preview": {},
                "repairable": True,
                "remaining_reasons": [],
            }
        )

    result = materialize_task._livermore_candidate_execution_gap_result(
        signal_kind="stock_candidate",
        targets=targets,
        mode="live",
        run_id="repair-run",
        repaired_count=55,
        deleted_physical_row_count=60,
    )

    assert result["target_count"] == 55
    assert result["target_physical_row_count"] == 60
    assert result["duplicate_physical_row_count"] == 5
    assert result["target_preview_count"] == 50
    assert result["preview_limit"] == 50
    assert result["targets_truncated"] is True
    assert len(result["target_keys"]) == 50
    assert len(result["targets"]) == 50
    assert result["reason_counts"] == {
        "formula_version_stale": 55,
        "raw_20d_without_adjusted_20d": 5,
    }
    assert result["remaining_reason_counts"] == {}
    assert result["repaired_count"] == 55
    assert result["deleted_physical_row_count"] == 60
