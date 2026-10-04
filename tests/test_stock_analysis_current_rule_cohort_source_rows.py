from __future__ import annotations

import copy
from contextlib import contextmanager, nullcontext
from pathlib import Path

import duckdb
import pytest

from backend.app.core_finance.matched_baseline import (
    STOCK_ADJUSTMENT_FACTOR_TABLE,
    TABLE_LIMIT_PRICE,
    TABLE_OBS,
    _control_execution_pit_proof,
)
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.tasks import stock_analysis_current_rule_cohort_bundle_producer as producer
from backend.app.tasks import stock_analysis_current_rule_cohort_materialize as task

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_livermore]


def _source_bundle(tmp_path: Path) -> tuple[Path, task._ValidatedBundle]:
    path = tmp_path / "source.duckdb"
    source_index = {
        (TABLE_OBS, "observation", "vv", "rv", "obs_run"): "2026-06-01",
        (STOCK_ADJUSTMENT_FACTOR_TABLE, "factor", "vv", "rv", "factor_run"): "2026-06-01",
        (TABLE_LIMIT_PRICE, "limit_day_5", "vv", "rv", "limit_run_5"): "2026-06-05",
    }
    conn = duckdb.connect(str(path))
    try:
        conn.execute(
            "create table choice_stock_daily_observation(trade_date varchar, stock_code varchar, "
            "open_value double, close_value double, tradestatus varchar, highlimit varchar, "
            "lowlimit varchar, source_version varchar, vendor_version varchar, rule_version varchar, run_id varchar)"
        )
        conn.execute(
            "create table stock_adjustment_factor(stock_code varchar, trade_date varchar, "
            "adj_factor double, source_version varchar, vendor_version varchar, rule_version varchar, run_id varchar)"
        )
        conn.execute(
            "create table stock_limit_price_daily(stock_code varchar, trade_date varchar, "
            "up_limit double, down_limit double, source_version varchar, vendor_version varchar, "
            "rule_version varchar, run_id varchar)"
        )
        for code in ("A", "B"):
            for day in range(1, 21):
                trade_date = f"2026-06-{day:02d}"
                conn.execute(
                    "insert into choice_stock_daily_observation values (?, ?, 10, ?, 'Trading', "
                    "'12', '8', 'observation', 'vv', 'rv', 'obs_run')",
                    [trade_date, code, 9 if day == 5 else 10],
                )
                conn.execute(
                    "insert into stock_adjustment_factor values (?, ?, 1, 'factor', 'vv', 'rv', 'factor_run')",
                    [code, trade_date],
                )
            conn.execute(
                "insert into stock_limit_price_daily values (?, '2026-06-05', 11, 9, "
                "'limit_day_5', 'vv', 'rv', 'limit_run_5')",
                [code],
            )
        proofs = {
            code: _control_execution_pit_proof(
                conn,
                stock_code=code,
                signal_date="2026-05-31",
                evaluation_as_of_date="2026-06-20",
                source_availability_index=source_index,
            )
            for code in ("A", "B")
        }
    finally:
        conn.close()
    bundle = task._ValidatedBundle(
        path=tmp_path / "bundle.json",
        payload={"evaluation_as_of_date": "2026-06-20"},
        bundle_sha256="",
        calendar_path=tmp_path / "calendar.json",
        calendar_sha256="",
        source_receipt_sha256s=(),
        source_availability_index=source_index,
        zero_certificates={},
        facts=({
            "signal_date": "2026-05-31",
            "stock_code": "A",
            "evidence": {"candidate_source_evidence": proofs["A"]["source_evidence"]},
            "control_pit_proof": {"controls": [{
                "control_stock_code": "B",
                "source_evidence": proofs["B"]["source_evidence"],
            }]},
        },),
        certificates=(),
        summary={},
    )
    return path, bundle


