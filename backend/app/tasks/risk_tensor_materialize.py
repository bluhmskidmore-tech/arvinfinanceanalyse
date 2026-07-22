from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
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
from backend.app.repositories.task_write_guard import repository_task_write_scope
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
        rule_version="rv_risk_tensor_formal_materialize_v3",
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

_REQUIRED_BOND_NUMERIC_FIELDS = (
    "market_value",
    "coupon_rate",
    "modified_duration",
    "convexity",
    "dv01",
    "spread_dv01",
)
_OPTIONAL_BOND_NUMERIC_FIELDS = ("face_value",)
_REQUIRED_LIABILITY_NUMERIC_FIELDS = ("principal_amount", "funding_cost_rate")

_DISCOUNT_NCD_BOND_TYPE = "\u540c\u4e1a\u5b58\u5355"
_NCD_ZERO_COUPON_RULE_ID = "ncd_zero_coupon_coupon_rate_v1"
_ZERO = Decimal("0")
_ONE = Decimal("1")


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


def _rate_unit_violations(rows: list[dict[str, object]]) -> list[str]:
    violations: list[str] = []
    for row in rows:
        instrument_code = str(row.get("instrument_code") or "").strip() or "<unknown>"
        value = row.get("coupon_rate")
        if value is None or str(value).strip() == "":
            continue
        rate = Decimal(str(value))
        if abs(rate) > Decimal("1"):
            violations.append(f"{instrument_code}.coupon_rate={rate}")
    return violations


def _decimal_parse_violation(value: object, *, row_label: str, field_name: str) -> str | None:
    if value is None or str(value).strip() == "":
        return f"{row_label}.{field_name}=<missing>"
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return f"{row_label}.{field_name}={value!r}"
    if not parsed.is_finite():
        return f"{row_label}.{field_name}={value!r}"
    return None


def _numeric_input_violations(
    rows: list[dict[str, object]],
    *,
    required_fields: tuple[str, ...],
    label_field: str,
    optional_fields: tuple[str, ...] = (),
) -> list[str]:
    violations: list[str] = []
    for index, row in enumerate(rows, start=1):
        row_label = str(row.get(label_field) or "").strip() or f"row-{index}"
        for field_name in required_fields:
            violation = _decimal_parse_violation(
                row.get(field_name),
                row_label=row_label,
                field_name=field_name,
            )
            if violation is not None:
                violations.append(violation)
        for field_name in optional_fields:
            value = row.get(field_name)
            if value is None or str(value).strip() == "":
                continue
            violation = _decimal_parse_violation(
                value,
                row_label=row_label,
                field_name=field_name,
            )
            if violation is not None:
                violations.append(violation)
    return violations


def _finite_decimal_or_none(value: object) -> Decimal | None:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return parsed if parsed.is_finite() else None


def _normalized_discount_ncd_coupon_market_value(
    row: dict[str, object],
    *,
    report_day: date,
) -> Decimal | None:
    coupon_rate = row.get("coupon_rate")
    if coupon_rate is not None and str(coupon_rate).strip() != "":
        return None
    if str(row.get("bond_type") or "").strip() != _DISCOUNT_NCD_BOND_TYPE:
        return None
    maturity_text = str(row.get("maturity_date") or "").strip()
    try:
        maturity_day = date.fromisoformat(maturity_text)
    except ValueError:
        return None
    if maturity_day <= report_day:
        return None
    ytm = _finite_decimal_or_none(row.get("ytm"))
    accrued_interest = _finite_decimal_or_none(row.get("accrued_interest"))
    face_value = _finite_decimal_or_none(row.get("face_value"))
    market_value = _finite_decimal_or_none(row.get("market_value"))
    if ytm is None or ytm <= _ZERO or ytm > _ONE:
        return None
    if accrued_interest != _ZERO:
        return None
    if face_value is None or face_value <= _ZERO:
        return None
    if market_value is None or market_value <= _ZERO or market_value >= face_value:
        return None
    return market_value


