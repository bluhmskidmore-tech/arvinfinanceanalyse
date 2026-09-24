"""One-shot input snapshots for codex-page-readiness tests.

Extracted from tests/test_native_dev_scripts.py so that
tests/test_codex_page_readiness_gate.py can pin the same snapshot mechanism.

The readiness evaluation samples the shared real DuckDB (data/moss.duckdb)
PAGE_CATALOG_DATE_TABLES dates and the real governance streams with no lock
retry (in-process via build_page_readiness_report and from powershell/CLI
subprocesses alike). Any concurrent writer holding the real DuckDB read-write
(other pytest workers, dev worker materialize jobs, rebuild sessions) makes
read-only opens fail, which flips "catalog_date_evidence" to incomplete and
resurfaces the "full data-catalog/date review required" residual gap, turning
static-pass pages into blocked. To keep readiness tests order- and
concurrency-independent while still exercising the real data-catalog state,
derive a one-shot snapshot from the real inputs (with lock retry) and pin the
tests to it via MOSS_DUCKDB_PATH / MOSS_GOVERNANCE_PATH. A genuine catalog
regression (dropped table, emptied dates) is mirrored into the snapshot, so
the assertions keep their meaning.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_READINESS_SNAPSHOT_TRANSIENT_STATUSES = {"catalog_unavailable", "date_sample_failed"}
_BALANCE_MOVEMENT_FRESHNESS_COLUMNS = {
    "fact_accounting_asset_movement_monthly": ", currency_basis varchar",
    "product_category_pnl_canonical_fact": ", currency varchar, account_code varchar",
}


def _quoted_duckdb_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _readiness_freshness_scalar(conn, sql: str):
    """Run one freshness max-date query; treat a missing table as absent."""
    import duckdb

    try:
        row = conn.execute(sql).fetchone()
    except duckdb.Error as exc:
        if "does not exist" in str(exc) or "Catalog Error" in str(exc):
            return None
        raise
    if not row or row[0] is None:
        return None
    return str(row[0])


def _collect_readiness_catalog_inputs() -> tuple[dict[str, dict], str | None, str | None]:
    """Sample the real catalog once, retrying through transient DuckDB locks."""
    import time

    import duckdb

    from scripts.codex_page_readiness import ALL_DIRECT_EVIDENCE_PAGE_SLUGS
    from scripts.mcp.moss_project_mcp import (
        DEFAULT_DUCKDB_PATH,
        page_catalog_date_evidence,
        product_page_trace_bundles,
        resolve_path_env,
    )

    real_duckdb = resolve_path_env("MOSS_DUCKDB_PATH", DEFAULT_DUCKDB_PATH)
    bundles = product_page_trace_bundles()
    last_error: object = None
    for attempt in range(8):
        if attempt:
            time.sleep(5)
        payload = page_catalog_date_evidence(
            bundles,
            real_duckdb,
            list(ALL_DIRECT_EVIDENCE_PAGE_SLUGS),
            limit=20,
        )
        tables: dict[str, dict] = {}
        for page in payload.get("pages") or []:
            for row in page.get("table_evidence") or []:
                tables.setdefault(str(row["table_name"]), dict(row))
        transient = [
            row
            for row in tables.values()
            if row["status"] in _READINESS_SNAPSHOT_TRANSIENT_STATUSES
        ]
        if transient:
            last_error = transient[0].get("error")
            continue
        try:
            conn = duckdb.connect(str(real_duckdb), read_only=True)
            try:
                movement_latest = _readiness_freshness_scalar(
                    conn,
                    """
                    select max(cast(report_date as varchar))
                    from fact_accounting_asset_movement_monthly
                    where currency_basis = 'CNX'
                    """,
                )
                control_latest = _readiness_freshness_scalar(
                    conn,
                    """
                    select max(cast(report_date as varchar))
                    from product_category_pnl_canonical_fact
                    where currency = 'CNX'
                      and account_code not like '144020%'
                      and (
                        account_code like '141%'
                        or account_code like '142%'
                        or account_code like '143%'
                        or account_code like '1440101%'
                      )
                    """,
                )
            finally:
                conn.close()
        except duckdb.Error as exc:
            last_error = exc
            continue
        return tables, movement_latest, control_latest
    pytest.fail(
        "Could not snapshot the real DuckDB catalog for codex-page-readiness tests; "
        f"the shared database stayed locked or unreadable: {last_error}"
    )


def _build_readiness_snapshot_duckdb(
    destination: Path,
    tables: dict[str, dict],
    movement_latest: str | None,
    control_latest: str | None,
) -> None:
    import duckdb

    conn = duckdb.connect(str(destination))
    try:
        for name, row in sorted(tables.items()):
            status = str(row["status"])
            if status not in {"present", "present_no_date_column"}:
                # Mirror absent/unknown tables by omission.
                continue
            quoted_table = _quoted_duckdb_identifier(name)
            if status == "present_no_date_column":
                conn.execute(f"create table {quoted_table} (value_col varchar)")
                continue
            date_column = _quoted_duckdb_identifier(str(row["date_column"]))
            extra_columns = _BALANCE_MOVEMENT_FRESHNESS_COLUMNS.get(name, "")
            conn.execute(
                f"create table {quoted_table} ({date_column} varchar{extra_columns})"
            )
            date_values = [str(value) for value in row.get("available_dates") or []]
            if date_values:
                null_fillers = ", null" * extra_columns.count(" varchar")
                conn.executemany(
                    f"insert into {quoted_table} values (?{null_fillers})",
                    [(value,) for value in date_values],
                )
        if movement_latest is not None and "fact_accounting_asset_movement_monthly" in tables:
            conn.execute(
                "insert into fact_accounting_asset_movement_monthly values (?, 'CNX')",
                [movement_latest],
            )
        if control_latest is not None and "product_category_pnl_canonical_fact" in tables:
            conn.execute(
                "insert into product_category_pnl_canonical_fact values (?, 'CNX', '1410101')",
                [control_latest],
            )
    finally:
        conn.close()


def _copy_governance_streams(destination_dir: Path) -> None:
    import shutil

    from scripts.codex_page_readiness import _governance_stream_paths

    destination_dir.mkdir(parents=True, exist_ok=True)
    for source_path in _governance_stream_paths().values():
        if source_path.is_file():
            shutil.copyfile(source_path, destination_dir / source_path.name)


def build_readiness_input_snapshot_env(base: Path) -> dict[str, str]:
    """Build a readiness input snapshot under *base* and return env overrides."""
    snapshot_duckdb = base / "catalog-snapshot.duckdb"
    governance_dir = base / "governance"
    tables, movement_latest, control_latest = _collect_readiness_catalog_inputs()
    _build_readiness_snapshot_duckdb(snapshot_duckdb, tables, movement_latest, control_latest)
    _copy_governance_streams(governance_dir)
    return {
        "MOSS_DUCKDB_PATH": str(snapshot_duckdb),
        "MOSS_GOVERNANCE_PATH": str(governance_dir),
    }
