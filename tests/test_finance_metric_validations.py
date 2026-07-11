from __future__ import annotations

import importlib
from dataclasses import replace
from datetime import date
from decimal import Decimal
from typing import Any


EXPECTED_VALIDATION_IDS = (
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
)


def _module():
    return importlib.import_module("backend.app.core_finance.finance_metric_engine")


def _rules() -> dict[str, Any]:
    module = _module()
    frozen = module.load_finance_metric_rules()
    return {
        "metadata": {"conversion_divisor": "100000000"},
        "validation_rules": frozen["validation_rules"],
        "scale_rules": [
            {
                "id": "scale.observed",
                "available_bases": ["point"],
                "terms": [{"source": "main", "level": "l1", "code": "101", "weight": "1"}],
            }
        ],
        "direct_rules": [
            {
                "id": "direct.observed",
                "basis": "cumulative",
                "terms": [
                    {"source": "ledger", "level": "l1", "code": "501", "weight": "1"}
                ],
            }
        ],
        "manual_metrics": [],
        "derived_rules": [
            {
                "id": "derived.observed",
                "basis": "cumulative",
                "calculation": {
                    "account_terms": [
                        {"source": "ledger", "level": "l1", "code": "601", "weight": "1"}
                    ]
                },
            }
        ],
    }


def _periods(module) -> tuple[Any, ...]:
    return (
        module.FinanceMetricPeriod("ledger", date(2026, 6, 1), date(2026, 6, 30)),
        module.FinanceMetricPeriod("daily_ytd", date(2026, 1, 1), date(2026, 6, 30)),
        module.FinanceMetricPeriod("daily_month", date(2026, 6, 1), date(2026, 6, 30)),
        module.FinanceMetricPeriod("microloan_ytd", date(2026, 1, 1), date(2026, 6, 30)),
        module.FinanceMetricPeriod("microloan_month", date(2026, 6, 1), date(2026, 6, 30)),
        module.FinanceMetricPeriod("microloan_ledger", date(2026, 6, 1), date(2026, 6, 30)),
    )


def _ledger_row(module, *, row: int = 2, code: str = "50101000001", ending: str = "11"):
    return module.FinanceMetricLedgerBalanceRow(
        source="main",
        row=row,
        code=code,
        currency="CNX",
        opening=Decimal("10"),
        debit=Decimal("3"),
        credit=Decimal("2"),
        ending=Decimal(ending),
    )


def _evidence(module, *, periods=None, currencies=("CNX",), ledger_rows=None):
    return module.FinanceMetricValidationEvidence(
        periods=_periods(module) if periods is None else tuple(periods),
        consumed_currencies=tuple(currencies),
        ledger_balance_rows=(
            (_ledger_row(module), _ledger_row(module, row=3, code="50201000001"))
            if ledger_rows is None
            else tuple(ledger_rows)
        ),
    )


def _context(module, *, include_derived_account: bool = True):
    observations = {
        ("main", "point", "l1", "101"): module.AccountObservation(Decimal("0")),
        ("ledger", "cumulative", "l1", "501"): module.AccountObservation(Decimal("0")),
    }
    if include_derived_account:
        observations[("ledger", "cumulative", "l1", "601")] = module.AccountObservation(
            Decimal("0")
        )
    for code in ("511", "512", "527", "513", "516", "517", "518", "519"):
        observations[("ledger", "cumulative", "l1", code)] = module.AccountObservation(
            Decimal("100000000")
        )
    return module.FinanceMetricDataContext(observations)


def _metric(module, metric_id: str, value: Decimal | None):
    return module.FinanceMetricResult(
        id=metric_id,
        name=metric_id,
        category="test",
        basis="cumulative",
        unit="亿元",
        value=value,
        status="error" if value is None else "ok",
        reasons=("unavailable",) if value is None else (),
        lineage=None,
    )


def _metrics(module) -> tuple[Any, ...]:
    values = {
        "balance.deposit.corporate.demand::point": "1",
        "balance.deposit.corporate.term::point": "2",
        "balance.deposit.corporate.structured::point": "3",
        "balance.deposit.corporate.total::point": "6",
        "balance.deposit.retail.demand::point": "1",
        "balance.deposit.retail.term::point": "2",
        "balance.deposit.retail.structured::point": "3",
        "balance.deposit.retail.total::point": "6",
        "balance.loan.retail.branch::point": "1",
        "balance.loan.retail.microloan::point": "2",
        "balance.loan.retail.credit_card::point": "3",
        "balance.loan.retail.total::point": "6",
        "income.interest.loan.corporate": "1",
        "income.interest.loan.personal": "2",
        "income.interest.loan.discount_unwind": "3",
        "income.interest.loan.total": "6",
        "input.adjustment.noninterest.r091": "1",
        "input.adjustment.noninterest.r112": "2",
        "input.adjustment.noninterest.r116": "3",
        "input.adjustment.noninterest.r120": "4",
        "income.noninterest.total": "2",
    }
    return tuple(_metric(module, metric_id, Decimal(value)) for metric_id, value in values.items())


