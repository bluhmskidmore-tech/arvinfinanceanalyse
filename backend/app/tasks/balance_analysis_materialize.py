from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterable
from contextlib import nullcontext
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

import duckdb
from backend.app.core_finance.balance_analysis import (
    BalancePositionScope,
    FormalTywBalanceFactRow,
    FormalZqtzBalanceFactRow,
    TywSnapshotRow,
    ZqtzSnapshotRow,
    project_tyw_formal_balance_row,
    project_zqtz_formal_balance_row,
)
from backend.app.core_finance.module_contracts import FormalComputeModuleDescriptor
from backend.app.core_finance.module_registry import ensure_formal_module
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.repositories.source_manifest_repo import SourceManifestRepository
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.schemas.formal_compute_runtime import (
    FormalComputeMaterializeFailure,
    FormalComputeMaterializeResult,
)
from backend.app.tasks.balance_analysis_overview_publication import (
    schedule_balance_analysis_overview_publication,
)
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.formal_compute_runtime import run_formal_materialize
from backend.app.tasks.fx_mid_materialize import (
    CHINAMONEY_PAIR_BY_BASE_CURRENCY,
    materialize_fx_mid_for_report_date,
)

BALANCE_ANALYSIS_MODULE = ensure_formal_module(
    FormalComputeModuleDescriptor(
        module_name="balance_analysis",
        basis="formal",
        input_sources=(
            "zqtz_bond_daily_snapshot",
            "tyw_interbank_daily_snapshot",
            "fx_daily_mid",
        ),
        fact_tables=(
            "fact_formal_zqtz_balance_daily",
            "fact_formal_tyw_balance_daily",
        ),
        rule_version="rv_balance_analysis_formal_materialize_v1",
        result_kind_family="balance-analysis",
        supports_standard_queries=True,
        supports_custom_queries=True,
    )
)
BALANCE_ANALYSIS_FORMAL_BASIS = BALANCE_ANALYSIS_MODULE.basis
CACHE_KEY = BALANCE_ANALYSIS_MODULE.cache_key
BALANCE_ANALYSIS_LOCK = LockDefinition(
    key=BALANCE_ANALYSIS_MODULE.lock_key,
    ttl_seconds=BALANCE_ANALYSIS_MODULE.lock_ttl_seconds,
)
RULE_VERSION = BALANCE_ANALYSIS_MODULE.rule_version
CACHE_VERSION = BALANCE_ANALYSIS_MODULE.cache_version


def compose_balance_analysis_source_version(
    source_versions: Iterable[str],
    fx_source_versions: Iterable[str],
) -> str:
    return (
        "__".join(sorted(set(source_versions) | set(fx_source_versions)))
        or "sv_balance_analysis_empty"
    )


_DIRECT_ZQTZ_INVEST_TYPE_LABELS = frozenset(
    {"持有至到期类资产", "可供出售类资产", "交易性资产", "应收投资款项", "发行类债劵", "发行类债券"}
)
# snapshot↔fact native 本金合计差异容差（单位：元）。
TYW_SNAPSHOT_FACT_PRINCIPAL_TOLERANCE = Decimal("0.01")
_DIRECT_SNAPSHOT_GUARD_REPORT_DATE = "2026-08-31"
_DIRECT_SNAPSHOT_GUARD_RULE_VERSION = "rv_snapshot_zqtz_tyw_v3"

logger = logging.getLogger(__name__)


def _tyw_consistency_entry(row: dict[str, Any], *, tolerance: Decimal) -> dict[str, object]:
    diff: Decimal = row["principal_native_diff"]
    status = "drift" if abs(diff) > tolerance else "consistent"
    return {
        "report_date": str(row["report_date"]),
        "status": status,
        "snapshot_row_count": int(row["snapshot_row_count"]),
        "fact_native_row_count": int(row["fact_native_row_count"]),
        "snapshot_principal_native_total": str(row["snapshot_principal_native_total"]),
        "fact_principal_native_total": str(row["fact_principal_native_total"]),
        "principal_native_diff": str(diff),
        "tolerance": str(tolerance),
    }


