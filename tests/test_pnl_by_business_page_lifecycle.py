from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.services import pnl_by_business_page_lifecycle as lifecycle
from backend.app.services import pnl_by_business_page_readiness as readiness
from backend.app.services import pnl_by_business_publication_service as publication_service
from backend.app.services.pnl_by_business_adjustment_handoff import (
    begin_pnl_by_business_adjustment_handoff,
)
from backend.app.services.pnl_by_business_candidate_insights import FORMAL_RULE_VERSION
from backend.app.services.pnl_by_business_publication_service import (
    PNL_BY_BUSINESS_PAGE_PROTOCOL_VERSION,
    PnlPublishedGenerationConflictError,
    require_current_pnl_by_business_governance,
)
from backend.app.services.pnl_service_by_business_support import (
    pnl_by_business_page_dependencies,
)


def _settings(tmp_path: Path) -> SimpleNamespace:
    governance = tmp_path / "governance"
    governance.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        duckdb_path=str(tmp_path / "active.duckdb"),
        governance_path=str(governance),
        financial_publication_enabled=True,
        financial_publication_root=str(tmp_path / "published"),
        ftp_rate_pct=2,
    )


def test_enabled_readiness_uses_only_sealed_publication_and_governance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    dependencies = pnl_by_business_page_dependencies(
        year=2026,
        as_of_date="2026-06-30",
    )
    versions: dict[str, str] = {}
    for dependency in dependencies:
        prefix = f"pnl_by_business.{dependency['key']}"
        requested = str(dependency["requested_report_date"])
        versions[f"{prefix}.requested_report_date"] = requested
        versions[f"{prefix}.resolved_report_date"] = requested

    monkeypatch.setattr(
        readiness,
        "list_retained_pnl_by_business_publications",
        lambda *_args, **_kwargs: (
            {
                "generation": "sealed-20260630",
                "report_date": "2026-06-30",
                "dependency_versions": versions,
                "source_version": "source-v1",
                "rule_version": "rules-v1",
                "prepared_at": "2026-09-13T01:00:00+00:00",
            },
        ),
    )
    GovernanceRepository(base_dir=settings.governance_path).append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "failed-refresh",
            "job_name": "pnl_by_business_precompute",
            "cache_key": "pnl:by-business:precompute",
            "status": "failed",
            "target_year": 2026,
            "report_date": "2026-06-30",
            "finished_at": "2026-09-13T02:00:00+00:00",
            "error_message": "new refresh failed",
            "failure_category": "source_error",
        },
    )

    class ActiveRepositoryMustNotOpen:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("enabled status opened the active DuckDB")

    result = readiness.pnl_by_business_published_page_status(
        settings,
        year=2026,
        as_of_date="2026-06-30",
        repository_cls=ActiveRepositoryMustNotOpen,
    )

    assert result["readiness"] == "ready"
    assert result["generation"] == "sealed-20260630"
    assert result["serving_mode"] == "published"
    assert result["report_date"] == "2026-06-30"
    assert result["status"] == "failed"
    assert result["refresh_status"] == "failed"
    assert result["refresh_error_message"] == "new refresh failed"
    assert result["refresh_failure_category"] == "source_error"
    assert result["record_count"] == 1
    assert {item["key"] for item in result["dependencies"]} == {
        "current_ytd",
        "baseline_ytd",
        "monthly",
        "monthly_baseline",
    }


