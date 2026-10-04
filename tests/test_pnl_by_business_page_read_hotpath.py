from __future__ import annotations

import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from backend.app.repositories.financial_result_publication_repo import (
    FinancialPublicationInvalid,
    FinancialPublicationUnavailable,
)
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM
from backend.app.services import pnl_by_business_page_dates as page_dates
from backend.app.services import pnl_by_business_page_readiness as readiness
from backend.app.services import pnl_by_business_publication_service as publication_service
from backend.app.services.pnl_service_by_business_support import (
    pnl_by_business_page_dependencies,
)
from backend.app.services.pnl_task_dispatch import (
    CACHE_KEY,
    PNL_BY_BUSINESS_PRECOMPUTE_CACHE_KEY,
)


def _page_manifest(*report_dates: str) -> dict[str, object]:
    return {
        "sealed_payload": {
            "coverage_dates": {"pnl_by_business_page": list(report_dates)},
            "dependency_versions": {},
            "tables": [
                {
                    "name": publication_service.PNL_BY_BUSINESS_PAGE_ENVELOPE_TABLE,
                    "date_column": "report_date",
                    "required_dates": list(report_dates),
                    "coverage_row_counts": {value: 1 for value in report_dates},
                }
            ],
        }
    }


class _PageRowConnection:
    def __init__(self) -> None:
        self.query_count = 0

    def execute(self, _query, _parameters):
        self.query_count += 1
        return self

    def fetchall(self):
        return [
            (
                1,
                json.dumps({}),
                "source-version",
                "rule-version",
                "adjustment-version",
                "2026-09-14 08:00:00+08:00",
                publication_service.PNL_BY_BUSINESS_PAGE_PROTOCOL_VERSION,
            )
        ]


def test_page_dates_reads_only_formal_pnl_receipts(monkeypatch) -> None:
    calls: list[tuple[str, tuple[str, ...]]] = []

    class Repository:
        def __init__(self, *, base_dir):
            assert base_dir == "governance"

        def read_by_cache_keys(self, stream, cache_keys):
            calls.append((stream, tuple(cache_keys)))
            return [
                {
                    "run_id": "run-1",
                    "job_name": "pnl_materialize",
                    "cache_key": CACHE_KEY,
                    "status": "completed",
                    "report_date": "2026-01-31",
                },
                {
                    "run_id": "run-1",
                    "job_name": "pnl_materialize",
                    "cache_key": CACHE_KEY,
                    "status": "failed",
                    "report_date": "2026-01-31",
                },
                {
                    "run_id": "run-2",
                    "job_name": "pnl_materialize",
                    "cache_key": CACHE_KEY,
                    "status": "completed",
                    "report_date": "2026-02-28",
                },
            ]

    monkeypatch.setattr(page_dates, "GovernanceRepository", Repository)
    monkeypatch.setattr(
        page_dates,
        "list_retained_pnl_by_business_publication_coverage",
        lambda *_a, **_k: (),
    )

    result = page_dates.pnl_by_business_page_dates_envelope(
        SimpleNamespace(
            governance_path="governance",
            financial_publication_root="published",
        )
    )

    assert calls == [(CACHE_BUILD_RUN_STREAM, (CACHE_KEY,))]
    assert result["result"]["report_dates"] == ["2026-02-28"]


def test_page_status_reads_complete_precompute_and_page_histories(monkeypatch) -> None:
    calls: list[tuple[str, tuple[str, ...]]] = []

    class Repository:
        def __init__(self, *, base_dir):
            assert base_dir == "governance"

        def read_by_cache_keys(self, stream, cache_keys):
            calls.append((stream, tuple(cache_keys)))
            return [
                {
                    "run_id": "page-run",
                    "job_name": "pnl_by_business_page_prepare",
                    "cache_key": "pnl_by_business_page_prepare",
                    "status": "queued",
                    "report_date": "2026-06-30",
                    "queued_at": "2026-09-14T01:00:00+00:00",
                    "protocol_version": "pnl_by_business_page_intent/v1",
                },
                {
                    "run_id": "page-run",
                    "job_name": "pnl_by_business_page_prepare",
                    "cache_key": "pnl_by_business_page_prepare",
                    "status": "failed",
                    "report_date": "2026-06-30",
                    "queued_at": "2026-09-14T01:00:00+00:00",
                    "finished_at": "2026-09-14T01:01:00+00:00",
                    "error_message": "page preparation failed",
                    "failure_category": "worker_error",
                    "protocol_version": "pnl_by_business_page_intent/v1",
                },
            ]

    monkeypatch.setattr(readiness, "GovernanceRepository", Repository)
    monkeypatch.setattr(
        readiness,
        "list_retained_pnl_by_business_publications",
        lambda *_a, **_k: (),
    )
    monkeypatch.setattr(
        readiness,
        "_adjustment_handoff_status",
        lambda *_a, **_k: {"pending": False, "last_event_at": None},
    )

    result = readiness.pnl_by_business_published_page_status(
        SimpleNamespace(governance_path="governance"),
        year=2026,
        as_of_date="2026-06-30",
    )

    assert calls == [
        (
            CACHE_BUILD_RUN_STREAM,
            (
                PNL_BY_BUSINESS_PRECOMPUTE_CACHE_KEY,
                "pnl_by_business_page_prepare",
            ),
        )
    ]
    assert result["status"] == "failed"
    assert result["refresh_error_message"] == "page preparation failed"
    assert result["refresh_failure_category"] == "worker_error"


