from __future__ import annotations

import hashlib
import json
import re
from calendar import isleap, monthrange
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

DEFAULT_RULE_VERSION = "qdb-finance-2026-v1.0.1"
RULE_ASSETS = {
    "qdb-finance-2026-v1.0.0": Path(__file__).with_name("qdb_finance_2026_v1_0_0.json"),
    DEFAULT_RULE_VERSION: Path(__file__).with_name("qdb_finance_2026_v1_0_1.json"),
}
APPROVED_RULE_SHA256_BY_VERSION = {
    "qdb-finance-2026-v1.0.0": "7f1b9d47dece2db850ef69cd9ab13b2520ad3bc09d6a2bce3a48ac6017777567",
    DEFAULT_RULE_VERSION: "c67f4c85390992a1929bcff65c2bbdbd5c5c382912af3ebcd49297b1e7ac6a66",
}
EXPECTED_METADATA_BASE = {
    "schema_version": "1.0",
    "currency": "CNX",
    "raw_amount_unit": "元",
    "output_amount_unit": "亿元",
    "conversion_divisor": "100000000",
}
HISTORICAL_SOURCE_HASHES = {
    "2026年财务指标表-3月最终(2).xlsx": "73d475d77d04a89d9d7eae5b9853ef5b604c413625eb308c1af9fd175aa17aeb",
    "总账对账202606.xlsx": "0ba128f1dca4084cfdf4aff410576f1945c11240a88778e00175cbc977e7493d",
    "日均202606.xlsx": "49e9a5b06c30656aaa07ef583d459dfff514ddd478640b0fb6f0b355d9758498",
}
EXPECTED_SOURCE_HASHES_BY_VERSION = {
    "qdb-finance-2026-v1.0.0": HISTORICAL_SOURCE_HASHES,
    DEFAULT_RULE_VERSION: {
        **HISTORICAL_SOURCE_HASHES,
        "总账对账202606.xlsx": "29717578b92e107cc2fbcd5b66cd7c63191c24e1a7d245c103c94e235331c0b7",
    },
}

# Backwards-compatible aliases expose the active contract to existing callers.
RULE_ASSET = RULE_ASSETS[DEFAULT_RULE_VERSION]
APPROVED_RULE_SHA256 = APPROVED_RULE_SHA256_BY_VERSION[DEFAULT_RULE_VERSION]
EXPECTED_METADATA = {"rule_version": DEFAULT_RULE_VERSION, **EXPECTED_METADATA_BASE}
EXPECTED_SOURCE_HASHES = EXPECTED_SOURCE_HASHES_BY_VERSION[DEFAULT_RULE_VERSION]

EXPECTED_VALIDATION_IDS = {
    "period.same_end_date",
    "period.ytd_starts_jan1",
    "period.month_is_calendar_month",
    "currency.cnx_only",
    "ledger.balance_identity",
    "ledger.duplicate_full_code",
    "rules.missing_accounts",
    "recon.company_deposit",
    "recon.retail_deposit",
    "recon.personal_loan",
    "recon.loan_interest",
    "recon.noninterest",
}
EXPECTED_SECTION_COUNTS = {
    "scale_rules": 19,
    "direct_rules": 75,
    "manual_metrics": 19,
    "derived_rules": 35,
}
EXPECTED_VALIDATION_RULES = 12
EXPECTED_EXPANDED_OUTPUTS = 186
EXPECTED_PERIOD_IDS = (
    "ledger",
    "daily_ytd",
    "daily_month",
    "microloan_ytd",
    "microloan_month",
    "microloan_ledger",
)
YTD_PERIOD_IDS = ("daily_ytd", "microloan_ytd")
MONTH_PERIOD_IDS = ("ledger", "daily_month", "microloan_month", "microloan_ledger")
LEDGER_IDENTITY_TOLERANCE_YUAN = Decimal("0.01")
RECONCILIATION_TOLERANCE_YI = Decimal("0.000001")
FINANCE_METRIC_ENGINE_CONTRACT_VERSION = "finance-metric-engine-v1"

AccountKey = tuple[str, str, str, str]
FinanceMetricStatus = Literal["ok", "warning", "manual_default", "error"]


@dataclass(frozen=True, slots=True)
class AccountObservation:
    raw_yuan: Decimal
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AccountResolution:
    raw_yuan: Decimal
    observed: bool
    evidence_refs: tuple[str, ...]


class FinanceMetricDataContext:
    def __init__(self, observations: Mapping[AccountKey, AccountObservation] | None = None) -> None:
        self._observations = dict(observations or {})

    def resolve(self, source: str, basis: str, level: str, code: str) -> AccountResolution:
        observation = self._observations.get((source, basis, level, code))
        if observation is None:
            return AccountResolution(raw_yuan=Decimal(0), observed=False, evidence_refs=())
        return AccountResolution(
            raw_yuan=observation.raw_yuan,
            observed=True,
            evidence_refs=observation.evidence_refs,
        )


@dataclass(frozen=True, slots=True)
class FinanceMetricAccountLineage:
    source: str
    basis: str | None
    level: str
    code: str
    weight: Decimal
    observed: bool
    raw_yuan: Decimal
    contribution_yi: Decimal
    evidence_refs: tuple[str, ...]
    lineage_type: Literal["account"] = field(default="account", init=False)