def test_page_rebuild_persists_exact_revision_batches_before_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)

    class Repository:
        def __init__(self, _path: str):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year: int, as_of_cap: str):
            return as_of_cap

        def pnl_by_business_precompute_dependency_revision(
            self, *, year: int, as_of_date: str
        ) -> int:
            return {
                "2026-06-30": 9,
                "2025-06-30": 7,
                "2025-12-31": 8,
            }[as_of_date]

    queue_calls: list[dict[str, object]] = []
    actor_calls: list[dict[str, object]] = []
    pointer_calls: list[bool] = []

    def queue_refresh(_settings, **kwargs):
        queue_calls.append(kwargs)
        return {"run_id": f"dependency-{len(queue_calls)}", "status": "queued"}

    monkeypatch.setattr(
        lifecycle.prepare_pnl_by_business_page_envelope_actor,
        "send",
        lambda **kwargs: actor_calls.append(kwargs),
    )
    monkeypatch.setattr(
        lifecycle,
        "pnl_by_business_published_page_status",
        lambda *_args, **_kwargs: {
            "status": "idle",
            "readiness": "stale",
            "generation": None,
            "dependencies": [],
        },
    )
    monkeypatch.setattr(
        lifecycle,
        "read_publication_pointer",
        lambda _root, *, require_valid: (
            pointer_calls.append(require_valid) or {"generation": "revoked-generation"}
        ),
    )

    result = lifecycle.request_pnl_by_business_page_rebuild(
        settings,
        year=2026,
        as_of_date="2026-06-30",
        queue_refresh=queue_refresh,
        repository_cls=Repository,
    )

    assert result["readiness"] == "pending"
    assert len(queue_calls) == 3
    assert {
        (
            int(call["year"]),
            int(call["dependency_revision"]),
            tuple(call["as_of_dates"]),
        )
        for call in queue_calls
    } == {
        (2025, 7, ("2025-06-30",)),
        (2025, 8, ("2025-12-31",)),
        (2026, 9, ("2026-06-30",)),
    }
    assert len(actor_calls) == 1
    assert actor_calls[0]["run_id"] == result["page_run_id"]
    assert actor_calls[0]["expected_previous_generation"] == "revoked-generation"
    assert pointer_calls == [False]
    records = GovernanceRepository(base_dir=settings.governance_path).read_all(
        CACHE_BUILD_RUN_STREAM
    )
    intent = next(
        record
        for record in records
        if record.get("run_id") == result["page_run_id"]
    )
    assert intent["target_as_of_dates"] == [
        "2025-06-30",
        "2025-12-31",
        "2026-06-30",
    ]
    assert intent["target_count"] == 3
    assert len(intent["dependency_batches"]) == 3
    assert intent["expected_previous_generation"] == "revoked-generation"


def test_pending_adjustment_handoff_rejects_published_generation(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    begin_pnl_by_business_adjustment_handoff(
        settings.governance_path,
        adjustment_id="adjustment-1",
        dependency_dates=("2026-06-30",),
        reason="approved",
        expected_adjustment_event={"adjustment_id": "adjustment-1", "status": "approved"},
    )
    versions = {
        "pnl_by_business_page.protocol": PNL_BY_BUSINESS_PAGE_PROTOCOL_VERSION,
        "pnl_by_business_page.rules": FORMAL_RULE_VERSION,
        "pnl_by_business.current_ytd.requested_report_date": "2026-06-30",
    }

    with pytest.raises(PnlPublishedGenerationConflictError, match="pending precompute handoff"):
        require_current_pnl_by_business_governance(settings, versions)


def test_page_recovery_reports_partial_dispatch_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    GovernanceRepository(base_dir=settings.governance_path).append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "page-run-1",
            "job_name": "pnl_by_business_page_prepare",
            "status": "queued",
            "target_year": 2026,
            "report_date": "2026-06-30",
            "queued_at": "2026-09-13T01:00:00+00:00",
            "expected_previous_generation": None,
            "protocol_version": lifecycle.PNL_BY_BUSINESS_PAGE_INTENT_PROTOCOL_VERSION,
        },
    )
    monkeypatch.setattr(lifecycle, "_completed_publication_for_intent", lambda *_a, **_k: None)

    def fail_dispatch(**_kwargs):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(
        lifecycle.prepare_pnl_by_business_page_envelope_actor,
        "send",
        fail_dispatch,
    )

    result = lifecycle.recover_pending_pnl_by_business_page_rebuilds(settings)

    assert result["status"] == "partial_failure"
    assert result["pending_count"] == 1
    assert result["failed_count"] == 1
    assert result["dispatched_count"] == 0


