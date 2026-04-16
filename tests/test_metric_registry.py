from __future__ import annotations

import pytest

from tests.helpers import load_module


def test_builtin_metric_registry_exposes_versioned_macro_metrics():
    module = load_module(
        "backend.app.core_finance.metric_registry",
        "backend/app/core_finance/metric_registry.py",
    )

    metrics = {
        (definition.metric_key, definition.version): definition
        for definition in module.list_metrics()
    }

    leading_indicator = metrics[("macro.leading_indicator", "v1")]
    assert leading_indicator.owner_module == "backend.app.core_finance.macro.leading_indicator"
    assert leading_indicator.callable_name == "compute_leading_indicator"
    assert callable(leading_indicator.compute)

    yield_curve_shape = metrics[("macro.yield_curve_shape", "v1")]
    assert yield_curve_shape.owner_module == "backend.app.core_finance.macro.yield_curve_shape"
    assert yield_curve_shape.callable_name == "compute_yield_curve_shape"
    assert callable(yield_curve_shape.compute)


def test_metric_registry_rejects_duplicate_metric_identity():
    module = load_module(
        "backend.app.core_finance.metric_registry",
        "backend/app/core_finance/metric_registry.py",
    )

    registry = module.MetricRegistry()
    definition = module.MetricDefinition(
        metric_key="macro.test_metric",
        version="v1",
        owner_module="tests.metric_registry",
        callable_name="compute_metric",
        compute=lambda: None,
    )
    registry.register(definition)

    with pytest.raises(ValueError, match="already registered"):
        registry.register(definition)


def test_metric_registry_allows_new_versions_for_same_metric_key():
    module = load_module(
        "backend.app.core_finance.metric_registry",
        "backend/app/core_finance/metric_registry.py",
    )

    registry = module.MetricRegistry()
    registry.register(
        module.MetricDefinition(
            metric_key="macro.test_metric",
            version="v1",
            owner_module="tests.metric_registry",
            callable_name="compute_metric_v1",
            compute=lambda: "v1",
        )
    )
    registry.register(
        module.MetricDefinition(
            metric_key="macro.test_metric",
            version="v2",
            owner_module="tests.metric_registry",
            callable_name="compute_metric_v2",
            compute=lambda: "v2",
        )
    )

    assert registry.get("macro.test_metric", "v1").callable_name == "compute_metric_v1"
    assert registry.get("macro.test_metric", "v2").callable_name == "compute_metric_v2"
