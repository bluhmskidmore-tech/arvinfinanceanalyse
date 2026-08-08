from __future__ import annotations

import hashlib
import os
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import duckdb
from backend.app.core_finance.accounting_asset_movement import (
    AccountingAssetMovementRow,
    GlAccountingAssetBalance,
    ZqtzAccountingAssetBalance,
    build_accounting_asset_movement_rows,
)
from backend.app.core_finance.accounting_basis_constants import ACCOUNTING_BASIS_AC
from backend.app.governance.locks import LockDefinition, acquire_lock, resolve_duckdb_writer_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.duckdb_migrations import apply_pending_migrations_on_connection
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.schemas.materialize import CacheBuildRunRecord, CacheManifestRecord
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.formal_balance_pipeline import run_formal_balance_pipeline_sync
from backend.app.tasks.product_category_pnl import materialize_product_category_pnl_sync

RULE_VERSION = "rv_accounting_asset_movement_v2"
CACHE_KEY = "accounting_asset_movement.monthly"
CACHE_VERSION = "cv_accounting_asset_movement_v1"
JOB_NAME = "accounting_asset_movement_refresh"
PENDING_SOURCE_VERSION = "sv_accounting_asset_movement_pending"
VENDOR_VERSION = "vv_none"
ACCOUNTING_ASSET_MOVEMENT_REFRESH_LOCK = LockDefinition(
    key="lock:duckdb:accounting-asset-movement:refresh",
    ttl_seconds=900,
)
INPUT_SOURCES = (
    "product_category_pnl_canonical_fact",
    "fact_formal_zqtz_balance_daily",
)
FACT_TABLES = ("fact_accounting_asset_movement_monthly",)
MODULE_NAME = "accounting_asset_movement"
BASIS = "read-model"
RESULT_KIND_FAMILY = "balance-analysis.movement"


class AccountingAssetMovementSourceMissingError(RuntimeError):
    pass


def _materialize_accounting_asset_movement(
    *,
    report_date: str,
    duckdb_path: str | None = None,
    currency_basis: str = "CNX",
) -> dict[str, object]:
    settings = get_settings()
    duckdb_file = Path(duckdb_path or settings.duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)

    conn = duckdb.connect(str(duckdb_file), read_only=False)
    try:
        conn.execute("begin transaction")
        rows = materialize_accounting_asset_movement_on_connection(
            conn,
            report_date=report_date,
            currency_basis=currency_basis,
        )
        conn.execute("commit")
        _checkpoint_if_possible(conn)
    except Exception:
        conn.execute("rollback")
        raise
    finally:
        conn.close()

    source_versions = sorted(
        {
            token
            for row in rows
            for token in row.source_version.split("__")
            if token
        }
    )
    return {
        "status": "completed",
        "cache_key": CACHE_KEY,
        "report_date": report_date,
        "currency_basis": currency_basis,
        "row_count": len(rows),
        "source_version": "__".join(source_versions),
        "rule_version": RULE_VERSION,
    }


materialize_accounting_asset_movement = register_actor_once(
    "materialize_accounting_asset_movement",
    _materialize_accounting_asset_movement,
)