def test_page_status_selects_exact_retained_historical_generation(monkeypatch) -> None:
    versions: dict[str, str] = {}
    for dependency in pnl_by_business_page_dependencies(
        year=2026,
        as_of_date="2026-08-31",
    ):
        prefix = f"pnl_by_business.{dependency['key']}"
        requested = dependency["requested_report_date"]
        versions[f"{prefix}.requested_report_date"] = requested
        versions[f"{prefix}.resolved_report_date"] = requested

    monkeypatch.setattr(
        readiness,
        "list_retained_pnl_by_business_publications",
        lambda *_a, **_k: (
            {
                "generation": "financial-20260731-current",
                "report_date": "2026-07-31",
            },
            {
                "generation": "financial-20260831-retained",
                "report_date": "2026-08-31",
                "dependency_versions": versions,
                "source_version": "source-august",
                "rule_version": "rules-august",
                "prepared_at": "2026-09-14T00:52:45+00:00",
            },
        ),
    )

    class Repository:
        def __init__(self, *, base_dir):
            assert base_dir == "governance"

        def read_by_cache_keys(self, _stream, _cache_keys):
            return []

    monkeypatch.setattr(readiness, "GovernanceRepository", Repository)
    monkeypatch.setattr(
        readiness,
        "_adjustment_handoff_status",
        lambda *_a, **_k: {"pending": False, "last_event_at": None},
    )

    result = readiness.pnl_by_business_published_page_status(
        SimpleNamespace(governance_path="governance"),
        year=2026,
        as_of_date="2026-08-31",
    )

    assert result["readiness"] == "ready"
    assert result["serving_mode"] == "published"
    assert result["generation"] == "financial-20260831-retained"
    assert result["report_date"] == "2026-08-31"


def test_unpublished_materialized_date_is_selectable_and_returns_prepare_state(
    monkeypatch,
) -> None:
    class DatesRepository:
        def __init__(self, *, base_dir):
            assert base_dir == "governance"

        def read_by_cache_keys(self, _stream, _cache_keys):
            return [
                {
                    "run_id": "materialized-september",
                    "job_name": "pnl_materialize",
                    "cache_key": CACHE_KEY,
                    "status": "completed",
                    "report_date": "2026-09-30",
                }
            ]

    catalog = (
        {
            "generation": "financial-20260831-retained",
            "manifest_sha256": "a" * 64,
            "report_date": "2026-08-31",
        },
    )
    monkeypatch.setattr(page_dates, "GovernanceRepository", DatesRepository)
    monkeypatch.setattr(
        page_dates,
        "list_retained_pnl_by_business_publication_coverage",
        lambda *_a, **_k: catalog,
    )
    dates = page_dates.pnl_by_business_page_dates_envelope(
        SimpleNamespace(governance_path="governance")
    )
    assert dates["result"]["report_dates"] == ["2026-08-31", "2026-09-30"]

    class StatusRepository(DatesRepository):
        def read_by_cache_keys(self, _stream, _cache_keys):
            return []

    monkeypatch.setattr(readiness, "GovernanceRepository", StatusRepository)
    monkeypatch.setattr(
        readiness,
        "list_retained_pnl_by_business_publications",
        lambda *_a, **_k: catalog,
    )
    monkeypatch.setattr(
        readiness,
        "_adjustment_handoff_status",
        lambda *_a, **_k: {"pending": False, "last_event_at": None},
    )
    status = readiness.pnl_by_business_published_page_status(
        SimpleNamespace(governance_path="governance"),
        year=2026,
        as_of_date="2026-09-30",
    )

    assert status["readiness"] == "stale"
    assert status["serving_mode"] == "unavailable"
    assert status["generation"] is None
    assert status["report_date"] == "2026-09-30"


