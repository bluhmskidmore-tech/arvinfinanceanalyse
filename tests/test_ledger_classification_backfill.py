from __future__ import annotations

import hashlib
from pathlib import Path

import duckdb
import pytest


def test_backfill_requires_explicit_batches_and_source_dir(tmp_path: Path) -> None:
    from backend.app.tasks.ledger_classification_backfill import build_backfill_plan

    with pytest.raises(ValueError, match="batch"):
        build_backfill_plan(tmp_path / "missing.duckdb", [], tmp_path)
    with pytest.raises(ValueError, match="source"):
        build_backfill_plan(tmp_path / "missing.duckdb", [1], tmp_path / "missing")


def test_repository_backfill_writer_requires_task_scope(tmp_path: Path) -> None:
    from backend.app.repositories.ledger_import_repo import LedgerImportRepository

    db = tmp_path / "guard.duckdb"
    conn = duckdb.connect(str(db))
    conn.close()
    with pytest.raises(PermissionError, match="task write scope"):
        LedgerImportRepository(str(db)).attest_classification_rule_versions(
            batch_ids=[1],
            from_rule_versions={1: "rv_ledger_import_v1"},
            target_rule_version="rv_ledger_classification_v2",
            expected_immutable_evidence_digest="irrelevant",
        )


def test_file_fingerprint_is_stable_and_sensitive(tmp_path: Path) -> None:
    from backend.app.tasks.ledger_classification_backfill import file_fingerprint

    path = tmp_path / "db.duckdb"
    path.write_bytes(b"abc")
    first = file_fingerprint(path)
    assert first["sha256"] == hashlib.sha256(b"abc").hexdigest()
    assert first["size"] == 3
    path.write_bytes(b"abcd")
    assert file_fingerprint(path)["sha256"] != first["sha256"]

def _csv_source(
    *,
    account_category: str = "银行账户",
    asset_class: str = "持有至到期类资产",
    bond_code: str = "BOND-1",
    row_count: int = 1,
) -> bytes:
    import csv
    import io
    from backend.app.services import ledger_import_service as service

    values = {
        "bond_code": bond_code,
        "bond_name": "Bond One",
        "portfolio": "P1",
        "as_of_date": "2026-01-31",
        "account_category_std": account_category,
        "asset_class_std": asset_class,
        "face_amount": "100000000",
        "currency": "CNY",
    }
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["ZQTZSHOW"])
    writer.writerow([spec.source_field for spec in service.FIELD_SPECS])
    for _ in range(row_count):
        writer.writerow([values.get(spec.standard_field, "") for spec in service.FIELD_SPECS])
    return output.getvalue().encode("utf-8-sig")


def _seed_replayable_legacy_db(
    db: Path,
    source_dir: Path,
    *,
    account_category: str = "银行账户",
    asset_class: str = "持有至到期类资产",
    row_count: int = 1,
) -> Path:
    from backend.app.repositories.ledger_import_repo import LedgerImportRepository
    from backend.app.repositories.task_write_guard import repository_task_write_scope
    from backend.app.services.ledger_import_service import parse_ledger_file

    source = source_dir / "renamed-source.csv"
    source.write_bytes(_csv_source(account_category=account_category, asset_class=asset_class, row_count=row_count))
    parsed = parse_ledger_file(file_name=source.name, content=source.read_bytes())
    with repository_task_write_scope("backend.app.tasks.test_ledger_backfill"):
        LedgerImportRepository(str(db)).insert_import(
            file_name="original-name-does-not-matter.csv",
            file_hash=parsed.file_hash,
            as_of_date=parsed.as_of_date,
            rows=parsed.rows,
            source_version=parsed.source_version,
            rule_version=parsed.rows[0]["rule_version"],
        )
    conn = duckdb.connect(str(db))
    try:
        for table in ("ledger_import_batch", "ledger_raw_row", "position_snapshot"):
            conn.execute(f"update {table} set rule_version = 'position_key_contract_v1'")
    finally:
        conn.close()
    return source