def _admit_synthetic_write(
    monkeypatch: pytest.MonkeyPatch, bundle: task._ValidatedBundle
) -> None:
    """Supply valid approval/backup preconditions without touching a write transaction."""
    target_sha, dry_sha, materialize_sha = "A" * 64, "D" * 64, "E" * 64
    monkeypatch.setattr(task, "_load_receipt", lambda _path, *, expected_kind: (
        {"target_database_sha256_after": target_sha, "bundle_sha256": bundle.bundle_sha256},
        dry_sha if expected_kind == task.DRY_RUN_RECEIPT_KIND else materialize_sha,
    ))
    monkeypatch.setattr(task, "_match_dry_receipt", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(task, "_load_approval", lambda *_args, **_kwargs: ({
        "target_database_sha256": target_sha,
        "dry_run_receipt_sha256": dry_sha,
        "materialize_receipt_sha256": materialize_sha,
    }, "B" * 64))
    monkeypatch.setattr(task, "_assert_approval_target", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(task, "_file_sha256", lambda _path: target_sha)
    monkeypatch.setattr(task, "_verify_prewrite_backup", lambda **_kwargs: {
        "path": Path("C:/Temp/unused-backup.duckdb"), "sha256": target_sha,
    })
    monkeypatch.setattr(task, "acquire_lock", lambda *_args, **_kwargs: nullcontext())


@pytest.mark.parametrize("role", ["candidate", "control"])
@pytest.mark.parametrize("mutation", ["missing_midpoint", "price_label_conflict"])
def test_v4_decisions_match_independent_source_rows(
    tmp_path: Path, role: str, mutation: str
) -> None:
    source_path, original = _source_bundle(tmp_path)
    task._validate_bundle_source_rows(target=source_path, bundle=original)
    changed = copy.deepcopy(original)
    fact = changed.facts[0]
    evidence = (
        fact["evidence"]["candidate_source_evidence"] if role == "candidate"
        else fact["control_pit_proof"]["controls"][0]["source_evidence"]
    )
    decisions = evidence["limit_price"]["exit_5d_decisions"]
    if mutation == "missing_midpoint":
        decisions.pop(0)
    else:
        decisions[0]["down_limit"] = 1
    with pytest.raises(task.CurrentRuleCohortError, match="decision source rows mismatch"):
        task._validate_bundle_source_rows(target=source_path, bundle=changed)


def test_v4_source_rows_fail_closed_when_observations_are_missing(tmp_path: Path) -> None:
    source_path, bundle = _source_bundle(tmp_path)
    conn = duckdb.connect(str(source_path))
    try:
        conn.execute("drop table choice_stock_daily_observation")
    finally:
        conn.close()
    with pytest.raises(task.CurrentRuleCohortError, match="unable to verify decision rows"):
        task._validate_bundle_source_rows(target=source_path, bundle=bundle)


def test_v4_source_version_drift_does_not_use_an_adjacent_row(tmp_path: Path) -> None:
    source_path, bundle = _source_bundle(tmp_path)
    conn = duckdb.connect(str(source_path))
    try:
        conn.execute(
            "update choice_stock_daily_observation set source_version = 'unproven' "
            "where stock_code = 'A' and trade_date = '2026-06-05'"
        )
    finally:
        conn.close()
    with pytest.raises(task.CurrentRuleCohortError, match="candidate decision source rows mismatch"):
        task._validate_bundle_source_rows(target=source_path, bundle=bundle)


def test_locked_source_read_closes_before_writable_connection(tmp_path: Path) -> None:
    source_path, bundle = _source_bundle(tmp_path)
    with acquire_lock(resolve_duckdb_writer_lock(source_path), base_dir=source_path.parent):
        task._validate_bundle_source_rows(target=source_path, bundle=bundle)
        conn = duckdb.connect(str(source_path))
        try:
            assert conn.execute("select count(*) from choice_stock_daily_observation").fetchone() == (40,)
        finally:
            conn.close()


@pytest.mark.parametrize("validator", [
    task._validate_exact_candidate_source_evidence,
    task._validate_exact_control_source_evidence,
    producer._validate_exact_candidate_source_evidence,
    producer._validate_exact_control_source_evidence,
])
def test_v4_price_label_conflict_rejected_by_each_structural_entry(
    tmp_path: Path, validator
) -> None:
    _, bundle = _source_bundle(tmp_path)
    evidence = copy.deepcopy(bundle.facts[0]["evidence"]["candidate_source_evidence"])
    kwargs = {
        "source_index": bundle.source_availability_index,
        "evaluation": "2026-06-20",
        "entry_date": "2026-06-01",
        "exit_date_5d": "2026-06-06",
        "exit_date_20d": "2026-06-20",
    }
    validator(evidence, **kwargs)
    evidence["limit_price"]["exit_5d_decisions"][0]["down_limit"] = 1
    with pytest.raises(task.CurrentRuleCohortError, match="decision contradicts price"):
        validator(evidence, **kwargs)


@pytest.mark.parametrize("entry", ["dry_run", "materialize", "promote"])
def test_target_identity_precedes_source_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entry: str
) -> None:
    source_path, bundle = _source_bundle(tmp_path)
    monkeypatch.setattr(task, "_load_and_validate_bundle", lambda _path: bundle)
    source_read = []
    monkeypatch.setattr(
        task, "_validate_bundle_source_rows", lambda **_kwargs: source_read.append(True)
    )

    def reject_identity(**_kwargs) -> None:
        raise task.CurrentRuleCohortError("target identity mismatch")

    monkeypatch.setattr(task, "_assert_bundle_target_identity", reject_identity)
    common = {"duckdb_path": source_path, "bundle_path": bundle.path, "created_at": "2026-06-20T12:00:00+08:00"}
    if entry == "dry_run":
        call = task.build_stock_analysis_current_rule_cohort_dry_run
        args = {"receipt_path": tmp_path / "dry.json"}
    elif entry == "materialize":
        call = task.materialize_stock_analysis_current_rule_cohort
        args = {
            "dry_run_receipt_path": tmp_path / "dry.json",
            "approval_artifact_path": tmp_path / "approval.json",
            "target_backup_path": tmp_path / "backup.duckdb",
            "receipt_path": tmp_path / "materialize.json",
            "allow_write": True,
        }
    else:
        call = task.promote_stock_analysis_current_rule_cohort
        args = {
            "materialize_receipt_path": tmp_path / "materialize.json",
            "approval_artifact_path": tmp_path / "approval.json",
            "receipt_path": tmp_path / "promote.json",
            "allow_write": True,
        }
    with pytest.raises(task.CurrentRuleCohortError, match="target identity mismatch"):
        call(**common, **args)
    assert source_read == []


@pytest.mark.parametrize("entry", ["dry_run", "materialize", "promote"])
@pytest.mark.parametrize("role", ["candidate", "control"])
@pytest.mark.parametrize("mutation", ["missing_midpoint", "price_label_conflict"])
def test_operational_entry_rejects_source_row_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entry: str, role: str, mutation: str
) -> None:
    source_path, bundle = _source_bundle(tmp_path)
    fact = bundle.facts[0]
    evidence = (
        fact["evidence"]["candidate_source_evidence"] if role == "candidate"
        else fact["control_pit_proof"]["controls"][0]["source_evidence"]
    )
    decisions = evidence["limit_price"]["exit_5d_decisions"]
    if mutation == "missing_midpoint":
        decisions.pop(0)
    else:
        decisions[0]["down_limit"] = 1
    monkeypatch.setattr(task, "_load_and_validate_bundle", lambda _path: bundle)
    # The separate identity-order test covers the boundary before this source-row gate.
    monkeypatch.setattr(task, "_assert_bundle_target_identity", lambda **_kwargs: None)
    common = {"duckdb_path": source_path, "bundle_path": bundle.path, "created_at": "2026-06-20T12:00:00+08:00"}
    if entry == "dry_run":
        call = task.build_stock_analysis_current_rule_cohort_dry_run
        args = {"receipt_path": tmp_path / "dry.json"}
    elif entry == "materialize":
        _admit_synthetic_write(monkeypatch, bundle)
        call = task.materialize_stock_analysis_current_rule_cohort
        args = {
            "dry_run_receipt_path": tmp_path / "dry.json",
            "approval_artifact_path": tmp_path / "approval.json",
            "target_backup_path": tmp_path / "backup.duckdb",
            "receipt_path": tmp_path / "materialize.json",
            "allow_write": True,
        }
    else:
        _admit_synthetic_write(monkeypatch, bundle)
        call = task.promote_stock_analysis_current_rule_cohort
        args = {
            "materialize_receipt_path": tmp_path / "materialize.json",
            "approval_artifact_path": tmp_path / "approval.json",
            "receipt_path": tmp_path / "promote.json",
            "allow_write": True,
        }
    with pytest.raises(task.CurrentRuleCohortError, match="decision source rows mismatch"):
        call(**common, **args)


