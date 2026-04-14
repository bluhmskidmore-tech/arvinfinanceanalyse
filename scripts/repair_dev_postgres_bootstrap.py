"""Repair dev storage (Postgres tmp-governance cluster + optional DuckDB file) after drift.

Postgres: only MOSS_POSTGRES_DSN on 127.0.0.1:55432 (dev_postgres_cluster default).
  - All baseline tables exist, alembic_version missing → `alembic stamp head`
  - job_run_state missing but other baseline tables exist → DROP orphan baseline tables, `upgrade head`
  - else → `alembic upgrade head`

DuckDB (optional --reset-dev-duckdb): delete repo `tmp-governance/runtime-clean/moss.duckdb` only
  (resets versioned migrations; use when startup fails e.g. "value_date already exists").

Usage (from repo root, after dev-env.ps1):
  python scripts/repair_dev_postgres_bootstrap.py
  python scripts/repair_dev_postgres_bootstrap.py --dry-run
  python scripts/repair_dev_postgres_bootstrap.py --reset-dev-duckdb
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import psycopg

ALLOWED_NETLOCS = frozenset(
    {
        ("127.0.0.1", 55432),
        ("localhost", 55432),
    }
)
_BASELINE_TABLES = (
    "job_run_state",
    "cache_build_run",
    "cache_manifest",
    "source_version_registry",
    "rule_version_registry",
)


def _parse_dsn(dsn: str) -> tuple[str, int, str]:
    parsed = urlparse(dsn)
    if parsed.scheme not in ("postgresql", "postgres"):
        raise SystemExit(f"Unexpected DSN scheme: {parsed.scheme!r}")
    host = parsed.hostname or ""
    port = parsed.port or 5432
    db = (parsed.path or "").lstrip("/") or "postgres"
    return host, port, db


def _require_dev_cluster(dsn: str) -> None:
    host, port, _db = _parse_dsn(dsn)
    if (host, port) not in ALLOWED_NETLOCS:
        raise SystemExit(
            f"Refusing to run: DSN must be dev cluster on 127.0.0.1:55432, got {host!r}:{port}"
        )


def _list_public_tables(conn: psycopg.Connection) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = %s",
            ("public",),
        )
        return {r[0] for r in cur.fetchall()}


def _alembic_version(conn: psycopg.Connection) -> str | None:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s)", ("public.alembic_version",))
        reg = cur.fetchone()[0]
        if reg is None:
            return None
        cur.execute("SELECT version_num FROM alembic_version LIMIT 1")
        row = cur.fetchone()
        return str(row[0]) if row else None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _allowed_dev_duckdb_path(repo_root: Path) -> Path:
    return (repo_root / "tmp-governance" / "runtime-clean" / "moss.duckdb").resolve()


def _reset_dev_duckdb_if_requested(*, dry_run: bool) -> None:
    """Remove dev DuckDB file only when MOSS_DUCKDB_PATH resolves to the canonical runtime-clean path."""
    raw = os.environ.get("MOSS_DUCKDB_PATH", "").strip()
    if not raw:
        raise SystemExit("MOSS_DUCKDB_PATH is not set (source dev-env.ps1 first).")
    repo = _repo_root()
    configured = Path(raw).expanduser().resolve()
    allowed = _allowed_dev_duckdb_path(repo)
    if configured != allowed:
        raise SystemExit(
            f"Refusing DuckDB reset: MOSS_DUCKDB_PATH must be {allowed} (got {configured})"
        )
    if not configured.exists():
        print("Dev DuckDB file already absent:", configured)
        return
    print("Removing dev DuckDB file:", configured)
    if dry_run:
        print("[dry-run] would delete DuckDB file")
        return
    configured.unlink()


def _run_alembic(*args: str, env: dict[str, str]) -> None:
    backend = _repo_root() / "backend"
    cmd = [sys.executable, "-m", "alembic", "-c", str(backend / "alembic.ini"), *args]
    subprocess.run(cmd, cwd=str(backend), env=env, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--reset-dev-duckdb",
        action="store_true",
        help="Delete tmp-governance/runtime-clean/moss.duckdb (dev path only).",
    )
    args = parser.parse_args()

    dsn = os.environ.get("MOSS_POSTGRES_DSN", "").strip()
    if not dsn:
        raise SystemExit("MOSS_POSTGRES_DSN is not set (source dev-env.ps1 first).")
    _require_dev_cluster(dsn)

    dry = args.dry_run
    with psycopg.connect(dsn, connect_timeout=15) as conn:
        tables = _list_public_tables(conn)
        version = _alembic_version(conn)
        baseline_present = {t for t in _BASELINE_TABLES if t in tables}
        print(f"alembic_version: {version!r}")
        print(f"baseline tables present: {sorted(baseline_present)}")

        all_baseline = all(t in tables for t in _BASELINE_TABLES)
        if all_baseline and version is None:
            print("All baseline tables exist; alembic_version missing — stamping head.")
            if dry:
                print("[dry-run] would run: alembic stamp head")
                return 0
            _run_alembic("stamp", "head", env=os.environ.copy() | {"MOSS_POSTGRES_DSN": dsn})
            print("Stamped head.")
            return 0

        need_job = "job_run_state" not in tables
        orphans = baseline_present - {"job_run_state"}
        if need_job and orphans:
            print(
                "Detected drift: job_run_state missing but other baseline tables exist; "
                "dropping orphan baseline tables (dev-only)."
            )
            if dry:
                print("[dry-run] would DROP TABLE " + ", ".join(sorted(orphans)))
            else:
                with conn.cursor() as cur:
                    for t in sorted(orphans):
                        cur.execute(f'DROP TABLE IF EXISTS public."{t}" CASCADE')
                conn.commit()
                tables = _list_public_tables(conn)
                print("after drop:", sorted(tables & set(_BASELINE_TABLES)))

    env = os.environ.copy()
    env.setdefault("MOSS_POSTGRES_DSN", dsn)

    if dry:
        print("[dry-run] would run: alembic upgrade head")
        return 0

    print("Running: alembic upgrade head")
    try:
        _run_alembic("upgrade", "head", env=env)
    except subprocess.CalledProcessError:
        print("alembic upgrade failed; try re-running after inspecting errors.", file=sys.stderr)
        return 1

    with psycopg.connect(dsn, connect_timeout=15) as conn:
        print("alembic_version after:", _alembic_version(conn))
        print("bootstrap tables:", sorted(_list_public_tables(conn) & set(_BASELINE_TABLES)))

    if args.reset_dev_duckdb:
        _reset_dev_duckdb_if_requested(dry_run=args.dry_run)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
