from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterator

import duckdb
import pytest
import requests

from backend.app.governance.locks import acquire_lock as acquire_real_lock
from backend.app.governance.locks import resolve_duckdb_writer_lock
from backend.app.tasks import livermore_candidate_history_materialize as candidate_task
from backend.app.tasks import livermore_candidate_outcome_maturity as maturity_task


pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]


def _captured_external_inputs() -> dict[str, object]:
    return {
        "identity_profiles": [
            {"name": name, "present": False, "content_sha256": "a" * 64}
            for name in (
                "choice_stock_catalog",
                "cycle_rotation_macro_official_availability",
                "cycle_rotation_macro_official_releases",
                "macro_adversarial_signal_payload",
            )
        ],
        "stock_readiness": None,
        "availability_manifest_payload": {},
        "releases_manifest_payload": {},
        "adversarial_payload": {},
        "adversarial_meta": {},
    }


class _UnexpectedNetwork(BaseException):
    pass


@pytest.fixture
def request_sentinel(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []

    def reject_request(*args: object, **kwargs: object) -> None:
        method = str(kwargs.get("method") or (args[1] if len(args) > 1 else "")).upper()
        url = str(kwargs.get("url") or (args[2] if len(args) > 2 else ""))
        calls.append((method, url))
        raise _UnexpectedNetwork(f"unexpected network request: {method} {url}")

    monkeypatch.setattr(requests.sessions.Session, "request", reject_request)
    return calls


def test_request_sentinel_self_check(request_sentinel: list[tuple[str, str]]) -> None:
    with pytest.raises(_UnexpectedNetwork, match="GET https://supplier.invalid/probe"):
        requests.get("https://supplier.invalid/probe")
    assert request_sentinel == [("GET", "https://supplier.invalid/probe")]


class _TrackedConnection:
    def __init__(
        self,
        raw: Any,
        events: list[str],
        *,
        rollback_error: str | None = None,
    ) -> None:
        self._raw = raw
        self._events = events
        self._rollback_error = rollback_error

    def __getattr__(self, name: str) -> Any:
        return getattr(self._raw, name)

    def execute(self, query: str, *args: object, **kwargs: object) -> Any:
        result = self._raw.execute(query, *args, **kwargs)
        if query.strip().lower() == "rollback" and self._rollback_error is not None:
            self._events.append("rollback_error_after_execute")
            raise RuntimeError(self._rollback_error)
        return result

    def close(self) -> None:
        self._raw.close()
        self._events.append("native_close")


def _install_lock_trace(
    monkeypatch: pytest.MonkeyPatch,
    *,
    db_path: Path,
    task_module: Any = candidate_task,
    no_wait_lock: object | None = None,
    rollback_error: str | None = None,
) -> list[str]:
    writer_lock = resolve_duckdb_writer_lock(db_path)
    events: list[str] = []
    writer_held = False
    real_connect = task_module.duckdb.connect

    @contextmanager
    def tracked_acquire_lock(*args: object, **kwargs: object) -> Iterator[Path]:
        nonlocal writer_held
        definition = args[0]
        is_writer_lock = definition == writer_lock
        if not is_writer_lock:
            effective_kwargs = dict(kwargs)
            if definition == no_wait_lock:
                effective_kwargs["timeout_seconds"] = 0.0
            with acquire_real_lock(*args, **effective_kwargs) as lock_path:
                yield lock_path
            return
        try:
            with acquire_real_lock(*args, **kwargs) as lock_path:
                writer_held = True
                events.append("writer_acquired")
                yield lock_path
        finally:
            writer_held = False
            events.append("writer_released")

    def tracked_connect(*args: object, **kwargs: object):
        database = Path(str(args[0])).resolve()
        if database == db_path.resolve() and kwargs.get("read_only") is False:
            assert writer_held, (
                "native write connection opened before canonical writer admission"
            )
            events.append("native_open")
            return _TrackedConnection(
                real_connect(*args, **kwargs),
                events,
                rollback_error=rollback_error,
            )
        return real_connect(*args, **kwargs)

    monkeypatch.setattr(task_module, "acquire_lock", tracked_acquire_lock)
    monkeypatch.setattr(task_module.duckdb, "connect", tracked_connect)
    return events


def _patch_local_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        candidate_task,
        "_capture_configured_external_inputs",
        _captured_external_inputs,
    )
    monkeypatch.setattr(
        candidate_task,
        "_configured_external_input_identities_match",
        lambda _captured: True,
    )


