from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
from fastapi import HTTPException
from starlette.responses import JSONResponse

from backend.app.api.routes import market_overview as market_overview_route
from backend.app.schemas.market_overview import MarketOverviewSnapshotEnvelope
from backend.app.services import market_overview_service as snapshot_service
from backend.app.services.macro_toolkit_refresh_receipt_service import (
    CORE_LATEST_OBSERVATION_KEYS,
    MacroToolkitRefreshReceiptHealth,
    load_macro_toolkit_refresh_receipt_health,
)

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_market_data,
]


def _write_ready_receipt(path: Path) -> None:
    steps = [
        {"step": name, "status": "success", "result": {"row_count": 1}}
        for name in (
            "choice_policy_rate_7d",
            "choice_crisis_aa_5y",
            "commodity_daily_ingest",
            "public_cross_asset_headlines",
            "tushare_ncd_shibor",
            "cffex_member_rank",
        )
    ]
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": "2026-08-27T08:00:00+00:00",
                "run_kind": "scheduled",
                "invocation_mode": "run_once",
                "task_name": "refresh_macro_toolkit_freshness",
                "source_version": "macro_toolkit_freshness_refresh_v4",
                "status": "success",
                "exit_code": 0,
                "warnings": [],
                "result": {
                    "status": "success",
                    "steps": steps,
                    "latest_observation_dates": {
                        key: "2026-08-27" for key in CORE_LATEST_OBSERVATION_KEYS
                    },
                },
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture
def ready_health(tmp_path: Path) -> MacroToolkitRefreshReceiptHealth:
    # Keep the API test boundary isolated from the live DuckDB and receipt.
    duckdb.connect(str(tmp_path / "moss.duckdb"), read_only=False).close()
    receipt_path = tmp_path / "macro_toolkit_freshness_refresh_receipt.json"
    _write_ready_receipt(receipt_path)
    return load_macro_toolkit_refresh_receipt_health(
        receipt_path,
        now=datetime(2026, 8, 27, 9, 0, tzinfo=UTC),
    )


def _point(
    series_id: str,
    *,
    trade_date: str = "2026-08-28",
    value: float = 1.0,
    unit: str = "index",
    latest_change: float | None = 0.0,
    name: str | None = None,
    quality_flag: str = "ok",
) -> dict[str, object]:
    return {
        "series_id": series_id,
        "series_name": name or series_id,
        "display_name": name or series_id,
        "trade_date": trade_date,
        "value_numeric": value,
        "frequency": "D",
        "unit": unit,
        "source_version": f"sv_{series_id}",
        "vendor_version": f"vv_{series_id}",
        "vendor_name": "test-vendor",
        "quality_flag": quality_flag,
        "latest_change": latest_change,
        "recent_points": [],
    }


def _envelope(
    result: dict[str, object],
    *,
    quality: str = "ok",
    basis: str = "analytical",
    source_version: str = "sv_test",
    vendor_version: str = "vv_test",
    tables: list[str] | None = None,
) -> dict[str, object]:
    return {
        "result": result,
        "result_meta": {
            "quality_flag": quality,
            "vendor_status": "ok",
            "basis": basis,
            "source_version": source_version,
            "vendor_version": vendor_version,
            "tables_used": tables or [],
            "evidence_rows": 1,
        },
    }


