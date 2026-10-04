from __future__ import annotations

import multiprocessing
import threading
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.repositories.financial_result_publication_repo import (
    FinancialPublicationInvalid,
    generation_database_path,
    generation_manifest_path,
    open_financial_generation,
    read_publication_pointer,
)
from backend.app.repositories.system_read_publication_repo import (
    SYSTEM_READ_API_VERSION,
    SYSTEM_READ_SCHEMA_VERSION,
    system_read_publication_root,
)
from backend.app.tasks.financial_result_publication import (
    FinancialPublicationPlan,
    FinancialTablePublicationSpec,
    _publication_lock,
    publish_financial_result,
)
from backend.app.tasks.system_read_publication import (
    recover_committed_system_read_publication,
)
from tests.test_system_online_read_boundary import _bundle, _seal_generation, _settings, _write_pointer


_REPORT_DATE = "2026-09-15"
_PNL_GENERATION = "pnl-r0"
_OLD_GENERATION = "system-read-2026-09-15-00000000000000000000"
_NEW_GENERATION = "system-read-2026-09-15-11111111111111111111"
_SOURCE_DEPENDENCY = {"synthetic-source": "fixture-v1"}


def _source_dependency_validator(
    _conn: duckdb.DuckDBPyConnection,
) -> Mapping[str, str]:
    return _SOURCE_DEPENDENCY


def _system_bundle(
    settings: SimpleNamespace,
    *,
    pnl_digest: str,
    data_update_run_id: str,
    global_run_id: str,
) -> dict[str, object]:
    return {
        **_bundle(settings, _PNL_GENERATION, pnl_digest),
        "data_update_run_id": data_update_run_id,
        "global_run_id": global_run_id,
        "workflow": "core_financial",
    }


def _plan(
    *,
    generation: str,
    expected_previous_generation: str | None,
    bundle: Mapping[str, object],
    source_dependency_validator: Callable[
        [duckdb.DuckDBPyConnection], Mapping[str, str]
    ] = _source_dependency_validator,
) -> FinancialPublicationPlan:
    return FinancialPublicationPlan(
        generation=generation,
        expected_previous_generation=expected_previous_generation,
        tables=(
            FinancialTablePublicationSpec(
                name="sentinel",
                date_column="report_date",
                required_dates=(_REPORT_DATE,),
            ),
        ),
        required_steps=("verify",),
        step_receipts=(
            {
                "name": "verify",
                "status": "completed",
                "result": {"status": "completed", "report_date": _REPORT_DATE},
            },
        ),
        required_dependency_keys=tuple(_SOURCE_DEPENDENCY),
        dependency_versions=_SOURCE_DEPENDENCY,
        coverage_dates={"sentinel": (_REPORT_DATE,)},
        supported_api_versions=(SYSTEM_READ_API_VERSION,),
        supported_schema_versions=(SYSTEM_READ_SCHEMA_VERSION,),
        quality={
            "status": "passed",
            "checks": ({"name": "fixture", "status": "passed"},),
        },
        source_dependency_validator=source_dependency_validator,
        full_database=True,
        system_read_bundle=bundle,
    )


def _publish_child_until_killed(
    source_path: str,
    publication_root: str,
    bundle: dict[str, object],
    target_stage: str,
    stage_sender,
) -> None:
    def pause_at_target_stage(stage: str) -> None:
        if stage != target_stage:
            return
        stage_sender.send(stage)
        threading.Event().wait()

    publish_financial_result(
        source_duckdb_path=source_path,
        publication_root=publication_root,
        plan=_plan(
            generation=_NEW_GENERATION,
            expected_previous_generation=_OLD_GENERATION,
            bundle=bundle,
        ),
        on_stage=pause_at_target_stage,
    )


