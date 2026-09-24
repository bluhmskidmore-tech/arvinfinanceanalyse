from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.mcp.moss_project_mcp import ProjectMcpServer, build_provider


REPO_ROOT = Path(__file__).resolve().parents[1]
MCP_SCRIPT = REPO_ROOT / "scripts" / "mcp" / "moss_project_mcp.py"

pytestmark = pytest.mark.mcp_fast


@pytest.fixture
def isolated_mcp_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, str]:
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir()
    duckdb_path = tmp_path / "missing.duckdb"
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    return {
        "MOSS_GOVERNANCE_PATH": str(governance_dir),
        "MOSS_DUCKDB_PATH": str(duckdb_path),
    }


@pytest.mark.parametrize(
    ("mode", "server_name"),
    [
        ("metric-contracts", "moss-metric-contracts"),
        ("lineage-evidence", "moss-lineage-evidence"),
        ("data-catalog", "moss-data-catalog"),
        ("data-quality", "moss-data-quality"),
    ],
)
def test_project_mcp_fast_contract_initializes_without_local_runtime_data(
    isolated_mcp_runtime: dict[str, str],
    mode: str,
    server_name: str,
) -> None:
    server = ProjectMcpServer(build_provider(mode))

    response = server._handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    )

    assert response["result"]["serverInfo"]["name"] == server_name
    assert response["result"]["capabilities"] == {"resources": {}, "tools": {}}


@pytest.mark.mcp_stdio
@pytest.mark.parametrize(
    ("mode", "server_name"),
    [
        ("metric-contracts", "moss-metric-contracts"),
        ("lineage-evidence", "moss-lineage-evidence"),
        ("data-catalog", "moss-data-catalog"),
        ("data-quality", "moss-data-quality"),
    ],
)
def test_project_mcp_fast_stdio_handshake_uses_isolated_runtime(
    isolated_mcp_runtime: dict[str, str],
    mode: str,
    server_name: str,
) -> None:
    env = os.environ.copy()
    env.update(isolated_mcp_runtime)
    request = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    ).encode("utf-8")
    frame = f"Content-Length: {len(request)}\r\n\r\n".encode("ascii") + request

    completed = subprocess.run(
        [sys.executable, str(MCP_SCRIPT), mode],
        cwd=REPO_ROOT,
        env=env,
        input=frame,
        capture_output=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    _, separator, raw_body = completed.stdout.partition(b"\r\n\r\n")
    assert separator
    response = json.loads(raw_body.decode("utf-8"))
    assert response["result"]["serverInfo"]["name"] == server_name