def check_tyw_snapshot_fact_consistency(
    *,
    duckdb_path: str | None = None,
    report_dates: list[str] | None = None,
    tolerance: Decimal = TYW_SNAPSHOT_FACT_PRINCIPAL_TOLERANCE,
) -> list[dict[str, object]]:
    """批量核对 TYW snapshot 与 formal fact 的 native 本金合计（只读，不改数据）。

    ``report_dates`` 为 None 时覆盖两侧出现过的全部报告日；用于对历史漂移
    （snapshot↔fact 不一致的报告日）出报告，哪一侧为准由数据 owner 裁决。
    """
    resolved_path = str(duckdb_path) if duckdb_path else str(get_settings().duckdb_path)
    repo = BalanceAnalysisRepository(resolved_path)
    rows = repo.fetch_tyw_snapshot_fact_native_consistency_rows(report_dates=report_dates)
    return [_tyw_consistency_entry(row, tolerance=tolerance) for row in rows]


def _verify_tyw_snapshot_fact_consistency_after_write(
    *,
    repo: BalanceAnalysisRepository,
    report_date: str,
    snapshot_ingest_batch_id: str | None,
) -> dict[str, object]:
    """物化写入后的只读一致性校验；校验自身失败不回滚、不中断任务。"""
    try:
        rows = repo.fetch_tyw_snapshot_fact_native_consistency_rows(
            report_dates=[report_date],
            snapshot_ingest_batch_id=snapshot_ingest_batch_id,
        )
    except (OSError, duckdb.Error) as exc:
        logger.warning(
            "TYW snapshot/fact consistency check failed to run for report_date=%s: %s",
            report_date,
            exc,
        )
        return {"report_date": report_date, "status": "check_failed", "error": str(exc)}
    entry = _tyw_consistency_entry(rows[0], tolerance=TYW_SNAPSHOT_FACT_PRINCIPAL_TOLERANCE)
    if entry["status"] == "drift":
        logger.warning(
            "TYW snapshot/fact native principal drift detected: report_date=%s "
            "snapshot_total=%s fact_total=%s diff=%s tolerance=%s "
            "(snapshot_rows=%s, fact_native_rows=%s); data owner adjudication required, "
            "no automatic re-materialization performed.",
            entry["report_date"],
            entry["snapshot_principal_native_total"],
            entry["fact_principal_native_total"],
            entry["principal_native_diff"],
            entry["tolerance"],
            entry["snapshot_row_count"],
            entry["fact_native_row_count"],
        )
    return entry


def _resolve_snapshot_ingest_batch_id(
    *,
    family: str,
    report_date: str,
    requested_ingest_batch_id: str | None,
    governance_dir: str,
    repo: BalanceAnalysisRepository,
) -> str | None:
    if family == "zqtz":
        count_rows_for_batch = repo.count_zqtz_snapshot_rows
        list_batch_ids = repo.list_zqtz_snapshot_ingest_batch_ids
        count_rows_for_report_date = repo.count_zqtz_snapshot_rows
    else:
        count_rows_for_batch = repo.count_tyw_snapshot_rows
        list_batch_ids = repo.list_tyw_snapshot_ingest_batch_ids
        count_rows_for_report_date = repo.count_tyw_snapshot_rows

    manifest_repo = SourceManifestRepository(
        governance_repo=GovernanceRepository(base_dir=Path(governance_dir)),
    )

    if requested_ingest_batch_id:
        requested_row_count = count_rows_for_batch(
            report_date,
            ingest_batch_id=requested_ingest_batch_id,
        )
        if requested_row_count <= 0:
            manifest_rows = manifest_repo.select_for_snapshot_materialization(
                source_families=[family],
                report_date=report_date,
                ingest_batch_id=requested_ingest_batch_id,
            )
            if manifest_rows:
                raise ValueError(
                    f"Explicit ingest_batch_id={requested_ingest_batch_id} for family={family} report_date={report_date} has no materialized snapshot rows."
                )
            return None
        return requested_ingest_batch_id

    manifest_rows = manifest_repo.select_for_snapshot_materialization(
        source_families=[family],
        report_date=report_date,
    )
    manifest_batch_ids = sorted(
        {
            str(row.get("ingest_batch_id") or "").strip()
            for row in manifest_rows
            if str(row.get("ingest_batch_id") or "").strip()
        }
    )
    if len(manifest_batch_ids) == 1:
        manifest_batch_id = manifest_batch_ids[0]
        if family == "zqtz":
            manifest_snapshot_row_count = repo.count_zqtz_snapshot_rows(
                report_date,
                ingest_batch_id=manifest_batch_id,
            )
        else:
            manifest_snapshot_row_count = repo.count_tyw_snapshot_rows(
                report_date,
                ingest_batch_id=manifest_batch_id,
            )
        if manifest_snapshot_row_count <= 0:
            raise ValueError(
                f"Manifest-selected ingest_batch_id={manifest_batch_id} for family={family} report_date={report_date} has no materialized snapshot rows."
            )
        return manifest_batch_id
    if len(manifest_batch_ids) > 1:
        raise ValueError(
            f"Multiple manifest ingest_batch_id values found for family={family} report_date={report_date}."
        )

    snapshot_batch_ids = list_batch_ids(report_date)
    snapshot_row_count = count_rows_for_report_date(report_date)

    if len(snapshot_batch_ids) == 1:
        return snapshot_batch_ids[0]
    if len(snapshot_batch_ids) > 1:
        raise ValueError(
            f"Multiple snapshot ingest_batch_id values found for family={family} report_date={report_date}; explicit ingest_batch_id required."
        )
    if snapshot_row_count > 0:
        raise ValueError(
            f"Snapshot rows for family={family} report_date={report_date} are missing governed ingest_batch_id lineage."
        )
    return None