def _base_components(
    *,
    choice_date: str = "2026-08-28",
    rate_change: float = 0.01,
    macro_quality: str = "ok",
    include_pulse_indicators: bool = True,
    crisis_regime: str = "正常",
    crisis_gate_eligible: bool = True,
    crisis_gate_triggered: bool = False,
    crisis_gate_reason_code: str = "crisis_score_below_threshold",
) -> dict[str, dict[str, object]]:
    choice = _envelope(
        {
            "read_target": "duckdb",
            "series": [
                _point(
                    "CA.CSI300",
                    trade_date=choice_date,
                    value=3500.0,
                    name="CSI 300 close",
                ),
                _point(
                    "CA.CSI300_PCT_CHG",
                    trade_date=choice_date,
                    value=0.35,
                    unit="%",
                    name="CSI 300 pct chg",
                ),
                _point(
                    "CA.BRENT",
                    trade_date="2026-08-25",
                    value=80.0,
                    unit="USD/bbl",
                    name="Brent spot",
                ),
                _point("EMM00058124", value=7.1, unit="CNY/USD", name="USD/CNY"),
                _point("CA.COPPER", value=70000.0, unit="CNY/t", name="Copper"),
            ]
        },
        source_version="sv_choice_a__sv_choice_b",
        vendor_version="vv_choice_a__vv_choice_b",
        tables=["fact_choice_macro_daily"],
    )
    rates = _envelope(
        {
            "read_target": "duckdb",
            "series": [
                _point("EMM00166466", value=2.0, unit="%", latest_change=rate_change),
                _point("E1000180", value=2.1, unit="%", latest_change=rate_change),
                _point("CA.DR007", value=1.7, unit="%", latest_change=rate_change),
                _point("EMM00088132", value=1.5, unit="%", latest_change=rate_change),
                _point("NCD.SHIBOR.3M", value=1.8, unit="%", latest_change=rate_change),
            ]
        },
        basis="formal",
        source_version="sv_rates_a__sv_rates_b",
        vendor_version="vv_rates_a__vv_rates_b",
        tables=["fact_formal_yield_curve_daily"],
    )
    indicators = (
        [
            {
                "key": key,
                "label": key,
                "previous_value": 99.0,
                "latest_value": 100.0,
                "change": 1.0,
                "latest_date": "2026-08-28",
                "source": "test-macro",
                "quality": "ok",
                "unit": "index" if key == "pmi" else "%",
            }
            for key in ("cpi", "ppi", "pmi", "social_financing")
        ]
        if include_pulse_indicators
        else []
    )
    macro = _envelope(
        {
            "as_of_date": "2026-08-28",
            "conclusion": {
                "stance": "neutral",
                "tone": "missing",
                "summary": "test conclusion",
                "recommended_action": "test action",
            },
            "indicators": indicators,
            "capability_results": [
                {
                    "key": "crisis_score_cn",
                    "status": "complete",
                    "score": 0.3,
                    "result": {
                        "report_date": "2026-08-28",
                        "requested_report_date": "2026-08-28",
                        "rule_version": "rv_macro_crisis_score_cn_v1",
                        "data_status": "complete",
                        "crisis_score": 0.3,
                        "regime": crisis_regime,
                        "percentile": 50.0,
                        "available_component_count": 5,
                        "component_count": 5,
                        "warnings": [],
                        "risk_gate": {
                            "eligible": crisis_gate_eligible,
                            "triggered": crisis_gate_triggered,
                            "threshold": 2.0,
                            "reason_code": crisis_gate_reason_code,
                        },
                        "score_trend": {
                            "requested_window_points": 20,
                            "window_points": 2,
                            "start_date": "2026-08-20",
                            "end_date": "2026-08-28",
                            "start_score": 0.1,
                            "end_score": 0.3,
                            "score_change": 0.2,
                            "start_percentile": 40.0,
                            "end_percentile": 50.0,
                            "percentile_change": 10.0,
                            "direction": "rising",
                        },
                        "score_trends": [
                            {
                                "requested_window_points": 20,
                                "window_points": 2,
                                "start_date": "2026-08-20",
                                "end_date": "2026-08-28",
                                "start_score": 0.1,
                                "end_score": 0.3,
                                "score_change": 0.2,
                                "start_percentile": 40.0,
                                "end_percentile": 50.0,
                                "percentile_change": 10.0,
                                "direction": "rising",
                            },
                            {
                                "requested_window_points": 60,
                                "window_points": 3,
                                "start_date": "2026-08-01",
                                "end_date": "2026-08-28",
                                "start_score": -0.5,
                                "end_score": 0.3,
                                "score_change": 0.8,
                                "start_percentile": 10.0,
                                "end_percentile": 50.0,
                                "percentile_change": 40.0,
                                "direction": "rising",
                            },
                        ],
                        "score_history": [
                            {
                                "date": "2026-08-01",
                                "crisis_score": -0.5,
                                "percentile": 10.0,
                                "available_component_count": 5,
                                "component_count": 5,
                                "available_weight": 1.0,
                                "data_status": "complete",
                            },
                            {
                                "date": "2026-08-20",
                                "crisis_score": 0.1,
                                "percentile": 40.0,
                                "available_component_count": 5,
                                "component_count": 5,
                                "available_weight": 1.0,
                                "data_status": "complete",
                            },
                            {
                                "date": "2026-08-28",
                                "crisis_score": 0.3,
                                "percentile": 50.0,
                                "available_component_count": 5,
                                "component_count": 5,
                                "available_weight": 1.0,
                                "data_status": "complete",
                            },
                        ],
                        "input_evidence": {
                            "inputs": [
                                {
                                    "field": "aa_5y",
                                    "label": "AA 5Y",
                                    "aliases": ["EMM00166683"],
                                    "warning": "AA 5Y unavailable",
                                    "required": True,
                                    "available": True,
                                    "row_count": 60,
                                    "latest_date": "2026-08-28",
                                    "series_id": "EMM00166683",
                                    "source": "Choice",
                                    "stale": False,
                                    "stale_days": 0,
                                    "value": 2.25,
                                }
                            ],
                            "missing_inputs": [],
                            "stale_inputs": [],
                            "sources": ["Choice"],
                            "latest_dates": ["2026-08-28"],
                        },
                    },
                }
            ],
            "signal_cards": [
                {"key": "liquidity", "tone": "neutral"},
                {"key": "outputs", "tone": "positive"},
            ],
        },
        quality=macro_quality,
        source_version="sv_macro_a__sv_macro_b",
        vendor_version="vv_macro_a__vv_macro_b",
        tables=["macro_indicator_daily"],
    )
    strategy = _envelope(
        {"as_of_date": "2026-08-24", "summaries": []},
        source_version="sv_strategy",
        vendor_version="vv_strategy",
    )
    news = _envelope(
        {
            "total_rows": 2,
            "excluded_future_rows": 0,
            "events": [
                {
                    "event_key": "event-clock",
                    "received_at": "2026-08-27T12:29:46+00:00",
                    "group_id": "tushare_news",
                    "topic_code": "rates",
                    "display_text": "clock event",
                },
                {
                    "event_key": "event-date",
                    "received_at": "2026-08-27T00:00:00+08:00",
                    "group_id": "tushare_research",
                    "topic_code": "macro",
                    "display_text": "date-only event",
                },
            ],
            "compare": {
                "same_direction": [],
                "conflicting": [],
                "review_needed": [{"event_key": "event-clock"}],
                "candidate_scenarios": [{"scenario_id": "s1"}],
            },
        },
        source_version="sv_news",
        vendor_version="vv_news",
        tables=["choice_news_event"],
    )
    return {
        "choice_latest": choice,
        "market_rates": rates,
        "macro_analysis_core": deepcopy(macro),
        "macro_analysis_full": macro,
        "macro_pulse": _envelope({"indicators": deepcopy(indicators)}),
        "macro_strategy_summaries": strategy,
        "choice_news": news,
    }


def _crisis_capability(
    components: dict[str, dict[str, object]],
) -> dict[str, object]:
    macro_result = components["macro_analysis_full"]["result"]
    assert isinstance(macro_result, dict)
    capabilities = macro_result["capability_results"]
    assert isinstance(capabilities, list)
    capability = capabilities[0]
    assert isinstance(capability, dict)
    return capability


def _crisis_result(
    components: dict[str, dict[str, object]],
) -> dict[str, object]:
    result = _crisis_capability(components)["result"]
    assert isinstance(result, dict)
    return result


