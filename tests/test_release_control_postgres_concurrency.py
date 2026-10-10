from __future__ import annotations

import os
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.pool import NullPool

from backend.app.repositories.release_control_repo import (
    AliasRevisionConflictError,
    ReleaseControlRepository,
)
from tests.test_release_control_repo import _candidate_to_approved

pytestmark = pytest.mark.integration

_EXPECTED_DATABASE = "moss_release_control_test"
_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
_SCOPES = (
    ("physical_bundle", "duckdb-main"),
    ("logical_lane", "bond-analytics-risk-tensor"),
    ("logical_lane", "bond-analytics-core"),
)


@pytest.fixture()
def postgres_test_dsn() -> str:
    dsn = os.environ.get("MOSS_TEST_POSTGRES_DSN", "").strip()
    required = os.environ.get("MOSS_REQUIRE_POSTGRES_CONCURRENCY_TEST", "").strip() == "1"
    if not dsn:
        if required:
            pytest.fail("MOSS_TEST_POSTGRES_DSN is required by the PostgreSQL concurrency gate")
        pytest.skip("MOSS_TEST_POSTGRES_DSN is not configured; PostgreSQL CAS proof was not run")

    url = make_url(dsn)
    if url.get_backend_name() != "postgresql":
        pytest.fail("PostgreSQL CAS proof refuses a non-PostgreSQL test DSN")
    if (url.host or "").lower() not in _LOOPBACK_HOSTS:
        pytest.fail("PostgreSQL CAS proof only accepts a loopback-hosted disposable database")
    if (url.database or "").lower() != _EXPECTED_DATABASE:
        pytest.fail(
            "PostgreSQL CAS proof only accepts the dedicated "
            f"{_EXPECTED_DATABASE!r} disposable database"
        )
    return dsn


def _engine(dsn: str, *, application_name: str) -> Engine:
    url = make_url(dsn).set(drivername="postgresql+psycopg")
    return create_engine(
        url,
        future=True,
        poolclass=NullPool,
        connect_args={"application_name": application_name, "connect_timeout": 5},
    )


def _expectations(expected_revision: int) -> list[dict[str, object]]:
    return [
        {
            "scope_kind": scope_kind,
            "scope_key": scope_key,
            "expected_revision": expected_revision,
        }
        for scope_kind, scope_key in _SCOPES
    ]


def _prepare_releases(
    dsn: str,
    *,
    environment: str,
    release_ids: tuple[str, ...],
) -> dict[str, Any]:
    repository = ReleaseControlRepository(sql_dsn=dsn)
    try:
        return {
            release_id: _candidate_to_approved(
                repository,
                release_id,
                target_environment=environment,
            )
            for release_id in release_ids
        }
    finally:
        repository.close()


def _overlap_fault_injector(
    monitor_engine: Engine,
    *,
    application_names: set[str],
    overlap_snapshot: list[dict[str, Any]],
) -> Callable[[str, Mapping[str, Any]], None]:
    observed = threading.Event()

    def inject(stage: str, context: Mapping[str, Any]) -> None:
        if stage != "after_alias_cas" or context.get("index") != 0 or observed.is_set():
            return

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with monitor_engine.connect() as connection:
                rows = connection.execute(
                    text(
                        "SELECT application_name, state, wait_event_type, wait_event, "
                        "xact_start IS NOT NULL AS has_transaction "
                        "FROM pg_stat_activity "
                        "WHERE datname = current_database() "
                        "AND application_name = ANY(:application_names)"
                    ),
                    {"application_names": sorted(application_names)},
                ).mappings().all()
            by_name = {str(row["application_name"]): dict(row) for row in rows}
            if set(by_name) == application_names and all(
                bool(row["has_transaction"]) for row in by_name.values()
            ):
                overlap_snapshot.extend(by_name[name] for name in sorted(by_name))
                observed.set()
                return
            time.sleep(0.02)

        raise AssertionError(
            "both independent PostgreSQL transactions were not simultaneously observable"
        )

    return inject


def _run_race(
    dsn: str,
    *,
    environment: str,
    contenders: dict[str, Any],
    expected_revision: int,
) -> tuple[str, str, AliasRevisionConflictError, list[dict[str, Any]]]:
    suffix = uuid.uuid4().hex[:8]
    application_names = {
        f"moss-cas-{suffix}-a",
        f"moss-cas-{suffix}-b",
    }
    engine_a = _engine(dsn, application_name=f"moss-cas-{suffix}-a")
    engine_b = _engine(dsn, application_name=f"moss-cas-{suffix}-b")
    monitor_engine = _engine(dsn, application_name=f"moss-cas-{suffix}-monitor")
    assert engine_a is not engine_b

    repositories = (
        ReleaseControlRepository(engine=engine_a),
        ReleaseControlRepository(engine=engine_b),
    )
    start_barrier = threading.Barrier(2)
    overlap_snapshot: list[dict[str, Any]] = []
    fault_injector = _overlap_fault_injector(
        monitor_engine,
        application_names=application_names,
        overlap_snapshot=overlap_snapshot,
    )
    release_ids = tuple(contenders)

    def activate(index: int) -> tuple[str, object]:
        release_id = release_ids[index]
        start_barrier.wait(timeout=10)
        try:
            receipt = repositories[index].activate_release(
                action="promote",
                target_environment=environment,
                release_id=release_id,
                manifest_digest=contenders[release_id].manifest_digest,
                scope_expectations=_expectations(expected_revision),
                idempotency_key=f"concurrent-promote-{suffix}-{index}",
                fault_injector=fault_injector,
            )
        except AliasRevisionConflictError as exc:
            return ("conflict", exc)
        return ("success", receipt)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = [future.result(timeout=20) for future in [
                executor.submit(activate, 0),
                executor.submit(activate, 1),
            ]]
    finally:
        for repository in repositories:
            repository.close()
        engine_a.dispose()
        engine_b.dispose()
        monitor_engine.dispose()

    assert [kind for kind, _value in outcomes].count("success") == 1
    assert [kind for kind, _value in outcomes].count("conflict") == 1
    assert {str(row["application_name"]) for row in overlap_snapshot} == application_names
    assert all(bool(row["has_transaction"]) for row in overlap_snapshot)

    winner_index = next(index for index, outcome in enumerate(outcomes) if outcome[0] == "success")
    loser_index = 1 - winner_index
    conflict = outcomes[loser_index][1]
    assert isinstance(conflict, AliasRevisionConflictError)
    return release_ids[winner_index], release_ids[loser_index], conflict, overlap_snapshot


