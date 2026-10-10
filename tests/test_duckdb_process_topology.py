from __future__ import annotations

import subprocess
import sys

import duckdb
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.source_preview_repo import ensure_source_preview_schema_tables
from backend.app.repositories.user_scope_repo import UserScopeRepository
from tests.helpers import load_module


def test_api_reports_temporary_unavailability_while_worker_process_holds_duckdb(
    tmp_path,
    monkeypatch,
):
    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        ensure_source_preview_schema_tables(conn)
    finally:
        conn.close()

    scope_path = tmp_path / "scopes.db"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{scope_path.as_posix()}")
    monkeypatch.setenv("MOSS_SOURCE_PREVIEW_HTTP_ENABLED", "true")
    get_settings.cache_clear()
    scope_repo = UserScopeRepository(get_settings().postgres_dsn)
    scope_repo.grant_scope(user_id="*", role=None, resource="source_preview.source_foundation", action="read")
    scope_repo.grant_scope(user_id="*", role=None, resource="pnl", action="read")

    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import duckdb,sys; "
                "conn=duckdb.connect(sys.argv[1], read_only=False); "
                "print('READY', flush=True); "
                "sys.stdin.readline(); conn.close()"
            ),
            str(duckdb_path),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "READY"
        client = TestClient(
            load_module("backend.app.main", "backend/app/main.py").app,
            headers={"X-User-Id": "lock-probe", "X-User-Role": "viewer"},
            raise_server_exceptions=False,
        )

        preview_response = client.get("/ui/preview/source-foundation")
        pnl_response = client.get("/api/pnl/dates")

        assert preview_response.status_code == 503
        assert preview_response.json() == {
            "detail": "Source preview storage is temporarily unavailable."
        }
        assert pnl_response.status_code == 503

        assert holder.stdin is not None
        holder.stdin.write("\n")
        holder.stdin.flush()
        holder.wait(timeout=10)

        recovered_response = client.get("/ui/preview/source-foundation")
        assert recovered_response.status_code == 200
        assert recovered_response.json()["result_meta"]["quality_flag"] == "ok"
    finally:
        if holder.poll() is None:
            holder.terminate()
            try:
                holder.wait(timeout=5)
            except subprocess.TimeoutExpired:
                holder.kill()
                holder.wait(timeout=5)
        get_settings.cache_clear()
