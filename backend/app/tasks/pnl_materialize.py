from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb

from backend.app.core_finance.pnl import (
    build_formal_pnl_fi_fact_rows,
    build_nonstd_pnl_bridge_rows,
    normalize_fi_pnl_records,
    normalize_nonstd_journal_entries,
)
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.schemas.materialize import CacheBuildRunRecord, CacheManifestRecord
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.build_runs import BuildRunRecord


# Basis-scoped PnL materialize identity (CACHE_SPEC §3: basis must participate in cache_key / locks).
PNL_FORMAL_BASIS = "formal"
CACHE_KEY = f"pnl:phase2:materialize:{PNL_FORMAL_BASIS}"
PNL_MATERIALIZE_LOCK = LockDefinition(
    key=f"lock:duckdb:{PNL_FORMAL_BASIS}:pnl:phase2:materialize",
    ttl_seconds=900,
)
RULE_VERSION = "rv_pnl_phase2_materialize_v1"
# API result_meta.cache_version: formal basis + materialize rule bundle (distinct from scenario/analytical).
PNL_RESULT_CACHE_VERSION = f"cv_pnl_formal__{RULE_VERSION}"


def _materialize_pnl_facts(
    *,
    report_date: str,
    is_month_end: bool,
    fi_rows: list[dict[str, object]],
    nonstd_rows_by_type: dict[str, list[dict[str, object]]],
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
    run_id: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    duckdb_file = Path(duckdb_path or settings.duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    governance_path = Path(governance_dir or settings.governance_path)
    repo = GovernanceRepository(base_dir=governance_path)
    run = BuildRunRecord(job_name="pnl_materialize", status="running")
    run_id = run_id or f"{run.job_name}:{run.created_at}"
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id=run_id,
                job_name=run.job_name,
                status="running",
                cache_key=CACHE_KEY,
                lock=PNL_MATERIALIZE_LOCK.key,
                source_version="sv_pnl_running",
                vendor_version="vv_none",
            ).model_dump(),
            "report_date": report_date,
            "started_at": run.created_at,
        },
    )

    normalized_fi = normalize_fi_pnl_records(fi_rows)
    normalized_nonstd = []
    for journal_type, rows in sorted(nonstd_rows_by_type.items()):
        if journal_type not in {"514", "516", "517", "adjustment"}:
            raise ValueError(f"Unsupported journal_type={journal_type}")
        normalized_nonstd.extend(
            normalize_nonstd_journal_entries(rows, journal_type=journal_type)
        )

    target_report_date = date.fromisoformat(report_date)
    _assert_partition_matches(report_date=target_report_date, fi_rows=normalized_fi, nonstd_rows=normalized_nonstd)

    bridge_rows = build_nonstd_pnl_bridge_rows(
        normalized_nonstd,
        target_date=target_report_date,
        is_month_end=is_month_end,
    )
    formal_fi_rows = build_formal_pnl_fi_fact_rows(normalized_fi)

    source_versions = sorted(
        {
            *(row.source_version for row in formal_fi_rows if row.source_version),
            *(row.source_version for row in bridge_rows if row.source_version),
        }
    )
    source_version = "__".join(source_versions) or "sv_pnl_empty"

    with acquire_lock(PNL_MATERIALIZE_LOCK, base_dir=duckdb_file.parent):
        conn = duckdb.connect(str(duckdb_file), read_only=False)
        try:
            conn.execute("begin transaction")
            _ensure_tables(conn)
            conn.execute(
                "delete from fact_formal_pnl_fi where report_date = ?",
                [report_date],
            )
            conn.execute(
                "delete from fact_nonstd_pnl_bridge where report_date = ?",
                [report_date],
            )

            for row in formal_fi_rows:
                conn.execute(
                    """
                    insert into fact_formal_pnl_fi values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        row.report_date.isoformat(),
                        row.instrument_code,
                        row.portfolio_name,
                        row.cost_center,
                        row.invest_type_std,
                        row.accounting_basis,
                        row.currency_basis,
                        row.interest_income_514,
                        row.fair_value_change_516,
                        row.capital_gain_517,
                        row.manual_adjustment,
                        row.total_pnl,
                        row.source_version,
                        RULE_VERSION,
                        row.ingest_batch_id,
                        row.trace_id,
                    ],
                )

            for row in bridge_rows:
                conn.execute(
                    """
                    insert into fact_nonstd_pnl_bridge values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        row.report_date.isoformat(),
                        row.bond_code,
                        row.portfolio_name,
                        row.cost_center,
                        row.interest_income_514,
                        row.fair_value_change_516,
                        row.capital_gain_517,
                        row.manual_adjustment,
                        row.total_pnl,
                        row.source_version,
                        RULE_VERSION,
                        row.ingest_batch_id,
                        row.trace_id,
                    ],
                )

            conn.execute("commit")
        except Exception as exc:
            conn.execute("rollback")
            failed_record = CacheBuildRunRecord(
                run_id=run_id,
                job_name=run.job_name,
                status="failed",
                cache_key=CACHE_KEY,
                lock=PNL_MATERIALIZE_LOCK.key,
                source_version=source_version,
                vendor_version="vv_none",
            ).model_dump()
            failed_record["error_message"] = str(exc)
            failed_record["report_date"] = report_date
            repo.append(CACHE_BUILD_RUN_STREAM, failed_record)
            raise
        finally:
            conn.close()

    completed_run = CacheBuildRunRecord(
        run_id=run_id,
        job_name=run.job_name,
        status="completed",
        cache_key=CACHE_KEY,
        lock=PNL_MATERIALIZE_LOCK.key,
        source_version=source_version,
        vendor_version="vv_none",
    ).model_dump()
    completed_run["report_date"] = report_date

    repo.append_many_atomic(
        [
            (
                CACHE_MANIFEST_STREAM,
                CacheManifestRecord(
                    cache_key=CACHE_KEY,
                    source_version=source_version,
                    vendor_version="vv_none",
                    rule_version=RULE_VERSION,
                ).model_dump(),
            ),
            (
                CACHE_BUILD_RUN_STREAM,
                completed_run,
            ),
        ]
    )

    return {
        "status": "completed",
        "cache_key": CACHE_KEY,
        "run_id": run_id,
        "report_date": report_date,
        "formal_fi_rows": len(formal_fi_rows),
        "nonstd_bridge_rows": len(bridge_rows),
        "source_version": source_version,
        "rule_version": RULE_VERSION,
        "vendor_version": "vv_none",
        "lock": PNL_MATERIALIZE_LOCK.key,
    }


