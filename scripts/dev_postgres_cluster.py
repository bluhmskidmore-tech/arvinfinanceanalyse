from __future__ import annotations

import argparse
import duckdb
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 55432
DEFAULT_USER = "moss"
DEFAULT_PASSWORD = "moss"
DEFAULT_DATABASE = "moss"
DEFAULT_REDIS_DSN = "redis://127.0.0.1:6379/11"
SMOKE_FILES = (
    "ZQTZSHOW-20251231.xls",
    "TYWLSHOW-20251231.xls",
)
RUNTIME_DUCKDB_SEED_TABLES = (
    "fact_formal_bond_analytics_daily",
    "zqtz_bond_daily_snapshot",
    "fact_formal_zqtz_balance_daily",
    "fact_formal_tyw_balance_daily",
)


@dataclass(frozen=True)
class DevPostgresClusterConfig:
    repo_root: Path
    bin_dir: Path
    cluster_root: Path
    data_dir: Path
    log_file: Path
    runtime_root: Path
    runtime_duckdb_path: Path
    runtime_governance_path: Path
    runtime_archive_path: Path
    runtime_data_input_path: Path
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    user: str = DEFAULT_USER
    password: str = DEFAULT_PASSWORD
    database: str = DEFAULT_DATABASE

    @property
    def admin_database(self) -> str:
        return "postgres"

    @property
    def postgres_dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


def build_cluster_config(repo_root: Path, pg_bin_dir: Path | None = None) -> DevPostgresClusterConfig:
    cluster_root = repo_root / "tmp-governance" / "pgdev"
    runtime_root = repo_root / "tmp-governance" / "runtime-clean"
    return DevPostgresClusterConfig(
        repo_root=repo_root,
        bin_dir=pg_bin_dir or resolve_pg_bin_dir(),
        cluster_root=cluster_root,
        data_dir=cluster_root / "data",
        log_file=cluster_root / "postgres.log",
        runtime_root=runtime_root,
        runtime_duckdb_path=runtime_root / "moss.duckdb",
        runtime_governance_path=runtime_root / "governance",
        runtime_archive_path=runtime_root / "archive",
        runtime_data_input_path=runtime_root / "data_input",
    )


def build_env_mapping(config: DevPostgresClusterConfig) -> dict[str, str]:
    storage_root = _resolve_storage_root_for_env(config)
    return {
        "MOSS_ENVIRONMENT": "development",
        "MOSS_POSTGRES_DSN": config.postgres_dsn,
        "MOSS_GOVERNANCE_SQL_DSN": config.postgres_dsn,
        "MOSS_REDIS_DSN": DEFAULT_REDIS_DSN,
        "MOSS_DUCKDB_PATH": str(storage_root / "moss.duckdb"),
        "MOSS_GOVERNANCE_PATH": str(storage_root / "governance"),
        "MOSS_LOCAL_ARCHIVE_PATH": str(storage_root / "archive"),
        "MOSS_DATA_INPUT_ROOT": str(config.repo_root / "data_input" if storage_root == config.repo_root / "data" else config.runtime_data_input_path),
        "MOSS_SOURCE_PREVIEW_GOVERNANCE_BACKEND": "jsonl",
        "MOSS_OBJECT_STORE_MODE": "local",
        "MOSS_MINIO_ENDPOINT": "localhost:9000",
        "MOSS_MINIO_ACCESS_KEY": "minioadmin",
        "MOSS_MINIO_SECRET_KEY": "minioadmin",
        "MOSS_MINIO_BUCKET": "moss-artifacts",
    }


def resolve_pg_bin_dir() -> Path:
    explicit = None
    if "MOSS_PG_BIN_DIR" in os.environ:
        explicit = Path(os.environ["MOSS_PG_BIN_DIR"]).expanduser()
    candidates = [
        explicit,
        Path(r"C:\Program Files\PostgreSQL\17\bin"),
        Path(r"C:\Program Files\PostgreSQL\16\bin"),
        Path(r"C:\Program Files\PostgreSQL\15\bin"),
    ]
    for candidate in candidates:
        if candidate and (candidate / "pg_ctl.exe").exists():
            return candidate
    raise FileNotFoundError("Unable to locate PostgreSQL bin directory. Set MOSS_PG_BIN_DIR.")


