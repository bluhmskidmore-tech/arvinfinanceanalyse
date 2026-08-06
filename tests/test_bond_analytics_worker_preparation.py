from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.schemas.formal_compute_runtime import (
    FormalComputeMaterializeFailure,
    FormalComputeMaterializeResult,
)


def test_bond_refresh_service_only_dispatches_and_does_not_prepare_curves(tmp_path, monkeypatch) -> None:
    from backend.app.services import bond_analytics_service as service

    sent: list[dict[str, object]] = []
    monkeypatch.setattr(
        service,
        "_prepare_yield_curve_inputs_for_refresh",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("request path wrote yield curves")),
        raising=False,
    )
    monkeypatch.setattr(
        service,
        "materialize_bond_analytics_facts",
        SimpleNamespace(send=lambda **kwargs: sent.append(dict(kwargs))),
    )
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "moss.duckdb",
        governance_path=tmp_path / "governance",
    )

    payload = service.refresh_bond_analytics(settings, report_date="2026-03-31")

    assert payload["status"] == "queued"
    assert len(sent) == 1
    assert sent[0]["run_id"] == payload["run_id"]


def test_bond_worker_anchor_dates_include_report_month_start_and_prior_balance_date(
    tmp_path,
    monkeypatch,
) -> None:
    from backend.app.tasks import bond_analytics_materialize as task

    duckdb_path = tmp_path / "moss.duckdb"
    monkeypatch.setattr(
        task.BondAnalyticsRepository,
        "resolve_prior_curve_anchor_report_date",
        lambda self, *, report_date: "2026-03-01" if report_date == "2026-03-31" else None,
    )

    anchors = task._yield_curve_anchor_dates_for_materialization(
        duckdb_path=str(duckdb_path),
        report_date="2026-03-31",
    )

    assert anchors == ("2026-03-01", "2026-03-31")


def test_bond_worker_curve_prepare_failure_blocks_main_materialization_and_is_traced(
    tmp_path,
    monkeypatch,
) -> None:
    from backend.app.tasks import bond_analytics_materialize as task

    main_calls: list[str] = []
    monkeypatch.setattr(
        task,
        "_yield_curve_anchor_dates_for_materialization",
        lambda **_kwargs: ("2026-03-01", "2026-03-31"),
        raising=False,
    )
    monkeypatch.setattr(
        task,
        "ensure_yield_curve_inputs_on_or_before",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("curve vendor unavailable")),
        raising=False,
    )
    monkeypatch.setattr(
        task,
        "_execute_bond_analytics_materialization",
        lambda **_kwargs: main_calls.append("main")
        or (_ for _ in ()).throw(AssertionError("main materialization must not run")),
    )

    with pytest.raises(FormalComputeMaterializeFailure, match="yield_curve_prepare_failed"):
        task.materialize_bond_analytics_facts.fn(
            report_date="2026-03-31",
            duckdb_path=str(tmp_path / "moss.duckdb"),
            governance_dir=str(tmp_path / "governance"),
            run_id="bond-worker-curve-failure",
        )

    records = GovernanceRepository(base_dir=tmp_path / "governance").read_all(CACHE_BUILD_RUN_STREAM)
    assert main_calls == []
    assert records[-1]["run_id"] == "bond-worker-curve-failure"
    assert records[-1]["status"] == "failed"
    assert "yield_curve_prepare_failed" in records[-1]["error_message"]


def test_bond_worker_prepares_curves_before_main_and_invalidates_cache_after_success(
    tmp_path,
    monkeypatch,
) -> None:
    from backend.app.tasks import bond_analytics_materialize as task

    events: list[str] = []
    monkeypatch.setattr(
        task,
        "_yield_curve_anchor_dates_for_materialization",
        lambda **_kwargs: ("2026-03-01", "2026-03-31"),
        raising=False,
    )
    monkeypatch.setattr(
        task,
        "ensure_yield_curve_inputs_on_or_before",
        lambda **_kwargs: events.append("prepare"),
        raising=False,
    )
    monkeypatch.setattr(
        task,
        "_execute_bond_analytics_materialization",
        lambda **_kwargs: events.append("main")
        or FormalComputeMaterializeResult(
            source_version="sv_bond",
            vendor_version="vv_none",
            payload={"row_count": 1},
        ),
    )
    monkeypatch.setattr(
        task,
        "_invalidate_bond_analytics_worker_caches",
        lambda _report_date: events.append("invalidate"),
        raising=False,
    )

    payload = task.materialize_bond_analytics_facts.fn(
        report_date="2026-03-31",
        duckdb_path=str(tmp_path / "moss.duckdb"),
        governance_dir=str(tmp_path / "governance"),
        run_id="bond-worker-success",
    )

    assert payload["status"] == "completed"
    assert events == ["prepare", "main", "invalidate"]
