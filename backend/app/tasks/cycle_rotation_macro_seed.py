"""Seed PMI / social-financing macro series for cycle rotation MacroScore (dev/test + sparse backfill bootstrap)."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import duckdb

from backend.app.repositories.duckdb_migrations import (
    apply_pending_migrations_on_connection,
    ensure_choice_macro_schema_if_missing,
)

RULE_VERSION = "rv_cycle_rotation_macro_seed_v1"
DEFAULT_CONFIG_PATH = _REPO_ROOT / "config" / "cycle_rotation_macro_series.json"
DEFAULT_FIXTURE_PATH = _REPO_ROOT / "tests" / "fixtures" / "cycle_rotation_macro_monthly.json"


@dataclass(frozen=True)
class MacroSeedRow:
    series_id: str
    series_name: str
    trade_date: str
    value_numeric: float
    frequency: str
    unit: str


def load_cycle_rotation_macro_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or DEFAULT_CONFIG_PATH
    return json.loads(config_path.read_text(encoding="utf-8"))


def load_cycle_rotation_macro_fixture(path: Path | None = None) -> dict[str, Any]:
    fixture_path = path or DEFAULT_FIXTURE_PATH
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def fixture_rows(fixture: dict[str, Any]) -> list[MacroSeedRow]:
    rows: list[MacroSeedRow] = []
    for series in fixture.get("series", []):
        if not isinstance(series, dict):
            continue
        series_id = str(series.get("series_id", "")).strip()
        series_name = str(series.get("series_name", "")).strip()
        frequency = str(series.get("frequency", "monthly"))
        unit = str(series.get("unit", ""))
        points = series.get("points")
        if not series_id or not isinstance(points, list):
            continue
        for point in points:
            if not isinstance(point, list) or len(point) != 2:
                continue
            trade_date = str(point[0])
            value = float(point[1])
            rows.append(
                MacroSeedRow(
                    series_id=series_id,
                    series_name=series_name,
                    trade_date=trade_date,
                    value_numeric=value,
                    frequency=frequency,
                    unit=unit,
                )
            )
    return rows


def ensure_cycle_rotation_macro_catalog(conn: duckdb.DuckDBPyConnection, config: dict[str, Any]) -> int:
    tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
    if "phase1_macro_vendor_catalog" not in tables:
        return 0
    inserted = 0
    for series in config.get("series", []):
        if not isinstance(series, dict):
            continue
        series_id = str(series.get("series_id", "")).strip()
        if not series_id:
            continue
        exists = conn.execute(
            "select count(*) from phase1_macro_vendor_catalog where series_id = ?",
            [series_id],
        ).fetchone()
        if exists and int(exists[0]) > 0:
            continue
        conn.execute(
            """
            insert into phase1_macro_vendor_catalog (
              series_id, series_name, vendor_name, vendor_series_code, frequency, unit, theme, is_core
            ) values (?, ?, 'choice', ?, ?, ?, ?, true)
            """,
            [
                series_id,
                str(series.get("series_name", series_id)),
                series_id,
                str(series.get("frequency", "monthly")),
                str(series.get("unit", "")),
                str(series.get("theme", "macro_leading")),
            ],
        )
        inserted += 1
    return inserted


def upsert_macro_seed_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    rows: list[MacroSeedRow],
    source_version: str,
    vendor_version: str,
    run_id: str,
    overwrite_existing: bool = False,
) -> int:
    if not rows:
        return 0
    written = 0
    for row in rows:
        existing = conn.execute(
            """
            select source_version
            from fact_choice_macro_daily
            where series_id = ? and trade_date = ?
            limit 1
            """,
            [row.series_id, row.trade_date],
        ).fetchone()
        if existing:
            if not overwrite_existing:
                continue
            conn.execute(
                "delete from fact_choice_macro_daily where series_id = ? and trade_date = ?",
                [row.series_id, row.trade_date],
            )
        conn.execute(
            """
            insert into fact_choice_macro_daily (
              series_id, series_name, trade_date, value_numeric, frequency, unit,
              source_version, vendor_version, rule_version, quality_flag, run_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ok', ?)
            """,
            [
                row.series_id,
                row.series_name,
                row.trade_date,
                row.value_numeric,
                row.frequency,
                row.unit,
                source_version,
                vendor_version,
                RULE_VERSION,
                run_id,
            ],
        )
        written += 1
    return written


def materialize_cycle_rotation_macro_fixture(
    *,
    duckdb_path: str,
    fixture_path: Path | None = None,
    config_path: Path | None = None,
    overwrite_existing: bool = False,
) -> dict[str, object]:
    db_path = Path(duckdb_path)
    if not db_path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {db_path}")

    fixture = load_cycle_rotation_macro_fixture(fixture_path)
    config = load_cycle_rotation_macro_config(config_path)
    rows = fixture_rows(fixture)
    run_id = str(fixture.get("run_id") or "cycle_rotation_macro_fixture")
    source_version = str(fixture.get("source_version") or "sv_cycle_rotation_macro_fixture_v1")
    vendor_version = str(fixture.get("vendor_version") or "vv_cycle_rotation_macro_fixture_v1")

    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        apply_pending_migrations_on_connection(conn)
        ensure_choice_macro_schema_if_missing(conn)
        catalog_inserted = ensure_cycle_rotation_macro_catalog(conn, config)
        row_count = upsert_macro_seed_rows(
            conn,
            rows=rows,
            source_version=source_version,
            vendor_version=vendor_version,
            run_id=run_id,
            overwrite_existing=overwrite_existing,
        )
    finally:
        conn.close()

    series_ids = sorted({row.series_id for row in rows})
    return {
        "status": "seeded",
        "duckdb_path": str(db_path),
        "run_id": run_id,
        "source_version": source_version,
        "vendor_version": vendor_version,
        "rule_version": RULE_VERSION,
        "row_count": row_count,
        "series_ids": series_ids,
        "catalog_inserted": catalog_inserted,
        "overwrite_existing": overwrite_existing,
        "fixture_path": str(fixture_path or DEFAULT_FIXTURE_PATH),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed cycle-rotation PMI / social-financing macro fixture rows.")
    parser.add_argument(
        "--duckdb-path",
        required=True,
        help="Target DuckDB path.",
    )
    parser.add_argument(
        "--fixture",
        default=str(DEFAULT_FIXTURE_PATH),
        help="Fixture JSON with deterministic monthly points.",
    )
    parser.add_argument(
        "--force-fixture-overwrite",
        action="store_true",
        help="Overwrite existing rows for the same series/date with fixture values.",
    )
    args = parser.parse_args()
    payload = materialize_cycle_rotation_macro_fixture(
        duckdb_path=args.duckdb_path,
        fixture_path=Path(args.fixture),
        overwrite_existing=args.force_fixture_overwrite,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