def test_page_recovery_does_not_redispatch_recent_active_intent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    now = datetime.now(UTC)
    GovernanceRepository(base_dir=settings.governance_path).append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "page-run-active",
            "job_name": "pnl_by_business_page_prepare",
            "status": "running",
            "target_year": 2026,
            "report_date": "2026-06-30",
            "started_at": now.isoformat(),
            "expected_previous_generation": None,
            "protocol_version": lifecycle.PNL_BY_BUSINESS_PAGE_INTENT_PROTOCOL_VERSION,
        },
    )
    monkeypatch.setattr(lifecycle, "_completed_publication_for_intent", lambda *_a, **_k: None)
    monkeypatch.setattr(
        lifecycle.prepare_pnl_by_business_page_envelope_actor,
        "send",
        lambda **_kwargs: pytest.fail("recent active intent was redispatched"),
    )

    result = lifecycle.recover_pending_pnl_by_business_page_rebuilds(settings)

    assert result["status"] == "completed"
    assert result["pending_count"] == 1
    assert result["active_count"] == 1
    assert result["dispatched_count"] == 0


def test_page_recovery_keeps_resource_over_budget_intent_terminal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    receipt = {"status": "over_budget", "peak_process_tree_memory_bytes": 123}
    GovernanceRepository(base_dir=settings.governance_path).append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "page-run-over-budget",
            "job_name": "pnl_by_business_page_prepare",
            "status": "failed",
            "failure_category": "resource_over_budget",
            "resource_limits": receipt,
            "error_message": "process tree memory exceeded the configured limit",
            "target_year": 2026,
            "report_date": "2026-06-30",
            "protocol_version": lifecycle.PNL_BY_BUSINESS_PAGE_INTENT_PROTOCOL_VERSION,
        },
    )
    GovernanceRepository(base_dir=settings.governance_path).append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "page-run-over-budget",
            "job_name": "pnl_by_business_page_prepare",
            "status": "queued",
            "target_year": 2026,
            "report_date": "2026-06-30",
            "protocol_version": lifecycle.PNL_BY_BUSINESS_PAGE_INTENT_PROTOCOL_VERSION,
        },
    )
    monkeypatch.setattr(
        lifecycle,
        "_completed_publication_for_intent",
        lambda *_a, **_k: pytest.fail("over-budget intent was reconciled as completed"),
    )
    monkeypatch.setattr(
        lifecycle.prepare_pnl_by_business_page_envelope_actor,
        "send",
        lambda **_kwargs: pytest.fail("over-budget intent was redispatched"),
    )

    result = lifecycle.recover_pending_pnl_by_business_page_rebuilds(settings)

    assert result["status"] == "partial_failure"
    assert result["failed_count"] == 1
    assert result["items"] == [
        {
            "run_id": "page-run-over-budget",
            "status": "failed",
            "error_message": "process tree memory exceeded the configured limit",
            "resource_limits": receipt,
        }
    ]