def _normalize_discount_ncd_coupon_rows(
    rows: list[dict[str, object]],
    *,
    report_day: date,
) -> tuple[list[dict[str, object]], int, Decimal]:
    normalized_rows: list[dict[str, object]] = []
    normalized_market_value = _ZERO
    normalized_count = 0
    for row in rows:
        normalized_row = dict(row)
        coupon_market_value = _normalized_discount_ncd_coupon_market_value(row, report_day=report_day)
        if coupon_market_value is not None:
            normalized_row["coupon_rate"] = _ZERO
            normalized_count += 1
            normalized_market_value += coupon_market_value
        normalized_rows.append(normalized_row)
    return normalized_rows, normalized_count, normalized_market_value


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
    lineage_fields = ("source_version", "rule_version", "cache_version")
    normalized_upstream_lineage = {
        field_name: str((upstream_lineage or {}).get(field_name) or "").strip()
        for field_name in lineage_fields
    }
    missing_lineage_fields = [
        field_name
        for field_name, field_value in normalized_upstream_lineage.items()
        if not field_value
    ]
    if missing_lineage_fields:
        raise FormalComputeMaterializeFailure(
            source_version="sv_risk_tensor_upstream_missing",
            vendor_version="vv_none",
            message=(
                "risk_tensor requires completed bond_analytics lineage with non-empty "
                "source_version, rule_version, and cache_version; "
                f"report_date={report_date}; missing={', '.join(missing_lineage_fields)}"
            ),
        )
    upstream_lineage = normalized_upstream_lineage

    bond_repo = BondAnalyticsRepository(str(duckdb_file))
    report_day = date.fromisoformat(report_date)
    raw_rows = bond_repo.fetch_bond_analytics_rows(report_date=report_date)
    rows, coupon_normalized_row_count, coupon_normalized_market_value = _normalize_discount_ncd_coupon_rows(
        raw_rows,
        report_day=report_day,
    )
    liability_rows = _load_liability_rows(
        duckdb_file=duckdb_file,
        report_date=report_date,
    )
    source_version = _build_source_version(
        upstream_lineage["source_version"],
        liability_source_versions=[
            str(row.get("source_version") or "").strip() for row in liability_rows
        ],
    )
    numeric_violations = _numeric_input_violations(
        rows,
        required_fields=_REQUIRED_BOND_NUMERIC_FIELDS,
        optional_fields=_OPTIONAL_BOND_NUMERIC_FIELDS,
        label_field="instrument_code",
    )
    numeric_violations.extend(
        _numeric_input_violations(
            liability_rows,
            required_fields=_REQUIRED_LIABILITY_NUMERIC_FIELDS,
            label_field="position_id",
        )
    )
    if numeric_violations:
        raise FormalComputeMaterializeFailure(
            source_version=source_version,
            vendor_version="vv_none",
            message=(
                "risk_tensor requires parseable numeric formal inputs; "
                f"report_date={report_date}; violations="
                + ", ".join(numeric_violations[:5])
            ),
        )
    rate_unit_violations = _rate_unit_violations(rows)
    if rate_unit_violations:
        raise FormalComputeMaterializeFailure(
            source_version=source_version,
            vendor_version="vv_none",
            message=(
                "risk_tensor requires decimal-form bond analytics rates; "
                "rebuild bond_analytics before materializing risk_tensor. "
                f"report_date={report_date}; violations="
                + ", ".join(rate_unit_violations[:5])
            ),
        )

    tensor = compute_portfolio_risk_tensor(
        rows,
        report_day,
        liability_rows=liability_rows,
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
        with repository_task_write_scope(__name__):
            RiskTensorRepository(str(duckdb_file)).replace_risk_tensor_row(
                report_date=report_date,
                tensor=tensor,
                source_version=source_version,
                upstream_source_version=upstream_lineage["source_version"],
                upstream_rule_version=upstream_lineage["rule_version"],
                upstream_cache_version=upstream_lineage["cache_version"],
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
            "coupon_normalization_rule_id": _NCD_ZERO_COUPON_RULE_ID,
            "coupon_normalized_row_count": coupon_normalized_row_count,
            "coupon_normalized_market_value": str(coupon_normalized_market_value),
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
        duckdb_path=str(duckdb_file),
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
