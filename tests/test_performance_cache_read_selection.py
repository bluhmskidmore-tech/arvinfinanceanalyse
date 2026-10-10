"""Read-model caches must follow the same immutable database as repositories."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.repositories.duckdb_read_context import (
    DuckDBReadSelection,
    DuckDBReadSelectionError,
    duckdb_read_scope,
    resolve_effective_read_path,
)
from backend.app.services import balance_analysis_service as balance_service
from backend.app.services import executive_service
from backend.app.services import pnl_attribution_service as attribution_service


@pytest.mark.parametrize("service", [balance_service, attribution_service])
def test_storage_identity_follows_selected_snapshot_without_active_file(tmp_path, service):
    active = tmp_path / "active.duckdb"
    snapshot = tmp_path / "snapshot.duckdb"
    snapshot.write_bytes(b"selected-generation")
    selection = DuckDBReadSelection(active, snapshot, "generation-1")
    with duckdb_read_scope(selection):
        identity = service._duckdb_storage_identity(str(active))
    assert identity == (str(snapshot.resolve()), snapshot.stat().st_mtime_ns, snapshot.stat().st_size)
    with duckdb_read_scope(None, required_online=False):
        assert service._duckdb_storage_identity(str(active)) is None


@pytest.mark.parametrize("surface", ["balance_workbook", "volume_rate"])
def test_read_model_cache_isolates_snapshots_and_rejects_missing_warm_snapshot(
    tmp_path, monkeypatch, surface,
):
    active = tmp_path / "active.duckdb"
    active.write_bytes(b"unchanged-active-file")
    snapshots = [tmp_path / "snapshot-1.duckdb", tmp_path / "snapshot-2.duckdb"]
    for index, snapshot in enumerate(snapshots):
        snapshot.write_text(f"generation-{index + 1}", encoding="utf-8")
    selections = [
        DuckDBReadSelection(active, snapshot, f"generation-{index + 1}")
        for index, snapshot in enumerate(snapshots)
    ]
    builds = []

    def build_result(**_kwargs):
        value = Path(resolve_effective_read_path(active)).read_text(encoding="utf-8")
        builds.append(value)
        if surface == "balance_workbook":
            return {"generation": value}, None
        return {"result": {"generation": value}, "result_meta": {"trace_id": "original"}}

    if surface == "balance_workbook":
        cache = balance_service._BALANCE_WORKBOOK_PAYLOAD_CACHE
        monkeypatch.setattr(balance_service, "_resolve_governance_backend_mode", lambda _: "jsonl")
        monkeypatch.setattr(
            balance_service.balance_analysis_workbook_service,
            "_build_balance_workbook_payload",
            build_result,
        )

        def read_result():
            result, _ = balance_service._build_balance_workbook_payload(
                duckdb_path=str(active), governance_dir=str(tmp_path / "governance"),
                report_date="2026-09-18", position_scope="all", currency_basis="CNY",
            )
            return result
    else:
        cache = attribution_service._PNL_ATTRIBUTION_CACHE
        monkeypatch.setattr(
            attribution_service,
            "get_settings",
            lambda: SimpleNamespace(
                duckdb_path=active,
                governance_backend="jsonl",
                governance_path=tmp_path / "governance",
            ),
        )
        monkeypatch.setattr(attribution_service, "_pnl_attribution_runtime_cache_enabled", lambda: True)
        monkeypatch.setattr(attribution_service, "_volume_rate_attribution_envelope_uncached", build_result)

        def read_result():
            return attribution_service.volume_rate_attribution_envelope(
                report_date="2026-09-18", compare_type="mom",
            )["result"]

    cache.clear()
    try:
        with duckdb_read_scope(selections[0]):
            assert read_result() == read_result() == {"generation": "generation-1"}
        with duckdb_read_scope(selections[1]):
            assert read_result() == read_result() == {"generation": "generation-2"}
            snapshots[1].unlink()
            with pytest.raises(DuckDBReadSelectionError):
                read_result()
        assert builds == ["generation-1", "generation-2"]
    finally:
        cache.clear()


@pytest.mark.parametrize(
    "service, probe",
    [
        (attribution_service, "_pnl_attribution_runtime_cache_enabled"),
        pytest.param(
            executive_service, "_executive_overview_runtime_cache_enabled",
            marks=[pytest.mark.excluded_surface_regression, pytest.mark.surface_executive],
        ),
    ],
)
@pytest.mark.parametrize("failure_type", [OSError, TypeError, ValueError])
def test_optional_cache_probes_disable_cache_for_configuration_errors(
    monkeypatch, service, probe, failure_type,
):
    def invalid_settings():
        raise failure_type("settings are unavailable")

    monkeypatch.setattr(service, "get_settings", invalid_settings)
    assert getattr(service, probe)() is False


@pytest.mark.parametrize(
    "service, probe",
    [
        (attribution_service, "_pnl_attribution_runtime_cache_enabled"),
        pytest.param(
            executive_service, "_executive_overview_runtime_cache_enabled",
            marks=[pytest.mark.excluded_surface_regression, pytest.mark.surface_executive],
        ),
    ],
)
def test_optional_cache_probes_disable_cache_for_invalid_settings_value(monkeypatch, service, probe):
    monkeypatch.setenv("MOSS_AGENT_ENABLED", "invalid-boolean")
    service.get_settings.cache_clear()
    with pytest.raises(ValueError, match="agent_enabled"):
        service.get_settings()
    assert getattr(service, probe)() is False


@pytest.mark.parametrize(
    "service, probe",
    [
        (attribution_service, "_pnl_attribution_runtime_cache_enabled"),
        pytest.param(
            executive_service, "_executive_overview_runtime_cache_enabled",
            marks=[pytest.mark.excluded_surface_regression, pytest.mark.surface_executive],
        ),
    ],
)
def test_optional_cache_probes_propagate_unexpected_internal_errors(monkeypatch, service, probe):
    class UnexpectedCacheProbeError(Exception):
        pass

    def broken_settings():
        raise UnexpectedCacheProbeError("internal settings defect")

    monkeypatch.setattr(service, "get_settings", broken_settings)
    with pytest.raises(UnexpectedCacheProbeError, match="internal settings defect"):
        getattr(service, probe)()