def test_page_recovery_requeues_persisted_batches_before_final_page_actor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.services import pnl_by_business_precompute_lifecycle as precompute_lifecycle

    settings = _settings(tmp_path)
    GovernanceRepository(base_dir=settings.governance_path).append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "existing-dependency-run",
            "job_name": "pnl_by_business_precompute",
            "cache_key": "pnl:by-business:precompute",
            "cache_version": "cv_pnl_by_business_precompute_v1",
            "status": "queued",
            "target_year": 2025,
            "report_date": None,
            "queued_at": "2099-09-13T01:00:00+00:00",
            "dependency_revision": 7,
            "target_as_of_dates": ["2025-06-30"],
        },
    )
    GovernanceRepository(base_dir=settings.governance_path).append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "page-run-recover",
            "job_name": "pnl_by_business_page_prepare",
            "status": "failed",
            "target_year": 2026,
            "report_date": "2026-06-30",
            "queued_at": "2026-09-13T01:00:00+00:00",
            "expected_previous_generation": "generation-a",
            "dependency_batches": [
                {
                    "year": 2025,
                    "dependency_revision": 7,
                    "target_as_of_dates": ["2025-06-30"],
                },
                {
                    "year": 2026,
                    "dependency_revision": 9,
                    "target_as_of_dates": ["2026-06-30"],
                },
            ],
            "protocol_version": lifecycle.PNL_BY_BUSINESS_PAGE_INTENT_PROTOCOL_VERSION,
        },
    )
    monkeypatch.setattr(lifecycle, "_completed_publication_for_intent", lambda *_a, **_k: None)
    events: list[tuple[str, object]] = []

    monkeypatch.setattr(
        precompute_lifecycle.rebuild_pnl_by_business_precompute,
        "send",
        lambda **kwargs: events.append(("dependency", kwargs["dependency_revision"])),
    )
    monkeypatch.setattr(
        lifecycle.prepare_pnl_by_business_page_envelope_actor,
        "send",
        lambda **kwargs: events.append(("page", kwargs["expected_previous_generation"])),
    )

    result = lifecycle.recover_pending_pnl_by_business_page_rebuilds(settings)

    assert result["status"] == "completed"
    assert result["dispatched_count"] == 1
    assert events == [
        ("dependency", 9),
        ("page", "generation-a"),
    ]
    assert result["items"][0]["dependency_runs"][0]["reused"] is True
    assert result["items"][0]["dependency_runs"][1]["reused"] is False


def test_source_missing_intent_is_visible_and_recovers_all_dependency_batches(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.services import pnl_service

    settings = _settings(tmp_path)

    class MissingRepository:
        def __init__(self, _path: str):
            pass

        def max_formal_or_nonstd_report_date_in_year(self, *, year: int, as_of_cap: str):
            return None if as_of_cap == "2025-06-30" else as_of_cap

        def pnl_by_business_precompute_dependency_revision(
            self, *, year: int, as_of_date: str
        ) -> int:
            return {"2025-12-31": 8, "2026-06-30": 9}[as_of_date]

    monkeypatch.setattr(
        lifecycle.prepare_pnl_by_business_page_envelope_actor,
        "send",
        lambda **_kwargs: pytest.fail("page actor dispatched before sources were complete"),
    )
    with pytest.raises(ValueError, match="baseline_ytd=2025-06-30"):
        lifecycle.request_pnl_by_business_page_rebuild(
            settings,
            year=2026,
            as_of_date="2026-06-30",
            queue_refresh=lambda *_args, **_kwargs: pytest.fail(
                "dependency queue dispatched before sources were complete"
            ),
            repository_cls=MissingRepository,
        )

    monkeypatch.setattr(
        readiness,
        "list_retained_pnl_by_business_publications",
        lambda *_args, **_kwargs: (),
    )
    unavailable = readiness.pnl_by_business_published_page_status(
        settings,
        year=2026,
        as_of_date="2026-06-30",
    )
    assert unavailable["readiness"] == "source_missing"
    assert unavailable["generation"] is None
    assert unavailable["record_count"] is None

    class ReadyRepository(MissingRepository):
        def max_formal_or_nonstd_report_date_in_year(self, *, year: int, as_of_cap: str):
            return as_of_cap

        def pnl_by_business_precompute_dependency_revision(
            self, *, year: int, as_of_date: str
        ) -> int:
            return {"2025-06-30": 7, "2025-12-31": 8, "2026-06-30": 9}[as_of_date]

    monkeypatch.setattr(lifecycle, "PnlRepository", ReadyRepository)
    monkeypatch.setattr(lifecycle, "_completed_publication_for_intent", lambda *_a, **_k: None)
    queued_dates: list[str] = []

    def recover_queue(_settings, **kwargs):
        queued_dates.extend(kwargs["as_of_dates"])
        return {"run_id": f"dependency-{kwargs['dependency_revision']}"}

    monkeypatch.setattr(pnl_service, "_queue_pnl_by_business_precompute_refresh", recover_queue)
    monkeypatch.setattr(
        lifecycle.prepare_pnl_by_business_page_envelope_actor,
        "send",
        lambda **_kwargs: None,
    )

    recovered = lifecycle.recover_pending_pnl_by_business_page_rebuilds(settings)

    assert recovered["status"] == "completed"
    assert sorted(set(queued_dates)) == ["2025-06-30", "2025-12-31", "2026-06-30"]


def test_completed_publication_for_intent_reads_exact_retained_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    run_id = "pnl_by_business_page_prepare:retained-august"
    expected_generation = (
        "financial-20260831-"
        + hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:16]
    )
    read_calls: list[dict[str, object]] = []

    def read_retained(_settings, **kwargs):
        read_calls.append(kwargs)
        return {
            "result": {"generation": expected_generation},
            "result_meta": {"generated_at": "2026-09-14T00:52:45+00:00"},
        }

    monkeypatch.setattr(
        publication_service,
        "read_published_pnl_by_business_insights",
        read_retained,
    )

    result = lifecycle._completed_publication_for_intent(
        settings,
        report_date="2026-08-31",
        run_id=run_id,
    )

    assert result == {
        "generation": expected_generation,
        "prepared_at": "2026-09-14T00:52:45+00:00",
    }
    assert read_calls == [
        {
            "year": 2026,
            "as_of_date": "2026-08-31",
            "generation": expected_generation,
        }
    ]


