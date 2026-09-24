from __future__ import annotations

import importlib
from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest


def _empty_rules() -> dict[str, Any]:
    return {
        "metadata": {"conversion_divisor": "100000000"},
        "scale_rules": [],
        "direct_rules": [],
        "manual_metrics": [],
        "derived_rules": [],
    }


def _derived_rule(metric_id: str, *dependencies: str) -> dict[str, Any]:
    return {
        "id": metric_id,
        "name": metric_id,
        "category": "营业收入",
        "unit": "亿元",
        "basis": "cumulative",
        "calculation": {
            "type": "linear",
            "metric_terms": [
                {"metric_id": dependency, "weight": "1"} for dependency in dependencies
            ],
        },
    }


def test_data_context_distinguishes_missing_account_from_observed_zero() -> None:
    module = importlib.import_module("backend.app.core_finance.finance_metric_engine")
    assert hasattr(module, "AccountObservation"), "AccountObservation is not implemented"
    assert hasattr(module, "FinanceMetricDataContext"), "FinanceMetricDataContext is not implemented"

    account_key = ("main", "point", "l1", "201")
    context = module.FinanceMetricDataContext(
        {account_key: module.AccountObservation(raw_yuan=Decimal("0"))}
    )

    observed = context.resolve(*account_key)
    missing = context.resolve("main", "point", "l1", "999")

    assert observed.raw_yuan == Decimal("0")
    assert observed.observed is True
    assert missing.raw_yuan == Decimal("0")
    assert missing.observed is False


def test_scale_evaluator_uses_basis_terms_divisor_and_frozen_order() -> None:
    module = importlib.import_module("backend.app.core_finance.finance_metric_engine")
    assert hasattr(module, "evaluate_finance_metrics"), "finance metric evaluator is not implemented"

    rules = _empty_rules()
    rules["scale_rules"] = [
        {
            "id": "scale.demo",
            "name": "规模示例",
            "category": "规模",
            "unit": "亿元",
            "available_bases": ["point", "ytd_average", "month_average"],
            "terms_by_basis": {
                "point": [{"source": "main", "level": "l1", "code": "101", "weight": "1"}],
                "ytd_average": [
                    {"source": "main", "level": "l1", "code": "102", "weight": "-1"}
                ],
                "month_average": [
                    {"source": "main", "level": "l1", "code": "103", "weight": "1"}
                ],
            },
        }
    ]
    context = module.FinanceMetricDataContext(
        {
            ("main", "point", "l1", "101"): module.AccountObservation(Decimal("100000000")),
            ("main", "ytd_average", "l1", "102"): module.AccountObservation(Decimal("200000000")),
            ("main", "month_average", "l1", "103"): module.AccountObservation(Decimal("123456789")),
        }
    )

    results = module.evaluate_finance_metrics(rules, context, include_lineage=False)

    assert tuple(result.id for result in results) == (
        "scale.demo::point",
        "scale.demo::ytd_average",
        "scale.demo::month_average",
    )
    assert tuple(result.basis for result in results) == ("point", "ytd_average", "month_average")
    assert tuple(result.value for result in results) == (
        Decimal("1"),
        Decimal("-2"),
        Decimal("1.23456789"),
    )
    assert all(result.unit == "亿元" for result in results)
    assert all(result.status == "ok" for result in results)
    assert all(result.lineage is None for result in results)


