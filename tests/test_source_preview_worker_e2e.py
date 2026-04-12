from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from tests.helpers import ROOT, load_module
from tests.test_bond_analytics_materialize_flow import _seed_bond_snapshot_rows
from tests.test_balance_analysis_materialize_flow import _seed_snapshot_and_fx_tables
from tests.test_product_category_pnl_flow import _write_month_pair


def test_source_preview_refresh_real_worker_e2e(tmp_path, monkeypatch):
    redis_server = _redis_server_path()
    if redis_server is None:
        pytest.skip("redis-server is not available on this machine")

    redis_port = _find_free_port()
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    data_root = tmp_path / "data_input"
    redis_dir = tmp_path / "redis"
    data_root.mkdir(parents=True, exist_ok=True)
    redis_dir.mkdir(parents=True, exist_ok=True)

    for file_name in ("ZQTZSHOW-20251231.xls", "TYWLSHOW-20251231.xls"):
        (data_root / file_name).write_bytes((ROOT / "data_input" / file_name).read_bytes())

    monkeypatch.setenv("MOSS_REDIS_DSN", f"redis://127.0.0.1:{redis_port}/0")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    monkeypatch.setenv("MOSS_DATA_INPUT_ROOT", str(data_root))
    get_settings.cache_clear()
    _reset_source_preview_modules()

    redis_proc = _start_redis_server(redis_server=redis_server, port=redis_port, work_dir=redis_dir)
    worker_proc = None
    try:
        _wait_for_port(redis_port)
        worker_proc = _start_worker_subprocess(redis_port=redis_port)
        time.sleep(1.5)

        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        refresh_response = client.post("/ui/preview/source-foundation/refresh")

        assert refresh_response.status_code == 200
        refresh_payload = refresh_response.json()
        assert refresh_payload["status"] == "queued"
        assert refresh_payload["trigger_mode"] == "async"
        run_id = refresh_payload["run_id"]

        status_payload = _wait_for_completed_status(client=client, run_id=run_id)
        assert status_payload["status"] == "completed"
        assert status_payload["run_id"] == run_id

        foundation_response = client.get("/ui/preview/source-foundation")
        assert foundation_response.status_code == 200
        assert {row["source_family"] for row in foundation_response.json()["result"]["sources"]} == {
            "zqtz",
            "tyw",
        }

        governance_rows = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
        matched = [row for row in governance_rows if row.get("run_id") == run_id]
        assert {row["status"] for row in matched} >= {"queued", "running", "completed"}

        conn = duckdb.connect(str(duckdb_path), read_only=True)
        try:
            families = {
                row[0]
                for row in conn.execute(
                    "select source_family from phase1_source_preview_summary"
                ).fetchall()
            }
        finally:
            conn.close()

        assert families == {"zqtz", "tyw"}
    finally:
        _stop_process(worker_proc)
        _stop_process(redis_proc)
        get_settings.cache_clear()
        _reset_source_preview_modules()


def test_product_category_refresh_real_worker_e2e(tmp_path, monkeypatch):
    redis_server = _redis_server_path()
    if redis_server is None:
        pytest.skip("redis-server is not available on this machine")

    redis_port = _find_free_port()
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    data_root = tmp_path / "data_input"
    source_dir = data_root / "pnl_总账对账-日均"
    redis_dir = tmp_path / "redis"
    archive_dir.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)
    redis_dir.mkdir(parents=True, exist_ok=True)

    _write_month_pair(source_dir, "202601", january=True)
    _write_month_pair(source_dir, "202602", january=False)

    monkeypatch.setenv("MOSS_REDIS_DSN", f"redis://127.0.0.1:{redis_port}/0")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    monkeypatch.setenv("MOSS_PRODUCT_CATEGORY_SOURCE_DIR", str(source_dir))
    get_settings.cache_clear()
    _reset_source_preview_modules()

    redis_proc = _start_redis_server(redis_server=redis_server, port=redis_port, work_dir=redis_dir)
    worker_proc = None
    try:
        _wait_for_port(redis_port)
        worker_proc = _start_worker_subprocess(redis_port=redis_port)
        time.sleep(1.5)

        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        refresh_response = client.post(
            "/ui/pnl/product-category/refresh",
        )

        assert refresh_response.status_code == 200
        refresh_payload = refresh_response.json()
        assert refresh_payload["status"] == "queued"
        assert refresh_payload["trigger_mode"] == "async"
        run_id = refresh_payload["run_id"]

        status_payload = _wait_for_completed_status(
            client=client,
            run_id=run_id,
            path="/ui/pnl/product-category/refresh-status",
        )
        assert status_payload["status"] == "completed"
        assert status_payload["run_id"] == run_id

        dates_response = client.get("/ui/pnl/product-category/dates")
        assert dates_response.status_code == 200
        assert dates_response.json()["result"]["report_dates"] == ["2026-02-28", "2026-01-31"]

        detail_response = client.get(
            "/ui/pnl/product-category",
            params={"report_date": "2026-02-28", "view": "monthly"},
        )
        assert detail_response.status_code == 200
        assert detail_response.json()["result"]["view"] == "monthly"

        governance_rows = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
        matched = [row for row in governance_rows if row.get("run_id") == run_id]
        assert {row["status"] for row in matched} >= {"queued", "running", "completed"}
    finally:
        _stop_process(worker_proc)
        _stop_process(redis_proc)
        get_settings.cache_clear()
        _reset_source_preview_modules()