def _load_direct_aug31_snapshot_rows(
    *,
    duckdb_file: Path,
    governance_path: Path,
    requested_ingest_batch_id: str | None,
) -> tuple[
    BalanceAnalysisRepository,
    str,
    str,
    list[ZqtzSnapshotRow],
    list[TywSnapshotRow],
]:
    report_date = _DIRECT_SNAPSHOT_GUARD_REPORT_DATE
    repo = BalanceAnalysisRepository(str(duckdb_file))
    manifest_repo = SourceManifestRepository(
        governance_repo=GovernanceRepository(base_dir=governance_path),
    )
    selected: dict[str, tuple[str, list[ZqtzSnapshotRow] | list[TywSnapshotRow]]] = {}
    for family, load_rows in (
        ("zqtz", repo.load_zqtz_snapshot_rows),
        ("tyw", repo.load_tyw_snapshot_rows),
    ):
        batch_id = _resolve_snapshot_ingest_batch_id(
            family=family,
            report_date=report_date,
            requested_ingest_batch_id=requested_ingest_batch_id,
            governance_dir=str(governance_path),
            repo=repo,
        )
        if not batch_id:
            raise ValueError(f"{report_date} {family} requires direct v3 snapshot lineage.")
        manifest_rows = manifest_repo.select_for_snapshot_materialization(
            source_families=[family],
            report_date=report_date,
            ingest_batch_id=batch_id,
        )
        rows = load_rows(report_date, ingest_batch_id=batch_id)
        manifest_source_versions = {
            str(manifest.get("source_version") or "").strip()
            for manifest in manifest_rows
        }
        snapshot_source_versions = {row.source_version for row in rows}
        if (
            not manifest_rows
            or not rows
            or "" in manifest_source_versions
            or snapshot_source_versions != manifest_source_versions
            or any(
                row.rule_version != _DIRECT_SNAPSHOT_GUARD_RULE_VERSION
                or not row.source_version
                or row.ingest_batch_id != batch_id
                for row in rows
            )
            or (
                family == "tyw"
                and (
                    batch_id.startswith("locf:")
                    or any(
                        row.source_version.startswith("sv_tyw_locf_")
                        or row.trace_id.startswith("locf:")
                        for row in rows
                    )
                )
            )
        ):
            raise ValueError(
                f"{report_date} {family} selected manifest/batch requires direct v3 snapshot rows."
            )
        selected[family] = batch_id, rows
    zqtz_batch, zqtz_rows = selected["zqtz"]
    tyw_batch, tyw_rows = selected["tyw"]
    # Each fixed family above is paired with its corresponding repository loader.
    return repo, zqtz_batch, tyw_batch, cast(list[ZqtzSnapshotRow], zqtz_rows), cast(list[TywSnapshotRow], tyw_rows)


