from __future__ import annotations

import hashlib
import os
import warnings
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import duckdb
from backend.app.core_finance.accounting_asset_movement import (
    DEFAULT_RELATIVE_TOLERANCE,
    DEFAULT_TOLERANCE,
    AccountingAssetMovementRow,
    ChainContinuityBreach,
    GlAccountingAssetBalance,
    ZqtzAccountingAssetBalance,
    apply_chain_continuity_status,
    build_accounting_asset_movement_rows,
    evaluate_chain_continuity,
)
from backend.app.core_finance.reconciliation_checks import (
    ReconciliationGateError,
    enforce_reconciliation_gate,
)
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

RULE_VERSION = "rv_accounting_asset_movement_v3"
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

POSITION_SOURCE_TABLE = "fact_formal_zqtz_balance_daily"
# 总账用 CNX（本外币折人民币）标记折算口径；ZQTZ 正式头寸表用 CNY 表示同一个
# 折算口径（外币持仓在 currency_basis='CNY' 行里已折人民币，'native' 行是原币）。
# 这个别名与 AccountingAssetMovementRepository 里既有的 CNX->CNY 映射一致。
POSITION_CURRENCY_BASIS_CANDIDATES: dict[str, tuple[str, ...]] = {
    "CNX": ("CNX", "CNY"),
}

CONTROL_GATE_ENV = "MOSS_MOVEMENT_CONTROL_GATE"
CONTROL_GATE_MODES = ("off", "warn", "enforce")
DEFAULT_CONTROL_GATE_MODE = "warn"


class AccountingAssetMovementSourceMissingError(RuntimeError):
    pass


class AccountingAssetMovementPositionSourceMissingError(
    AccountingAssetMovementSourceMissingError
):
    """独立头寸源在该报告日不可用（表缺失或该口径无行）。"""


class AccountingAssetMovementChainBrokenError(RuntimeError):
    """previous_balance(M) != current_balance(M-1)，拒绝落库。"""


class AccountingAssetMovementControlWarning(UserWarning):
    """落库前门禁在 warn 模式下检出的内控异常。"""