def test_balance_analysis_refresh_real_worker_e2e(tmp_path, monkeypatch):
    redis_server = _redis_server_path()
    if redis_server is None:
        pytest.skip("redis-server is not available on this machine")

    redis_port = _find_free_port()
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    redis_dir = tmp_path / "redis"
    archive_dir.mkdir(parents=True, exist_ok=True)
    redis_dir.mkdir(parents=True, exist_ok=True)

    _seed_snapshot_and_fx_tables(str(duckdb_path))

    monkeypatch.setenv("MOSS_REDIS_DSN", f"redis://127.0.0.1:{redis_port}/0")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    get_settings.cache_clear()
    _reset_source_preview_modules()

    redis_proc = _start_redis_server(redis_server=redis_server, port=redis_port, work_dir=redis_dir)
    worker_proc = None
    try:
        _wait_for_port(redis_port)
        worker_proc = _start_worker_subprocess(redis_port=redis_port)
        time.sleep(1.5)

        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        refresh_response = client.post(
            "/ui/balance-analysis/refresh",
            params={"report_date": "2025-12-31"},
        )

        assert refresh_response.status_code == 200
        refresh_payload = refresh_response.json()
        assert refresh_payload["status"] == "queued"
        assert refresh_payload["trigger_mode"] == "async"
        run_id = refresh_payload["run_id"]

        status_payload = _wait_for_completed_status(
            client=client,
            run_id=run_id,
            path="/ui/balance-analysis/refresh-status",
        )
        assert status_payload["status"] == "completed"
        assert status_payload["run_id"] == run_id

        overview_response = client.get(
            "/ui/balance-analysis/overview",
            params={
                "report_date": "2025-12-31",
                "position_scope": "all",
                "currency_basis": "CNY",
            },
        )
        assert overview_response.status_code == 200
        overview_payload = overview_response.json()
        assert overview_payload["result"]["detail_row_count"] == 2
        assert overview_payload["result"]["summary_row_count"] == 2

        governance_rows = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
        matched = [row for row in governance_rows if row.get("run_id") == run_id]
        assert {row["status"] for row in matched} >= {"queued", "running", "completed"}
    finally:
        _stop_process(worker_proc)
        _stop_process(redis_proc)
        get_settings.cache_clear()
        _reset_source_preview_modules()


