"""Synthetic catalog and governance inputs shared by readiness regression tests.

The tests exercise declared table anchors and direct-record validation,
including explicit missing/stale cases, without reading business storage.
"""

from __future__ import annotations

import json
from pathlib import Path

_READINESS_REPORT_DATE = "2026-05-31"
_BALANCE_MOVEMENT_FRESHNESS_COLUMNS = {
    "fact_accounting_asset_movement_monthly": ", currency_basis varchar",
    "product_category_pnl_canonical_fact": ", currency varchar, account_code varchar",
}


def _quoted_duckdb_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _collect_readiness_catalog_inputs() -> tuple[dict[str, dict], str, str]:
    """Seed declared table anchors at one explicit test date."""
    from scripts.mcp.moss_project_mcp import PAGE_CATALOG_DATE_TABLES

    table_names = {name for names in PAGE_CATALOG_DATE_TABLES.values() for name in names}
    tables = {
        name: {
            "status": "present",
            "date_column": "report_date",
            "available_dates": [_READINESS_REPORT_DATE],
        }
        for name in sorted(table_names)
    }
    # Preserve the ledger readiness test's missing-table and no-date-column
    # counterexamples instead of presenting every declared anchor as complete.
    tables["qdb_general_ledger_workbook"] = {"status": "missing"}
    tables["ledger_import_batch"] = {"status": "present_no_date_column"}
    tables["choice_news_event"]["date_column"] = "received_at"
    return tables, _READINESS_REPORT_DATE, _READINESS_REPORT_DATE


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


def _build_governance_streams(destination_dir: Path) -> None:
    from scripts.codex_page_readiness import DIRECT_EVIDENCE_PAGE_SLUGS
    from scripts.mcp.moss_project_mcp import (
        PAGE_CATALOG_DATE_TABLES,
        page_trace_bundle,
        product_page_trace_bundles,
    )

    bundles = product_page_trace_bundles()
    records = []
    record_page_slugs = (*DIRECT_EVIDENCE_PAGE_SLUGS, "news-events", "stock-analysis", "pnl-attribution")
    for page_slug in record_page_slugs:
        bundle = page_trace_bundle(bundles, page_slug)
        records.append({
            "page_id": bundle["page_id"],
            "page_slug": page_slug,
            "frontend_route": bundle["frontend_route"],
            "primary_api": bundle["primary_api"],
            "report_date": _READINESS_REPORT_DATE,
            "basis": "analytical",
            "source_surface": "synthetic_readiness_fixture",
            "tables_used": PAGE_CATALOG_DATE_TABLES[bundle["page_id"]],
            "source_version": f"sv_synthetic_readiness_{page_slug}",
            "rule_version": "rv_synthetic_readiness_v1",
            "created_at": "2026-06-01T00:00:00Z",
            "cache_key": f"synthetic-readiness:{page_slug}:{_READINESS_REPORT_DATE}",
            "formal_use_allowed": False,
        })
    destination_dir.mkdir(parents=True, exist_ok=True)
    (destination_dir / "cache_manifest.jsonl").write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def build_readiness_input_snapshot_env(base: Path) -> dict[str, str]:
    """Build isolated readiness inputs under *base* and return env overrides."""
    snapshot_duckdb = base / "catalog-snapshot.duckdb"
    governance_dir = base / "governance"
    tables, movement_latest, control_latest = _collect_readiness_catalog_inputs()
    _build_readiness_snapshot_duckdb(snapshot_duckdb, tables, movement_latest, control_latest)
    _build_governance_streams(governance_dir)
    return {
        "MOSS_DUCKDB_PATH": str(snapshot_duckdb),
        "MOSS_GOVERNANCE_PATH": str(governance_dir),
    }