@pytest.mark.parametrize("entry", ["materialize", "promote"])
def test_source_rows_are_rechecked_after_writer_lock_acquisition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entry: str
) -> None:
    source_path, bundle = _source_bundle(tmp_path)
    monkeypatch.setattr(task, "_load_and_validate_bundle", lambda _path: bundle)
    monkeypatch.setattr(task, "_assert_bundle_target_identity", lambda **_kwargs: None)
    _admit_synthetic_write(monkeypatch, bundle)
    entered_lock = []
    backup_reached = []
    monkeypatch.setattr(
        task, "_verify_prewrite_backup",
        lambda **_kwargs: backup_reached.append(True),
    )

    @contextmanager
    def mutate_before_lock_yields(*_args, **_kwargs):
        conn = duckdb.connect(str(source_path))
        try:
            conn.execute(
                "update choice_stock_daily_observation set source_version = 'unproven' "
                "where stock_code = 'A' and trade_date = '2026-06-05'"
            )
        finally:
            conn.close()
        entered_lock.append(True)
        yield

    monkeypatch.setattr(task, "acquire_lock", mutate_before_lock_yields)
    common = {"duckdb_path": source_path, "bundle_path": bundle.path, "created_at": "2026-06-20T12:00:00+08:00"}
    if entry == "materialize":
        call = task.materialize_stock_analysis_current_rule_cohort
        args = {
            "dry_run_receipt_path": tmp_path / "dry.json",
            "approval_artifact_path": tmp_path / "approval.json",
            "target_backup_path": tmp_path / "backup.duckdb",
            "receipt_path": tmp_path / "materialize.json",
            "allow_write": True,
        }
    else:
        call = task.promote_stock_analysis_current_rule_cohort
        args = {
            "materialize_receipt_path": tmp_path / "materialize.json",
            "approval_artifact_path": tmp_path / "approval.json",
            "receipt_path": tmp_path / "promote.json",
            "allow_write": True,
        }
    with pytest.raises(task.CurrentRuleCohortError, match="candidate decision source rows mismatch"):
        call(**common, **args)
    assert entered_lock == [True]
    assert backup_reached == []


