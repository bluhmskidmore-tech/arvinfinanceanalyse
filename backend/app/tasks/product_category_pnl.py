from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import duckdb

from backend.app.config.product_category_mapping import build_product_category_config_for_report_date
from backend.app.core_finance.product_category_pnl import (
    apply_manual_adjustments,
    calculate_read_model,
)
from backend.app.governance.locks import LockDefinition, acquire_lock, resolve_duckdb_writer_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.repositories.product_category_pnl_repo import (
    PRODUCT_CATEGORY_ADJUSTMENT_STREAM as PRODUCT_CATEGORY_ADJUSTMENT_STREAM,
)
from backend.app.repositories.product_category_pnl_repo import (
    load_product_category_manual_adjustments,
)
from backend.app.schemas.materialize import CacheBuildRunRecord, CacheManifestRecord
from backend.app.services.product_category_pnl_read_service import (
    PRODUCT_CATEGORY_AVAILABLE_VIEWS as PRODUCT_CATEGORY_AVAILABLE_VIEWS,
)
from backend.app.services.product_category_pnl_read_service import (
    product_category_pnl_payload_from_canonical_ytd_anchor as product_category_pnl_payload_from_canonical_ytd_anchor,
)
from backend.app.services.product_category_source_service import (
    RULE_VERSION,
    build_canonical_facts,
    discover_source_pairs,
)
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.build_runs import BuildRunRecord
from backend.app.tasks.product_category_refresh_state import (
    PRODUCT_CATEGORY_TABLES,
    REFRESH_STATE_VERSION,
    implementation_signature,
    input_signature,
    reusable_years,
    stored_state,
)

PRODUCT_CATEGORY_PNL_LOCK = LockDefinition(
    key="lock:duckdb:product-category-pnl",
    ttl_seconds=900,
)
# Compatibility for callers that previously loaded adjustments through this task.
_load_manual_adjustments = load_product_category_manual_adjustments