def _require_direct_aug31_completed_facts(
    *,
    repo: BalanceAnalysisRepository,
    zqtz_snapshots: list[ZqtzSnapshotRow],
    tyw_snapshots: list[TywSnapshotRow],
) -> None:
    report_date = _DIRECT_SNAPSHOT_GUARD_REPORT_DATE
    zqtz_fields = (
        "instrument_code", "portfolio_name", "cost_center", "currency_basis",
        "position_scope", "accounting_basis", "maturity_date", "source_version",
        "rule_version", "ingest_batch_id", "trace_id",
    )
    tyw_fields = (
        "position_id", "currency_basis", "position_scope", "source_version",
        "rule_version", "ingest_batch_id", "trace_id",
    )

    def cohort_value(field: str, value: object) -> object:
        return str(value) if field == "maturity_date" and value is not None else value

    for currency_basis in ("native", "CNY"):
        expected_zqtz: Counter[tuple[object, ...]] = Counter()
        for row in zqtz_snapshots:
            position_scope: BalancePositionScope = "liability" if row.is_issuance_like else "asset"
            invest_type_raw = (
                row.asset_class
                if row.asset_class in _DIRECT_ZQTZ_INVEST_TYPE_LABELS
                else (row.account_category or row.asset_class)
            )
            projected = project_zqtz_formal_balance_row(
                row,
                invest_type_raw=invest_type_raw,
                position_scope=position_scope,
                currency_basis=currency_basis,
                fx_rate=Decimal("1"),
            )
            if projected is not None:
                expected_zqtz[
                    tuple(cohort_value(field, getattr(projected, field)) for field in zqtz_fields)
                ] += 1

        expected_tyw: Counter[tuple[object, ...]] = Counter()
        for tyw_row in tyw_snapshots:
            if tyw_row.position_side == "asset":
                position_scope = "asset"
            elif tyw_row.position_side == "liability":
                position_scope = "liability"
            else:
                position_scope = "all"
            projected_tyw = project_tyw_formal_balance_row(
                tyw_row,
                invest_type_raw=tyw_row.product_type or tyw_row.account_type,
                position_scope=position_scope,
                currency_basis=currency_basis,
                fx_rate=Decimal("1"),
            )
            expected_tyw[tuple(getattr(projected_tyw, field) for field in tyw_fields)] += 1

        for family, expected, fields, fact_rows in (
            (
                "zqtz", expected_zqtz, zqtz_fields,
                repo.fetch_formal_zqtz_rows(report_date=report_date, currency_basis=currency_basis),
            ),
            (
                "tyw", expected_tyw, tyw_fields,
                repo.fetch_formal_tyw_rows(report_date=report_date, currency_basis=currency_basis),
            ),
        ):
            actual = Counter(
                tuple(cohort_value(field, row[field]) for field in fields)
                for row in fact_rows
            )
            if not expected or actual != expected:
                raise RuntimeError(
                    f"{report_date} {family} completed facts do not cover the selected snapshot cohort."
                )