def test_dry_run_replays_source_without_writing_and_has_stable_digest(tmp_path: Path) -> None:
    from backend.app.tasks.ledger_classification_backfill import build_backfill_plan, file_fingerprint

    db = tmp_path / "moss.duckdb"
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    _seed_replayable_legacy_db(db, source_dir)
    before = file_fingerprint(db)
    first = build_backfill_plan(db, [1], source_dir)
    second = build_backfill_plan(db, [1], source_dir)
    assert first == second
    assert file_fingerprint(db) == before
    assert first["row_count"] == 1
    assert first["direction_counts"] == {"ASSET": 1}
    assert first["transition_matrix"] == {"ASSET->ASSET": 1}
    assert first["direction_changes"] == 0
    assert first["trace_complete"] is True
    assert first["source_replay_complete"] is True
    assert first["planned_updates"] == {"batches": 1, "raw_rows": 1, "snapshot_rows": 1}
    assert "raw_json" not in str(first)


def test_apply_requires_matching_backup_and_updates_only_rule_lineage(tmp_path: Path) -> None:
    import shutil
    from backend.app.tasks.ledger_classification_backfill import apply_backfill_plan, build_backfill_plan

    db = tmp_path / "moss.duckdb"
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    _seed_replayable_legacy_db(db, source_dir)
    plan = build_backfill_plan(db, [1], source_dir)
    conn = duckdb.connect(str(db), read_only=True)
    before = conn.execute("select direction, position_key, face_amount from position_snapshot").fetchall()
    conn.close()
    backup = tmp_path / "moss.backup.duckdb"
    shutil.copy2(db, backup)
    receipt_path = tmp_path / "receipt.json"
    receipt = apply_backfill_plan(
        db_path=db,
        batch_ids=[1],
        source_dir=source_dir,
        expected_plan_digest=plan["plan_digest"],
        target_backup_path=backup,
        receipt_path=receipt_path,
    )
    assert receipt["status"] == "completed"
    assert receipt_path.exists()
    conn = duckdb.connect(str(db), read_only=True)
    try:
        versions = {
            conn.execute(f"select distinct rule_version from {table}").fetchone()[0]
            for table in ("ledger_import_batch", "ledger_raw_row", "position_snapshot")
        }
        after = conn.execute("select direction, position_key, face_amount from position_snapshot").fetchall()
    finally:
        conn.close()
    assert versions == {"rv_ledger_classification_v2"}
    assert after == before
    current = build_backfill_plan(db, [1], source_dir)
    assert current["planned_updates"] == {"batches": 0, "raw_rows": 0, "snapshot_rows": 0}

def test_plan_blocks_duplicate_source_hash_and_direction_change(tmp_path: Path) -> None:
    from backend.app.tasks.ledger_classification_backfill import build_backfill_plan

    db = tmp_path / "moss.duckdb"
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    source = _seed_replayable_legacy_db(db, source_dir)
    duplicate = source_dir / "duplicate.csv"
    duplicate.write_bytes(source.read_bytes())
    with pytest.raises(ValueError, match="exactly one source hash match"):
        build_backfill_plan(db, [1], source_dir)
    duplicate.unlink()
    conn = duckdb.connect(str(db))
    conn.execute("update position_snapshot set direction = 'LIABILITY'")
    conn.close()
    with pytest.raises(ValueError, match="direction would change"):
        build_backfill_plan(db, [1], source_dir)


def test_apply_is_idempotent_for_already_current_batch(tmp_path: Path) -> None:
    import shutil
    from backend.app.tasks.ledger_classification_backfill import (
        apply_backfill_plan,
        build_backfill_plan,
        file_fingerprint,
    )

    db = tmp_path / "moss.duckdb"
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    _seed_replayable_legacy_db(db, source_dir)
    first_plan = build_backfill_plan(db, [1], source_dir)
    first_backup = tmp_path / "first.backup.duckdb"
    shutil.copy2(db, first_backup)
    apply_backfill_plan(
        db_path=db,
        batch_ids=[1],
        source_dir=source_dir,
        expected_plan_digest=first_plan["plan_digest"],
        target_backup_path=first_backup,
        receipt_path=tmp_path / "first.receipt.json",
    )
    current_plan = build_backfill_plan(db, [1], source_dir)
    second_backup = tmp_path / "second.backup.duckdb"
    shutil.copy2(db, second_backup)
    before = file_fingerprint(db)
    second = apply_backfill_plan(
        db_path=db,
        batch_ids=[1],
        source_dir=source_dir,
        expected_plan_digest=current_plan["plan_digest"],
        target_backup_path=second_backup,
        receipt_path=tmp_path / "second.receipt.json",
    )
    assert second["applied_updates"] == {
        "batches_updated": 0,
        "raw_rows_updated": 0,
        "snapshot_rows_updated": 0,
        "position_snapshot_agg_unchanged": True,
    }
    assert file_fingerprint(db) == before