def _seed_observations_and_control(
    db_path: Path,
    *,
    snapshot_date: date,
    stock_code: str = "000001.SZ",
) -> None:
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            "create table choice_stock_daily_observation "
            "(trade_date varchar, stock_code varchar, close_value double)"
        )
        conn.execute("create table control_probe (value integer)")
        conn.execute("insert into control_probe values (7)")
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?)",
            [
                (
                    (snapshot_date + timedelta(days=index)).isoformat(),
                    stock_code,
                    100.0 + index,
                )
                for index in range(25)
            ],
        )
    finally:
        conn.close()


def _strategy_payload(
    *,
    snapshot_date: date,
    items: list[dict[str, object]],
) -> tuple[dict[str, object], dict[str, object]]:
    return (
        {
            "as_of_date": snapshot_date.isoformat(),
            "requested_as_of_date": snapshot_date.isoformat(),
            "stock_candidates": {"items": items},
            "market_gate": {"state": "HOT", "exposure": 0.5},
        },
        {
            "source_version": "sv-test-candidate-meta",
            "vendor_version": "vv-test-candidate-meta",
            "quality_flag": "ok",
        },
    )


def _assert_writer_lifecycle(events: list[str]) -> None:
    assert events == [
        "writer_acquired",
        "native_open",
        "native_close",
        "writer_released",
    ]


def _seed_empty_maturity_database(db_path: Path) -> None:
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        candidate_task.ensure_livermore_candidate_history_schema(conn)
        conn.execute(
            "create table choice_stock_daily_observation "
            "(trade_date varchar, stock_code varchar, close_value double)"
        )
        conn.execute("create table control_probe (value integer)")
        conn.execute("insert into control_probe values (7)")
    finally:
        conn.close()


def test_maturity_writer_lock_precedes_native_open_and_covers_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    request_sentinel: list[tuple[str, str]],
) -> None:
    db_path = tmp_path / "maturity-success.duckdb"
    _seed_empty_maturity_database(db_path)
    events = _install_lock_trace(
        monkeypatch,
        db_path=db_path,
        task_module=maturity_task,
    )

    result = maturity_task.mature_livermore_candidate_outcomes(
        db_path,
        evaluation_as_of_date="2026-09-15",
    )

    assert result["status"] == "completed"
    assert result["candidate_row_count"] == 0
    _assert_writer_lifecycle(events)
    assert request_sentinel == []


