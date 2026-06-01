"""Optional observability helpers for backend startup."""

from .opentelemetry import OtelSetupResult, setup_opentelemetry

__all__ = ["OtelSetupResult", "setup_opentelemetry"]
