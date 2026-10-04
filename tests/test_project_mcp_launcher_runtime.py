from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.mcp_full

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def isolated_default_mcp_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Path]:
    governance_dir = tmp_path / "default-governance"
    governance_dir.mkdir()
    duckdb_path = tmp_path / "missing.duckdb"
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    return {"governance_dir": governance_dir, "duckdb_path": duckdb_path}



def test_full_mcp_contracts_default_to_isolated_runtime_paths(
    isolated_default_mcp_runtime: dict[str, Path],
) -> None:
    assert Path(os.environ["MOSS_GOVERNANCE_PATH"]) == isolated_default_mcp_runtime[
        "governance_dir"
    ]
    assert Path(os.environ["MOSS_DUCKDB_PATH"]) == isolated_default_mcp_runtime[
        "duckdb_path"
    ]
    assert isolated_default_mcp_runtime["governance_dir"].is_dir()
    assert not isolated_default_mcp_runtime["duckdb_path"].exists()


@pytest.fixture
def isolated_mcp_launcher_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "launcher-workspace"
    launchers = repo / "scripts" / "mcp"
    launchers.mkdir(parents=True)
    for name in (
        "moss_mcp_launcher.py",
        "moss_lineage.cmd",
        "moss_catalog.cmd",
        "moss_data_quality.cmd",
    ):
        (launchers / name).write_bytes((REPO_ROOT / "scripts" / "mcp" / name).read_bytes())

    settings_dir = repo / "backend" / "app" / "governance"
    settings_dir.mkdir(parents=True)
    for package in (repo / "backend", repo / "backend" / "app", settings_dir):
        (package / "__init__.py").write_text("", encoding="utf-8")
    (settings_dir / "settings.py").write_bytes(
        (REPO_ROOT / "backend" / "app" / "governance" / "settings.py").read_bytes()
    )
    (launchers / "moss_project_mcp.py").write_text(
        "import json, os, sys\n"
        "def main():\n"
        "    print(json.dumps({\n"
        "        'cwd': os.getcwd(),\n"
        "        'mode': sys.argv[1],\n"
        "        'governance_path': os.environ.get('MOSS_GOVERNANCE_PATH'),\n"
        "        'duckdb_path': os.environ.get('MOSS_DUCKDB_PATH'),\n"
        "    }))\n"
        "    return 0\n",
        encoding="utf-8",
    )
    return repo


def _probe_isolated_mcp_launcher(
    repo: Path,
    launcher_name: str,
    mode: str,
    entrypoint: str,
    *,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    process_env = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("MOSS_") and key.upper() != "RAW_FILES_DIR"
    }
    process_env.update(env or {})
    process_env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + process_env.get("PATH", "")
    launchers = repo / "scripts" / "mcp"
    if entrypoint == "cmd":
        if os.name != "nt":
            pytest.skip("Windows cmd launcher")
        command = ["cmd.exe", "/d", "/s", "/c", str(launchers / launcher_name)]
    else:
        command = [sys.executable, str(launchers / "moss_mcp_launcher.py"), mode]
    completed = subprocess.run(
        command,
        cwd=repo.parent,
        env=process_env,
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert Path(payload["cwd"]) == repo
    assert payload["mode"] == mode
    return payload


@pytest.mark.parametrize("entrypoint", ["cmd", "python"])
@pytest.mark.parametrize(
    ("launcher_name", "mode"),
    [
        ("moss_lineage.cmd", "lineage-evidence"),
        ("moss_catalog.cmd", "data-catalog"),
        ("moss_data_quality.cmd", "data-quality"),
    ],
)
def test_moss_launcher_preserves_explicit_runtime_paths(
    isolated_mcp_launcher_repo: Path,
    launcher_name: str,
    mode: str,
    entrypoint: str,
) -> None:
    repo = isolated_mcp_launcher_repo
    (repo / ".env").write_text(
        "MOSS_GOVERNANCE_PATH=dotenv/governance\n"
        "MOSS_DUCKDB_PATH=dotenv/moss.duckdb\n",
        encoding="utf-8",
    )
    expected = {
        "MOSS_GOVERNANCE_PATH": str(repo.parent / "external-governance"),
        "MOSS_DUCKDB_PATH": str(repo.parent / "external.duckdb"),
    }
    payload = _probe_isolated_mcp_launcher(
        repo, launcher_name, mode, entrypoint, env=expected
    )
    assert payload["governance_path"] == expected["MOSS_GOVERNANCE_PATH"]
    assert payload["duckdb_path"] == expected["MOSS_DUCKDB_PATH"]


@pytest.mark.parametrize("entrypoint", ["cmd", "python"])
@pytest.mark.parametrize("root_env_override", [False, True])
@pytest.mark.parametrize(
    ("launcher_name", "mode"),
    [
        ("moss_lineage.cmd", "lineage-evidence"),
        ("moss_catalog.cmd", "data-catalog"),
        ("moss_data_quality.cmd", "data-quality"),
    ],
)
def test_moss_launcher_uses_dotenv_runtime_paths(
    isolated_mcp_launcher_repo: Path,
    launcher_name: str,
    mode: str,
    entrypoint: str,
    root_env_override: bool,
) -> None:
    repo = isolated_mcp_launcher_repo
    config = repo / "config"
    config.mkdir()
    (config / ".env").write_text(
        "MOSS_GOVERNANCE_PATH=configured/governance\n"
        "MOSS_DUCKDB_PATH=configured/moss.duckdb\n",
        encoding="utf-8",
    )
    selected_root = repo / "configured"
    if root_env_override:
        selected_root = repo.parent / "external-storage"
        (repo / ".env").write_text(
            f"MOSS_GOVERNANCE_PATH={selected_root.as_posix()}/governance\n"
            f"MOSS_DUCKDB_PATH={selected_root.as_posix()}/moss.duckdb\n",
            encoding="utf-8",
        )
    payload = _probe_isolated_mcp_launcher(repo, launcher_name, mode, entrypoint)
    assert Path(payload["governance_path"]) == selected_root / "governance"
    assert Path(payload["duckdb_path"]) == selected_root / "moss.duckdb"


@pytest.mark.parametrize("entrypoint", ["cmd", "python"])
@pytest.mark.parametrize(
    ("launcher_name", "mode"),
    [
        ("moss_lineage.cmd", "lineage-evidence"),
        ("moss_catalog.cmd", "data-catalog"),
        ("moss_data_quality.cmd", "data-quality"),
    ],
)
def test_moss_launcher_defaults_runtime_paths(
    isolated_mcp_launcher_repo: Path,
    launcher_name: str,
    mode: str,
    entrypoint: str,
) -> None:
    repo = isolated_mcp_launcher_repo
    payload = _probe_isolated_mcp_launcher(repo, launcher_name, mode, entrypoint)
    assert Path(payload["governance_path"]) == repo / "data" / "governance"
    assert Path(payload["duckdb_path"]) == repo / "data" / "moss.duckdb"