def test_apply_uses_global_then_ledger_lock_order(tmp_path: Path, monkeypatch) -> None:
    import shutil
    from contextlib import contextmanager
    from backend.app.tasks import ledger_classification_backfill as task

    db = tmp_path / "moss.duckdb"
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    _seed_replayable_legacy_db(db, source_dir)
    plan = task.build_backfill_plan(db, [1], source_dir)
    backup = tmp_path / "backup.duckdb"
    shutil.copy2(db, backup)
    acquired = []

    @contextmanager
    def recording_lock(definition, **_kwargs):
        acquired.append(definition.key)
        yield tmp_path / "lock"

    monkeypatch.setattr(task, "acquire_lock", recording_lock)
    task.apply_backfill_plan(
        db_path=db,
        batch_ids=[1],
        source_dir=source_dir,
        expected_plan_digest=plan["plan_digest"],
        target_backup_path=backup,
        receipt_path=tmp_path / "receipt.json",
    )
    assert acquired[0].startswith("lock:duckdb:materialize:")
    assert acquired[1] == "lock:duckdb:ledger-import"


def test_repository_postcheck_failure_rolls_back_all_versions(tmp_path: Path, monkeypatch) -> None:
    from backend.app.repositories import ledger_import_repo as repo_mod
    from backend.app.repositories.task_write_guard import repository_task_write_scope
    from backend.app.tasks.ledger_classification_backfill import build_backfill_plan

    db = tmp_path / "moss.duckdb"
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    _seed_replayable_legacy_db(db, source_dir)
    plan = build_backfill_plan(db, [1], source_dir)
    real_evidence = repo_mod.classification_immutable_evidence
    calls = 0

    def fail_postcheck(conn, batch_ids):
        nonlocal calls
        calls += 1
        value = real_evidence(conn, batch_ids)
        if calls == 1:
            return value
        return {**value, "digest": "forced-postcheck-failure"}

    monkeypatch.setattr(repo_mod, "classification_immutable_evidence", fail_postcheck)
    with repository_task_write_scope("backend.app.tasks.test_ledger_backfill"):
        with pytest.raises(RuntimeError, match="transaction rolled back"):
            repo_mod.LedgerImportRepository(str(db)).attest_classification_rule_versions(
                batch_ids=[1],
                from_rule_versions={1: "position_key_contract_v1"},
                target_rule_version="rv_ledger_classification_v2",
                expected_immutable_evidence_digest=plan["immutable_evidence_digest"],
            )
    conn = duckdb.connect(str(db), read_only=True)
    try:
        versions = [
            conn.execute(f"select distinct rule_version from {table}").fetchone()[0]
            for table in ("ledger_import_batch", "ledger_raw_row", "position_snapshot")
        ]
    finally:
        conn.close()
    assert versions == ["position_key_contract_v1"] * 3

def test_apply_rejects_backup_hardlink_to_target(tmp_path: Path) -> None:
    import os
    from backend.app.tasks.ledger_classification_backfill import apply_backfill_plan, build_backfill_plan

    db = tmp_path / "moss.duckdb"
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    _seed_replayable_legacy_db(db, source_dir)
    plan = build_backfill_plan(db, [1], source_dir)
    backup = tmp_path / "hardlink.duckdb"
    try:
        os.link(db, backup)
    except OSError as exc:
        pytest.skip(f"hard links unavailable: {exc}")
    with pytest.raises(ValueError, match="hard link"):
        apply_backfill_plan(
            db_path=db,
            batch_ids=[1],
            source_dir=source_dir,
            expected_plan_digest=plan["plan_digest"],
            target_backup_path=backup,
            receipt_path=tmp_path / "receipt.json",
        )


