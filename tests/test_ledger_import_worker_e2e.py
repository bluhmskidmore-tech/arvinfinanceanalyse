from __future__ import annotations

import csv
import io
import os
import socket
import subprocess
import sys
import time
from contextlib import ExitStack
from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import Any, BinaryIO, Iterator

import dramatiq
import duckdb
import pytest
from dramatiq.brokers.redis import RedisBroker
from dramatiq.errors import QueueJoinTimeout
from fastapi.testclient import TestClient

from tests.helpers import ROOT, load_module

JOB_TIMEOUT_MS = 60_000
ALLOWED_PROMETHEUS_FAILURES = {
    ("before_process_message", "inprogress_messages"),
    ("after_process_message", "message_durations"),
    ("after_nack", "total_rejected_messages"),
}


@dataclass
class _ManagedProcess:
    proc: subprocess.Popen[bytes]
    log_path: Path
    log_file: BinaryIO


@dataclass(frozen=True)
class _LedgerFacts:
    batches: tuple[tuple[int, str, str, int], ...]
    raw_rows: tuple[tuple[int, int], ...]
    snapshots: tuple[tuple[int, int, str, str], ...]


@dataclass
class _LiveLedger:
    tmp_path: Path
    duckdb_path: Path
    broker: Any
    actor: Any
    client: Any
    worker: _ManagedProcess | None = None
    worker_index: int = 0
    workers: list[_ManagedProcess] = field(default_factory=list)

    def start_worker(self) -> None:
        assert self.worker is None
        self.worker_index += 1
        self.worker = _start_worker_subprocess(
            log_path=self.tmp_path / f"worker-{self.worker_index}.log"
        )
        self.workers.append(self.worker)
        _wait_for_worker_ready(self.worker)

    def stop_worker(self) -> None:
        _stop_process(self.worker)
        self.worker = None

    def join(self) -> None:
        try:
            self.broker.join(
                self.actor.queue_name,
                interval=100,
                timeout=JOB_TIMEOUT_MS,
            )
        except QueueJoinTimeout as exc:
            raise AssertionError(
                "Timed out waiting for the real Ledger worker queue. "
                f"{_queue_diagnostics(self)}"
            ) from exc
        except Exception as exc:
            raise AssertionError(
                f"Ledger queue join failed: {exc!r}. {_queue_diagnostics(self)}"
            ) from exc


@pytest.fixture
def live_ledger(tmp_path, monkeypatch) -> Iterator[_LiveLedger]:
    redis_server = _redis_server_path()
    if redis_server is None:
        pytest.skip("redis-server is not available on this machine")

    redis_port = _find_free_port()
    redis_dir = tmp_path / "redis"
    redis_dir.mkdir()
    duckdb_path = tmp_path / "ledger-e2e.duckdb"
    authority_path = tmp_path / "auth-governance.db"
    authority_dsn = f"sqlite:///{authority_path.as_posix()}"

    monkeypatch.setenv("MOSS_ENVIRONMENT", "development")
    monkeypatch.setenv("MOSS_REDIS_DSN", f"redis://127.0.0.1:{redis_port}/0")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_POSTGRES_DSN", authority_dsn)
    monkeypatch.setenv("MOSS_GOVERNANCE_SQL_DSN", authority_dsn)
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(tmp_path / "archive"))
    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(tmp_path / "data-input"))

    original_broker = dramatiq.get_broker()
    redis_process: _ManagedProcess | None = None
    producer_broker: RedisBroker | None = None
    client: TestClient | None = None
    live: _LiveLedger | None = None
    _reset_ledger_modules()
    try:
        from backend.app.repositories.user_scope_repo import UserScopeRepository

        scopes = UserScopeRepository(authority_dsn)
        scopes.grant_scope(
            user_id="*",
            role=None,
            resource="ledger.data",
            action="import",
        )

        redis_process = _start_redis_server(
            redis_server=redis_server,
            port=redis_port,
            work_dir=redis_dir,
            log_path=tmp_path / "redis.log",
        )
        _wait_for_port(redis_process, redis_port)

        broker_module = import_module("backend.app.tasks.broker")
        task_module = import_module("backend.app.tasks.ledger_import")
        producer_broker = broker_module.get_broker()
        assert isinstance(producer_broker, RedisBroker)
        assert task_module.run_ledger_import.broker is producer_broker

        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        live = _LiveLedger(
            tmp_path=tmp_path,
            duckdb_path=duckdb_path,
            broker=producer_broker,
            actor=task_module.run_ledger_import,
            client=client,
        )
        live.start_worker()
        yield live
    finally:
        _cleanup_live_ledger(
            live=live,
            client=client,
            producer_broker=producer_broker,
            redis_process=redis_process,
            original_broker=original_broker,
        )