@contextmanager
def _publisher_paused_in_child(
    *,
    source: Path,
    root: Path,
    bundle: dict[str, object],
    target_stage: str,
) -> Iterator[multiprocessing.Process]:
    context = multiprocessing.get_context("spawn")
    stage_receiver, stage_sender = context.Pipe(duplex=False)
    process = context.Process(
        target=_publish_child_until_killed,
        args=(str(source), str(root), bundle, target_stage, stage_sender),
    )
    process.start()
    stage_sender.close()
    try:
        if not stage_receiver.poll(30):
            process.join(0.1)
            raise AssertionError(
                f"Publisher child did not reach {target_stage}; exitcode={process.exitcode}"
            )
        assert stage_receiver.recv() == target_stage
        assert process.is_alive(), "Publisher exited instead of remaining at the crash boundary."
        yield process
    finally:
        stage_receiver.close()
        if process.is_alive():
            process.terminate()
            process.join(10)
        if process.is_alive():
            process.kill()
            process.join(10)
    assert not process.is_alive()
    assert process.exitcode not in (None, 0)


@pytest.fixture
def publication_fixture(tmp_path: Path) -> tuple[SimpleNamespace, Path, Path, dict[str, object]]:
    settings = _settings(tmp_path)
    Path(settings.governance_path).mkdir(parents=True, exist_ok=True)
    source = Path(settings.duckdb_path)
    conn = duckdb.connect(str(source))
    try:
        conn.execute(f"ALTER TABLE sentinel ADD COLUMN report_date DATE DEFAULT '{_REPORT_DATE}'")
    finally:
        conn.close()

    pnl_root = Path(settings.financial_publication_root)
    pnl_digest = _seal_generation(pnl_root, _PNL_GENERATION, "PNL")
    _write_pointer(pnl_root, _PNL_GENERATION, [(_PNL_GENERATION, pnl_digest)])

    root = system_read_publication_root(settings)
    old_bundle = _system_bundle(
        settings,
        pnl_digest=pnl_digest,
        data_update_run_id="update-r0",
        global_run_id="global-r0",
    )
    publish_financial_result(
        source_duckdb_path=source,
        publication_root=root,
        plan=_plan(
            generation=_OLD_GENERATION,
            expected_previous_generation=None,
            bundle=old_bundle,
        ),
    )

    conn = duckdb.connect(str(source))
    try:
        conn.execute("UPDATE sentinel SET value = 'NEW'")
    finally:
        conn.close()

    new_bundle = _system_bundle(
        settings,
        pnl_digest=pnl_digest,
        data_update_run_id="update-r1",
        global_run_id="global-r1",
    )
    return settings, source, root, new_bundle


def _read_sentinel(root: Path, generation: str) -> str:
    with open_financial_generation(
        root,
        generation=generation,
        reader_api_version=SYSTEM_READ_API_VERSION,
        reader_schema_version=SYSTEM_READ_SCHEMA_VERSION,
    ) as (conn, _resolved):
        return str(conn.execute("SELECT value FROM sentinel").fetchone()[0])


def _assert_child_holds_writer_lock(source: Path) -> None:
    writer_lock = resolve_duckdb_writer_lock(source, ttl_seconds=1)
    with pytest.raises(TimeoutError):
        with acquire_lock(writer_lock, base_dir=source.parent, timeout_seconds=0.1):
            pass


def _assert_process_exit_released_locks(source: Path, root: Path) -> None:
    writer_lock = resolve_duckdb_writer_lock(source, ttl_seconds=1)
    with acquire_lock(writer_lock, base_dir=source.parent, timeout_seconds=2):
        pass
    with acquire_lock(_publication_lock(root), base_dir=root, timeout_seconds=2):
        pass


