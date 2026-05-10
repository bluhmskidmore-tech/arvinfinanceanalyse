from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import duckdb

from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.config.product_category_mapping import build_product_category_config_for_report_date
from backend.app.core_finance.product_category_pnl import (
    CanonicalFactRow,
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
from backend.app.schemas.product_category_pnl import ProductCategoryPnlPayload, ProductCategoryPnlRow
from backend.app.services.product_category_source_service import (
    RULE_VERSION,
    build_canonical_facts,
    discover_source_pairs,
)
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.build_runs import BuildRunRecord


PRODUCT_CATEGORY_PNL_LOCK = LockDefinition(
    key="lock:duckdb:product-category-pnl",
    ttl_seconds=900,
)
PRODUCT_CATEGORY_ADJUSTMENT_STREAM = "product_category_pnl_adjustments"
PRODUCT_CATEGORY_AVAILABLE_VIEWS = ["monthly", "qtd", "ytd", "year_to_report_month_end"]


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
    pairs = discover_source_pairs(Path(source_dir or settings.product_category_source_dir))
    repo = GovernanceRepository(base_dir=governance_path)
    run = BuildRunRecord(job_name="product_category_pnl", status="running")
    run_id = run_id or f"{run.job_name}:{run.created_at}"

    with acquire_lock(PRODUCT_CATEGORY_PNL_LOCK, base_dir=governance_path):
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
        try:
            conn.execute("begin transaction")
            _ensure_tables(conn)

            if not pairs:
                source_path = Path(source_dir or settings.product_category_source_dir)
                raise ValueError(
                    f"No product-category source pairs found in {source_path}; "
                    "existing read model was left untouched."
                )

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
                config = build_product_category_config_for_report_date(
                    pair.report_date,
                    settings.ftp_rate_pct,
                )
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

            conn.execute("commit")
            _checkpoint_if_possible(conn)
        except Exception as exc:
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
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                },
            )
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


materialize_product_category_pnl = register_actor_once(
    "materialize_product_category_pnl",
    _materialize_product_category_pnl,
)


def product_category_pnl_payload_from_canonical_ytd_anchor(
    duckdb_path: str,
    governance_dir: str,
    report_date: str,
    ftp_rate_pct: float,
) -> ProductCategoryPnlPayload | None:
    """Rebuild YTD rows from canonical facts when persisted YTD rows are missing."""
    try:
        anchor = date.fromisoformat(report_date)
    except ValueError:
        return None

    gov_path = Path(governance_dir)
    fallback_rate = Decimal(str(ftp_rate_pct))

    try:
        conn = duckdb.connect(duckdb_path, read_only=True)
    except (OSError, duckdb.Error):
        return None

    try:
        dates_rows = conn.execute(
            """
            select distinct report_date
            from product_category_pnl_canonical_fact
            where report_date <= ? and substr(report_date, 1, 4) = ?
            order by report_date
            """,
            [report_date, str(anchor.year)],
        ).fetchall()

        date_strings = [str(row[0]) for row in dates_rows]
        if report_date not in date_strings:
            return None

        facts_by: dict[date, list[CanonicalFactRow]] = {}
        for ds in date_strings:
            d_obj = date.fromisoformat(ds)
            rows = conn.execute(
                """
                select report_date, account_code, currency, account_name,
                       beginning_balance, ending_balance, monthly_pnl,
                       daily_avg_balance, annual_avg_balance, days_in_period
                from product_category_pnl_canonical_fact
                where report_date = ?
                order by account_code, currency
                """,
                [ds],
            ).fetchall()
            raw: list[CanonicalFactRow] = []
            for tup in rows:
                raw.append(
                    CanonicalFactRow(
                        report_date=date.fromisoformat(str(tup[0])),
                        account_code=str(tup[1]),
                        currency=str(tup[2]),
                        account_name=str(tup[3]),
                        beginning_balance=Decimal(str(tup[4])),
                        ending_balance=Decimal(str(tup[5])),
                        monthly_pnl=Decimal(str(tup[6])),
                        daily_avg_balance=Decimal(str(tup[7])),
                        annual_avg_balance=Decimal(str(tup[8])),
                        days_in_period=int(tup[9]),
                    )
                )
            facts_by[d_obj] = apply_manual_adjustments(
                raw,
                _load_manual_adjustments(gov_path, d_obj),
            )
    except duckdb.Error:
        return None
    finally:
        conn.close()

    if anchor not in facts_by:
        return None

    try:
        config = build_product_category_config_for_report_date(anchor, fallback_rate)
        calc_out = calculate_read_model(facts_by, anchor, "ytd", config)
    except (KeyError, ValueError, TypeError, ArithmeticError):
        return None

    typed_rows = [ProductCategoryPnlRow.model_validate(row) for row in calc_out["rows"]]
    asset_total = ProductCategoryPnlRow.model_validate(calc_out["asset_total"])
    liability_total = ProductCategoryPnlRow.model_validate(calc_out["liability_total"])
    grand_total = ProductCategoryPnlRow.model_validate(calc_out["grand_total"])
    return ProductCategoryPnlPayload(
        report_date=report_date,
        view="ytd",
        available_views=list(PRODUCT_CATEGORY_AVAILABLE_VIEWS),
        scenario_rate_pct=None,
        rows=typed_rows,
        asset_total=asset_total,
        liability_total=liability_total,
        grand_total=grand_total,
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