def _refresh_accounting_asset_movement_window(
    *,
    report_dates: list[str],
    anchor_report_date: str,
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
    currency_basis: str = "CNX",
    product_category_refreshed_dates: list[str] | None = None,
    formal_balance_refreshed_dates: list[str] | None = None,
    product_category_source_dir: str | None = None,
    data_root: str | None = None,
    archive_dir: str | None = None,
    fx_source_path: str | None = None,
    run_id: str | None = None,
) -> dict[str, object]:
    if not _movement_refresh_via_task_enabled():
        raise RuntimeError("Task-owned accounting asset movement refresh is disabled.")

    normalized_report_dates = sorted({str(value) for value in report_dates if str(value).strip()})
    if not normalized_report_dates:
        raise ValueError("report_dates is required for accounting asset movement refresh.")

    settings = get_settings()
    duckdb_file = Path(duckdb_path or settings.duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    governance_path = Path(governance_dir or settings.governance_path)
    governance_repo = GovernanceRepository(base_dir=governance_path)
    lock_definition = _refresh_lock_definition(
        report_dates=normalized_report_dates,
        anchor_report_date=anchor_report_date,
        currency_basis=currency_basis,
    )
    active_run_id = run_id or _build_refresh_run_id()
    queued_at = datetime.now(UTC).isoformat()
    governance_repo.append(
        CACHE_BUILD_RUN_STREAM,
        _build_run_record(
            run_id=active_run_id,
            status="queued",
            lock_key=lock_definition.key,
            source_version=PENDING_SOURCE_VERSION,
            report_date=anchor_report_date,
            queued_at=queued_at,
        ),
    )
    started_at = datetime.now(UTC).isoformat()
    governance_repo.append(
        CACHE_BUILD_RUN_STREAM,
        _build_run_record(
            run_id=active_run_id,
            status="running",
            lock_key=lock_definition.key,
            source_version=PENDING_SOURCE_VERSION,
            report_date=anchor_report_date,
            queued_at=queued_at,
            started_at=started_at,
        ),
    )

    payloads_by_date: dict[str, dict[str, object]] = {}
    refreshed_product_category_dates: list[str] = []
    refreshed_formal_balance_dates: list[str] = []
    try:
        refreshed_product_category_dates = (
            list(product_category_refreshed_dates)
            if product_category_refreshed_dates is not None
            else (
                _refresh_missing_product_category_dates(
                    duckdb_path=str(duckdb_file),
                    governance_dir=str(governance_path),
                    report_dates=normalized_report_dates,
                    currency_basis=currency_basis,
                    source_dir=product_category_source_dir,
                )
                if product_category_source_dir is not None
                else []
            )
        )
        refreshed_formal_balance_dates = (
            list(formal_balance_refreshed_dates)
            if formal_balance_refreshed_dates is not None
            else (
                _refresh_formal_zqtz_dates(
                    duckdb_path=str(duckdb_file),
                    governance_dir=str(governance_path),
                    report_dates=normalized_report_dates,
                    data_root=data_root,
                    archive_dir=archive_dir,
                    fx_source_path=fx_source_path,
                )
                if data_root is not None
                else []
            )
        )
        writer_lock = resolve_duckdb_writer_lock(
            duckdb_file,
            ttl_seconds=lock_definition.ttl_seconds,
        )
        with acquire_lock(
            writer_lock,
            base_dir=duckdb_file.parent,
            timeout_seconds=0.1,
        ):
            conn = duckdb.connect(str(duckdb_file), read_only=False)
            try:
                conn.execute("begin transaction")
                for current_report_date in normalized_report_dates:
                    rows = materialize_accounting_asset_movement_on_connection(
                        conn,
                        report_date=current_report_date,
                        currency_basis=currency_basis,
                    )
                    payloads_by_date[current_report_date] = {
                        "status": "completed",
                        "cache_key": CACHE_KEY,
                        "report_date": current_report_date,
                        "currency_basis": currency_basis,
                        "row_count": len(rows),
                        "source_version": _rows_source_version(rows),
                        "rule_version": RULE_VERSION,
                    }
                conn.execute("commit")
                _checkpoint_if_possible(conn)
            except Exception:
                conn.execute("rollback")
                raise
            finally:
                conn.close()
    except Exception as exc:
        governance_repo.append(
            CACHE_BUILD_RUN_STREAM,
            _build_run_record(
                run_id=active_run_id,
                status="failed",
                lock_key=lock_definition.key,
                source_version=_payloads_source_version(payloads_by_date) or PENDING_SOURCE_VERSION,
                report_date=anchor_report_date,
                queued_at=queued_at,
                started_at=started_at,
                finished_at=datetime.now(UTC).isoformat(),
                error_message=str(exc),
                failure_category="lock_timeout" if isinstance(exc, TimeoutError) else "materialize_failure",
                failure_reason=_failure_reason(exc),
            ),
        )
        raise

    manifest_entries: list[tuple[str, dict[str, object]]] = []
    for current_report_date in normalized_report_dates:
        payload = payloads_by_date[current_report_date]
        manifest_entries.append(
            (
                CACHE_MANIFEST_STREAM,
                CacheManifestRecord(
                    cache_key=CACHE_KEY,
                    cache_version=CACHE_VERSION,
                    source_version=str(payload["source_version"]),
                    vendor_version=VENDOR_VERSION,
                    rule_version=RULE_VERSION,
                    basis=BASIS,
                    module_name=MODULE_NAME,
                    result_kind_family=RESULT_KIND_FAMILY,
                    run_id=active_run_id,
                    report_date=current_report_date,
                    input_sources=list(INPUT_SOURCES),
                    fact_tables=list(FACT_TABLES),
                    lineage={
                        "run_id": active_run_id,
                        "anchor_report_date": anchor_report_date,
                        "report_date": current_report_date,
                        "currency_basis": currency_basis,
                        "cache_key": CACHE_KEY,
                        "cache_version": CACHE_VERSION,
                        "source_version": str(payload["source_version"]),
                        "rule_version": RULE_VERSION,
                        "fact_tables": list(FACT_TABLES),
                        "movement_refreshed_dates": normalized_report_dates,
                        "product_category_refreshed_dates": refreshed_product_category_dates,
                        "formal_balance_refreshed_dates": refreshed_formal_balance_dates,
                    },
                ).model_dump(),
            )
        )

    source_version = _payloads_source_version(payloads_by_date)
    manifest_entries.append(
        (
            CACHE_BUILD_RUN_STREAM,
            _build_run_record(
                run_id=active_run_id,
                status="completed",
                lock_key=lock_definition.key,
                source_version=source_version,
                report_date=anchor_report_date,
                queued_at=queued_at,
                started_at=started_at,
                finished_at=datetime.now(UTC).isoformat(),
            ),
        )
    )
    governance_repo.append_many_atomic(manifest_entries)

    return {
        "status": "completed",
        "cache_key": CACHE_KEY,
        "cache_version": CACHE_VERSION,
        "run_id": active_run_id,
        "job_name": JOB_NAME,
        "report_date": anchor_report_date,
        "currency_basis": currency_basis,
        "lock": lock_definition.key,
        "source_version": source_version,
        "rule_version": RULE_VERSION,
        "payloads_by_date": payloads_by_date,
        "movement_refreshed_dates": normalized_report_dates,
        "product_category_refreshed_dates": refreshed_product_category_dates,
        "formal_balance_refreshed_dates": refreshed_formal_balance_dates,
    }


refresh_accounting_asset_movement_window = register_actor_once(
    "refresh_accounting_asset_movement_window",
    _refresh_accounting_asset_movement_window,
)


def refresh_accounting_asset_movement_window_sync(
    *,
    report_dates: list[str],
    anchor_report_date: str,
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
    currency_basis: str = "CNX",
    product_category_refreshed_dates: list[str] | None = None,
    formal_balance_refreshed_dates: list[str] | None = None,
    product_category_source_dir: str | None = None,
    data_root: str | None = None,
    archive_dir: str | None = None,
    fx_source_path: str | None = None,
    run_id: str | None = None,
) -> dict[str, object]:
    return _refresh_accounting_asset_movement_window(
        report_dates=report_dates,
        anchor_report_date=anchor_report_date,
        currency_basis=currency_basis,
        **({} if duckdb_path is None else {"duckdb_path": duckdb_path}),
        **({} if governance_dir is None else {"governance_dir": governance_dir}),
        **(
            {}
            if product_category_refreshed_dates is None
            else {"product_category_refreshed_dates": product_category_refreshed_dates}
        ),
        **(
            {}
            if formal_balance_refreshed_dates is None
            else {"formal_balance_refreshed_dates": formal_balance_refreshed_dates}
        ),
        **(
            {}
            if product_category_source_dir is None
            else {"product_category_source_dir": product_category_source_dir}
        ),
        **({} if data_root is None else {"data_root": data_root}),
        **({} if archive_dir is None else {"archive_dir": archive_dir}),
        **({} if fx_source_path is None else {"fx_source_path": fx_source_path}),
        **({} if run_id is None else {"run_id": run_id}),
    )


def _movement_refresh_via_task_enabled() -> bool:
    return str(os.environ.get("MOSS_MOVEMENT_REFRESH_VIA_TASK", "1")).strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _refresh_lock_definition(
    *,
    report_dates: list[str],
    anchor_report_date: str,
    currency_basis: str,
) -> LockDefinition:
    window_token = ",".join(report_dates)
    digest = hashlib.sha256(window_token.encode("utf-8")).hexdigest()[:12]
    return LockDefinition(
        key=(
            f"{ACCOUNTING_ASSET_MOVEMENT_REFRESH_LOCK.key}"
            f":{CACHE_KEY}:{currency_basis}:{anchor_report_date}:{digest}"
        ),
        ttl_seconds=ACCOUNTING_ASSET_MOVEMENT_REFRESH_LOCK.ttl_seconds,
    )


def _build_refresh_run_id() -> str:
    return f"{JOB_NAME}:{datetime.now(UTC).isoformat()}"


def _build_run_record(
    *,
    run_id: str,
    status: str,
    lock_key: str,
    source_version: str,
    report_date: str,
    queued_at: str | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    error_message: str | None = None,
    failure_category: str | None = None,
    failure_reason: str | None = None,
) -> dict[str, object]:
    return {
        **CacheBuildRunRecord(
            run_id=run_id,
            job_name=JOB_NAME,
            status=status,
            cache_key=CACHE_KEY,
            cache_version=CACHE_VERSION,
            lock=lock_key,
            source_version=source_version,
            vendor_version=VENDOR_VERSION,
            rule_version=RULE_VERSION,
        ).model_dump(),
        "report_date": report_date,
        "queued_at": queued_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "error_message": error_message,
        "failure_category": failure_category,
        "failure_reason": failure_reason,
    }


def _rows_source_version(rows: list[AccountingAssetMovementRow]) -> str:
    tokens = sorted(
        {
            token
            for row in rows
            for token in str(row.source_version or "").split("__")
            if token
        }
    )
    return "__".join(tokens) or "sv_accounting_asset_movement_empty"


def _payloads_source_version(payloads_by_date: dict[str, dict[str, object]]) -> str:
    tokens: set[str] = set()
    for payload in payloads_by_date.values():
        for token in str(payload.get("source_version") or "").split("__"):
            normalized = token.strip()
            if normalized:
                tokens.add(normalized)
    return "__".join(sorted(tokens))


def _failure_reason(exc: Exception) -> str:
    reason = str(exc).strip()
    return reason or exc.__class__.__name__


def _ensure_tables(conn: duckdb.DuckDBPyConnection) -> None:
    apply_pending_migrations_on_connection(conn)


def _checkpoint_if_possible(conn: duckdb.DuckDBPyConnection) -> None:
    try:
        conn.execute("checkpoint")
    except duckdb.Error:
        pass


def _refresh_missing_product_category_dates(
    *,
    duckdb_path: str,
    governance_dir: str,
    report_dates: list[str],
    currency_basis: str,
    source_dir: str | None,
) -> list[str]:
    missing_dates = _missing_product_category_control_dates(
        duckdb_path,
        report_dates=report_dates,
        currency_basis=currency_basis,
    )
    if not missing_dates:
        return []

    source_path = Path(source_dir) if source_dir else Path(get_settings().product_category_source_dir)
    if not _has_product_category_sources_for_dates(source_path, missing_dates):
        joined_dates = ", ".join(missing_dates)
        raise RuntimeError(
            "Cannot refresh accounting asset movement because "
            "product_category_pnl_canonical_fact has no control-account rows "
            f"for {joined_dates}, and no matching product-category source files were found."
        )

    materialize_product_category_pnl_sync(
        duckdb_path=duckdb_path,
        source_dir=str(source_path),
        governance_dir=governance_dir,
    )

    remaining_dates = _missing_product_category_control_dates(
        duckdb_path,
        report_dates=missing_dates,
        currency_basis=currency_basis,
    )
    if remaining_dates:
        joined_dates = ", ".join(remaining_dates)
        raise RuntimeError(
            "Product-category PnL refresh completed but control-account rows "
            f"are still missing for {joined_dates}."
        )
    return missing_dates


def _missing_product_category_control_dates(
    duckdb_path: str,
    *,
    report_dates: list[str],
    currency_basis: str,
) -> list[str]:
    if not report_dates:
        return []
    try:
        conn = duckdb.connect(duckdb_path, read_only=True)
        table_exists = conn.execute(
            """
            select 1
            from information_schema.tables
            where table_name = 'product_category_pnl_canonical_fact'
            limit 1
            """
        ).fetchone()
        if table_exists is None:
            return report_dates
        rows = conn.execute(
            """
            select cast(report_date as varchar) as report_date, count(*) as row_count
            from product_category_pnl_canonical_fact
            where cast(report_date as varchar) in (select unnest(?))
              and currency = ?
              and (
                account_code like '141%'
                or account_code like '142%'
                or account_code like '143%'
                or account_code like '1440101%'
              )
            group by 1
            """,
            [report_dates, currency_basis],
        ).fetchall()
    except duckdb.Error:
        return report_dates
    finally:
        if "conn" in locals():
            conn.close()

    available_dates = {str(row[0]) for row in rows if int(row[1] or 0) > 0}
    return [
        current_report_date
        for current_report_date in report_dates
        if current_report_date not in available_dates
    ]


def _has_product_category_sources_for_dates(
    source_dir: Path,
    report_dates: list[str],
) -> bool:
    if not report_dates or not source_dir.exists():
        return False
    for report_date in report_dates:
        month_token = report_date[:7].replace("-", "")
        if not any(source_dir.glob(f"*{month_token}*.xls*")):
            return False
    return True


def _refresh_formal_zqtz_dates(
    *,
    duckdb_path: str,
    governance_dir: str,
    report_dates: list[str],
    data_root: str | None,
    archive_dir: str | None,
    fx_source_path: str | None,
) -> list[str]:
    stale_dates = _stale_formal_zqtz_dates(duckdb_path, report_dates=report_dates)
    if not stale_dates:
        return []

    data_root_path = Path(data_root) if data_root else Path(get_settings().data_input_root)
    if not _has_zqtz_sources_for_dates(data_root_path, stale_dates):
        joined_dates = ", ".join(stale_dates)
        raise RuntimeError(
            "Cannot refresh formal ZQTZ balances because matching ZQTZSHOW "
            f"source files were not found for {joined_dates}."
        )
    for current_report_date in stale_dates:
        run_formal_balance_pipeline_sync(
            report_date=current_report_date,
            data_root=str(data_root_path),
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            archive_dir=archive_dir,
            fx_source_path=fx_source_path,
        )
    return stale_dates


def _has_zqtz_sources_for_dates(data_root: Path, report_dates: list[str]) -> bool:
    if not report_dates or not data_root.exists():
        return False
    for report_date in report_dates:
        compact_date = report_date.replace("-", "")
        dotted_date = report_date.replace("-", ".")
        has_source = any(
            any(data_root.glob(pattern))
            for pattern in (
                f"ZQTZSHOW*{compact_date}*.xls",
                f"ZQTZSHOW*{dotted_date}*.xls",
            )
        )
        if not has_source:
            return False
    return True


def _stale_formal_zqtz_dates(
    duckdb_path: str,
    *,
    report_dates: list[str],
) -> list[str]:
    if not report_dates:
        return []
    try:
        conn = duckdb.connect(duckdb_path, read_only=True)
        rows = conn.execute(
            """
            select
              cast(report_date as varchar) as report_date,
              count(*) as row_count,
              sum(
                case
                  when coalesce(trim(business_type_primary), '') = '' then 1
                  else 0
                end
              ) as empty_business_type_count
            from fact_formal_zqtz_balance_daily
            where cast(report_date as varchar) in (select unnest(?))
              and currency_basis = 'CNY'
              and position_scope = 'asset'
            group by 1
            """,
            [report_dates],
        ).fetchall()
    except duckdb.Error:
        return report_dates
    finally:
        if "conn" in locals():
            conn.close()

    freshness_by_date = {
        str(row[0]): {
            "row_count": int(row[1] or 0),
            "empty_business_type_count": int(row[2] or 0),
        }
        for row in rows
    }
    stale_dates: list[str] = []
    for current_report_date in report_dates:
        freshness = freshness_by_date.get(current_report_date)
        if freshness is None:
            stale_dates.append(current_report_date)
            continue
        row_count = freshness["row_count"]
        if row_count == 0 or freshness["empty_business_type_count"] == row_count:
            stale_dates.append(current_report_date)
    return stale_dates


def materialize_accounting_asset_movement_on_connection(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    currency_basis: str = "CNX",
) -> list[AccountingAssetMovementRow]:
    parsed_report_date = date.fromisoformat(report_date)
    _ensure_tables(conn)
    _validate_gl_control_source_rows(
        conn,
        report_date=report_date,
        currency_basis=currency_basis,
    )
    zqtz_rows = _load_zqtz_rows(
        conn,
        report_date=report_date,
        currency_basis=currency_basis,
    )
    gl_rows = _load_gl_rows(
        conn,
        report_date=report_date,
        currency_basis=currency_basis,
    )
    rows = build_accounting_asset_movement_rows(
        report_date=parsed_report_date,
        zqtz_rows=zqtz_rows,
        gl_rows=gl_rows,
    )
    conn.execute(
        """
        delete from fact_accounting_asset_movement_monthly
        where report_date = ?
          and currency_basis = ?
        """,
        [report_date, currency_basis],
    )
    _insert_rows(conn, rows, currency_basis=currency_basis)
    return rows


def _validate_gl_control_source_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    currency_basis: str,
) -> None:
    try:
        row = conn.execute(
            """
            select count(*)
            from product_category_pnl_canonical_fact
            where cast(report_date as varchar) = ?
              and currency = ?
              and (
                account_code like '141%'
                or account_code like '142%'
                or account_code like '143%'
                or account_code like '1440101%'
              )
            """,
            [report_date, currency_basis],
        ).fetchone()
    except duckdb.Error as exc:
        raise AccountingAssetMovementSourceMissingError(
            "product_category_pnl_canonical_fact is required before "
            "materializing accounting asset movement."
        ) from exc

    if int(row[0] if row else 0) == 0:
        raise AccountingAssetMovementSourceMissingError(
            "No product-category control-account rows for "
            f"report_date={report_date}, currency_basis={currency_basis}."
        )