def test_maturity_writer_admission_rolls_back_and_releases_after_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    request_sentinel: list[tuple[str, str]],
) -> None:
    db_path = tmp_path / "maturity-failure.duckdb"
    _seed_empty_maturity_database(db_path)
    events = _install_lock_trace(
        monkeypatch,
        db_path=db_path,
        task_module=maturity_task,
    )

    def failing_candidates(conn: Any, **_kwargs: object):
        conn.execute("insert into control_probe values (9)")
        raise RuntimeError("maturity failed")

    monkeypatch.setattr(maturity_task, "_load_candidates", failing_candidates)

    with pytest.raises(RuntimeError, match="maturity failed"):
        maturity_task.mature_livermore_candidate_outcomes(
            db_path,
            evaluation_as_of_date="2026-09-15",
        )

    _assert_writer_lifecycle(events)
    assert request_sentinel == []
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        assert conn.execute("select value from control_probe").fetchall() == [(7,)]
    finally:
        conn.close()

    child = subprocess.run(
        [sys.executable, "-c", _lock_reacquire_script(), str(db_path)],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert child.returncode == 0, child.stderr
    assert child.stdout.strip() == "acquired"


def _named_lock_holder_script() -> str:
    return """
from pathlib import Path
import sys
from _pytest_duckdb_guard import install_pytest_duckdb_guard
install_pytest_duckdb_guard(repo_root=Path.cwd())
from backend.app.governance.locks import LockDefinition, acquire_lock
target = Path(sys.argv[1])
definition = LockDefinition(key=sys.argv[2], ttl_seconds=600)
with acquire_lock(definition, base_dir=target.parent, timeout_seconds=0.5):
    print("ready", flush=True)
    sys.stdin.readline()
"""


def test_maturity_second_lock_failure_releases_writer_without_native_open(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    request_sentinel: list[tuple[str, str]],
) -> None:
    db_path = tmp_path / "maturity-second-lock.duckdb"
    _seed_empty_maturity_database(db_path)
    special_lock = maturity_task.LIVERMORE_CANDIDATE_OUTCOME_LOCK
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            _named_lock_holder_script(),
            str(db_path),
            special_lock.key,
        ],
        cwd=Path.cwd(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        with ThreadPoolExecutor(max_workers=1) as executor:
            readiness = executor.submit(holder.stdout.readline)
            try:
                assert readiness.result(timeout=5).strip() == "ready"
            except FutureTimeoutError:
                holder.terminate()
                raise AssertionError(
                    "lock holder did not report readiness within 5 seconds"
                ) from None

        events = _install_lock_trace(
            monkeypatch,
            db_path=db_path,
            task_module=maturity_task,
            no_wait_lock=special_lock,
        )
        with pytest.raises(TimeoutError, match="Timed out acquiring lock"):
            maturity_task.mature_livermore_candidate_outcomes(
                db_path,
                evaluation_as_of_date="2026-09-15",
            )
        assert events == ["writer_acquired", "writer_released"]
        assert request_sentinel == []
    finally:
        if holder.stdin is not None:
            holder.stdin.write("release\n")
            holder.stdin.flush()
        try:
            _stdout, stderr = holder.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            holder.terminate()
            _stdout, stderr = holder.communicate(timeout=5)
        assert holder.returncode == 0, stderr


def test_writer_lock_precedes_native_open_and_covers_early_return(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    request_sentinel: list[tuple[str, str]],
) -> None:
    db_path = tmp_path / "candidate.duckdb"
    events = _install_lock_trace(monkeypatch, db_path=db_path)
    _patch_local_inputs(monkeypatch)
    monkeypatch.setattr(
        candidate_task,
        "load_livermore_strategy_payload_from_connection",
        lambda *_args, **_kwargs: ({"as_of_date": None}, {"source_version": "sv-test"}),
    )

    result = candidate_task.materialize_livermore_candidate_history(str(db_path))

    assert result["status"] == "partial"
    assert result["row_count"] == 0
    assert result["skipped"] == ["missing_resolved_as_of_date"]
    _assert_writer_lifecycle(events)
    assert request_sentinel == []


def test_writer_admission_preserves_success_result_and_control_row(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    request_sentinel: list[tuple[str, str]],
) -> None:
    db_path = tmp_path / "success.duckdb"
    snapshot_date = date(2026, 9, 15)
    stock_code = "000001.SZ"
    _seed_observations_and_control(
        db_path,
        snapshot_date=snapshot_date,
        stock_code=stock_code,
    )
    events = _install_lock_trace(monkeypatch, db_path=db_path)
    _patch_local_inputs(monkeypatch)
    monkeypatch.setattr(
        candidate_task,
        "_choice_stock_inputs_have_full_coverage",
        lambda **_kwargs: True,
    )
    monkeypatch.setattr(
        candidate_task,
        "load_livermore_strategy_payload_from_connection",
        lambda *_args, **_kwargs: _strategy_payload(
            snapshot_date=snapshot_date,
            items=[
                {
                    "rank": 1,
                    "stock_code": stock_code,
                    "stock_name": "Ping",
                    "sector_code": "S1",
                    "sector_name": "Bank",
                }
            ],
        ),
    )

    result = candidate_task.materialize_livermore_candidate_history(
        str(db_path),
        as_of_date=snapshot_date.isoformat(),
    )

    assert result["status"] == "ok"
    assert result["row_count"] == 1
    assert result["empty_result"] is False
    assert result["snapshot_as_of_date"] == snapshot_date.isoformat()
    assert isinstance(result["run_id"], str)
    assert isinstance(result["strategy_payload_sha256"], str)
    assert len(result["strategy_payload_sha256"]) == 64
    assert isinstance(result["candidate_history_sha256"], str)
    assert len(result["candidate_history_sha256"]) == 64
    assert result["input_snapshot_before"] == result["input_snapshot_after"]
    _assert_writer_lifecycle(events)
    assert request_sentinel == []

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        assert conn.execute("select value from control_probe").fetchall() == [(7,)]
        assert conn.execute(
            "select stock_code, candidate_rank from livermore_candidate_history"
        ).fetchall() == [(stock_code, 1)]
    finally:
        conn.close()


def test_writer_admission_preserves_ready_empty_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    request_sentinel: list[tuple[str, str]],
) -> None:
    db_path = tmp_path / "ready-empty.duckdb"
    snapshot_date = date(2026, 9, 15)
    _seed_observations_and_control(db_path, snapshot_date=snapshot_date)
    events = _install_lock_trace(monkeypatch, db_path=db_path)
    _patch_local_inputs(monkeypatch)
    monkeypatch.setattr(
        candidate_task,
        "_choice_stock_inputs_have_full_coverage",
        lambda **_kwargs: True,
    )
    monkeypatch.setattr(
        candidate_task,
        "load_livermore_strategy_payload_from_connection",
        lambda *_args, **_kwargs: _strategy_payload(
            snapshot_date=snapshot_date,
            items=[],
        ),
    )

    result = candidate_task.materialize_livermore_candidate_history(
        str(db_path),
        as_of_date=snapshot_date.isoformat(),
    )

    assert result["status"] == "ok"
    assert result["row_count"] == 0
    assert result["empty_result"] is True
    assert result["skipped"] == ["no_strategy_signals"]
    assert result["input_coverage_status"] == "ready"
    assert result["input_snapshot_before"] == result["input_snapshot_after"]
    _assert_writer_lifecycle(events)
    assert request_sentinel == []

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        assert conn.execute("select value from control_probe").fetchall() == [(7,)]
        assert conn.execute(
            "select count(*) from livermore_candidate_history"
        ).fetchone() == (0,)
    finally:
        conn.close()


