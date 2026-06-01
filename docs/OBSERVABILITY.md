# Observability

The backend includes an opt-in OpenTelemetry bootstrap.

Default behavior is disabled and safe:

- `MOSS_OTEL_ENABLED` unset: no instrumentation imports are attempted.
- `MOSS_OTEL_ENABLED=1` without packages installed: startup continues and
  `app.state.moss_otel.status` is `missing-packages`.
- `MOSS_OTEL_EXPORTER=console|otlp` selects the exporter when the optional OTEL
  packages are installed.

Install optional dependencies when needed:

```powershell
uv sync --project backend --extra otel
```

Useful env vars:

- `MOSS_OTEL_ENABLED=1`
- `MOSS_OTEL_EXPORTER=console`
- `MOSS_OTEL_SERVICE_NAME=moss-backend`

This foundation instruments FastAPI, requests, and SQLAlchemy when the optional
packages are present. Worker/task processes are intentionally not wired yet.