class _ComponentCache:
    def __init__(
        self,
        components: dict[str, dict[str, object]],
        *,
        missing: set[str] | None = None,
    ) -> None:
        self.components = components
        self.missing = missing or set()

    def get_or_build(self, key: str, _builder):
        component = self._component_name(key)
        if component in self.missing:
            raise RuntimeError(f"{component} deliberately unavailable")
        return self.components[component]

    def get_or_build_with_status(self, key: str, builder):
        return self.get_or_build(key, builder), "hit"

    def shorten_if_same(self, key: str, value: object, *, ttl_seconds: float) -> bool:
        # This fixture pins component payloads; real cache expiry is tested separately.
        assert self.components[self._component_name(key)] is value
        assert ttl_seconds > 0
        return False

    @staticmethod
    def _component_name(key: str) -> str:
        if key.startswith("choice-series/latest"):
            return "choice_latest"
        if key.startswith("market-data/rates"):
            return "market_rates"
        if key.startswith("macro-toolkit/analysis::core"):
            return "macro_analysis_core"
        if key.startswith("macro-toolkit/analysis::full"):
            return "macro_analysis_full"
        if key.startswith("macro-toolkit/strategy-summaries"):
            return "macro_strategy_summaries"
        raise AssertionError(key)


def _build_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    health: MacroToolkitRefreshReceiptHealth,
    *,
    components: dict[str, dict[str, object]] | None = None,
    missing: set[str] | None = None,
    include: frozenset[str] | None = None,
    duckdb_path: str = "test.duckdb",
) -> dict[str, object]:
    values = components or _base_components()
    monkeypatch.setattr(
        snapshot_service,
        "market_home_response_cache",
        _ComponentCache(values, missing=missing),
    )
    monkeypatch.setattr(
        snapshot_service,
        "choice_news_latest_envelope",
        lambda *_args, **_kwargs: values["choice_news"],
    )
    monkeypatch.setattr(
        snapshot_service,
        "_load_macro_pulse_envelope",
        lambda *_args: values["macro_pulse"],
    )
    return snapshot_service.build_market_snapshot(
        include=include or snapshot_service.DEFAULT_MARKET_OVERVIEW_INCLUDE,
        duckdb_path=duckdb_path,
        refresh_receipt_health=health,
    )


def test_snapshot_partitions_and_include_filter(
    monkeypatch: pytest.MonkeyPatch,
    ready_health: MacroToolkitRefreshReceiptHealth,
) -> None:
    complete = _build_snapshot(monkeypatch, ready_health)
    result = complete["result"]
    assert set(result) == {
        "funding_observation",
        "rates_observation",
        "components",
        "gate",
        "dates",
        "tape",
        "pulse",
        "crisis",
        "signals",
        "news",
        "actions",
        "charts",
    }
    validated = MarketOverviewSnapshotEnvelope.model_validate(complete)
    assert validated.result.charts is not None
    assert validated.result.charts.choice_latest is not None
    assert validated.result.charts.market_rates is not None
    tape_only = _build_snapshot(monkeypatch, ready_health, include=frozenset({"tape"}))
    assert set(tape_only["result"]) == {"components", "tape"}


def _observation_components() -> dict[str, dict[str, object]]:
    components = _base_components()
    series = []
    for series_id, value, previous in (
        ("CA.DR007", 1.5, 1.6),
        ("NCD.SHIBOR.3M", 1.43, 1.42),
        ("EMM00588704", 1.25, 1.30),
        ("EMM00166462", 1.5, 1.52),
        ("EMM00166466", 1.68, 1.70),
    ):
        item = _point(series_id, trade_date="2026-09-04", value=value, unit="%")
        item["recent_points"] = [{
            "trade_date": "2026-09-03", "value_numeric": previous,
            "quality_flag": "ok", "source_version": item["source_version"],
            "vendor_version": item["vendor_version"],
        }]
        series.append(item)
    components["market_rates"] = _envelope({"series": series}, basis="formal")
    return components


def test_observations_isolate_unrelated_stable_series_warning_in_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    ready_health: MacroToolkitRefreshReceiptHealth,
) -> None:
    components = _observation_components()
    components["market_rates"]["result"]["series"].append(
        _point("NCD.SHIBOR.1M", unit="%", quality_flag="warning"),
    )
    components["market_rates"]["result_meta"]["quality_flag"] = "warning"

    # The normal cache loader calls _component_from_envelope; do not bypass its
    # aggregate degraded status by passing source_ok directly to the builder.
    payload = _build_snapshot(monkeypatch, ready_health, components=components)

    assert payload["result"]["components"]["market_rates"]["status"] == "degraded"
    assert payload["result_meta"]["quality_flag"] == "warning"
    funding = payload["result"]["funding_observation"]
    rates = payload["result"]["rates_observation"]
    assert funding["judgment_allowed"]
    assert funding["rows"][0]["change_bp"] == -10
    assert rates["full_curve_comparison_allowed"]
    assert [row["change_bp"] for row in rates["rows"]] == [-5, -2, -2]
    assert rates["spreads"][0]["change_bp"] == 3
    MarketOverviewSnapshotEnvelope.model_validate(payload)


def test_observations_invalid_required_leg_only_blocks_its_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    ready_health: MacroToolkitRefreshReceiptHealth,
) -> None:
    components = _observation_components()
    components["market_rates"]["result"]["series"][2]["quality_flag"] = "warning"
    components["market_rates"]["result_meta"]["quality_flag"] = "warning"

    payload = _build_snapshot(monkeypatch, ready_health, components=components)

    rates = payload["result"]["rates_observation"]
    assert rates["judgment_allowed"] and not rates["full_curve_comparison_allowed"]
    assert [row["change_bp"] for row in rates["rows"]] == [None, -2, -2]
    assert rates["spreads"][0]["value_bp"] is None
    assert rates["spreads"][1]["change_bp"] == 0
    assert payload["result"]["funding_observation"]["judgment_allowed"]