def test_direct_evaluator_distinguishes_observed_zero_from_missing_account() -> None:
    module = importlib.import_module("backend.app.core_finance.finance_metric_engine")
    rules = _empty_rules()
    rules["direct_rules"] = [
        {
            "id": "direct.observed-zero",
            "name": "显式零",
            "category": "利息收入",
            "unit": "亿元",
            "basis": "cumulative",
            "terms": [{"source": "ledger", "level": "l1", "code": "501", "weight": "1"}],
        },
        {
            "id": "direct.missing",
            "name": "缺失账户",
            "category": "利息收入",
            "unit": "亿元",
            "basis": "cumulative",
            "terms": [{"source": "ledger", "level": "l1", "code": "999", "weight": "-1"}],
        },
    ]
    context = module.FinanceMetricDataContext(
        {
            ("ledger", "cumulative", "l1", "501"): module.AccountObservation(Decimal("0")),
        }
    )

    results = module.evaluate_finance_metrics(rules, context, include_lineage=False)

    assert tuple(result.id for result in results) == ("direct.observed-zero", "direct.missing")
    assert results[0].value == Decimal("0")
    assert results[0].status == "ok"
    assert results[0].reasons == ()
    assert results[1].value == Decimal("0")
    assert results[1].status == "warning"
    assert results[1].reasons == ("missing_account:ledger:cumulative:l1:999",)


def test_manual_evaluator_distinguishes_explicit_zero_from_required_default() -> None:
    module = importlib.import_module("backend.app.core_finance.finance_metric_engine")
    rules = _empty_rules()
    rules["manual_metrics"] = [
        {
            "id": "manual.explicit-zero",
            "name": "显式零调整",
            "category": "手工调整",
            "unit": "亿元",
            "basis": "cumulative",
            "default": "0",
            "manual_required": True,
        },
        {
            "id": "manual.explicit-value",
            "name": "显式非零调整",
            "category": "手工调整",
            "unit": "亿元",
            "basis": "cumulative",
            "default": "0",
            "manual_required": True,
        },
        {
            "id": "manual.default",
            "name": "缺失调整",
            "category": "手工调整",
            "unit": "亿元",
            "basis": "cumulative",
            "default": "0",
            "manual_required": True,
        },
    ]

    results = module.evaluate_finance_metrics(
        rules,
        module.FinanceMetricDataContext(),
        manual_overrides={
            "manual.explicit-zero": Decimal("0"),
            "manual.explicit-value": Decimal("1.25"),
        },
        include_lineage=False,
    )

    assert tuple(result.id for result in results) == (
        "manual.explicit-zero",
        "manual.explicit-value",
        "manual.default",
    )
    assert tuple(result.value for result in results) == (
        Decimal("0"),
        Decimal("1.25"),
        Decimal("0"),
    )
    assert tuple(result.status for result in results) == ("ok", "ok", "manual_default")
    assert results[2].reasons == ("manual_required_not_supplied",)


def test_derived_linear_combines_account_and_metric_terms_without_rescaling_metrics() -> None:
    module = importlib.import_module("backend.app.core_finance.finance_metric_engine")
    rules = _empty_rules()
    rules["direct_rules"] = [
        {
            "id": "direct.base",
            "name": "直接基础值",
            "category": "利息收入",
            "unit": "亿元",
            "basis": "cumulative",
            "terms": [{"source": "ledger", "level": "l1", "code": "501", "weight": "-1"}],
        }
    ]
    rules["manual_metrics"] = [
        {
            "id": "manual.base",
            "name": "手工基础值",
            "category": "手工调整",
            "unit": "亿元",
            "basis": "cumulative",
            "default": "0",
            "manual_required": True,
        }
    ]
    rules["derived_rules"] = [
        {
            "id": "derived.mix",
            "name": "派生混合值",
            "category": "营业收入",
            "unit": "亿元",
            "basis": "cumulative",
            "calculation": {
                "type": "linear",
                "account_terms": [
                    {"source": "ledger", "level": "l1", "code": "600", "weight": "1"}
                ],
                "metric_terms": [
                    {"metric_id": "direct.base", "weight": "-2"},
                    {"metric_id": "manual.base", "weight": "1"},
                ],
            },
        }
    ]
    context = module.FinanceMetricDataContext(
        {
            ("ledger", "cumulative", "l1", "501"): module.AccountObservation(Decimal("200000000")),
            ("ledger", "cumulative", "l1", "600"): module.AccountObservation(Decimal("300000000")),
        }
    )

    results = module.evaluate_finance_metrics(
        rules,
        context,
        manual_overrides={"manual.base": Decimal("1")},
        include_lineage=False,
    )

    assert tuple(result.id for result in results) == ("direct.base", "manual.base", "derived.mix")
    assert tuple(result.value for result in results) == (Decimal("-2"), Decimal("1"), Decimal("8"))
    assert results[-1].status == "ok"
    assert results[-1].reasons == ()