@pytest.mark.parametrize(
    "error",
    [
        PnlPublishedGenerationConflictError("retained generation was revoked"),
        RuntimeError("retained generation is incompatible"),
    ],
)
def test_completed_publication_for_intent_rejects_unusable_exact_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: RuntimeError,
) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr(
        publication_service,
        "read_published_pnl_by_business_insights",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
    )

    assert (
        lifecycle._completed_publication_for_intent(
            settings,
            report_date="2026-08-31",
            run_id="pnl_by_business_page_prepare:wrong-or-unusable",
        )
        is None
    )


def test_completed_publication_for_intent_does_not_accept_another_run_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    published_run_id = "pnl_by_business_page_prepare:published-run"
    published_generation = (
        "financial-20260831-"
        + hashlib.sha256(published_run_id.encode("utf-8")).hexdigest()[:16]
    )

    def read_only_published_run(_settings, **kwargs):
        if kwargs["generation"] != published_generation:
            raise PnlPublishedGenerationConflictError("generation is not retained")
        return {
            "result": {"generation": published_generation},
            "result_meta": {"generated_at": "2026-09-14T00:52:45+00:00"},
        }

    monkeypatch.setattr(
        publication_service,
        "read_published_pnl_by_business_insights",
        read_only_published_run,
    )

    assert (
        lifecycle._completed_publication_for_intent(
            settings,
            report_date="2026-08-31",
            run_id="pnl_by_business_page_prepare:different-run",
        )
        is None
    )