def _lock_reacquire_script() -> str:
    return """
from pathlib import Path
import sys
from _pytest_duckdb_guard import install_pytest_duckdb_guard
install_pytest_duckdb_guard(repo_root=Path.cwd())
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
target = Path(sys.argv[1])
with acquire_lock(resolve_duckdb_writer_lock(target), base_dir=target.parent, timeout_seconds=0.5):
    print("acquired", flush=True)
"""


def test_writer_admission_rolls_back_and_releases_after_loader_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    request_sentinel: list[tuple[str, str]],
) -> None:
    db_path = tmp_path / "failure.duckdb"
    snapshot_date = date(2026, 9, 15)
    _seed_observations_and_control(db_path, snapshot_date=snapshot_date)
    events = _install_lock_trace(monkeypatch, db_path=db_path)
    _patch_local_inputs(monkeypatch)

    def failing_loader(conn: Any, **_kwargs: object):
        conn.execute("insert into control_probe values (9)")
        raise RuntimeError("strategy failed")

    monkeypatch.setattr(
        candidate_task,
        "load_livermore_strategy_payload_from_connection",
        failing_loader,
    )

    with pytest.raises(RuntimeError, match="strategy failed"):
        candidate_task.materialize_livermore_candidate_history(
            str(db_path),
            as_of_date=snapshot_date.isoformat(),
        )

    _assert_writer_lifecycle(events)
    assert request_sentinel == []
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        assert conn.execute("select value from control_probe").fetchall() == [(7,)]
    finally:
        conn.close()

    child = subprocess.run(
        [sys.executable, "-c", _lock_reacquire_script(), str(db_path)],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert child.returncode == 0, child.stderr
    assert child.stdout.strip() == "acquired"


@pytest.mark.parametrize("failure_stage", ["loader", "compute"])
def test_candidate_rollback_error_still_closes_before_writer_release(
    failure_stage: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    request_sentinel: list[tuple[str, str]],
) -> None:
    db_path = tmp_path / f"rollback-error-{failure_stage}.duckdb"
    snapshot_date = date(2026, 9, 15)
    stock_code = "000001.SZ"
    _seed_observations_and_control(
        db_path,
        snapshot_date=snapshot_date,
        stock_code=stock_code,
    )
    events = _install_lock_trace(
        monkeypatch,
        db_path=db_path,
        rollback_error="rollback cleanup failed",
    )
    _patch_local_inputs(monkeypatch)

    if failure_stage == "loader":

        def failing_loader(conn: Any, **_kwargs: object):
            conn.execute("insert into control_probe values (9)")
            raise ValueError("loader failed")

        monkeypatch.setattr(
            candidate_task,
            "load_livermore_strategy_payload_from_connection",
            failing_loader,
        )
    else:
        monkeypatch.setattr(
            candidate_task,
            "_choice_stock_inputs_have_full_coverage",
            lambda **_kwargs: True,
        )
        monkeypatch.setattr(
            candidate_task,
            "load_livermore_strategy_payload_from_connection",
            lambda *_args, **_kwargs: _strategy_payload(
                snapshot_date=snapshot_date,
                items=[{"rank": 1, "stock_code": stock_code}],
            ),
        )

        def failing_compute(conn: Any, **_kwargs: object):
            conn.execute("insert into control_probe values (9)")
            raise ValueError("compute failed")

        monkeypatch.setattr(
            candidate_task,
            "_forward_returns_for_candidate",
            failing_compute,
        )

    with pytest.raises(RuntimeError, match="rollback cleanup failed"):
        candidate_task.materialize_livermore_candidate_history(
            str(db_path),
            as_of_date=snapshot_date.isoformat(),
        )

    assert events == [
        "writer_acquired",
        "native_open",
        "rollback_error_after_execute",
        "native_close",
        "writer_released",
    ]
    assert request_sentinel == []
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        assert conn.execute("select value from control_probe").fetchall() == [(7,)]
    finally:
        conn.close()

    child = subprocess.run(
        [sys.executable, "-c", _lock_reacquire_script(), str(db_path)],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert child.returncode == 0, child.stderr
    assert child.stdout.strip() == "acquired"


def _lock_holder_script() -> str:
    return """
from pathlib import Path
import sys
from _pytest_duckdb_guard import install_pytest_duckdb_guard
install_pytest_duckdb_guard(repo_root=Path.cwd())
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
target = Path(sys.argv[1])
with acquire_lock(resolve_duckdb_writer_lock(target), base_dir=target.parent, timeout_seconds=0.5):
    print("ready", flush=True)
    sys.stdin.readline()
"""


def test_writer_lock_contention_fails_before_native_open(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    request_sentinel: list[tuple[str, str]],
) -> None:
    db_path = tmp_path / "contended.duckdb"
    native_open_count = 0
    real_connect = candidate_task.duckdb.connect

    def counted_connect(*args: object, **kwargs: object):
        nonlocal native_open_count
        database = Path(str(args[0])).resolve()
        if database == db_path.resolve() and kwargs.get("read_only") is False:
            native_open_count += 1
        return real_connect(*args, **kwargs)

    @contextmanager
    def no_wait_acquire(*args: object, **kwargs: object) -> Iterator[Path]:
        definition = args[0]
        with acquire_real_lock(
            definition,
            base_dir=kwargs.get("base_dir", db_path.parent),
            timeout_seconds=0.0,
        ) as lock_path:
            yield lock_path

    monkeypatch.setattr(candidate_task.duckdb, "connect", counted_connect)
    monkeypatch.setattr(candidate_task, "acquire_lock", no_wait_acquire)
    holder = subprocess.Popen(
        [sys.executable, "-c", _lock_holder_script(), str(db_path)],
        cwd=Path.cwd(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        with ThreadPoolExecutor(max_workers=1) as executor:
            readiness = executor.submit(holder.stdout.readline)
            try:
                assert readiness.result(timeout=5).strip() == "ready"
            except FutureTimeoutError:
                holder.terminate()
                raise AssertionError(
                    "lock holder did not report readiness within 5 seconds"
                ) from None
        with pytest.raises(TimeoutError, match="Timed out acquiring lock"):
            candidate_task.materialize_livermore_candidate_history(str(db_path))
        assert native_open_count == 0
        assert request_sentinel == []
    finally:
        if holder.stdin is not None:
            holder.stdin.write("release\n")
            holder.stdin.flush()
        try:
            _stdout, stderr = holder.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            holder.terminate()
            _stdout, stderr = holder.communicate(timeout=5)
        assert holder.returncode == 0, stderr
