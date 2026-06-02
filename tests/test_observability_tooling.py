from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_backend_declares_opentelemetry_as_optional_extra_only() -> None:
    pyproject = (ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8")

    assert "otel = [" in pyproject
    assert '"opentelemetry-instrumentation-fastapi>=0.60b0,<1"' in pyproject
    assert '"opentelemetry-instrumentation-requests>=0.60b0,<1"' in pyproject
    assert '"opentelemetry-instrumentation-sqlalchemy>=0.60b0,<1"' in pyproject
    assert 'dependencies = [\n  "beautifulsoup4>=4.12,<5",' in pyproject


def test_observability_doc_records_opt_in_runtime_boundary() -> None:
    doc = (ROOT / "docs" / "OBSERVABILITY.md").read_text(encoding="utf-8")

    assert "MOSS_OTEL_ENABLED=1" in doc
    assert "missing-packages" in doc
    assert "Worker/task processes are intentionally not wired yet." in doc