def test_source_drift_after_prepared_receipt_blocks_with_zero_db_writes(tmp_path: Path, monkeypatch) -> None:
    import json
    import shutil
    from backend.app.tasks import ledger_classification_backfill as task

    db = tmp_path / "moss.duckdb"
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    source = _seed_replayable_legacy_db(db, source_dir)
    plan = task.build_backfill_plan(db, [1], source_dir)
    backup = tmp_path / "backup.duckdb"
    shutil.copy2(db, backup)
    receipt = tmp_path / "receipt.json"
    real_write = task._write_prepared_receipt

    def drift_after_prepared(path, payload):
        real_write(path, payload)
        source.write_bytes(source.read_bytes() + b"drift")

    monkeypatch.setattr(task, "_write_prepared_receipt", drift_after_prepared)
    with pytest.raises(RuntimeError, match="Source file drifted"):
        task.apply_backfill_plan(
            db_path=db,
            batch_ids=[1],
            source_dir=source_dir,
            expected_plan_digest=plan["plan_digest"],
            target_backup_path=backup,
            receipt_path=receipt,
        )
    assert json.loads(receipt.read_text(encoding="utf-8"))["status"] == "prepared"
    conn = duckdb.connect(str(db), read_only=True)
    try:
        assert conn.execute("select distinct rule_version from ledger_import_batch").fetchone()[0] == "position_key_contract_v1"
    finally:
        conn.close()


def test_source_drift_after_commit_does_not_turn_completion_into_rollback_failure(tmp_path: Path, monkeypatch) -> None:
    import json
    import shutil
    from backend.app.repositories.ledger_import_repo import LedgerImportRepository
    from backend.app.tasks import ledger_classification_backfill as task

    db = tmp_path / "moss.duckdb"
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    source = _seed_replayable_legacy_db(db, source_dir)
    plan = task.build_backfill_plan(db, [1], source_dir)
    backup = tmp_path / "backup.duckdb"
    shutil.copy2(db, backup)
    receipt = tmp_path / "receipt.json"
    real_apply = LedgerImportRepository.attest_classification_rule_versions

    def apply_then_drift(self, **kwargs):
        result = real_apply(self, **kwargs)
        source.write_bytes(source.read_bytes() + b"post-commit-drift")
        return result

    monkeypatch.setattr(LedgerImportRepository, "attest_classification_rule_versions", apply_then_drift)
    completed = task.apply_backfill_plan(
        db_path=db,
        batch_ids=[1],
        source_dir=source_dir,
        expected_plan_digest=plan["plan_digest"],
        target_backup_path=backup,
        receipt_path=receipt,
    )
    assert completed["status"] == "completed"
    assert json.loads(receipt.read_text(encoding="utf-8"))["status"] == "completed"


def test_prepared_receipt_creation_is_exclusive_under_race(tmp_path: Path, monkeypatch) -> None:
    import shutil
    from backend.app.tasks import ledger_classification_backfill as task

    db = tmp_path / "moss.duckdb"
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    _seed_replayable_legacy_db(db, source_dir)
    plan = task.build_backfill_plan(db, [1], source_dir)
    backup = tmp_path / "backup.duckdb"
    shutil.copy2(db, backup)
    receipt = tmp_path / "receipt.json"
    real_build = task.build_backfill_plan

    def race_receipt(*args, **kwargs):
        result = real_build(*args, **kwargs)
        receipt.write_text("racer", encoding="utf-8")
        return result

    monkeypatch.setattr(task, "build_backfill_plan", race_receipt)
    with pytest.raises(FileExistsError):
        task.apply_backfill_plan(
            db_path=db,
            batch_ids=[1],
            source_dir=source_dir,
            expected_plan_digest=plan["plan_digest"],
            target_backup_path=backup,
            receipt_path=receipt,
        )
    assert receipt.read_text(encoding="utf-8") == "racer"
    conn = duckdb.connect(str(db), read_only=True)
    try:
        assert conn.execute("select distinct rule_version from ledger_import_batch").fetchone()[0] == "position_key_contract_v1"
    finally:
        conn.close()


def test_position_snapshot_agg_is_in_immutable_evidence_and_remains_unchanged(tmp_path: Path) -> None:
    import shutil
    from backend.app.tasks.ledger_classification_backfill import apply_backfill_plan, build_backfill_plan

    db = tmp_path / "moss.duckdb"
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    _seed_replayable_legacy_db(db, source_dir)
    conn = duckdb.connect(str(db))
    try:
        conn.execute(
            "insert into position_snapshot_agg values (1, '2026-01-31', 1, 1, 0, 100000000, 0, 100000000, 'sv', 'legacy-agg-rule', '2026-02-01')"
        )
    finally:
        conn.close()
    plan = build_backfill_plan(db, [1], source_dir)
    assert plan["position_snapshot_agg_evidence"]["table_present"] is True
    assert plan["position_snapshot_agg_evidence"]["row_count"] == 1
    backup = tmp_path / "backup.duckdb"
    shutil.copy2(db, backup)
    completed = apply_backfill_plan(
        db_path=db,
        batch_ids=[1],
        source_dir=source_dir,
        expected_plan_digest=plan["plan_digest"],
        target_backup_path=backup,
        receipt_path=tmp_path / "receipt.json",
    )
    assert completed["position_snapshot_agg_unchanged"] is True
    conn = duckdb.connect(str(db), read_only=True)
    try:
        assert conn.execute("select rule_version, asset_face_amount from position_snapshot_agg").fetchall() == [("legacy-agg-rule", 100000000)]
    finally:
        conn.close()


