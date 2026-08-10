from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from scripts import run_decimal_precision_backfill as runner
from scripts.verify_decimal_precision_backfill import verify_databases


def _path_fixture(tmp_path: Path) -> runner.BackfillPaths:
    current = tmp_path / "current.duckdb"
    baseline = tmp_path / "baseline.duckdb"
    current.write_bytes(b"same-static-point")
    baseline.write_bytes(b"same-static-point")
    governance = tmp_path / "governance"
    archive = tmp_path / "archive"
    governance.mkdir()
    archive.mkdir()
    verifier_temp = tmp_path / "verifier-temp"
    verifier_temp.mkdir()
    return runner.BackfillPaths(
        duckdb_path=current.resolve(),
        governance_dir=governance.resolve(),
        archive_root=archive.resolve(),
        baseline_db_path=baseline.resolve(),
        receipt_path=(tmp_path / "receipt.json").resolve(),
        verifier_temp_dir=verifier_temp.resolve(),
    )


def _database_receipt() -> dict[str, object]:
    return {
        "schema_migrations": {"required": list(range(1, 40)), "missing": []},
        "target_counts": dict(runner.EXPECTED_TARGET_COUNTS),
        "fx": [{"base_currency": currency} for currency in runner.EXPECTED_FX],
        "curves": [{"curve_type": curve} for curve in runner.CURVE_CONTRACTS],
    }


def _verifier_pass_receipt(**overrides: object) -> dict[str, object]:
    target_keys = set(runner.VERIFIER_ALLOWED_TARGET_DATE_TABLE_KEYS)
    table_keys = sorted(
        target_keys | set(runner.VERIFIER_FROZEN_TABLE_KEYS) | {"main.other_table"}
    )
    inventory = []
    table_checks: dict[str, dict[str, object]] = {}

    def digest(label: str) -> dict[str, object]:
        return {
            "row_count": 1,
            "table_sha256": hashlib.sha256(label.encode("utf-8")).hexdigest(),
        }

    for table_key in table_keys:
        schema, table = table_key.split(".", 1)
        inventory.append(
            {
                "schema": schema,
                "table": table,
                "table_type": "BASE TABLE",
                "columns": [
                    {
                        "name": "fixture_column",
                        "ordinal_position": 1,
                        "duckdb_type": "VARCHAR",
                        "is_nullable": "YES",
                    }
                ],
            }
        )
        full = digest(f"{table_key}:full")
        before: dict[str, object] = {"full": full}
        after: dict[str, object] = {"full": dict(full)}
        if table_key in target_keys:
            target_date = {
                "date": runner.TARGET_REPORT_DATE,
                **digest(f"{table_key}:target"),
            }
            non_target = digest(f"{table_key}:non-target")
            before.update({"target_date": target_date, "non_target": non_target})
            after.update(
                {
                    "target_date": dict(target_date),
                    "non_target": dict(non_target),
                }
            )
        table_checks[table_key] = {
            "delta_policy": (
                "target_date_only" if table_key in target_keys else "table_unchanged"
            ),
            "allowed": True,
            "full_changed": False,
            "before": before,
            "after": after,
        }

    payload: dict[str, object] = {
        "schema_version": 1,
        "verifier_version": "1",
        "verifier_source_sha256": "a" * 64,
        "status": "pass",
        "verdict": "PASS",
        "report_date": runner.TARGET_REPORT_DATE,
        "allowed_target_date_tables": list(runner.VERIFIER_ALLOWED_TARGET_DATE_TABLES),
        "allowed_target_date_table_keys": list(
            runner.VERIFIER_ALLOWED_TARGET_DATE_TABLE_KEYS
        ),
        "frozen_tables": list(runner.VERIFIER_FROZEN_TABLES),
        "frozen_table_keys": list(runner.VERIFIER_FROZEN_TABLE_KEYS),
        "all_other_base_tables_policy": runner.VERIFIER_OTHER_TABLES_POLICY,
        "algorithm": dict(runner.VERIFIER_ALGORITHM_MARKERS),
        "baseline": {
            "fingerprint_stable": True,
            "inventory": inventory,
        },
        "current": {
            "fingerprint_stable": True,
            "inventory": [dict(entry) for entry in inventory],
        },
        "checks": {
            "fingerprint": {
                "status": "pass",
                "errors": [],
                "baseline_stable": True,
                "current_stable": True,
            },
            "inventory": {"status": "pass", "errors": []},
            "tables": table_checks,
        },
        "errors": [],
    }
    payload.update(overrides)
    return payload


def _formal_result(stage: str, run_id: str) -> dict[str, object]:
    contract = runner.FORMAL_STAGE_CONTRACTS[stage]
    source_version = f"sv_{stage}_fixture"
    counts = dict(contract["counts"])
    return {
        "status": "completed",
        "cache_key": contract["cache_key"],
        "cache_version": contract["cache_version"],
        "run_id": run_id,
        "report_date": runner.TARGET_REPORT_DATE,
        "source_version": source_version,
        "rule_version": contract["rule_version"],
        "vendor_version": "vv_none",
        "lock": f"lock:{stage}",
        "payload": {
            "run": {
                "run_id": run_id,
                "job_name": f"{stage}_materialize",
                "report_date": runner.TARGET_REPORT_DATE,
                "status": "completed",
                "lock": f"lock:{stage}",
            },
            "lineage": {
                "run_id": run_id,
                "report_date": runner.TARGET_REPORT_DATE,
                "source_version": source_version,
                "rule_version": contract["rule_version"],
                "cache_version": contract["cache_version"],
                "cache_key": contract["cache_key"],
            },
            "error": None,
            "result": counts,
        },
        **counts,
    }


def _snapshot_result() -> dict[str, object]:
    return {
        "status": "completed",
        "run_id": "snapshot-task-run",
        "snapshot_run_id": "snapshot-lineage-run",
        "zqtz_rows": 1_872,
        "tyw_rows": 3_128,
        "ingest_batch_ids": [runner.TARGET_INGEST_BATCH_ID],
        "lock": "lock:snapshot",
    }