def test_derived_metrics_propagate_missing_and_manual_default_reasons() -> None:
    module = importlib.import_module("backend.app.core_finance.finance_metric_engine")
    rules = _empty_rules()
    rules["direct_rules"] = [
        {
            "id": "direct.missing",
            "name": "缺失直接值",
            "category": "利息收入",
            "unit": "亿元",
            "basis": "cumulative",
            "terms": [{"source": "ledger", "level": "l1", "code": "999", "weight": "1"}],
        }
    ]
    rules["manual_metrics"] = [
        {
            "id": "manual.default",
            "name": "缺失手工值",
            "category": "手工调整",
            "unit": "亿元",
            "basis": "cumulative",
            "default": "0",
            "manual_required": True,
        }
    ]
    rules["derived_rules"] = [
        {
            "id": "derived.first",
            "name": "一级派生",
            "category": "营业收入",
            "unit": "亿元",
            "basis": "cumulative",
            "calculation": {
                "type": "linear",
                "account_terms": [
                    {"source": "ledger", "level": "l1", "code": "888", "weight": "1"}
                ],
                "metric_terms": [
                    {"metric_id": "direct.missing", "weight": "1"},
                    {"metric_id": "manual.default", "weight": "1"},
                ],
            },
        },
        {
            "id": "derived.second",
            "name": "二级派生",
            "category": "营业收入",
            "unit": "亿元",
            "basis": "cumulative",
            "calculation": {
                "type": "linear",
                "metric_terms": [{"metric_id": "derived.first", "weight": "1"}],
            },
        },
    ]

    results = module.evaluate_finance_metrics(rules, module.FinanceMetricDataContext(), include_lineage=False)
    first = next(result for result in results if result.id == "derived.first")
    second = next(result for result in results if result.id == "derived.second")

    assert first.value == Decimal("0")
    assert first.status == "warning"
    assert first.reasons == (
        "missing_account:ledger:cumulative:l1:888",
        "dependency:direct.missing:missing_account:ledger:cumulative:l1:999",
        "dependency:manual.default:manual_required_not_supplied",
    )
    assert second.value == Decimal("0")
    assert second.status == "warning"
    assert second.reasons == tuple(f"dependency:derived.first:{reason}" for reason in first.reasons)


def test_derived_metric_does_not_treat_unavailable_dependency_as_zero() -> None:
    module = importlib.import_module("backend.app.core_finance.finance_metric_engine")
    rules = _empty_rules()
    rules["manual_metrics"] = [
        {
            "id": "manual.unavailable",
            "name": "不可用手工值",
            "category": "手工调整",
            "unit": "亿元",
            "basis": "cumulative",
            "default": "0",
            "manual_required": True,
        }
    ]
    rules["derived_rules"] = [
        {
            "id": "derived.unavailable",
            "name": "不可用派生值",
            "category": "营业收入",
            "unit": "亿元",
            "basis": "cumulative",
            "calculation": {
                "type": "linear",
                "metric_terms": [{"metric_id": "manual.unavailable", "weight": "1"}],
            },
        }
    ]

    results = module.evaluate_finance_metrics(
        rules,
        module.FinanceMetricDataContext(),
        manual_overrides={"manual.unavailable": None},
        include_lineage=True,
    )

    assert results[0].value is None
    assert results[0].status == "error"
    assert results[0].reasons == ("manual_override_unavailable",)
    assert results[1].value is None
    assert results[1].status == "error"
    assert results[1].reasons == (
        "dependency:manual.unavailable:manual_override_unavailable",
    )
    assert results[1].lineage == (
        module.FinanceMetricMetricLineage(
            metric_id="manual.unavailable",
            weight=Decimal("1"),
            metric_value_yi=None,
            contribution_yi=None,
            dependency_status="error",
        ),
    )


