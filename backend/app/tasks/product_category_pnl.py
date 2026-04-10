from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import dramatiq
import duckdb

from backend.app.config.product_category_mapping import build_default_product_category_config
from backend.app.core_finance.product_category_pnl import (
    ManualAdjustment,
    apply_manual_adjustments,
    calculate_read_model,
)
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.schemas.materialize import CacheBuildRunRecord, CacheManifestRecord
from backend.app.services.product_category_source_service import (
    RULE_VERSION,
    build_canonical_facts,
    discover_source_pairs,
)
from backend.app.tasks.build_runs import BuildRunRecord


PRODUCT_CATEGORY_PNL_LOCK = LockDefinition(
    key="lock:duckdb:product-category-pnl",
    ttl_seconds=900,
)
PRODUCT_CATEGORY_ADJUSTMENT_STREAM = "product_category_pnl_adjustments"


@dramatiq.actor
def materialize_product_category_pnl(
    duckdb_path: str | None = None,
    source_dir: str | None = None,
    governance_dir: str | None = None,
    run_id: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    duckdb_file = Path(duckdb_path or settings.duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    governance_path = Path(governance_dir or settings.governance_path)
    pairs = discover_source_pairs(Path(source_dir or settings.product_category_source_dir))
    config = build_default_product_category_config(settings.ftp_rate_pct)
    repo = GovernanceRepository(base_dir=governance_path)
    run = BuildRunRecord(job_name="product_category_pnl", status="running")
    run_id = run_id or f"{run.job_name}:{run.created_at}"

    with acquire_lock(PRODUCT_CATEGORY_PNL_LOCK, base_dir=governance_path):
        repo.append(
            CACHE_BUILD_RUN_STREAM,
            CacheBuildRunRecord(
                run_id=run_id,
                job_name=run.job_name,
                status="running",
                cache_key="product_category_pnl.formal",
                lock=PRODUCT_CATEGORY_PNL_LOCK.key,
                source_version="sv_product_category_running",
                vendor_version="vv_none",
            ).model_dump(),
        )
        conn = duckdb.connect(str(duckdb_file), read_only=False)
        try:
            conn.execute("begin transaction")
            _ensure_tables(conn)

            conn.execute("delete from product_category_pnl_canonical_fact")
            conn.execute("delete from product_category_pnl_formal_read_model")
            conn.execute("delete from product_category_pnl_scenario_read_model")

            facts_by_date = {}
            source_versions: list[str] = []
            for pair in pairs:
                source_versions.append(pair.source_version)
                adjustments = _load_manual_adjustments(governance_path, pair.report_date)
                facts = apply_manual_adjustments(build_canonical_facts(pair), adjustments)
                facts_by_date[pair.report_date] = facts
                for fact in facts:
                    conn.execute(
                        """
                        insert into product_category_pnl_canonical_fact values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        [
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
                        ],
                    )

            for pair in pairs:
                for view in ("monthly", "qtd", "ytd", "year_to_report_month_end"):
                    payload = calculate_read_model(facts_by_date, pair.report_date, view, config)
                    _insert_rows(
                        conn,
                        "product_category_pnl_formal_read_model",
                        pair.report_date.isoformat(),
                        view,
                        payload["rows"],
                        pair.source_version,
                    )
                    _insert_rows(
                        conn,
                        "product_category_pnl_scenario_read_model",
                        pair.report_date.isoformat(),
                        view,
                        payload["rows"],
                        pair.source_version,
                    )

            conn.execute("commit")
        except Exception:
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
            repo.append(CACHE_BUILD_RUN_STREAM, failed_run.model_dump())
            raise
        finally:
            conn.close()

    joined_source_version = "__".join(source_versions) or "sv_product_category_empty"
    repo.append(
        CACHE_MANIFEST_STREAM,
        CacheManifestRecord(
            cache_key="product_category_pnl.formal",
            source_version=joined_source_version,
            vendor_version="vv_none",
            rule_version=RULE_VERSION,
        ).model_dump(),
    )
    repo.append(
        CACHE_BUILD_RUN_STREAM,
        CacheBuildRunRecord(
            run_id=run_id,
            job_name=run.job_name,
            status="completed",
            cache_key="product_category_pnl.formal",
            lock=PRODUCT_CATEGORY_PNL_LOCK.key,
            source_version=joined_source_version,
            vendor_version="vv_none",
        ).model_dump(),
    )
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


def _ensure_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table if not exists product_category_pnl_canonical_fact (
          report_date varchar,
          account_code varchar,
          currency varchar,
          account_name varchar,
          beginning_balance decimal(24, 8),
          ending_balance decimal(24, 8),
          monthly_pnl decimal(24, 8),
          daily_avg_balance decimal(24, 8),
          annual_avg_balance decimal(24, 8),
          days_in_period integer,
          source_version varchar,
          rule_version varchar
        )
        """
    )
    for table_name in (
        "product_category_pnl_formal_read_model",
        "product_category_pnl_scenario_read_model",
    ):
        conn.execute(
            f"""
            create table if not exists {table_name} (
              report_date varchar,
              view varchar,
              sort_order integer,
              category_id varchar,
              category_name varchar,
              side varchar,
              level integer,
              baseline_ftp_rate_pct decimal(12, 6),
              cnx_scale decimal(24, 8),
              cny_scale decimal(24, 8),
              foreign_scale decimal(24, 8),
              cnx_cash decimal(24, 8),
              cny_cash decimal(24, 8),
              foreign_cash decimal(24, 8),
              cny_ftp decimal(24, 8),
              foreign_ftp decimal(24, 8),
              cny_net decimal(24, 8),
              foreign_net decimal(24, 8),
              business_net_income decimal(24, 8),
              weighted_yield decimal(24, 8),
              is_total boolean,
              children_json varchar,
              source_version varchar,
              rule_version varchar
            )
            """
        )


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


def _load_manual_adjustments(governance_path: Path, report_date: date) -> list[ManualAdjustment]:
    rows = GovernanceRepository(base_dir=governance_path).read_all(PRODUCT_CATEGORY_ADJUSTMENT_STREAM)
    latest_by_id: dict[str, dict[str, object]] = {}
    legacy_rows: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        if str(row.get("report_date")) != report_date.isoformat():
            continue
        adjustment_id = str(row.get("adjustment_id") or "")
        if not adjustment_id:
            legacy_rows.append(row | {"adjustment_id": f"legacy-{index}"})
            continue
        existing = latest_by_id.get(adjustment_id)
        if existing is None or str(row.get("created_at", "")) >= str(existing.get("created_at", "")):
            latest_by_id[adjustment_id] = row

    adjustments: list[ManualAdjustment] = []
    for row in [*legacy_rows, *latest_by_id.values()]:
        adjustments.append(
            ManualAdjustment(
                report_date=report_date,
                operator=str(row.get("operator", "")),
                approval_status=str(row.get("approval_status", "")),
                account_code=str(row.get("account_code", "")),
                currency=str(row.get("currency", "")),
                account_name=str(row.get("account_name", "")),
                beginning_balance=_decimal_or_none(row.get("beginning_balance")),
                ending_balance=_decimal_or_none(row.get("ending_balance")),
                monthly_pnl=_decimal_or_none(row.get("monthly_pnl")),
                daily_avg_balance=_decimal_or_none(row.get("daily_avg_balance")),
                annual_avg_balance=_decimal_or_none(row.get("annual_avg_balance")),
            )
        )
    return adjustments


def _decimal_or_none(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))
