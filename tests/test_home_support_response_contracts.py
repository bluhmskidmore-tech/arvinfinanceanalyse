"""Homepage supplemental read contracts, using synthetic service inputs only."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.exceptions import ResponseValidationError
from fastapi.testclient import TestClient

from backend.app.api.routes import choice_news, macro_vendor, research_calendar
from backend.app.schemas.macro_vendor import (
    ChoiceMacroLatestPayload,
    ChoiceMacroLatestPoint,
)
from backend.app.schemas.research_calendar import ResearchCalendarEvent
from backend.app.security.auth_context import get_auth_context
from backend.app.services import (
    choice_news_service,
    macro_vendor_service,
    research_calendar_service,
)


def _support_client(monkeypatch, route_module, payload, tmp_path):
    app = FastAPI()
    app.include_router(route_module.router)
    app.dependency_overrides[get_auth_context] = lambda: object()
    monkeypatch.setattr(
        route_module,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path=tmp_path / "absent.duckdb"),
    )
    if route_module is macro_vendor:
        monkeypatch.setattr(
            route_module, "_ensure_macro_vendor_read_allowed", lambda _auth: None
        )
        monkeypatch.setattr(
            route_module.market_home_response_cache,
            "get_or_build",
            lambda _key, builder: builder(),
        )
        monkeypatch.setattr(
            route_module, "choice_macro_formal_envelope", lambda _path: payload
        )
    elif route_module is research_calendar:
        monkeypatch.setattr(
            route_module, "_ensure_research_calendar_read_allowed", lambda _auth: None
        )
        monkeypatch.setattr(
            route_module,
            "supply_auction_calendar_envelope",
            lambda *_args, **_kwargs: payload,
        )
    else:
        monkeypatch.setattr(route_module, "ensure_user_allowed", lambda **_kwargs: None)
        monkeypatch.setattr(
            route_module, "choice_news_latest_batch_envelope", lambda **_kwargs: payload
        )
    return TestClient(app)


def _response_schema(document, path):
    schema = document["paths"][path]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    while "$ref" in schema:
        schema = document["components"]["schemas"][schema["$ref"].rsplit("/", 1)[1]]
    return schema


def _nested_schema(document, schema, key, *, array=False):
    nested = schema["properties"][key]
    if array:
        nested = nested["items"]
    while "$ref" in nested:
        nested = document["components"]["schemas"][nested["$ref"].rsplit("/", 1)[1]]
    return nested


def _rates_payload(monkeypatch, branch):
    points = (
        []
        if branch == "empty"
        else [
            ChoiceMacroLatestPoint(
                series_id="synthetic_rate",
                series_name="Synthetic rate",
                display_name="Rate",
                trade_date="2026-09-29",
                value_numeric=1.5,
                frequency="daily",
                unit="%",
                source_version="sv_synthetic",
                vendor_version="vv_synthetic",
                vendor_name="synthetic",
                refresh_tier="stable",
                fetch_mode="date_slice",
                fetch_granularity="batch",
                policy_note=None,
                quality_flag="stale" if branch == "degraded" else "ok",
                latest_change=None,
                recent_points=[
                    {
                        "trade_date": "2026-09-29",
                        "value_numeric": 1.5,
                        "source_version": "sv_synthetic",
                        "vendor_version": "vv_synthetic",
                        "quality_flag": "ok",
                    }
                ],
            )
        ]
    )
    monkeypatch.setattr(
        macro_vendor_service,
        "_load_choice_macro_latest_payload_with_warnings",
        lambda *_args, **_kwargs: (
            ChoiceMacroLatestPayload(
                series=points, derived_spreads={"synthetic_bp": None}
            ),
            ["synthetic query warning"] if branch == "degraded" else [],
        ),
    )
    monkeypatch.setattr(
        macro_vendor_service,
        "_load_formal_yield_curve_points",
        lambda _path: ([], None, []),
    )
    return macro_vendor_service.choice_macro_formal_envelope(
        "synthetic-do-not-open.duckdb"
    )


def _calendar_payload(monkeypatch, tmp_path, branch):
    path = tmp_path / "calendar.synthetic"
    if branch != "empty":
        path.touch()
        event = ResearchCalendarEvent(
            event_id="synthetic_event",
            series_id="synthetic_supply",
            event_date=date(2026, 9, 30),
            event_kind="auction",
            title="Synthetic auction",
            source_family="synthetic",
            severity="low",
            issuer="Synthetic issuer",
            market="interbank",
            instrument_type="bond",
            term_label="1Y",
            amount=None,
            amount_unit="亿元",
            currency="CNY",
            status="unknown" if branch == "degraded" else "scheduled",
            headline_text=None,
            headline_url=None,
            headline_published_at=None,
        )
        page = SimpleNamespace(
            events=[event],
            total_rows=1,
            limit=50,
            offset=0,
            table_name="synthetic_calendar",
            source_version="sv_synthetic",
            vendor_version="vv_synthetic",
            rule_version="rv_synthetic",
        )
        monkeypatch.setattr(
            research_calendar_service,
            "ResearchCalendarRepository",
            lambda **_kwargs: SimpleNamespace(
                fetch_supply_auction_page=lambda **_query: page
            ),
        )
    return research_calendar_service.supply_auction_calendar_envelope(str(path))


def _news_payload(monkeypatch, branch):
    # Raw row shape follows the existing repository/service mapper, not live news.
    rows = (
        []
        if branch == "empty"
        else [
            (
                "synthetic_event",
                "2026-09-29T23:59:59+08:00",
                "synthetic_group",
                "sectornews",
                1,
                2,
                0,
                "",
                "SYNTHETIC_TOPIC",
                0,
                None,
                '{"headline":"Synthetic headline"}',
                "Synthetic headline",
                None,
            )
        ]
    )
    raw = SimpleNamespace(
        events_per_request=[rows, []],
        source_unavailable=branch == "degraded",
        excluded_future_rows=1 if branch == "degraded" else 0,
    )
    monkeypatch.setattr(
        choice_news_service,
        "ChoiceNewsRepository",
        lambda **_kwargs: SimpleNamespace(fetch_latest_batch=lambda **_query: raw),
    )
    return choice_news_service.choice_news_latest_batch_envelope(
        "synthetic-do-not-open.duckdb",
        topic_requests=[("SYNTHETIC_TOPIC", 2)],
        group_requests=[("synthetic_group", 2)],
    )


class TestMarketRatesResponseContract:
    pytestmark = [
        pytest.mark.excluded_surface_regression,
        pytest.mark.surface_market_data,
    ]
    path = "/ui/market-data/rates"

    def test_openapi_exposes_series_and_recent_point_fields(
        self, monkeypatch, tmp_path
    ):
        client = _support_client(
            monkeypatch, macro_vendor, _rates_payload(monkeypatch, "normal"), tmp_path
        )
        document = client.app.openapi()
        envelope = _response_schema(document, self.path)
        assert {"result_meta", "result"} <= set(envelope.get("required", []))
        result = _nested_schema(document, envelope, "result")
        point = _nested_schema(document, result, "series", array=True)
        assert {
            "trade_date",
            "value_numeric",
            "unit",
            "source_version",
            "recent_points",
            "latest_change",
            "refresh_tier",
        } <= point["properties"].keys()
        recent = _nested_schema(document, point, "recent_points", array=True)
        assert {
            "trade_date",
            "value_numeric",
            "source_version",
            "vendor_version",
            "quality_flag",
        } <= recent["properties"].keys()

    def test_route_rejects_missing_series(self, monkeypatch, tmp_path):
        payload = _rates_payload(monkeypatch, "normal")
        del payload["result"]["series"]
        client = _support_client(monkeypatch, macro_vendor, payload, tmp_path)
        with pytest.raises(ResponseValidationError):
            client.get(self.path)

    def test_route_rejects_wrong_nested_value_type(self, monkeypatch, tmp_path):
        payload = _rates_payload(monkeypatch, "normal")
        payload["result"]["series"][0]["value_numeric"] = {"raw": 1.5}
        client = _support_client(monkeypatch, macro_vendor, payload, tmp_path)
        with pytest.raises(ResponseValidationError):
            client.get(self.path)

    def test_unknown_metadata_is_rejected_instead_of_silently_dropped(
        self, monkeypatch, tmp_path
    ):
        payload = _rates_payload(monkeypatch, "normal")
        payload["result_meta"]["undeclared_disclosure"] = "synthetic"
        client = _support_client(monkeypatch, macro_vendor, payload, tmp_path)
        with pytest.raises(ResponseValidationError):
            client.get(self.path)

    def test_absent_optional_fields_are_not_added(self, monkeypatch, tmp_path):
        payload = _rates_payload(monkeypatch, "normal")
        del payload["result"]["derived_spreads"]
        for key in ("display_name", "latest_change", "policy_note", "recent_points"):
            del payload["result"]["series"][0][key]
        client = _support_client(monkeypatch, macro_vendor, payload, tmp_path)
        assert client.get(self.path).json() == payload

    @pytest.mark.parametrize("branch", ["normal", "empty", "degraded"])
    def test_actual_service_branches_round_trip_without_field_loss(
        self, monkeypatch, tmp_path, branch
    ):
        payload = _rates_payload(monkeypatch, branch)
        expected = deepcopy(payload)
        client = _support_client(monkeypatch, macro_vendor, payload, tmp_path)
        response = client.get(self.path)
        assert response.status_code == 200
        assert response.json() == expected
        assert response.json()["result_meta"]["basis"] == "formal"
        assert response.json()["result"]["derived_spreads"]["synthetic_bp"] is None


class TestSupplyCalendarResponseContract:
    pytestmark = [
        pytest.mark.excluded_surface_regression,
        pytest.mark.surface_macro_data,
    ]
    path = "/ui/calendar/supply-auctions"

    def test_openapi_exposes_event_fields_and_units(self, monkeypatch, tmp_path):
        client = _support_client(
            monkeypatch,
            research_calendar,
            _calendar_payload(monkeypatch, tmp_path, "normal"),
            tmp_path,
        )
        document = client.app.openapi()
        result = _nested_schema(
            document, _response_schema(document, self.path), "result"
        )
        event = _nested_schema(document, result, "events", array=True)
        assert {
            "event_date",
            "amount",
            "amount_unit",
            "currency",
            "status",
            "headline_text",
            "headline_url",
            "headline_published_at",
        } <= event["properties"].keys()

    def test_route_rejects_missing_events(self, monkeypatch, tmp_path):
        payload = _calendar_payload(monkeypatch, tmp_path, "empty")
        del payload["result"]["events"]
        client = _support_client(monkeypatch, research_calendar, payload, tmp_path)
        with pytest.raises(ResponseValidationError):
            client.get(self.path)

    def test_route_rejects_wrong_nested_amount_type(self, monkeypatch, tmp_path):
        payload = _calendar_payload(monkeypatch, tmp_path, "normal")
        payload["result"]["events"][0]["amount"] = {"raw": 1.5}
        client = _support_client(monkeypatch, research_calendar, payload, tmp_path)
        with pytest.raises(ResponseValidationError):
            client.get(self.path)

    def test_absent_optional_fields_are_not_added(self, monkeypatch, tmp_path):
        payload = _calendar_payload(monkeypatch, tmp_path, "normal")
        for key in (
            "amount",
            "status",
            "headline_text",
            "headline_url",
            "headline_published_at",
        ):
            del payload["result"]["events"][0][key]
        client = _support_client(monkeypatch, research_calendar, payload, tmp_path)
        assert client.get(self.path).json() == payload

    @pytest.mark.parametrize("branch", ["normal", "empty", "degraded"])
    def test_actual_service_branches_round_trip_without_field_loss(
        self, monkeypatch, tmp_path, branch
    ):
        payload = _calendar_payload(monkeypatch, tmp_path, branch)
        expected = deepcopy(payload)
        client = _support_client(monkeypatch, research_calendar, payload, tmp_path)
        response = client.get(self.path)
        assert response.status_code == 200
        assert response.json() == expected
        assert response.json()["result_meta"]["basis"] == "analytical"
        assert response.json()["result_meta"]["formal_use_allowed"] is False
        if branch != "empty":
            assert response.json()["result"]["events"][0]["amount"] is None
            assert response.json()["result"]["events"][0]["amount_unit"] == "亿元"


class TestChoiceNewsBatchResponseContract:
    pytestmark = [
        pytest.mark.excluded_surface_acceptance,
        pytest.mark.surface_choice_news,
    ]
    path = "/ui/news/choice-events/latest-batch"
    params = {"topics": "SYNTHETIC_TOPIC:2", "groups": "synthetic_group:2"}

    def test_openapi_exposes_batch_event_fields(self, monkeypatch, tmp_path):
        client = _support_client(
            monkeypatch, choice_news, _news_payload(monkeypatch, "normal"), tmp_path
        )
        document = client.app.openapi()
        result = _nested_schema(
            document, _response_schema(document, self.path), "result"
        )
        batch = _nested_schema(document, result, "batches", array=True)
        assert {"key", "topic_code", "group_id", "events"} <= set(
            batch.get("required", [])
        )
        event = _nested_schema(document, batch, "events", array=True)
        assert {
            "event_key",
            "received_at",
            "payload_text",
            "payload_json",
            "display_text",
            "error_code",
        } <= event["properties"].keys()

    @pytest.mark.parametrize("missing_field", ["batches", "group_id", "display_text"])
    def test_route_rejects_missing_fields_including_required_nullable(
        self, monkeypatch, tmp_path, missing_field
    ):
        payload = _news_payload(monkeypatch, "normal")
        if missing_field == "batches":
            del payload["result"]["batches"]
        elif missing_field == "group_id":
            del payload["result"]["batches"][0]["group_id"]
        else:
            del payload["result"]["batches"][0]["events"][0]["display_text"]
        client = _support_client(monkeypatch, choice_news, payload, tmp_path)
        with pytest.raises(ResponseValidationError):
            client.get(self.path, params=self.params)

    def test_route_rejects_wrong_nested_payload_type(self, monkeypatch, tmp_path):
        payload = _news_payload(monkeypatch, "normal")
        payload["result"]["batches"][0]["events"][0]["payload_json"] = {
            "headline": "Synthetic"
        }
        client = _support_client(monkeypatch, choice_news, payload, tmp_path)
        with pytest.raises(ResponseValidationError):
            client.get(self.path, params=self.params)

    def test_null_event_text_and_payload_are_preserved(self, monkeypatch, tmp_path):
        payload = _news_payload(monkeypatch, "normal")
        event = payload["result"]["batches"][0]["events"][0]
        event.update(payload_text=None, payload_json=None, display_text=None)
        client = _support_client(monkeypatch, choice_news, payload, tmp_path)
        assert client.get(self.path, params=self.params).json() == payload

    @pytest.mark.parametrize("branch", ["normal", "empty", "degraded"])
    def test_actual_service_branches_round_trip_without_field_loss(
        self, monkeypatch, tmp_path, branch
    ):
        payload = _news_payload(monkeypatch, branch)
        expected = deepcopy(payload)
        client = _support_client(monkeypatch, choice_news, payload, tmp_path)
        response = client.get(self.path, params=self.params)
        assert response.status_code == 200
        assert response.json() == expected
        meta = response.json()["result_meta"]
        assert meta["basis"] == "analytical"
        assert meta["formal_use_allowed"] is False
        assert meta["date_basis"] == "received_at_as_of_filter"
        if branch == "degraded":
            assert meta["vendor_status"] == "vendor_unavailable"
            assert meta["filters_applied"]["future_rows_excluded"] == 1