def test_finalize_failure_leaves_prepared_receipt_and_committed_attestation(tmp_path: Path, monkeypatch) -> None:
    import json
    import shutil
    from backend.app.tasks import ledger_classification_backfill as task

    db = tmp_path / "moss.duckdb"
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    _seed_replayable_legacy_db(db, source_dir)
    plan = task.build_backfill_plan(db, [1], source_dir)
    backup = tmp_path / "backup.duckdb"
    shutil.copy2(db, backup)
    receipt = tmp_path / "receipt.json"
    monkeypatch.setattr(task, "_replace_receipt", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("finalize failed")))
    with pytest.raises(OSError, match="finalize failed"):
        task.apply_backfill_plan(
            db_path=db,
            batch_ids=[1],
            source_dir=source_dir,
            expected_plan_digest=plan["plan_digest"],
            target_backup_path=backup,
            receipt_path=receipt,
        )
    assert json.loads(receipt.read_text(encoding="utf-8"))["status"] == "prepared"
    conn = duckdb.connect(str(db), read_only=True)
    try:
        assert conn.execute("select distinct rule_version from ledger_import_batch").fetchone()[0] == "rv_ledger_classification_v2"
    finally:
        conn.close()

@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("update ledger_import_batch set status = 'failed'", "not an error-free successful import"),
        ("update ledger_import_batch set error_count = 1", "not an error-free successful import"),
        ("update ledger_import_batch set as_of_date = '2026-02-01'", "date/row count mismatch"),
        ("update ledger_import_batch set source_version = 'sv_wrong'", "source version"),
        ("update ledger_raw_row set raw_json = '{bad-json}'", "raw replay mismatch"),
        ("update ledger_raw_row set rule_version = 'rv_other'", "raw lineage mismatch"),
        ("delete from ledger_raw_row", "three-table row counts"),
        ("update ledger_raw_row set row_no = 2", "key sets do not tie"),
        ("update position_snapshot set bond_code = 'TAMPERED'", "replay mismatch in bond_code"),
        ("update position_snapshot set position_key = 'tampered'", "replay mismatch in position_key"),
        ("update position_snapshot set rule_version = 'rv_other'", "snapshot rule lineage mismatch"),
        ("update position_snapshot set direction = 'UNCLASSIFIED'", "direction would change"),
    ],
)
def test_plan_blocks_each_material_lineage_mismatch(tmp_path: Path, mutation: str, message: str) -> None:
    from backend.app.tasks.ledger_classification_backfill import build_backfill_plan

    db = tmp_path / "moss.duckdb"
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    _seed_replayable_legacy_db(db, source_dir)
    conn = duckdb.connect(str(db))
    try:
        conn.execute(mutation)
    finally:
        conn.close()
    with pytest.raises(ValueError, match=message):
        build_backfill_plan(db, [1], source_dir)


def test_plan_blocks_missing_duplicate_batch_ids_and_unclassified_replay(tmp_path: Path) -> None:
    from backend.app.tasks.ledger_classification_backfill import build_backfill_plan

    db = tmp_path / "moss.duckdb"
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    _seed_replayable_legacy_db(db, source_dir)
    with pytest.raises(ValueError, match="Missing batch"):
        build_backfill_plan(db, [2], source_dir)
    with pytest.raises(ValueError, match="Duplicate batch"):
        build_backfill_plan(db, [1, 1], source_dir)

    other_db = tmp_path / "unclassified.duckdb"
    other_sources = tmp_path / "unclassified-sources"
    other_sources.mkdir()
    _seed_replayable_legacy_db(other_db, other_sources, asset_class="未知分类")
    with pytest.raises(ValueError, match="unknown or conflicting classification"):
        build_backfill_plan(other_db, [1], other_sources)