@dataclass(frozen=True, slots=True)
class FinanceMetricMetricLineage:
    metric_id: str
    weight: Decimal
    metric_value_yi: Decimal | None
    contribution_yi: Decimal | None
    dependency_status: FinanceMetricStatus
    lineage_type: Literal["metric"] = field(default="metric", init=False)


@dataclass(frozen=True, slots=True)
class FinanceMetricManualLineage:
    supplied: bool
    value_yi: Decimal | None
    lineage_type: Literal["manual"] = field(default="manual", init=False)


FinanceMetricLineage = (
    FinanceMetricAccountLineage | FinanceMetricMetricLineage | FinanceMetricManualLineage
)


@dataclass(frozen=True, slots=True)
class FinanceMetricResult:
    id: str
    name: str
    category: str
    basis: str
    unit: str
    value: Decimal | None
    status: FinanceMetricStatus
    reasons: tuple[str, ...]
    lineage: tuple[FinanceMetricLineage, ...] | None


class FinanceMetricRuleError(ValueError):
    def __init__(self, code: str, metric_ids: tuple[str, ...]) -> None:
        self.code = code
        self.metric_ids = metric_ids
        super().__init__(f"{code}: {', '.join(metric_ids)}")


class FinanceMetricInputError(ValueError):
    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code} at {path}: {message}")


@dataclass(frozen=True, slots=True)
class FinanceMetricPeriod:
    id: str
    start: date
    end: date


@dataclass(frozen=True, slots=True)
class FinanceMetricLedgerBalanceRow:
    source: str
    row: int
    code: str
    currency: str
    opening: Decimal
    debit: Decimal
    credit: Decimal
    ending: Decimal


@dataclass(frozen=True, slots=True)
class FinanceMetricValidationEvidence:
    periods: tuple[FinanceMetricPeriod, ...] = ()
    consumed_currencies: tuple[str, ...] = ()
    ledger_balance_rows: tuple[FinanceMetricLedgerBalanceRow, ...] = ()


@dataclass(frozen=True, slots=True)
class FinanceMetricValidationResult:
    id: str
    severity: Literal["error", "warning"]
    passed: bool
    message: str
    delta_yi: Decimal | None
    sample: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FinanceMetricRatioResult:
    value: Decimal | None
    reason: str | None


@dataclass(frozen=True, slots=True)
class FinanceMetricCumulativeMomResult:
    current_month: Decimal | None
    previous_month: Decimal | None
    delta: Decimal | None
    rate: Decimal | None
    reason: str | None


@dataclass(frozen=True, slots=True)
class FinanceMetricThreeFactorAttribution:
    volume: Decimal
    rate: Decimal
    cross: Decimal
    total_change: Decimal
    reconciliation_delta: Decimal


def evaluate_finance_metrics(
    rules: dict[str, Any],
    context: FinanceMetricDataContext,
    *,
    manual_overrides: Mapping[str, Decimal | None] | None = None,
    include_lineage: bool = True,
) -> tuple[FinanceMetricResult, ...]:
    derived_rules = list(rules.get("derived_rules", []))
    derived_evaluation_order = _validated_derived_order(rules)
    divisor = Decimal(rules["metadata"]["conversion_divisor"])
    overrides = _validated_manual_overrides(rules, manual_overrides)
    results: list[FinanceMetricResult] = []
    # manual_metrics 分支的 value 可为 None（override 显式置空），提前声明联合类型。
    value: Decimal | None
    for rule in rules.get("scale_rules", []):
        for basis in rule["available_bases"]:
            terms_by_basis = rule.get("terms_by_basis")
            terms = terms_by_basis[basis] if terms_by_basis is not None else rule["terms"]
            value, reasons, lineage = _evaluate_account_terms(
                terms,
                basis,
                context,
                divisor,
                include_lineage=include_lineage,
            )
            results.append(
                FinanceMetricResult(
                    id=f"{rule['id']}::{basis}",
                    name=rule["name"],
                    category=rule["category"],
                    basis=basis,
                    unit=rule["unit"],
                    value=value,
                    status="warning" if reasons else "ok",
                    reasons=reasons,
                    lineage=lineage,
                )
            )
    for rule in rules.get("direct_rules", []):
        basis = rule["basis"]
        value, reasons, lineage = _evaluate_account_terms(
            rule["terms"],
            basis,
            context,
            divisor,
            include_lineage=include_lineage,
        )
        results.append(
            FinanceMetricResult(
                id=rule["id"],
                name=rule["name"],
                category=rule["category"],
                basis=basis,
                unit=rule["unit"],
                value=value,
                status="warning" if reasons else "ok",
                reasons=reasons,
                lineage=lineage,
            )
        )
    for rule in rules.get("manual_metrics", []):
        supplied = rule["id"] in overrides
        value = overrides[rule["id"]] if supplied else Decimal(rule["default"])
        required_default = not supplied and rule.get("manual_required", False)
        unavailable = supplied and value is None
        results.append(
            FinanceMetricResult(
                id=rule["id"],
                name=rule["name"],
                category=rule["category"],
                basis=rule["basis"],
                unit=rule["unit"],
                value=value,
                status="error" if unavailable else "manual_default" if required_default else "ok",
                reasons=(
                    ("manual_override_unavailable",)
                    if unavailable
                    else ("manual_required_not_supplied",)
                    if required_default
                    else ()
                ),
                lineage=(FinanceMetricManualLineage(supplied=supplied, value_yi=value),)
                if include_lineage
                else None,
            )
        )
    results_by_id = {result.id: result for result in results}
    for rule in derived_evaluation_order:
        basis = rule["basis"]
        calculation = rule["calculation"]
        value, reasons, account_lineage = _evaluate_account_terms(
            calculation.get("account_terms", []),
            basis,
            context,
            divisor,
            include_lineage=include_lineage,
        )
        derived_reasons = list(reasons)
        derived_lineage: list[FinanceMetricLineage] | None = (
            list(account_lineage or ()) if include_lineage else None
        )
        dependency_error = False
        unavailable_dependency = False
        for term in calculation.get("metric_terms", []):
            dependency = results_by_id[term["metric_id"]]
            if dependency.value is None:
                unavailable_dependency = True
                contribution = None
            else:
                contribution = Decimal(term["weight"]) * dependency.value
                value += contribution
            dependency_error = dependency_error or dependency.status == "error"
            if derived_lineage is not None:
                derived_lineage.append(
                    FinanceMetricMetricLineage(
                        metric_id=dependency.id,
                        weight=Decimal(term["weight"]),
                        metric_value_yi=dependency.value,
                        contribution_yi=contribution,
                        dependency_status=dependency.status,
                    )
                )
            if dependency.status != "ok":
                dependency_reasons = dependency.reasons or (dependency.status,)
                derived_reasons.extend(
                    f"dependency:{dependency.id}:{reason}" for reason in dependency_reasons
                )
        result = FinanceMetricResult(
            id=rule["id"],
            name=rule["name"],
            category=rule["category"],
            basis=basis,
            unit=rule["unit"],
            value=None if unavailable_dependency else value,
            status=(
                "error"
                if dependency_error or unavailable_dependency
                else "warning"
                if derived_reasons
                else "ok"
            ),
            reasons=tuple(derived_reasons),
            lineage=tuple(derived_lineage) if derived_lineage is not None else None,
        )
        results_by_id[result.id] = result
    results.extend(results_by_id[rule["id"]] for rule in derived_rules)
    return tuple(results)