def _validate(*, rules=None, context=None, metrics=None, evidence=None):
    module = _module()
    assert hasattr(module, "validate_finance_metrics"), "finance metric validations are not implemented"
    return module.validate_finance_metrics(
        _rules() if rules is None else rules,
        _context(module) if context is None else context,
        _metrics(module) if metrics is None else metrics,
        _evidence(module) if evidence is None else evidence,
    )


def test_validations_return_declared_order_severity_and_pass_consistent_evidence() -> None:
    module = _module()
    assert hasattr(module, "FinanceMetricPeriod"), "typed period evidence is not implemented"
    assert hasattr(module, "FinanceMetricLedgerBalanceRow"), "typed ledger evidence is not implemented"
    assert hasattr(module, "FinanceMetricValidationResult"), "typed validation result is not implemented"

    results = _validate()

    assert tuple(result.id for result in results) == EXPECTED_VALIDATION_IDS
    assert tuple(result.severity for result in results) == (
        "error",
        "error",
        "error",
        "error",
        "error",
        "warning",
        "warning",
        "warning",
        "warning",
        "warning",
        "warning",
        "warning",
    )
    assert all(result.passed for result in results)


def test_missing_or_invalid_period_evidence_never_passes_period_checks() -> None:
    module = _module()
    missing_period = tuple(period for period in _periods(module) if period.id != "microloan_ytd")
    missing_results = _validate(evidence=_evidence(module, periods=missing_period))
    assert all(not result.passed for result in missing_results[:3])

    invalid_periods = list(_periods(module))
    invalid_periods[1] = module.FinanceMetricPeriod(
        "daily_ytd", date(2026, 1, 2), date(2026, 6, 30)
    )
    invalid_periods[2] = module.FinanceMetricPeriod(
        "daily_month", date(2026, 6, 1), date(2026, 6, 29)
    )
    invalid_results = _validate(evidence=_evidence(module, periods=invalid_periods))
    assert invalid_results[0].passed is False
    assert invalid_results[1].passed is False
    assert invalid_results[2].passed is False


def test_currency_identity_and_duplicate_validations_use_typed_source_evidence() -> None:
    module = _module()
    assert _validate(evidence=_evidence(module, currencies=()))[3].passed is False
    assert _validate(evidence=_evidence(module, currencies=("CNX", "CNY")))[3].passed is False
    cny_ledger_row = replace(_ledger_row(module), currency="CNY")
    assert _validate(evidence=_evidence(module, ledger_rows=(cny_ledger_row,)))[3].passed is False

    at_tolerance = _ledger_row(module, ending="10.99")
    beyond_tolerance = _ledger_row(module, ending="10.9899")
    assert _validate(evidence=_evidence(module, ledger_rows=(at_tolerance,)))[4].passed is True
    identity_failure = _validate(evidence=_evidence(module, ledger_rows=(beyond_tolerance,)))[4]
    assert identity_failure.passed is False
    assert identity_failure.delta_yi == Decimal("0.0101") / Decimal("100000000")

    duplicate_rows = (
        _ledger_row(module, row=2),
        _ledger_row(module, row=3),
        replace(_ledger_row(module, row=4), source="microloan"),
    )
    duplicate_failure = _validate(evidence=_evidence(module, ledger_rows=duplicate_rows))[5]
    assert duplicate_failure.passed is False
    assert duplicate_failure.sample == ("main:50101000001:rows=2,3",)


def test_missing_accounts_scans_scale_direct_and_derived_and_preserves_observed_zero() -> None:
    module = _module()
    missing_result = _validate(context=_context(module, include_derived_account=False))[6]
    assert missing_result.passed is False
    assert missing_result.sample == ("ledger:cumulative:l1:601",)

    observed_zero_result = _validate(context=_context(module, include_derived_account=True))[6]
    assert observed_zero_result.passed is True


def test_reconciliations_apply_tolerance_and_none_is_not_evaluable() -> None:
    module = _module()
    metrics = list(_metrics(module))
    corporate_index = next(
        index for index, metric in enumerate(metrics) if metric.id == "balance.deposit.corporate.total::point"
    )
    metrics[corporate_index] = replace(metrics[corporate_index], value=Decimal("6.000001"))
    assert _validate(metrics=tuple(metrics))[7].passed is True

    metrics[corporate_index] = replace(metrics[corporate_index], value=Decimal("6.0000011"))
    beyond_tolerance = _validate(metrics=tuple(metrics))[7]
    assert beyond_tolerance.passed is False
    assert beyond_tolerance.delta_yi == Decimal("0.0000011")

    metrics[corporate_index] = replace(
        metrics[corporate_index], value=None, status="error", reasons=("unavailable",)
    )
    all_results = _validate(metrics=tuple(metrics))
    not_evaluable = all_results[7]
    assert len(all_results) == 12
    assert not_evaluable.passed is False
    assert not_evaluable.delta_yi is None
    assert "not_evaluable" in not_evaluable.message


def test_noninterest_reconciliation_uses_raw_l1_algebra_not_derived_self_proof() -> None:
    module = _module()
    metrics = list(_metrics(module))
    total_index = next(
        index for index, metric in enumerate(metrics) if metric.id == "income.noninterest.total"
    )
    metrics[total_index] = replace(metrics[total_index], value=Decimal("999"))

    result = _validate(metrics=tuple(metrics))[11]

    assert result.passed is False
    assert result.delta_yi == Decimal("997")