def test_duplicate_position_keys_are_allowed_but_rows_remain_batch_row_scoped(tmp_path: Path) -> None:
    from backend.app.tasks.ledger_classification_backfill import build_backfill_plan

    db = tmp_path / "moss.duckdb"
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    _seed_replayable_legacy_db(db, source_dir, row_count=2)
    plan = build_backfill_plan(db, [1], source_dir)
    assert plan["row_count"] == 2
    assert plan["batches"][0]["position_key_duplicate_groups"] == 1
    conn = duckdb.connect(str(db), read_only=True)
    try:
        assert conn.execute("select count(distinct position_key), count(distinct row_no) from position_snapshot").fetchone() == (1, 2)
    finally:
        conn.close()


@pytest.mark.parametrize("stage", ["position_snapshot", "ledger_raw_row", "ledger_import_batch"])
def test_each_repository_update_stage_failure_rolls_back(tmp_path: Path, monkeypatch, stage: str) -> None:
    from backend.app.repositories import ledger_import_repo as repo_mod
    from backend.app.repositories.task_write_guard import repository_task_write_scope
    from backend.app.tasks.ledger_classification_backfill import build_backfill_plan

    db = tmp_path / "moss.duckdb"
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    _seed_replayable_legacy_db(db, source_dir)
    plan = build_backfill_plan(db, [1], source_dir)
    original_connect = repo_mod.duckdb.connect

    class FailingConnection:
        def __init__(self, conn):
            self._conn = conn

        def execute(self, sql, params=None):
            if str(sql).strip().lower().startswith(f"update {stage}"):
                raise RuntimeError(f"forced {stage} failure")
            return self._conn.execute(sql, params) if params is not None else self._conn.execute(sql)

        def __getattr__(self, name):
            return getattr(self._conn, name)

    monkeypatch.setattr(repo_mod.duckdb, "connect", lambda *args, **kwargs: FailingConnection(original_connect(*args, **kwargs)))
    with repository_task_write_scope("backend.app.tasks.test_ledger_backfill"):
        with pytest.raises(RuntimeError, match=f"forced {stage} failure"):
            repo_mod.LedgerImportRepository(str(db)).attest_classification_rule_versions(
                batch_ids=[1],
                from_rule_versions={1: "position_key_contract_v1"},
                target_rule_version="rv_ledger_classification_v2",
                expected_immutable_evidence_digest=plan["immutable_evidence_digest"],
            )
    conn = original_connect(str(db), read_only=True)
    try:
        assert [
            conn.execute(f"select distinct rule_version from {table}").fetchone()[0]
            for table in ("ledger_import_batch", "ledger_raw_row", "position_snapshot")
        ] == ["position_key_contract_v1"] * 3
    finally:
        conn.close()

def _apply_case(tmp_path: Path):
    import shutil
    from backend.app.tasks.ledger_classification_backfill import build_backfill_plan

    db = tmp_path / "moss.duckdb"
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    _seed_replayable_legacy_db(db, source_dir)
    plan = build_backfill_plan(db, [1], source_dir)
    backup = tmp_path / "backup.duckdb"
    shutil.copy2(db, backup)
    return db, source_dir, plan, backup


def test_apply_rejects_wrong_digest_backup_self_missing_mismatch_and_existing_receipt(tmp_path: Path) -> None:
    from backend.app.tasks.ledger_classification_backfill import apply_backfill_plan

    db, source_dir, plan, backup = _apply_case(tmp_path)
    base = dict(db_path=db, batch_ids=[1], source_dir=source_dir, expected_plan_digest=plan["plan_digest"])
    with pytest.raises(RuntimeError, match="plan digest"):
        apply_backfill_plan(**{**base, "expected_plan_digest": "wrong"}, target_backup_path=backup, receipt_path=tmp_path / "wrong.json")
    with pytest.raises(ValueError, match="target database"):
        apply_backfill_plan(**base, target_backup_path=db, receipt_path=tmp_path / "self.json")
    with pytest.raises(ValueError, match="already exist"):
        apply_backfill_plan(**base, target_backup_path=tmp_path / "missing.duckdb", receipt_path=tmp_path / "missing.json")
    mismatch = tmp_path / "mismatch.duckdb"
    mismatch.write_bytes(b"not-the-target")
    with pytest.raises(ValueError, match="hash and size"):
        apply_backfill_plan(**base, target_backup_path=mismatch, receipt_path=tmp_path / "mismatch.json")
    existing = tmp_path / "existing.json"
    existing.write_text("keep", encoding="utf-8")
    with pytest.raises(ValueError, match="must not already exist"):
        apply_backfill_plan(**base, target_backup_path=backup, receipt_path=existing)
    assert existing.read_text(encoding="utf-8") == "keep"