@pytest.mark.parametrize(
    ("derived_rules", "expected_code"),
    [
        ([_derived_rule("derived.unknown", "missing.metric")], "derived_unknown_dependency"),
        ([_derived_rule("derived.self", "derived.self")], "derived_self_cycle"),
        (
            [_derived_rule("derived.a", "derived.b"), _derived_rule("derived.b", "derived.a")],
            "derived_cycle",
        ),
    ],
)
def test_rule_graph_validation_distinguishes_dependency_errors(
    derived_rules: list[dict[str, Any]], expected_code: str
) -> None:
    module = importlib.import_module("backend.app.core_finance.finance_metric_engine")
    assert hasattr(module, "FinanceMetricRuleError"), "typed rule graph error is not implemented"
    rules = _empty_rules()
    rules["derived_rules"] = derived_rules

    with pytest.raises(module.FinanceMetricRuleError) as exc_info:
        module.evaluate_finance_metrics(rules, module.FinanceMetricDataContext())

    assert exc_info.value.code == expected_code


def test_derived_rules_evaluate_topologically_but_return_in_frozen_order() -> None:
    module = importlib.import_module("backend.app.core_finance.finance_metric_engine")
    rules = _empty_rules()
    rules["direct_rules"] = [
        {
            "id": "direct.base",
            "name": "基础值",
            "category": "利息收入",
            "unit": "亿元",
            "basis": "cumulative",
            "terms": [{"source": "ledger", "level": "l1", "code": "501", "weight": "1"}],
        }
    ]
    rules["derived_rules"] = [
        _derived_rule("derived.final", "derived.base"),
        _derived_rule("derived.base", "direct.base"),
    ]
    context = module.FinanceMetricDataContext(
        {
            ("ledger", "cumulative", "l1", "501"): module.AccountObservation(Decimal("100000000")),
        }
    )

    results = module.evaluate_finance_metrics(rules, context, include_lineage=False)

    assert tuple(result.id for result in results) == (
        "direct.base",
        "derived.final",
        "derived.base",
    )
    assert tuple(result.value for result in results) == (Decimal("1"), Decimal("1"), Decimal("1"))


def test_typed_lineage_is_frozen_ordered_and_carries_account_evidence() -> None:
    module = importlib.import_module("backend.app.core_finance.finance_metric_engine")
    assert hasattr(module, "FinanceMetricAccountLineage"), "typed account lineage is not implemented"
    assert hasattr(module, "FinanceMetricMetricLineage"), "typed metric lineage is not implemented"
    assert hasattr(module, "FinanceMetricManualLineage"), "typed manual lineage is not implemented"

    rules = _empty_rules()
    rules["direct_rules"] = [
        {
            "id": "direct.base",
            "name": "直接值",
            "category": "利息收入",
            "unit": "亿元",
            "basis": "cumulative",
            "terms": [{"source": "ledger", "level": "l1", "code": "501", "weight": "-1"}],
        }
    ]
    rules["manual_metrics"] = [
        {
            "id": "manual.base",
            "name": "手工值",
            "category": "手工调整",
            "unit": "亿元",
            "basis": "cumulative",
            "default": "0",
            "manual_required": True,
        }
    ]
    rules["derived_rules"] = [
        {
            "id": "derived.mix",
            "name": "派生值",
            "category": "营业收入",
            "unit": "亿元",
            "basis": "cumulative",
            "calculation": {
                "type": "linear",
                "account_terms": [
                    {"source": "ledger", "level": "l1", "code": "600", "weight": "1"}
                ],
                "metric_terms": [
                    {"metric_id": "direct.base", "weight": "-2"},
                    {"metric_id": "manual.base", "weight": "1"},
                ],
            },
        }
    ]
    context = module.FinanceMetricDataContext(
        {
            ("ledger", "cumulative", "l1", "501"): module.AccountObservation(
                Decimal("200000000"), evidence_refs=("ledger.xlsx#row=2",)
            ),
            ("ledger", "cumulative", "l1", "600"): module.AccountObservation(
                Decimal("300000000"), evidence_refs=("ledger.xlsx#row=3",)
            ),
        }
    )

    results = module.evaluate_finance_metrics(
        rules,
        context,
        manual_overrides={"manual.base": Decimal("1")},
        include_lineage=True,
    )
    direct, manual, derived = results

    assert direct.lineage is not None
    assert direct.lineage == (
        module.FinanceMetricAccountLineage(
            source="ledger",
            basis="cumulative",
            level="l1",
            code="501",
            weight=Decimal("-1"),
            observed=True,
            raw_yuan=Decimal("200000000"),
            contribution_yi=Decimal("-2"),
            evidence_refs=("ledger.xlsx#row=2",),
        ),
    )
    assert manual.lineage == (
        module.FinanceMetricManualLineage(supplied=True, value_yi=Decimal("1")),
    )
    assert derived.lineage == (
        module.FinanceMetricAccountLineage(
            source="ledger",
            basis="cumulative",
            level="l1",
            code="600",
            weight=Decimal("1"),
            observed=True,
            raw_yuan=Decimal("300000000"),
            contribution_yi=Decimal("3"),
            evidence_refs=("ledger.xlsx#row=3",),
        ),
        module.FinanceMetricMetricLineage(
            metric_id="direct.base",
            weight=Decimal("-2"),
            metric_value_yi=Decimal("-2"),
            contribution_yi=Decimal("4"),
            dependency_status="ok",
        ),
        module.FinanceMetricMetricLineage(
            metric_id="manual.base",
            weight=Decimal("1"),
            metric_value_yi=Decimal("1"),
            contribution_yi=Decimal("1"),
            dependency_status="ok",
        ),
    )
    assert all(item.lineage_type in {"account", "metric"} for item in derived.lineage)
    with pytest.raises(FrozenInstanceError):
        direct.lineage[0].code = "999"