def test_ledger_import_api_real_worker_deduplicates_and_recovers_queued_work(
    live_ledger: _LiveLedger,
) -> None:
    assert isinstance(live_ledger.broker, RedisBroker)
    first_content = _ledger_csv_bytes(
        bond_code="LIVE-001",
        as_of_date="2026-03-17",
    )

    first = _post_ledger(live_ledger.client, "ZQTZSHOW-20260317.csv", first_content)
    assert first.status_code == 202
    assert first.json()["data"]["status"] == "queued"
    assert first.json()["data"]["run_id"].startswith("ledger_import:")
    live_ledger.join()

    first_facts = _wait_for_facts(
        live_ledger.duckdb_path,
        batch_count=1,
        raw_count=1,
        snapshot_count=1,
        worker=live_ledger.worker,
    )
    assert first_facts.batches == ((1, "ZQTZSHOW-20260317.csv", "2026-03-17", 1),)
    assert first_facts.raw_rows == ((1, 1),)
    assert first_facts.snapshots == ((1, 1, "2026-03-17", "LIVE-001"),)

    duplicate = _post_ledger(live_ledger.client, "same-content-new-name.csv", first_content)
    assert duplicate.status_code == 202
    assert duplicate.json()["data"]["status"] == "queued"
    assert duplicate.json()["data"]["run_id"].startswith("ledger_import:")
    live_ledger.join()
    assert _wait_for_facts(
        live_ledger.duckdb_path,
        batch_count=1,
        raw_count=1,
        snapshot_count=1,
        worker=live_ledger.worker,
    ) == first_facts

    live_ledger.stop_worker()
    second_content = _ledger_csv_bytes(
        bond_code="LIVE-002",
        as_of_date="2026-03-18",
    )
    queued_while_stopped = _post_ledger(
        live_ledger.client,
        "ZQTZSHOW-20260318.csv",
        second_content,
    )
    assert queued_while_stopped.status_code == 202
    assert queued_while_stopped.json()["data"]["status"] == "queued"
    assert queued_while_stopped.json()["data"]["run_id"].startswith("ledger_import:")
    assert live_ledger.broker.do_qsize(live_ledger.actor.queue_name) > 0
    assert _read_facts_with_retry(live_ledger.duckdb_path) == first_facts

    live_ledger.start_worker()
    live_ledger.join()
    recovered = _wait_for_facts(
        live_ledger.duckdb_path,
        batch_count=2,
        raw_count=2,
        snapshot_count=2,
        worker=live_ledger.worker,
    )
    assert recovered.batches == (
        (1, "ZQTZSHOW-20260317.csv", "2026-03-17", 1),
        (2, "ZQTZSHOW-20260318.csv", "2026-03-18", 1),
    )
    assert recovered.raw_rows == ((1, 1), (2, 1))
    assert recovered.snapshots == (
        (1, 1, "2026-03-17", "LIVE-001"),
        (2, 1, "2026-03-18", "LIVE-002"),
    )


