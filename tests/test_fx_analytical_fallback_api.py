"""MS-010: independent synthetic HTTP/auth/publication regression coverage.

The registered router, actual SQLite permission repository, SQL readers, selector,
service and envelope serialization all run. Only settings and inbound identity
are test-supplied. Publication responses are produced by the actual middleware.
Equal-date storage order is not claimed as a provider revision policy: those
assertions follow the selector's documented first-direct/last-older ordered-input
semantics, using the unchanged raw recent_points returned by the same query.
"""
from __future__ import annotations

import json
import math
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes import macro_vendor as routes
from backend.app.core_finance.fx_rates import FxRateUnavailableError
from backend.app.main import SystemReadPublicationMiddleware
from backend.app.repositories.financial_result_publication_repo import (
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)
from backend.app.repositories.system_read_publication_repo import (
    SYSTEM_READ_GENERATION_HEADER,
    system_read_publication_root,
)
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.security.auth_context import AuthContext, get_auth_context
from backend.app.services.macro_vendor_service import load_fx_analytical_payload
from tests.test_system_online_read_boundary import _bundle, _seal_generation, _settings, _write_pointer

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_market_data]

ENDPOINT = "/ui/market-data/fx/analytical"
USD_NAME = "中间价:美元兑人民币"
SCHEMA = Path(__file__).resolve().parents[1] / "backend/app/schema_registry/duckdb/11_choice_macro.sql"
DAY = date(2026, 10, 6)


def _observation(day, value, identity, quality="ok"):
    return (str(day), value, f"sv_synthetic_{identity}", f"vv_synthetic_{identity}", quality)


def _seed(path, series, *, active_series=None):
    """Create only synthetic data, with the actual registered macro schema."""
    with duckdb.connect(str(path)) as conn:
        for statement in SCHEMA.read_text(encoding="utf-8").split("-- MOSS:STMT"):
            if statement.strip():
                conn.execute(statement)
        for series_id, name, observations in series:
            conn.execute(
                """INSERT INTO phase1_macro_vendor_catalog
                   (series_id, series_name, frequency, unit, refresh_tier, fetch_mode,
                    fetch_granularity, policy_note)
                   VALUES (?, ?, 'daily', 'synthetic-unit', 'stable', 'date_slice',
                           'batch', 'Synthetic policy is retained')""",
                [series_id, name],
            )
            for day, value, source, vendor, quality in observations:
                conn.execute(
                    """INSERT INTO fact_choice_macro_daily
                       (series_id, series_name, trade_date, value_numeric, frequency, unit,
                        source_version, vendor_version, quality_flag)
                       VALUES (?, ?, ?, ?, 'daily', 'synthetic-unit', ?, ?, ?)""",
                    [series_id, name, day, value, source, vendor, quality],
                )
        for series_id in active_series or ():
            conn.execute("INSERT INTO choice_market_snapshot(series_id) VALUES (?)", [series_id])


def _fallback_series(identity="G1", *, gap=1, value=7.2):
    return [("synthetic-usd", USD_NAME, [
        _observation(DAY, 0, f"{identity}_invalid"),
        _observation(DAY - timedelta(days=gap), value, f"{identity}_selected"),
        _observation(DAY - timedelta(days=gap + 1), value - 0.1, f"{identity}_older"),
    ])]


def _app(settings, monkeypatch, *, publication=False):
    settings.governance_sql_dsn = f"sqlite:///{Path(settings.duckdb_path).parent / 'synthetic-scopes.sqlite'}"
    settings.postgres_dsn = settings.governance_sql_dsn
    scopes = UserScopeRepository(settings.governance_sql_dsn)
    try:
        scopes.grant_scope(user_id="synthetic-reader", role="viewer", resource="macro_vendor", action="read",
                           operator="synthetic-review", reason="Isolated synthetic MS-010 read permission")
    finally:
        scopes.engine.dispose()
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    app = FastAPI()
    if publication:
        app.add_middleware(SystemReadPublicationMiddleware, settings_provider=lambda: settings)
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        user_id="synthetic-reader", role="viewer", identity_source="synthetic-test")
    return app