def test_frozen_rule_pack_evaluates_all_186_metrics_in_expanded_order() -> None:
    module = importlib.import_module("backend.app.core_finance.finance_metric_engine")
    rules = module.load_finance_metric_rules()
    expected_ids = tuple(
        [
            f"{rule['id']}::{basis}"
            for rule in rules["scale_rules"]
            for basis in rule["available_bases"]
        ]
        + [rule["id"] for rule in rules["direct_rules"]]
        + [rule["id"] for rule in rules["manual_metrics"]]
        + [rule["id"] for rule in rules["derived_rules"]]
    )

    results = module.evaluate_finance_metrics(
        rules,
        module.FinanceMetricDataContext(),
        include_lineage=False,
    )

    assert len(results) == 186
    assert tuple(result.id for result in results) == expected_ids
    assert all(result.unit == "亿元" for result in results)
    assert all(result.lineage is None for result in results)


def test_idempotency_key_canonicalizes_mapping_order_decimal_and_sequence_types() -> None:
    module = importlib.import_module("backend.app.core_finance.finance_metric_engine")
    assert hasattr(
        module, "build_finance_metric_idempotency_key"
    ), "canonical finance metric idempotency is not implemented"
    rules = module.load_finance_metric_rules()

    first = module.build_finance_metric_idempotency_key(
        ledger_sha256="a" * 64,
        daily_sha256="b" * 64,
        rules=rules,
        manual_overrides={
            "input.adjustment.noninterest.r010": Decimal("1.0"),
            "input.adjustment.noninterest.r019": None,
        },
        references={
            "prior": {"value": Decimal("2.00"), "as_of": date(2026, 5, 31)},
            "enabled": True,
        },
        analysis_requests=(
            {"kind": "ratio", "metric_ids": ("metric.a", "metric.b"), "days": 181},
        ),
        include_lineage=True,
        requested_metric_id="income.noninterest.total",
    )
    second = module.build_finance_metric_idempotency_key(
        ledger_sha256="A" * 64,
        daily_sha256="B" * 64,
        rules=rules,
        manual_overrides={
            "input.adjustment.noninterest.r019": None,
            "input.adjustment.noninterest.r010": Decimal("1.00"),
        },
        references={
            "enabled": True,
            "prior": {"as_of": date(2026, 5, 31), "value": Decimal("2.0")},
        },
        analysis_requests=[
            {"days": 181, "metric_ids": ["metric.a", "metric.b"], "kind": "ratio"},
        ],
        include_lineage=True,
        requested_metric_id="income.noninterest.total",
    )

    assert first == second
    assert len(first) == 64
    assert set(first) <= set("0123456789abcdef")


