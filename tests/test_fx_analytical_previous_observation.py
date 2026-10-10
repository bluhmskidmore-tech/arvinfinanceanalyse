"""IR-05: immediate USD/CNY comparator validity through real DuckDB and HTTP.

Storage uses the registered macro schema. The actual route, read authorization,
service, quote selector and JSON response execute; only settings and inbound
identity are supplied by the existing synthetic API fixture.
"""
from __future__ import annotations

import json
import math
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app.core_finance.fx_rates import FxRateUnavailableError
from backend.app.repositories.duckdb_read_context import DuckDBReadSelection, duckdb_read_scope
from backend.app.services import macro_vendor_service as service
from tests.test_fx_analytical_fallback_api import DAY, ENDPOINT, USD_NAME, _app, _observation, _seed

pytestmark = [pytest.mark.excluded_surface_regression, pytest.mark.surface_market_data]

INVALID_QUOTES = [0.0, -1.0, float("nan"), float("inf"), float("-inf")]
INVALID_IDS = ["zero", "negative", "nan", "positive_infinity", "negative_infinity"]


@pytest.fixture
def http(tmp_path, monkeypatch):
    settings = SimpleNamespace(duckdb_path=str(tmp_path / "synthetic.duckdb"))
    with TestClient(_app(settings, monkeypatch)) as client:
        yield SimpleNamespace(path=Path(settings.duckdb_path), client=client)


def _observations(values):
    return [_observation(DAY - timedelta(days=index), value, f"observation_{index}")
            for index, value in enumerate(values)]


def _seed_values(path, values):
    observations = _observations(values)
    _seed(path, [("synthetic-usd", USD_NAME, observations)])
    return observations


def _point(body):
    return body["result"]["groups"][0]["series"][0]


def _warnings(body):
    return body["result_meta"]["filters_applied"].get("warnings", [])


def _assert_selected(body, observation):
    point = _point(body)
    day, value, source, vendor, _quality = observation
    assert (point["trade_date"], point["value_numeric"], point["source_version"], point["vendor_version"]) == (
        day, value, source, vendor)
    assert (point["frequency"], point["unit"]) == ("daily", "synthetic-unit")
    assert point["refresh_tier"] == "stable"
    assert point["policy_note"] == "Synthetic policy is retained"
    meta = body["result_meta"]
    assert (meta["source_version"], meta["vendor_version"]) == (source, vendor)
    assert meta["basis"] == "analytical" and meta["formal_use_allowed"] is False
    assert meta["fallback_mode"] == "none"


@pytest.mark.parametrize("invalid", INVALID_QUOTES, ids=INVALID_IDS)
def test_invalid_immediate_previous_quote_never_manufactures_delta(tmp_path, invalid):
    path = tmp_path / "synthetic.duckdb"
    observations = _seed_values(path, [7.2, invalid, 7.1])
    body = service.fx_analytical_envelope(str(path))
    assert _point(body)["latest_change"] is None
    _assert_selected(body, observations[0])
    assert _point(body)["quality_flag"] == body["result_meta"]["quality_flag"] == "warning"
    assert any("latest_change" in warning and "invalid previous" in warning
               and observations[1][0] in warning for warning in _warnings(body))
    previous = _point(body)["recent_points"][1]
    assert previous["trade_date"] == observations[1][0]
    assert previous["source_version"] == observations[1][2]
    assert previous["vendor_version"] == observations[1][3]
    assert previous["quality_flag"] == "ok"  # Raw source history is not rewritten.
    if math.isfinite(invalid):
        assert previous["value_numeric"] == invalid
    else:
        assert previous["value_numeric"] is None
    # In particular, the older valid 7.1 quote never becomes a substitute comparator.
    payload = service.load_fx_analytical_payload(str(path))
    assert payload.groups[0].series[0].latest_change is None


@pytest.mark.parametrize("invalid", INVALID_QUOTES, ids=INVALID_IDS)
def test_route_serializes_invalid_previous_observation(http, invalid):
    observations = _seed_values(http.path, [7.2, invalid, 7.1])
    response = http.client.get(ENDPOINT)
    assert response.status_code == 200
    body = response.json()
    json.dumps(body, allow_nan=False)
    _assert_selected(body, observations[0])
    assert _point(body)["latest_change"] is None
    assert _point(body)["quality_flag"] == body["result_meta"]["quality_flag"] == "warning"
    # Current FastAPI already serializes nonfinite history to null. Preserve that
    # wire contract and its exact observation metadata; do not drop or reorder it.
    assert _point(body)["recent_points"] == [
        {"trade_date": day, "value_numeric": value if math.isfinite(value) else None,
         "source_version": source, "vendor_version": vendor, "quality_flag": quality}
        for day, value, source, vendor, quality in observations]


