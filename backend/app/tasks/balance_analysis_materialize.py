from __future__ import annotations

from pathlib import Path

from backend.app.core_finance.balance_analysis import (
    project_tyw_formal_balance_row,
    project_zqtz_formal_balance_row,
)
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    CACHE_MANIFEST_STREAM,
    GovernanceRepository,
)
from backend.app.schemas.materialize import CacheBuildRunRecord, CacheManifestRecord
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.build_runs import BuildRunRecord

BALANCE_ANALYSIS_FORMAL_BASIS = "formal"
CACHE_KEY = f"balance_analysis:materialize:{BALANCE_ANALYSIS_FORMAL_BASIS}"
BALANCE_ANALYSIS_LOCK = LockDefinition(
    key=f"lock:duckdb:{BALANCE_ANALYSIS_FORMAL_BASIS}:balance-analysis:materialize",
    ttl_seconds=900,
)
RULE_VERSION = "rv_balance_analysis_formal_materialize_v1"
CACHE_VERSION = f"cv_balance_analysis_formal__{RULE_VERSION}"
_DIRECT_ZQTZ_INVEST_TYPE_LABELS = frozenset(
    {"持有至到期类资产", "可供出售类资产", "交易性资产", "应收投资款项", "发行类债劵", "发行类债券"}
)


def _materialize_balance_analysis_facts(
    *,
    report_date: str,
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
    run_id: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    duckdb_file = Path(duckdb_path or settings.duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    governance_path = Path(governance_dir or settings.governance_path)
    repo = BalanceAnalysisRepository(str(duckdb_file))
    governance_repo = GovernanceRepository(base_dir=governance_path)
    run = BuildRunRecord(job_name="balance_analysis_materialize", status="running")
    run_id = run_id or f"{run.job_name}:{run.created_at}"
    governance_repo.append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id=run_id,
                job_name=run.job_name,
                status="running",
                cache_key=CACHE_KEY,
                lock=BALANCE_ANALYSIS_LOCK.key,
                source_version="sv_balance_analysis_running",
                vendor_version="vv_none",
            ).model_dump(),
            "report_date": report_date,
            "started_at": run.created_at,
        },
    )

    zqtz_snapshot_rows = repo.load_zqtz_snapshot_rows(report_date)
    tyw_snapshot_rows = repo.load_tyw_snapshot_rows(report_date)

    zqtz_fact_rows = []
    tyw_fact_rows = []
    source_versions: set[str] = set()
    fx_source_versions: set[str] = set()

    for row in zqtz_snapshot_rows:
        position_scope = "liability" if row.is_issuance_like else "asset"
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
        fx_rate, fx_source_version = repo.lookup_fx_rate(
            report_date=report_date,
            base_currency=row.currency_code,
        )
        cny_row = project_zqtz_formal_balance_row(
            row,
            invest_type_raw=invest_type_raw,
            position_scope=position_scope,
            currency_basis="CNY",
            fx_rate=fx_rate,
        )
        if cny_row is not None:
            zqtz_fact_rows.append(cny_row)
            if cny_row.source_version:
                source_versions.add(cny_row.source_version)
        if fx_source_version and fx_source_version != "sv_fx_identity":
            fx_source_versions.add(fx_source_version)

    for row in tyw_snapshot_rows:
        position_scope = row.position_side if row.position_side in {"asset", "liability"} else "all"
        invest_type_raw = row.product_type or row.account_type
        native_row = project_tyw_formal_balance_row(
            row,
            invest_type_raw=invest_type_raw,
            position_scope=position_scope,
            currency_basis="native",
        )
        tyw_fact_rows.append(native_row)
        if native_row.source_version:
            source_versions.add(native_row.source_version)
        fx_rate, fx_source_version = repo.lookup_fx_rate(
            report_date=report_date,
            base_currency=row.currency_code,
        )
        cny_row = project_tyw_formal_balance_row(
            row,
            invest_type_raw=invest_type_raw,
            position_scope=position_scope,
            currency_basis="CNY",
            fx_rate=fx_rate,
        )
        tyw_fact_rows.append(cny_row)
        if cny_row.source_version:
            source_versions.add(cny_row.source_version)
        if fx_source_version and fx_source_version != "sv_fx_identity":
            fx_source_versions.add(fx_source_version)

    combined_source_version = "__".join(sorted(source_versions | fx_source_versions)) or "sv_balance_analysis_empty"

    try:
        with acquire_lock(BALANCE_ANALYSIS_LOCK, base_dir=duckdb_file.parent):
            repo.replace_formal_balance_rows(
                report_date=report_date,
                zqtz_rows=zqtz_fact_rows,
                tyw_rows=tyw_fact_rows,
            )
    except Exception as exc:
        failed = CacheBuildRunRecord(
            run_id=run_id,
            job_name=run.job_name,
            status="failed",
            cache_key=CACHE_KEY,
            lock=BALANCE_ANALYSIS_LOCK.key,
            source_version=combined_source_version,
            vendor_version="vv_none",
            rule_version=RULE_VERSION,
        ).model_dump()
        failed["report_date"] = report_date
        failed["error_message"] = str(exc)
        governance_repo.append(CACHE_BUILD_RUN_STREAM, failed)
        raise

    governance_repo.append_many_atomic(
        [
            (
                CACHE_MANIFEST_STREAM,
                CacheManifestRecord(
                    cache_key=CACHE_KEY,
                    source_version=combined_source_version,
                    vendor_version="vv_none",
                    rule_version=RULE_VERSION,
                ).model_dump(),
            ),
            (
                CACHE_BUILD_RUN_STREAM,
                {
                    **CacheBuildRunRecord(
                        run_id=run_id,
                        job_name=run.job_name,
                        status="completed",
                        cache_key=CACHE_KEY,
                        lock=BALANCE_ANALYSIS_LOCK.key,
                        source_version=combined_source_version,
                        vendor_version="vv_none",
                        rule_version=RULE_VERSION,
                    ).model_dump(),
                    "report_date": report_date,
                },
            ),
        ]
    )

    return {
        "status": "completed",
        "cache_key": CACHE_KEY,
        "cache_version": CACHE_VERSION,
        "run_id": run_id,
        "report_date": report_date,
        "zqtz_rows": len(zqtz_fact_rows),
        "tyw_rows": len(tyw_fact_rows),
        "source_version": combined_source_version,
        "rule_version": RULE_VERSION,
        "vendor_version": "vv_none",
        "lock": BALANCE_ANALYSIS_LOCK.key,
    }


materialize_balance_analysis_facts = register_actor_once(
    "materialize_balance_analysis_facts",
    _materialize_balance_analysis_facts,
)