def _run(
    paths: runner.BackfillPaths,
    *,
    dry_run: bool = False,
    verify_only: bool = False,
    actor_loader=None,
    source_validator=None,
    database_validator=None,
    terminal_validator=None,
    verifier=None,
    execution_lock_factory=None,
    use_default_source_validator: bool = False,
    use_default_database_validator: bool = False,
):
    return runner.run_decimal_precision_backfill(
        report_date=runner.TARGET_REPORT_DATE,
        ingest_batch_id=runner.TARGET_INGEST_BATCH_ID,
        duckdb_path=paths.duckdb_path,
        governance_dir=paths.governance_dir,
        archive_root=paths.archive_root,
        baseline_db_path=paths.baseline_db_path,
        receipt_path=paths.receipt_path,
        verifier_temp_dir=paths.verifier_temp_dir,
        approved_commit=None,
        maintenance_window_ref="MW-123",
        dba_backup_ref="DBA-456",
        dry_run=dry_run,
        verify_only=verify_only,
        apply_changes=not dry_run and not verify_only,
        production_gate=False,
        actor_loader=actor_loader,
        source_input_validator=(
            None
            if use_default_source_validator
            else source_validator or (lambda _paths: {"immutable": "same"})
        ),
        database_validator=(
            None
            if use_default_database_validator
            else database_validator or (lambda _path: _database_receipt())
        ),
        terminal_validator=terminal_validator
        or (lambda **kwargs: {"run_id": kwargs["result"]["run_id"]}),
        verifier=verifier or (lambda *_args, **_kwargs: _verifier_pass_receipt()),
        execution_lock_factory=execution_lock_factory,
    )


def test_dry_run_executes_real_read_only_hooks_but_never_loads_actors(
    tmp_path: Path,
) -> None:
    paths = _path_fixture(tmp_path)
    calls: list[str] = []

    def source_validator(_paths):
        calls.append("source")
        return {
            "manifest_sha256": "fixture",
            "parser_replay": {"zqtz": 1_872, "tyw": 3_128},
        }

    def database_validator(_path):
        calls.append("database")
        return _database_receipt()

    def forbidden_actor_loader():
        raise AssertionError("dry-run must not load actors")

    def forbidden_verifier(*_args, **_kwargs):
        raise AssertionError("dry-run must not invoke the post-run verifier")

    receipt = _run(
        paths,
        dry_run=True,
        actor_loader=forbidden_actor_loader,
        source_validator=source_validator,
        database_validator=database_validator,
        verifier=forbidden_verifier,
        execution_lock_factory=lambda _paths: (_ for _ in ()).throw(
            AssertionError("dry-run must not acquire the apply lock")
        ),
    )

    assert calls == ["source", "database"]
    assert receipt["status"] == "dry_run"
    assert receipt["write_executed"] is False
    assert receipt["write_completed"] is False
    assert receipt["stages"] == []
    assert (
        json.loads(paths.receipt_path.read_text(encoding="utf-8"))["status"]
        == "dry_run"
    )


def test_write_runs_only_four_pinned_actor_seams_in_order_then_verifies(
    tmp_path: Path,
) -> None:
    paths = _path_fixture(tmp_path)
    calls: list[tuple[str, dict[str, object]]] = []

    def snapshot(**kwargs):
        assert lock_events == ["enter"]
        calls.append(("snapshot", kwargs))
        return _snapshot_result()

    def balance(**kwargs):
        calls.append(("balance", kwargs))
        return _formal_result("balance", str(kwargs["run_id"]))

    def bond(**kwargs):
        calls.append(("bond", kwargs))
        return _formal_result("bond", str(kwargs["run_id"]))

    def risk(**kwargs):
        calls.append(("risk", kwargs))
        return _formal_result("risk", str(kwargs["run_id"]))

    database_validator_calls: list[Path] = []

    def one_argument_database_validator(path):
        database_validator_calls.append(path)
        return _database_receipt()

    verifier_calls: list[tuple[object, object, object, object]] = []

    def verifier(before, current, *, report_date, temp_dir):
        assert lock_events == ["enter"]
        verifier_calls.append((before, current, report_date, temp_dir))
        return _verifier_pass_receipt()

    lock_events: list[str] = []

    @contextmanager
    def execution_lock(_paths):
        lock_events.append("enter")
        yield
        lock_events.append("exit")

    receipt = _run(
        paths,
        actor_loader=lambda: runner.BackfillActors(snapshot, balance, bond, risk),
        database_validator=one_argument_database_validator,
        verifier=verifier,
        execution_lock_factory=execution_lock,
    )

    assert [name for name, _kwargs in calls] == ["snapshot", "balance", "bond", "risk"]
    snapshot_kwargs = calls[0][1]
    assert snapshot_kwargs["report_date"] == runner.TARGET_REPORT_DATE
    assert snapshot_kwargs["ingest_batch_id"] == runner.TARGET_INGEST_BATCH_ID
    assert snapshot_kwargs["source_families"] == ["zqtz", "tyw"]
    assert snapshot_kwargs["local_archive_path"] == str(paths.archive_root)
    assert calls[1][1]["ingest_batch_id"] == runner.TARGET_INGEST_BATCH_ID
    assert calls[1][1]["use_existing_fx_only"] is True
    assert "data_root" not in calls[1][1]
    assert "fx_source_path" not in calls[1][1]
    assert calls[2][1]["use_existing_curves_only"] is True
    assert verifier_calls == [
        (
            paths.baseline_db_path,
            paths.duckdb_path,
            runner.TARGET_REPORT_DATE,
            paths.verifier_temp_dir,
        )
    ]
    assert lock_events == ["enter", "exit"]
    assert database_validator_calls == [paths.duckdb_path] * 6
    assert receipt["status"] == "completed"
    assert receipt["verdict"] == "PASS"
    assert receipt["authorization"]["production_approval_granted_by_script"] is False
    assert receipt["verifier"]["result"]["status"] == "pass"
    assert [stage["name"] for stage in receipt["stages"]] == [
        "snapshot",
        "balance",
        "bond",
        "risk",
    ]