@pytest.mark.parametrize(
    "error",
    [
        FinancialPublicationUnavailable("generation was revoked"),
        FinancialPublicationUnavailable("generation expired"),
        FinancialPublicationInvalid("generation artifact is corrupt"),
    ],
)
def test_retained_catalog_excludes_unusable_generations(monkeypatch, error) -> None:
    monkeypatch.setattr(
        publication_service,
        "read_publication_pointer",
        lambda *_a, **_k: {
            "retained_generations": [{"generation": "unusable-generation"}]
        },
    )
    monkeypatch.setattr(
        publication_service,
        "open_financial_generation",
        lambda *_a, **_k: (_ for _ in ()).throw(error),
    )

    result = publication_service.list_retained_pnl_by_business_publications(
        SimpleNamespace(financial_publication_root="published"),
        year=2026,
    )

    assert result == ()


def test_page_date_coverage_uses_committed_manifest_without_opening_database(
    monkeypatch,
) -> None:
    resolved_generations: list[str] = []
    monkeypatch.setattr(
        publication_service,
        "read_publication_pointer",
        lambda *_a, **_k: {
            "retained_generations": [{"generation": "committed-generation"}]
        },
    )

    def resolve(_root, *, generation, **_kwargs):
        resolved_generations.append(generation)
        return SimpleNamespace(
            generation=generation,
            manifest=_page_manifest("2026-08-31"),
            manifest_sha256="d" * 64,
        )

    monkeypatch.setattr(publication_service, "resolve_financial_generation", resolve)
    monkeypatch.setattr(
        publication_service,
        "open_financial_generation",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not open DuckDB")),
    )

    result = publication_service.list_retained_pnl_by_business_publication_coverage(
        SimpleNamespace(financial_publication_root="published"),
        year=2026,
    )

    assert result == (
        {
            "generation": "committed-generation",
            "manifest_sha256": "d" * 64,
            "report_date": "2026-08-31",
        },
    )
    assert resolved_generations == ["committed-generation"]


@pytest.mark.parametrize(
    "error",
    [
        FinancialPublicationUnavailable("generation was revoked"),
        FinancialPublicationUnavailable("generation expired"),
        FinancialPublicationInvalid("generation artifact is corrupt"),
    ],
)
def test_page_date_coverage_excludes_unusable_generations(monkeypatch, error) -> None:
    monkeypatch.setattr(
        publication_service,
        "read_publication_pointer",
        lambda *_a, **_k: {
            "retained_generations": [{"generation": "unusable-generation"}]
        },
    )
    monkeypatch.setattr(
        publication_service,
        "resolve_financial_generation",
        lambda *_a, **_k: (_ for _ in ()).throw(error),
    )

    result = publication_service.list_retained_pnl_by_business_publication_coverage(
        SimpleNamespace(financial_publication_root="published"),
        year=2026,
    )

    assert result == ()


def test_governance_stale_manifest_date_is_selectable_but_cannot_be_ready(
    monkeypatch,
) -> None:
    pointer = {"retained_generations": [{"generation": "stale-generation"}]}
    resolved = SimpleNamespace(
        generation="stale-generation",
        manifest=_page_manifest("2026-08-31"),
        manifest_sha256="e" * 64,
    )
    monkeypatch.setattr(
        publication_service,
        "read_publication_pointer",
        lambda *_a, **_k: pointer,
    )
    monkeypatch.setattr(
        publication_service,
        "resolve_financial_generation",
        lambda *_a, **_k: resolved,
    )

    @contextmanager
    def open_generation(*_args, **_kwargs):
        yield _PageRowConnection(), resolved

    monkeypatch.setattr(publication_service, "open_financial_generation", open_generation)
    monkeypatch.setattr(
        publication_service,
        "_require_current_governance",
        lambda *_a, **_k: (_ for _ in ()).throw(
            publication_service.PnlPublishedGenerationConflictError("governance is stale")
        ),
    )

    selectable = publication_service.list_retained_pnl_by_business_publication_coverage(
        SimpleNamespace(financial_publication_root="published"),
        year=2026,
    )
    ready_catalog = publication_service.list_retained_pnl_by_business_publications(
        SimpleNamespace(financial_publication_root="published"),
        year=2026,
        as_of_date="2026-08-31",
    )

    assert [item["report_date"] for item in selectable] == ["2026-08-31"]
    assert ready_catalog == ()


def test_retained_catalog_skips_invalid_current_and_keeps_valid_history(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        publication_service,
        "read_publication_pointer",
        lambda *_a, **_k: {
            "retained_generations": [
                {"generation": "damaged-current"},
                {"generation": "valid-retained"},
            ]
        },
    )

    @contextmanager
    def open_generation(_root, *, generation, **_kwargs):
        if generation == "damaged-current":
            raise FinancialPublicationInvalid("current artifact is damaged")
        yield _PageRowConnection(), SimpleNamespace(
            generation=generation,
            manifest=_page_manifest("2026-08-31"),
            manifest_sha256="a" * 64,
        )

    monkeypatch.setattr(
        publication_service,
        "open_financial_generation",
        open_generation,
    )
    monkeypatch.setattr(
        publication_service,
        "_require_current_governance",
        lambda *_a, **_k: None,
    )

    result = publication_service.list_retained_pnl_by_business_publications(
        SimpleNamespace(financial_publication_root="published"),
        year=2026,
    )

    assert len(result) == 1
    assert result[0]["generation"] == "valid-retained"
    assert result[0]["report_date"] == "2026-08-31"