def _execute_balance_analysis_materialization(
    *,
    report_date: str,
    duckdb_file: Path,
    ingest_batch_id: str | None = None,
    governance_dir: str,
    data_root: str | None = None,
    fx_source_path: str | None = None,
    use_existing_fx_only: bool = False,
    expected_fx_source_version: str | None = None,
) -> FormalComputeMaterializeResult:
    settings = get_settings()
    if expected_fx_source_version is not None and not use_existing_fx_only:
        raise ValueError(
            "expected_fx_source_version requires use_existing_fx_only=True."
        )
    guarded_snapshots = (
        _load_direct_aug31_snapshot_rows(
            duckdb_file=duckdb_file,
            governance_path=Path(governance_dir),
            requested_ingest_batch_id=ingest_batch_id,
        )
        if report_date == _DIRECT_SNAPSHOT_GUARD_REPORT_DATE
        else None
    )
    if not use_existing_fx_only:
        materialize_fx_mid_for_report_date.fn(
            report_date=report_date,
            duckdb_path=str(duckdb_file),
            data_input_root=str(data_root or settings.data_input_root),
            official_csv_path=str(
                fx_source_path
                or getattr(settings, "fx_official_source_path", "")
                or ""
            ),
            explicit_csv_path=str(getattr(settings, "fx_mid_csv_path", "") or ""),
            writer_lock_already_held=True,
        )

    zqtz_ingest_batch_id: str | None
    tyw_ingest_batch_id: str | None
    if guarded_snapshots is not None:
        (
            repo,
            zqtz_ingest_batch_id,
            tyw_ingest_batch_id,
            zqtz_snapshot_rows,
            tyw_snapshot_rows,
        ) = guarded_snapshots
    else:
        repo = BalanceAnalysisRepository(str(duckdb_file))
        zqtz_ingest_batch_id = _resolve_snapshot_ingest_batch_id(
            family="zqtz",
            report_date=report_date,
            requested_ingest_batch_id=ingest_batch_id,
            governance_dir=governance_dir,
            repo=repo,
        )
        tyw_ingest_batch_id = _resolve_snapshot_ingest_batch_id(
            family="tyw",
            report_date=report_date,
            requested_ingest_batch_id=ingest_batch_id,
            governance_dir=governance_dir,
            repo=repo,
        )
        zqtz_snapshot_rows = repo.load_zqtz_snapshot_rows(
            report_date,
            ingest_batch_id=zqtz_ingest_batch_id,
        )
        tyw_snapshot_rows = repo.load_tyw_snapshot_rows(
            report_date,
            ingest_batch_id=tyw_ingest_batch_id,
        )
    if expected_fx_source_version is not None:
        required_base_currencies = {
            row.currency_code for row in zqtz_snapshot_rows
        } | {row.currency_code for row in tyw_snapshot_rows}
        repo.validate_existing_formal_fx_snapshot(
            report_date=report_date,
            required_base_currencies=required_base_currencies,
            canonical_base_currencies=set(CHINAMONEY_PAIR_BY_BASE_CURRENCY),
            expected_source_version=expected_fx_source_version,
        )

    zqtz_fact_rows: list[FormalZqtzBalanceFactRow] = []
    tyw_fact_rows: list[FormalTywBalanceFactRow] = []
    source_versions: set[str] = set()
    fx_source_versions: set[str] = set()

    for row in zqtz_snapshot_rows:
        position_scope: BalancePositionScope = "liability" if row.is_issuance_like else "asset"
        invest_type_raw = (
            row.asset_class
            if row.asset_class in _DIRECT_ZQTZ_INVEST_TYPE_LABELS
            else (row.account_category or row.asset_class)
        )
        native_row = project_zqtz_formal_balance_row(
            row,
            invest_type_raw=invest_type_raw,
            position_scope=position_scope,
            currency_basis="native",
        )
        if native_row is not None:
            zqtz_fact_rows.append(native_row)
            if native_row.source_version:
                source_versions.add(native_row.source_version)
        fx_lookup = repo.lookup_formal_fx_rate(
            report_date=report_date,
            base_currency=row.currency_code,
        )
        cny_row = project_zqtz_formal_balance_row(
            row,
            invest_type_raw=invest_type_raw,
            position_scope=position_scope,
            currency_basis="CNY",
            fx_rate=fx_lookup.rate,
        )
        if cny_row is not None:
            zqtz_fact_rows.append(cny_row)
            if cny_row.source_version:
                source_versions.add(cny_row.source_version)
        if fx_lookup.source_version and fx_lookup.source_version != "sv_fx_identity":
            fx_source_versions.add(fx_lookup.source_version)

    for tyw_row in tyw_snapshot_rows:
        # Equivalent to: position_side if position_side in {"asset", "liability"} else "all".
        if tyw_row.position_side == "asset":
            position_scope = "asset"
        elif tyw_row.position_side == "liability":
            position_scope = "liability"
        else:
            position_scope = "all"
        invest_type_raw = tyw_row.product_type or tyw_row.account_type
        tyw_native_row = project_tyw_formal_balance_row(
            tyw_row,
            invest_type_raw=invest_type_raw,
            position_scope=position_scope,
            currency_basis="native",
        )
        tyw_fact_rows.append(tyw_native_row)
        if tyw_native_row.source_version:
            source_versions.add(tyw_native_row.source_version)
        fx_lookup = repo.lookup_formal_fx_rate(
            report_date=report_date,
            base_currency=tyw_row.currency_code,
        )
        tyw_cny_row = project_tyw_formal_balance_row(
            tyw_row,
            invest_type_raw=invest_type_raw,
            position_scope=position_scope,
            currency_basis="CNY",
            fx_rate=fx_lookup.rate,
        )
        tyw_fact_rows.append(tyw_cny_row)
        if tyw_cny_row.source_version:
            source_versions.add(tyw_cny_row.source_version)
        if fx_lookup.source_version and fx_lookup.source_version != "sv_fx_identity":
            fx_source_versions.add(fx_lookup.source_version)

    combined_source_version = compose_balance_analysis_source_version(
        source_versions,
        fx_source_versions,
    )
    try:
        with repository_task_write_scope(__name__):
            repo.replace_formal_balance_rows(
                report_date=report_date,
                zqtz_rows=zqtz_fact_rows,
                tyw_rows=tyw_fact_rows,
                writer_lock_already_held=True,
            )
    except Exception as exc:
        raise FormalComputeMaterializeFailure(
            source_version=combined_source_version,
            vendor_version="vv_none",
            message=str(exc),
        ) from exc
    tyw_consistency = _verify_tyw_snapshot_fact_consistency_after_write(
        repo=repo,
        report_date=report_date,
        snapshot_ingest_batch_id=tyw_ingest_batch_id,
    )
    return FormalComputeMaterializeResult(
        source_version=combined_source_version,
        vendor_version="vv_none",
        payload={
            "zqtz_rows": len(zqtz_fact_rows),
            "tyw_rows": len(tyw_fact_rows),
            "tyw_snapshot_fact_consistency": tyw_consistency,
        },
    )