def _recover_new_generation_without_candidate_rebuild(
    *,
    source: Path,
    root: Path,
    bundle: dict[str, object],
) -> tuple[str, int]:
    source_validation_calls = 0
    candidate_rebuild_calls = 0

    def validate_source_cut(_conn: duckdb.DuckDBPyConnection) -> Mapping[str, str]:
        nonlocal source_validation_calls
        source_validation_calls += 1
        return _SOURCE_DEPENDENCY

    def forbid_candidate_rebuild(*_args: object) -> None:
        nonlocal candidate_rebuild_calls
        candidate_rebuild_calls += 1
        raise AssertionError("A sealed candidate must be reused without rebuilding financial facts.")

    receipt = publish_financial_result(
        source_duckdb_path=source,
        publication_root=root,
        plan=_plan(
            generation=_NEW_GENERATION,
            expected_previous_generation=_OLD_GENERATION,
            bundle=bundle,
            source_dependency_validator=validate_source_cut,
        ),
        candidate_connection_initializer=forbid_candidate_rebuild,
    )
    assert candidate_rebuild_calls == 0
    return receipt.status, source_validation_calls


def test_process_crash_before_pointer_commit_keeps_old_pointer_and_reuses_sealed_candidate(
    publication_fixture: tuple[SimpleNamespace, Path, Path, dict[str, object]],
) -> None:
    settings, source, root, new_bundle = publication_fixture

    with _publisher_paused_in_child(
        source=source,
        root=root,
        bundle=new_bundle,
        target_stage="before_pointer_commit",
    ):
        assert read_publication_pointer(root)["generation"] == _OLD_GENERATION
        assert _read_sentinel(root, _OLD_GENERATION) == "ACTIVE"
        _assert_child_holds_writer_lock(source)

    assert read_publication_pointer(root)["generation"] == _OLD_GENERATION
    assert generation_database_path(root, _NEW_GENERATION).is_file()
    assert generation_manifest_path(root, _NEW_GENERATION).is_file()
    assert _read_sentinel(root, _OLD_GENERATION) == "ACTIVE"
    assert recover_committed_system_read_publication(
        settings, data_update_run_id="update-r1", report_date=_REPORT_DATE,
        workflow="core_financial",
    ) is None
    _assert_process_exit_released_locks(source, root)

    status, source_validation_calls = _recover_new_generation_without_candidate_rebuild(
        source=source,
        root=root,
        bundle=new_bundle,
    )
    assert status == "published"
    assert source_validation_calls == 2
    assert read_publication_pointer(root)["generation"] == _NEW_GENERATION
    assert _read_sentinel(root, _NEW_GENERATION) == "NEW"
    assert _read_sentinel(root, _OLD_GENERATION) == "ACTIVE"
    assert recover_committed_system_read_publication(
        settings,
        data_update_run_id="update-r1",
        report_date=_REPORT_DATE,
        workflow="core_financial",
    )["generation"] == _NEW_GENERATION


def test_process_crash_after_pointer_commit_recovers_metadata_without_callbacks(
    publication_fixture: tuple[SimpleNamespace, Path, Path, dict[str, object]],
) -> None:
    settings, source, root, new_bundle = publication_fixture

    with _publisher_paused_in_child(
        source=source,
        root=root,
        bundle=new_bundle,
        target_stage="pointer_committed",
    ):
        assert read_publication_pointer(root)["generation"] == _NEW_GENERATION
        assert _read_sentinel(root, _OLD_GENERATION) == "ACTIVE"
        _assert_child_holds_writer_lock(source)

    assert read_publication_pointer(root)["generation"] == _NEW_GENERATION
    assert _read_sentinel(root, _NEW_GENERATION) == "NEW"
    assert _read_sentinel(root, _OLD_GENERATION) == "ACTIVE"
    _assert_process_exit_released_locks(source, root)

    recovered = recover_committed_system_read_publication(
        settings,
        data_update_run_id="update-r1",
        report_date=_REPORT_DATE,
        workflow="core_financial",
    )
    assert recovered is not None
    assert recovered["generation"] == _NEW_GENERATION
    assert recovered["recovered_after_commit"] is True

    def forbid_source_validation(_conn: duckdb.DuckDBPyConnection) -> Mapping[str, str]:
        raise AssertionError("Committed-pointer recovery must not revalidate or replay source facts.")

    def forbid_candidate_rebuild(*_args: object) -> None:
        raise AssertionError("Committed-pointer recovery must not rebuild the sealed candidate.")

    receipt = publish_financial_result(
        source_duckdb_path=source,
        publication_root=root,
        plan=_plan(
            generation=_NEW_GENERATION,
            expected_previous_generation=_OLD_GENERATION,
            bundle=new_bundle,
            source_dependency_validator=forbid_source_validation,
        ),
        candidate_connection_initializer=forbid_candidate_rebuild,
    )
    assert receipt.status == "already_published"
    assert receipt.recovered_after_commit is True