@dataclass(slots=True, frozen=True)
class PositionSourceResolution:
    """独立头寸源在某个报告日 / 折算口径下的可用性。"""

    table: str
    requested_currency_basis: str
    resolved_currency_basis: str | None
    row_count: int

    @property
    def available(self) -> bool:
        return self.resolved_currency_basis is not None and self.row_count > 0

    def as_lineage(self) -> dict[str, object]:
        return {
            "table": self.table,
            "requested_currency_basis": self.requested_currency_basis,
            "resolved_currency_basis": self.resolved_currency_basis,
            "row_count": self.row_count,
            "available": self.available,
        }


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
    control_reports: dict[str, dict[str, object]] = {}
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
                    # 落库后立刻按已写入的行取证。逐行结论现在落在
                    # chain_status / position_source_basis 列上，这里的汇总是
                    # 给 governance manifest lineage 留的批次级留痕。
                    control_reports[current_report_date] = _control_evidence(
                        conn,
                        report_date=current_report_date,
                        currency_basis=currency_basis,
                    )
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
                        "reconciliation_control": control_reports.get(current_report_date, {}),
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
        "reconciliation_control_by_date": control_reports,
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
    position_source = _resolve_position_source(
        conn,
        report_date=report_date,
        currency_basis=currency_basis,
    )
    _apply_position_source_gate(
        position_source,
        report_date=report_date,
    )
    zqtz_rows = _load_zqtz_rows(
        conn,
        report_date=report_date,
        position_source=position_source,
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
        position_source_available=position_source.available,
        position_source_basis=position_source.resolved_currency_basis,
    )
    # 勾稽判定与门禁模式无关：mode='off' 只表示"不拦截"，不表示"不判断"。结论
    # 要跟着行落库，页面才能把跨月断裂和横截面不平区分开。
    prior_report_date, prior_balances = _prior_bucket_balances(
        conn,
        report_date=report_date,
        currency_basis=currency_basis,
    )
    chain_breaches = evaluate_chain_continuity(
        rows=rows,
        prior_report_date=prior_report_date,
        prior_current_balances=prior_balances,
        tolerance=DEFAULT_TOLERANCE,
        relative_tolerance=DEFAULT_RELATIVE_TOLERANCE,
    )
    rows = apply_chain_continuity_status(
        rows,
        breaches=chain_breaches,
        prior_report_date=prior_report_date,
        prior_current_balances=prior_balances,
    )
    _apply_chain_continuity_gate(
        chain_breaches,
        report_date=report_date,
        currency_basis=currency_basis,
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


def _control_gate_mode() -> str:
    """off / warn / enforce。

    默认 warn：跨月勾稽在真实库里 90/90 全断、头寸源在 2024 全年缺失，
    默认 enforce 会让整条回补链路无法运行；warn 模式下断点仍然会写进
    governance manifest 的 lineage 并抛 Python warning，是可审计的检测型
    控制。生产上要把它升级成预防型控制，把该环境变量设成 enforce。
    """
    mode = str(os.environ.get(CONTROL_GATE_ENV, DEFAULT_CONTROL_GATE_MODE)).strip().lower()
    return mode if mode in CONTROL_GATE_MODES else DEFAULT_CONTROL_GATE_MODE


def _apply_position_source_gate(
    position_source: PositionSourceResolution,
    *,
    report_date: str,
) -> None:
    message = (
        "Independent position source is unavailable for "
        f"report_date={report_date}, currency_basis={position_source.requested_currency_basis}: "
        f"{position_source.table} has no asset rows for any of "
        f"{_position_currency_candidates(position_source.requested_currency_basis)}. "
        "Reconciliation cannot pass for this date; rows are written as gl_only."
    )
    check = {
        "dimension": "position_source_availability",
        "breached": not position_source.available,
        "missing_keys": [] if position_source.available else ["position"],
        **position_source.as_lineage(),
    }
    try:
        breaches = enforce_reconciliation_gate(
            check,
            context=f"accounting asset movement {report_date}",
            mode=_control_gate_mode(),
        )
    except ReconciliationGateError as exc:
        raise AccountingAssetMovementPositionSourceMissingError(message) from exc
    if breaches:
        warnings.warn(message, AccountingAssetMovementControlWarning, stacklevel=3)


def _apply_chain_continuity_gate(
    breaches: list[ChainContinuityBreach],
    *,
    report_date: str,
    currency_basis: str,
) -> None:
    mode = _control_gate_mode()
    if mode == "off" or not breaches:
        return
    message = _chain_breach_message(
        breaches,
        report_date=report_date,
        currency_basis=currency_basis,
    )
    try:
        enforce_reconciliation_gate(
            [
                {
                    "dimension": f"chain_continuity:{breach.basis_bucket}",
                    "breached": True,
                    "missing_keys": [],
                    "diff": float(breach.gap),
                }
                for breach in breaches
            ],
            context=f"accounting asset movement {report_date}",
            mode=mode,
        )
    except ReconciliationGateError as exc:
        raise AccountingAssetMovementChainBrokenError(message) from exc
    warnings.warn(message, AccountingAssetMovementControlWarning, stacklevel=3)


def _chain_breach_message(
    breaches: list[ChainContinuityBreach],
    *,
    report_date: str,
    currency_basis: str,
) -> str:
    details = "; ".join(
        (
            f"{breach.basis_bucket}: previous_balance={breach.reported_previous_balance} "
            f"vs {breach.prior_report_date} current_balance={breach.prior_current_balance} "
            f"(gap={breach.gap}, tolerance={breach.tolerance})"
        )
        for breach in breaches
    )
    return (
        "Month-over-month balance chain is broken for "
        f"report_date={report_date}, currency_basis={currency_basis}: {details}"
    )


def _control_evidence(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    currency_basis: str,
) -> dict[str, object]:
    """从已落库的行反读对账 / 勾稽结论，供 governance lineage 留痕。"""
    try:
        status_rows = conn.execute(
            """
            select
              reconciliation_status,
              count(*),
              coalesce(max(abs(reconciliation_diff)), 0)
            from fact_accounting_asset_movement_monthly
            where cast(report_date as varchar) = ?
              and currency_basis = ?
            group by 1
            order by 1
            """,
            [report_date, currency_basis],
        ).fetchall()
    except duckdb.Error:
        return {"gate_mode": _control_gate_mode(), "status": "unavailable"}

    prior_report_date, prior_balances = _prior_bucket_balances(
        conn,
        report_date=report_date,
        currency_basis=currency_basis,
    )
    persisted_rows = conn.execute(
        """
        select
          basis_bucket,
          coalesce(previous_balance, 0),
          chain_status,
          position_source_basis
        from fact_accounting_asset_movement_monthly
        where cast(report_date as varchar) = ?
          and currency_basis = ?
        """,
        [report_date, currency_basis],
    ).fetchall()
    chain_gaps = {
        str(bucket): str(Decimal(str(previous_balance or "0")) - prior_balances[str(bucket)])
        for bucket, previous_balance, _chain_status, _basis in persisted_rows
        if str(bucket) in prior_balances
    }
    chain_status_counts: dict[str, int] = {}
    for _bucket, _previous_balance, chain_status, _basis in persisted_rows:
        key = str(chain_status) if chain_status is not None else "unrecorded"
        chain_status_counts[key] = chain_status_counts.get(key, 0) + 1
    return {
        "gate_mode": _control_gate_mode(),
        "status_counts": {str(row[0]): int(row[1]) for row in status_rows},
        "unmatched_row_count": sum(
            int(row[1]) for row in status_rows if str(row[0]) != "matched"
        ),
        "max_abs_reconciliation_diff": str(
            max((Decimal(str(row[2] or "0")) for row in status_rows), default=Decimal("0"))
        ),
        "chain_prior_report_date": prior_report_date,
        "chain_gaps": chain_gaps,
        "chain_status_counts": dict(sorted(chain_status_counts.items())),
        "position_source_bases": sorted(
            {str(basis) for _b, _p, _c, basis in persisted_rows if basis is not None}
        ),
    }


def _prior_bucket_balances(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    currency_basis: str,
) -> tuple[str | None, dict[str, Decimal]]:
    """上一个已落库月份的 basis_bucket -> current_balance。"""
    try:
        rows = conn.execute(
            """
            with prior as (
              select max(cast(report_date as varchar)) as report_date
              from fact_accounting_asset_movement_monthly
              where currency_basis = ?
                and cast(report_date as varchar) < ?
            )
            select
              cast(fact.report_date as varchar),
              fact.basis_bucket,
              coalesce(fact.current_balance, 0)
            from fact_accounting_asset_movement_monthly as fact
            join prior on cast(fact.report_date as varchar) = prior.report_date
            where fact.currency_basis = ?
            """,
            [currency_basis, report_date, currency_basis],
        ).fetchall()
    except duckdb.Error:
        return None, {}
    if not rows:
        return None, {}
    return str(rows[0][0]), {
        str(bucket): Decimal(str(balance or "0"))
        for _, bucket, balance in rows
    }


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


def _position_currency_candidates(currency_basis: str) -> tuple[str, ...]:
    normalized = str(currency_basis or "").strip().upper()
    return POSITION_CURRENCY_BASIS_CANDIDATES.get(normalized, (currency_basis,))


def _resolve_position_source(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    currency_basis: str,
) -> PositionSourceResolution:
    """挑出该报告日实际有资产头寸行的 currency_basis。

    优先用与总账完全同名的口径（例如 ZQTZ 侧将来真的产出 'CNX' 行时自动切
    过去），否则退到既有的 CNX->CNY 折算口径别名。两者都没有行时返回
    available=False，而不是静默按 0 参与对账。
    """
    for candidate in _position_currency_candidates(currency_basis):
        try:
            row = conn.execute(
                f"""
                select count(*)
                from {POSITION_SOURCE_TABLE}
                where cast(report_date as varchar) = ?
                  and currency_basis = ?
                  and position_scope = 'asset'
                """,
                [report_date, candidate],
            ).fetchone()
        except duckdb.Error:
            return PositionSourceResolution(
                table=POSITION_SOURCE_TABLE,
                requested_currency_basis=currency_basis,
                resolved_currency_basis=None,
                row_count=0,
            )
        row_count = int(row[0] if row else 0)
        if row_count > 0:
            return PositionSourceResolution(
                table=POSITION_SOURCE_TABLE,
                requested_currency_basis=currency_basis,
                resolved_currency_basis=candidate,
                row_count=row_count,
            )
    return PositionSourceResolution(
        table=POSITION_SOURCE_TABLE,
        requested_currency_basis=currency_basis,
        resolved_currency_basis=None,
        row_count=0,
    )


def _load_zqtz_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    position_source: PositionSourceResolution,
) -> list[ZqtzAccountingAssetBalance]:
    if not position_source.available:
        return []
    return _load_zqtz_formal_rows(
        conn,
        report_date=report_date,
        currency_basis=str(position_source.resolved_currency_basis),
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
        # 显式列名而非位置插入：控制结论列是追加到表尾的（既有库走
        # alter table add column），位置插入会随列序变化静默错位。
        conn.execute(
            """
            insert into fact_accounting_asset_movement_monthly (
              report_date, report_month, currency_basis, sort_order, basis_bucket,
              previous_balance, current_balance, balance_change, change_pct,
              contribution_pct, zqtz_amount, gl_amount, reconciliation_diff,
              reconciliation_status, source_version, rule_version,
              chain_status, position_source_basis
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
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
                row.chain_status,
                row.position_source_basis,
            ],
        )