def _resolve_python_executable() -> str:
    return shutil.which("python") or sys.executable


def command_up(config: DevPostgresClusterConfig) -> dict[str, object]:
    config.cluster_root.mkdir(parents=True, exist_ok=True)
    if not config.data_dir.exists():
        _initdb_with_locale_fallback(config)

    if not _is_port_open(config.host, config.port):
        _run_checked(
            [
                str(config.bin_dir / "pg_ctl.exe"),
                "-D",
                str(config.data_dir),
                "-l",
                str(config.log_file),
                "-o",
                f" -h {config.host} -p {config.port} ",
                "-w",
                "start",
            ]
        )
    _wait_for_postgres_ready(config)

    _ensure_role_and_database(config)
    _wait_for_postgres_ready(config, database=config.database)
    _apply_alembic_migrations_and_grants(config)
    _prepare_runtime_clean_paths(config)

    status = command_status(config)
    status["action"] = "up"
    return status


def command_down(config: DevPostgresClusterConfig) -> dict[str, object]:
    if config.data_dir.exists() and _is_port_open(config.host, config.port):
        _run_checked(
            [
                str(config.bin_dir / "pg_ctl.exe"),
                "-D",
                str(config.data_dir),
                "-m",
                "fast",
                "-w",
                "stop",
            ]
        )
    status = command_status(config)
    status["action"] = "down"
    return status


def command_status(config: DevPostgresClusterConfig) -> dict[str, object]:
    return {
        "repo_root": str(config.repo_root),
        "cluster_root": str(config.cluster_root),
        "data_dir_exists": config.data_dir.exists(),
        "running": _is_port_open(config.host, config.port),
        "postgres_dsn": config.postgres_dsn,
        "runtime_root": str(config.runtime_root),
        "runtime_data_input_path": str(config.runtime_data_input_path),
    }


def command_print_env(config: DevPostgresClusterConfig) -> dict[str, str]:
    try:
        _prepare_runtime_clean_paths(config)
    except PermissionError:
        pass
    return build_env_mapping(config)


def _ensure_role_and_database(config: DevPostgresClusterConfig) -> None:
    role_exists = _run_checked_retry(
        [
            str(config.bin_dir / "psql.exe"),
            "-h",
            config.host,
            "-p",
            str(config.port),
            "-U",
            "postgres",
            "-d",
            config.admin_database,
            "-tAc",
            f"SELECT 1 FROM pg_roles WHERE rolname = '{config.user}'",
        ],
        capture_output=True,
    ).strip()
    if role_exists != "1":
        _run_checked_retry(
            [
                str(config.bin_dir / "psql.exe"),
                "-h",
                config.host,
                "-p",
                str(config.port),
                "-U",
                "postgres",
                "-d",
                config.admin_database,
                "-c",
                f"CREATE ROLE {config.user} LOGIN PASSWORD '{config.password}';",
            ]
        )

    db_exists = _run_checked_retry(
        [
            str(config.bin_dir / "psql.exe"),
            "-h",
            config.host,
            "-p",
            str(config.port),
            "-U",
            "postgres",
            "-d",
            config.admin_database,
            "-tAc",
            f"SELECT 1 FROM pg_database WHERE datname = '{config.database}'",
        ],
        capture_output=True,
    ).strip()
    if db_exists != "1":
        _run_checked_retry(
            [
                str(config.bin_dir / "createdb.exe"),
                "-h",
                config.host,
                "-p",
                str(config.port),
                "-U",
                "postgres",
                "-O",
                config.user,
                config.database,
            ]
        )


def _reset_moss_public_schema(config: DevPostgresClusterConfig) -> None:
    """Drop and recreate public schema on the moss DB (dev cluster only)."""
    sql = (
        "DROP SCHEMA IF EXISTS public CASCADE; "
        "CREATE SCHEMA public; "
        "ALTER SCHEMA public OWNER TO moss; "
        "GRANT ALL ON SCHEMA public TO moss; "
        "GRANT ALL ON SCHEMA public TO public;"
    )
    _run_checked_retry(
        [
            str(config.bin_dir / "psql.exe"),
            "-h",
            config.host,
            "-p",
            str(config.port),
            "-U",
            "postgres",
            "-d",
            config.database,
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            sql,
        ]
    )


