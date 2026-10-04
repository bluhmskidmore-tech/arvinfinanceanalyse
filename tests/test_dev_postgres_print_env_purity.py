import json
import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import duckdb
import pytest

from tests.helpers import ROOT, load_module


SCRIPT = ROOT / "scripts" / "dev_postgres_cluster.py"


@pytest.fixture(autouse=True)
def forbid_http(monkeypatch):
    def blocked_connection(*_args, **_kwargs):
        raise AssertionError(
            "HTTP/network access is forbidden in print-env purity tests"
        )

    monkeypatch.setattr(socket, "create_connection", blocked_connection)


def _owned_repo(tmp_path: Path) -> Path:
    resolved = tmp_path.resolve()
    repo_root = ROOT.resolve()
    formal_data_root = (ROOT / "data").resolve()
    assert resolved != repo_root
    assert resolved != formal_data_root
    assert formal_data_root not in resolved.parents
    owned_repo = resolved / "repo"
    owned_repo.mkdir()
    return owned_repo


def _write_duckdb(path: Path, report_date: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(path), read_only=False) as conn:
        conn.execute(
            "create table fact_formal_bond_analytics_daily (report_date varchar)"
        )
        conn.execute(
            "insert into fact_formal_bond_analytics_daily values (?)",
            [report_date],
        )