@pytest.fixture
def http(tmp_path, monkeypatch):
    settings = SimpleNamespace(duckdb_path=str(tmp_path / "synthetic.duckdb"))
    app = _app(settings, monkeypatch)
    with TestClient(app) as client:
        yield SimpleNamespace(path=Path(settings.duckdb_path), client=client, app=app)


def _read(client, *, headers=None):
    response = client.get(ENDPOINT, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["result_meta"]["basis"] == "analytical"
    assert body["result_meta"]["formal_use_allowed"] is False
    return body


def _only_point(body):
    assert len(body["result"]["groups"]) == 1
    assert len(body["result"]["groups"][0]["series"]) == 1
    return body["result"]["groups"][0]["series"][0]


def _warnings(body):
    return (body["result_meta"].get("filters_applied") or {}).get("warnings", [])


def _assert_lineage(body, identity, value, observed):
    point = _only_point(body)
    assert point["value_numeric"] == value
    assert point["trade_date"] == str(observed)
    assert point["source_version"] == f"sv_synthetic_{identity}_selected"
    assert point["vendor_version"] == f"vv_synthetic_{identity}_selected"
    assert body["result_meta"]["source_version"] == point["source_version"]
    assert body["result_meta"]["vendor_version"] == point["vendor_version"]


@pytest.mark.parametrize("invariant", ["headline_lineage", "null_change", "selector_diagnostic"])
def test_registered_http_route_fallback_observation_contract(http, invariant):
    _seed(http.path, _fallback_series())
    body = _read(http.client)
    point = _only_point(body)
    if invariant == "headline_lineage":
        _assert_lineage(body, "G1", 7.2, DAY - timedelta(days=1))
    elif invariant == "null_change":
        assert point["latest_change"] is None
    else:
        assert any("USD/CNY analytical LOCF: target_date=2026-10-06, observed_date=2026-10-05" in warning
                   for warning in _warnings(body))
        assert any("synthetic-usd" in warning and "change" in warning.lower() and "fallback" in warning.lower()
                   for warning in _warnings(body))
    assert point["quality_flag"] == "warning"
    assert body["result_meta"]["quality_flag"] == "warning"
    assert body["result_meta"]["fallback_mode"] == "none"  # Existing catalog-tier meaning is unchanged.
    assert {key: point[key] for key in ("refresh_tier", "fetch_mode", "fetch_granularity", "policy_note")} == {
        "refresh_tier": "stable", "fetch_mode": "date_slice", "fetch_granularity": "batch",
        "policy_note": "Synthetic policy is retained",
    }
    assert point["recent_points"] == [
        {"trade_date": day, "value_numeric": value, "source_version": source,
         "vendor_version": vendor, "quality_flag": quality}
        for day, value, source, vendor, quality in _fallback_series()[0][2]
    ]


def test_http_stale_fallback_preserves_selector_reason_and_selected_lineage(http):
    _seed(http.path, _fallback_series("stale", gap=45, value=6.8))
    body = _read(http.client)
    _assert_lineage(body, "stale", 6.8, DAY - timedelta(days=45))
    assert _only_point(body)["latest_change"] is None
    assert any("USD/CNY analytical stale fallback beyond 30 days:" in warning for warning in _warnings(body))


@pytest.mark.parametrize("latest,previous,quality,expected", [
    (7.2, 7.1, "ok", 0.1),
    (7.2, 7.2, "ok", 0.0),
    (7.1, 7.2, "ok", -0.1),
    (7.2, 7.1, "warning", 0.1),
    (7.2, None, "ok", None),
])
def test_http_healthy_zero_negative_warning_and_single_observation_controls(http, latest, previous, quality, expected):
    observations = [_observation(DAY, latest, "healthy", quality)]
    if previous is not None:
        observations.append(_observation(DAY - timedelta(days=1), previous, "healthy_prior"))
    _seed(http.path, [("synthetic-usd", USD_NAME, observations)])
    body = _read(http.client)
    point = _only_point(body)
    assert point["value_numeric"] == latest
    assert point["trade_date"] == str(DAY)
    assert point["source_version"] == body["result_meta"]["source_version"] == "sv_synthetic_healthy"
    assert point["vendor_version"] == body["result_meta"]["vendor_version"] == "vv_synthetic_healthy"
    assert point["quality_flag"] == quality
    assert point["latest_change"] == (None if expected is None else pytest.approx(expected))
    assert _warnings(body) == []


@pytest.mark.parametrize("name,group,latest,prior", [
    ("中间价:欧元兑人民币", "middle_rate", 0.0, 7.8),
    ("人民币指数", "fx_index", 0.0, 99.0),
    ("人民币Swap", "fx_swap_curve", -0.3, -0.2),
    ("人民币掉期", "fx_swap_curve", 0.0, 0.0),
])
def test_http_non_usd_paths_preserve_existing_zero_negative_semantics(http, name, group, latest, prior):
    _seed(http.path, [("synthetic-other", name, [
        _observation(DAY, latest, "other"),
        _observation(DAY - timedelta(days=1), prior, "other_prior"),
    ])])
    body = _read(http.client)
    point = _only_point(body)
    assert point["group_key"] == group
    assert point["value_numeric"] == latest
    assert point["trade_date"] == str(DAY)
    assert point["latest_change"] == pytest.approx(latest - prior)
    assert point["source_version"] == "sv_synthetic_other"
    assert point["quality_flag"] == "ok"
    assert _warnings(body) == []


def test_http_active_snapshot_filter_keeps_fallback_lineage(http):
    series = _fallback_series() + [("synthetic-inactive", "人民币指数", [_observation(DAY, 99, "inactive")])]
    _seed(http.path, series, active_series=["synthetic-usd"])
    body = _read(http.client)
    _assert_lineage(body, "G1", 7.2, DAY - timedelta(days=1))
    assert _only_point(body)["latest_change"] is None


def test_http_mixed_groups_aggregate_selected_lineage_without_suppressing_healthy_delta(http):
    _seed(http.path, _fallback_series() + [
        ("synthetic-swap", "人民币Swap", [
            _observation(DAY, -0.2, "swap"),
            _observation(DAY - timedelta(days=1), -0.1, "swap_prior"),
        ])
    ])
    body = _read(http.client)
    assert [group["group_key"] for group in body["result"]["groups"]] == ["middle_rate", "fx_swap_curve"]
    usd, swap = [group["series"][0] for group in body["result"]["groups"]]
    assert usd["latest_change"] is None
    assert swap["latest_change"] == pytest.approx(-0.1)
    assert swap["quality_flag"] == "ok"
    assert body["result_meta"]["source_version"] == "sv_synthetic_G1_selected__sv_synthetic_swap"
    assert body["result_meta"]["vendor_version"] == "vv_synthetic_G1_selected__vv_synthetic_swap"
    assert _warnings(body)
    assert all("series_id=synthetic-usd:" in warning for warning in _warnings(body))


@pytest.mark.parametrize("reverse", [False, True])
def test_http_same_date_valid_observation_is_not_confused_with_invalid_lineage(http, reverse):
    observations = [_observation(DAY, 0, "same_invalid"), _observation(DAY, 7.3, "same_valid")]
    if reverse:
        observations.reverse()
    _seed(http.path, [("synthetic-usd", USD_NAME, observations)])
    body = _read(http.client)
    point = _only_point(body)
    assert point["value_numeric"] == 7.3
    assert point["trade_date"] == str(DAY)
    assert point["source_version"] == body["result_meta"]["source_version"] == "sv_synthetic_same_valid"
    assert point["vendor_version"] == body["result_meta"]["vendor_version"] == "vv_synthetic_same_valid"
    if point["recent_points"][0]["value_numeric"] == 0:
        assert point["latest_change"] is None
        assert point["quality_flag"] == "warning"
        assert any("fallback" in warning.lower() for warning in _warnings(body))
    else:
        assert point["latest_change"] is None  # The immediate comparator is invalid, even on the same date.
        assert point["quality_flag"] == "warning"
        assert any("invalid previous observation" in warning for warning in _warnings(body))


@pytest.mark.parametrize("second_value", [7.2, 7.4])
def test_http_older_duplicate_date_lineage_follows_the_selector_ordered_input(http, second_value):
    _seed(http.path, [("synthetic-usd", USD_NAME, [
        _observation(DAY, 0, "duplicate_invalid"),
        _observation(DAY - timedelta(days=1), 7.2, "duplicate_a"),
        _observation(DAY - timedelta(days=1), second_value, "duplicate_b"),
    ])])
    body = _read(http.client)
    point = _only_point(body)
    # For older-date ties, the unchanged selector uses the last valid ordered input.
    selected = point["recent_points"][-1]
    for key in ("trade_date", "value_numeric", "source_version", "vendor_version"):
        assert point[key] == selected[key]
    assert body["result_meta"]["source_version"] == selected["source_version"]
    assert body["result_meta"]["vendor_version"] == selected["vendor_version"]
    assert point["latest_change"] is None


@pytest.mark.parametrize("state", ["no_file", "no_schema", "empty", "broken_schema", "corrupt_database"])
def test_http_empty_sources_and_domain_read_failure_contract(http, state):
    if state == "no_schema":
        with duckdb.connect(str(http.path)) as conn:
            conn.execute("CREATE TABLE unrelated(value INTEGER)")
    elif state == "empty":
        _seed(http.path, [])
    elif state == "broken_schema":
        with duckdb.connect(str(http.path)) as conn:
            conn.execute("CREATE TABLE fact_choice_macro_daily(wrong_column INTEGER)")
            conn.execute("CREATE TABLE phase1_macro_vendor_catalog(wrong_column INTEGER)")
    elif state == "corrupt_database":
        http.path.write_bytes(b"synthetic invalid DuckDB file")
    if state in {"broken_schema", "corrupt_database"}:
        response = http.client.get(ENDPOINT)
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "fx_analytical_read_failed"
        assert "DuckDB query failed surface=fx_analytical table=fact_choice_macro_daily" in response.json()["detail"]["message"]
    else:
        body = _read(http.client)
        assert body["result"]["groups"] == []
        assert body["result_meta"]["quality_flag"] == "warning"
        assert body["result_meta"]["vendor_version"] == "vv_none"
        assert body["result_meta"]["source_version"] == "sv_fx_analytical_empty"
        assert _warnings(body) == []
    if state == "no_file":
        assert not http.path.exists()


def test_http_no_grant_is_denied_before_loading_all_invalid_inputs(http):
    _seed(http.path, [("synthetic-usd", USD_NAME, [_observation(DAY, 0, "invalid")])])
    http.app.dependency_overrides[get_auth_context] = lambda: AuthContext(
        user_id="synthetic-no-grant", role="viewer", identity_source="synthetic-test")
    response = http.client.get(ENDPOINT)
    assert response.status_code == 403
    assert "not allowed" in response.json()["detail"]


def test_http_all_invalid_inputs_keep_explicit_selector_failure(http):
    _seed(http.path, [("synthetic-usd", USD_NAME, [_observation(DAY, 0, "invalid")])])
    response = http.client.get(ENDPOINT)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "fx_analytical_unavailable"
    assert "no valid input rows" in response.json()["detail"]["message"]


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")], ids=["nan", "inf", "negative_inf"])
def test_nonfinite_history_is_null_in_service_and_http(http, invalid):
    """Nonfinite stored values normalize to null without changing observation lineage."""
    _seed(http.path, [("synthetic-usd", USD_NAME, [
        _observation(DAY, invalid, "nonfinite"),
        _observation(DAY - timedelta(days=1), 7.2, "selected"),
    ])])
    point = load_fx_analytical_payload(str(http.path)).groups[0].series[0]
    assert point.value_numeric == 7.2
    assert point.recent_points[0].value_numeric is None
    response = http.client.get(ENDPOINT)
    assert response.status_code == 200, response.text
    body = response.json()
    http_point = _only_point(body)
    assert http_point["value_numeric"] == 7.2
    assert http_point["recent_points"][0]["value_numeric"] is None
    assert http_point["recent_points"][0]["source_version"] == "sv_synthetic_nonfinite"


def _published_fx(root, number, settings, pnl_digest):
    generation = f"system-read-2026-09-15-{str(number) * 20}"
    _seal_generation(root, generation, f"synthetic-FX-G{number}",
                     system_read_bundle=_bundle(settings, "pnl-synthetic", pnl_digest))
    database = root / "generations" / f"{generation}.duckdb"
    _seed(database, _fallback_series(f"G{number}", gap=number, value=6.0 + number))
    manifest_path = root / "generations" / f"{generation}.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["database"].update(size_bytes=database.stat().st_size, sha256=sha256_file(database))
    content = canonical_json_bytes(manifest)
    manifest_path.write_bytes(content)
    return generation, sha256_bytes(content)


def test_actual_publication_middleware_fx_lineage_g1_g2_g1_and_auth(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    _seed(Path(settings.duckdb_path), _fallback_series("ACTIVE", value=9.9))
    pnl_root = Path(settings.financial_publication_root)
    pnl_digest = _seal_generation(pnl_root, "pnl-synthetic", "SYNTHETIC")
    _write_pointer(pnl_root, "pnl-synthetic", [("pnl-synthetic", pnl_digest)])
    root = system_read_publication_root(settings)
    g1 = _published_fx(root, 1, settings, pnl_digest)
    g2 = _published_fx(root, 2, settings, pnl_digest)
    _write_pointer(root, g2[0], [g2, g1])
    app = _app(settings, monkeypatch, publication=True)
    with TestClient(app) as client:
        bodies = []
        for number, generation in ((1, g1[0]), (2, g2[0]), (1, g1[0])):
            response = client.get(ENDPOINT, headers={SYSTEM_READ_GENERATION_HEADER: generation})
            assert response.status_code == 200, response.text
            assert response.headers[SYSTEM_READ_GENERATION_HEADER] == generation
            body = response.json()
            assert body["result_meta"]["basis"] == "analytical"
            assert body["result_meta"]["formal_use_allowed"] is False
            _assert_lineage(body, f"G{number}", 6.0 + number, DAY - timedelta(days=number))
            assert _only_point(body)["latest_change"] is None
            assert _only_point(body)["recent_points"][0]["source_version"] == f"sv_synthetic_G{number}_invalid"
            assert f"observed_date={DAY - timedelta(days=number)}" in " ".join(_warnings(body))
            bodies.append(body)
        assert bodies[0]["result"] == bodies[2]["result"]
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            user_id="synthetic-no-grant", role="viewer", identity_source="synthetic-test")
        denied = client.get(ENDPOINT, headers={SYSTEM_READ_GENERATION_HEADER: g1[0]})
        assert denied.status_code == 403
        app.dependency_overrides[get_auth_context] = lambda: AuthContext(
            user_id="synthetic-reader", role="viewer", identity_source="synthetic-test")
        unavailable = client.get(ENDPOINT, headers={SYSTEM_READ_GENERATION_HEADER: "system-read-unknown"})
        assert unavailable.status_code == 503
        assert SYSTEM_READ_GENERATION_HEADER not in unavailable.headers