def test_ledger_import_failed_message_does_not_kill_real_worker(
    live_ledger: _LiveLedger,
) -> None:
    assert isinstance(live_ledger.broker, RedisBroker)
    live_ledger.actor.send_with_options(
        kwargs={
            "file_name": "invalid.csv",
            "content_base64": "%%%not-base64%%%",
            "duckdb_path": str(live_ledger.duckdb_path),
            "run_id": "ledger_import:invalid-e2e",
        },
        max_retries=0,
    )
    live_ledger.join()

    empty = _wait_for_facts(
        live_ledger.duckdb_path,
        batch_count=0,
        raw_count=0,
        snapshot_count=0,
        worker=live_ledger.worker,
    )
    assert empty == _LedgerFacts(batches=(), raw_rows=(), snapshots=())
    assert live_ledger.worker is not None
    assert live_ledger.worker.proc.poll() is None, _process_diagnostics(live_ledger.worker)

    content = _ledger_csv_bytes(
        bond_code="AFTER-FAILURE",
        as_of_date="2026-03-19",
    )
    accepted = _post_ledger(
        live_ledger.client,
        "ZQTZSHOW-20260319.csv",
        content,
    )
    assert accepted.status_code == 202
    assert accepted.json()["data"]["status"] == "queued"
    assert accepted.json()["data"]["run_id"].startswith("ledger_import:")
    live_ledger.join()

    recovered = _wait_for_facts(
        live_ledger.duckdb_path,
        batch_count=1,
        raw_count=1,
        snapshot_count=1,
        worker=live_ledger.worker,
    )
    assert recovered.batches == ((1, "ZQTZSHOW-20260319.csv", "2026-03-19", 1),)
    assert recovered.raw_rows == ((1, 1),)
    assert recovered.snapshots == ((1, 1, "2026-03-19", "AFTER-FAILURE"),)
    assert live_ledger.worker.proc.poll() is None, _process_diagnostics(live_ledger.worker)


def test_cleanup_runs_every_stage_and_propagates_failure(monkeypatch) -> None:
    events: list[str] = []

    class CleanupFailure(RuntimeError):
        pass

    def fail_worker_stop() -> None:
        events.append("worker")
        raise CleanupFailure("worker stop failed")

    live = SimpleNamespace(
        stop_worker=fail_worker_stop,
        workers=[],
        client=SimpleNamespace(close=lambda: events.append("client")),
        broker=SimpleNamespace(close=lambda: events.append("broker")),
    )
    redis_process = object()
    original_broker = object()
    monkeypatch.setattr(
        sys.modules[__name__],
        "_assert_worker_logs_healthy",
        lambda _workers: events.append("logs"),
        raising=False,
    )
    monkeypatch.setattr(
        sys.modules[__name__],
        "_stop_process",
        lambda managed: events.append("redis") if managed is redis_process else None,
    )
    monkeypatch.setattr(
        dramatiq,
        "set_broker",
        lambda broker: events.append("restore") if broker is original_broker else None,
    )
    monkeypatch.setattr(
        sys.modules[__name__],
        "_reset_ledger_modules",
        lambda: events.append("reset"),
    )

    with pytest.raises(CleanupFailure, match="worker stop failed"):
        _cleanup_live_ledger(
            live=live,
            client=None,
            producer_broker=None,
            redis_process=redis_process,
            original_broker=original_broker,
        )

    assert events == ["worker", "logs", "client", "broker", "redis", "restore", "reset"]


@pytest.mark.parametrize("starter", ["redis", "worker"])
def test_start_helpers_close_log_when_popen_fails(tmp_path, monkeypatch, starter: str) -> None:
    log_file = io.BytesIO()

    def fail_popen(*_args, **_kwargs):
        raise OSError("injected Popen failure")

    monkeypatch.setattr(Path, "open", lambda *_args, **_kwargs: log_file)
    monkeypatch.setattr(subprocess, "Popen", fail_popen)

    with pytest.raises(OSError, match="injected Popen failure"):
        if starter == "redis":
            _start_redis_server(
                redis_server="redis-server",
                port=6380,
                work_dir=tmp_path,
                log_path=tmp_path / "redis.log",
            )
        else:
            _start_worker_subprocess(log_path=tmp_path / "worker.log")

    assert log_file.closed