@pytest.mark.parametrize("failure", [
    "load_failed", "malformed_envelope", "quality_error", "quality_stale",
    "quality_missing", "vendor_unavailable", "vendor_stale", "fallback",
])
def test_observations_keep_whole_source_failures_blocked_in_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    ready_health: MacroToolkitRefreshReceiptHealth,
    failure: str,
) -> None:
    components = _observation_components()
    meta = components["market_rates"]["result_meta"]
    missing = {"market_rates"} if failure == "load_failed" else None
    if failure == "malformed_envelope":
        components["market_rates"].pop("result_meta")
    elif failure.startswith("quality_"):
        meta["quality_flag"] = {"quality_error": "error", "quality_stale": "stale", "quality_missing": None}[failure]
    elif failure.startswith("vendor_"):
        meta["vendor_status"] = failure
    elif failure == "fallback":
        meta["fallback_mode"] = "latest_snapshot"

    result = _build_snapshot(
        monkeypatch, ready_health, components=components, missing=missing,
    )["result"]

    for partition in (result["funding_observation"], result["rates_observation"]):
        assert not partition["judgment_allowed"]
        assert all(row["change_bp"] is None for row in partition["rows"])
    assert all(spread["value_bp"] is None for spread in result["rates_observation"]["spreads"])
    if failure != "load_failed":
        assert result["rates_observation"]["rows"][0]["value"] == 1.25


@pytest.mark.parametrize("later_value", [1.25, 1.26])
def test_failed_receipt_cannot_use_same_day_step_ids_to_restore_current_facts(
    monkeypatch: pytest.MonkeyPatch,
    ready_health: MacroToolkitRefreshReceiptHealth,
    tmp_path: Path,
    later_value: float,
) -> None:
    components = _observation_components()
    series = components["market_rates"]["result"]["series"]
    series.append(_point("M002", trade_date="2026-09-04", value=1.2, unit="%"))
    for point in series:
        point.update(
            source_version="sv_public_bond_zh_us_rate_20260904",
            vendor_version="vv_public_bond_zh_us_rate_20260904",
            run_id="public_cross_asset_refresh:2026-09-04",
        )
        for recent in point["recent_points"]:
            recent.update(source_version=point["source_version"], vendor_version=point["vendor_version"])
    series[2]["value_numeric"] = later_value
    blocked = replace(
        ready_health, ready=False, status="blocked", run_status="failed",
        missing_fields=("receipt.result.steps.commodity_daily_ingest.status",),
        step_statuses={"public_cross_asset_headlines": {
            "status": "success", "row_count": 20,
            "run_id": "public_cross_asset_refresh:2026-09-04",
            "covered_required_series": ["M002", "EMM00588704", "EMM00166462", "EMM00166466"],
            "failed_sources": [], "source_failures": [],
        }},
    )

    # These are exactly the current facts that the old verifier could match to
    # the successful-looking step. Its date-based IDs also survive the update.
    path = tmp_path / "same_day_repeat.duckdb"
    with duckdb.connect(str(path)) as conn:
        conn.execute(
            "CREATE TABLE fact_choice_macro_daily(series_id VARCHAR, trade_date VARCHAR, "
            "value_numeric DOUBLE, unit VARCHAR, source_version VARCHAR, "
            "vendor_version VARCHAR, run_id VARCHAR, quality_flag VARCHAR)"
        )
        for item in series:
            for point in [item, *item["recent_points"]]:
                conn.execute(
                    "INSERT INTO fact_choice_macro_daily VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [item["series_id"], point["trade_date"], point["value_numeric"], item["unit"],
                     item["source_version"], item["vendor_version"], item["run_id"], "ok"],
                )

    result = _build_snapshot(
        monkeypatch, blocked, components=components, duckdb_path=str(path),
    )["result"]

    assert result["gate"]["level"] == "blocked"
    assert result["gate"]["human_reason"] == blocked.analysis_warnings()[0]
    assert not result["funding_observation"]["judgment_allowed"]
    assert result["funding_observation"]["rows"][0]["series_id"] == "CA.DR007"
    assert not result["rates_observation"]["judgment_allowed"]
    assert result["rates_observation"]["rows"][0]["value"] == later_value
    assert all(row["change_bp"] is None for row in result["rates_observation"]["rows"])
    assert all(spread["value_bp"] is None for spread in result["rates_observation"]["spreads"])