def _materialize_balance_analysis_facts(
    *,
    report_date: str,
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
    run_id: str | None = None,
    ingest_batch_id: str | None = None,
    data_root: str | None = None,
    fx_source_path: str | None = None,
    use_existing_fx_only: bool = False,
    expected_fx_source_version: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    duckdb_file = Path(duckdb_path or settings.duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    governance_path = Path(governance_dir or settings.governance_path)
    normalized_run_id = str(run_id or "").strip() or None
    run_lock = (
        LockDefinition(
            key=(
                "balance_analysis_materialize_run_"
                + sha256(normalized_run_id.encode("utf-8")).hexdigest()[:24]
            ),
            ttl_seconds=BALANCE_ANALYSIS_MODULE.lock_ttl_seconds,
        )
        if normalized_run_id is not None
        else None
    )
    lock_context = (
        acquire_lock(run_lock, base_dir=duckdb_file.parent)
        if run_lock is not None
        else nullcontext()
    )
    with lock_context:
        return _run_or_resume_balance_analysis_materialization(
            settings=settings,
            report_date=report_date,
            duckdb_file=duckdb_file,
            governance_path=governance_path,
            run_id=normalized_run_id,
            ingest_batch_id=ingest_batch_id,
            data_root=data_root,
            fx_source_path=fx_source_path,
            use_existing_fx_only=use_existing_fx_only,
            expected_fx_source_version=expected_fx_source_version,
        )


def _run_or_resume_balance_analysis_materialization(
    *,
    settings: Any,
    report_date: str,
    duckdb_file: Path,
    governance_path: Path,
    run_id: str | None,
    ingest_batch_id: str | None,
    data_root: str | None,
    fx_source_path: str | None,
    use_existing_fx_only: bool,
    expected_fx_source_version: str | None,
) -> dict[str, object]:
    governance = GovernanceRepository(base_dir=governance_path)
    identity = _materialize_run_identity(
        settings=settings,
        report_date=report_date,
        duckdb_file=duckdb_file,
        governance_path=governance_path,
        run_id=run_id,
        ingest_batch_id=ingest_batch_id,
        data_root=data_root,
        fx_source_path=fx_source_path,
        use_existing_fx_only=use_existing_fx_only,
        expected_fx_source_version=expected_fx_source_version,
    )
    if run_id is not None:
        completed, latest = _completed_materialize_runs(
            governance,
            report_date=report_date,
            run_id=run_id,
        )
        recorded_identity = _recorded_materialize_run_identity(
            governance,
            run_id=run_id,
        )
        if (
            report_date == _DIRECT_SNAPSHOT_GUARD_REPORT_DATE
            and completed is not None
            and recorded_identity is None
        ):
            raise RuntimeError(
                "2026-08-31 completed run has no snapshot rule guard identity; use a new run_id."
            )
        if completed is not None and recorded_identity is not None:
            if recorded_identity != identity:
                if report_date == _DIRECT_SNAPSHOT_GUARD_REPORT_DATE and (
                    recorded_identity.get("snapshot_rule_version_guard")
                    != _DIRECT_SNAPSHOT_GUARD_RULE_VERSION
                ):
                    raise RuntimeError(
                        "2026-08-31 completed run predates the snapshot rule guard; use a new run_id."
                    )
                raise RuntimeError(
                    "Completed balance-analysis materialize run was replayed with a different identity."
                )
            if report_date == _DIRECT_SNAPSHOT_GUARD_REPORT_DATE:
                repo, _, _, zqtz_rows, tyw_rows = _load_direct_aug31_snapshot_rows(
                    duckdb_file=duckdb_file,
                    governance_path=governance_path,
                    requested_ingest_batch_id=ingest_batch_id,
                )
                _require_direct_aug31_completed_facts(
                    repo=repo,
                    zqtz_snapshots=zqtz_rows,
                    tyw_snapshots=tyw_rows,
                )
            payload = _completed_materialize_payload(completed)
            payload["idempotent_replay"] = True
            latest_run_id = str(latest.get("run_id") or "") if latest is not None else ""
            if latest_run_id != run_id:
                payload["overview_publication_dispatch"] = {
                    "status": "superseded",
                    "source_build_run_id": run_id,
                    "latest_source_build_run_id": latest_run_id or None,
                }
                return payload
            _dispatch_balance_overview_publication(
                payload,
                settings=settings,
                report_date=report_date,
                duckdb_file=duckdb_file,
                governance_path=governance_path,
            )
            return payload
        governance.append(CACHE_BUILD_RUN_STREAM, identity)

    payload = run_formal_materialize(
        descriptor=BALANCE_ANALYSIS_MODULE,
        job_name="balance_analysis_materialize",
        report_date=report_date,
        governance_dir=str(governance_path),
        lock_base_dir=str(duckdb_file.parent),
        duckdb_path=str(duckdb_file),
        run_id=run_id,
        execute_materialization=lambda: _execute_balance_analysis_materialization(
            report_date=report_date,
            duckdb_file=duckdb_file,
            ingest_batch_id=ingest_batch_id,
            governance_dir=str(governance_path),
            data_root=data_root,
            fx_source_path=fx_source_path,
            use_existing_fx_only=use_existing_fx_only,
            expected_fx_source_version=expected_fx_source_version,
        ),
    )
    if run_id is None and report_date == _DIRECT_SNAPSHOT_GUARD_REPORT_DATE:
        governance.append(
            CACHE_BUILD_RUN_STREAM,
            {**identity, "run_id": str(payload["run_id"])},
        )
    _dispatch_balance_overview_publication(
        payload,
        settings=settings,
        report_date=report_date,
        duckdb_file=duckdb_file,
        governance_path=governance_path,
    )
    return payload


def _dispatch_balance_overview_publication(
    payload: dict[str, object],
    *,
    settings: Any,
    report_date: str,
    duckdb_file: Path,
    governance_path: Path,
) -> None:
    if (
        settings.balance_analysis_publication_enabled
        and duckdb_file.resolve() == Path(settings.duckdb_path).resolve()
        and governance_path.resolve() == Path(settings.governance_path).resolve()
    ):
        payload["overview_publication_dispatch"] = (
            schedule_balance_analysis_overview_publication(
                settings,
                report_date=report_date,
                source_build_run_id=str(payload["run_id"]),
                duckdb_path=duckdb_file,
                governance_dir=governance_path,
            )
        )


def _materialize_run_identity(
    *,
    settings: Any,
    report_date: str,
    duckdb_file: Path,
    governance_path: Path,
    run_id: str | None,
    ingest_batch_id: str | None,
    data_root: str | None,
    fx_source_path: str | None,
    use_existing_fx_only: bool,
    expected_fx_source_version: str | None,
) -> dict[str, object]:
    effective_data_root = Path(data_root or settings.data_input_root).resolve()
    effective_fx_source = str(
        fx_source_path or getattr(settings, "fx_official_source_path", "") or ""
    ).strip()
    explicit_fx_source = str(getattr(settings, "fx_mid_csv_path", "") or "").strip()
    return {
        "status": "running",
        "phase": "materialize_run_identity",
        "job_name": "balance_analysis_materialize",
        "cache_key": CACHE_KEY,
        "run_id": run_id,
        "report_date": report_date,
        "duckdb_path": str(duckdb_file.resolve()),
        "governance_path": str(governance_path.resolve()),
        "ingest_batch_id": str(ingest_batch_id) if ingest_batch_id is not None else None,
        "data_root": str(effective_data_root),
        "fx_source_path": (
            str(Path(effective_fx_source).resolve()) if effective_fx_source else None
        ),
        "explicit_fx_source_path": (
            str(Path(explicit_fx_source).resolve()) if explicit_fx_source else None
        ),
        "use_existing_fx_only": bool(use_existing_fx_only),
        "expected_fx_source_version": expected_fx_source_version,
        **(
            {"snapshot_rule_version_guard": _DIRECT_SNAPSHOT_GUARD_RULE_VERSION}
            if report_date == _DIRECT_SNAPSHOT_GUARD_REPORT_DATE
            else {}
        ),
    }


def _recorded_materialize_run_identity(
    governance: GovernanceRepository,
    *,
    run_id: str,
) -> dict[str, object] | None:
    for row in reversed(governance.read_all(CACHE_BUILD_RUN_STREAM)):
        if (
            row.get("phase") == "materialize_run_identity"
            and str(row.get("run_id") or "") == run_id
        ):
            keys: tuple[str, ...] = (
                "status",
                "phase",
                "job_name",
                "cache_key",
                "run_id",
                "report_date",
                "duckdb_path",
                "governance_path",
                "ingest_batch_id",
                "data_root",
                "fx_source_path",
                "explicit_fx_source_path",
                "use_existing_fx_only",
                "expected_fx_source_version",
            )
            if str(row.get("report_date") or "") == _DIRECT_SNAPSHOT_GUARD_REPORT_DATE:
                keys += ("snapshot_rule_version_guard",)
            return {key: row.get(key) for key in keys}
    return None


def _completed_materialize_runs(
    governance: GovernanceRepository,
    *,
    report_date: str,
    run_id: str,
) -> tuple[dict[str, object] | None, dict[str, object] | None]:
    completed = [
        row
        for row in governance.read_all(CACHE_BUILD_RUN_STREAM)
        if row.get("status") == "completed"
        and str(row.get("job_name") or "") == "balance_analysis_materialize"
        and str(row.get("cache_key") or "") == CACHE_KEY
        and str(row.get("report_date") or "") == report_date
    ]
    exact = next(
        (row for row in reversed(completed) if str(row.get("run_id") or "") == run_id),
        None,
    )
    latest = completed[-1] if completed else None
    return exact, latest


def _completed_materialize_payload(row: dict[str, object]) -> dict[str, object]:
    return {
        "status": "completed",
        "cache_key": CACHE_KEY,
        "cache_version": row.get("cache_version"),
        "run_id": str(row.get("run_id") or ""),
        "report_date": str(row.get("report_date") or ""),
        "source_version": row.get("source_version"),
        "rule_version": row.get("rule_version"),
        "vendor_version": row.get("vendor_version"),
        "lock": row.get("lock"),
    }


materialize_balance_analysis_facts = register_actor_once(
    "materialize_balance_analysis_facts",
    _materialize_balance_analysis_facts,
)