def _evaluate_account_terms(
    terms: list[dict[str, Any]],
    basis: str,
    context: FinanceMetricDataContext,
    divisor: Decimal,
    *,
    include_lineage: bool,
) -> tuple[Decimal, tuple[str, ...], tuple[FinanceMetricAccountLineage, ...] | None]:
    value = Decimal(0)
    reasons: list[str] = []
    lineage: list[FinanceMetricAccountLineage] | None = [] if include_lineage else None
    for term in terms:
        resolution = context.resolve(term["source"], basis, term["level"], term["code"])
        weight = Decimal(term["weight"])
        contribution = weight * resolution.raw_yuan / divisor
        value += contribution
        if lineage is not None:
            lineage.append(
                FinanceMetricAccountLineage(
                    source=term["source"],
                    basis=basis,
                    level=term["level"],
                    code=term["code"],
                    weight=weight,
                    observed=resolution.observed,
                    raw_yuan=resolution.raw_yuan,
                    contribution_yi=contribution,
                    evidence_refs=resolution.evidence_refs,
                )
            )
        if not resolution.observed:
            reasons.append(
                f"missing_account:{term['source']}:{basis}:{term['level']}:{term['code']}"
            )
    return value, tuple(reasons), tuple(lineage) if lineage is not None else None


def _validated_derived_order(rules: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    derived_rules = list(rules.get("derived_rules", []))
    derived_ids = tuple(rule["id"] for rule in derived_rules)
    known_ids = {
        f"{rule['id']}::{basis}"
        for rule in rules.get("scale_rules", [])
        for basis in rule["available_bases"]
    }
    known_ids.update(rule["id"] for rule in rules.get("direct_rules", []))
    known_ids.update(rule["id"] for rule in rules.get("manual_metrics", []))
    known_ids.update(derived_ids)
    dependencies = {
        rule["id"]: tuple(
            term["metric_id"] for term in rule["calculation"].get("metric_terms", [])
        )
        for rule in derived_rules
    }

    unknown_edges = tuple(
        f"{rule_id}->{dependency_id}"
        for rule_id in derived_ids
        for dependency_id in dependencies[rule_id]
        if dependency_id not in known_ids
    )
    if unknown_edges:
        raise FinanceMetricRuleError("derived_unknown_dependency", unknown_edges)

    self_cycles = tuple(rule_id for rule_id in derived_ids if rule_id in dependencies[rule_id])
    if self_cycles:
        raise FinanceMetricRuleError("derived_self_cycle", self_cycles)

    available = known_ids.difference(derived_ids)
    pending = list(derived_rules)
    ordered: list[dict[str, Any]] = []
    while pending:
        ready = [
            rule
            for rule in pending
            if all(dependency_id in available for dependency_id in dependencies[rule["id"]])
        ]
        if not ready:
            raise FinanceMetricRuleError(
                "derived_cycle",
                tuple(rule["id"] for rule in pending),
            )
        for rule in ready:
            pending.remove(rule)
            ordered.append(rule)
            available.add(rule["id"])
    return tuple(ordered)


def _validated_manual_overrides(
    rules: Mapping[str, Any],
    manual_overrides: Mapping[str, Decimal | None] | None,
) -> dict[str, Decimal | None]:
    if manual_overrides is None:
        return {}
    if not isinstance(manual_overrides, Mapping):
        raise FinanceMetricInputError(
            "invalid_manual_overrides",
            "manual_overrides",
            "manual overrides must be a mapping",
        )
    known_ids = {rule["id"] for rule in rules.get("manual_metrics", [])}
    validated: dict[str, Decimal | None] = {}
    for metric_id, value in manual_overrides.items():
        if not isinstance(metric_id, str):
            raise FinanceMetricInputError(
                "invalid_manual_override_id",
                "manual_overrides",
                "manual override IDs must be strings",
            )
        if metric_id not in known_ids:
            raise FinanceMetricInputError(
                "unknown_manual_override",
                f"manual_overrides.{metric_id}",
                "manual override ID is not declared by the rule pack",
            )
        if value is not None and not isinstance(value, Decimal):
            raise FinanceMetricInputError(
                "invalid_manual_override_type",
                f"manual_overrides.{metric_id}",
                "manual override must be Decimal or None",
            )
        if isinstance(value, Decimal) and not value.is_finite():
            raise FinanceMetricInputError(
                "non_finite_manual_override",
                f"manual_overrides.{metric_id}",
                "manual override must be finite",
            )
        validated[metric_id] = value
    return validated


def validate_finance_metrics(
    rules: dict[str, Any],
    context: FinanceMetricDataContext,
    metrics: tuple[FinanceMetricResult, ...],
    evidence: FinanceMetricValidationEvidence,
) -> tuple[FinanceMetricValidationResult, ...]:
    divisor = Decimal(rules["metadata"]["conversion_divisor"])
    metrics_by_id = {metric.id: metric for metric in metrics}
    outcomes = {
        **_period_validation_outcomes(evidence.periods),
        "currency.cnx_only": _currency_validation_outcome(evidence),
        "ledger.balance_identity": _ledger_identity_outcome(evidence, divisor),
        "ledger.duplicate_full_code": _duplicate_ledger_outcome(evidence),
        "rules.missing_accounts": _missing_accounts_outcome(rules, context),
        "recon.company_deposit": _additivity_outcome(
            metrics_by_id,
            "balance.deposit.corporate.total::point",
            (
                "balance.deposit.corporate.demand::point",
                "balance.deposit.corporate.term::point",
                "balance.deposit.corporate.structured::point",
            ),
        ),
        "recon.retail_deposit": _additivity_outcome(
            metrics_by_id,
            "balance.deposit.retail.total::point",
            (
                "balance.deposit.retail.demand::point",
                "balance.deposit.retail.term::point",
                "balance.deposit.retail.structured::point",
            ),
        ),
        "recon.personal_loan": _additivity_outcome(
            metrics_by_id,
            "balance.loan.retail.total::point",
            (
                "balance.loan.retail.branch::point",
                "balance.loan.retail.microloan::point",
                "balance.loan.retail.credit_card::point",
            ),
        ),
        "recon.loan_interest": _additivity_outcome(
            metrics_by_id,
            "income.interest.loan.total",
            (
                "income.interest.loan.corporate",
                "income.interest.loan.personal",
                "income.interest.loan.discount_unwind",
            ),
        ),
        "recon.noninterest": _noninterest_outcome(metrics_by_id, context, divisor),
    }
    results: list[FinanceMetricValidationResult] = []
    for rule in rules["validation_rules"]:
        validation_id = rule["id"]
        passed, message, delta_yi, sample = outcomes[validation_id]
        results.append(
            FinanceMetricValidationResult(
                id=validation_id,
                severity=rule["severity"],
                passed=passed,
                message=message,
                delta_yi=delta_yi,
                sample=sample,
            )
        )
    return tuple(results)


ValidationOutcome = tuple[bool, str, Decimal | None, tuple[str, ...]]


def _period_validation_outcomes(
    periods: tuple[FinanceMetricPeriod, ...],
) -> dict[str, ValidationOutcome]:
    period_ids = tuple(period.id for period in periods)
    complete = len(period_ids) == len(EXPECTED_PERIOD_IDS) and set(period_ids) == set(
        EXPECTED_PERIOD_IDS
    )
    if not complete:
        missing = tuple(period_id for period_id in EXPECTED_PERIOD_IDS if period_id not in period_ids)
        sample = missing or ("duplicate_period_id",)
        outcome = (False, "not_evaluable: six unique periods are required", None, sample)
        return {
            "period.same_end_date": outcome,
            "period.ytd_starts_jan1": outcome,
            "period.month_is_calendar_month": outcome,
        }

    by_id = {period.id: period for period in periods}
    end_dates = {period.end for period in periods}
    same_end = len(end_dates) == 1
    same_end_sample = tuple(
        f"{period.id}:{period.end.isoformat()}" for period in periods
    ) if not same_end else ()
    ytd_failures = tuple(
        period_id
        for period_id in YTD_PERIOD_IDS
        if by_id[period_id].start != date(by_id[period_id].end.year, 1, 1)
    )
    month_failures = tuple(
        period_id
        for period_id in MONTH_PERIOD_IDS
        if not _is_complete_calendar_month(by_id[period_id])
    )
    return {
        "period.same_end_date": (
            same_end,
            "all period end dates match" if same_end else "period end dates do not match",
            None,
            same_end_sample,
        ),
        "period.ytd_starts_jan1": (
            not ytd_failures,
            "YTD periods start on January 1" if not ytd_failures else "YTD period start is invalid",
            None,
            ytd_failures,
        ),
        "period.month_is_calendar_month": (
            not month_failures,
            "monthly periods cover a calendar month"
            if not month_failures
            else "monthly period is incomplete",
            None,
            month_failures,
        ),
    }


def _is_complete_calendar_month(period: FinanceMetricPeriod) -> bool:
    expected_start = date(period.end.year, period.end.month, 1)
    expected_end = date(
        period.end.year,
        period.end.month,
        monthrange(period.end.year, period.end.month)[1],
    )
    return period.start == expected_start and period.end == expected_end


def _currency_validation_outcome(
    evidence: FinanceMetricValidationEvidence,
) -> ValidationOutcome:
    currencies = (
        *evidence.consumed_currencies,
        *(row.currency for row in evidence.ledger_balance_rows),
    )
    passed = bool(evidence.consumed_currencies) and all(
        currency == "CNX" for currency in currencies
    )
    invalid = tuple(sorted({currency for currency in currencies if currency != "CNX"}))
    sample = invalid if invalid else (() if passed else ("missing_currency_evidence",))
    return (
        passed,
        "all consumed values use CNX" if passed else "non-CNX or missing currency evidence",
        None,
        sample,
    )


def _ledger_identity_outcome(
    evidence: FinanceMetricValidationEvidence,
    divisor: Decimal,
) -> ValidationOutcome:
    if not evidence.ledger_balance_rows:
        return False, "not_evaluable: ledger rows are required", None, ("missing_ledger_rows",)
    residuals = tuple(
        (
            row,
            row.opening + row.debit - row.credit - row.ending,
        )
        for row in evidence.ledger_balance_rows
    )
    failures = tuple(
        f"{row.source}:{row.row}:{row.code}:delta_yuan={residual}"
        for row, residual in residuals
        if abs(residual) > LEDGER_IDENTITY_TOLERANCE_YUAN
    )
    worst_residual = max(abs(residual) for _row, residual in residuals)
    return (
        not failures,
        "ledger rows balance" if not failures else "ledger balance identity failed",
        worst_residual / divisor,
        failures,
    )


def _duplicate_ledger_outcome(evidence: FinanceMetricValidationEvidence) -> ValidationOutcome:
    grouped: dict[tuple[str, str], list[int]] = {}
    for row in evidence.ledger_balance_rows:
        if row.source == "main" and len(row.code) == 11:
            grouped.setdefault((row.code, row.currency), []).append(row.row)
    duplicates = tuple(
        f"main:{code}:rows={','.join(str(row) for row in rows)}"
        for (code, _currency), rows in grouped.items()
        if len(rows) > 1
    )
    return (
        not duplicates,
        "main full codes are unique" if not duplicates else "duplicate main full codes detected",
        None,
        duplicates,
    )


def _missing_accounts_outcome(
    rules: dict[str, Any],
    context: FinanceMetricDataContext,
) -> ValidationOutcome:
    missing = tuple(
        ":".join(key)
        for key in _referenced_account_keys(rules)
        if not context.resolve(*key).observed
    )
    return (
        not missing,
        "all referenced accounts were observed" if not missing else "referenced accounts are missing",
        None,
        missing,
    )


def _referenced_account_keys(rules: dict[str, Any]) -> tuple[AccountKey, ...]:
    keys: list[AccountKey] = []
    for rule in rules.get("scale_rules", []):
        for basis in rule["available_bases"]:
            terms_by_basis = rule.get("terms_by_basis")
            terms = terms_by_basis[basis] if terms_by_basis is not None else rule["terms"]
            keys.extend((term["source"], basis, term["level"], term["code"]) for term in terms)
    for rule in rules.get("direct_rules", []):
        keys.extend(
            (term["source"], rule["basis"], term["level"], term["code"])
            for term in rule["terms"]
        )
    for rule in rules.get("derived_rules", []):
        keys.extend(
            (term["source"], rule["basis"], term["level"], term["code"])
            for term in rule["calculation"].get("account_terms", [])
        )
    return tuple(dict.fromkeys(keys))


def _reconciled_metric_value(metric: FinanceMetricResult) -> Decimal:
    """类型收窄辅助：调用方已用 unavailable 守卫保证 value 非 None，assert 不改变行为。"""
    assert metric.value is not None
    return metric.value


def _additivity_outcome(
    metrics: dict[str, FinanceMetricResult],
    total_id: str,
    component_ids: tuple[str, ...],
) -> ValidationOutcome:
    required_ids = (total_id, *component_ids)
    unavailable = tuple(
        metric_id
        for metric_id in required_ids
        if metric_id not in metrics or metrics[metric_id].value is None
    )
    if unavailable:
        return False, "not_evaluable: required metric is unavailable", None, unavailable
    delta = _reconciled_metric_value(metrics[total_id]) - sum(
        (_reconciled_metric_value(metrics[metric_id]) for metric_id in component_ids),
        Decimal(0),
    )
    passed = abs(delta) <= RECONCILIATION_TOLERANCE_YI
    return (
        passed,
        "additivity reconciliation passed" if passed else "additivity reconciliation failed",
        delta,
        () if passed else (f"delta_yi={delta}",),
    )


def _noninterest_outcome(
    metrics: dict[str, FinanceMetricResult],
    context: FinanceMetricDataContext,
    divisor: Decimal,
) -> ValidationOutcome:
    # Human: caliber-subject_514_516_517_merge-justified -- governed recon.noninterest
    # explicitly reconciles 511, 512, 527, 513, 516, 517, 518, and 519; this is not
    # JournalType sign or subject-merge logic.
    account_codes = ("511", "512", "527", "513", "516", "517", "518", "519")
    manual_ids = (
        "input.adjustment.noninterest.r091",
        "input.adjustment.noninterest.r112",
        "input.adjustment.noninterest.r116",
        "input.adjustment.noninterest.r120",
    )
    total_id = "income.noninterest.total"
    missing_accounts = tuple(
        f"ledger:cumulative:l1:{code}"
        for code in account_codes
        if not context.resolve("ledger", "cumulative", "l1", code).observed
    )
    unavailable_metrics = tuple(
        metric_id
        for metric_id in (total_id, *manual_ids)
        if metric_id not in metrics or metrics[metric_id].value is None
    )
    if missing_accounts or unavailable_metrics:
        return (
            False,
            "not_evaluable: noninterest source input is unavailable",
            None,
            (*missing_accounts, *unavailable_metrics),
        )
    raw_total_yi = sum(
        (
            context.resolve("ledger", "cumulative", "l1", code).raw_yuan
            for code in account_codes
        ),
        Decimal(0),
    ) / divisor
    expected = -raw_total_yi + sum(
        (_reconciled_metric_value(metrics[metric_id]) for metric_id in manual_ids),
        Decimal(0),
    )
    delta = _reconciled_metric_value(metrics[total_id]) - expected
    passed = abs(delta) <= RECONCILIATION_TOLERANCE_YI
    return (
        passed,
        "noninterest reconciliation passed" if passed else "noninterest reconciliation failed",
        delta,
        () if passed else (f"delta_yi={delta}",),
    )


def finance_metric_ratio(
    numerator: Decimal | None,
    denominator: Decimal | None,
) -> FinanceMetricRatioResult:
    if numerator is None or denominator is None:
        return FinanceMetricRatioResult(value=None, reason="missing_reference")
    if denominator == 0:
        return FinanceMetricRatioResult(value=None, reason="zero_denominator")
    return FinanceMetricRatioResult(value=numerator / abs(denominator), reason=None)


def finance_metric_cumulative_mom(
    *,
    current_cumulative: Decimal | None,
    prior_cumulative: Decimal | None,
    two_month_prior_cumulative: Decimal | None,
) -> FinanceMetricCumulativeMomResult:
    if (
        current_cumulative is None
        or prior_cumulative is None
        or two_month_prior_cumulative is None
    ):
        return FinanceMetricCumulativeMomResult(
            current_month=None,
            previous_month=None,
            delta=None,
            rate=None,
            reason="missing_reference",
        )
    current_month = current_cumulative - prior_cumulative
    previous_month = prior_cumulative - two_month_prior_cumulative
    delta = current_month - previous_month
    ratio = finance_metric_ratio(delta, previous_month)
    return FinanceMetricCumulativeMomResult(
        current_month=current_month,
        previous_month=previous_month,
        delta=delta,
        rate=ratio.value,
        reason=ratio.reason,
    )


def finance_metric_budget_progress(
    actual: Decimal | None,
    budget: Decimal | None,
) -> FinanceMetricRatioResult:
    return finance_metric_ratio(actual, budget)


def finance_metric_time_progress(*, days: int, year_days: int) -> FinanceMetricRatioResult:
    _validate_positive_days(days, year_days)
    return FinanceMetricRatioResult(
        value=Decimal(days) / Decimal(year_days),
        reason=None,
    )


def finance_metric_mix(
    part: Decimal | None,
    total: Decimal | None,
) -> FinanceMetricRatioResult:
    return finance_metric_ratio(part, total)


def finance_metric_year_days(as_of: date) -> int:
    return 366 if isleap(as_of.year) else 365


def finance_metric_elapsed_days(start: date, end: date) -> int:
    if start > end:
        raise ValueError("start must not be after end")
    return (end - start).days + 1


def finance_metric_annualize(
    value: Decimal | None,
    *,
    days: int,
    year_days: int,
) -> Decimal | None:
    _validate_positive_days(days, year_days)
    if value is None:
        return None
    return value / Decimal(days) * Decimal(year_days)


def finance_metric_annualized_rate(
    *,
    amount_yi: Decimal | None,
    average_balance_yi: Decimal | None,
    days: int,
    year_days: int,
) -> FinanceMetricRatioResult:
    _validate_positive_days(days, year_days)
    ratio = finance_metric_ratio(amount_yi, average_balance_yi)
    if ratio.value is None:
        return ratio
    return FinanceMetricRatioResult(
        value=ratio.value * Decimal(year_days) / Decimal(days),
        reason=None,
    )


def finance_metric_three_factor_attribution(
    *,
    prior_balance_yi: Decimal,
    current_balance_yi: Decimal,
    prior_rate: Decimal,
    current_rate: Decimal,
    days: int,
    year_days: int,
) -> FinanceMetricThreeFactorAttribution:
    _validate_positive_days(days, year_days)
    factor = Decimal(days) / Decimal(year_days)
    balance_change = current_balance_yi - prior_balance_yi
    rate_change = current_rate - prior_rate
    volume = balance_change * prior_rate * factor
    rate = prior_balance_yi * rate_change * factor
    cross = balance_change * rate_change * factor
    total_change = (
        current_balance_yi * current_rate * factor
        - prior_balance_yi * prior_rate * factor
    )
    return FinanceMetricThreeFactorAttribution(
        volume=volume,
        rate=rate,
        cross=cross,
        total_change=total_change,
        reconciliation_delta=volume + rate + cross - total_change,
    )


def _validate_positive_days(days: int, year_days: int) -> None:
    if days <= 0:
        raise ValueError("days must be positive")
    if year_days <= 0:
        raise ValueError("year_days must be positive")


def build_finance_metric_idempotency_key(
    *,
    ledger_sha256: str,
    daily_sha256: str,
    rules: Mapping[str, Any],
    manual_overrides: Mapping[str, Decimal | None] | None,
    references: Mapping[str, Any] | None,
    analysis_requests: list[Any] | tuple[Any, ...] | None,
    include_lineage: bool,
    requested_metric_id: str | None,
    report_month: str | None = None,
) -> str:
    ledger_hash = _validated_sha256(ledger_sha256, "ledger_sha256")
    daily_hash = _validated_sha256(daily_sha256, "daily_sha256")
    rule_hash = _validated_sha256(rules.get("rule_hash"), "rules.rule_hash")
    metadata = rules.get("metadata")
    rule_version = metadata.get("rule_version") if isinstance(metadata, Mapping) else None
    if not isinstance(rule_version, str) or not rule_version:
        raise FinanceMetricInputError(
            "invalid_rule_version",
            "rules.metadata.rule_version",
            "rule version must be a non-empty string",
        )
    overrides = _validated_manual_overrides(rules, manual_overrides)
    if references is not None and not isinstance(references, Mapping):
        raise FinanceMetricInputError(
            "invalid_references",
            "references",
            "references must be a mapping or None",
        )
    if analysis_requests is not None and not isinstance(analysis_requests, (list, tuple)):
        raise FinanceMetricInputError(
            "invalid_analysis_requests",
            "analysis_requests",
            "analysis requests must be a list, tuple, or None",
        )
    if not isinstance(include_lineage, bool):
        raise FinanceMetricInputError(
            "invalid_include_lineage",
            "include_lineage",
            "include_lineage must be bool",
        )
    if requested_metric_id is not None and not isinstance(requested_metric_id, str):
        raise FinanceMetricInputError(
            "invalid_requested_metric_id",
            "requested_metric_id",
            "requested metric ID must be a string or None",
        )
    if report_month is not None:
        if not isinstance(report_month, str) or re.fullmatch(r"\d{6}", report_month) is None:
            raise FinanceMetricInputError(
                "invalid_report_month",
                "report_month",
                "report month must be a real YYYYMM month or None",
            )
        try:
            date(int(report_month[:4]), int(report_month[4:]), 1)
        except ValueError as exc:
            raise FinanceMetricInputError(
                "invalid_report_month",
                "report_month",
                "report month must be a real YYYYMM month or None",
            ) from exc
    payload = {
        "engine_contract_version": FINANCE_METRIC_ENGINE_CONTRACT_VERSION,
        "ledger_sha256": ledger_hash,
        "daily_sha256": daily_hash,
        "rule_hash": rule_hash,
        "rule_version": rule_version,
        "manual_overrides": overrides,
        "references": references or {},
        "analysis_requests": analysis_requests or [],
        "include_lineage": include_lineage,
        "requested_metric_id": requested_metric_id,
        "report_month": report_month,
    }
    canonical = _canonical_idempotency_value(payload)
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validated_sha256(value: Any, path: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-fA-F]{64}", value) is None:
        raise FinanceMetricInputError(
            "invalid_sha256",
            path,
            "SHA-256 must be exactly 64 hexadecimal characters",
        )
    return value.lower()


def _canonical_idempotency_value(value: Any, path: str = "$") -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise FinanceMetricInputError(
                "non_finite_decimal",
                path,
                "non-finite Decimal is forbidden in idempotency input",
            )
        return {"$decimal": _canonical_decimal_text(value)}
    if isinstance(value, date) and not isinstance(value, datetime):
        return {"$date": value.isoformat()}
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise FinanceMetricInputError(
                "non_string_mapping_key",
                path,
                "idempotency mappings require string keys",
            )
        return {
            key: _canonical_idempotency_value(value[key], f"{path}.{key}")
            for key in sorted(value)
        }
    if isinstance(value, (list, tuple)):
        return [
            _canonical_idempotency_value(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, float):
        raise FinanceMetricInputError(
            "float_not_supported",
            path,
            "float is forbidden in idempotency input",
        )
    raise FinanceMetricInputError(
        "unsupported_canonical_type",
        path,
        f"unsupported idempotency input type: {type(value).__name__}",
    )


def _canonical_decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def load_finance_metric_rules(
    path: str | Path | None = None,
    *,
    rule_version: str | None = None,
) -> dict[str, Any]:
    if path is not None and rule_version is not None:
        raise ValueError("path and rule_version cannot be provided together")
    requested_version: str | None = None
    if path is None:
        requested_version = rule_version or DEFAULT_RULE_VERSION
        try:
            rule_path = RULE_ASSETS[requested_version]
        except KeyError as exc:
            raise ValueError(f"unsupported finance metric rule_version: {requested_version!r}") from exc
    else:
        rule_path = Path(path)
    raw = rule_path.read_bytes()
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("finance metric rules must be a JSON object")

    metadata = payload.get("metadata")
    selected_version = metadata.get("rule_version") if isinstance(metadata, dict) else None
    if selected_version not in RULE_ASSETS:
        raise ValueError(f"unsupported metadata.rule_version: {selected_version!r}")
    if requested_version is not None and selected_version != requested_version:
        raise ValueError(
            f"requested rule_version {requested_version!r} does not match "
            f"asset metadata.rule_version {selected_version!r}"
        )
    expected_metadata = {"rule_version": selected_version, **EXPECTED_METADATA_BASE}
    expected_source_hashes = EXPECTED_SOURCE_HASHES_BY_VERSION[selected_version]
    _validate_metadata(payload, expected_metadata, expected_source_hashes)
    _validate_code_and_weight_strings(payload)
    _validate_rule_counts(payload)

    rule_hash = hashlib.sha256(raw).hexdigest()
    approved_rule_hash = APPROVED_RULE_SHA256_BY_VERSION[selected_version]
    if rule_hash != approved_rule_hash:
        raise ValueError(
            f"finance metric rule asset SHA-256 {rule_hash} does not match approved "
            f"SHA-256 {approved_rule_hash}; "
            "create a new approved asset and upgrade metadata.rule_version"
        )
    return {**payload, "rule_hash": rule_hash}


def _validate_metadata(
    payload: dict[str, Any],
    expected_metadata: Mapping[str, str],
    expected_source_hashes: Mapping[str, str],
) -> None:
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be an object")
    for metadata_field, expected in expected_metadata.items():
        if metadata.get(metadata_field) != expected:
            raise ValueError(f"metadata.{metadata_field} must equal {expected!r}")
    derived_from = metadata.get("derived_from")
    if not isinstance(derived_from, list):
        raise ValueError("metadata.derived_from must be a list")
    if len(derived_from) != len(expected_source_hashes) or not all(
        isinstance(source, dict) for source in derived_from
    ):
        raise ValueError("metadata.derived_from source records must match the frozen contract")
    source_hashes = {source.get("file"): source.get("sha256") for source in derived_from}
    if source_hashes != expected_source_hashes:
        raise ValueError("metadata.derived_from source records must match the frozen contract")
    if not isinstance(metadata.get("important_limitations"), list):
        raise ValueError("metadata.important_limitations must be a list")


def _validate_code_and_weight_strings(value: Any, path: str = "rules") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in {"code", "weight"} and not isinstance(child, str):
                raise ValueError(f"{child_path}: {key} must be a string")
            _validate_code_and_weight_strings(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_code_and_weight_strings(child, f"{path}[{index}]")


def _validate_rule_counts(payload: dict[str, Any]) -> None:
    validation_rules = _rule_list(payload, "validation_rules")
    if len(validation_rules) != EXPECTED_VALIDATION_RULES:
        raise ValueError("validation_rules must contain exactly 12 rules")
    validation_ids = [_rule_id(rule, "validation_rules") for rule in validation_rules]
    if len(validation_ids) != len(set(validation_ids)) or set(validation_ids) != EXPECTED_VALIDATION_IDS:
        raise ValueError("validation rule IDs must match the frozen contract and be unique")

    expanded_ids: list[str] = []
    rules_by_section = {
        section: _rule_list(payload, section)
        for section in EXPECTED_SECTION_COUNTS
    }
    for rule in rules_by_section["scale_rules"]:
        rule_id = _rule_id(rule, "scale_rules")
        bases = rule.get("available_bases")
        if not isinstance(bases, list) or not all(isinstance(basis, str) and basis for basis in bases):
            raise ValueError(f"scale rule {rule_id} must define string available_bases")
        expanded_ids.extend(f"{rule_id}::{basis}" for basis in bases)

    for section in ("direct_rules", "manual_metrics", "derived_rules"):
        expanded_ids.extend(_rule_id(rule, section) for rule in rules_by_section[section])

    if len(expanded_ids) != EXPECTED_EXPANDED_OUTPUTS:
        raise ValueError("expanded output count must be 186")
    if len(expanded_ids) != len(set(expanded_ids)):
        raise ValueError("expanded output IDs must be unique")
    for section, expected_count in EXPECTED_SECTION_COUNTS.items():
        if len(rules_by_section[section]) != expected_count:
            raise ValueError(f"{section} must contain exactly {expected_count} rules")


def _rule_list(payload: dict[str, Any], section: str) -> list[dict[str, Any]]:
    rules = payload.get(section)
    if not isinstance(rules, list) or not all(isinstance(rule, dict) for rule in rules):
        raise ValueError(f"{section} must be a list of rule objects")
    return rules


def _rule_id(rule: dict[str, Any], section: str) -> str:
    rule_id = rule.get("id")
    if not isinstance(rule_id, str) or not rule_id:
        raise ValueError(f"{section} rule id must be a non-empty string")
    return rule_id