def test_snapshot_non_finite_values_fail_closed_and_remain_json_serializable(
    monkeypatch: pytest.MonkeyPatch,
    ready_health: MacroToolkitRefreshReceiptHealth,
) -> None:
    components = _base_components()
    rates = components["market_rates"]["result"]
    assert isinstance(rates, dict)
    rate_series = rates["series"]
    assert isinstance(rate_series, list)
    government_10y = next(item for item in rate_series if item["series_id"] == "E1000180")
    government_10y["value_numeric"] = float("nan")
    government_10y["latest_change"] = float("inf")
    dr007 = next(item for item in rate_series if item["series_id"] == "CA.DR007")
    dr007["value_numeric"] = 0.0
    dr007["latest_change"] = float("-inf")
    omo = next(item for item in rate_series if item["series_id"] == "EMM00088132")
    omo["latest_change"] = 1e308
    rates["derived_spreads"] = {"finite_negative": -1.25, "invalid": float("-inf")}

    choice = components["choice_latest"]["result"]
    assert isinstance(choice, dict)
    choice_series = choice["series"]
    assert isinstance(choice_series, list)
    csi_change = next(item for item in choice_series if item["series_id"] == "CA.CSI300_PCT_CHG")
    csi_change["value_numeric"] = -0.25

    pulse = components["macro_pulse"]["result"]
    assert isinstance(pulse, dict)
    indicators = pulse["indicators"]
    assert isinstance(indicators, list)
    cpi = next(item for item in indicators if item["key"] == "cpi")
    cpi["latest_value"] = float("inf")
    ppi = next(item for item in indicators if item["key"] == "ppi")
    ppi["previous_value"] = -1.0
    ppi["latest_value"] = 0.0

    crisis_result = _crisis_result(components)
    crisis_result["crisis_score"] = float("nan")
    crisis_result["percentile"] = float("inf")
    history = crisis_result["score_history"]
    assert isinstance(history, list)
    history.append({"date": "2026-08-29", "crisis_score": float("nan")})

    core_result = components["macro_analysis_core"]["result"]
    assert isinstance(core_result, dict)
    signal_cards = core_result["signal_cards"]
    assert isinstance(signal_cards, list)
    signal_cards[0]["score"] = float("inf")

    payload = _build_snapshot(monkeypatch, ready_health, components=components)
    dumped = MarketOverviewSnapshotEnvelope.model_validate(payload).model_dump(mode="json")
    JSONResponse(dumped)

    result = dumped["result"]
    tape_by_key = {item["key"]: item for item in result["tape"]["slots"]}
    assert tape_by_key["gov_10y"]["value"] is None
    assert tape_by_key["gov_10y"]["status"] == "unavailable"
    assert tape_by_key["gov_10y"]["quality_flag"] == "error"
    assert tape_by_key["dr007"]["value"] == 0.0
    assert tape_by_key["dr007"]["change"] is None
    assert tape_by_key["dr007"]["status"] == "degraded"
    assert all(item["key"] != "rate_move_omo_7d" for item in result["actions"]["items"])
    assert tape_by_key["csi300_close"]["change"] == -0.25

    charts = result["charts"]
    assert charts["status"] == "degraded"
    assert all(
        item["series_id"] != "E1000180"
        for item in charts["market_rates"]["series"]
    )
    assert charts["market_rates"]["derived_spreads"] == {
        "finite_negative": -1.25,
        "invalid": None,
    }

    pulse_by_key = {item["key"]: item for item in result["pulse"]["items"]}
    assert pulse_by_key["cpi"]["latest_value"] is None
    assert pulse_by_key["cpi"]["status"] == "unavailable"
    assert pulse_by_key["ppi"]["previous_value"] == -1.0
    assert pulse_by_key["ppi"]["latest_value"] == 0.0

    assert result["signals"]["status"] == "degraded"
    assert result["signals"]["cards"][0]["score"] is None

    crisis = result["crisis"]
    assert crisis["score"] is None
    assert crisis["percentile"] is None
    assert crisis["current_available"] is False
    assert all(point["crisis_score"] is not None for point in crisis["score_history"])
    assert dumped["result_meta"]["quality_flag"] == "warning"


def test_snapshot_charts_only_carry_governed_first_screen_series(
    monkeypatch: pytest.MonkeyPatch,
    ready_health: MacroToolkitRefreshReceiptHealth,
) -> None:
    components = _base_components()
    choice_rows = components["choice_latest"]["result"]["series"]
    rates_rows = components["market_rates"]["result"]["series"]
    assert isinstance(choice_rows, list)
    assert isinstance(rates_rows, list)
    choice_rows.append(_point("UNRELATED.CHOICE", name="unrelated choice series"))
    rates_rows.extend(
        [
            _point("UNRELATED.RATE", name="unrelated rate series", unit="%"),
            _point("EMM00167613", name="SHIBOR:3M", unit="%"),
        ]
    )

    payload = _build_snapshot(monkeypatch, ready_health, components=components)
    charts = payload["result"]["charts"]
    choice_ids = {item["series_id"] for item in charts["choice_latest"]["series"]}
    rate_ids = {item["series_id"] for item in charts["market_rates"]["series"]}

    assert choice_ids == {"CA.CSI300", "CA.BRENT", "EMM00058124", "CA.COPPER"}
    assert "CA.CSI300_PCT_CHG" not in choice_ids
    assert rate_ids == {
        "EMM00166466",
        "E1000180",
        "CA.DR007",
        "EMM00088132",
        "NCD.SHIBOR.3M",
    }
    assert "EMM00167613" not in rate_ids


def test_gate_levels_preserve_receipt_reason_and_conclusion_tone(
    monkeypatch: pytest.MonkeyPatch,
    ready_health: MacroToolkitRefreshReceiptHealth,
) -> None:
    ok = _build_snapshot(monkeypatch, ready_health)
    assert ok["result"]["gate"]["level"] == "ok"

    warning_components = _base_components(macro_quality="warning")
    review = _build_snapshot(monkeypatch, ready_health, components=warning_components)
    assert review["result"]["gate"]["level"] == "review"

    abandoned = MacroToolkitRefreshReceiptHealth(
        status="abandoned",
        ready=False,
        cache_fingerprint="test:abandoned",
        generated_at="2026-08-27T00:00:00+00:00",
        run_status="running",
        source_version="macro_toolkit_freshness_refresh_v4",
        missing_fields=("receipt.abandoned_running",),
        warnings=(),
        latest_observation_dates={},
        running_age_hours=7.0,
    )
    blocked = _build_snapshot(monkeypatch, abandoned)
    assert blocked["result"]["gate"]["level"] == "blocked"
    assert blocked["result"]["gate"]["human_reason"] == abandoned.analysis_warnings()[0]
    assert blocked["result"]["gate"]["conclusion"]["tone"] == "missing"
    assert blocked["result"]["signals"]["cards"] == []
    assert not blocked["result"]["funding_observation"]["judgment_allowed"]
    assert not blocked["result"]["rates_observation"]["judgment_allowed"]