materialize_pnl_facts = register_actor_once("materialize_pnl_facts", _materialize_pnl_facts)


def _ensure_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table if not exists fact_formal_pnl_fi (
          report_date varchar,
          instrument_code varchar,
          portfolio_name varchar,
          cost_center varchar,
          invest_type_std varchar,
          accounting_basis varchar,
          currency_basis varchar,
          interest_income_514 decimal(24, 8),
          fair_value_change_516 decimal(24, 8),
          capital_gain_517 decimal(24, 8),
          manual_adjustment decimal(24, 8),
          total_pnl decimal(24, 8),
          source_version varchar,
          rule_version varchar,
          ingest_batch_id varchar,
          trace_id varchar
        )
        """
    )
    conn.execute(
        """
        create table if not exists fact_nonstd_pnl_bridge (
          report_date varchar,
          bond_code varchar,
          portfolio_name varchar,
          cost_center varchar,
          interest_income_514 decimal(24, 8),
          fair_value_change_516 decimal(24, 8),
          capital_gain_517 decimal(24, 8),
          manual_adjustment decimal(24, 8),
          total_pnl decimal(24, 8),
          source_version varchar,
          rule_version varchar,
          ingest_batch_id varchar,
          trace_id varchar
        )
        """
    )


def _assert_partition_matches(
    *,
    report_date: date,
    fi_rows,
    nonstd_rows,
) -> None:
    for row in fi_rows:
        if row.report_date != report_date:
            raise ValueError(f"FI row report_date {row.report_date.isoformat()} does not match task report_date {report_date.isoformat()}")
    for row in nonstd_rows:
        if row.voucher_date.year != report_date.year or row.voucher_date.month != report_date.month:
            raise ValueError(
                f"NonStd row voucher_date {row.voucher_date.isoformat()} is outside task report_date month {report_date.isoformat()}"
            )