def _idempotency_inputs(module) -> dict[str, Any]:
    return {
        "ledger_sha256": "a" * 64,
        "daily_sha256": "b" * 64,
        "rules": module.load_finance_metric_rules(),
        "manual_overrides": {"input.adjustment.noninterest.r010": Decimal("1")},
        "references": {"prior": Decimal("2")},
        "analysis_requests": [{"kind": "ratio", "days": 181}],
        "include_lineage": True,
        "requested_metric_id": "income.noninterest.total",
        "report_month": "202606",
    }


def test_idempotency_key_changes_for_every_semantic_input_and_engine_contract(monkeypatch) -> None:
    module = importlib.import_module("backend.app.core_finance.finance_metric_engine")
    inputs = _idempotency_inputs(module)
    baseline = module.build_finance_metric_idempotency_key(**inputs)

    variants: list[dict[str, Any]] = []
    for field, value in (
        ("ledger_sha256", "c" * 64),
        ("daily_sha256", "d" * 64),
        ("manual_overrides", {"input.adjustment.noninterest.r010": Decimal("2")}),
        ("references", {"prior": Decimal("3")}),
        ("analysis_requests", [{"kind": "ratio", "days": 182}]),
        ("include_lineage", False),
        ("requested_metric_id", "income.interest.net"),
        ("report_month", "202607"),
    ):
        variant = deepcopy(inputs)
        variant[field] = value
        variants.append(variant)
    changed_rule_hash = deepcopy(inputs)
    changed_rule_hash["rules"]["rule_hash"] = "e" * 64
    variants.append(changed_rule_hash)
    changed_rule_version = deepcopy(inputs)
    changed_rule_version["rules"]["metadata"]["rule_version"] = "qdb-finance-2026-v1.0.0"
    variants.append(changed_rule_version)

    assert all(module.build_finance_metric_idempotency_key(**variant) != baseline for variant in variants)

    monkeypatch.setattr(module, "FINANCE_METRIC_ENGINE_CONTRACT_VERSION", "finance-metric-engine-v2")
    assert module.build_finance_metric_idempotency_key(**inputs) != baseline


def test_idempotency_rejects_invalid_source_or_rule_hash_with_typed_error() -> None:
    module = importlib.import_module("backend.app.core_finance.finance_metric_engine")
    assert hasattr(module, "FinanceMetricInputError"), "typed finance metric input error is not implemented"

    for field, value in (("ledger_sha256", "a" * 63), ("daily_sha256", "g" * 64)):
        inputs = _idempotency_inputs(module)
        inputs[field] = value
        with pytest.raises(module.FinanceMetricInputError) as exc_info:
            module.build_finance_metric_idempotency_key(**inputs)
        assert exc_info.value.code == "invalid_sha256"
        assert exc_info.value.path == field

    inputs = _idempotency_inputs(module)
    inputs["rules"]["rule_hash"] = "not-a-hash"
    with pytest.raises(module.FinanceMetricInputError) as exc_info:
        module.build_finance_metric_idempotency_key(**inputs)
    assert exc_info.value.code == "invalid_sha256"
    assert exc_info.value.path == "rules.rule_hash"


@pytest.mark.parametrize("report_month", ["2026-06", "202613", 202606])
def test_idempotency_rejects_invalid_report_month(report_month: Any) -> None:
    module = importlib.import_module("backend.app.core_finance.finance_metric_engine")
    inputs = _idempotency_inputs(module)
    inputs["report_month"] = report_month

    with pytest.raises(module.FinanceMetricInputError) as exc_info:
        module.build_finance_metric_idempotency_key(**inputs)

    assert exc_info.value.code == "invalid_report_month"
    assert exc_info.value.path == "report_month"