def _run_print_env(
    repo_root: Path,
    guard_root: Path,
    result_name: str,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    guard_result = guard_root / f"{result_name}.json"
    child_code = r"""
import json
import runpy
import socket
import sys
from pathlib import Path

import _pytest_duckdb_guard as guard

owned_root = Path(sys.argv[1]).resolve()
receipt_root = Path(sys.argv[2]).resolve()
result_path = Path(sys.argv[3]).resolve()
script_path = Path(sys.argv[4]).resolve()
repo_root = Path(sys.argv[5]).resolve()
pg_bin_dir = Path(sys.argv[6]).resolve()
guard.register_pytest_duckdb_temp_root(owned_root)
guard.register_pytest_duckdb_temp_root(receipt_root)
guard.set_pytest_duckdb_guard_phase("dev-postgres-print-env-child")

http_calls = []

def forbid_http(*args, **kwargs):
    http_calls.append({"args": [str(value) for value in args], "kwargs": kwargs})
    raise AssertionError("HTTP is forbidden in the print-env child")

socket.create_connection = forbid_http
import requests
requests.Session.request = forbid_http

attempts_before = guard.get_pytest_duckdb_guard_attempts()
exit_code = 0
try:
    sys.argv = [
        str(script_path),
        "print-env",
        "--repo-root",
        str(repo_root),
        "--pg-bin-dir",
        str(pg_bin_dir),
    ]
    try:
        runpy.run_path(str(script_path), run_name="__main__")
    except SystemExit as exc:
        exit_code = int(exc.code or 0)
finally:
    attempts_after = guard.get_pytest_duckdb_guard_attempts()
    receipt_path = guard.finalize_pytest_duckdb_guard()
    result_path.write_text(
        json.dumps(
            {
                "attempts_before": attempts_before,
                "attempts_after": attempts_after,
                "http_calls": http_calls,
                "receipt_path": str(receipt_path),
            },
            sort_keys=True,
            default=str,
        ),
        encoding="utf-8",
    )
if exit_code:
    raise SystemExit(exit_code)
"""
    env = os.environ.copy()
    env.update(
        {
            "HTTP_PROXY": "http://127.0.0.1:1",
            "HTTPS_PROXY": "http://127.0.0.1:1",
            "NO_PROXY": "",
        }
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            child_code,
            str(repo_root.parent),
            str(guard_root),
            str(guard_result),
            str(SCRIPT),
            str(repo_root),
            str(repo_root / "unused-pg-bin"),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    return result, json.loads(guard_result.read_text(encoding="utf-8"))


def _tree_metadata(root: Path) -> tuple[tuple[str, str, int, int], ...]:
    entries = []
    for path in sorted(root.rglob("*")):
        info = path.stat()
        kind = "dir" if path.is_dir() else "file"
        entries.append(
            (path.relative_to(root).as_posix(), kind, info.st_size, info.st_mtime_ns)
        )
    return tuple(entries)


@contextmanager
def _native_rw_holder(database_path: Path, ready_path: Path, guard_root: Path):
    guard_result = guard_root / "holder.json"
    holder_code = r"""
import json
import socket
import sys
from pathlib import Path

import _pytest_duckdb_guard as guard

owned_root = Path(sys.argv[1]).resolve()
receipt_root = Path(sys.argv[2]).resolve()
database_path = Path(sys.argv[3]).resolve()
ready_path = Path(sys.argv[4]).resolve()
result_path = Path(sys.argv[5]).resolve()
guard.register_pytest_duckdb_temp_root(owned_root)
guard.register_pytest_duckdb_temp_root(receipt_root)
guard.set_pytest_duckdb_guard_phase("dev-postgres-print-env-rw-holder")

http_calls = []

def forbid_http(*args, **kwargs):
    http_calls.append({"args": [str(value) for value in args], "kwargs": kwargs})
    raise AssertionError("HTTP is forbidden in the print-env RW holder")

socket.create_connection = forbid_http
import requests
requests.Session.request = forbid_http

attempts_before = guard.get_pytest_duckdb_guard_attempts()
conn = None
try:
    import duckdb

    conn = duckdb.connect(str(database_path), read_only=False)
    conn.execute("create table if not exists print_env_lock_holder (value integer)")
    conn.execute("begin transaction")
    conn.execute("insert into print_env_lock_holder values (1)")
    ready_path.write_text("native-rw-open", encoding="utf-8")
    sys.stdin.buffer.read(1)
finally:
    if conn is not None:
        conn.rollback()
        conn.close()
    attempts_after = guard.get_pytest_duckdb_guard_attempts()
    receipt_path = guard.finalize_pytest_duckdb_guard()
    result_path.write_text(
        json.dumps(
            {
                "attempts_before": attempts_before,
                "attempts_after": attempts_after,
                "http_calls": http_calls,
                "receipt_path": str(receipt_path),
            },
            sort_keys=True,
            default=str,
        ),
        encoding="utf-8",
    )
"""
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            holder_code,
            str(database_path.parents[2]),
            str(guard_root),
            str(database_path),
            str(ready_path),
            str(guard_result),
        ],
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 10
        while not ready_path.exists():
            if process.poll() is not None:
                _, stderr = process.communicate(timeout=1)
                raise AssertionError(
                    f"native RW holder exited early: {stderr.decode(errors='replace')}"
                )
            if time.monotonic() >= deadline:
                raise AssertionError("native RW holder did not reach its ready barrier")
            time.sleep(0.02)
        assert ready_path.read_text(encoding="utf-8") == "native-rw-open"
        yield process, guard_result
    finally:
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.write(b"x")
            process.stdin.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()


def test_real_print_env_is_identical_and_read_only_while_repo_duckdb_has_native_writer(
    tmp_path,
):
    repo_root = _owned_repo(tmp_path)
    guard_root = tmp_path / "child-guard"
    guard_root.mkdir()
    repo_duckdb = repo_root / "data" / "moss.duckdb"
    _write_duckdb(repo_duckdb, "2026-02-28")

    idle_before = _tree_metadata(repo_root)
    idle_result, idle_guard = _run_print_env(repo_root, guard_root, "idle")
    idle_after = _tree_metadata(repo_root)

    ready_path = repo_root / "holder.ready"
    with _native_rw_holder(repo_duckdb, ready_path, guard_root) as (
        _,
        holder_guard_path,
    ):
        held_before = _tree_metadata(repo_root)
        held_result, held_guard = _run_print_env(repo_root, guard_root, "held")
        held_after = _tree_metadata(repo_root)
    holder_guard = json.loads(holder_guard_path.read_text(encoding="utf-8"))

    assert idle_result.returncode == 0, idle_result.stderr
    assert held_result.returncode == 0, held_result.stderr
    idle_env = json.loads(idle_result.stdout)
    held_env = json.loads(held_result.stdout)
    assert held_env == idle_env
    assert idle_env["MOSS_DUCKDB_PATH"] == str(repo_duckdb)
    assert idle_env["MOSS_GOVERNANCE_PATH"] == str(repo_root / "data" / "governance")
    assert idle_env["MOSS_LOCAL_ARCHIVE_PATH"] == str(repo_root / "data" / "archive")
    assert idle_env["MOSS_DATA_INPUT_ROOT"] == str(repo_root / "data_input")
    assert idle_guard["attempts_before"] == []
    assert idle_guard["attempts_after"] == []
    assert idle_guard["http_calls"] == []
    assert held_guard["attempts_before"] == []
    assert held_guard["attempts_after"] == []
    assert held_guard["http_calls"] == []
    assert holder_guard["attempts_before"] == []
    assert len(holder_guard["attempts_after"]) == 1
    holder_attempt = holder_guard["attempts_after"][0]
    assert holder_attempt["canonical_path"] == str(repo_duckdb.resolve())
    assert holder_attempt["decision"] == "allow"
    assert holder_guard["http_calls"] == []
    assert Path(idle_guard["receipt_path"]).parent == guard_root
    assert Path(held_guard["receipt_path"]).parent == guard_root
    assert Path(holder_guard["receipt_path"]).parent == guard_root
    assert idle_after == idle_before
    assert held_after == held_before


@pytest.mark.parametrize("repo_contents", [b"", b"not-a-duckdb"])
def test_print_env_selects_repo_for_any_regular_database_file(tmp_path, repo_contents):
    repo_root = _owned_repo(tmp_path)
    repo_duckdb = repo_root / "data" / "moss.duckdb"
    repo_duckdb.parent.mkdir(parents=True)
    repo_duckdb.write_bytes(repo_contents)
    module = load_module(
        "scripts.dev_postgres_cluster",
        "scripts/dev_postgres_cluster.py",
    )
    config = module.build_cluster_config(repo_root, repo_root / "unused-pg-bin")
    _write_duckdb(config.runtime_duckdb_path, "2026-01-31")

    env = module.command_print_env(config)

    assert env["MOSS_DUCKDB_PATH"] == str(repo_duckdb)


@pytest.mark.parametrize("runtime_exists", [False, True])
def test_print_env_uses_runtime_root_only_when_repo_database_is_genuinely_absent(
    tmp_path,
    runtime_exists,
):
    repo_root = _owned_repo(tmp_path)
    module = load_module(
        "scripts.dev_postgres_cluster",
        "scripts/dev_postgres_cluster.py",
    )
    config = module.build_cluster_config(repo_root, repo_root / "unused-pg-bin")
    if runtime_exists:
        config.runtime_duckdb_path.parent.mkdir(parents=True)
        config.runtime_duckdb_path.write_bytes(b"runtime-placeholder")

    env = module.command_print_env(config)

    assert env["MOSS_DUCKDB_PATH"] == str(config.runtime_root / "moss.duckdb")
    assert env["MOSS_GOVERNANCE_PATH"] == str(config.runtime_root / "governance")
    assert env["MOSS_LOCAL_ARCHIVE_PATH"] == str(config.runtime_root / "archive")
    assert env["MOSS_DATA_INPUT_ROOT"] == str(config.runtime_data_input_path)


@pytest.mark.parametrize("invalid_candidate", ["repo", "runtime"])
def test_print_env_rejects_database_path_that_is_a_directory(
    tmp_path, invalid_candidate
):
    repo_root = _owned_repo(tmp_path)
    module = load_module(
        "scripts.dev_postgres_cluster",
        "scripts/dev_postgres_cluster.py",
    )
    config = module.build_cluster_config(repo_root, repo_root / "unused-pg-bin")
    candidate = (
        repo_root / "data" / "moss.duckdb"
        if invalid_candidate == "repo"
        else config.runtime_duckdb_path
    )
    candidate.mkdir(parents=True)

    with pytest.raises(RuntimeError, match="regular file"):
        module.command_print_env(config)


def test_print_env_accepts_valid_database_symlink_alias(tmp_path):
    repo_root = _owned_repo(tmp_path)
    module = load_module(
        "scripts.dev_postgres_cluster",
        "scripts/dev_postgres_cluster.py",
    )
    config = module.build_cluster_config(repo_root, repo_root / "unused-pg-bin")
    repo_duckdb = repo_root / "data" / "moss.duckdb"
    repo_duckdb.parent.mkdir(parents=True)
    alias_target = repo_root / "alias-target.duckdb"
    alias_target.write_bytes(b"alias-target")
    try:
        repo_duckdb.symlink_to(alias_target)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    env = module.command_print_env(config)

    assert env["MOSS_DUCKDB_PATH"] == str(repo_duckdb)


@pytest.mark.parametrize("invalid_candidate", ["repo", "runtime"])
def test_print_env_rejects_broken_database_symlink(tmp_path, invalid_candidate):
    repo_root = _owned_repo(tmp_path)
    module = load_module(
        "scripts.dev_postgres_cluster",
        "scripts/dev_postgres_cluster.py",
    )
    config = module.build_cluster_config(repo_root, repo_root / "unused-pg-bin")
    candidate = (
        repo_root / "data" / "moss.duckdb"
        if invalid_candidate == "repo"
        else config.runtime_duckdb_path
    )
    candidate.parent.mkdir(parents=True)
    try:
        candidate.symlink_to(repo_root / f"missing-{invalid_candidate}.duckdb")
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    with pytest.raises(RuntimeError, match="broken symlink"):
        module.command_print_env(config)


@pytest.mark.parametrize("ancestor_kind", ["file", "broken-symlink"])
def test_print_env_rejects_invalid_database_path_ancestor(tmp_path, ancestor_kind):
    repo_root = _owned_repo(tmp_path)
    module = load_module(
        "scripts.dev_postgres_cluster",
        "scripts/dev_postgres_cluster.py",
    )
    config = module.build_cluster_config(repo_root, repo_root / "unused-pg-bin")
    data_root = repo_root / "data"
    if ancestor_kind == "file":
        data_root.write_bytes(b"not-a-directory")
    else:
        try:
            data_root.symlink_to(repo_root / "missing-data", target_is_directory=True)
        except OSError as exc:
            pytest.skip(f"symlink creation unavailable: {exc}")

    with pytest.raises(RuntimeError, match="database path|broken symlink"):
        module.command_print_env(config)


@pytest.mark.parametrize("invalid_candidate", ["repo", "runtime"])
def test_print_env_turns_metadata_error_into_explicit_failure(
    tmp_path,
    monkeypatch,
    invalid_candidate,
):
    repo_root = _owned_repo(tmp_path)
    module = load_module(
        "scripts.dev_postgres_cluster",
        "scripts/dev_postgres_cluster.py",
    )
    config = module.build_cluster_config(repo_root, repo_root / "unused-pg-bin")
    candidate = (
        repo_root / "data" / "moss.duckdb"
        if invalid_candidate == "repo"
        else config.runtime_duckdb_path
    )
    original_lstat = Path.lstat

    def denied_lstat(path):
        if path == candidate:
            raise PermissionError("metadata denied")
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", denied_lstat)

    with pytest.raises(RuntimeError, match="metadata"):
        module.command_print_env(config)


def test_print_env_cli_failure_has_no_partial_stdout(tmp_path):
    repo_root = _owned_repo(tmp_path)
    guard_root = tmp_path / "child-guard"
    guard_root.mkdir()
    (repo_root / "data" / "moss.duckdb").mkdir(parents=True)

    result, guard_result = _run_print_env(repo_root, guard_root, "invalid-path")

    assert result.returncode == 1
    assert result.stdout == ""
    assert json.loads(result.stderr)["error"]
    assert guard_result["attempts_before"] == []
    assert guard_result["attempts_after"] == []
    assert guard_result["http_calls"] == []