def test_db_preimage_drift_after_locked_plan_blocks_before_receipt(tmp_path: Path, monkeypatch) -> None:
    from backend.app.tasks import ledger_classification_backfill as task

    db, source_dir, plan, backup = _apply_case(tmp_path)
    real_build = task.build_backfill_plan

    def drift_after_locked_plan(*args, **kwargs):
        result = real_build(*args, **kwargs)
        with db.open("ab") as handle:
            handle.write(b"drift")
        return result

    monkeypatch.setattr(task, "build_backfill_plan", drift_after_locked_plan)
    receipt = tmp_path / "receipt.json"
    with pytest.raises(RuntimeError, match="preimage drifted"):
        task.apply_backfill_plan(
            db_path=db,
            batch_ids=[1],
            source_dir=source_dir,
            expected_plan_digest=plan["plan_digest"],
            target_backup_path=backup,
            receipt_path=receipt,
        )
    assert not receipt.exists()


def test_cli_dry_run_requires_explicit_args_and_never_prints_raw_json(tmp_path: Path, capsys) -> None:
    from backend.app.tasks.ledger_classification_backfill import main

    db, source_dir, _plan, _backup = _apply_case(tmp_path)
    with pytest.raises(SystemExit):
        main(["--db-path", str(db), "--source-dir", str(source_dir)])
    assert main(["--db-path", str(db), "--source-dir", str(source_dir), "--batch-id", "1"]) == 0
    output = capsys.readouterr().out
    assert '"batch_count": 1' in output
    assert "raw_json" not in output
    with pytest.raises(ValueError, match="target backup and receipt"):
        main(["--db-path", str(db), "--source-dir", str(source_dir), "--batch-id", "1", "--apply"])


def test_apply_uses_canonical_task_scope_when_module_runs_as_main(tmp_path: Path, monkeypatch) -> None:
    from backend.app.tasks import ledger_classification_backfill as task

    db, source_dir, plan, backup = _apply_case(tmp_path)
    receipt = tmp_path / "receipt.json"
    monkeypatch.setitem(task.__dict__, "__name__", "__main__")

    completed = task.apply_backfill_plan(
        db_path=db,
        batch_ids=[1],
        source_dir=source_dir,
        expected_plan_digest=plan["plan_digest"],
        target_backup_path=backup,
        receipt_path=receipt,
    )

    assert completed["status"] == "completed"
    assert completed["applied_updates"] == {
        "batches_updated": 1,
        "raw_rows_updated": 1,
        "snapshot_rows_updated": 1,
        "position_snapshot_agg_unchanged": True,
    }


def test_multi_batch_postcheck_failure_is_all_or_none(tmp_path: Path, monkeypatch) -> None:
    from backend.app.repositories import ledger_import_repo as repo_mod
    from backend.app.repositories.task_write_guard import repository_task_write_scope

    db = tmp_path / "moss.duckdb"
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    _seed_replayable_legacy_db(db, source_dir)
    conn = duckdb.connect(str(db))
    try:
        conn.execute(
            "insert into ledger_import_batch select 2, 'second.csv', ?, as_of_date, status, row_count, error_count, ?, rule_version, null, created_at from ledger_import_batch where batch_id = 1",
            ["sha256:" + "b" * 64, "sv_ledger_" + "b" * 12],
        )
        conn.execute(
            "insert into ledger_raw_row select 2, row_no, raw_json, ?, rule_version from ledger_raw_row where batch_id = 1",
            ["sv_ledger_" + "b" * 12],
        )
        conn.execute(
            "insert into position_snapshot select * replace (2 as batch_id, ? as source_version) from position_snapshot where batch_id = 1",
            ["sv_ledger_" + "b" * 12],
        )
        expected = repo_mod.classification_immutable_evidence(conn, [1, 2])["digest"]
    finally:
        conn.close()
    real_evidence = repo_mod.classification_immutable_evidence
    calls = 0

    def fail_second(conn, batch_ids):
        nonlocal calls
        calls += 1
        value = real_evidence(conn, batch_ids)
        return value if calls == 1 else {**value, "digest": "forced"}

    monkeypatch.setattr(repo_mod, "classification_immutable_evidence", fail_second)
    with repository_task_write_scope("backend.app.tasks.test_ledger_backfill"):
        with pytest.raises(RuntimeError, match="transaction rolled back"):
            repo_mod.LedgerImportRepository(str(db)).attest_classification_rule_versions(
                batch_ids=[1, 2],
                from_rule_versions={1: "position_key_contract_v1", 2: "position_key_contract_v1"},
                target_rule_version="rv_ledger_classification_v2",
                expected_immutable_evidence_digest=expected,
            )
    conn = duckdb.connect(str(db), read_only=True)
    try:
        assert conn.execute("select count(*) from ledger_import_batch where rule_version = 'position_key_contract_v1'").fetchone()[0] == 2
        assert conn.execute("select count(*) from position_snapshot where rule_version = 'rv_ledger_classification_v2'").fetchone()[0] == 0
    finally:
        conn.close()

