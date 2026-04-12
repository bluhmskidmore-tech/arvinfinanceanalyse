from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
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
    bootstrap_sql_path: Path
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
        bootstrap_sql_path=repo_root / "sql" / "0001_bootstrap_governance.sql",
    )


def build_env_mapping(config: DevPostgresClusterConfig) -> dict[str, str]:
    return {
        "MOSS_ENVIRONMENT": "development",
        "MOSS_POSTGRES_DSN": config.postgres_dsn,
        "MOSS_GOVERNANCE_SQL_DSN": config.postgres_dsn,
        "MOSS_REDIS_DSN": DEFAULT_REDIS_DSN,
        "MOSS_DUCKDB_PATH": str(config.runtime_duckdb_path),
        "MOSS_GOVERNANCE_PATH": str(config.runtime_governance_path),
        "MOSS_LOCAL_ARCHIVE_PATH": str(config.runtime_archive_path),
        "MOSS_DATA_INPUT_ROOT": str(config.runtime_data_input_path),
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


def command_up(config: DevPostgresClusterConfig) -> dict[str, object]:
    config.cluster_root.mkdir(parents=True, exist_ok=True)
    if not config.data_dir.exists():
        _run_checked(
            [
                str(config.bin_dir / "initdb.exe"),
                "-D",
                str(config.data_dir),
                "-U",
                "postgres",
                "-A",
                "trust",
                "--no-instructions",
            ]
        )

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

    _ensure_role_and_database(config)
    _bootstrap_governance_schema(config)
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
    return build_env_mapping(config)


def _ensure_role_and_database(config: DevPostgresClusterConfig) -> None:
    role_exists = _run_checked(
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
                config.admin_database,
                "-c",
                f"CREATE ROLE {config.user} LOGIN PASSWORD '{config.password}';",
            ]
        )

    db_exists = _run_checked(
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
        _run_checked(
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


def _bootstrap_governance_schema(config: DevPostgresClusterConfig) -> None:
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
            "-f",
            str(config.bootstrap_sql_path),
        ]
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
                "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO moss; "
                "ALTER TABLE source_version_registry OWNER TO moss; "
                "ALTER TABLE rule_version_registry OWNER TO moss; "
                "ALTER TABLE cache_manifest OWNER TO moss; "
                "ALTER TABLE cache_build_run OWNER TO moss;"
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


def _is_port_open(host: str, port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _run_checked(args: list[str], *, capture_output: bool = False) -> str:
    result = subprocess.run(
        args,
        check=True,
        text=True,
        capture_output=capture_output,
    )
    return result.stdout if capture_output else ""
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("up", "down", "status", "print-env"))
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--pg-bin-dir", default=None)
    args = parser.parse_args()

    config = build_cluster_config(
        Path(args.repo_root).resolve(),
        Path(args.pg_bin_dir).resolve() if args.pg_bin_dir else None,
    )

    if args.command == "up":
        payload = command_up(config)
    elif args.command == "down":
        payload = command_down(config)
    elif args.command == "status":
        payload = command_status(config)
    else:
        payload = command_print_env(config)

    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