def test_recovery_completes_exact_retained_intent_without_redispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(tmp_path)
    retained_run_id = "pnl_by_business_page_prepare:retained-august"
    retained_generation = (
        "financial-20260831-"
        + hashlib.sha256(retained_run_id.encode("utf-8")).hexdigest()[:16]
    )
    governance = GovernanceRepository(base_dir=settings.governance_path)
    governance.append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": retained_run_id,
            "job_name": "pnl_by_business_page_prepare",
            "status": "failed",
            "target_year": 2026,
            "report_date": "2026-08-31",
            "queued_at": "2026-09-14T00:40:17+00:00",
            "protocol_version": lifecycle.PNL_BY_BUSINESS_PAGE_INTENT_PROTOCOL_VERSION,
        },
    )
    governance.append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "pnl_by_business_page_prepare:current-july",
            "job_name": "pnl_by_business_page_prepare",
            "status": "completed",
            "target_year": 2026,
            "report_date": "2026-07-31",
            "generation": "financial-20260731-current",
            "protocol_version": lifecycle.PNL_BY_BUSINESS_PAGE_INTENT_PROTOCOL_VERSION,
        },
    )

    def read_retained(_settings, **kwargs):
        assert kwargs == {
            "year": 2026,
            "as_of_date": "2026-08-31",
            "generation": retained_generation,
        }
        return {
            "result": {"generation": retained_generation},
            "result_meta": {"generated_at": "2026-09-14T00:52:45+00:00"},
        }

    monkeypatch.setattr(
        publication_service,
        "read_published_pnl_by_business_insights",
        read_retained,
    )
    monkeypatch.setattr(
        lifecycle.prepare_pnl_by_business_page_envelope_actor,
        "send",
        lambda **_kwargs: pytest.fail("completed retained intent was redispatched"),
    )

    result = lifecycle.recover_pending_pnl_by_business_page_rebuilds(settings)

    assert result["status"] == "completed"
    assert result["pending_count"] == 1
    assert result["completed_count"] == 1
    assert result["dispatched_count"] == 0
    latest = [
        record
        for record in governance.read_all(CACHE_BUILD_RUN_STREAM)
        if record.get("run_id") == retained_run_id
    ][-1]
    assert latest["status"] == "completed"
    assert latest["generation"] == retained_generation


def test_completed_publication_rejects_sealed_generation_not_committed_to_pointer(
    tmp_path: Path,
) -> None:
    import duckdb

    from backend.app.repositories.financial_result_publication_repo import (
        FINANCIAL_PUBLICATION_API_VERSION,
        FINANCIAL_PUBLICATION_SCHEMA_VERSION,
        generation_database_path,
        generation_manifest_path,
        read_publication_pointer,
        validate_sealed_financial_generation,
    )
    from backend.app.tasks.financial_result_publication import (
        FinancialPublicationPlan,
        FinancialTablePublicationSpec,
        publish_financial_result,
    )

    settings = _settings(tmp_path)
    source = Path(settings.duckdb_path)
    publication_root = Path(settings.financial_publication_root)
    conn = duckdb.connect(str(source))
    try:
        conn.execute("create table fact_result(report_date date, value integer)")
        conn.execute("insert into fact_result values (date '2026-08-31', 1)")
    finally:
        conn.close()

    def dependency_versions(_conn) -> dict[str, str]:
        return {"source": "source-v1"}

    def plan(generation: str, previous: str | None) -> FinancialPublicationPlan:
        return FinancialPublicationPlan(
            generation=generation,
            expected_previous_generation=previous,
            tables=(
                FinancialTablePublicationSpec(
                    name="fact_result",
                    date_column="report_date",
                    required_dates=("2026-08-31",),
                ),
            ),
            required_steps=("materialize",),
            step_receipts=(
                {
                    "name": "materialize",
                    "status": "completed",
                    "result": {"status": "completed", "report_date": "2026-08-31"},
                },
            ),
            required_dependency_keys=("source",),
            dependency_versions={"source": "source-v1"},
            coverage_dates={"current": ("2026-08-31",)},
            supported_api_versions=("financial-api/v1",),
            supported_schema_versions=("financial-results/v1",),
            quality={"status": "passed", "checks": ({"status": "passed"},)},
            source_dependency_validator=dependency_versions,
        )

    current_generation = "financial-20260831-current"
    publish_financial_result(
        source_duckdb_path=source,
        publication_root=publication_root,
        plan=plan(current_generation, None),
    )
    run_id = "pnl_by_business_page_prepare:sealed-but-uncommitted"
    candidate_generation = (
        "financial-20260831-"
        + hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:16]
    )

    def fail_before_pointer(stage: str) -> None:
        if stage == "candidate_validated":
            raise RuntimeError("injected pre-pointer failure")

    with pytest.raises(RuntimeError, match="pre-pointer failure"):
        publish_financial_result(
            source_duckdb_path=source,
            publication_root=publication_root,
            plan=plan(candidate_generation, current_generation),
            on_stage=fail_before_pointer,
        )

    assert generation_manifest_path(publication_root, candidate_generation).is_file()
    assert generation_database_path(publication_root, candidate_generation).is_file()
    sealed = validate_sealed_financial_generation(
        publication_root,
        generation=candidate_generation,
        expected_manifest_sha256=None,
        reader_api_version=FINANCIAL_PUBLICATION_API_VERSION,
        reader_schema_version=FINANCIAL_PUBLICATION_SCHEMA_VERSION,
    )
    assert sealed.generation == candidate_generation
    pointer = read_publication_pointer(publication_root)
    assert pointer is not None
    assert pointer["generation"] == current_generation
    with pytest.raises(
        PnlPublishedGenerationConflictError,
        match="not in the committed retention window",
    ):
        publication_service.read_published_pnl_by_business_insights(
            settings,
            year=2026,
            as_of_date="2026-08-31",
            generation=candidate_generation,
        )
    assert (
        lifecycle._completed_publication_for_intent(
            settings,
            report_date="2026-08-31",
            run_id=run_id,
        )
        is None
    )