def test_mixed_legacy_current_selection_is_blocked_without_writes(tmp_path: Path) -> None:
    from backend.app.repositories.ledger_import_repo import LedgerImportRepository
    from backend.app.repositories.task_write_guard import repository_task_write_scope
    from backend.app.services.ledger_import_service import parse_ledger_file
    from backend.app.tasks.ledger_classification_backfill import build_backfill_plan, file_fingerprint

    db = tmp_path / "moss.duckdb"
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    _seed_replayable_legacy_db(db, source_dir)
    second = source_dir / "second.csv"
    second.write_bytes(_csv_source(bond_code="BOND-2"))
    parsed = parse_ledger_file(file_name=second.name, content=second.read_bytes())
    with repository_task_write_scope("backend.app.tasks.test_ledger_backfill"):
        LedgerImportRepository(str(db)).insert_import(
            file_name=second.name,
            file_hash=parsed.file_hash,
            as_of_date=parsed.as_of_date,
            rows=parsed.rows,
            source_version=parsed.source_version,
            rule_version=parsed.rows[0]["rule_version"],
        )
    before = file_fingerprint(db)
    with pytest.raises(ValueError, match="Mixed legacy/current"):
        build_backfill_plan(db, [1, 2], source_dir)
    assert file_fingerprint(db) == before


def test_selected_batch_with_missing_source_hash_is_blocked(tmp_path: Path) -> None:
    from backend.app.tasks.ledger_classification_backfill import build_backfill_plan

    db = tmp_path / "moss.duckdb"
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    source = _seed_replayable_legacy_db(db, source_dir)
    source.unlink()
    with pytest.raises(ValueError, match="exactly one source hash match; found 0"):
        build_backfill_plan(db, [1], source_dir)

def test_prepared_receipt_loops_until_every_encoded_byte_is_written(tmp_path: Path, monkeypatch) -> None:
    import json
    from backend.app.tasks import ledger_classification_backfill as task

    receipt = tmp_path / "prepared.json"
    payload = {"status": "prepared", "message": "完整"}
    expected = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    real_write = task.os.write
    calls = 0

    def one_byte_write(descriptor, data):
        nonlocal calls
        calls += 1
        return real_write(descriptor, data[:1])

    monkeypatch.setattr(task.os, "write", one_byte_write)
    task._write_prepared_receipt(receipt, payload)
    assert calls == len(expected)
    assert receipt.read_bytes() == expected
    assert json.loads(receipt.read_text(encoding="utf-8")) == payload


def test_zero_byte_receipt_write_blocks_db_and_leaves_recognizable_failure(tmp_path: Path, monkeypatch) -> None:
    import json
    from backend.app.tasks import ledger_classification_backfill as task

    db, source_dir, plan, backup = _apply_case(tmp_path)
    receipt = tmp_path / "receipt.json"
    monkeypatch.setattr(task.os, "write", lambda _descriptor, _data: 0)
    with pytest.raises(OSError, match="zero bytes"):
        task.apply_backfill_plan(
            db_path=db,
            batch_ids=[1],
            source_dir=source_dir,
            expected_plan_digest=plan["plan_digest"],
            target_backup_path=backup,
            receipt_path=receipt,
        )
    assert json.loads(receipt.read_text(encoding="utf-8"))["status"] == "prepared_write_failed"
    conn = duckdb.connect(str(db), read_only=True)
    try:
        assert [
            conn.execute(f"select distinct rule_version from {table}").fetchone()[0]
            for table in ("ledger_import_batch", "ledger_raw_row", "position_snapshot")
        ] == ["position_key_contract_v1"] * 3
    finally:
        conn.close()