def test_tape_prefers_configured_aliases_and_never_name_matches(
    monkeypatch: pytest.MonkeyPatch,
    ready_health: MacroToolkitRefreshReceiptHealth,
) -> None:
    components = _base_components()
    choice_rows = components["choice_latest"]["result"]["series"]
    assert isinstance(choice_rows, list)
    choice_rows.append(
        _point("mystery-brent", name="Brent fallback name", unit="USD/bbl")
    )
    choice_rows[:] = [item for item in choice_rows if item["series_id"] != "CA.BRENT"]
    payload = _build_snapshot(monkeypatch, ready_health, components=components)
    slots = {item["key"]: item for item in payload["result"]["tape"]["slots"]}
    assert slots["gov_10y"]["series_id"] == "E1000180"
    assert slots["gov_10y"]["basis"] == "formal"
    assert slots["brent"]["status"] == "unresolved"
    assert slots["brent"]["series_id"] is None


def test_tape_does_not_map_shibor_3m_to_dr007(
    monkeypatch: pytest.MonkeyPatch,
    ready_health: MacroToolkitRefreshReceiptHealth,
) -> None:
    components = _base_components()
    rate_rows = components["market_rates"]["result"]["series"]
    assert isinstance(rate_rows, list)
    rate_rows[:] = [item for item in rate_rows if item["series_id"] != "CA.DR007"]
    rate_rows.append(_point("EMM00167613", name="SHIBOR:3M", unit="%"))

    payload = _build_snapshot(monkeypatch, ready_health, components=components)
    slots = {item["key"]: item for item in payload["result"]["tape"]["slots"]}

    assert slots["dr007"]["status"] == "unresolved"
    assert slots["dr007"]["series_id"] is None


def test_dates_and_news_density_keep_surface_dates_and_shanghai_granularity(
    monkeypatch: pytest.MonkeyPatch,
    ready_health: MacroToolkitRefreshReceiptHealth,
) -> None:
    payload = _build_snapshot(monkeypatch, ready_health)
    result = payload["result"]
    dates = result["dates"]
    assert dates["tape_span"] == {"earliest": "2026-08-25", "latest": "2026-08-28"}
    slots = result["tape"]["slots"]
    assert dates["tape_span"]["latest"] == max(item["trade_date"] for item in slots)
    density = result["news"]["density"]
    rates = next(item for item in density["topics"] if item["key"] == "rates")
    assert rates["cells"][10] == 1  # 12:29 UTC is 20:29 Asia/Shanghai.
    assert result["news"]["granularity"] == {"datetime_rows": 1, "date_only_rows": 1}
    assert sum(sum(item["cells"]) for item in density["topics"]) == 1


def test_missing_choice_component_preserves_rates_and_both_missing_is_error(
    monkeypatch: pytest.MonkeyPatch,
    ready_health: MacroToolkitRefreshReceiptHealth,
) -> None:
    choice_missing = _build_snapshot(
        monkeypatch, ready_health, missing={"choice_latest"}
    )
    assert choice_missing["result"]["tape"]["status"] == "degraded"
    slots = choice_missing["result"]["tape"]["slots"]
    assert all(item["status"] == "ok" for item in slots if item["kind"] == "rate")
    assert all(item["status"] == "unavailable" for item in slots if item["kind"] != "rate")
    assert choice_missing["result_meta"]["quality_flag"] == "warning"

    both_missing = _build_snapshot(
        monkeypatch,
        ready_health,
        missing={"choice_latest", "market_rates"},
    )
    assert both_missing["result_meta"]["quality_flag"] == "error"


def test_missing_contract_pulse_and_full_crisis_are_explicitly_degraded(
    monkeypatch: pytest.MonkeyPatch,
    ready_health: MacroToolkitRefreshReceiptHealth,
) -> None:
    components = _base_components(include_pulse_indicators=False)
    core_result = components["macro_analysis_core"]["result"]
    core_result["indicators"] = []
    full_result = components["macro_analysis_full"]["result"]
    full_result["capability_results"] = []
    payload = _build_snapshot(monkeypatch, ready_health, components=components)
    pulse = payload["result"]["pulse"]
    assert pulse["status"] == "unavailable"
    assert {item["status"] for item in pulse["items"]} == {"unavailable"}
    assert all(item["reason"] == "本地宏观序列暂不可用" for item in pulse["items"])
    assert payload["result"]["crisis"]["status"] == "degraded"
    assert payload["result"]["crisis"]["delta"]["window_points"] == 0


def test_crisis_reads_full_while_gate_and_pulse_use_their_own_components(
    monkeypatch: pytest.MonkeyPatch,
    ready_health: MacroToolkitRefreshReceiptHealth,
) -> None:
    components = _base_components()
    core_result = components["macro_analysis_core"]["result"]
    core_result["capability_results"] = []

    payload = _build_snapshot(monkeypatch, ready_health, components=components)

    assert payload["result"]["gate"]["level"] == "ok"
    assert payload["result"]["pulse"]["status"] == "ok"
    crisis = payload["result"]["crisis"]
    assert crisis["status"] == "ok"
    assert crisis["score"] == pytest.approx(0.3)
    assert crisis["regime"] == "正常"
    assert crisis["percentile"] == pytest.approx(50.0)
    assert crisis["delta"]["window_points"] == 2
    assert crisis["delta"]["score_delta"] == pytest.approx(0.2)
    assert crisis["delta"]["percentile_delta"] == pytest.approx(10.0)
    assert crisis["risk_gate"] == {
        "eligible": True,
        "triggered": False,
        "threshold": 2.0,
        "reason_code": "crisis_score_below_threshold",
    }