def _materialize_product_category_pnl(
    duckdb_path: str | None = None,
    source_dir: str | None = None,
    governance_dir: str | None = None,
    run_id: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    duckdb_file = Path(duckdb_path or settings.duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    governance_path = Path(governance_dir or settings.governance_path)
    repo = GovernanceRepository(base_dir=governance_path)
    run = BuildRunRecord(job_name="product_category_pnl", status="running")
    run_id = run_id or f"{run.job_name}:{run.created_at}"

    writer_lock = resolve_duckdb_writer_lock(
        duckdb_file,
        ttl_seconds=PRODUCT_CATEGORY_PNL_LOCK.ttl_seconds,
    )

    with acquire_lock(writer_lock, base_dir=duckdb_file.parent):
        previous_manifest = repo.read_latest_manifest("product_category_pnl.formal")
        previous_run = next(
            (
                row for row in reversed(repo.read_all(CACHE_BUILD_RUN_STREAM))
                if row.get("cache_key") == "product_category_pnl.formal"
                and row.get("job_name") == run.job_name
                and row.get("status") != "queued"
            ),
            None,
        )
        repo.append(
            CACHE_BUILD_RUN_STREAM,
            {
                **CacheBuildRunRecord(
                    run_id=run_id,
                    job_name=run.job_name,
                    status="running",
                    cache_key="product_category_pnl.formal",
                    lock=PRODUCT_CATEGORY_PNL_LOCK.key,
                    source_version="sv_product_category_running",
                    vendor_version="vv_none",
                ).model_dump(),
                "started_at": run.created_at,
            },
        )
        conn = duckdb.connect(str(duckdb_file), read_only=False)
        transaction_open = False
        try:
            conn.execute("begin transaction")
            transaction_open = True
            _ensure_tables(conn)
            source_path = Path(source_dir or settings.product_category_source_dir)
            pairs = discover_source_pairs(source_path)

            if not pairs:
                raise ValueError(
                    f"No product-category source pairs found in {source_path}; "
                    "existing read model was left untouched."
                )

            implementation = implementation_signature()
            events = repo.read_all(PRODUCT_CATEGORY_ADJUSTMENT_STREAM)
            adjustments_by_date = {
                pair.report_date: load_product_category_manual_adjustments(
                    governance_path, pair.report_date, events=events,
                )
                for pair in pairs
            }
            configs = {
                pair.report_date: build_product_category_config_for_report_date(
                    pair.report_date, settings.ftp_rate_pct,
                )
                for pair in pairs
            }
            years = sorted({str(pair.report_date.year) for pair in pairs})
            inputs = {
                year: input_signature([
                    {
                        "date": pair.report_date.isoformat(),
                        "source": pair.source_version,
                        "adjustments": [asdict(item) for item in adjustments_by_date[pair.report_date]],
                        "config": configs[pair.report_date],
                        "rule": RULE_VERSION,
                    }
                    for pair in pairs if str(pair.report_date.year) == year
                ])
                for year in years
            }
            before = stored_state(conn, years)
            reused = reusable_years(
                manifest=previous_manifest, previous_run=previous_run,
                inputs=inputs, stored=before, implementation=implementation, rule_version=RULE_VERSION,
            )
            rebuilt = set(years) - reused
            removed = set(before["years"]) - set(years)
            for year in sorted(rebuilt | removed):
                for table in PRODUCT_CATEGORY_TABLES:
                    conn.execute(
                        f"delete from {table} where coalesce(substr(report_date, 1, 4), '<invalid>') = ?",
                        [year],
                    )

            # Always parse original inputs for a rebuilt year. Persisted canonical
            # amounts are rounded to 8 decimal places and already include adjustments.
            facts_by_date = {}
            rebuilt_pairs = [pair for pair in pairs if str(pair.report_date.year) in rebuilt]
            for pair in rebuilt_pairs:
                facts = apply_manual_adjustments(
                    build_canonical_facts(pair), adjustments_by_date[pair.report_date],
                )
                facts_by_date[pair.report_date] = facts
                # Bound SQL/parameter size while avoiding one statement per fact.
                # Keep scalar Decimal bindings and the enclosing refresh transaction.
                for offset in range(0, len(facts), 500):
                    batch = facts[offset : offset + 500]
                    placeholders = ", ".join(["(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"] * len(batch))
                    conn.execute(
                        f"insert into product_category_pnl_canonical_fact values {placeholders}",
                        [
                            value
                            for fact in batch
                            for value in (
                                fact.report_date.isoformat(),
                                fact.account_code,
                                fact.currency,
                                fact.account_name,
                                fact.beginning_balance,
                                fact.ending_balance,
                                fact.monthly_pnl,
                                fact.daily_avg_balance,
                                fact.annual_avg_balance,
                                fact.days_in_period,
                                pair.source_version,
                                RULE_VERSION,
                            )
                        ],
                    )

            for pair in rebuilt_pairs:
                config = configs[pair.report_date]
                for view in ("monthly", "qtd", "ytd", "year_to_report_month_end"):
                    payload = calculate_read_model(facts_by_date, pair.report_date, view, config)
                    _insert_rows(
                        conn,
                        "product_category_pnl_formal_read_model",
                        pair.report_date.isoformat(),
                        view,
                        cast(list[dict[str, object]], payload["rows"]),
                        pair.source_version,
                    )

            # A source or adjustment edited during this run must not certify a
            # mixture of input versions as a completed materialization.
            if (
                [(pair.report_date, pair.source_version) for pair in discover_source_pairs(source_path)]
                != [(pair.report_date, pair.source_version) for pair in pairs]
                or repo.read_all(PRODUCT_CATEGORY_ADJUSTMENT_STREAM) != events
                or implementation_signature() != implementation
            ):
                raise ValueError("Product-category inputs changed during materialization; retry the refresh.")
            after = stored_state(conn, years) if rebuilt or removed else before
            joined_source_version = "__".join(pair.source_version for pair in pairs)
            manifest = CacheManifestRecord(
                cache_key="product_category_pnl.formal",
                source_version=joined_source_version,
                vendor_version="vv_none",
                rule_version=RULE_VERSION,
                run_id=run_id,
                created_at=datetime.now(UTC).isoformat(),
                lineage={
                    "product_category_refresh": {
                        "version": REFRESH_STATE_VERSION,
                        "implementation": implementation,
                        "inputs": inputs,
                        "stored": after,
                        "rebuilt_years": sorted(rebuilt),
                        "reused_years": sorted(reused),
                        "removed_years": sorted(removed),
                    },
                },
            )
            completed = CacheBuildRunRecord(
                run_id=run_id,
                job_name=run.job_name,
                status="completed",
                cache_key="product_category_pnl.formal",
                lock=PRODUCT_CATEGORY_PNL_LOCK.key,
                source_version=joined_source_version,
                vendor_version="vv_none",
            )
            conn.execute("commit")
            transaction_open = False
            _checkpoint_if_possible(conn)
            # Keep the writer lock until both receipts are durable. A failed
            # receipt leaves a failed run, so the next attempt will rebuild.
            repo.append_many_atomic([
                (CACHE_MANIFEST_STREAM, manifest.model_dump()),
                (CACHE_BUILD_RUN_STREAM, completed.model_dump()),
            ])
        except Exception as exc:
            if transaction_open:
                conn.execute("rollback")
            failed_run = CacheBuildRunRecord(
                run_id=run_id,
                job_name=run.job_name,
                status="failed",
                cache_key="product_category_pnl.formal",
                lock=PRODUCT_CATEGORY_PNL_LOCK.key,
                source_version="sv_product_category_failed",
                vendor_version="vv_none",
            )
            repo.append(
                CACHE_BUILD_RUN_STREAM,
                {
                    **failed_run.model_dump(),
                    "error_message": str(exc),
                    "finished_at": datetime.now(UTC).isoformat(),
                },
            )
            raise
        finally:
            conn.close()

    return {
        "status": "completed",
        "run_id": run_id,
        "lock": PRODUCT_CATEGORY_PNL_LOCK.key,
        "cache_key": "product_category_pnl.formal",
        "month_count": len(pairs),
        "report_dates": [pair.report_date.isoformat() for pair in pairs],
        "rule_version": RULE_VERSION,
        "source_version": joined_source_version,
    }


materialize_product_category_pnl = register_actor_once(
    "materialize_product_category_pnl",
    _materialize_product_category_pnl,
)


def materialize_product_category_pnl_sync(
    duckdb_path: str | None = None,
    source_dir: str | None = None,
    governance_dir: str | None = None,
    run_id: str | None = None,
) -> dict[str, object]:
    return _materialize_product_category_pnl(
        duckdb_path=duckdb_path,
        source_dir=source_dir,
        governance_dir=governance_dir,
        run_id=run_id,
    )


def _ensure_tables(conn: duckdb.DuckDBPyConnection) -> None:
    """Baseline DDL is versioned in `duckdb_migrations` (also run at API/worker startup)."""
    apply_pending_migrations_on_connection(conn)


def _checkpoint_if_possible(conn: duckdb.DuckDBPyConnection) -> None:
    try:
        conn.execute("checkpoint")
    except duckdb.Error:
        pass


def _insert_rows(
    conn: duckdb.DuckDBPyConnection,
    table_name: str,
    report_date: str,
    view: str,
    rows: list[dict[str, object]],
    source_version: str,
) -> None:
    for sort_order, row in enumerate(rows, start=1):
        conn.execute(
            f"""
            insert into {table_name} values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                report_date,
                view,
                sort_order,
                row["category_id"],
                row["category_name"],
                row["side"],
                row["level"],
                row["baseline_ftp_rate_pct"],
                row["cnx_scale"],
                row["cny_scale"],
                row["foreign_scale"],
                row["cnx_cash"],
                row["cny_cash"],
                row["foreign_cash"],
                row["cny_ftp"],
                row["foreign_ftp"],
                row["cny_net"],
                row["foreign_net"],
                row["business_net_income"],
                row["weighted_yield"],
                row["is_total"],
                json.dumps(row["children"], ensure_ascii=False),
                source_version,
                RULE_VERSION,
            ],
        )