def _assert_winner_bundle(
    repository: ReleaseControlRepository,
    *,
    environment: str,
    winner: str,
    loser: str,
    expected_revision: int,
    previous_release_id: str | None,
) -> None:
    aliases = repository.list_aliases(target_environment=environment)
    assert {(alias.scope_kind, alias.scope_key) for alias in aliases} == set(_SCOPES)
    assert {alias.current_release_id for alias in aliases} == {winner}
    assert {alias.previous_release_id for alias in aliases} == {previous_release_id}
    assert {alias.revision for alias in aliases} == {expected_revision + 1}

    assert len(
        repository.list_events(
            release_id=winner,
            action="promote",
            target_environment=environment,
        )
    ) == 1
    assert repository.list_events(
        release_id=loser,
        action="promote",
        target_environment=environment,
    ) == []
    assert repository.get_manifest(winner).state == "current"
    assert repository.get_manifest(loser).state == "approved"


def test_postgres_whole_bundle_cas_allows_exactly_one_existing_alias_winner(
    postgres_test_dsn: str,
) -> None:
    suffix = uuid.uuid4().hex[:8]
    environment = f"pg-cas-update-{suffix}"
    base_release = f"pg-cas-update-{suffix}-base"
    contender_ids = (
        f"pg-cas-update-{suffix}-a",
        f"pg-cas-update-{suffix}-b",
    )
    manifests = _prepare_releases(
        postgres_test_dsn,
        environment=environment,
        release_ids=(base_release, *contender_ids),
    )
    setup_repository = ReleaseControlRepository(sql_dsn=postgres_test_dsn)
    try:
        setup_repository.activate_release(
            action="promote",
            target_environment=environment,
            release_id=base_release,
            manifest_digest=manifests[base_release].manifest_digest,
            scope_expectations=_expectations(0),
            idempotency_key=f"bootstrap-{suffix}",
        )
    finally:
        setup_repository.close()

    winner, loser, conflict, _snapshot = _run_race(
        postgres_test_dsn,
        environment=environment,
        contenders={release_id: manifests[release_id] for release_id in contender_ids},
        expected_revision=1,
    )

    assert conflict.expected_revision == 1
    assert conflict.actual_revision == 2
    assertion_repository = ReleaseControlRepository(sql_dsn=postgres_test_dsn)
    try:
        _assert_winner_bundle(
            assertion_repository,
            environment=environment,
            winner=winner,
            loser=loser,
            expected_revision=1,
            previous_release_id=base_release,
        )
        supersede_events = assertion_repository.list_events(
            release_id=base_release,
            action="supersede",
            target_environment=environment,
        )
        assert len(supersede_events) == 1
        assert supersede_events[0].event_payload["activated_release_id"] == winner
        assert assertion_repository.get_manifest(base_release).state == "deprecated"
    finally:
        assertion_repository.close()


def test_postgres_whole_bundle_cas_allows_exactly_one_first_insert_winner(
    postgres_test_dsn: str,
) -> None:
    suffix = uuid.uuid4().hex[:8]
    environment = f"pg-cas-insert-{suffix}"
    contender_ids = (
        f"pg-cas-insert-{suffix}-a",
        f"pg-cas-insert-{suffix}-b",
    )
    manifests = _prepare_releases(
        postgres_test_dsn,
        environment=environment,
        release_ids=contender_ids,
    )

    winner, loser, conflict, _snapshot = _run_race(
        postgres_test_dsn,
        environment=environment,
        contenders={release_id: manifests[release_id] for release_id in contender_ids},
        expected_revision=0,
    )

    assert conflict.expected_revision == 0
    assert conflict.actual_revision == 1
    assertion_repository = ReleaseControlRepository(sql_dsn=postgres_test_dsn)
    try:
        _assert_winner_bundle(
            assertion_repository,
            environment=environment,
            winner=winner,
            loser=loser,
            expected_revision=0,
            previous_release_id=None,
        )
        contender_promotes = [
            event
            for release_id in contender_ids
            for event in assertion_repository.list_events(
                release_id=release_id,
                action="promote",
                target_environment=environment,
            )
        ]
        assert len(contender_promotes) == 1
        assert contender_promotes[0].release_id == winner
    finally:
        assertion_repository.close()
