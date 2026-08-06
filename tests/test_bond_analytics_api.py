"""Contract tests for bond-analytics HTTP API (envelope + core result fields)."""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone
from typing import Any

import duckdb
import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport

from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.schemas.materialize import CacheBuildRunRecord
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module
from tests.test_bond_analytics_materialize_flow import (
    _seed_bond_snapshot_rows,
    seed_yield_curves_for_bond_analytics_tests,
)

REPORT_DATE = "2026-03-31"
BOND_ANALYTICS_READ_HEADERS = {"X-User-Id": "bond-analytics-read-user", "X-User-Role": "viewer"}


@pytest.fixture(autouse=True)
def _keep_bond_analytics_api_tests_local(monkeypatch) -> None:
    """API contract tests should not trigger worker-side vendor curve backfills."""
    curve_task_mod = load_module(
        "backend.app.tasks.yield_curve_materialize",
        "backend/app/tasks/yield_curve_materialize.py",
    )
    monkeypatch.setattr(
        curve_task_mod,
        "ensure_yield_curve_inputs_on_or_before",
        lambda **_kwargs: None,
    )


def _perf_records(caplog, endpoint: str):
    return [
        record
        for record in caplog.records
        if record.name == "backend.app.api.perf" and getattr(record, "endpoint", None) == endpoint
    ]


def test_log_api_perf_message_includes_basic_formatter_fields(monkeypatch, caplog):
    perf_logging = load_module("backend.app.api.perf_logging", "backend/app/api/perf_logging.py")
    monkeypatch.setattr(perf_logging.time, "perf_counter", lambda: 12.345)

    with caplog.at_level(logging.INFO, logger="backend.app.api.perf"):
        payload = perf_logging.log_api_perf(
            endpoint="/test/perf",
            started_at=12.0,
            payload={"result_meta": {"trace_id": "trace-123", "result_kind": "test.kind"}},
            duckdb_statement_count=7,
        )

    record = caplog.records[-1]
    assert payload["result_meta"]["trace_id"] == "trace-123"
    assert (
        record.getMessage()
        == 'moss_api_perf endpoint="/test/perf" duration_ms=345.0 '
        'trace_id="trace-123" result_kind="test.kind" duckdb_statement_count=7'
    )
    assert record.endpoint == "/test/perf"
    assert record.duration_ms == 345.0
    assert record.trace_id == "trace-123"
    assert record.result_kind == "test.kind"
    assert record.duckdb_statement_count == 7


def test_log_api_perf_message_quotes_spaces_and_distinguishes_empty_from_none(monkeypatch, caplog):
    perf_logging = load_module("backend.app.api.perf_logging", "backend/app/api/perf_logging.py")
    monkeypatch.setattr(perf_logging.time, "perf_counter", lambda: 12.345)

    with caplog.at_level(logging.INFO, logger="backend.app.api.perf"):
        perf_logging.log_api_perf(
            endpoint="/test perf",
            started_at=12.0,
            payload={"result_meta": {"trace_id": "trace 123", "result_kind": ""}},
            duckdb_statement_count=None,
        )

    assert (
        caplog.records[-1].getMessage()
        == 'moss_api_perf endpoint="/test perf" duration_ms=345.0 '
        'trace_id="trace 123" result_kind="" duckdb_statement_count=null'
    )


def test_log_api_perf_skips_message_encoding_when_info_disabled(monkeypatch, caplog):
    perf_logging = load_module("backend.app.api.perf_logging", "backend/app/api/perf_logging.py")
    payload = {"result_meta": {"trace_id": "trace-disabled", "result_kind": "test.disabled"}}
    encoded_values = []

    monkeypatch.setattr(
        perf_logging.json,
        "dumps",
        lambda *args, **kwargs: encoded_values.append((args, kwargs)) or '"encoded"',
    )
    with caplog.at_level(logging.WARNING, logger="backend.app.api.perf"):
        returned = perf_logging.log_api_perf(
            endpoint="/test/disabled",
            started_at=12.0,
            payload=payload,
            duckdb_statement_count=7,
        )

    assert returned is payload
    assert encoded_values == []
    assert not any(record.name == "backend.app.api.perf" for record in caplog.records)