@pytest.mark.parametrize(
    ("bad_value", "expected_code"),
    [
        (1.5, "float_not_supported"),
        (float("nan"), "float_not_supported"),
        (float("inf"), "float_not_supported"),
        (Decimal("NaN"), "non_finite_decimal"),
        (Decimal("Infinity"), "non_finite_decimal"),
        ({1: "value"}, "non_string_mapping_key"),
        (datetime(2026, 6, 30, 12, 30), "unsupported_canonical_type"),
        (object(), "unsupported_canonical_type"),
    ],
)
def test_idempotency_rejects_unsafe_canonical_values(bad_value: Any, expected_code: str) -> None:
    module = importlib.import_module("backend.app.core_finance.finance_metric_engine")
    inputs = _idempotency_inputs(module)
    inputs["references"] = {"bad": bad_value}

    with pytest.raises(module.FinanceMetricInputError) as exc_info:
        module.build_finance_metric_idempotency_key(**inputs)

    assert exc_info.value.code == expected_code


def _manual_only_rules() -> dict[str, Any]:
    rules = _empty_rules()
    rules["manual_metrics"] = [
        {
            "id": "manual.allowed",
            "name": "允许的手工项",
            "category": "手工调整",
            "unit": "亿元",
            "basis": "cumulative",
            "default": "0",
            "manual_required": True,
        }
    ]
    return rules


def test_manual_overrides_reject_unknown_id_invalid_type_and_non_finite_decimal() -> None:
    module = importlib.import_module("backend.app.core_finance.finance_metric_engine")
    rules = _manual_only_rules()

    with pytest.raises(module.FinanceMetricInputError) as exc_info:
        module.evaluate_finance_metrics(
            rules,
            module.FinanceMetricDataContext(),
            manual_overrides={"manual.unknown": Decimal("1")},
        )
    assert exc_info.value.code == "unknown_manual_override"

    for invalid_value in ("1", 1, 1.0, True):
        with pytest.raises(module.FinanceMetricInputError) as exc_info:
            module.evaluate_finance_metrics(
                rules,
                module.FinanceMetricDataContext(),
                manual_overrides={"manual.allowed": invalid_value},
            )
        assert exc_info.value.code == "invalid_manual_override_type"

    for invalid_value in (Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")):
        with pytest.raises(module.FinanceMetricInputError) as exc_info:
            module.evaluate_finance_metrics(
                rules,
                module.FinanceMetricDataContext(),
                manual_overrides={"manual.allowed": invalid_value},
            )
        assert exc_info.value.code == "non_finite_manual_override"


def test_manual_override_none_and_finite_decimal_remain_explicit_supported_inputs() -> None:
    module = importlib.import_module("backend.app.core_finance.finance_metric_engine")
    rules = _manual_only_rules()

    unavailable = module.evaluate_finance_metrics(
        rules,
        module.FinanceMetricDataContext(),
        manual_overrides={"manual.allowed": None},
    )[0]
    supplied = module.evaluate_finance_metrics(
        rules,
        module.FinanceMetricDataContext(),
        manual_overrides={"manual.allowed": Decimal("1.25")},
    )[0]

    assert (unavailable.value, unavailable.status) == (None, "error")
    assert (supplied.value, supplied.status) == (Decimal("1.25"), "ok")


def test_idempotency_decimal_canonicalization_preserves_full_precision() -> None:
    module = importlib.import_module("backend.app.core_finance.finance_metric_engine")
    first = _idempotency_inputs(module)
    second = _idempotency_inputs(module)
    first["manual_overrides"] = {
        "input.adjustment.noninterest.r010": Decimal("1.1234567890123456789012345678901")
    }
    second["manual_overrides"] = {
        "input.adjustment.noninterest.r010": Decimal("1.1234567890123456789012345678902")
    }

    assert module.build_finance_metric_idempotency_key(
        **first
    ) != module.build_finance_metric_idempotency_key(**second)