def test_join_reports_queue_timeout_separately_from_other_failures(tmp_path) -> None:
    timeout = QueueJoinTimeout("default")
    failed = RuntimeError("redis connection lost")

    for error, expected_message in (
        (timeout, "Timed out waiting for the real Ledger worker queue"),
        (failed, "Ledger queue join failed"),
    ):
        broker = SimpleNamespace(join=lambda *_args, **_kwargs: (_ for _ in ()).throw(error))
        live = _LiveLedger(
            tmp_path=tmp_path,
            duckdb_path=tmp_path / "unused.duckdb",
            broker=broker,
            actor=SimpleNamespace(queue_name="default"),
            client=SimpleNamespace(),
        )

        with pytest.raises(AssertionError, match=expected_message) as exc_info:
            live.join()

        assert exc_info.value.__cause__ is error
        assert "redis_queue_size_error=" in str(exc_info.value)
        assert "worker=stopped" in str(exc_info.value)


def test_worker_log_health_allows_only_known_prometheus_noise(tmp_path) -> None:
    expected_log = tmp_path / "expected.log"
    expected_log.write_text(
        "ValueError: Ledger import content must be valid base64 ASCII.\n"
        "Unexpected failure in after_process_message of "
        "<dramatiq.middleware.prometheus.Prometheus object at 0x1>.\n"
        "Traceback (most recent call last):\n"
        "AttributeError: 'Prometheus' object has no attribute 'message_durations'\n",
        encoding="utf-8",
    )
    _assert_worker_log_health(expected_log)

    unexpected_log = tmp_path / "unexpected.log"
    unexpected_log.write_text(
        "Unexpected failure in after_process_message of <custom.Middleware>.\n"
        "RuntimeError: broken middleware\n",
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="Unexpected worker middleware failure"):
        _assert_worker_log_health(unexpected_log)

    unknown_prometheus_attr_log = tmp_path / "unknown-prometheus-attr.log"
    unknown_prometheus_attr_log.write_text(
        "Unexpected failure in after_process_message of "
        "<dramatiq.middleware.prometheus.Prometheus object at 0x2>.\n"
        "AttributeError: 'Prometheus' object has no attribute 'brand_new_failure'\n",
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="Unexpected worker middleware failure"):
        _assert_worker_log_health(unknown_prometheus_attr_log)


def _cleanup_live_ledger(
    *,
    live,
    client,
    producer_broker,
    redis_process,
    original_broker,
) -> None:
    active_client = live.client if live is not None else client
    active_broker = live.broker if live is not None else producer_broker
    with ExitStack() as cleanup:
        cleanup.callback(_reset_ledger_modules)
        cleanup.callback(dramatiq.set_broker, original_broker)
        cleanup.callback(_stop_process, redis_process)
        if active_broker is not None:
            cleanup.callback(active_broker.close)
        if active_client is not None:
            cleanup.callback(active_client.close)
        if live is not None:
            cleanup.callback(_assert_worker_logs_healthy, live.workers)
            cleanup.callback(live.stop_worker)


def _queue_diagnostics(live: _LiveLedger) -> str:
    queue_name = live.actor.queue_name
    try:
        redis_queue_state = f"redis_queue_size={live.broker.do_qsize(queue_name)}"
    except Exception as exc:
        redis_queue_state = f"redis_queue_size_error={exc!r}"
    return (
        f"redis_broker={type(live.broker).__name__}, "
        f"queue={queue_name!r}, {redis_queue_state}, {_process_diagnostics(live.worker)}"
    )


def _post_ledger(client: TestClient, file_name: str, content: bytes):
    return client.post(
        "/api/ledger/import",
        files={"file": (file_name, content, "text/csv")},
    )