_BOND_ANALYTICS_CASES: list[tuple[str, dict[str, str]]] = [
    (
        "/api/bond-analytics/dates",
        {},
    ),
    (
        "/api/bond-analytics/return-decomposition",
        {"report_date": REPORT_DATE, "period_type": "MoM"},
    ),
    (
        "/api/bond-analytics/benchmark-excess",
        {
            "report_date": REPORT_DATE,
            "period_type": "MoM",
            "benchmark_id": "CDB_INDEX",
        },
    ),
    (
        "/api/bond-analytics/krd-curve-risk",
        {"report_date": REPORT_DATE},
    ),
    (
        "/api/bond-analytics/dv01-risk",
        {"report_date": REPORT_DATE, "accounting_class": "OCI", "top_n": "20", "shock_bps": "1,10,25,50"},
    ),
    (
        "/api/bond-analytics/dv01-reconciliation",
        {"report_date": REPORT_DATE, "accounting_class": "OCI"},
    ),
    (
        "/api/bond-analytics/dv01-movement",
        {"report_date": REPORT_DATE, "accounting_class": "OCI", "top_n": "20"},
    ),
    (
        "/api/bond-analytics/credit-spread-migration",
        {"report_date": REPORT_DATE},
    ),
    (
        "/api/bond-analytics/action-attribution",
        {"report_date": REPORT_DATE, "period_type": "MoM"},
    ),
    (
        "/api/bond-analytics/accounting-class-audit",
        {"report_date": REPORT_DATE},
    ),
    (
        "/api/bond-analytics/portfolio-headlines",
        {"report_date": REPORT_DATE},
    ),
    (
        "/api/bond-analytics/top-holdings",
        {"report_date": REPORT_DATE, "top_n": "20"},
    ),
    (
        "/api/bond-analytics/yield-curve-term-structure",
        {"report_date": REPORT_DATE, "curve_types": "treasury"},
    ),
]


_BOND_ANALYTICS_READ_CASES: list[tuple[str, dict[str, str]]] = [
    *_BOND_ANALYTICS_CASES,
    (
        "/api/bond-analytics/dv01-action-plan",
        {
            "report_date": REPORT_DATE,
            "accounting_class": "OCI",
            "top_n": "20",
            "limit_dv01": "1000",
            "warning_dv01": "800",
        },
    ),
    (
        "/api/bond-analytics/dv01-limit-config-status",
        {"report_date": REPORT_DATE},
    ),
    (
        "/api/bond-analytics/position-changes",
        {"report_date": REPORT_DATE, "top_n": "5"},
    ),
    (
        "/api/bond-analytics/refresh-status",
        {"run_id": "bond-analytics-run"},
    ),
]


def _setup_route_scope_store(tmp_path, monkeypatch) -> UserScopeRepository:
    sqlite_path = tmp_path / "auth-scope-contract.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    repo = UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}")
    _grant_bond_analytics_read_scope(repo)
    return repo


def _grant_bond_analytics_read_scope(repo: UserScopeRepository, *, user_id: str = "*") -> None:
    repo.grant_scope(
        user_id=user_id,
        role=None,
        resource="bond_analytics",
        action="read",
    )


@pytest.fixture(autouse=True)
def seed_bond_analytics_read_scope(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "bond-analytics-read-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    _grant_bond_analytics_read_scope(UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}"))
    yield
    get_settings.cache_clear()


def _assert_envelope(payload: dict[str, Any]) -> None:
    assert "result_meta" in payload
    assert "result" in payload
    meta = payload["result_meta"]
    for key in ("trace_id", "basis", "source_version", "rule_version"):
        assert key in meta, f"result_meta missing {key!r}"
        assert meta[key] not in (None, ""), f"result_meta.{key} must be non-empty"

    result = payload["result"]
    # `/dates` returns only ``report_dates``; other payloads may include both lists and ``report_date``.
    if "report_dates" in result and "report_date" not in result:
        assert isinstance(result["report_dates"], list)
        return
    for key in ("report_date", "computed_at", "warnings"):
        assert key in result, f"result missing {key!r}"