def test_recovery_finds_exact_committed_run_after_later_writer_and_repairs_queue_only(
    publication_fixture: tuple[SimpleNamespace, Path, Path, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.repositories.data_update_repo import latest_runs, save_run
    from backend.app.tasks import data_update_center

    settings, source, root, new_bundle = publication_fixture
    old = recover_committed_system_read_publication(
        settings, data_update_run_id="update-r0", report_date=_REPORT_DATE,
        workflow="core_financial",
    )
    assert old is not None
    publish_financial_result(
        source_duckdb_path=source, publication_root=root,
        plan=_plan(generation=_NEW_GENERATION, expected_previous_generation=_OLD_GENERATION,
                   bundle=new_bundle),
    )
    recovered = recover_committed_system_read_publication(
        settings, data_update_run_id="update-r0", report_date=_REPORT_DATE,
        workflow="core_financial",
    )
    assert recovered == old
    save_run(settings.governance_path, {
        "run_id": "update-r0", "workflow": "core_financial", "report_date": _REPORT_DATE,
        "status": "running", "attempt": 1, "steps": [],
        "submitted_at": "2026-09-15T01:00:00+00:00",
    })
    monkeypatch.setattr(data_update_center, "_recover_pending_pnl_by_business_precompute",
                        lambda *_args, **_kwargs: 0)

    def forbid_replay(*_args: object, **_kwargs: object) -> None:
        pytest.fail("Recovering a retained commit must not replay financial work")

    monkeypatch.setattr(data_update_center, "_execute_core", forbid_replay)
    assert data_update_center.drain_updates(settings) == 0
    receipt = latest_runs(settings.governance_path)[0]
    assert receipt["status"] == "completed"
    assert receipt["steps"][-1]["result"]["generation"] == _OLD_GENERATION


@pytest.mark.parametrize("mismatch", ["writer_run_id", "report_date", "workflow", "data_update_run_id"])
def test_retained_recovery_requires_every_supplied_identity(
    publication_fixture: tuple[SimpleNamespace, Path, Path, dict[str, object]],
    mismatch: str,
) -> None:
    settings, source, root, new_bundle = publication_fixture
    publish_financial_result(
        source_duckdb_path=source, publication_root=root,
        plan=_plan(generation=_NEW_GENERATION, expected_previous_generation=_OLD_GENERATION,
                   bundle=new_bundle),
    )
    identity = dict(writer_run_id="update-r0", data_update_run_id="update-r0",
                    report_date=_REPORT_DATE, workflow="core_financial")
    identity[mismatch] = "2026-09-14" if mismatch == "report_date" else "unrelated"
    assert recover_committed_system_read_publication(settings, **identity) is None


def test_retained_recovery_rejects_manifest_digest_mismatch(
    publication_fixture: tuple[SimpleNamespace, Path, Path, dict[str, object]],
) -> None:
    settings, source, root, new_bundle = publication_fixture
    publish_financial_result(
        source_duckdb_path=source, publication_root=root,
        plan=_plan(generation=_NEW_GENERATION, expected_previous_generation=_OLD_GENERATION,
                   bundle=new_bundle),
    )
    manifest = generation_manifest_path(root, _OLD_GENERATION)
    manifest.write_bytes(manifest.read_bytes() + b" ")
    with pytest.raises(FinancialPublicationInvalid, match="manifest"):
        recover_committed_system_read_publication(
            settings, data_update_run_id="update-r0", report_date=_REPORT_DATE,
            workflow="core_financial",
        )


@pytest.mark.parametrize("current_failure", ["revoked", "manifest", "pointer"])
def test_retained_recovery_is_independent_of_unrelated_current_failure(
    publication_fixture: tuple[SimpleNamespace, Path, Path, dict[str, object]],
    current_failure: str,
) -> None:
    from backend.app.repositories.financial_result_publication_repo import (
        PUBLICATION_POINTER_FILE, canonical_json_bytes, generation_invalidation_path,
    )

    settings, source, root, new_bundle = publication_fixture
    publish_financial_result(
        source_duckdb_path=source, publication_root=root,
        plan=_plan(generation=_NEW_GENERATION, expected_previous_generation=_OLD_GENERATION,
                   bundle=new_bundle),
    )
    if current_failure == "revoked":
        invalidation = generation_invalidation_path(root, _NEW_GENERATION)
        invalidation.parent.mkdir(parents=True, exist_ok=True)
        invalidation.write_bytes(canonical_json_bytes({"reason": "unrelated current revocation"}))
    elif current_failure == "manifest":
        manifest = generation_manifest_path(root, _NEW_GENERATION)
        manifest.write_bytes(manifest.read_bytes() + b" ")
    else:
        pointer = read_publication_pointer(root)
        pointer["validity"] = {"state": "invalid"}
        (root / PUBLICATION_POINTER_FILE).write_bytes(canonical_json_bytes(pointer))
    assert _read_sentinel(root, _OLD_GENERATION) == "ACTIVE"
    recovered = recover_committed_system_read_publication(
        settings, data_update_run_id="update-r0", report_date=_REPORT_DATE,
        workflow="core_financial",
    )
    assert recovered is not None
    assert recovered["generation"] == _OLD_GENERATION


def test_recovery_keeps_candidate_identity_when_current_advances(
    publication_fixture: tuple[SimpleNamespace, Path, Path, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.tasks import system_read_publication

    settings, source, root, new_bundle = publication_fixture
    publish_financial_result(
        source_duckdb_path=source, publication_root=root,
        plan=_plan(generation=_NEW_GENERATION, expected_previous_generation=_OLD_GENERATION,
                   bundle=new_bundle),
    )
    original_resolve = system_read_publication.resolve_financial_generation
    advanced = False

    def resolve_after_publish(*args: object, **kwargs: object):
        nonlocal advanced
        if not advanced:
            advanced = True
            publish_financial_result(
                source_duckdb_path=source, publication_root=root,
                plan=_plan(
                    generation="system-read-2026-09-15-22222222222222222222",
                    expected_previous_generation=_NEW_GENERATION,
                    bundle={**new_bundle, "data_update_run_id": "update-r2", "global_run_id": "global-r2"},
                ),
            )
        return original_resolve(*args, **kwargs)

    monkeypatch.setattr(system_read_publication, "resolve_financial_generation", resolve_after_publish)
    recovered = recover_committed_system_read_publication(
        settings, data_update_run_id="update-r1", report_date=_REPORT_DATE,
        workflow="core_financial",
    )
    assert recovered is not None
    assert recovered["generation"] == _NEW_GENERATION
    assert _read_sentinel(root, _NEW_GENERATION) == "NEW"


def test_recovery_rejects_current_pointer_invalidity_without_marker(
    publication_fixture: tuple[SimpleNamespace, Path, Path, dict[str, object]],
) -> None:
    from backend.app.repositories.financial_result_publication_repo import (
        PUBLICATION_POINTER_FILE, FinancialPublicationUnavailable, canonical_json_bytes,
    )

    settings, _source, root, _new_bundle = publication_fixture
    pointer = read_publication_pointer(root)
    pointer["validity"] = {"state": "invalid"}
    (root / PUBLICATION_POINTER_FILE).write_bytes(canonical_json_bytes(pointer))
    with pytest.raises(FinancialPublicationUnavailable):
        recover_committed_system_read_publication(
            settings, data_update_run_id="update-r0", report_date=_REPORT_DATE,
            workflow="core_financial",
        )
