from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module


MetricCallable = Callable[..., object]


@dataclass(slots=True, frozen=True)
class MetricDefinition:
    metric_key: str
    version: str
    owner_module: str
    callable_name: str
    compute: MetricCallable

    def __post_init__(self) -> None:
        if not self.metric_key.strip():
            raise ValueError("metric_key is required")
        if not self.version.strip():
            raise ValueError("version is required")
        if not self.owner_module.strip():
            raise ValueError("owner_module is required")
        if not self.callable_name.strip():
            raise ValueError("callable_name is required")
        if not callable(self.compute):
            raise ValueError("compute must be callable")


class MetricRegistry:
    def __init__(self) -> None:
        self._definitions: dict[tuple[str, str], MetricDefinition] = {}

    def register(self, definition: MetricDefinition) -> MetricDefinition:
        identity = (definition.metric_key, definition.version)
        if identity in self._definitions:
            raise ValueError(
                f"Metric {definition.metric_key!r} version {definition.version!r} is already registered"
            )
        self._definitions[identity] = definition
        return definition

    def get(self, metric_key: str, version: str) -> MetricDefinition:
        try:
            return self._definitions[(metric_key, version)]
        except KeyError as exc:
            raise KeyError(f"Unknown metric {metric_key!r} version {version!r}") from exc

    def list(self) -> tuple[MetricDefinition, ...]:
        return tuple(
            self._definitions[key]
            for key in sorted(self._definitions, key=lambda item: (item[0], item[1]))
        )


def _lazy_metric_callable(owner_module: str, callable_name: str) -> MetricCallable:
    def _compute(*args, **kwargs):
        module = import_module(owner_module)
        target = getattr(module, callable_name)
        return target(*args, **kwargs)

    return _compute


_REGISTRY = MetricRegistry()


def register_metric(definition: MetricDefinition) -> MetricDefinition:
    return _REGISTRY.register(definition)


def get_metric(metric_key: str, version: str) -> MetricDefinition:
    return _REGISTRY.get(metric_key, version)


def list_metrics() -> tuple[MetricDefinition, ...]:
    return _REGISTRY.list()


def _register_builtin_metrics() -> None:
    register_metric(
        MetricDefinition(
            metric_key="macro.leading_indicator",
            version="v1",
            owner_module="backend.app.core_finance.macro.leading_indicator",
            callable_name="compute_leading_indicator",
            compute=_lazy_metric_callable(
                "backend.app.core_finance.macro.leading_indicator",
                "compute_leading_indicator",
            ),
        )
    )
    register_metric(
        MetricDefinition(
            metric_key="macro.yield_curve_shape",
            version="v1",
            owner_module="backend.app.core_finance.macro.yield_curve_shape",
            callable_name="compute_yield_curve_shape",
            compute=_lazy_metric_callable(
                "backend.app.core_finance.macro.yield_curve_shape",
                "compute_yield_curve_shape",
            ),
        )
    )
    register_metric(
        MetricDefinition(
            metric_key="macro.credit_spread_percentile",
            version="v1",
            owner_module="backend.app.core_finance.macro.credit_spread_percentile",
            callable_name="compute_credit_spread_percentile",
            compute=_lazy_metric_callable(
                "backend.app.core_finance.macro.credit_spread_percentile",
                "compute_credit_spread_percentile",
            ),
        )
    )


_register_builtin_metrics()