def test_bond_analytics_refresh_real_worker_e2e(tmp_path, monkeypatch):
    redis_server = _redis_server_path()
    if redis_server is None:
        pytest.skip("redis-server is not available on this machine")

    redis_port = _find_free_port()
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    redis_dir = tmp_path / "redis"
    archive_dir.mkdir(parents=True, exist_ok=True)
    redis_dir.mkdir(parents=True, exist_ok=True)

    _seed_bond_snapshot_rows(str(duckdb_path))

    monkeypatch.setenv("MOSS_REDIS_DSN", f"redis://127.0.0.1:{redis_port}/0")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_OBJECT_STORE_MODE", "local")
    monkeypatch.setenv("MOSS_LOCAL_ARCHIVE_PATH", str(archive_dir))
    get_settings.cache_clear()
    _reset_source_preview_modules()

    redis_proc = _start_redis_server(redis_server=redis_server, port=redis_port, work_dir=redis_dir)
    worker_proc = None
    try:
        _wait_for_port(redis_port)
        worker_proc = _start_worker_subprocess(redis_port=redis_port)
        time.sleep(1.5)

        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        refresh_response = client.post(
            "/api/bond-analytics/refresh",
            params={"report_date": "2026-03-31"},
        )

        assert refresh_response.status_code == 200
        refresh_payload = refresh_response.json()
        assert refresh_payload["status"] == "queued"
        assert refresh_payload["trigger_mode"] == "async"
        run_id = refresh_payload["run_id"]

        status_payload = _wait_for_completed_status(
            client=client,
            run_id=run_id,
            path="/api/bond-analytics/refresh-status",
        )
        assert status_payload["status"] == "completed"
        assert status_payload["run_id"] == run_id

        risk_response = client.get(
            "/api/bond-analytics/krd-curve-risk",
            params={"report_date": "2026-03-31"},
        )
        assert risk_response.status_code == 200
        risk_payload = risk_response.json()
        assert risk_payload["result"]["portfolio_dv01"] != "0.00000000"
        assert risk_payload["result"]["krd_buckets"]

        governance_rows = GovernanceRepository(base_dir=governance_dir).read_all(CACHE_BUILD_RUN_STREAM)
        matched = [row for row in governance_rows if row.get("run_id") == run_id]
        assert {row["status"] for row in matched} >= {"queued", "running", "completed"}
    finally:
        _stop_process(worker_proc)
        _stop_process(redis_proc)
        get_settings.cache_clear()
        _reset_source_preview_modules()


def _redis_server_path() -> str | None:
    if os.name == "nt":
        candidate = Path(r"C:\Program Files\Redis\redis-server.exe")
        if candidate.exists():
            return str(candidate)
    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        candidate = Path(path_dir) / ("redis-server.exe" if os.name == "nt" else "redis-server")
        if candidate.exists():
            return str(candidate)
    return None


def _find_free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def _start_redis_server(*, redis_server: str, port: int, work_dir: Path) -> subprocess.Popen:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
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
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )


def _start_worker_subprocess(*, redis_port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env["MOSS_REDIS_DSN"] = f"redis://127.0.0.1:{redis_port}/0"
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "dramatiq",
            "--processes",
            "1",
            "--threads",
            "1",
            "backend.app.tasks.worker_bootstrap",
        ],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )


def _wait_for_port(port: int, timeout_seconds: float = 10.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for TCP port {port}")


def _wait_for_completed_status(
    *,
    client: TestClient,
    run_id: str,
    path: str = "/ui/preview/source-foundation/refresh-status",
    timeout_seconds: float = 20.0,
) -> dict[str, object]:
    deadline = time.time() + timeout_seconds
    latest_payload: dict[str, object] | None = None
    while time.time() < deadline:
        response = client.get(path, params={"run_id": run_id})
        assert response.status_code == 200
        latest_payload = response.json()
        if latest_payload["status"] == "completed":
            return latest_payload
        if latest_payload["status"] == "failed":
            raise AssertionError(f"worker run failed: {latest_payload}")
        time.sleep(0.2)
    raise AssertionError(f"Timed out waiting for completed source preview refresh: {latest_payload}")


def _stop_process(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _reset_source_preview_modules() -> None:
    prefixes = (
        "backend.app.main",
        "backend.app.api",
        "backend.app.schemas.balance_analysis",
        "backend.app.tasks.broker",
        "backend.app.tasks.source_preview_refresh",
        "backend.app.tasks.balance_analysis_materialize",
        "backend.app.tasks.bond_analytics_materialize",
        "backend.app.tasks.product_category_pnl",
        "backend.app.services.source_preview_refresh_service",
        "backend.app.services.balance_analysis_service",
        "backend.app.services.bond_analytics_service",
        "backend.app.services.product_category_pnl_service",
    )
    for module_name in list(sys.modules):
        if module_name.startswith(prefixes):
            sys.modules.pop(module_name, None)