@pytest.mark.parametrize("failure_type", [RuntimeError, TypeError])
def test_page_recovery_failure_status_api_omits_private_payload(tmp_path, monkeypatch, failure_type):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.app.api.routes import pnl as routes

    settings = _settings(tmp_path)
    governance = GovernanceRepository(base_dir=settings.governance_path)
    for run_id, report_date in [("page-failed", "2026-06-30"), ("page-next", "2026-07-31")]:
        governance.append(CACHE_BUILD_RUN_STREAM, {
            "run_id": run_id, "job_name": "pnl_by_business_page_prepare",
            "cache_key": "pnl_by_business_page_prepare",
            "status": "queued", "target_year": 2026, "report_date": report_date,
            "queued_at": "2026-09-13T01:00:00+00:00", "expected_previous_generation": None,
            "protocol_version": lifecycle.PNL_BY_BUSINESS_PAGE_INTENT_PROTOCOL_VERSION,
        })
    monkeypatch.setattr(lifecycle, "_completed_publication_for_intent", lambda *_a, **_k: None)
    monkeypatch.setattr(lifecycle, "_dispatch_persisted_dependency_batches", lambda *_a, **_k: [])
    marker = "synthetic-page-dispatch-private-token"
    calls = []
    def dispatch(**kwargs):
        calls.append(kwargs["run_id"])
        if kwargs["run_id"] == "page-failed":
            raise failure_type(marker)
    monkeypatch.setattr(lifecycle.prepare_pnl_by_business_page_envelope_actor, "send", dispatch)
    result = lifecycle.recover_pending_pnl_by_business_page_rebuilds(settings)
    assert result["status"] == "partial_failure"
    assert result["failed_count"] == 1
    assert result["dispatched_count"] == 1
    assert calls == ["page-failed", "page-next"]
    latest = [row for row in governance.read_all(CACHE_BUILD_RUN_STREAM) if row["run_id"] == "page-failed"][-1]
    assert latest["status"] == "failed"
    assert latest["failure_category"] == "page_recovery_failure"
    monkeypatch.setattr(readiness, "list_retained_pnl_by_business_publications", lambda *_a, **_k: ())
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    monkeypatch.setattr(routes, "_ensure_pnl_read_allowed", lambda *_a: None)
    monkeypatch.setattr(routes, "_precompute_rebuild_permissions", lambda *_a: {})
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as client:
        response = client.get("/api/pnl/by-business/precompute-status", params={"year": 2026, "as_of_date": "2026-06-30"})
    assert response.status_code == 200
    assert marker not in response.text
    assert marker not in str(result)
    assert marker not in str(latest)
    assert failure_type.__name__ in response.text


