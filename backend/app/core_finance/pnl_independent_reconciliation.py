from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Literal

from backend.app.core_finance.finance_metric_engine import (
    LEDGER_IDENTITY_TOLERANCE_YUAN,
)

INDEPENDENT_PNL_REFERENCE_SCHEMA_VERSION = "pnl-independent-reference-v1"
INDEPENDENT_PNL_REFERENCE_BASIS = "independent_ledger"
FACT_MATERIALIZED_ADJUSTMENT_STAGE = "fact_materialized"
PNL_COMPONENTS = (
    "interest_income_514",
    "fair_value_change_516",
    "capital_gain_517",
    "manual_adjustment",
)

ReferenceStatus = Literal["ready", "pending"]
ReconciliationStatus = Literal["pass", "fail", "pending"]


def _finite_decimal(value: object, *, field_name: str) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError(f"{field_name} must use Decimal, int, or decimal text; float is not allowed")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a finite decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{field_name} must be a finite decimal")
    return result


def _non_negative_int(value: object, *, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"{field_name} must be a non-negative integer")
    try:
        result = int(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a non-negative integer") from exc
    if result < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return result


@dataclass(frozen=True, slots=True)
class DailyBalanceObservation:
    report_date: date
    observation_id: str
    amount_native: Decimal
    fx_mid_rate: Decimal
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.observation_id.strip():
            raise ValueError("Daily balance observation requires observation_id")
        _finite_decimal(self.amount_native, field_name="daily_balance.amount_native")
        rate = _finite_decimal(self.fx_mid_rate, field_name="daily_balance.fx_mid_rate")
        if rate <= 0:
            raise ValueError("daily_balance.fx_mid_rate must be greater than zero")
        if not self.evidence_refs:
            raise ValueError("Daily balance observation requires evidence_refs")


def calculate_complete_daily_average_cny(
    observations: Iterable[DailyBalanceObservation],
    *,
    period_start: date,
    period_end: date,
) -> dict[str, object]:
    """Hand-calculate a calendar-day CNY-equivalent average from daily facts.

    Duplicate natural keys fail loudly. Any missing calendar day returns
    ``pending`` without a numeric average, so an incomplete series can never be
    interpreted as zero-filled coverage.
    """

    if period_end < period_start:
        raise ValueError("period_end must be on or after period_start")
    expected_dates: list[date] = []
    current = period_start
    while current <= period_end:
        expected_dates.append(current)
        current += timedelta(days=1)
    daily_totals = {item_date: Decimal("0") for item_date in expected_dates}
    seen: set[tuple[date, str]] = set()
    evidence_refs: list[str] = []
    observation_count = 0
    for row in observations:
        if row.report_date < period_start or row.report_date > period_end:
            continue
        key = (row.report_date, row.observation_id)
        if key in seen:
            raise ValueError(
                "Duplicate daily balance observation "
                f"report_date={row.report_date.isoformat()} observation_id={row.observation_id}"
            )
        seen.add(key)
        observation_count += 1
        daily_totals[row.report_date] += row.amount_native * row.fx_mid_rate
        for evidence_ref in row.evidence_refs:
            if evidence_ref not in evidence_refs:
                evidence_refs.append(evidence_ref)
    observed_dates = {item_date for item_date, _ in seen}
    missing_dates = [item_date.isoformat() for item_date in expected_dates if item_date not in observed_dates]
    if missing_dates:
        return {
            "status": "pending",
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "calendar_days": len(expected_dates),
            "observation_count": observation_count,
            "average_balance_cny": None,
            "missing_dates": missing_dates,
            "evidence_refs": evidence_refs,
            "reason": "daily balance coverage is incomplete",
        }
    average = sum(daily_totals.values(), Decimal("0")) / Decimal(len(expected_dates))
    return {
        "status": "ready",
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "calendar_days": len(expected_dates),
        "observation_count": observation_count,
        "average_balance_cny": average,
        "missing_dates": [],
        "evidence_refs": evidence_refs,
        "reason": "",
    }


@dataclass(frozen=True, slots=True)
class IndependentPnlComponentReference:
    status: ReferenceStatus
    value_yuan: Decimal | None = None
    evidence_refs: tuple[str, ...] = ()
    reason: str = ""

    def __post_init__(self) -> None:
        if self.status not in {"ready", "pending"}:
            raise ValueError(f"Unsupported component reference status={self.status!r}")
        if self.status == "ready":
            if self.value_yuan is None:
                raise ValueError("A ready component reference requires value_yuan")
            _finite_decimal(self.value_yuan, field_name="component.value_yuan")
            if not self.evidence_refs:
                raise ValueError("A ready component reference requires evidence_refs")
        elif self.value_yuan is not None:
            raise ValueError("A pending component reference must not expose value_yuan")
        if self.status == "pending" and not self.reason.strip():
            raise ValueError("A pending component reference requires a reason")

    def to_record(self) -> dict[str, object]:
        return {
            "status": self.status,
            "value_yuan": None if self.value_yuan is None else format(self.value_yuan, "f"),
            "evidence_refs": list(self.evidence_refs),
            "reason": self.reason,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> IndependentPnlComponentReference:
        status = str(record.get("status") or "")
        value = record.get("value_yuan")
        raw_evidence_refs = record.get("evidence_refs") or ()
        if not isinstance(raw_evidence_refs, (list, tuple)):
            raise ValueError("component.evidence_refs must be a list or tuple")
        return cls(
            status=status,  # type: ignore[arg-type]
            value_yuan=(
                None
                if value is None
                else _finite_decimal(value, field_name="component.value_yuan")
            ),
            evidence_refs=tuple(str(item) for item in raw_evidence_refs),
            reason=str(record.get("reason") or ""),
        )


@dataclass(frozen=True, slots=True)
class IndependentPnlReference:
    report_date: str
    currency_basis: str
    ledger_currency_code: str
    source_version: str
    rule_version: str
    formal_source_version: str
    formal_rule_version: str
    approved_adjustment_version: str
    formal_dependency_revision: int
    formal_dependency_protocol_version: str
    adjustment_stage: str
    components: Mapping[str, IndependentPnlComponentReference]

    def __post_init__(self) -> None:
        try:
            date.fromisoformat(self.report_date)
        except ValueError as exc:
            raise ValueError("Independent PnL reference requires an ISO report_date") from exc
        if self.currency_basis != "CNY":
            raise ValueError("Independent PnL reference currency_basis must be CNY")
        if self.ledger_currency_code != "CNX":
            raise ValueError("Independent PnL reference must select the CNX consolidated ledger rows")
        if self.adjustment_stage != FACT_MATERIALIZED_ADJUSTMENT_STAGE:
            raise ValueError("Independent PnL reference adjustment_stage must be fact_materialized")
        if isinstance(self.formal_dependency_revision, bool) or self.formal_dependency_revision < 0:
            raise ValueError("Independent PnL reference requires a non-negative dependency revision")
        required_versions = {
            "source_version": self.source_version,
            "rule_version": self.rule_version,
            "formal_source_version": self.formal_source_version,
            "formal_rule_version": self.formal_rule_version,
            "approved_adjustment_version": self.approved_adjustment_version,
            "formal_dependency_protocol_version": self.formal_dependency_protocol_version,
        }
        missing_versions = [name for name, value in required_versions.items() if not value.strip()]
        if missing_versions:
            raise ValueError(
                f"Independent PnL reference requires version bindings: {missing_versions}"
            )
        unknown = set(self.components) - set(PNL_COMPONENTS)
        if unknown:
            raise ValueError(f"Unknown independent PnL reference components: {sorted(unknown)}")

    @property
    def pending_components(self) -> tuple[str, ...]:
        return tuple(
            component
            for component in PNL_COMPONENTS
            if component not in self.components or self.components[component].status == "pending"
        )

    @property
    def total_yuan(self) -> Decimal | None:
        if self.pending_components:
            return None
        return sum(
            (self.components[component].value_yuan or Decimal("0") for component in PNL_COMPONENTS),
            Decimal("0"),
        )

    def to_record(self) -> dict[str, object]:
        return {
            "schema_version": INDEPENDENT_PNL_REFERENCE_SCHEMA_VERSION,
            "basis": INDEPENDENT_PNL_REFERENCE_BASIS,
            "report_date": self.report_date,
            "currency_basis": self.currency_basis,
            "ledger_currency_code": self.ledger_currency_code,
            "source_version": self.source_version,
            "rule_version": self.rule_version,
            "formal_source_version": self.formal_source_version,
            "formal_rule_version": self.formal_rule_version,
            "approved_adjustment_version": self.approved_adjustment_version,
            "formal_dependency_revision": self.formal_dependency_revision,
            "formal_dependency_protocol_version": self.formal_dependency_protocol_version,
            "adjustment_stage": self.adjustment_stage,
            "components": {
                component: self.components[component].to_record()
                for component in PNL_COMPONENTS
                if component in self.components
            },
            "pending_components": list(self.pending_components),
            "total_yuan": None if self.total_yuan is None else format(self.total_yuan, "f"),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> IndependentPnlReference:
        if record.get("schema_version") != INDEPENDENT_PNL_REFERENCE_SCHEMA_VERSION:
            raise ValueError("Unsupported independent PnL reference schema_version")
        if record.get("basis") != INDEPENDENT_PNL_REFERENCE_BASIS:
            raise ValueError("Independent PnL reference basis must be independent_ledger")
        raw_components = record.get("components")
        if not isinstance(raw_components, Mapping):
            raise ValueError("Independent PnL reference components must be a mapping")
        components = {
            str(component): IndependentPnlComponentReference.from_record(component_record)
            for component, component_record in raw_components.items()
            if isinstance(component_record, Mapping)
        }
        if len(components) != len(raw_components):
            raise ValueError("Independent PnL component records must be mappings")
        reference = cls(
            report_date=str(record.get("report_date") or ""),
            currency_basis=str(record.get("currency_basis") or ""),
            ledger_currency_code=str(record.get("ledger_currency_code") or ""),
            source_version=str(record.get("source_version") or ""),
            rule_version=str(record.get("rule_version") or ""),
            formal_source_version=str(record.get("formal_source_version") or ""),
            formal_rule_version=str(record.get("formal_rule_version") or ""),
            approved_adjustment_version=str(record.get("approved_adjustment_version") or ""),
            formal_dependency_revision=_non_negative_int(
                record.get("formal_dependency_revision"),
                field_name="formal_dependency_revision",
            ),
            formal_dependency_protocol_version=str(
                record.get("formal_dependency_protocol_version") or ""
            ),
            adjustment_stage=str(record.get("adjustment_stage") or ""),
            components=components,
        )
        raw_pending = record.get("pending_components")
        if not isinstance(raw_pending, list):
            raise ValueError("Independent PnL reference pending_components must be a list")
        if tuple(str(item) for item in raw_pending) != reference.pending_components:
            raise ValueError("Independent PnL reference pending_components does not match components")
        serialized_total = record.get("total_yuan")
        if reference.total_yuan is not None and serialized_total is None:
            raise ValueError("A ready independent PnL reference requires total_yuan")
        if serialized_total is not None:
            expected_total = _finite_decimal(serialized_total, field_name="total_yuan")
            if reference.total_yuan != expected_total:
                raise ValueError("Independent PnL reference total_yuan does not equal its components")
        return reference


def reconcile_pnl_overview_to_independent_reference(
    formal_totals: Mapping[str, object],
    reference: IndependentPnlReference | None,
    *,
    report_date: str,
    formal_dependency_revision: int,
    formal_dependency_protocol_version: str,
    adjustment_stage: str,
    threshold_yuan: Decimal = LEDGER_IDENTITY_TOLERANCE_YUAN,
) -> dict[str, object]:
    """Compare formal PnL with a separately prepared ledger reference.

    The caller must load ``reference`` from a background-prepared result. This
    function performs no source-file I/O and never turns missing evidence into
    zero. A definite component mismatch is a failure even if another component
    remains pending; the total comparison is only available when every component
    has complete independent evidence.
    """

    tolerance = _finite_decimal(threshold_yuan, field_name="threshold_yuan")
    if tolerance <= 0:
        raise ValueError("threshold_yuan must be greater than zero")
    if reference is None:
        return {
            "check_kind": INDEPENDENT_PNL_REFERENCE_BASIS,
            "status": "pending",
            "breached": None,
            "report_date": report_date,
            "currency_basis": "CNY",
            "source_version": None,
            "rule_version": None,
            "threshold_yuan": format(tolerance, "f"),
            "components": [],
            "pending_components": list(PNL_COMPONENTS),
            "formal_total_yuan": None,
            "reference_total_yuan": None,
            "total_diff_yuan": None,
            "reason": "independent ledger reference is not prepared",
        }
    if reference.report_date != report_date:
        raise ValueError(
            f"Independent PnL reference report_date={reference.report_date} does not match {report_date}"
        )
    normalized_dependency_revision = _non_negative_int(
        formal_dependency_revision,
        field_name="formal_dependency_revision",
    )
    requested_binding = {
        "formal_dependency_revision": normalized_dependency_revision,
        "formal_dependency_protocol_version": formal_dependency_protocol_version,
        "adjustment_stage": adjustment_stage,
    }
    reference_binding = {
        "formal_dependency_revision": reference.formal_dependency_revision,
        "formal_dependency_protocol_version": reference.formal_dependency_protocol_version,
        "adjustment_stage": reference.adjustment_stage,
    }
    mismatched_bindings = [
        name
        for name, value in requested_binding.items()
        if value != reference_binding[name]
    ]
    if not formal_dependency_protocol_version.strip():
        mismatched_bindings.append("formal_dependency_protocol_version")
    if not adjustment_stage.strip():
        mismatched_bindings.append("adjustment_stage")
    mismatched_bindings = list(dict.fromkeys(mismatched_bindings))
    if mismatched_bindings:
        return {
            "check_kind": INDEPENDENT_PNL_REFERENCE_BASIS,
            "status": "pending",
            "breached": None,
            "report_date": report_date,
            "currency_basis": reference.currency_basis,
            "source_version": reference.source_version,
            "rule_version": reference.rule_version,
            "threshold_yuan": format(tolerance, "f"),
            "components": [],
            "pending_components": list(PNL_COMPONENTS),
            "formal_total_yuan": None,
            "reference_total_yuan": None,
            "total_diff_yuan": None,
            "reason": f"reference dependency binding mismatch: {mismatched_bindings}",
        }

    rows: list[dict[str, object]] = []
    pending_components: list[str] = []
    definite_failure = False
    for component in PNL_COMPONENTS:
        component_reference = reference.components.get(component)
        formal_raw = formal_totals.get(component)
        if component_reference is None or component_reference.status == "pending":
            pending_components.append(component)
            formal_value = (
                None
                if formal_raw is None
                else _finite_decimal(formal_raw, field_name=f"formal_totals.{component}")
            )
            rows.append(
                {
                    "component": component,
                    "status": "pending",
                    "formal_value_yuan": (
                        None if formal_value is None else format(formal_value, "f")
                    ),
                    "reference_value_yuan": None,
                    "diff_yuan": None,
                    "evidence_refs": (
                        [] if component_reference is None else list(component_reference.evidence_refs)
                    ),
                    "reason": (
                        "component reference is missing"
                        if component_reference is None
                        else component_reference.reason
                    ),
                }
            )
            continue
        if formal_raw is None:
            pending_components.append(component)
            rows.append(
                {
                    "component": component,
                    "status": "pending",
                    "formal_value_yuan": None,
                    "reference_value_yuan": format(component_reference.value_yuan or Decimal("0"), "f"),
                    "diff_yuan": None,
                    "evidence_refs": list(component_reference.evidence_refs),
                    "reason": "formal component is missing",
                }
            )
            continue
        formal_value = _finite_decimal(formal_raw, field_name=f"formal_totals.{component}")
        reference_value = component_reference.value_yuan
        assert reference_value is not None
        diff = formal_value - reference_value
        failed = abs(diff) > tolerance
        definite_failure = definite_failure or failed
        rows.append(
            {
                "component": component,
                "status": "fail" if failed else "pass",
                "formal_value_yuan": format(formal_value, "f"),
                "reference_value_yuan": format(reference_value, "f"),
                "diff_yuan": format(diff, "f"),
                "evidence_refs": list(component_reference.evidence_refs),
                "reason": "",
            }
        )

    formal_total_raw = formal_totals.get("total_pnl")
    reference_total = reference.total_yuan
    formal_total: Decimal | None = None
    total_diff: Decimal | None = None
    if not pending_components and formal_total_raw is not None and reference_total is not None:
        formal_total = _finite_decimal(formal_total_raw, field_name="formal_totals.total_pnl")
        total_diff = formal_total - reference_total
        definite_failure = definite_failure or abs(total_diff) > tolerance
    elif formal_total_raw is None and "total_pnl" not in pending_components:
        pending_components.append("total_pnl")

    status: ReconciliationStatus = (
        "fail" if definite_failure else "pending" if pending_components else "pass"
    )
    return {
        "check_kind": INDEPENDENT_PNL_REFERENCE_BASIS,
        "status": status,
        "breached": True if status == "fail" else None if status == "pending" else False,
        "report_date": report_date,
        "currency_basis": reference.currency_basis,
        "source_version": reference.source_version,
        "rule_version": reference.rule_version,
        "threshold_yuan": format(tolerance, "f"),
        "components": rows,
        "pending_components": pending_components,
        "formal_total_yuan": None if formal_total is None else format(formal_total, "f"),
        "reference_total_yuan": None if reference_total is None else format(reference_total, "f"),
        "total_diff_yuan": None if total_diff is None else format(total_diff, "f"),
        "reason": "" if status != "pending" else "one or more independent components are not ready",
    }


__all__ = [
    "FACT_MATERIALIZED_ADJUSTMENT_STAGE",
    "INDEPENDENT_PNL_REFERENCE_BASIS",
    "INDEPENDENT_PNL_REFERENCE_SCHEMA_VERSION",
    "PNL_COMPONENTS",
    "DailyBalanceObservation",
    "IndependentPnlComponentReference",
    "IndependentPnlReference",
    "calculate_complete_daily_average_cny",
    "reconcile_pnl_overview_to_independent_reference",
]