def test_retained_catalog_prefers_current_when_both_generations_cover_target(
    monkeypatch,
) -> None:
    opened: list[str] = []
    monkeypatch.setattr(
        publication_service,
        "read_publication_pointer",
        lambda *_a, **_k: {
            "retained_generations": [
                {"generation": "current-generation"},
                {"generation": "previous-generation"},
            ]
        },
    )

    @contextmanager
    def open_generation(_root, *, generation, **_kwargs):
        opened.append(generation)
        yield _PageRowConnection(), SimpleNamespace(
            generation=generation,
            manifest=_page_manifest("2026-08-31"),
            manifest_sha256=generation,
        )

    monkeypatch.setattr(publication_service, "open_financial_generation", open_generation)
    monkeypatch.setattr(
        publication_service,
        "_require_current_governance",
        lambda *_a, **_k: None,
    )

    result = publication_service.list_retained_pnl_by_business_publications(
        SimpleNamespace(financial_publication_root="published"),
        year=2026,
        as_of_date="2026-08-31",
    )

    assert [item["generation"] for item in result] == ["current-generation"]
    assert opened == ["current-generation"]


def test_retained_catalog_rechecks_selected_generation_after_pointer_rotation(
    monkeypatch,
) -> None:
    pointer_state = {"retained": ["selected-generation", "older-generation"]}
    monkeypatch.setattr(
        publication_service,
        "read_publication_pointer",
        lambda *_a, **_k: {
            "retained_generations": [
                {"generation": generation} for generation in pointer_state["retained"]
            ]
        },
    )

    @contextmanager
    def open_generation(_root, *, generation, **_kwargs):
        pointer_state["retained"] = ["new-current-generation", "selected-generation"]
        refreshed_pointer = publication_service.read_publication_pointer(
            "published",
            require_valid=False,
        )
        assert refreshed_pointer is not None
        retained = [
            str(item["generation"])
            for item in refreshed_pointer["retained_generations"]
        ]
        if generation not in retained:
            raise FinancialPublicationUnavailable("generation was evicted")
        yield _PageRowConnection(), SimpleNamespace(
            generation=generation,
            manifest=_page_manifest("2026-08-31"),
            manifest_sha256="b" * 64,
        )

    monkeypatch.setattr(publication_service, "open_financial_generation", open_generation)
    monkeypatch.setattr(
        publication_service,
        "_require_current_governance",
        lambda *_a, **_k: None,
    )

    result = publication_service.list_retained_pnl_by_business_publications(
        SimpleNamespace(financial_publication_root="published"),
        year=2026,
        as_of_date="2026-08-31",
    )

    assert [item["generation"] for item in result] == ["selected-generation"]
    assert pointer_state["retained"] == ["new-current-generation", "selected-generation"]


def test_retained_catalog_ignores_physical_row_not_declared_by_manifest(monkeypatch) -> None:
    connection = _PageRowConnection()
    monkeypatch.setattr(
        publication_service,
        "read_publication_pointer",
        lambda *_a, **_k: {
            "retained_generations": [{"generation": "current-generation"}]
        },
    )

    @contextmanager
    def open_generation(_root, *, generation, **_kwargs):
        yield connection, SimpleNamespace(
            generation=generation,
            manifest=_page_manifest("2026-07-31"),
            manifest_sha256="c" * 64,
        )

    monkeypatch.setattr(publication_service, "open_financial_generation", open_generation)

    result = publication_service.list_retained_pnl_by_business_publications(
        SimpleNamespace(financial_publication_root="published"),
        year=2026,
        as_of_date="2026-08-31",
    )

    assert result == ()
    assert connection.query_count == 0


def test_pinned_history_read_rejects_generation_evicted_after_status(monkeypatch) -> None:
    selected_generation = "financial-20260831-selected"

    def evicted(*_args, **_kwargs):
        raise FinancialPublicationUnavailable(
            "Financial publication is not in the committed retention window."
        )

    monkeypatch.setattr(publication_service, "open_financial_generation", evicted)

    with pytest.raises(
        publication_service.PnlPublishedGenerationConflictError,
        match="not in the committed retention window",
    ):
        publication_service.read_published_pnl_by_business_insights(
            SimpleNamespace(financial_publication_root="published"),
            year=2026,
            as_of_date="2026-08-31",
            generation=selected_generation,
        )
