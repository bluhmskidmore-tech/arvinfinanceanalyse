from __future__ import annotations

from pathlib import Path

from backend.app.core_finance.balance_analysis import (
    project_tyw_formal_balance_row,
    project_zqtz_formal_balance_row,
)
from backend.app.core_finance.module_contracts import FormalComputeModuleDescriptor
from backend.app.core_finance.module_registry import ensure_formal_module
from backend.app.governance.settings import get_settings
from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository
from backend.app.schemas.formal_compute_runtime import (
    FormalComputeMaterializeFailure,
    FormalComputeMaterializeResult,
)
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.fx_mid_materialize import materialize_fx_mid_rows, resolve_fx_mid_csv_path
from backend.app.tasks.formal_compute_runtime import run_formal_materialize

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
        cache_key_prefix="balance_analysis:materialize",
        lock_key_prefix="lock:duckdb:{basis}:balance-analysis:materialize",
        cache_version_prefix="cv_balance_analysis",
        result_kind_family="balance-analysis",
        supports_standard_queries=True,
        supports_custom_queries=True,
    )
)
BALANCE_ANALYSIS_FORMAL_BASIS = BALANCE_ANALYSIS_MODULE.basis
CACHE_KEY = BALANCE_ANALYSIS_MODULE.cache_key
BALANCE_ANALYSIS_LOCK = BALANCE_ANALYSIS_MODULE.lock_definition
RULE_VERSION = BALANCE_ANALYSIS_MODULE.rule_version
CACHE_VERSION = BALANCE_ANALYSIS_MODULE.cache_version
_DIRECT_ZQTZ_INVEST_TYPE_LABELS = frozenset(
    {"持有至到期类资产", "可供出售类资产", "交易性资产", "应收投资款项", "发行类债劵", "发行类债券"}
)


def _execute_balance_analysis_materialization(
    *,
    report_date: str,
    duckdb_file: Path,
    data_root: str | None = None,
    fx_source_path: str | None = None,
) -> FormalComputeMaterializeResult:
    settings = get_settings()
    fx_mid_csv_path = resolve_fx_mid_csv_path(
        official_csv_path=str(
            fx_source_path
            or getattr(settings, "fx_official_source_path", "")
            or ""
        ),
        explicit_csv_path=str(getattr(settings, "fx_mid_csv_path", "") or ""),
        data_input_root=Path(data_root or settings.data_input_root),
    )
    if fx_mid_csv_path is not None:
        materialize_fx_mid_rows.fn(
            csv_path=str(fx_mid_csv_path),
            duckdb_path=str(duckdb_file),
        )

    repo = BalanceAnalysisRepository(str(duckdb_file))
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
        repo.replace_formal_balance_rows(
            report_date=report_date,
            zqtz_rows=zqtz_fact_rows,
            tyw_rows=tyw_fact_rows,
        )
    except Exception as exc:
        raise FormalComputeMaterializeFailure(
            source_version=combined_source_version,
            vendor_version="vv_none",
            message=str(exc),
        ) from exc
    return FormalComputeMaterializeResult(
        source_version=combined_source_version,
        vendor_version="vv_none",
        payload={
            "zqtz_rows": len(zqtz_fact_rows),
            "tyw_rows": len(tyw_fact_rows),
        },
    )


def _materialize_balance_analysis_facts(
    *,
    report_date: str,
    duckdb_path: str | None = None,
    governance_dir: str | None = None,
    run_id: str | None = None,
    data_root: str | None = None,
    fx_source_path: str | None = None,
) -> dict[str, object]:
    settings = get_settings()
    duckdb_file = Path(duckdb_path or settings.duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    governance_path = Path(governance_dir or settings.governance_path)

    return run_formal_materialize(
        descriptor=BALANCE_ANALYSIS_MODULE,
        job_name="balance_analysis_materialize",
        report_date=report_date,
        governance_dir=str(governance_path),
        lock_base_dir=str(duckdb_file.parent),
        run_id=run_id,
        execute_materialization=lambda: _execute_balance_analysis_materialization(
            report_date=report_date,
            duckdb_file=duckdb_file,
            data_root=data_root,
            fx_source_path=fx_source_path,
        ),
    )


materialize_balance_analysis_facts = register_actor_once(
    "materialize_balance_analysis_facts",
    _materialize_balance_analysis_facts,
)