def _ledger_csv_bytes(*, bond_code: str, as_of_date: str) -> bytes:
    service_module = import_module("backend.app.services.ledger_import_service")
    values = {
        "bond_code": bond_code,
        "bond_name": f"{bond_code}-name",
        "counterparty_cif_no": "3000000001",
        "portfolio": "FIOA",
        "as_of_date": as_of_date,
        "business_type": "bond-investment",
        "business_type_1": "bond-investment",
        "account_category_std": "banking-book",
        "cost_center": "5010",
        "asset_class_std": "held-to-maturity",
        "face_amount": "100.25",
        "fair_value": "99.50",
        "amortized_cost": "98.25",
        "accrued_interest": "1.25",
        "interest_method": "fixed",
        "coupon_rate": "0.025",
        "interest_start_date": "2024-01-01",
        "maturity_date": "2029-01-01",
        "credit_customer_id": "ID-001",
        "credit_customer_rating": "AAA",
        "credit_customer_industry": "financial",
        "interest_receivable_payable": "1.25",
        "currency": "CNY",
    }
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow([service_module.LEDGER_SHEET_NAME])
    writer.writerow([spec.source_field for spec in service_module.FIELD_SPECS])
    writer.writerow([values.get(spec.standard_field, "") for spec in service_module.FIELD_SPECS])
    return output.getvalue().encode("utf-8-sig")


def _read_facts(path: Path) -> _LedgerFacts:
    if not path.is_file():
        return _LedgerFacts(batches=(), raw_rows=(), snapshots=())
    conn = duckdb.connect(str(path), read_only=True)
    try:
        batches = tuple(
            (int(row[0]), str(row[1]), str(row[2]), int(row[3]))
            for row in conn.execute(
                """
                select batch_id, file_name, as_of_date, row_count
                from ledger_import_batch
                order by batch_id
                """
            ).fetchall()
        )
        raw_rows = tuple(
            (int(row[0]), int(row[1]))
            for row in conn.execute(
                "select batch_id, row_no from ledger_raw_row order by batch_id, row_no"
            ).fetchall()
        )
        snapshots = tuple(
            (int(row[0]), int(row[1]), str(row[2]), str(row[3]))
            for row in conn.execute(
                """
                select batch_id, row_no, as_of_date, bond_code
                from position_snapshot
                order by batch_id, row_no
                """
            ).fetchall()
        )
        return _LedgerFacts(batches=batches, raw_rows=raw_rows, snapshots=snapshots)
    finally:
        conn.close()


def _read_facts_with_retry(path: Path, timeout_seconds: float = 5.0) -> _LedgerFacts:
    deadline = time.monotonic() + timeout_seconds
    latest_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return _read_facts(path)
        except (duckdb.Error, OSError) as exc:
            latest_error = exc
            time.sleep(0.1)
    raise AssertionError(f"Unable to read temporary Ledger DuckDB: {latest_error}")


def _wait_for_facts(
    path: Path,
    *,
    batch_count: int,
    raw_count: int,
    snapshot_count: int,
    worker: _ManagedProcess | None,
    timeout_seconds: float = 60.0,
) -> _LedgerFacts:
    deadline = time.monotonic() + timeout_seconds
    latest_facts: _LedgerFacts | None = None
    latest_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            latest_facts = _read_facts(path)
            if (
                len(latest_facts.batches) == batch_count
                and len(latest_facts.raw_rows) == raw_count
                and len(latest_facts.snapshots) == snapshot_count
            ):
                return latest_facts
        except (duckdb.Error, OSError) as exc:
            latest_error = exc
        if worker is not None and worker.proc.poll() is not None:
            raise AssertionError(f"Ledger worker exited early. {_process_diagnostics(worker)}")
        time.sleep(0.1)
    raise AssertionError(
        "Timed out waiting for temporary Ledger facts: "
        f"latest={latest_facts}, error={latest_error}. {_process_diagnostics(worker)}"
    )


def _redis_server_path() -> str | None:
    if os.name == "nt":
        candidate = Path(r"C:\Program Files\Redis\redis-server.exe")
        if candidate.is_file():
            return str(candidate)
    executable = "redis-server.exe" if os.name == "nt" else "redis-server"
    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(path_dir) / executable
        if candidate.is_file():
            return str(candidate)
    return None