def _seed_materialized_bond_analytics(duckdb_path, governance_dir) -> None:
    get_settings.cache_clear()
    _seed_bond_snapshot_rows(str(duckdb_path))
    task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )


def _mark_one_fact_row_as_unmapped_accounting_class(duckdb_path) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update fact_formal_bond_analytics_daily
            set accounting_class = 'other',
                accounting_rule_id = 'test_unmapped_accounting_class'
            where report_date = ? and instrument_code = 'CB-001'
            """,
            [REPORT_DATE],
        )
    finally:
        conn.close()


async def _check_all_endpoints() -> None:
    current_app = load_module("backend.app.main", "backend/app/main.py").app
    transport = ASGITransport(app=current_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for path, params in _BOND_ANALYTICS_CASES:
            response = await client.get(path, params=params)
            assert response.status_code == 200, (
                f"{path} {params} -> {response.status_code}: {response.text}"
            )
            payload = response.json()
            _assert_envelope(payload)


def test_bond_analytics_endpoints_envelope_and_result_shape() -> None:
    """Six bond-analytics routes return 200 + result_meta/result with required keys."""
    asyncio.run(_check_all_endpoints())


def test_bond_analytics_each_path_distinct_contract() -> None:
    """Sanity: each configured path is exercised once."""
    paths = [p for p, _ in _BOND_ANALYTICS_CASES]
    assert len(paths) == len(set(paths)) == 13


def test_bond_analytics_read_surfaces_require_explicit_read_scope(tmp_path, monkeypatch) -> None:
    route_module = load_module(
        "backend.app.api.routes.bond_analytics",
        "backend/app/api/routes/bond_analytics.py",
    )
    for name in (
        "bond_analytics_dates_envelope",
        "get_return_decomposition",
        "get_return_decomposition_summary",
        "get_benchmark_excess",
        "get_krd_curve_risk",
        "get_dv01_risk",
        "get_dv01_reconciliation",
        "get_dv01_movement",
        "get_dv01_action_plan",
        "get_dv01_limit_config_status",
        "get_credit_spread_migration",
        "get_yield_curve_term_structure",
        "get_portfolio_headlines",
        "get_top_holdings",
        "get_position_changes",
        "get_action_attribution",
        "get_accounting_class_audit",
    ):
        monkeypatch.setattr(
            route_module,
            name,
            lambda *_args, **_kwargs: {"result_meta": {"result_kind": "bond_analytics.stub"}, "result": {}},
        )
    monkeypatch.setattr(
        route_module,
        "bond_analytics_refresh_status",
        lambda _settings, *, run_id: {"status": "queued", "run_id": run_id},
    )
    sqlite_path = tmp_path / "bond-analytics-read-denied.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    for path, params in _BOND_ANALYTICS_READ_CASES:
        response = client.get(path, params=params, headers=BOND_ANALYTICS_READ_HEADERS)
        assert response.status_code == 403, f"{path}: {response.status_code} {response.text}"


def test_bond_analytics_return_decomposition_summary_detail_uses_summary_projection(monkeypatch) -> None:
    route_module = load_module(
        "backend.app.api.routes.bond_analytics",
        "backend/app/api/routes/bond_analytics.py",
    )
    called = {}

    def _summary(report_date, period_type, asset_class, accounting_class):
        called["args"] = (report_date.isoformat(), period_type, asset_class, accounting_class)
        return {
            "result_meta": {"result_kind": "bond_analytics.return_decomposition"},
            "result": {
                "report_date": report_date.isoformat(),
                "computed_at": "2026-04-13T00:00:00Z",
                "warnings": [],
                "bond_details": [],
            },
        }

    monkeypatch.setattr(route_module, "get_return_decomposition_summary", _summary)
    monkeypatch.setattr(
        route_module,
        "get_return_decomposition",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("full detail path should not be used")),
    )
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    response = client.get(
        "/api/bond-analytics/return-decomposition",
        params={
            "report_date": REPORT_DATE,
            "period_type": "MoM",
            "asset_class": "rate",
            "accounting_class": "AC",
            "detail": "summary",
        },
        headers=BOND_ANALYTICS_READ_HEADERS,
    )

    assert response.status_code == 200, response.text
    assert called["args"] == (REPORT_DATE, "MoM", "rate", "AC")
    assert response.json()["result"]["bond_details"] == []


def test_bond_analytics_dates_returns_available_report_dates(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    _seed_bond_snapshot_rows(str(duckdb_path))
    task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/bond-analytics/dates")

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["result_kind"] == "bond_analytics.dates"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["result"]["report_dates"] == [REPORT_DATE]
    get_settings.cache_clear()


def test_bond_analytics_dv01_risk_returns_numeric_payload(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    _seed_bond_snapshot_rows(str(duckdb_path))
    task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get(
        "/api/bond-analytics/dv01-risk",
        params={
            "report_date": REPORT_DATE,
            "accounting_class": "OCI",
            "top_n": 2,
            "shock_bps": "10,25",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["result_kind"] == "bond_analytics.dv01_risk"
    result = payload["result"]
    assert result["accounting_class"] == "OCI"
    assert result["dv01_basis"] == "face_value_modified_duration"
    assert result["scenario_pnl_basis"] == "face_value_dv01_linear"
    assert result["total_dv01"]["unit"] == "dv01"
    assert result["total_face_value"]["unit"] == "yuan"
    assert result["shock_scenarios"][0]["estimated_pnl"]["unit"] == "yuan"
    assert result["tenor_buckets"][0]["dv01_share"]["unit"] == "ratio"
    assert result["top_bonds"][0]["dv01"]["unit"] == "dv01"
    assert payload["result_meta"]["amount_currency_basis"] == "CNY"
    assert "CNY/RMB basis" in payload["result_meta"]["amount_currency_basis_note"]
    get_settings.cache_clear()


def test_bond_analytics_dv01_reconciliation_returns_numeric_payload(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    _seed_bond_snapshot_rows(str(duckdb_path))
    task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get(
        "/api/bond-analytics/dv01-reconciliation",
        params={
            "report_date": REPORT_DATE,
            "accounting_class": "OCI",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["result_kind"] == "bond_analytics.dv01_reconciliation"
    result = payload["result"]
    assert result["accounting_class"] == "OCI"
    assert result["total_face_value"]["unit"] == "yuan"
    assert result["total_market_value"]["unit"] == "yuan"
    assert result["face_weighted_modified_duration"]["unit"] == "ratio"
    assert result["total_dv01"]["unit"] == "dv01"
    assert result["rows"][0]["face_value"]["unit"] == "yuan"
    assert result["rows"][0]["market_value"]["unit"] == "yuan"
    assert result["rows"][0]["modified_duration"]["unit"] == "ratio"
    assert result["rows"][0]["dv01"]["unit"] == "dv01"
    assert result["rows"][0]["dv01_share"]["unit"] == "ratio"
    get_settings.cache_clear()


def test_bond_analytics_dv01_all_scope_warning_surfaces_over_http(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    _seed_materialized_bond_analytics(duckdb_path, governance_dir)
    _mark_one_fact_row_as_unmapped_accounting_class(duckdb_path)

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    risk_response = client.get(
        "/api/bond-analytics/dv01-risk",
        params={
            "report_date": REPORT_DATE,
            "accounting_class": "all",
        },
    )
    reconciliation_response = client.get(
        "/api/bond-analytics/dv01-reconciliation",
        params={
            "report_date": REPORT_DATE,
            "accounting_class": "all",
        },
    )

    assert risk_response.status_code == 200, risk_response.text
    assert reconciliation_response.status_code == 200, reconciliation_response.text
    risk_warnings = risk_response.json()["result"]["warnings"]
    reconciliation_warnings = reconciliation_response.json()["result"]["warnings"]
    assert any("未映射会计分类" in warning for warning in risk_warnings)
    assert any("other" in warning for warning in risk_warnings)
    assert any("未映射会计分类" in warning for warning in reconciliation_warnings)
    assert any("other" in warning for warning in reconciliation_warnings)
    get_settings.cache_clear()


def test_bond_analytics_dv01_movement_returns_numeric_payload(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    _seed_bond_snapshot_rows(str(duckdb_path))
    task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get(
        "/api/bond-analytics/dv01-movement",
        params={
            "report_date": REPORT_DATE,
            "accounting_class": "OCI",
            "top_n": "20",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["result_kind"] == "bond_analytics.dv01_movement"
    result = payload["result"]
    assert result["accounting_class"] == "OCI"
    assert result["current_total_dv01"]["unit"] == "dv01"
    assert result["previous_total_dv01"]["unit"] == "dv01"
    assert result["delta_dv01"]["unit"] == "dv01"
    assert result["current_face_weighted_modified_duration"]["unit"] == "ratio"
    assert result["current_total_face_value"]["unit"] == "yuan"
    assert result["current_total_market_value"]["unit"] == "yuan"
    if result["attribution"]:
        assert result["attribution"][0]["dv01_delta"]["unit"] == "dv01"
        assert result["attribution"][0]["dv01_delta_share"]["unit"] == "ratio"
    if result["anomaly_bonds"]:
        assert result["anomaly_bonds"][0]["current_dv01"]["unit"] == "dv01"
        assert result["anomaly_bonds"][0]["dv01_delta"]["unit"] == "dv01"
    if result["methodology_checks"]:
        assert result["methodology_checks"][0]["estimated_dv01_from_face_duration"]["unit"] == "dv01"
        assert result["methodology_checks"][0]["dv01_estimate_gap"]["unit"] == "dv01"
    get_settings.cache_clear()


def test_bond_analytics_dv01_action_plan_returns_numeric_payload(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    _seed_bond_snapshot_rows(str(duckdb_path))
    task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get(
        "/api/bond-analytics/dv01-action-plan",
        params={
            "report_date": REPORT_DATE,
            "accounting_class": "OCI",
            "top_n": "20",
            "limit_dv01": "1000",
            "warning_dv01": "800",
            "hedge_instrument_dv01": "250",
            "hedge_target_dv01": "800",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["formal_use_allowed"] is False
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result_meta"]["result_kind"] == "bond_analytics.dv01_action_plan"
    result = payload["result"]
    assert result["accounting_class"] == "OCI"
    assert result["total_dv01"]["unit"] == "dv01"
    assert result["limit_dv01"]["unit"] == "dv01"
    assert result["warning_dv01"]["unit"] == "dv01"
    assert result["dv01_to_reduce"]["unit"] == "dv01"
    assert result["limit_usage"]["unit"] == "ratio"
    assert result["remaining_limit_dv01"]["unit"] == "dv01"
    assert result["policy_basis"] == "page_threshold_fallback"
    assert result["limit_source"] == "page_threshold"
    assert result["limit_source_version"] == "unconfigured"
    assert result["limit_rule_version"] == "rv_dv01_page_threshold_v3"
    assert result["hedge_instrument_dv01"]["unit"] == "dv01"
    assert result["suggested_hedge_units"]["unit"] == "ratio"
    if result["scenario_breaches"]:
        assert result["scenario_breaches"][0]["shock_bp"]["unit"] == "bp"
        assert result["scenario_breaches"][0]["estimated_loss"]["unit"] == "yuan"
    if result["tenor_actions"]:
        assert result["tenor_actions"][0]["dv01_share"]["unit"] == "ratio"
    get_settings.cache_clear()


def test_bond_analytics_dv01_limit_config_status_returns_formal_envelope(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    GovernanceRepository(base_dir=governance_dir).append(
        "bond_dv01_limit_config",
        {
            "report_date": REPORT_DATE,
            "accounting_class": "OCI",
            "limit_dv01": "1200",
            "warning_dv01": "1000",
            "hedge_target_dv01": "1000",
            "limit_source": "risk_committee_minutes",
            "limit_source_version": "risk_minutes_2026_03",
            "limit_rule_version": "rv_dv01_limit_policy_v1",
            "limit_effective_date": "2026-03-01",
        },
    )
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    response = client.get(
        "/api/bond-analytics/dv01-limit-config-status",
        params={"report_date": REPORT_DATE},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["result_kind"] == "bond_analytics.dv01_limit_config_status"
    result = payload["result"]
    assert result["overall_status"] == "incomplete"
    assert result["acceptance_status"] == "blocked"
    assert result["config_stream"] == "bond_dv01_limit_config"
    assert result["required_accounting_classes"] == ["AC", "OCI", "TPL", "all"]
    assert "limit_effective_date" in result["required_fields"]
    assert result["configured_accounting_classes"] == ["OCI"]
    assert result["missing_accounting_classes"] == ["AC", "TPL", "all"]
    assert result["invalid_accounting_classes"] == []
    assert result["missing_business_fields_by_class"]["AC"] == [
        "limit_dv01",
        "warning_dv01",
        "hedge_target_dv01",
        "limit_source",
        "limit_source_version",
        "limit_rule_version",
        "limit_effective_date",
    ]
    assert "bond_dv01_limit_config_review_2026-03-31.csv" in result["dry_run_command"]
    assert "--review-package-dir" in result["review_package_command"]
    assert "AC, TPL, all" in result["acceptance_message"]
    assert "bond_dv01_limit_config" in result["next_action"]
    rows_by_class = {row["accounting_class"]: row for row in result["rows"]}
    assert rows_by_class["OCI"]["status"] == "ready"
    assert rows_by_class["OCI"]["limit_dv01"]["unit"] == "dv01"
    assert rows_by_class["OCI"]["warning_dv01"]["unit"] == "dv01"
    assert rows_by_class["OCI"]["hedge_target_dv01"]["unit"] == "dv01"
    assert rows_by_class["AC"]["status"] == "missing"
    get_settings.cache_clear()


def test_bond_analytics_home_supplement_routes_log_api_perf(tmp_path, monkeypatch, caplog):
    duckdb_path = tmp_path / "empty-bond-analytics-perf.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)

    with caplog.at_level(logging.INFO, logger="backend.app.api.perf"):
        credit = client.get(
            "/api/bond-analytics/credit-spread-migration",
            params={"report_date": REPORT_DATE},
        )
        portfolio = client.get(
            "/api/bond-analytics/portfolio-headlines",
            params={"report_date": REPORT_DATE},
        )

    assert credit.status_code == 200
    assert portfolio.status_code == 200
    credit_records = _perf_records(caplog, "/api/bond-analytics/credit-spread-migration")
    portfolio_records = _perf_records(caplog, "/api/bond-analytics/portfolio-headlines")
    assert credit_records
    assert portfolio_records
    assert getattr(credit_records[-1], "result_kind") == "bond_analytics.credit_spread_migration"
    assert getattr(portfolio_records[-1], "result_kind") == "bond_analytics.portfolio_headlines"
    get_settings.cache_clear()


def test_bond_analytics_refresh_queue_and_status_flow(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    scope_repo = _setup_route_scope_store(tmp_path, monkeypatch)
    scope_repo.grant_scope(
        user_id="*",
        role=None,
        resource="bond_analytics",
        action="refresh",
    )
    _seed_bond_snapshot_rows(str(duckdb_path))
    seed_yield_curves_for_bond_analytics_tests(str(duckdb_path))

    sys.modules.pop("backend.app.main", None)
    sys.modules.pop("backend.app.api", None)
    sys.modules.pop("backend.app.api.routes.bond_analytics", None)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )
    queued_messages: list[dict[str, object]] = []
    monkeypatch.setattr(
        service_mod.materialize_bond_analytics_facts,
        "send",
        lambda **kwargs: queued_messages.append(kwargs),
    )

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    refresh_response = client.post(
        "/api/bond-analytics/refresh",
        params={"report_date": REPORT_DATE},
    )

    assert refresh_response.status_code == 200
    payload = refresh_response.json()
    assert payload["status"] == "queued"
    assert payload["job_name"] == "bond_analytics_materialize"
    assert payload["trigger_mode"] == "async"
    assert payload["cache_key"] == "bond_analytics:materialize:formal"
    assert queued_messages[0]["run_id"] == payload["run_id"]
    assert queued_messages[0]["report_date"] == REPORT_DATE

    status_response = client.get(
        "/api/bond-analytics/refresh-status",
        params={"run_id": payload["run_id"]},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "queued"
    get_settings.cache_clear()


def test_bond_analytics_refresh_requires_explicit_refresh_scope_grant(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    scope_repo = _setup_route_scope_store(tmp_path, monkeypatch)
    _seed_bond_snapshot_rows(str(duckdb_path))
    seed_yield_curves_for_bond_analytics_tests(str(duckdb_path))

    calls: list[tuple[str, str | None]] = []

    def fake_refresh(settings, *, report_date, idempotency_key=None):
        calls.append((report_date, idempotency_key))
        return {"status": "queued", "run_id": "bond-analytics-refresh-auth-test"}

    app = load_module("backend.app.main", "backend/app/main.py").app
    import backend.app.api.routes.bond_analytics as route_module

    monkeypatch.setattr(route_module, "refresh_bond_analytics", fake_refresh)
    client = TestClient(
        app,
        raise_server_exceptions=False,
    )

    denied = client.post(
        "/api/bond-analytics/refresh",
        params={"report_date": REPORT_DATE},
        headers={"X-User-Id": "bond-refresh-user", "X-User-Role": "viewer"},
    )
    assert denied.status_code == 403, denied.text
    assert calls == []

    scope_repo.grant_scope(
        user_id="bond-refresh-user",
        role=None,
        resource="bond_analytics",
        action="refresh",
    )
    allowed = client.post(
        "/api/bond-analytics/refresh",
        params={"report_date": REPORT_DATE},
        headers={"X-User-Id": "bond-refresh-user", "X-User-Role": "viewer"},
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["run_id"] == "bond-analytics-refresh-auth-test"
    assert calls == [(REPORT_DATE, None)]
    get_settings.cache_clear()


def test_bond_analytics_refresh_status_returns_404_for_unknown_run(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.get(
        "/api/bond-analytics/refresh-status",
        params={"run_id": "missing-run"},
    )

    assert response.status_code == 404
    get_settings.cache_clear()


def test_bond_analytics_refresh_returns_409_when_report_date_is_already_inflight(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    scope_repo = _setup_route_scope_store(tmp_path, monkeypatch)
    scope_repo.grant_scope(
        user_id="*",
        role=None,
        resource="bond_analytics",
        action="refresh",
    )
    _seed_bond_snapshot_rows(str(duckdb_path))

    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_BUILD_RUN_STREAM,
        {
            **CacheBuildRunRecord(
                run_id="bond-analytics-inflight",
                job_name="bond_analytics_materialize",
                status="queued",
                cache_key="bond_analytics:materialize:formal",
                lock="lock:duckdb:formal:bond-analytics:materialize",
                source_version="sv_bond_analytics_pending",
                vendor_version="vv_none",
            ).model_dump(),
            "report_date": REPORT_DATE,
            "queued_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )
    response = client.post(
        "/api/bond-analytics/refresh",
        params={"report_date": REPORT_DATE},
    )

    assert response.status_code == 409
    assert "already in progress" in response.json()["detail"]
    get_settings.cache_clear()