@pytest.mark.parametrize("entry", ["materialize", "promote"])
def test_idempotent_replay_rejects_source_row_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, entry: str
) -> None:
    source_path, bundle = _source_bundle(tmp_path)
    conn = duckdb.connect(str(source_path))
    try:
        conn.execute(
            "update choice_stock_daily_observation set source_version = 'unproven' "
            "where stock_code = 'A' and trade_date = '2026-06-05'"
        )
    finally:
        conn.close()
    monkeypatch.setattr(task, "_load_and_validate_bundle", lambda _path: bundle)
    monkeypatch.setattr(task, "_assert_bundle_target_identity", lambda **_kwargs: None)
    _admit_synthetic_write(monkeypatch, bundle)
    monkeypatch.setattr(task, "_file_sha256", lambda _path: "C" * 64)
    common = {"duckdb_path": source_path, "bundle_path": bundle.path, "created_at": "2026-06-20T12:00:00+08:00"}
    if entry == "materialize":
        monkeypatch.setattr(task, "_exact_existing_materialization", lambda *_args, **_kwargs: {
            "backup_path": str(tmp_path / "backup.duckdb"),
        })
        call = task.materialize_stock_analysis_current_rule_cohort
        args = {
            "dry_run_receipt_path": tmp_path / "dry.json",
            "approval_artifact_path": tmp_path / "approval.json",
            "target_backup_path": tmp_path / "backup.duckdb",
            "receipt_path": tmp_path / "materialize.json",
            "allow_write": True,
        }
    else:
        monkeypatch.setattr(task, "_promotion_already_applied", lambda *_args, **_kwargs: (True, None))
        call = task.promote_stock_analysis_current_rule_cohort
        args = {
            "materialize_receipt_path": tmp_path / "materialize.json",
            "approval_artifact_path": tmp_path / "approval.json",
            "receipt_path": tmp_path / "promote.json",
            "allow_write": True,
        }
    with pytest.raises(task.CurrentRuleCohortError, match="candidate decision source rows mismatch"):
        call(**common, **args)