def command_reset_schema(config: DevPostgresClusterConfig) -> dict[str, object]:
    """Rebuild moss.public from scratch and re-apply Alembic head + grants.

    Refuses to run unless the target is the default local dev cluster endpoint
    (127.0.0.1:55432) to avoid accidental use against shared Postgres.
    """
    if config.host != DEFAULT_HOST or int(config.port) != DEFAULT_PORT:
        raise RuntimeError(
            "reset-schema refused: only allowed for "
            f"{DEFAULT_HOST}:{DEFAULT_PORT} (got {config.host}:{config.port})"
        )
    if not _is_port_open(config.host, config.port):
        raise RuntimeError("cluster is not running on the dev port; run `up` first")
    _reset_moss_public_schema(config)
    _apply_alembic_migrations_and_grants(config)
    status = command_status(config)
    status["action"] = "reset-schema"
    return status


def _apply_alembic_migrations_and_grants(config: DevPostgresClusterConfig) -> None:
    backend_dir = config.repo_root / "backend"
    env = os.environ.copy()
    env["MOSS_POSTGRES_DSN"] = config.postgres_dsn
    env.pop("MOSS_SKIP_POSTGRES_MIGRATIONS", None)
    env.pop("MOSS_SKIP_STARTUP_STORAGE_MIGRATIONS", None)
    alembic_args = [
        _resolve_python_executable(),
        "-m",
        "alembic",
        "-c",
        str(backend_dir / "alembic.ini"),
        "upgrade",
        "head",
    ]
    for attempt in range(1, 4):
        result = subprocess.run(
            alembic_args,
            cwd=str(backend_dir),
            check=False,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            break

        combined_output = "\n".join(part for part in (result.stdout, result.stderr) if part)
        normalized_output = combined_output.lower()
        is_transient_connect_timeout = "connection timeout expired" in normalized_output
        if is_transient_connect_timeout and attempt < 3:
            _wait_for_postgres_ready(config, database=config.database, attempts=5, retry_delay_seconds=1.0)
            continue

        if result.stdout:
            print(result.stdout, end="", file=sys.stderr)
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        raise subprocess.CalledProcessError(
            result.returncode,
            alembic_args,
            output=result.stdout,
            stderr=result.stderr,
        )

    _run_checked(
        [
            str(config.bin_dir / "psql.exe"),
            "-h",
            config.host,
            "-p",
            str(config.port),
            "-U",
            "postgres",
            "-d",
            config.database,
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            (
                "GRANT ALL PRIVILEGES ON TABLE source_version_registry TO moss; "
                "GRANT ALL PRIVILEGES ON TABLE rule_version_registry TO moss; "
                "GRANT ALL PRIVILEGES ON TABLE cache_manifest TO moss; "
                "GRANT ALL PRIVILEGES ON TABLE cache_build_run TO moss; "
                "GRANT ALL PRIVILEGES ON TABLE job_run_state TO moss; "
                "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO moss; "
                "ALTER TABLE source_version_registry OWNER TO moss; "
                "ALTER TABLE rule_version_registry OWNER TO moss; "
                "ALTER TABLE cache_manifest OWNER TO moss; "
                "ALTER TABLE cache_build_run OWNER TO moss; "
                "ALTER TABLE job_run_state OWNER TO moss;"
            ),
        ]
    )


def _prepare_runtime_clean_paths(config: DevPostgresClusterConfig) -> None:
    config.runtime_governance_path.mkdir(parents=True, exist_ok=True)
    config.runtime_archive_path.mkdir(parents=True, exist_ok=True)
    config.runtime_data_input_path.mkdir(parents=True, exist_ok=True)
    for file_name in SMOKE_FILES:
        source = config.repo_root / "data_input" / file_name
        target = config.runtime_data_input_path / file_name
        if source.exists() and not target.exists():
            shutil.copy2(source, target)
    _seed_runtime_duckdb_from_repo_if_needed(config)


def _seed_runtime_duckdb_from_repo_if_needed(config: DevPostgresClusterConfig) -> None:
    runtime_duckdb = config.runtime_duckdb_path
    if _duckdb_has_seed_data(runtime_duckdb):
        return

    repo_duckdb = config.repo_root / "data" / "moss.duckdb"
    if not _duckdb_has_seed_data(repo_duckdb):
        return

    runtime_duckdb.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(repo_duckdb, runtime_duckdb)


def _resolve_storage_root_for_env(config: DevPostgresClusterConfig) -> Path:
    if _duckdb_has_seed_data(config.runtime_duckdb_path):
        return config.runtime_root

    repo_data_root = config.repo_root / "data"
    if _duckdb_has_seed_data(repo_data_root / "moss.duckdb"):
        return repo_data_root

    return config.runtime_root


def _duckdb_has_seed_data(path: Path) -> bool:
    if not path.exists() or path.stat().st_size <= 0:
        return False
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        return False

    try:
        for table_name in RUNTIME_DUCKDB_SEED_TABLES:
            row = conn.execute(
                """
                select 1
                from information_schema.tables
                where table_name = ?
                limit 1
                """,
                [table_name],
            ).fetchone()
            if row is None:
                continue
            populated = conn.execute(f"select 1 from {table_name} limit 1").fetchone()
            if populated is not None:
                return True
        return False
    finally:
        conn.close()


def _is_port_open(host: str, port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _probe_postgres_ready(config: DevPostgresClusterConfig, *, database: str | None = None) -> bool:
    try:
        _run_checked_retry(
            [
                str(config.bin_dir / "psql.exe"),
                "-h",
                config.host,
                "-p",
                str(config.port),
                "-U",
                "postgres",
                "-d",
                database or config.admin_database,
                "-tAc",
                "SELECT 1",
            ],
            capture_output=True,
            attempts=1,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def _wait_for_postgres_ready(
    config: DevPostgresClusterConfig,
    *,
    database: str | None = None,
    attempts: int = 20,
    retry_delay_seconds: float = 1.0,
) -> None:
    for attempt in range(1, attempts + 1):
        if _probe_postgres_ready(config, database=database):
            return
        if attempt < attempts:
            time.sleep(retry_delay_seconds)
    raise RuntimeError(
        f"Local PostgreSQL dev cluster did not accept SQL connections for database "
        f"{database or config.admin_database} on {config.host}:{config.port}."
    )


def _initdb_with_locale_fallback(config: DevPostgresClusterConfig) -> None:
    base_args = [
        str(config.bin_dir / "initdb.exe"),
        "-D",
        str(config.data_dir),
        "-U",
        "postgres",
        "-A",
        "trust",
        "--no-instructions",
    ]
    try:
        _run_checked(base_args)
    except subprocess.CalledProcessError as exc:
        if not _is_locale_text_search_failure(exc):
            raise
        _run_checked([*base_args, "--no-locale", "--encoding=UTF8"])


def _is_locale_text_search_failure(exc: subprocess.CalledProcessError) -> bool:
    output = "\n".join(
        part for part in (getattr(exc, "output", None), getattr(exc, "stderr", None)) if part
    ).lower()
    return "text search configuration" in output and "locale" in output


def _run_checked(args: list[str], *, capture_output: bool = False) -> str:
    result = subprocess.run(
        args,
        check=True,
        text=True,
        capture_output=capture_output,
    )
    return result.stdout if capture_output else ""


def _run_checked_retry(
    args: list[str],
    *,
    capture_output: bool = False,
    attempts: int = 5,
    retry_delay_seconds: float = 1.0,
    retry_returncodes: tuple[int, ...] = (2,),
) -> str:
    last_error: subprocess.CalledProcessError | None = None
    for attempt in range(1, attempts + 1):
        try:
            return _run_checked(args, capture_output=capture_output)
        except subprocess.CalledProcessError as exc:
            last_error = exc
            if exc.returncode not in retry_returncodes or attempt >= attempts:
                raise
            time.sleep(retry_delay_seconds)
    if last_error is not None:
        raise last_error
    raise RuntimeError("unreachable retry state")
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=("up", "down", "status", "print-env", "reset-schema"),
    )
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--pg-bin-dir", default=None)
    args = parser.parse_args()

    config = build_cluster_config(
        Path(args.repo_root).resolve(),
        Path(args.pg_bin_dir).resolve() if args.pg_bin_dir else None,
    )

    try:
        if args.command == "up":
            payload = command_up(config)
        elif args.command == "down":
            payload = command_down(config)
        elif args.command == "status":
            payload = command_status(config)
        elif args.command == "reset-schema":
            payload = command_reset_schema(config)
        else:
            payload = command_print_env(config)
    except RuntimeError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