@pytest.mark.parametrize("failure_type", [ValueError, RuntimeError, TypeError])
def test_page_initial_dispatch_keeps_failure_and_safe_status(tmp_path, monkeypatch, failure_type):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.app.api.routes import pnl as routes
    from unittest.mock import Mock
    settings = _settings(tmp_path)
    class Repository:
        def __init__(self, _path): pass
        def max_formal_or_nonstd_report_date_in_year(self, *, year, as_of_cap): return as_of_cap
        def pnl_by_business_precompute_dependency_revision(self, *, year, as_of_date): return 1
    marker = "synthetic-page-initial-dispatch-private-token"
    failure = failure_type(marker)
    queue = Mock(side_effect=failure)
    actor = Mock()
    monkeypatch.setattr(lifecycle.prepare_pnl_by_business_page_envelope_actor, "send", actor)
    def request_page(*_args, **_kwargs):
        return lifecycle.request_pnl_by_business_page_rebuild(settings, year=2026, as_of_date="2026-06-30", queue_refresh=queue, repository_cls=Repository)
    with pytest.raises(failure_type) as caught:
        request_page()
    assert caught.value is failure
    actor.assert_not_called()
    stored = GovernanceRepository(base_dir=settings.governance_path).read_all(CACHE_BUILD_RUN_STREAM)[-1]
    assert stored["status"] == "failed"
    assert stored["failure_category"] == "page_dispatch_failure"
    monkeypatch.setattr(readiness, "list_retained_pnl_by_business_publications", lambda *_a, **_k: ())
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    monkeypatch.setattr(routes, "_ensure_pnl_read_allowed", lambda *_a: None)
    monkeypatch.setattr(routes, "_ensure_by_business_adjustment_write_allowed", lambda *_a: None)
    monkeypatch.setattr(routes, "_precompute_rebuild_permissions", lambda *_a: {})
    service = routes._pnl_service()
    monkeypatch.setattr(service, "request_pnl_by_business_page_rebuild", request_page)
    app = FastAPI(); app.include_router(routes.router)
    with TestClient(app) as client:
        response = client.get("/api/pnl/by-business/precompute-status", params={"year": 2026, "as_of_date": "2026-06-30"})
        assert response.status_code == 200
        assert marker not in response.text
        if failure_type is not TypeError:
            response = client.post("/api/pnl/by-business/precompute-rebuild", params={"year": 2026, "as_of_date": "2026-06-30", "include_page_dependencies": True})
            assert response.status_code == (422 if failure_type is ValueError else 503)
            assert marker not in response.text
    assert marker not in str(stored)


@pytest.mark.parametrize("failure_type", [ValueError, RuntimeError])
def test_page_rebuild_post_failure_omits_private_payload(tmp_path, monkeypatch, failure_type):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.app.api.routes import pnl as routes
    from unittest.mock import Mock
    settings = _settings(tmp_path)
    marker = "synthetic-page-post-private-token"
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    monkeypatch.setattr(routes, "_ensure_by_business_adjustment_write_allowed", lambda *_a: None)
    monkeypatch.setattr(routes._pnl_service(), "request_pnl_by_business_page_rebuild", Mock(side_effect=failure_type(marker)))
    app = FastAPI(); app.include_router(routes.router)
    with TestClient(app) as client:
        response = client.post("/api/pnl/by-business/precompute-rebuild", params={"year": 2026, "as_of_date": "2026-06-30", "include_page_dependencies": True})
    assert response.status_code == (422 if failure_type is ValueError else 503)
    assert marker not in response.text
    assert failure_type.__name__ in response.text