def _find_free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_redis_server(
    *,
    redis_server: str,
    port: int,
    work_dir: Path,
    log_path: Path,
) -> _ManagedProcess:
    log_file = log_path.open("wb")
    try:
        proc = subprocess.Popen(
            [
                redis_server,
                "--bind",
                "127.0.0.1",
                "--port",
                str(port),
                "--save",
                "",
                "--appendonly",
                "no",
                "--dir",
                str(work_dir),
            ],
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=_subprocess_creationflags(),
        )
    except BaseException:
        log_file.close()
        raise
    return _ManagedProcess(proc=proc, log_path=log_path, log_file=log_file)


def _start_worker_subprocess(*, log_path: Path) -> _ManagedProcess:
    log_file = log_path.open("wb")
    try:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "backend.app.tasks.dev_worker_runner",
                "--threads",
                "1",
            ],
            cwd=str(ROOT),
            env=os.environ.copy(),
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=_subprocess_creationflags(),
        )
    except BaseException:
        log_file.close()
        raise
    return _ManagedProcess(proc=proc, log_path=log_path, log_file=log_file)


def _wait_for_port(
    redis_process: _ManagedProcess,
    port: int,
    timeout_seconds: float = 10.0,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if redis_process.proc.poll() is not None:
            raise AssertionError(f"Redis exited before readiness. {_process_diagnostics(redis_process)}")
        with socket.socket() as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting 10s for Redis. {_process_diagnostics(redis_process)}")


def _wait_for_worker_ready(worker: _ManagedProcess, timeout_seconds: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if worker.proc.poll() is not None:
            raise AssertionError(f"Ledger worker exited before readiness. {_process_diagnostics(worker)}")
        if "starting in-process Dramatiq worker" in _read_log(worker.log_path):
            return
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for Ledger worker. {_process_diagnostics(worker)}")


def _stop_process(managed: _ManagedProcess | None) -> None:
    if managed is None:
        return
    try:
        if managed.proc.poll() is None:
            managed.proc.terminate()
            try:
                managed.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                managed.proc.kill()
                managed.proc.wait(timeout=5)
    finally:
        managed.log_file.close()


def _subprocess_creationflags() -> int:
    if os.name == "nt":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _read_log(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _assert_worker_logs_healthy(workers: list[_ManagedProcess]) -> None:
    for worker in workers:
        _assert_worker_log_health(worker.log_path)


def _assert_worker_log_health(log_path: Path) -> None:
    lines = _read_log(log_path).splitlines()
    unexpected_indexes = [index for index, line in enumerate(lines) if "Unexpected failure" in line]
    for position, index in enumerate(unexpected_indexes):
        end = (
            unexpected_indexes[position + 1]
            if position + 1 < len(unexpected_indexes)
            else len(lines)
        )
        block = lines[index:end]
        known_prometheus_noise = any(
            f"Unexpected failure in {hook} of "
            "<dramatiq.middleware.prometheus.Prometheus " in lines[index]
            and any(
                f"AttributeError: 'Prometheus' object has no attribute '{attribute}'" in line
                for line in block
            )
            for hook, attribute in ALLOWED_PROMETHEUS_FAILURES
        )
        if not known_prometheus_noise:
            raise AssertionError(
                "Unexpected worker middleware failure: "
                f"log={log_path}, block={block[-40:]}"
            )


def _process_diagnostics(managed: _ManagedProcess | None) -> str:
    if managed is None:
        return "worker=stopped"
    lines = _read_log(managed.log_path).splitlines()
    return f"exit={managed.proc.poll()}, log_tail={lines[-40:]}"


def _reset_ledger_modules() -> None:
    settings_module = sys.modules.get("backend.app.governance.settings")
    if settings_module is not None:
        settings_module.get_settings.cache_clear()
    prefixes = (
        "backend.app.main",
        "backend.app.api",
        "backend.app.security.auth_context",
        "backend.app.tasks.broker",
        "backend.app.tasks.ledger_import",
        "backend.app.services.ledger_import_service",
    )
    for module_name in list(sys.modules):
        if module_name.startswith(prefixes):
            sys.modules.pop(module_name, None)