def _load_zqtz_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    currency_basis: str,
) -> list[ZqtzAccountingAssetBalance]:
    if str(currency_basis or "").strip().upper() == "CNX":
        return _load_zqtz_cnx_control_rows(
            conn,
            report_date=report_date,
            currency_basis=currency_basis,
        )
    return _load_zqtz_formal_rows(
        conn,
        report_date=report_date,
        currency_basis=currency_basis,
    )


def _load_zqtz_formal_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    currency_basis: str,
) -> list[ZqtzAccountingAssetBalance]:
    rows = conn.execute(
        """
        select
          cast(report_date as varchar),
          accounting_basis,
          position_scope,
          currency_basis,
          market_value_amount,
          amortized_cost_amount,
          source_version,
          rule_version
        from fact_formal_zqtz_balance_daily
        where cast(report_date as varchar) = ?
          and currency_basis = ?
          and position_scope = 'asset'
        """,
        [report_date, currency_basis],
    ).fetchall()
    return [
        ZqtzAccountingAssetBalance(
            report_date=date.fromisoformat(str(row[0])),
            accounting_basis=str(row[1]),
            position_scope=str(row[2]),
            currency_basis=str(row[3]),
            market_value_amount=Decimal(str(row[4] or "0")),
            amortized_cost_amount=Decimal(str(row[5] or "0")),
            source_version=str(row[6] or ""),
            rule_version=str(row[7] or ""),
        )
        for row in rows
    ]