@pytest.mark.parametrize("values,delta", [([7.2, 7.1], 0.1), ([7.2, 7.2], 0.0), ([7.1, 7.2], -0.1)])
def test_valid_immediate_comparator_retains_arithmetic_and_history(http, values, delta):
    observations = _seed_values(http.path, values)
    response = http.client.get(ENDPOINT)
    assert response.status_code == 200
    body = response.json()
    _assert_selected(body, observations[0])
    point = _point(body)
    assert point["latest_change"] == pytest.approx(delta)
    assert point["quality_flag"] == body["result_meta"]["quality_flag"] == "ok"
    assert _warnings(body) == []
    assert point["recent_points"] == [
        {"trade_date": day, "value_numeric": value, "source_version": source,
         "vendor_version": vendor, "quality_flag": quality}
        for day, value, source, vendor, quality in observations]


@pytest.mark.parametrize("invalid", INVALID_QUOTES, ids=INVALID_IDS)
def test_invalid_latest_retains_exact_fallback_observation(http, invalid):
    observations = _seed_values(http.path, [invalid, 7.2, 7.1])
    response = http.client.get(ENDPOINT)
    assert response.status_code == 200
    body = response.json()
    json.dumps(body, allow_nan=False)
    _assert_selected(body, observations[1])
    assert _point(body)["latest_change"] is None
    assert _point(body)["quality_flag"] == "warning"
    assert any("latest_change" in warning and "fallback" in warning for warning in _warnings(body))


@pytest.mark.parametrize("invalid", INVALID_QUOTES, ids=INVALID_IDS)
def test_all_invalid_quotes_retain_explicit_selector_failure(http, invalid):
    _seed_values(http.path, [invalid, invalid])
    with pytest.raises(FxRateUnavailableError, match="analytical fallback unavailable.*no valid input rows"):
        service.fx_analytical_envelope(str(http.path))
    response = http.client.get(ENDPOINT)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "fx_analytical_unavailable"
    assert "no valid input rows" in response.json()["detail"]["message"]


@pytest.mark.parametrize("state", ["absent", "empty", "single_valid"])
def test_no_comparator_and_no_data_keep_existing_contract(http, state):
    if state != "absent":
        _seed_values(http.path, [7.2] if state == "single_valid" else [])
    response = http.client.get(ENDPOINT)
    assert response.status_code == 200
    body = response.json()
    assert _warnings(body) == []
    if state == "single_valid":
        assert _point(body)["latest_change"] is None
        assert _point(body)["quality_flag"] == "ok"
    else:
        assert body["result"]["groups"] == []
        assert body["result_meta"]["source_version"] == "sv_fx_analytical_empty"
    assert http.path.exists() is (state != "absent")


def test_selected_snapshot_keeps_latest_lineage_without_active_database(tmp_path):
    active = tmp_path / "absent-active.duckdb"
    selected = tmp_path / "selected.duckdb"
    observations = _seed_values(selected, [7.2, 0.0, 7.1])
    with duckdb_read_scope(DuckDBReadSelection(active, selected, "synthetic-generation"), required_online=True):
        body = service.fx_analytical_envelope(str(active))
    _assert_selected(body, observations[0])
    assert _point(body)["latest_change"] is None
    assert not active.exists()


@pytest.mark.parametrize("quality", ["warning", "stale", "error"])
def test_invalid_comparator_does_not_downgrade_latest_source_quality(http, quality):
    observations = _observations([7.2, 0.0, 7.1])
    observations[0] = (*observations[0][:4], quality)
    _seed(http.path, [("synthetic-usd", USD_NAME, observations)])
    response = http.client.get(ENDPOINT)
    assert response.status_code == 200
    body = response.json()
    point = _point(body)
    assert point["latest_change"] is None
    assert point["quality_flag"] == body["result_meta"]["quality_flag"] == quality


@pytest.mark.parametrize("quality", ["stale", "error"])
@pytest.mark.parametrize("usd_values", [[7.2, 0.0, 7.1], [0.0, 7.2, 7.1]], ids=["invalid_comparator", "fallback"])
def test_warning_does_not_hide_worse_quality_in_other_fx_series(http, quality, usd_values):
    usd = _observations(usd_values)
    swap = [
        _observation(DAY, -0.2, "swap_latest", quality),
        _observation(DAY - timedelta(days=1), -0.1, "swap_previous"),
    ]
    _seed(http.path, [("synthetic-usd", USD_NAME, usd), ("synthetic-swap", "人民币Swap", swap)])
    response = http.client.get(ENDPOINT)
    assert response.status_code == 200
    body = response.json()
    usd_point, swap_point = [group["series"][0] for group in body["result"]["groups"]]
    assert usd_point["quality_flag"] == "warning" and usd_point["latest_change"] is None
    assert swap_point["quality_flag"] == body["result_meta"]["quality_flag"] == quality
    assert swap_point["latest_change"] == pytest.approx(-0.1)
    assert _warnings(body)