def test_crisis_v3_passes_dates_trends_history_quality_and_compact_evidence(
    monkeypatch: pytest.MonkeyPatch,
    ready_health: MacroToolkitRefreshReceiptHealth,
) -> None:
    components = _base_components()
    result = _crisis_result(components)
    result["warnings"] = ["result warning"]
    _crisis_capability(components)["warnings"] = ["result warning", "card warning"]
    history_start = date(2026, 6, 25)
    result["score_history"] = [
        {
            "date": (history_start + timedelta(days=index)).isoformat(),
            "crisis_score": round(-0.34 + index / 100, 4),
            "percentile": float(index),
            "available_component_count": 5 if index % 2 == 0 else 4,
            "component_count": 5,
            "available_weight": 1.0 if index % 2 == 0 else 0.8,
            "data_status": "complete" if index % 2 == 0 else "degraded",
        }
        for index in range(65)
    ]

    payload = _build_snapshot(monkeypatch, ready_health, components=components)
    crisis = payload["result"]["crisis"]

    assert payload["result_meta"]["rule_version"] == "rv_market_overview_snapshot_v8"
    assert payload["result_meta"]["cache_version"] == "cv_market_overview_snapshot_v8"
    assert "::cv_market_overview_snapshot_v8::" in payload["result_meta"]["cache_key"]
    assert crisis["report_date"] == "2026-08-28"
    assert crisis["requested_report_date"] == "2026-08-28"
    assert crisis["rule_version"] == "rv_macro_crisis_score_cn_v1"
    assert [item["requested_window_points"] for item in crisis["score_trends"]] == [20, 60]
    assert crisis["score_trend"] == crisis["score_trends"][0]
    assert crisis["delta"] == {
        "window_points": 2,
        "score_delta": pytest.approx(0.2),
        "percentile_delta": pytest.approx(10.0),
    }
    assert len(crisis["score_history"]) == 60
    assert crisis["score_history"][0] == {
        "date": "2026-06-30",
        "crisis_score": pytest.approx(-0.29),
        "percentile": pytest.approx(5.0),
        "available_component_count": 4,
        "component_count": 5,
        "available_weight": pytest.approx(0.8),
        "data_status": "degraded",
    }
    assert crisis["warnings"] == ["result warning", "card warning"]
    assert crisis["available_component_count"] == 5
    assert crisis["component_count"] == 5
    assert crisis["input_evidence"]["inputs"][0] == {
        "field": "aa_5y",
        "label": "AA 5Y",
        "aliases": ["EMM00166683"],
        "warning": "AA 5Y unavailable",
        "required": True,
        "available": True,
        "row_count": 60,
        "latest_date": "2026-08-28",
        "series_id": "EMM00166683",
        "source": "Choice",
        "stale": False,
        "stale_days": 0,
    }
    assert "value" not in crisis["input_evidence"]["inputs"][0]
    MarketOverviewSnapshotEnvelope.model_validate(payload)


def test_crisis_legacy_single_trend_is_projected_into_v3_list(
    monkeypatch: pytest.MonkeyPatch,
    ready_health: MacroToolkitRefreshReceiptHealth,
) -> None:
    components = _base_components()
    result = _crisis_result(components)
    result.pop("score_trends")

    crisis = _build_snapshot(
        monkeypatch,
        ready_health,
        components=components,
    )["result"]["crisis"]

    assert crisis["status"] == "ok"
    assert crisis["score_trends"] == [crisis["score_trend"]]


@pytest.mark.parametrize(
    ("failure", "expected_reason"),
    [
        ("dependency", "required_refresh_step_not_ready"),
        ("data_status", "crisis_score_data_not_complete"),
        ("missing_gate", "crisis_score_risk_gate_contract_invalid"),
        ("inconsistent_gate", "crisis_score_risk_gate_inconsistent"),
    ],
)
def test_crisis_risk_gate_fails_closed_on_untrusted_upstream_state(
    monkeypatch: pytest.MonkeyPatch,
    ready_health: MacroToolkitRefreshReceiptHealth,
    failure: str,
    expected_reason: str,
) -> None:
    components = _base_components(crisis_gate_triggered=True)
    capability = _crisis_capability(components)
    result = _crisis_result(components)
    risk_gate = result["risk_gate"]
    assert isinstance(risk_gate, dict)
    if failure == "dependency":
        capability["dependency_gate"] = {
            "status": "blocked",
            "blocked_by": ["choice_crisis_aa_5y"],
            "reason_code": expected_reason,
        }
    elif failure == "data_status":
        result["data_status"] = "degraded"
    elif failure == "missing_gate":
        result.pop("risk_gate")
    else:
        risk_gate["eligible"] = False

    crisis = _build_snapshot(
        monkeypatch,
        ready_health,
        components=components,
    )["result"]["crisis"]

    assert crisis["status"] == "degraded"
    assert crisis["risk_gate"]["eligible"] is False
    assert crisis["risk_gate"]["triggered"] is False
    assert crisis["risk_gate"]["reason_code"] == expected_reason
    if failure == "dependency":
        assert crisis["score"] is None
        assert crisis["dependency_gate"] == {
            "status": "blocked",
            "blocked_by": ["choice_crisis_aa_5y"],
            "reason_code": expected_reason,
        }


def test_crisis_preserves_raw_precision_and_explicit_null_percentile(
    monkeypatch: pytest.MonkeyPatch,
    ready_health: MacroToolkitRefreshReceiptHealth,
) -> None:
    components = _base_components()
    capability = _crisis_capability(components)
    result = _crisis_result(components)
    capability["score"] = -0.7
    result["crisis_score"] = -0.6971
    result["percentile"] = None
    history = result["score_history"]
    assert isinstance(history, list)
    assert isinstance(history[-1], dict)
    history[-1]["percentile"] = 99.0

    payload = _build_snapshot(monkeypatch, ready_health, components=components)
    crisis = payload["result"]["crisis"]

    assert crisis["score"] == pytest.approx(-0.6971)
    assert crisis["percentile"] is None
    serialized = MarketOverviewSnapshotEnvelope.model_validate(payload).model_dump(
        mode="json",
        exclude_unset=True,
    )
    assert "percentile" in serialized["result"]["crisis"]
    assert serialized["result"]["crisis"]["percentile"] is None


def test_crisis_status_ignores_unrelated_macro_component_degradation(
    monkeypatch: pytest.MonkeyPatch,
    ready_health: MacroToolkitRefreshReceiptHealth,
) -> None:
    components = _base_components()
    full_meta = components["macro_analysis_full"]["result_meta"]
    assert isinstance(full_meta, dict)
    full_meta["quality_flag"] = "warning"

    payload = _build_snapshot(monkeypatch, ready_health, components=components)

    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result"]["crisis"]["status"] == "ok"