def _load_zqtz_cnx_control_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    currency_basis: str,
) -> list[ZqtzAccountingAssetBalance]:
    rows = conn.execute(
        """
        with bucketed as (
          select
            case
              when account_code like '141%' then 'FVTPL'
              when account_code like '142%' or account_code like '143%' then 'AC'
              when account_code like '1440101%' then 'FVOCI'
            end as accounting_basis,
            coalesce(ending_balance, 0) as ending_balance,
            coalesce(source_version, '') as source_version,
            coalesce(rule_version, '') as rule_version
          from product_category_pnl_canonical_fact
          where cast(report_date as varchar) = ?
            and currency = ?
            and (
              account_code like '141%'
              or account_code like '142%'
              or account_code like '143%'
              or account_code like '1440101%'
            )
        )
        select
          accounting_basis,
          coalesce(sum(ending_balance), 0) as ending_balance,
          coalesce(string_agg(distinct nullif(source_version, ''), '__' order by nullif(source_version, '')), '') as source_version,
          coalesce(string_agg(distinct nullif(rule_version, ''), '__' order by nullif(rule_version, '')), '') as rule_version
        from bucketed
        where accounting_basis is not null
        group by accounting_basis
        order by accounting_basis
        """,
        [report_date, currency_basis],
    ).fetchall()
    parsed_report_date = date.fromisoformat(report_date)
    balances: list[ZqtzAccountingAssetBalance] = []
    for accounting_basis, ending_balance, source_version, rule_version in rows:
        amount = Decimal(str(ending_balance or "0"))
        normalized_basis = str(accounting_basis)
        balances.append(
            ZqtzAccountingAssetBalance(
                report_date=parsed_report_date,
                accounting_basis=normalized_basis,
                position_scope="asset",
                currency_basis=currency_basis,
                market_value_amount=Decimal("0") if normalized_basis == ACCOUNTING_BASIS_AC else amount,
                amortized_cost_amount=amount if normalized_basis == ACCOUNTING_BASIS_AC else Decimal("0"),
                source_version=str(source_version or ""),
                rule_version=str(rule_version or ""),
            )
        )
    return balances


