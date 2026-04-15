from __future__ import annotations

from datetime import date
from pathlib import Path

from backend.app.core_finance.module_contracts import FormalComputeModuleDescriptor
from backend.app.core_finance.module_registry import ensure_formal_module
from backend.app.core_finance.risk_tensor import compute_portfolio_risk_tensor
from backend.app.governance.settings import get_settings
from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository
from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository
from backend.app.repositories.risk_tensor_repo import (
    RiskTensorRepository,
    load_latest_bond_analytics_lineage,
)
from backend.app.schemas.formal_compute_runtime import (
    FormalComputeMaterializeFailure,
    FormalComputeMaterializeResult,
)
from backend.app.tasks.bond_analytics_materialize import CACHE_KEY as BOND_ANALYTICS_CACHE_KEY
from backend.app.tasks.broker import register_actor_once
from backend.app.tasks.formal_compute_runtime import run_formal_materialize

RISK_TENSOR_MODULE = ensure_formal_module(
    FormalComputeModuleDescriptor(
        module_name="risk_tensor",
        basis="formal",
        # Governed downstream derivative of bond_analytics formal facts.
        input_sources=("fact_formal_bond_analytics_daily", "fact_formal_tyw_balance_daily"),
        fact_tables=("fact_formal_risk_tensor_daily",),
        rule_version="rv_risk_tensor_formal_materialize_v1",
        result_kind_family="risk-tensor",
        supports_standard_queries=True,
        supports_custom_queries=False,
    )
)
RISK_TENSOR_FORMAL_BASIS = RISK_TENSOR_MODULE.basis
CACHE_KEY = RISK_TENSOR_MODULE.cache_key
RISK_TENSOR_LOCK = RISK_TENSOR_MODULE.lock_definition
RULE_VERSION = RISK_TENSOR_MODULE.rule_version
CACHE_VERSION = RISK_TENSOR_MODULE.cache_version


def _build_source_version(
    upstream_source_version: str,
    liability_source_versions: list[str] | None = None,
) -> str:
    parts = ["sv_risk_tensor", upstream_source_version]
    for value in sorted({str(item).strip() for item in (liability_source_versions or []) if str(item).strip()}):
        parts.append(value)
    return "__".join(parts)


def _load_liability_rows(*, duckdb_file: Path, report_date: str) -> list[dict[str, object]]:
    repo = BalanceAnalysisRepository(str(duckdb_file))
    try:
        return repo.fetch_formal_tyw_rows(
            report_date=report_date,
            position_scope="liability",
            currency_basis="CNY",
        )
    except Exception as exc:
        if "fact_formal_tyw_balance_daily" in str(exc) and "does not exist" in str(exc):
            return []
        raise


def _execute_risk_tensor_materialization(
    *,
    report_date: str,
    duckdb_file: Path,
    governance_dir: str,
) -> FormalComputeMaterializeResult:
    upstream_lineage = load_latest_bond_analytics_lineage(
        governance_dir=governance_dir,
        report_date=report_date,
    )
    if upstream_lineage is None or not upstream_lineage["source_version"]:
        raise FormalComputeMaterializeFailure(
            source_version="sv_risk_tensor_upstream_missing",
            vendor_version="vv_none",
            message=(
                "risk_tensor requires completed bond_analytics lineage "
                f"for report_date={report_date}"
            ),
        )

    bond_repo = BondAnalyticsRepository(str(duckdb_file))
    rows = bond_repo.fetch_bond_analytics_rows(report_date=report_date)
    liability_rows = _load_liability_rows(
        duckdb_file=duckdb_file,
        report_date=report_date,
    )
    tensor = compute_portfolio_risk_tensor(
        rows,
        date.fromisoformat(report_date),
        liability_rows=liability_rows,
    )
    source_version = _build_source_version(
        upstream_lineage["source_version"],
        liability_source_versions=[
            str(row.get("source_version") or "").strip() for row in liability_rows
        ],
    )
    liability_source_version = "__".join(
        sorted(
            {
                str(row.get("source_version") or "").strip()
                for row in liability_rows
                if str(row.get("source_version") or "").strip()
            }
        )
    )
    liability_rule_version = "__".join(
        sorted(
            {
                str(row.get("rule_version") or "").strip()
                for row in liability_rows
                if str(row.get("rule_version") or "").strip()
            }
        )
    )

    try:
        RiskTensorRepository(str(duckdb_file)).replace_risk_tensor_row(
            report_date=report_date,
            tensor=tensor,
            source_version=source_version,
            upstream_source_version=upstream_lineage["source_version"],
            liability_source_version=liability_source_version,
            liability_rule_version=liability_rule_version,
            rule_version=RULE_VERSION,
            cache_version=CACHE_VERSION,
            trace_id=f"trace_risk_tensor_{report_date.replace('-', '')}",
        )
    except Exception as exc:
        raise FormalComputeMaterializeFailure(
            source_version=source_version,
            vendor_version="vv_none",
            message=str(exc),
        ) from exc

    return FormalComputeMaterializeResult(
        source_version=source_version,
        vendor_version="vv_none",
        payload={
            "bond_count": tensor.bond_count,
            "quality_flag": tensor.quality_flag,
            "upstream_cache_key": BOND_ANALYTICS_CACHE_KEY,
        },
    )


def _materialize_risk_tensor_facts(
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

    return run_formal_materialize(
        descriptor=RISK_TENSOR_MODULE,
        job_name="risk_tensor_materialize",
        report_date=report_date,
        governance_dir=str(governance_path),
        lock_base_dir=str(duckdb_file.parent),
        run_id=run_id,
        execute_materialization=lambda: _execute_risk_tensor_materialization(
            report_date=report_date,
            duckdb_file=duckdb_file,
            governance_dir=str(governance_path),
        ),
    )


materialize_risk_tensor_facts = register_actor_once(
    "materialize_risk_tensor_facts",
    _materialize_risk_tensor_facts,
)