def test_gate_and_pulse_do_not_depend_on_full_component(
    monkeypatch: pytest.MonkeyPatch,
    ready_health: MacroToolkitRefreshReceiptHealth,
) -> None:
    payload = _build_snapshot(
        monkeypatch,
        ready_health,
        missing={"macro_analysis_full"},
    )

    assert payload["result"]["gate"]["level"] == "ok"
    assert payload["result"]["pulse"]["status"] == "ok"
    assert payload["result"]["crisis"]["status"] == "unavailable"
    assert payload["result"]["crisis"]["risk_gate"]["eligible"] is False


def test_crisis_actions_follow_formal_risk_gate_not_localized_regime(
    monkeypatch: pytest.MonkeyPatch,
    ready_health: MacroToolkitRefreshReceiptHealth,
) -> None:
    normal = _build_snapshot(monkeypatch, ready_health)
    normal_action_keys = {
        item["key"] for item in normal["result"]["actions"]["items"]
    }
    assert "crisis_regime_review" not in normal_action_keys

    loose = _build_snapshot(
        monkeypatch,
        ready_health,
        components=_base_components(crisis_regime="宽松"),
    )
    loose_action_keys = {
        item["key"] for item in loose["result"]["actions"]["items"]
    }
    assert "crisis_regime_review" not in loose_action_keys

    ineligible = _build_snapshot(
        monkeypatch,
        ready_health,
        components=_base_components(
            crisis_gate_eligible=False,
            crisis_gate_reason_code="crisis_score_data_not_complete",
        ),
    )
    crisis_action = next(
        item
        for item in ineligible["result"]["actions"]["items"]
        if item["key"] == "crisis_regime_review"
    )
    assert crisis_action["label"] == "复核 Crisis Score 数据完整性"
    assert crisis_action["evidence"]["reason_code"] == "crisis_score_data_not_complete"


def test_result_meta_lineage_is_bounded_and_actions_cover_each_rule(
    monkeypatch: pytest.MonkeyPatch,
    ready_health: MacroToolkitRefreshReceiptHealth,
) -> None:
    components = _base_components(
        choice_date="2020-01-01",
        rate_change=0.06,
        crisis_regime="高风险",
        crisis_gate_triggered=True,
        crisis_gate_reason_code="crisis_score_at_or_above_threshold",
    )
    for index, component in enumerate(components.values(), start=1):
        component["result_meta"]["source_version"] = "__".join(
            f"sv_{index}_{part}" for part in range(9)
        )
        component["result_meta"]["vendor_version"] = "__".join(
            f"vv_{index}_{part}" for part in range(9)
        )
    payload = _build_snapshot(monkeypatch, ready_health, components=components)
    meta = payload["result_meta"]
    assert meta["source_version"].startswith("sha256:")
    assert meta["filters_applied"]["lineage_segments"]["source_version"] > 8
    action_keys = {item["key"] for item in payload["result"]["actions"]["items"]}
    assert "news_human_review" in action_keys
    assert "rate_move_gov_10y" in action_keys
    assert "crisis_regime_review" in action_keys
    assert any(key.startswith("surface_stale_") for key in action_keys)


def test_blocked_gate_creates_p0_action(
    monkeypatch: pytest.MonkeyPatch,
    ready_health: MacroToolkitRefreshReceiptHealth,
) -> None:
    blocked = MacroToolkitRefreshReceiptHealth(
        status="blocked",
        ready=False,
        cache_fingerprint="test:blocked",
        generated_at=ready_health.generated_at,
        run_status="failed",
        source_version=ready_health.source_version,
        missing_fields=("receipt.status",),
        warnings=(),
        latest_observation_dates={},
        failure_message="test failure",
    )
    payload = _build_snapshot(monkeypatch, blocked)
    assert any(
        item["priority"] == "P0" and item["key"] == "refresh_gate_blocked"
        for item in payload["result"]["actions"]["items"]
    )


def test_route_parses_include_and_reuses_macro_toolkit_read_authorization(
    monkeypatch: pytest.MonkeyPatch,
    ready_health: MacroToolkitRefreshReceiptHealth,
) -> None:
    captured: dict[str, object] = {}
    snapshot_route = next(
        route
        for route in market_overview_route.router.routes
        if route.path == "/ui/market-overview/snapshot"
    )
    assert snapshot_route.response_model is MarketOverviewSnapshotEnvelope
    assert snapshot_route.response_model_exclude_unset is True

    class RouteCache:
        def generation(self):
            return 0

        def get_or_build_with_status(self, key, builder):
            captured["cache_key"] = key
            return builder(), "produce"

    monkeypatch.setattr(
        market_overview_route,
        "ensure_read_allowed",
        lambda *args, **kwargs: captured.setdefault("authorized", args[1]),
    )
    monkeypatch.setattr(
        market_overview_route,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path="route.duckdb"),
    )
    monkeypatch.setattr(
        market_overview_route,
        "load_macro_toolkit_refresh_receipt_health",
        lambda: ready_health,
    )
    monkeypatch.setattr(
        market_overview_route, "market_home_response_cache", RouteCache()
    )
    monkeypatch.setattr(
        market_overview_route,
        "build_market_snapshot",
        lambda **kwargs: (captured.setdefault("build", kwargs), {"result": {}})[1],
    )

    market_overview_route.market_overview_snapshot(auth=object(), include="tape,news")
    assert captured["authorized"] == "macro_toolkit"
    assert "::cv_market_overview_snapshot_v8::" in captured["cache_key"]
    assert captured["build"]["include"] == frozenset({"tape", "news"})
    with pytest.raises(HTTPException, match="Unsupported market-overview include"):
        market_overview_route._parse_include("tape,unknown")