def _load_gl_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    currency_basis: str,
) -> list[GlAccountingAssetBalance]:
    rows = conn.execute(
        """
        select
          cast(report_date as varchar),
          account_code,
          currency,
          beginning_balance,
          ending_balance,
          source_version,
          rule_version
        from product_category_pnl_canonical_fact
        where cast(report_date as varchar) = ?
          and currency = ?
          and (
            account_code like '141%'
            or account_code like '142%'
            or account_code like '143%'
            or account_code like '1440101%'
          )
        """,
        [report_date, currency_basis],
    ).fetchall()
    return [
        GlAccountingAssetBalance(
            report_date=date.fromisoformat(str(row[0])),
            account_code=str(row[1]),
            currency_basis=str(row[2]),
            beginning_balance=Decimal(str(row[3] or "0")),
            ending_balance=Decimal(str(row[4] or "0")),
            source_version=str(row[5] or ""),
            rule_version=str(row[6] or ""),
        )
        for row in rows
    ]

def _insert_rows(
    conn: duckdb.DuckDBPyConnection,
    rows: list[AccountingAssetMovementRow],
    *,
    currency_basis: str,
) -> None:
    for sort_order, row in enumerate(rows, start=1):
        conn.execute(
            """
            insert into fact_accounting_asset_movement_monthly values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                row.report_date.isoformat(),
                row.report_month,
                currency_basis,
                sort_order,
                row.basis_bucket,
                row.previous_balance,
                row.current_balance,
                row.balance_change,
                row.change_pct,
                row.contribution_pct,
                row.zqtz_amount,
                row.gl_amount,
                row.reconciliation_diff,
                row.reconciliation_status,
                row.source_version,
                row.rule_version or RULE_VERSION,
            ],
        )
