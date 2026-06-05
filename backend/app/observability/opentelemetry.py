from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib import import_module as _import_module
from types import ModuleType

from fastapi import FastAPI

logger = logging.getLogger(__name__)

ImportModule = Callable[[str], ModuleType]

_CORE_MODULES = (
    "opentelemetry.trace",
    "opentelemetry.sdk.resources",
    "opentelemetry.sdk.trace",
    "opentelemetry.sdk.trace.export",
    "opentelemetry.instrumentation.fastapi",
    "opentelemetry.instrumentation.requests",
    "opentelemetry.instrumentation.sqlalchemy",
)
_OTLP_HTTP_EXPORTER_MODULE = "opentelemetry.exporter.otlp.proto.http.trace_exporter"


@dataclass(frozen=True)
class OtelSetupResult:
    requested: bool
    active: bool
    status: str
    missing_packages: tuple[str, ...] = ()
    exporter: str = "none"
    service_name: str = "moss-backend"
    error: str | None = None


def setup_opentelemetry(
    app: FastAPI,
    *,
    env: Mapping[str, str] | None = None,
    import_module: ImportModule = _import_module,
) -> OtelSetupResult:
    source_env = os.environ if env is None else env
    enabled = _env_flag(source_env, "MOSS_OTEL_ENABLED")
    exporter = _normalize_exporter(source_env.get("MOSS_OTEL_EXPORTER"))
    service_name = str(source_env.get("MOSS_OTEL_SERVICE_NAME") or "").strip() or "moss-backend"

    if not enabled:
        result = OtelSetupResult(
            requested=False,
            active=False,
            status="disabled",
            exporter=exporter,
            service_name=service_name,
        )
        app.state.moss_otel = result
        return result

    required_modules = list(_CORE_MODULES)
    if exporter == "otlp":
        required_modules.append(_OTLP_HTTP_EXPORTER_MODULE)

    loaded_modules: dict[str, ModuleType] = {}
    missing_packages: list[str] = []
    for module_name in required_modules:
        try:
            loaded_modules[module_name] = import_module(module_name)
        except ImportError:
            missing_packages.append(module_name)

    if missing_packages:
        result = OtelSetupResult(
            requested=True,
            active=False,
            status="missing-packages",
            missing_packages=tuple(missing_packages),
            exporter=exporter,
            service_name=service_name,
        )
        logger.warning(
            "OpenTelemetry requested but missing packages: %s",
            ", ".join(result.missing_packages),
        )
        app.state.moss_otel = result
        return result

    try:
        resource_module = loaded_modules["opentelemetry.sdk.resources"]
        sdk_trace_module = loaded_modules["opentelemetry.sdk.trace"]
        export_module = loaded_modules["opentelemetry.sdk.trace.export"]
        trace_module = loaded_modules["opentelemetry.trace"]
        fastapi_module = loaded_modules["opentelemetry.instrumentation.fastapi"]
        requests_module = loaded_modules["opentelemetry.instrumentation.requests"]
        sqlalchemy_module = loaded_modules["opentelemetry.instrumentation.sqlalchemy"]

        resource = resource_module.Resource.create({"service.name": service_name})
        tracer_provider = sdk_trace_module.TracerProvider(resource=resource)
        span_exporter = _build_exporter(exporter, loaded_modules, export_module)
        if span_exporter is not None:
            tracer_provider.add_span_processor(export_module.BatchSpanProcessor(span_exporter))
        trace_module.set_tracer_provider(tracer_provider)

        fastapi_module.FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)
        requests_module.RequestsInstrumentor().instrument(tracer_provider=tracer_provider)
        sqlalchemy_module.SQLAlchemyInstrumentor().instrument(tracer_provider=tracer_provider)
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        result = OtelSetupResult(
            requested=True,
            active=False,
            status="error",
            exporter=exporter,
            service_name=service_name,
            error=f"{type(exc).__name__}: {exc}",
        )
        logger.exception("OpenTelemetry setup failed")
        app.state.moss_otel = result
        return result

    result = OtelSetupResult(
        requested=True,
        active=True,
        status="enabled",
        exporter=exporter,
        service_name=service_name,
    )
    logger.info(
        "OpenTelemetry enabled with exporter=%s service_name=%s",
        exporter,
        service_name,
    )
    app.state.moss_otel = result
    return result


def _build_exporter(exporter: str, loaded_modules: Mapping[str, ModuleType], export_module: ModuleType):
    if exporter == "console":
        return export_module.ConsoleSpanExporter()
    if exporter == "otlp":
        otlp_module = loaded_modules[_OTLP_HTTP_EXPORTER_MODULE]
        return otlp_module.OTLPSpanExporter()
    return None


def _env_flag(env: Mapping[str, str], key: str) -> bool:
    value = str(env.get(key, "") or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _normalize_exporter(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"console", "otlp"}:
        return normalized
    return "none"
