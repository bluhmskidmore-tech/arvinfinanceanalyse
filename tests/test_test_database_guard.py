from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import duckdb
import pytest

import backend.app.tasks.financial_result_publication as financial_publication
from _pytest_duckdb_guard import (
    PytestDuckDBIsolationViolation,
    _DuckDBConnectGuard,
    expect_pytest_duckdb_guard_denial,
    get_pytest_duckdb_guard_attempts,
    get_pytest_duckdb_guard_receipt_path,
)
from tests.test_system_read_publication import _create_source, _plan

REPO_ROOT = Path(__file__).resolve().parents[1]


def _isolated_guard(
    tmp_path: Path,
    calls: list[tuple[tuple[object, ...], dict[str, object]]],
    *,
    protected: Path | None = None,
) -> _DuckDBConnectGuard:
    def fake_native(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        return object()

    return _DuckDBConnectGuard(
        native_connect=fake_native,
        repo_root=tmp_path,
        protected_paths=(protected,) if protected is not None else None,
        run_id="synthetic-guard-run",
    )


def _preserve_child_trace(child_basetemp: Path, destination: Path) -> list[dict[str, object]]:
    receipt = child_basetemp / "pytest-duckdb-guard-attempts.jsonl"
    raw_receipt = receipt.read_text(encoding="utf-8")
    destination.write_text(raw_receipt, encoding="utf-8")
    return [json.loads(line) for line in raw_receipt.splitlines()]


def test_default_and_absolute_protected_paths_are_denied_before_native_connect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    protected = tmp_path / "data" / "moss.duckdb"
    protected.parent.mkdir()
    protected.write_bytes(b"synthetic-protected-sentinel")
    guard = _isolated_guard(tmp_path, calls, protected=protected)
    owned = tmp_path / ".codex-tmp" / "pytest-basetemp-101"
    guard.register_temp_root(owned)
    monkeypatch.chdir(tmp_path)

    for database, read_only in (
        ("data/moss.duckdb", False),
        (protected, True),
    ):
        with expect_pytest_duckdb_guard_denial():
            with pytest.raises(PytestDuckDBIsolationViolation):
                guard.connect(database, read_only=read_only)

    assert calls == []
    assert protected.read_bytes() == b"synthetic-protected-sentinel"
    denied = [attempt for attempt in guard.attempts if attempt["decision"] == "deny"]
    assert [attempt["target_classification"] for attempt in denied] == [
        "protected_database",
        "protected_database",
    ]
    assert all(attempt["expected_denial"] is True for attempt in denied)
    assert all("sql" not in attempt and "rows" not in attempt for attempt in denied)


def test_only_memory_and_the_exact_owned_temp_root_are_allowed(tmp_path: Path) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    guard = _isolated_guard(tmp_path, calls)
    codex_tmp = tmp_path / ".codex-tmp"
    owned = codex_tmp / "pytest-basetemp-101"
    sibling = codex_tmp / "pytest-basetemp-202" / "other.duckdb"
    guard.register_temp_root(owned)

    guard.connect()
    guard.connect(":memory:", read_only=True)
    guard.connect(owned / "case" / "allowed.duckdb", read_only=False)
    with expect_pytest_duckdb_guard_denial():
        with pytest.raises(PytestDuckDBIsolationViolation):
            guard.connect(sibling, read_only=True)
    with expect_pytest_duckdb_guard_denial():
        with pytest.raises(PytestDuckDBIsolationViolation):
            guard.connect(tmp_path / "unknown.duckdb")

    assert len(calls) == 3
    assert [attempt["target_classification"] for attempt in guard.attempts] == [
        "memory",
        "memory",
        "owned_temp",
        "outside_owned_temp",
        "outside_owned_temp",
    ]


def test_relative_case_and_parent_segments_resolve_against_the_owned_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    guard = _isolated_guard(tmp_path, calls)
    owned = tmp_path / "OwnedTemp"
    owned.mkdir()
    guard.register_temp_root(owned)
    monkeypatch.chdir(tmp_path)

    relative_owned = "ownedtemp/nested.duckdb" if os.name == "nt" else "OwnedTemp/nested.duckdb"
    guard.connect(relative_owned)
    with expect_pytest_duckdb_guard_denial():
        with pytest.raises(PytestDuckDBIsolationViolation):
            guard.connect("OwnedTemp/../outside.duckdb")

    assert len(calls) == 1


def test_symlink_and_hardlink_aliases_cannot_reenter_an_owned_root(tmp_path: Path) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    protected = tmp_path / "protected" / "active.duckdb"
    protected.parent.mkdir()
    protected.write_bytes(b"synthetic-protected-sentinel")
    owned = tmp_path / "owned"
    owned.mkdir()
    guard = _isolated_guard(tmp_path, calls, protected=protected)
    guard.register_temp_root(owned)

    hardlink = owned / "hardlink.duckdb"
    os.link(protected, hardlink)
    with expect_pytest_duckdb_guard_denial():
        with pytest.raises(PytestDuckDBIsolationViolation):
            guard.connect(hardlink)

    symlink = owned / "symlink.duckdb"
    try:
        symlink.symlink_to(protected)
    except OSError:
        symlink = None
    if symlink is not None:
        with expect_pytest_duckdb_guard_denial():
            with pytest.raises(PytestDuckDBIsolationViolation):
                guard.connect(symlink, read_only=True)

    assert calls == []
    assert protected.read_bytes() == b"synthetic-protected-sentinel"


def test_broad_temp_root_containing_a_protected_database_is_rejected(tmp_path: Path) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    protected = tmp_path / "data" / "moss.duckdb"
    guard = _isolated_guard(tmp_path, calls, protected=protected)

    with expect_pytest_duckdb_guard_denial():
        with pytest.raises(PytestDuckDBIsolationViolation):
            guard.register_temp_root(tmp_path)

    assert calls == []


def test_deleted_attempt_receipt_is_rebuilt_from_in_memory_attempts(tmp_path: Path) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []
    guard = _isolated_guard(tmp_path, calls)
    owned = tmp_path / "owned"
    owned.mkdir()
    guard.register_temp_root(owned)
    guard.connect()
    receipt = guard.persist_attempts()
    assert len(receipt.read_text(encoding="utf-8").splitlines()) == 1

    receipt.unlink()
    guard.connect(":memory:", read_only=True)

    rebuilt = [json.loads(line) for line in receipt.read_text(encoding="utf-8").splitlines()]
    assert len(rebuilt) == 2
    assert [attempt["access"] for attempt in rebuilt] == [
        "read_write_or_default",
        "read_only",
    ]


def test_installed_guard_opens_real_memory_and_current_process_tmp(
    tmp_path: Path,
) -> None:
    with duckdb.connect() as memory:
        assert memory.execute("select 1").fetchone() == (1,)

    database = tmp_path / "actual-safe.duckdb"
    with duckdb.connect(str(database), read_only=False) as connection:
        connection.execute("create table safe_fixture(value integer)")
    assert database.is_file()

    attempts = get_pytest_duckdb_guard_attempts()
    assert any(
        attempt["canonical_path"] == str(database.resolve())
        and attempt["decision"] == "allow"
        and attempt["phase"] == "test"
        for attempt in attempts
    )
    receipt_path = get_pytest_duckdb_guard_receipt_path()
    assert receipt_path.parent == tmp_path.parents[0]
    assert receipt_path.is_file()


def test_actual_financial_publisher_copies_between_owned_temp_databases(
    tmp_path: Path,
) -> None:
    source = tmp_path / "publisher-source.duckdb"
    publication_root = tmp_path / "publisher-generations"
    governance = tmp_path / "publisher-governance"
    governance.mkdir()
    _create_source(source)

    receipt = financial_publication.publish_financial_result(
        source_duckdb_path=source,
        publication_root=publication_root,
        plan=_plan(
            source,
            governance,
            dependency_validator=lambda _conn: {"source": "source-v1"},
        ),
        writer_lock_already_held=True,
    )

    with duckdb.connect(str(receipt.database_path), read_only=True) as connection:
        assert connection.execute("select value from fact_result").fetchone() == (11,)
    attempts = get_pytest_duckdb_guard_attempts()
    assert any(
        attempt["access"] == "attach_read_only_source"
        and attempt["canonical_path"] == str(source.resolve())
        and attempt["decision"] == "allow"
        for attempt in attempts
    )


def test_forbidden_publication_attach_source_is_rejected_before_candidate_open(
    tmp_path: Path,
) -> None:
    forbidden = REPO_ROOT / ".codex-tmp" / (
        f"synthetic-attach-forbidden-{os.getpid()}-{uuid.uuid4().hex}.duckdb"
    )
    forbidden.parent.mkdir(parents=True, exist_ok=True)
    forbidden.write_bytes(b"synthetic-attach-sentinel")
    candidate = tmp_path / "candidate-must-not-open.duckdb"
    try:
        with expect_pytest_duckdb_guard_denial():
            with pytest.raises(PytestDuckDBIsolationViolation):
                financial_publication._build_candidate_from_attached_source(
                    source_path=forbidden,
                    candidate_path=candidate,
                    plan=None,  # type: ignore[arg-type]
                    input_identity_sha256="synthetic",
                    connection_initializer=None,
                )
    finally:
        forbidden.unlink(missing_ok=True)

    assert not candidate.exists()


def test_untracked_borrowed_source_is_rejected_before_attach_execute(tmp_path: Path) -> None:
    class UnknownConnection:
        def __init__(self) -> None:
            self.execute_called = False

        def execute(self, *_args: object, **_kwargs: object) -> None:
            self.execute_called = True
            raise AssertionError("native execute must not run")

    source_connection = UnknownConnection()
    with expect_pytest_duckdb_guard_denial():
        with pytest.raises(PytestDuckDBIsolationViolation):
            financial_publication._build_candidate_from_existing_source_connection(
                source_connection=source_connection,  # type: ignore[arg-type]
                candidate_path=tmp_path / "borrowed-candidate.duckdb",
                plan=None,  # type: ignore[arg-type]
                input_identity_sha256="synthetic",
                connection_initializer=None,
            )

    assert source_connection.execute_called is False


def test_explicit_plugin_blocks_an_other_process_temp_file_during_collection(
    tmp_path: Path,
) -> None:
    sentinel = tmp_path / "collection-forbidden.duckdb"
    sentinel.write_bytes(b"synthetic-collection-sentinel")
    probe = tmp_path / "test_collection_guard_probe.py"
    child_basetemp = tmp_path / "explicit-plugin-child-basetemp"
    probe.write_text(
        "import duckdb\n"
        f"duckdb.connect({str(sentinel)!r}, read_only=False)\n"
        "def test_never_runs():\n"
        "    raise AssertionError('collection guard did not run')\n",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "_pytest_duckdb_guard",
            "-q",
            f"--basetemp={child_basetemp}",
            str(probe),
        ],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert completed.returncode != 0
    combined_output = completed.stdout + completed.stderr
    assert "PytestDuckDBIsolationViolation" in combined_output
    assert "collection guard did not run" not in combined_output
    assert sentinel.read_bytes() == b"synthetic-collection-sentinel"
    attempts = _preserve_child_trace(
        child_basetemp,
        tmp_path / "explicit-plugin-child-trace.jsonl",
    )
    assert any(attempt["decision"] == "deny" for attempt in attempts)


def test_child_guard_denies_unowned_sentinel_and_persists_trace(tmp_path: Path) -> None:
    owned = tmp_path / "child-owned"
    owned.mkdir()
    sentinel = tmp_path / "child-forbidden.duckdb"
    sentinel.write_bytes(b"synthetic-child-sentinel")
    probe = (
        "import sys\n"
        "import _pytest_duckdb_guard as guard\n"
        "guard.register_pytest_duckdb_temp_root(sys.argv[1])\n"
        "guard.set_pytest_duckdb_guard_phase('child')\n"
        "try:\n"
        "    import duckdb\n"
        "    duckdb.connect(sys.argv[2])\n"
        "finally:\n"
        "    guard.finalize_pytest_duckdb_guard()\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe, str(owned), str(sentinel)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert completed.returncode != 0
    assert sentinel.read_bytes() == b"synthetic-child-sentinel"
    attempts = _preserve_child_trace(
        owned,
        tmp_path / "unowned-child-trace.jsonl",
    )
    assert len(attempts) == 1
    assert attempts[0]["phase"] == "child"
    assert attempts[0]["decision"] == "deny"
    assert attempts[0]["expected_denial"] is False


@pytest.mark.parametrize("test_root", ("tests", "backend/tests"))
def test_repository_root_plugin_blocks_both_test_roots_during_collection(
    tmp_path: Path,
    test_root: str,
) -> None:
    sentinel = tmp_path / f"{test_root.replace('/', '-')}-forbidden.duckdb"
    sentinel.write_bytes(b"synthetic-double-root-sentinel")
    probe_dir = REPO_ROOT / test_root
    probe_dir.mkdir(parents=True, exist_ok=True)
    probe = probe_dir / f"test_pytest_duckdb_guard_probe_{os.getpid()}_{uuid.uuid4().hex}.py"
    probe.write_text(
        "import duckdb\n"
        f"duckdb.connect({str(sentinel)!r}, read_only=True)\n"
        "def test_never_runs():\n"
        "    raise AssertionError('root collection guard did not run')\n",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    child_basetemp = tmp_path / f"{test_root.replace('/', '-')}-collection-basetemp"
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                f"--basetemp={child_basetemp}",
                str(probe),
            ],
            cwd=REPO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    finally:
        probe.unlink(missing_ok=True)

    assert completed.returncode != 0
    combined_output = completed.stdout + completed.stderr
    assert "PytestDuckDBIsolationViolation" in combined_output
    assert "root collection guard did not run" not in combined_output
    assert sentinel.read_bytes() == b"synthetic-double-root-sentinel"
    attempts = _preserve_child_trace(
        child_basetemp,
        tmp_path / f"{test_root.replace('/', '-')}-collection-trace.jsonl",
    )
    assert any(attempt["decision"] == "deny" for attempt in attempts)


def test_backend_root_registers_actual_factory_tmp_and_caught_denial_fails_session(
    tmp_path: Path,
) -> None:
    sentinel = tmp_path / "caught-denial-forbidden.duckdb"
    sentinel.write_bytes(b"synthetic-caught-denial-sentinel")
    child_basetemp = tmp_path / "backend-child-basetemp"
    probe_dir = REPO_ROOT / "backend" / "tests"
    probe_dir.mkdir(parents=True, exist_ok=True)
    probe = probe_dir / f"test_pytest_duckdb_guard_session_{os.getpid()}_{uuid.uuid4().hex}.py"
    probe.write_text(
        "from pathlib import Path\n"
        "import duckdb\n"
        "def test_actual_tmp_is_allowed(tmp_path):\n"
        "    database = tmp_path / 'allowed.duckdb'\n"
        "    with duckdb.connect(str(database)) as conn:\n"
        "        conn.execute('create table fixture(value integer)')\n"
        "    assert database.is_file()\n"
        "def test_caught_denial_still_fails_session():\n"
        "    try:\n"
        f"        duckdb.connect({str(sentinel)!r})\n"
        "    except BaseException:\n"
        "        pass\n",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                f"--basetemp={child_basetemp}",
                str(probe),
            ],
            cwd=REPO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    finally:
        probe.unlink(missing_ok=True)

    assert completed.returncode == int(pytest.ExitCode.TESTS_FAILED)
    assert "2 passed" in completed.stdout
    assert sentinel.read_bytes() == b"synthetic-caught-denial-sentinel"
    attempts = _preserve_child_trace(
        child_basetemp,
        tmp_path / "backend-caught-denial-child-trace.jsonl",
    )
    assert any(
        attempt["decision"] == "allow"
        and attempt["target_classification"] == "owned_temp"
        for attempt in attempts
    )
    caught = [attempt for attempt in attempts if attempt["decision"] == "deny"]
    assert len(caught) == 1
    assert caught[0]["expected_denial"] is False
    assert set(caught[0]) == {
        "access",
        "callsite",
        "canonical_path",
        "decision",
        "expected_denial",
        "phase",
        "pid",
        "run_id",
        "target_classification",
    }