def test_apply_dispatches_default_database_validation_by_materialized_prefix(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _path_fixture(tmp_path)
    database_calls: list[str] = []
    source_calls = 0

    def full_database_validator(_path):
        database_calls.append("full")
        return _database_receipt()

    def stage_database_validator(_path, *, through_stage):
        database_calls.append(str(through_stage))
        return {
            **_database_receipt(),
            "validated_through_stage": through_stage,
        }

    def source_validator(_paths):
        nonlocal source_calls
        source_calls += 1
        return {
            "immutable": "same",
            "source_to_snapshot_tie_out": {"status": "passed"},
        }

    monkeypatch.setattr(runner, "_validate_database_contract", full_database_validator)
    monkeypatch.setattr(
        runner,
        "_validate_database_stage_contract",
        stage_database_validator,
    )
    monkeypatch.setattr(runner, "_validate_source_inputs", source_validator)
    actors = runner.BackfillActors(
        lambda **_kwargs: _snapshot_result(),
        lambda **kwargs: _formal_result("balance", str(kwargs["run_id"])),
        lambda **kwargs: _formal_result("bond", str(kwargs["run_id"])),
        lambda **kwargs: _formal_result("risk", str(kwargs["run_id"])),
    )

    receipt = _run(
        paths,
        actor_loader=lambda: actors,
        use_default_source_validator=True,
        use_default_database_validator=True,
    )

    assert database_calls == ["full", "snapshot", "balance", "bond", "risk", "full"]
    assert source_calls == 3
    assert [
        stage["database_contract"]["validated_through_stage"]
        for stage in receipt["stages"]
    ] == ["snapshot", "balance", "bond", "risk"]
    assert receipt["stages"][0]["snapshot_source_contract"][
        "source_to_snapshot_tie_out"
    ] == {"status": "passed"}


def test_stage_contract_failure_is_fail_fast_and_does_not_claim_success(
    tmp_path: Path,
) -> None:
    paths = _path_fixture(tmp_path)
    called: list[str] = []

    def snapshot(**_kwargs):
        called.append("snapshot")
        return _snapshot_result()

    def balance(**_kwargs):
        called.append("balance")
        return {
            "status": "completed",
            "run_id": "balance",
            "zqtz_rows": 0,
            "tyw_rows": 0,
        }

    def must_not_run(name):
        def inner(**_kwargs):
            called.append(name)
            raise AssertionError(f"{name} must not run")

        return inner

    with pytest.raises(runner.DecimalPrecisionBackfillFailed) as caught:
        _run(
            paths,
            actor_loader=lambda: runner.BackfillActors(
                snapshot,
                balance,
                must_not_run("bond"),
                must_not_run("risk"),
            ),
        )

    receipt = caught.value.receipt
    assert called == ["snapshot", "balance"]
    assert receipt["status"] == "failed"
    assert receipt["verdict"] == "FAIL"
    assert receipt["failed_step"] == "balance"
    assert receipt["write_completed"] is False
    assert [stage["status"] for stage in receipt["stages"]] == ["completed", "failed"]
    assert receipt["write_executed"] is True
    assert receipt["stage_writes_completed"] is False
    assert receipt["failure_forensics"]["status"] == "captured"
    assert receipt["failure_forensics"]["overall_run_remains_failed"] is True


def test_strong_verifier_failure_makes_whole_run_fail(tmp_path: Path) -> None:
    paths = _path_fixture(tmp_path)

    actors = runner.BackfillActors(
        lambda **_kwargs: _snapshot_result(),
        lambda **kwargs: _formal_result("balance", str(kwargs["run_id"])),
        lambda **kwargs: _formal_result("bond", str(kwargs["run_id"])),
        lambda **kwargs: _formal_result("risk", str(kwargs["run_id"])),
    )

    with pytest.raises(runner.DecimalPrecisionBackfillFailed) as caught:
        _run(
            paths,
            actor_loader=lambda: actors,
            verifier=lambda *_args, **_kwargs: {
                "status": "fail",
                "verdict": "FAIL",
                "verifier_source_sha256": "fixture",
                "errors": ["out-of-scope table changed"],
            },
        )

    assert caught.value.receipt["failed_step"] == "verifier"
    assert caught.value.receipt["failure_category"] == "verification_failure"
    assert caught.value.receipt["status"] == "failed"
    assert caught.value.receipt["write_executed"] is True
    assert caught.value.receipt["stage_writes_completed"] is True


@pytest.mark.parametrize(
    "case",
    [
        "metadata_only",
        "minimal",
        "errors",
        "source_sha256",
        "schema_version",
        "verifier_version",
        "report_date",
        "target_tables",
        "target_table_keys",
        "frozen_tables",
        "frozen_table_keys",
        "other_tables_policy",
        "canonical_algorithm",
        "inventory_scope",
        "fingerprint_check",
        "inventory_check",
        "baseline_unstable",
        "inventory_missing",
        "table_coverage",
        "table_not_allowed",
    ],
)
def test_strong_verifier_rejects_contradictory_or_minimal_pass_receipts(
    tmp_path: Path,
    case: str,
) -> None:
    paths = _path_fixture(tmp_path)
    payload = _verifier_pass_receipt()
    if case == "metadata_only":
        payload.pop("baseline")
        payload.pop("current")
        payload.pop("checks")
    elif case == "minimal":
        payload = {
            "status": "pass",
            "verdict": "PASS",
            "verifier_source_sha256": "a" * 64,
            "errors": [],
        }
    elif case == "errors":
        payload["errors"] = ["contradicts PASS"]
    elif case == "source_sha256":
        payload["verifier_source_sha256"] = "not-a-64-hex-digest"
    elif case == "schema_version":
        payload["schema_version"] = True
    elif case == "verifier_version":
        payload["verifier_version"] = 1
    elif case == "report_date":
        payload["report_date"] = "2026-07-30"
    elif case == "target_tables":
        payload["allowed_target_date_tables"] = []
    elif case == "target_table_keys":
        payload["allowed_target_date_table_keys"] = []
    elif case == "frozen_tables":
        payload["frozen_tables"] = []
    elif case == "frozen_table_keys":
        payload["frozen_table_keys"] = []
    elif case == "other_tables_policy":
        payload["all_other_base_tables_policy"] = "unspecified"
    elif case == "canonical_algorithm":
        payload["algorithm"] = {
            **runner.VERIFIER_ALGORITHM_MARKERS,
            "canonical_serialization": "lossy",
        }
    elif case == "inventory_scope":
        payload["algorithm"] = {
            **runner.VERIFIER_ALGORITHM_MARKERS,
            "inventory_scope": "selected tables only",
        }
    elif case == "fingerprint_check":
        payload["checks"]["fingerprint"]["status"] = "not_checked"
    elif case == "inventory_check":
        payload["checks"]["inventory"]["status"] = "not_checked"
    elif case == "baseline_unstable":
        payload["baseline"]["fingerprint_stable"] = False
    elif case == "inventory_missing":
        payload["current"]["inventory"] = []
    elif case == "table_coverage":
        payload["checks"]["tables"].pop(next(iter(payload["checks"]["tables"])))
    elif case == "table_not_allowed":
        first_comparison = next(iter(payload["checks"]["tables"].values()))
        first_comparison["allowed"] = False

    with pytest.raises(RuntimeError, match="Strong verifier"):
        runner._run_verifier(
            paths=paths,
            verifier=lambda *_args, **_kwargs: payload,
        )


def test_strong_verifier_contract_accepts_the_real_machine_receipt(
    tmp_path: Path,
) -> None:
    paths = _path_fixture(tmp_path)
    paths.baseline_db_path.unlink()
    paths.duckdb_path.unlink()
    for db_path in (paths.baseline_db_path, paths.duckdb_path):
        conn = duckdb.connect(str(db_path))
        try:
            for table in runner.VERIFIER_ALLOWED_TARGET_DATE_TABLES:
                conn.execute(
                    f'create table "{table}" (report_date date, amount decimal(24,8))'
                )
                conn.execute(
                    f"insert into \"{table}\" values (date '2026-07-31', 1.00000000)"
                )
            for table in runner.VERIFIER_FROZEN_TABLES:
                conn.execute(
                    f'create table "{table}" (trade_date date, amount decimal(24,8))'
                )
                conn.execute(
                    f"insert into \"{table}\" values (date '2026-06-30', 1.00000000)"
                )
            conn.execute("create table other_table (row_key integer)")
            conn.execute("insert into other_table values (1)")
        finally:
            conn.close()
    conn = duckdb.connect(str(paths.duckdb_path))
    try:
        conn.execute(
            """
            update fact_formal_risk_tensor_daily
            set amount = 2.00000000
            where report_date = date '2026-07-31'
            """
        )
    finally:
        conn.close()

    evidence = runner._run_verifier(paths=paths, verifier=verify_databases)

    assert evidence["result"]["status"] == "pass"
    assert evidence["result"]["checks"]["fingerprint"]["status"] == "pass"
    assert evidence["result"]["checks"]["inventory"]["status"] == "pass"


def test_verify_only_calls_verifier_and_never_loads_actors(tmp_path: Path) -> None:
    paths = _path_fixture(tmp_path)
    calls: list[str] = []

    def source_validator(_paths):
        calls.append("source")
        return {"immutable": "same"}

    def verifier(*_args, **_kwargs):
        calls.append("verifier")
        return _verifier_pass_receipt()

    receipt = _run(
        paths,
        verify_only=True,
        actor_loader=lambda: (_ for _ in ()).throw(
            AssertionError("actors must not load")
        ),
        source_validator=source_validator,
        verifier=verifier,
    )

    assert calls == ["source", "verifier", "source"]
    assert receipt["status"] == "verified"
    assert receipt["write_executed"] is False
    assert receipt["write_completed"] is False


def test_verify_only_requires_the_second_archive_snapshot_tieout_to_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _path_fixture(tmp_path)
    source_calls = 0

    def source_validator(_paths):
        nonlocal source_calls
        source_calls += 1
        return {
            "immutable": "same",
            "source_to_snapshot_tie_out": {
                "status": "passed" if source_calls == 1 else "failed",
                "mismatched_row_count": 0 if source_calls == 1 else 1,
            },
        }

    monkeypatch.setattr(runner, "_validate_source_inputs", source_validator)

    with pytest.raises(runner.DecimalPrecisionBackfillFailed) as caught:
        _run(
            paths,
            verify_only=True,
            actor_loader=lambda: (_ for _ in ()).throw(
                AssertionError("actors must not load")
            ),
            use_default_source_validator=True,
        )

    assert source_calls == 2
    assert caught.value.receipt["status"] == "failed"
    assert caught.value.receipt["failed_step"] == "immutable_input_postcheck"
    assert "does not exactly match" in caught.value.receipt["error_message"]


def test_apply_rejects_baseline_tampering_before_final_verifier(
    tmp_path: Path,
) -> None:
    paths = _path_fixture(tmp_path)
    source_calls = 0
    verifier_calls = 0
    actors = runner.BackfillActors(
        lambda **_kwargs: _snapshot_result(),
        lambda **kwargs: _formal_result("balance", str(kwargs["run_id"])),
        lambda **kwargs: _formal_result("bond", str(kwargs["run_id"])),
        lambda **kwargs: _formal_result("risk", str(kwargs["run_id"])),
    )

    def source_validator(_paths):
        nonlocal source_calls
        source_calls += 1
        if source_calls == 2:
            paths.baseline_db_path.write_bytes(b"tampered-after-stage-writes")
        return {"immutable": "same"}

    def verifier(*_args, **_kwargs):
        nonlocal verifier_calls
        verifier_calls += 1
        return _verifier_pass_receipt()

    with pytest.raises(runner.DecimalPrecisionBackfillFailed) as caught:
        _run(
            paths,
            actor_loader=lambda: actors,
            source_validator=source_validator,
            verifier=verifier,
        )

    receipt = caught.value.receipt
    assert source_calls == 2
    assert verifier_calls == 0
    assert receipt["failed_step"] == "baseline_pre_verifier"
    assert receipt["failure_category"] == "baseline_evidence_failure"
    assert receipt["write_executed"] is True
    assert receipt["stage_writes_completed"] is True
    assert receipt["write_completed"] is False
    assert receipt["failure_forensics"]["status"] == "capture_failed"
    assert "Baseline DuckDB" in receipt["error_message"]


def test_production_gate_rejects_dirty_tree_before_any_business_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _path_fixture(tmp_path)
    repo_root = tmp_path / "approved-repo-root"
    repo_root.mkdir()
    monkeypatch.setattr(runner, "ROOT", repo_root)
    settings = SimpleNamespace(
        environment="production",
        governance_backend="sql-authority",
        source_preview_governance_backend="sql-authority",
        governance_sql_dsn="postgresql://configured-but-never-opened",
        duckdb_path=str(paths.duckdb_path),
        governance_path=paths.governance_dir,
        local_archive_path=paths.archive_root,
    )
    calls: list[str] = []

    with pytest.raises(runner.DecimalPrecisionBackfillFailed) as caught:
        runner.run_decimal_precision_backfill(
            report_date=runner.TARGET_REPORT_DATE,
            ingest_batch_id=runner.TARGET_INGEST_BATCH_ID,
            duckdb_path=paths.duckdb_path,
            governance_dir=paths.governance_dir,
            archive_root=paths.archive_root,
            baseline_db_path=paths.baseline_db_path,
            receipt_path=paths.receipt_path,
            verifier_temp_dir=paths.verifier_temp_dir,
            approved_commit="a" * 40,
            dry_run=True,
            settings_loader=lambda: settings,
            git_probe=lambda _root: {
                "repo_root": str(runner.ROOT),
                "head": "a" * 40,
                "status": "?? unreviewed.py",
            },
            source_input_validator=lambda _paths: calls.append("source") or {},
            database_validator=lambda _path: (
                calls.append("database") or _database_receipt()
            ),
        )

    assert calls == []
    assert "clean" in caught.value.receipt["error_message"].lower()
    assert caught.value.receipt["failure_category"] == "production_gate_failure"


def test_cli_requires_an_explicit_execution_mode(tmp_path: Path) -> None:
    paths = _path_fixture(tmp_path)
    argv = [
        "--report-date",
        runner.TARGET_REPORT_DATE,
        "--ingest-batch-id",
        runner.TARGET_INGEST_BATCH_ID,
        "--duckdb-path",
        str(paths.duckdb_path),
        "--governance-dir",
        str(paths.governance_dir),
        "--archive-root",
        str(paths.archive_root),
        "--baseline-db",
        str(paths.baseline_db_path),
        "--receipt-path",
        str(paths.receipt_path),
        "--approved-commit",
        "a" * 40,
    ]

    with pytest.raises(SystemExit) as caught:
        runner._build_parser().parse_args(argv)

    assert caught.value.code == 2


def test_apply_rejects_stale_baseline_before_loading_actors(tmp_path: Path) -> None:
    paths = _path_fixture(tmp_path)
    paths.baseline_db_path.write_bytes(b"stale-backup")

    with pytest.raises(runner.DecimalPrecisionBackfillFailed) as caught:
        _run(
            paths,
            actor_loader=lambda: (_ for _ in ()).throw(
                AssertionError("actors must not load")
            ),
        )

    assert caught.value.receipt["failed_step"] == "preflight"
    assert "baseline/current" in caught.value.receipt["error_message"]
    assert caught.value.receipt["write_executed"] is False


def test_snapshot_terminal_requires_raw_counts_and_pinned_manifest_contract(
    tmp_path: Path,
) -> None:
    paths = _path_fixture(tmp_path)
    result = _snapshot_result()
    (paths.governance_dir / "snapshot_build_run.jsonl").write_text(
        json.dumps(
            {
                "run_id": result["run_id"],
                "status": "completed",
                "source_version": "__".join(
                    sorted(
                        str(runner.SOURCE_CONTRACTS[family]["source_version"])
                        for family in runner.TARGET_SOURCE_FAMILIES
                    )
                ),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    manifests = []
    for family, table in (
        ("zqtz", "zqtz_bond_daily_snapshot"),
        ("tyw", "tyw_interbank_daily_snapshot"),
    ):
        manifests.append(
            {
                "snapshot_run_id": result["snapshot_run_id"],
                "target_table": table,
                "status": "completed",
                "produced_row_count": runner.SOURCE_CONTRACTS[family]["raw_rows"],
                "rule_version": "rv_snapshot_zqtz_tyw_v1",
                "schema_version": "snapshot.schema.v1",
                "canonical_grain_version": "cgv_v1",
                "source_linkage": {
                    "source_family": family,
                    "ingest_batch_id": runner.TARGET_INGEST_BATCH_ID,
                    "source_version": runner.SOURCE_CONTRACTS[family]["source_version"],
                    "archived_path": str(
                        paths.archive_root
                        / runner.SOURCE_CONTRACTS[family]["file_name"]
                    ),
                },
            }
        )
    manifest_path = paths.governance_dir / "snapshot_manifest.jsonl"
    manifest_path.write_text(
        "\n".join(json.dumps(row) for row in manifests) + "\n",
        encoding="utf-8",
    )

    terminal = runner._validate_governance_terminal(
        stage="snapshot",
        result=result,
        paths=paths,
        settings=None,
        production_gate=False,
    )

    assert terminal["manifest_count"] == 2
    assert terminal["authority"] == "jsonl_only_repository_contract"
    assert terminal["sql_jsonl_parity"] == "not_applicable_stream_not_sql_supported"

    manifests[1]["produced_row_count"] = 3_128
    manifest_path.write_text(
        "\n".join(json.dumps(row) for row in manifests) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="produced_row_count"):
        runner._validate_governance_terminal(
            stage="snapshot",
            result=result,
            paths=paths,
            settings=None,
            production_gate=False,
        )


def test_formal_terminal_requires_sequence_basis_fact_tables_and_lineage(
    tmp_path: Path,
) -> None:
    paths = _path_fixture(tmp_path)
    result = _formal_result("bond", "bond-run")
    build_rows = [
        {
            "run_id": result["run_id"],
            "status": status,
            "cache_key": result["cache_key"],
            "cache_version": result["cache_version"],
            "report_date": result["report_date"],
            "source_version": result["source_version"]
            if status == "completed"
            else "sv_running",
            "rule_version": result["rule_version"] if status == "completed" else None,
        }
        for status in ("queued", "running", "completed")
    ]
    (paths.governance_dir / "cache_build_run.jsonl").write_text(
        "\n".join(json.dumps(row) for row in build_rows) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "run_id": result["run_id"],
        "report_date": result["report_date"],
        "cache_key": result["cache_key"],
        "cache_version": result["cache_version"],
        "source_version": result["source_version"],
        "rule_version": result["rule_version"],
        "basis": "formal",
        "fact_tables": ["fact_formal_bond_analytics_daily"],
        "lineage": {
            "run_id": result["run_id"],
            "report_date": result["report_date"],
            "source_version": result["source_version"],
            "rule_version": result["rule_version"],
        },
    }
    manifest_path = paths.governance_dir / "cache_manifest.jsonl"
    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")

    terminal = runner._validate_governance_terminal(
        stage="bond",
        result=result,
        paths=paths,
        settings=None,
        production_gate=False,
    )

    assert terminal["terminal_statuses"] == ["queued", "running", "completed"]

    manifest["basis"] = "preview"
    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="basis"):
        runner._validate_governance_terminal(
            stage="bond",
            result=result,
            paths=paths,
            settings=None,
            production_gate=False,
        )


def test_source_input_contract_uses_exact_two_manifests_and_full_archive_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _path_fixture(tmp_path)
    payloads = {"zqtz": b"zqtz-fixture", "tyw": b"tyw-fixture"}
    contracts: dict[str, dict[str, object]] = {}
    manifest_rows = []
    for family, payload in payloads.items():
        archive = paths.archive_root / f"{family}.xls"
        archive.write_bytes(payload)
        contracts[family] = {
            "source_version": f"sv_{family}",
            "file_name": archive.name,
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest().upper(),
            "raw_rows": 1,
            "canonical_rows": 1,
        }
        manifest_rows.append(
            {
                "report_date": runner.TARGET_REPORT_DATE,
                "ingest_batch_id": runner.TARGET_INGEST_BATCH_ID,
                "source_family": family,
                "source_version": f"sv_{family}",
                "source_file": archive.name,
                "archived_path": str(archive.resolve()),
                "status": "completed",
            }
        )
    manifest = paths.governance_dir / "source_manifest.jsonl"
    manifest.write_text(
        "\n".join(json.dumps(row) for row in manifest_rows) + "\n", encoding="utf-8"
    )

    monkeypatch.setattr(runner, "SOURCE_CONTRACTS", contracts)
    monkeypatch.setattr(
        runner,
        "_replay_locked_archives",
        lambda selected: {
            family: {"raw_rows": 1, "canonical_rows": 1} for family in selected
        },
    )
    monkeypatch.setattr(
        runner,
        "_snapshot_archive_tieout",
        lambda _paths, _selected: {"status": "passed"},
    )

    evidence = runner._validate_source_inputs(paths)

    assert [row["family"] for row in evidence["locked_archives"]] == ["tyw", "zqtz"]
    assert evidence["archive_inventory"]["file_count"] == 2
    assert (
        evidence["source_manifest"]["sha256"]
        == hashlib.sha256(manifest.read_bytes()).hexdigest().upper()
    )

    duplicate = dict(manifest_rows[0])
    duplicate["status"] = "rerun"
    with manifest.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(duplicate) + "\n")
    with pytest.raises(RuntimeError, match="exactly two"):
        runner._validate_source_inputs(paths)


def test_snapshot_archive_tieout_rejects_same_count_with_wrong_decimal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "snapshot-tieout.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table zqtz_bond_daily_snapshot (
              report_date date, instrument_code varchar, instrument_name varchar,
              portfolio_name varchar, cost_center varchar, currency_code varchar,
              account_category varchar, asset_class varchar, bond_type varchar,
              business_type_primary varchar, maturity_date date, next_call_date date,
              is_issuance_like boolean, source_version varchar, ingest_batch_id varchar,
              market_value_native decimal(24,8)
            )
            """
        )
        conn.execute(
            """
            insert into zqtz_bond_daily_snapshot values (
              date '2026-07-31', 'B1', 'Bond', 'P', 'C', 'CNY', 'AC', 'AS',
              'BT', 'BP', date '2027-07-31', null, false, 'sv', 'ib', 2.00000000
            )
            """
        )
        conn.execute(
            """
            create table tyw_interbank_daily_snapshot (
              report_date date, position_id varchar, principal_native decimal(24,8)
            )
            """
        )
        conn.execute(
            "insert into tyw_interbank_daily_snapshot values (date '2026-07-31', 'T1', 5.00000000)"
        )
    finally:
        conn.close()

    expected = {
        "zqtz": [
            {
                "report_date": runner.TARGET_REPORT_DATE,
                "instrument_code": "B1",
                "instrument_name": "Bond",
                "portfolio_name": "P",
                "cost_center": "C",
                "currency_code": "CNY",
                "account_category": "AC",
                "asset_class": "AS",
                "bond_type": "BT",
                "business_type_primary": "BP",
                "maturity_date": "2027-07-31",
                "next_call_date": None,
                "is_issuance_like": False,
                "source_version": "sv",
                "ingest_batch_id": "ib",
                "market_value_native": Decimal("1.00000000"),
            }
        ],
        "tyw": [
            {
                "report_date": runner.TARGET_REPORT_DATE,
                "position_id": "T1",
                "principal_native": Decimal("5.00000000"),
            }
        ],
    }
    monkeypatch.setattr(
        runner,
        "SNAPSHOT_SOURCE_FIELDS",
        {
            "zqtz": tuple(expected["zqtz"][0]),
            "tyw": tuple(expected["tyw"][0]),
        },
    )

    receipt = runner._compare_snapshot_rows(db_path, expected)

    assert receipt["status"] == "failed"
    assert receipt["zqtz"]["missing_key_count"] == 0
    assert receipt["zqtz"]["extra_key_count"] == 0
    assert receipt["zqtz"]["mismatched_row_count"] == 1

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute("update zqtz_bond_daily_snapshot set market_value_native = 1")
    finally:
        conn.close()
    assert runner._compare_snapshot_rows(db_path, expected)["status"] == "passed"


def test_database_contract_checks_stage_prefix_transitions_fx_and_curve_hashes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "contract.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            "create table _schema_migrations (version integer, description varchar)"
        )
        conn.executemany(
            "insert into _schema_migrations values (?, 'fixture')",
            [(version,) for version in range(1, 40)],
        )
        conn.execute(
            """
            create table zqtz_bond_daily_snapshot (
              report_date date, is_issuance_like boolean, currency_code varchar,
              face_value_native decimal(24,8), market_value_native decimal(24,8),
              amortized_cost_native decimal(24,8), accrued_interest_native decimal(24,8),
              source_version varchar,
              rule_version varchar, ingest_batch_id varchar, trace_id varchar
            )
            """
        )
        conn.execute(
            "insert into zqtz_bond_daily_snapshot values (date '2026-07-31', false, 'CNY', 100, 10, 9, 1, 'sv', 'rv', 'ib', 'trace-z')"
        )
        conn.execute(
            """
            create table tyw_interbank_daily_snapshot (
              report_date date, currency_code varchar, principal_native decimal(24,8),
              accrued_interest_native decimal(24,8), source_version varchar, rule_version varchar,
              ingest_batch_id varchar, trace_id varchar
            )
            """
        )
        conn.execute(
            "insert into tyw_interbank_daily_snapshot values (date '2026-07-31', 'CNY', 20, 2, 'sv', 'rv', 'ib', 'trace-t')"
        )
        conn.execute(
            """
            create table fact_formal_zqtz_balance_daily (
              report_date date, currency_basis varchar, face_value_amount decimal(24,8),
              market_value_amount decimal(24,8), amortized_cost_amount decimal(24,8),
              accrued_interest_amount decimal(24,8), source_version varchar,
              rule_version varchar, ingest_batch_id varchar, trace_id varchar
            )
            """
        )
        conn.execute(
            "insert into fact_formal_zqtz_balance_daily values (date '2026-07-31', 'native', 100, 10, 9, 1, 'sv', 'rv', 'ib', 'trace-z'), (date '2026-07-31', 'CNY', 100, 10, 9, 1, 'sv', 'rv', 'ib', 'trace-z')"
        )
        conn.execute(
            """
            create table fact_formal_tyw_balance_daily (
              report_date date, currency_basis varchar, principal_amount decimal(24,8),
              accrued_interest_amount decimal(24,8), source_version varchar,
              rule_version varchar, ingest_batch_id varchar, trace_id varchar
            )
            """
        )
        conn.execute(
            "insert into fact_formal_tyw_balance_daily values (date '2026-07-31', 'native', 20, 2, 'sv', 'rv', 'ib', 'trace-t'), (date '2026-07-31', 'CNY', 20, 2, 'sv', 'rv', 'ib', 'trace-t')"
        )
        conn.execute(
            """
            create table fact_formal_bond_analytics_daily (
              report_date date, face_value decimal(24,8), market_value decimal(24,8),
              amortized_cost decimal(24,8), accrued_interest decimal(24,8),
              market_value_native decimal(24,8), dv01 decimal(24,8),
              spread_dv01 decimal(24,8), source_version varchar, rule_version varchar,
              ingest_batch_id varchar, trace_id varchar
            )
            """
        )
        conn.execute(
            "insert into fact_formal_bond_analytics_daily values (date '2026-07-31', 100, 10, 9, 1, 10, 2, 3, 'sv', 'rv', 'ib', 'trace-z')"
        )
        conn.execute(
            """
            create table fact_formal_risk_tensor_daily (
              report_date date, bond_count integer, total_market_value decimal(24,8),
              portfolio_dv01 decimal(24,8), cs01 decimal(24,8), source_version varchar,
              rule_version varchar, cache_version varchar, upstream_source_version varchar,
              upstream_rule_version varchar, upstream_cache_version varchar,
              liability_source_version varchar, liability_rule_version varchar, trace_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_risk_tensor_daily values (
              date '2026-07-31', 1, 10, 2, 3, 'sv', 'rv', 'cv',
              'up-sv', 'up-rv', 'up-cv', 'liab-sv', 'liab-rv', 'trace-risk'
            )
            """
        )
        conn.execute(
            """
            create table fx_daily_mid (
              trade_date date, base_currency varchar, quote_currency varchar,
              mid_rate decimal(18,8), source_name varchar, source_version varchar,
              vendor_name varchar, vendor_version varchar, vendor_series_code varchar,
              observed_trade_date date, is_business_day boolean, is_carry_forward boolean
            )
            """
        )
        for currency, contract in runner.EXPECTED_FX.items():
            lineage = contract["lineage"]
            conn.execute(
                "insert into fx_daily_mid values (date '2026-07-31', ?, 'CNY', ?, ?, ?, ?, ?, ?, date '2026-07-31', true, false)",
                [currency, contract["rate"], *lineage],
            )
        conn.execute(
            """
            create table fact_formal_yield_curve_daily (
              trade_date date, curve_type varchar, tenor varchar, rate_pct decimal(18,8),
              vendor_name varchar, vendor_version varchar, source_version varchar, rule_version varchar
            )
            """
        )
        for curve_type, contract in runner.CURVE_CONTRACTS.items():
            conn.execute(
                "insert into fact_formal_yield_curve_daily values (date '2026-06-30', ?, '1Y', 1.00000000, ?, ?, ?, 'rv_yield_curve_formal_materialize_v1')",
                [
                    curve_type,
                    contract["vendor_name"],
                    contract["vendor_version"],
                    contract["source_version"],
                ],
            )

        patched_curves = {}
        for curve_type, contract in runner.CURVE_CONTRACTS.items():
            rows = conn.execute(
                """
                select tenor, cast(rate_pct as varchar), vendor_name, vendor_version,
                       source_version, rule_version
                from fact_formal_yield_curve_daily
                where curve_type = ? order by tenor
                """,
                [curve_type],
            ).fetchall()
            patched_curves[curve_type] = {
                **contract,
                "points": 1,
                "sha256": hashlib.sha256(
                    json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode(
                        "utf-8"
                    )
                )
                .hexdigest()
                .upper(),
            }
    finally:
        conn.close()

    monkeypatch.setattr(
        runner,
        "EXPECTED_TARGET_COUNTS",
        {
            "zqtz_bond_daily_snapshot": 1,
            "tyw_interbank_daily_snapshot": 1,
            "fact_formal_zqtz_balance_daily": 2,
            "fact_formal_tyw_balance_daily": 2,
            "fact_formal_bond_analytics_daily": 1,
            "fact_formal_risk_tensor_daily": 1,
        },
    )
    monkeypatch.setattr(runner, "CURVE_CONTRACTS", patched_curves)

    evidence = runner._validate_database_contract(db_path)

    assert evidence["schema_migrations"]["missing"] == []
    assert len(evidence["fx"]) == 5
    assert {row["resolved_trade_date"] for row in evidence["curve_anchors"]} == {
        "2026-06-30"
    }
    assert evidence["business_tie_outs"]["risk_to_bond"]["cs01"]["residual"] == "0"

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute("update zqtz_bond_daily_snapshot set trace_id = 'trace-z-new'")
        stale_downstream_traces = conn.execute(
            """
            select
              (select min(trace_id) from fact_formal_zqtz_balance_daily),
              (select min(trace_id) from fact_formal_bond_analytics_daily)
            """
        ).fetchone()
    finally:
        conn.close()

    assert stale_downstream_traces == ("trace-z", "trace-z")
    snapshot_stage = runner._validate_database_stage_contract(
        db_path,
        through_stage="snapshot",
    )
    assert set(snapshot_stage["target_counts"]) == set(runner.STAGE_TABLES["snapshot"])
    with pytest.raises(RuntimeError, match="snapshot/formal balance trace tie-out"):
        runner._validate_database_stage_contract(db_path, through_stage="balance")

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            "update fact_formal_zqtz_balance_daily set trace_id = 'trace-z-new'"
        )
        stale_bond_trace = conn.execute(
            "select min(trace_id) from fact_formal_bond_analytics_daily"
        ).fetchone()[0]
    finally:
        conn.close()

    assert stale_bond_trace == "trace-z"
    balance_stage = runner._validate_database_stage_contract(
        db_path,
        through_stage="balance",
    )
    assert set(balance_stage["target_counts"]) == {
        *runner.STAGE_TABLES["snapshot"],
        *runner.STAGE_TABLES["balance"],
    }
    with pytest.raises(RuntimeError, match="Bond/non-issuance snapshot trace tie-out"):
        runner._validate_database_stage_contract(db_path, through_stage="bond")

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            "update fact_formal_bond_analytics_daily set trace_id = 'trace-z-new'"
        )
        conn.execute(
            "update fact_formal_risk_tensor_daily set total_market_value = 999"
        )
    finally:
        conn.close()

    bond_stage = runner._validate_database_stage_contract(
        db_path,
        through_stage="bond",
    )
    assert set(bond_stage["target_counts"]) == {
        *runner.STAGE_TABLES["snapshot"],
        *runner.STAGE_TABLES["balance"],
        *runner.STAGE_TABLES["bond"],
    }
    with pytest.raises(RuntimeError, match="total_market_value"):
        runner._validate_database_stage_contract(db_path, through_stage="risk")

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute("update fact_formal_risk_tensor_daily set total_market_value = 10")
    finally:
        conn.close()
    risk_stage = runner._validate_database_stage_contract(
        db_path,
        through_stage="risk",
    )
    assert risk_stage["validation_scope"] == "full_chain"

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute("update zqtz_bond_daily_snapshot set trace_id = 'trace-z'")
        conn.execute("update fact_formal_zqtz_balance_daily set trace_id = 'trace-z'")
        conn.execute("update fact_formal_bond_analytics_daily set trace_id = 'trace-z'")
    finally:
        conn.close()

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            "update zqtz_bond_daily_snapshot set currency_code = 'USD' where trace_id = 'trace-z'"
        )
        conn.execute(
            """
            update fact_formal_zqtz_balance_daily
            set face_value_amount = 678.94000000,
                market_value_amount = 67.89400000,
                amortized_cost_amount = 61.10460000,
                accrued_interest_amount = 6.78940000
            where trace_id = 'trace-z' and currency_basis = 'CNY'
            """
        )
        conn.execute(
            """
            update fact_formal_bond_analytics_daily
            set face_value = 678.94000000,
                market_value = 67.89400000,
                amortized_cost = 61.10460000,
                accrued_interest = 6.78940000
            where trace_id = 'trace-z'
            """
        )
        conn.execute(
            "update fact_formal_risk_tensor_daily set total_market_value = 67.89400000"
        )
    finally:
        conn.close()

    usd_evidence = runner._validate_database_contract(db_path)
    assert (
        usd_evidence["business_tie_outs"]["snapshot_to_formal_balance_amounts"]["zqtz"][
            "max_absolute_residual"
        ]
        == "0.00000000"
    )

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            update fact_formal_zqtz_balance_daily
            set market_value_amount = market_value_amount + 0.00000001
            where trace_id = 'trace-z' and currency_basis = 'CNY'
            """
        )
    finally:
        conn.close()
    with pytest.raises(RuntimeError, match="Decimal amount tie-out"):
        runner._validate_database_contract(db_path)

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            update fact_formal_zqtz_balance_daily
            set market_value_amount = 67.89400000
            where trace_id = 'trace-z' and currency_basis = 'CNY'
            """
        )
        conn.execute(
            """
            update fact_formal_bond_analytics_daily
            set market_value_native = market_value_native + 0.00000001
            where trace_id = 'trace-z'
            """
        )
    finally:
        conn.close()
    with pytest.raises(RuntimeError, match="Bond/formal-balance"):
        runner._validate_database_contract(db_path)

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            "update zqtz_bond_daily_snapshot set currency_code = 'CNY' where trace_id = 'trace-z'"
        )
        conn.execute(
            """
            update fact_formal_zqtz_balance_daily
            set face_value_amount = 100,
                market_value_amount = 10,
                amortized_cost_amount = 9,
                accrued_interest_amount = 1
            where trace_id = 'trace-z' and currency_basis = 'CNY'
            """
        )
        conn.execute(
            """
            update fact_formal_bond_analytics_daily
            set face_value = 100,
                market_value = 10,
                amortized_cost = 9,
                accrued_interest = 1,
                market_value_native = 10
            where trace_id = 'trace-z'
            """
        )
        conn.execute("update fact_formal_risk_tensor_daily set total_market_value = 10")
    finally:
        conn.close()

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            "update fact_formal_zqtz_balance_daily set market_value_amount = 11 where currency_basis = 'CNY'"
        )
    finally:
        conn.close()
    with pytest.raises(RuntimeError, match="Decimal amount tie-out"):
        runner._validate_database_contract(db_path)

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            "update fact_formal_zqtz_balance_daily set market_value_amount = 10 where currency_basis = 'CNY'"
        )
        conn.execute("update fact_formal_bond_analytics_daily set amortized_cost = 8")
    finally:
        conn.close()
    with pytest.raises(RuntimeError, match="Bond/formal-balance"):
        runner._validate_database_contract(db_path)

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute("update fact_formal_bond_analytics_daily set amortized_cost = 9")
    finally:
        conn.close()

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute("update fact_formal_risk_tensor_daily set cs01 = 4")
    finally:
        conn.close()
    with pytest.raises(RuntimeError, match="cs01"):
        runner._validate_database_contract(db_path)

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute("update fact_formal_risk_tensor_daily set cs01 = 3")
        conn.execute(
            "update fact_formal_tyw_balance_daily set currency_basis = 'native' where currency_basis = 'CNY'"
        )
    finally:
        conn.close()
    with pytest.raises(RuntimeError, match="tyw snapshot/formal balance"):
        runner._validate_database_contract(db_path)

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            "update fact_formal_tyw_balance_daily set currency_basis = 'CNY' where rowid = (select max(rowid) from fact_formal_tyw_balance_daily)"
        )
        conn.execute("delete from _schema_migrations where version = 39")
    finally:
        conn.close()
    with pytest.raises(RuntimeError, match="39"):
        runner._validate_database_contract(db_path)
