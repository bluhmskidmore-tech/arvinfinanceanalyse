"""Read-only composition for the market-overview first-screen snapshot."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import SupportsFloat, SupportsIndex, TypedDict, cast
from zoneinfo import ZoneInfo

from backend.app.core_finance.macro.crisis_score import (
    CRISIS_SCORE_RISK_GATE_THRESHOLD,
    DEFAULT_CRISIS_SCORE_HISTORY_LIMIT,
)
from backend.app.core_finance.rate_units import pct_to_bp
from backend.app.observability.response_cache import (
    market_home_choice_latest_cache_key,
    market_home_macro_analysis_cache_key,
    market_home_rates_cache_key,
    market_home_response_cache,
    market_home_strategy_summaries_cache_key,
)
from backend.app.repositories.home_macro_release_context_repo import HomeMacroReleaseContextRepository
from backend.app.schemas.macro_vendor import ChoiceMacroLatestPoint
from backend.app.services.choice_news_service import choice_news_latest_envelope
from backend.app.services.formal_result_runtime import QualityFlag, VendorStatus, build_result_envelope
from backend.app.services.home_macro_release_context_service import HomeMacroReleaseContextService
from backend.app.services.macro_toolkit_read_service import (
    build_macro_toolkit_analysis,
    build_macro_toolkit_strategy_summaries,
)
from backend.app.services.macro_toolkit_refresh_receipt_service import (
    MacroToolkitRefreshReceiptHealth,
)
from backend.app.services.macro_vendor_service import (
    _latest_choice_macro_point,
    choice_macro_formal_envelope,
    choice_macro_latest_envelope,
)
from backend.app.services.market_observation_service import build_market_observations

MARKET_SNAPSHOT_RULE_VERSION = "rv_market_overview_snapshot_v8"
MARKET_SNAPSHOT_CACHE_VERSION = "cv_market_overview_snapshot_v8"
MARKET_SNAPSHOT_TRACE_ID = "tr_market_overview_snapshot"


class _CrisisTrend(TypedDict):
    requested_window_points: int
    window_points: int
    start_date: str | None
    end_date: str | None
    start_score: float | None
    end_score: float | None
    score_change: float | None
    start_percentile: float | None
    end_percentile: float | None
    percentile_change: float | None
    direction: str


class _CrisisHistoryPoint(TypedDict):
    date: str
    crisis_score: float
    percentile: float | None
    available_component_count: int | None
    component_count: int | None
    available_weight: float | None
    data_status: str | None


DEFAULT_MARKET_OVERVIEW_INCLUDE = frozenset(
    {
        "gate",
        "dates",
        "tape",
        "pulse",
        "crisis",
        "signals",
        "news",
        "actions",
        "charts",
        "funding_observation",
        "rates_observation",
    }
)
SUPPORTED_MARKET_OVERVIEW_INCLUDE = DEFAULT_MARKET_OVERVIEW_INCLUDE
MARKET_OVERVIEW_NEWS_LIMIT = 500
MARKET_OVERVIEW_NEWS_BUCKET_HOURS = 2
MARKET_OVERVIEW_NEWS_DATE_ONLY_GROUPS = frozenset({"tushare_research", "tushare_cctv"})
MARKET_OVERVIEW_RATE_ACTION_BP = 5.0
MARKET_OVERVIEW_CRISIS_HISTORY_LIMIT = 60
MARKET_OVERVIEW_TIMEZONE = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class MarketOverviewTapeSlot:
    key: str
    label: str
    aliases: tuple[str, ...]
    kind: str
    prefer: str = "choice_latest"
    change_key: str | None = None
    change_aliases: tuple[str, ...] = ()


# This is a governed identity registry, not a display-name matcher.  Brent and
# USD/CNY are the stable catalog facts verified for the Phase 1 rollout.
MARKET_OVERVIEW_TAPE_SLOTS = (
    MarketOverviewTapeSlot(
        "gov_10y",
        "10Y国债",
        ("E1000180", "EMM00166466", "CA.CN_GOV_10Y"),
        "rate",
        prefer="rates",
    ),
    MarketOverviewTapeSlot(
        "dr007",
        "DR007",
        ("CA.DR007", "M002"),
        "rate",
        prefer="rates",
    ),
    MarketOverviewTapeSlot(
        "omo_7d",
        "7D逆回购",
        ("EMM00088132", "M001"),
        "rate",
        prefer="rates",
    ),
    MarketOverviewTapeSlot(
        "shibor_3m",
        "SHIBOR 3M",
        ("NCD.SHIBOR.3M",),
        "rate",
        prefer="rates",
    ),
    MarketOverviewTapeSlot(
        "csi300_close",
        "沪深300",
        ("CA.CSI300",),
        "equity",
        change_key="csi300_pct_chg",
        change_aliases=("CA.CSI300_PCT_CHG",),
    ),
    MarketOverviewTapeSlot("brent", "Brent原油", ("CA.BRENT",), "commodity"),
    MarketOverviewTapeSlot(
        "usd_cny_mid",
        "USD/CNY",
        ("EMM00058124", "CA.USDCNY"),
        "fx",
    ),
    MarketOverviewTapeSlot("copper_main", "铜主力", ("CA.COPPER",), "commodity"),
)

# Snapshot charts only need the series used by the dense first screen.  Keep the
# allowlists explicit so an unrelated catalog expansion cannot silently inflate
# this latency-sensitive response or enter a chart through a loose name match.
MARKET_OVERVIEW_CHART_CHOICE_SERIES_IDS = frozenset(
    {
        "CA.ALUMINUM",
        "CA.BRENT",
        "CA.COPPER",
        "CA.CSI300",
        "CA.USDCNY",
        "EMM00058124",
    }
)
MARKET_OVERVIEW_CHART_RATE_SERIES_IDS = frozenset(
    {
        "CA.DR007",
        "E1000180",
        "EMM00088132",
        "EMM00166455",
        "EMM00166456",
        "EMM00166457",
        "EMM00166458",
        "EMM00166460",
        "EMM00166462",
        "EMM00166464",
        "EMM00166466",
        "EMM00166468",
        "EMM00166469",
        "EMM00166489",
        "EMM00166490",
        "EMM00166491",
        "EMM00166492",
        "EMM00166493",
        "EMM00166494",
        "EMM00166495",
        "EMM00166496",
        "EMM00166497",
        "EMM00166498",
        "EMM00166499",
        "EMM00166502",
        "EMM00166504",
        "EMM00588704",
        "M002",
        "NCD.SHIBOR.1M",
        "NCD.SHIBOR.3M",
    }
)

_PULSE_SLOTS = (
    ("cpi", "CPI同比"),
    ("ppi", "PPI同比"),
    ("pmi", "制造业PMI"),
    ("social_financing", "社融存量同比"),
)
# Identities/units follow TUSHARE_M2A_SERIES and cycle_rotation_macro_series.json.
# The macro-toolkit core indicator list contains market rates, not these series.
_PULSE_SOURCE_CONFIGS = (
    {"key": "cpi", "label": "CPI同比", "alias": "M0000612", "unit": "%", "group": "增长与通胀"},
    {"key": "ppi", "label": "PPI同比", "alias": "M0001227", "unit": "%", "group": "增长与通胀"},
    {"key": "pmi", "label": "制造业PMI", "alias": "M0017126", "unit": "index", "group": "增长与通胀"},
    {"key": "social_financing", "label": "社融存量同比", "alias": "M5525763", "unit": "%", "group": "增长与通胀"},
)
_COMPONENT_ORDER = (
    "choice_latest",
    "market_rates",
    "macro_analysis_core",
    "macro_analysis_full",
    "macro_pulse",
    "macro_strategy_summaries",
    "choice_news",
)
_MAX_COMPONENT_WORKERS = 3
MARKET_OVERVIEW_UNAVAILABLE_CACHE_TTL_SECONDS = 15.0
_MACRO_ANALYSIS_INPUTS_UNAVAILABLE_REASON = (
    "macro analysis inputs unavailable: coverage hit_count=0"
)


@dataclass(frozen=True)
class _Component:
    name: str
    cache_key: str | None
    envelope: Mapping[str, object] | None
    status: str
    reason: str | None


def market_overview_snapshot_cache_key(
    *,
    include: frozenset[str],
    duckdb_path: str,
    freshness_fingerprint: str,
) -> str:
    """Return the snapshot key shared by the thin route and result metadata."""
    include_token = ",".join(sorted(_normalized_include(include)))
    return (
        f"market-overview/snapshot::{include_token}::{MARKET_SNAPSHOT_CACHE_VERSION}::"
        f"{freshness_fingerprint}::{duckdb_path}"
    )


def build_market_snapshot(
    *,
    include: frozenset[str],
    duckdb_path: str,
    refresh_receipt_health: MacroToolkitRefreshReceiptHealth,
) -> dict[str, object]:
    """Build the analytical market snapshot from existing read-model envelopes."""
    resolved_include = _normalized_include(include)
    component_names = _required_component_names(resolved_include)
    components = _load_components(
        component_names=component_names,
        duckdb_path=duckdb_path,
        refresh_receipt_health=refresh_receipt_health,
    )
    component_payload = _component_payload(components)

    tape = _build_tape(components) if {"tape", "dates", "actions"}.intersection(resolved_include) else None
    dates = _build_dates(components, tape=tape) if {"dates", "actions"}.intersection(resolved_include) else None
    gate = (
        _build_gate(refresh_receipt_health, components.get("macro_analysis_core"))
        if {"gate", "actions"}.intersection(resolved_include)
        else None
    )
    pulse = _build_pulse(components.get("macro_pulse")) if "pulse" in resolved_include else None
    crisis = (
        _build_crisis(components.get("macro_analysis_full"))
        if {"crisis", "actions"}.intersection(resolved_include)
        else None
    )
    signals = _build_signals(components.get("macro_analysis_core")) if "signals" in resolved_include else None
    if signals is not None and not refresh_receipt_health.ready:
        signals = {"status": "unavailable", "reason": "刷新回执未通过核验，方向标签暂停展示。", "cards": []}
    observations = {}
    if {"funding_observation", "rates_observation"}.intersection(resolved_include):
        rates_component = components.get("market_rates")
        rates_meta = _component_meta(rates_component) if rates_component is not None else {}
        # Stable-series quality is aggregated across unrelated inputs. A warning
        # must stay visible on the component without disabling valid curve legs;
        # each observation still checks its own quality, dates, unit and fallback.
        source_ok = (
            rates_component is not None
            and rates_component.status != "unavailable"
            and rates_meta.get("quality_flag") in {"ok", "warning"}
            and rates_meta.get("vendor_status") in {None, "ok"}
            and rates_meta.get("fallback_mode") in {None, "none"}
        )
        funding, rates = build_market_observations(
            _component_result(rates_component),
            source_ok=source_ok,
            receipt_ready=refresh_receipt_health.ready,
        )
        observations = {"funding_observation": funding, "rates_observation": rates}
    news = _build_news(components.get("choice_news")) if {"news", "actions"}.intersection(resolved_include) else None
    charts = _build_charts(components) if "charts" in resolved_include else None
    actions = (
        _build_actions(gate=gate, dates=dates, tape=tape, crisis=crisis, news=news)
        if "actions" in resolved_include
        else None
    )

    result: dict[str, object] = {"components": component_payload}
    result.update({key: value for key, value in observations.items() if key in resolved_include})
    for name, partition in (
        ("gate", gate),
        ("dates", dates),
        ("tape", tape),
        ("pulse", pulse),
        ("crisis", crisis),
        ("signals", signals),
        ("news", news),
        ("actions", actions),
        ("charts", charts),
    ):
        if name in resolved_include and partition is not None:
            result[name] = partition
    source_version, source_segments = _aggregate_lineage_value(
        components.values(), "source_version", empty_value="sv_market_snapshot_empty"
    )
    vendor_version, vendor_segments = _aggregate_lineage_value(
        components.values(), "vendor_version", empty_value="vv_none"
    )
    quality_flag = _snapshot_quality_flag(components, gate)
    if quality_flag == "ok" and any(
        isinstance(partition, Mapping) and partition.get("status") != "ok"
        for partition in (tape, pulse, crisis, signals, news, charts)
        if partition is not None
    ):
        quality_flag = "warning"
    vendor_status = _snapshot_vendor_status(components)
    filters_applied: dict[str, object] = {
        "include": sorted(resolved_include),
        "date_basis": "per_surface",
        "news_density": {
            "timezone": "Asia/Shanghai",
            "bucket_hours": MARKET_OVERVIEW_NEWS_BUCKET_HOURS,
            "date_only_groups": sorted(MARKET_OVERVIEW_NEWS_DATE_ONLY_GROUPS),
        },
        "lineage_segments": {
            "source_version": source_segments,
            "vendor_version": vendor_segments,
        },
    }
    if isinstance(dates, Mapping):
        filters_applied["dates"] = {
            "date_basis": dates.get("date_basis"),
            "tape_span": dates.get("tape_span"),
        }

    return build_result_envelope(
        basis="analytical",
        trace_id=MARKET_SNAPSHOT_TRACE_ID,
        result_kind="market.snapshot",
        cache_version=MARKET_SNAPSHOT_CACHE_VERSION,
        cache_key=market_overview_snapshot_cache_key(
            include=resolved_include,
            duckdb_path=duckdb_path,
            freshness_fingerprint=refresh_receipt_health.cache_fingerprint,
        ),
        source_version=source_version,
        rule_version=MARKET_SNAPSHOT_RULE_VERSION,
        result_payload=result,
        quality_flag=quality_flag,
        vendor_version=vendor_version,
        vendor_status=vendor_status,
        fallback_mode="none",
        filters_applied=filters_applied,
        tables_used=_tables_used(components.values()),
        evidence_rows=_evidence_rows(components.values()),
        source_surface="market_data",
        as_of_date=None,
        date_basis="per_surface",
    )


def _normalized_include(include: frozenset[str]) -> frozenset[str]:
    return include or DEFAULT_MARKET_OVERVIEW_INCLUDE


def _required_component_names(include: frozenset[str]) -> set[str]:
    needed: set[str] = set()
    if {"funding_observation", "rates_observation"}.intersection(include):
        needed.add("market_rates")
    if {"tape", "dates", "actions", "charts"}.intersection(include):
        needed.update({"choice_latest", "market_rates"})
    if {"gate", "dates", "signals", "actions"}.intersection(include):
        needed.add("macro_analysis_core")
    if "pulse" in include:
        needed.add("macro_pulse")
    if {"crisis", "actions"}.intersection(include):
        needed.add("macro_analysis_full")
    if {"dates", "actions"}.intersection(include):
        needed.add("macro_strategy_summaries")
    if {"news", "dates", "actions"}.intersection(include):
        needed.add("choice_news")
    return needed


def _load_components(
    *,
    component_names: set[str],
    duckdb_path: str,
    refresh_receipt_health: MacroToolkitRefreshReceiptHealth,
) -> dict[str, _Component]:
    builders: dict[str, tuple[str, Callable[[], dict[str, object]]]] = {
        "choice_latest": (
            market_home_choice_latest_cache_key(duckdb_path),
            lambda: choice_macro_latest_envelope(duckdb_path, category=None),
        ),
        "market_rates": (
            market_home_rates_cache_key(duckdb_path),
            lambda: choice_macro_formal_envelope(duckdb_path),
        ),
        "macro_analysis_core": (
            market_home_macro_analysis_cache_key(
                duckdb_path,
                "core",
                freshness_fingerprint=refresh_receipt_health.cache_fingerprint,
            ),
            lambda: build_macro_toolkit_analysis(
                "core",
                refresh_receipt_health=refresh_receipt_health,
            ),
        ),
        "macro_analysis_full": (
            market_home_macro_analysis_cache_key(
                duckdb_path,
                "full",
                history_limit=DEFAULT_CRISIS_SCORE_HISTORY_LIMIT,
                freshness_fingerprint=refresh_receipt_health.cache_fingerprint,
            ),
            lambda: build_macro_toolkit_analysis(
                "full",
                history_limit=DEFAULT_CRISIS_SCORE_HISTORY_LIMIT,
                refresh_receipt_health=refresh_receipt_health,
            ),
        ),
        "macro_strategy_summaries": (
            market_home_strategy_summaries_cache_key(duckdb_path),
            build_macro_toolkit_strategy_summaries,
        ),
    }

    def load_component(component_name: str) -> _Component:
        if component_name == "macro_pulse":
            return _load_direct_component(
                component_name, lambda: _load_macro_pulse_envelope(duckdb_path)
            )
        if component_name == "choice_news":
            return _load_direct_component(
                component_name,
                lambda: choice_news_latest_envelope(
                    duckdb_path,
                    limit=MARKET_OVERVIEW_NEWS_LIMIT,
                ),
            )
        cache_key, builder = builders[component_name]
        return _load_cached_component(
            component_name,
            cache_key=cache_key,
            builder=builder,
        )

    selected_names = tuple(name for name in _COMPONENT_ORDER if name in component_names)
    if len(selected_names) < 2:
        return {name: load_component(name) for name in selected_names}

    with ThreadPoolExecutor(
        max_workers=min(_MAX_COMPONENT_WORKERS, len(selected_names)),
        thread_name_prefix="market-overview-component",
    ) as executor:
        futures = {
            name: executor.submit(copy_context().run, load_component, name)
            for name in selected_names
        }
        return {name: futures[name].result() for name in selected_names}


def _load_macro_pulse_envelope(duckdb_path: str) -> dict[str, object]:
    from backend.app.core_finance.macro.toolkit.system_sources import load_series_by_aliases
    from backend.app.services.macro_toolkit_route_support import _indicator_payload

    frames = load_series_by_aliases(
        tuple(config["alias"] for config in _PULSE_SOURCE_CONFIGS),
        end=datetime.now(MARKET_OVERVIEW_TIMEZONE).date().isoformat(),
        duckdb_path=duckdb_path,
    )
    indicators = [_indicator_payload(config, frames[config["alias"]]) for config in _PULSE_SOURCE_CONFIGS]
    # The compatibility table labels every row as Choice. Resolve the actual
    # publisher from the same observation's persisted lineage, as the home
    # macro release panel already does, without changing any observed value.
    repository = HomeMacroReleaseContextRepository(duckdb_path)
    for item in indicators:
        if item.get("source") != "choice" or not item.get("latest_date"):
            continue
        observed_date = _parse_iso_date(item["latest_date"])
        if observed_date is None:
            continue
        try:
            read = repository.read_recent_observations(
                table="fact_choice_macro_daily", series_id=str(item["series_id"]),
                cutoff_date=observed_date, limit=1,
            )
            observation = read.observations[0] if read.observations else None
            if (
                observation is not None and observation.observation_date == observed_date
                and observation.value is not None
                and round(observation.value, 4) == item["latest_value"]
            ):
                source = HomeMacroReleaseContextService._vendor_label(observation, configured=None)
                item["source"] = {
                    "NBS official artifact": "国家统计局（官方发布）",
                    "unknown vendor": "来源待核验",
                }.get(source, source)
            else:
                item["source"] = "来源待核验"
        except Exception:  # noqa: BLE001 - preserve available values if lineage cannot be read
            item["source"] = "来源待核验"
    available = [item for item in indicators if item["latest_value"] is not None]
    dates = [str(item["latest_date"]) for item in available if item["latest_date"]]
    return build_result_envelope(
        basis="analytical",
        trace_id="tr_market_overview_macro_pulse",
        result_kind="market.snapshot.pulse",
        cache_version=MARKET_SNAPSHOT_CACHE_VERSION,
        source_version="sv_macro_pulse_" + hashlib.sha256(
            repr([(item["series_id"], item["latest_date"], item["latest_value"]) for item in indicators]).encode()
        ).hexdigest()[:12],
        rule_version=MARKET_SNAPSHOT_RULE_VERSION,
        result_payload={"indicators": indicators},
        quality_flag="ok" if len(available) == len(indicators) else "warning",
        vendor_status="ok" if available else "vendor_unavailable",
        evidence_rows=sum(int(cast(int, item["row_count"])) for item in indicators),
        source_surface="market_data",
        as_of_date=max(dates) if dates else None,
        date_basis="per_series_observation_date",
    )


def _load_cached_component(
    name: str,
    *,
    cache_key: str,
    builder: Callable[[], dict[str, object]],
) -> _Component:
    try:
        envelope, _cache_status = market_home_response_cache.get_or_build_with_status(
            cache_key,
            builder,
        )
    # One failed component must remain visible without breaking the composite snapshot.
    except Exception as exc:  # noqa: BLE001
        return _Component(
            name=name,
            cache_key=cache_key,
            envelope=None,
            status="unavailable",
            reason=f"component load failed: {type(exc).__name__}",
        )
    component = _component_from_envelope(name, cache_key=cache_key, envelope=envelope)
    if (
        component.status == "unavailable"
        or market_overview_response_requires_short_cache(envelope)
    ):
        market_home_response_cache.shorten_if_same(
            cache_key,
            envelope,
            ttl_seconds=MARKET_OVERVIEW_UNAVAILABLE_CACHE_TTL_SECONDS,
        )
    return component


def _load_direct_component(name: str, builder: Callable[[], dict[str, object]]) -> _Component:
    try:
        envelope = builder()
    # One failed component must remain visible without breaking the composite snapshot.
    except Exception as exc:  # noqa: BLE001
        return _Component(
            name=name,
            cache_key=None,
            envelope=None,
            status="unavailable",
            reason=f"component load failed: {type(exc).__name__}",
        )
    return _component_from_envelope(name, cache_key=None, envelope=envelope)


def _component_from_envelope(
    name: str,
    *,
    cache_key: str | None,
    envelope: object,
) -> _Component:
    if not isinstance(envelope, Mapping):
        return _Component(
            name=name,
            cache_key=cache_key,
            envelope=None,
            status="unavailable",
            reason="component returned no result envelope",
        )
    result = envelope.get("result")
    meta = envelope.get("result_meta")
    if not isinstance(result, Mapping) or not isinstance(meta, Mapping):
        return _Component(
            name=name,
            cache_key=cache_key,
            envelope=envelope,
            status="unavailable",
            reason="component envelope is missing result or result_meta",
        )
    if _macro_analysis_inputs_unavailable(envelope):
        return _Component(
            name=name,
            cache_key=cache_key,
            envelope=envelope,
            status="unavailable",
            reason=_MACRO_ANALYSIS_INPUTS_UNAVAILABLE_REASON,
        )
    quality_flag = str(meta.get("quality_flag") or "warning")
    reasons = []
    if quality_flag != "ok":
        reasons.append(f"quality_flag={quality_flag}")
    if meta.get("vendor_status") not in (None, "ok"):
        reasons.append(f"vendor_status={meta['vendor_status']}")
    if meta.get("fallback_mode") not in (None, "none"):
        reasons.append(f"fallback_mode={meta['fallback_mode']}")
    return _Component(
        name=name,
        cache_key=cache_key,
        envelope=envelope,
        status="degraded" if reasons else "ok",
        reason="; ".join(reasons) or None,
    )


def market_overview_response_requires_short_cache(payload: object) -> bool:
    """Return whether a transiently unavailable page read needs the short TTL."""
    if not isinstance(payload, Mapping):
        return True
    meta = _mapping_or_empty(payload.get("result_meta"))
    if meta.get("vendor_status") == "vendor_unavailable":
        return True
    if _macro_analysis_inputs_unavailable(payload):
        return True
    components = _mapping_or_empty(_mapping_or_empty(payload.get("result")).get("components"))
    return any(
        isinstance(component, Mapping)
        and (
            component.get("status") == "unavailable"
            or component.get("vendor_status") == "vendor_unavailable"
        )
        for component in components.values()
    )


def _macro_analysis_inputs_unavailable(payload: Mapping[str, object]) -> bool:
    meta = _mapping_or_empty(payload.get("result_meta"))
    if meta.get("result_kind") != "macro_toolkit.analysis":
        return False
    coverage = _mapping_or_empty(_mapping_or_empty(payload.get("result")).get("coverage"))
    indicator_count = _integer_or_none(coverage.get("indicator_count"))
    hit_count = _integer_or_none(coverage.get("hit_count"))
    return indicator_count is not None and indicator_count > 0 and hit_count == 0


def _component_payload(components: Mapping[str, _Component]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for name in _COMPONENT_ORDER:
        component = components.get(name)
        if component is None:
            continue
        meta = _component_meta(component)
        payload[name] = {
            "status": component.status,
            "reason": component.reason,
            "quality_flag": meta.get("quality_flag"),
            "vendor_status": meta.get("vendor_status"),
            "basis": meta.get("basis"),
            "cache_key": component.cache_key,
            **_component_use_metadata(component),
        }
    return payload


def _component_use_metadata(component: _Component | None) -> dict[str, object]:
    meta = _component_meta(component) if component is not None else {}
    return {
        "fallback_mode": meta.get("fallback_mode"),
        "fallback_date": meta.get("fallback_date"),
        "formal_use_allowed": meta.get("formal_use_allowed"),
    }


def _build_charts(components: Mapping[str, _Component]) -> dict[str, object]:
    chart_sources: dict[str, object | None] = {}
    source_components: list[_Component | None] = []
    reasons: list[str] = []
    for source_key in ("choice_latest", "market_rates"):
        component = components.get(source_key)
        source_components.append(component)
        result = _component_result(component)
        allowed_series_ids = (
            MARKET_OVERVIEW_CHART_CHOICE_SERIES_IDS
            if source_key == "choice_latest"
            else MARKET_OVERVIEW_CHART_RATE_SERIES_IDS
        )
        if result:
            chart_sources[source_key], had_non_finite = _filter_chart_payload(
                result,
                allowed_series_ids=allowed_series_ids,
            )
            if had_non_finite:
                reasons.append(f"{source_key} contains non-finite numeric values")
        else:
            chart_sources[source_key] = None
        if component is None:
            reasons.append(f"{source_key} component not loaded")
        elif component.status != "ok":
            reasons.append(component.reason or f"{source_key} status={component.status}")

    available_count = sum(1 for payload in chart_sources.values() if payload is not None)
    status = (
        "unavailable"
        if available_count == 0
        else "degraded"
        if available_count < len(chart_sources)
        or bool(reasons)
        or any(component is None or component.status != "ok" for component in source_components)
        else "ok"
    )
    return {
        "status": status,
        "reason": "; ".join(dict.fromkeys(reasons)) or None,
        **chart_sources,
    }


def _filter_chart_payload(
    payload: Mapping[str, object],
    *,
    allowed_series_ids: frozenset[str],
) -> tuple[dict[str, object], bool]:
    series = payload.get("series")
    filtered_series: list[dict[str, object]] = []
    had_non_finite = False
    if isinstance(series, Sequence) and not isinstance(series, (str, bytes)):
        for item in series:
            if not isinstance(item, Mapping) or str(item.get("series_id") or "") not in allowed_series_ids:
                continue
            normalized, item_had_non_finite = _sanitize_chart_series_item(item)
            had_non_finite = had_non_finite or item_had_non_finite
            if normalized is not None:
                filtered_series.append(normalized)
    derived_spreads = payload.get("derived_spreads")
    normalized_spreads: dict[str, float | None] = {}
    if isinstance(derived_spreads, Mapping):
        for key, raw_value in derived_spreads.items():
            normalized_value = _number_or_none(raw_value)
            if raw_value is not None and normalized_value is None:
                had_non_finite = True
            normalized_spreads[str(key)] = normalized_value
    return (
        {
            "read_target": payload.get("read_target") or "duckdb",
            "series": filtered_series,
            "derived_spreads": normalized_spreads,
        },
        had_non_finite,
    )


def _sanitize_chart_series_item(
    item: Mapping[str, object],
) -> tuple[dict[str, object] | None, bool]:
    value = _number_or_none(item.get("value_numeric"))
    if value is None:
        return None, item.get("value_numeric") is not None

    normalized = dict(item)
    normalized["value_numeric"] = value
    had_non_finite = False
    if "latest_change" in normalized:
        raw_change = normalized.get("latest_change")
        normalized_change = _number_or_none(raw_change)
        if raw_change is not None and normalized_change is None:
            had_non_finite = True
        normalized["latest_change"] = normalized_change

    recent_points = normalized.get("recent_points")
    if isinstance(recent_points, Sequence) and not isinstance(recent_points, (str, bytes)):
        finite_recent_points: list[dict[str, object]] = []
        for point in recent_points:
            if not isinstance(point, Mapping):
                continue
            point_value = _number_or_none(point.get("value_numeric"))
            if point_value is None:
                if point.get("value_numeric") is not None:
                    had_non_finite = True
                continue
            finite_recent_points.append({**dict(point), "value_numeric": point_value})
        normalized["recent_points"] = finite_recent_points
    return normalized, had_non_finite


def _build_gate(
    refresh_receipt_health: MacroToolkitRefreshReceiptHealth,
    macro_component: _Component | None,
) -> dict[str, object]:
    conclusion = dict(_mapping_or_empty(_component_result(macro_component).get("conclusion")))
    recommended_action = str(conclusion.get("recommended_action") or "")
    if any(script_name in recommended_action for script_name in ("signal_aggregator", "risk_monitor")):
        conclusion["recommended_action"] = "复核宏观信号与风险监测结果，再形成今日判断。"
    evidence = {
        "receipt_status": refresh_receipt_health.status,
        "receipt_generated_at": refresh_receipt_health.generated_at,
        "receipt_age_hours": refresh_receipt_health.running_age_hours,
        "missing_field_count": len(refresh_receipt_health.missing_fields),
    }
    recovery_action = refresh_receipt_health.recovery_action()
    health_warnings = refresh_receipt_health.analysis_warnings()
    receipt_reason = health_warnings[0] if health_warnings else "刷新回执未通过完整性校验"
    if not refresh_receipt_health.ready:
        # Cached core payloads can still contain raw technical exceptions. Keep
        # operational details in the receipt and expose only the use boundary.
        conclusion = {
            "stance": "暂停形成今日判断",
            "tone": "missing",
            "summary": receipt_reason,
            "recommended_action": recovery_action,
        }
        return {
            "level": "blocked",
            "reason_code": (
                "refresh_receipt_abandoned"
                if refresh_receipt_health.status == "abandoned"
                else "refresh_receipt_blocked"
            ),
            "human_reason": receipt_reason,
            "recovery_action": recovery_action,
            "conclusion": conclusion,
            "evidence": evidence,
            "issues": [],
        }
    if macro_component is None or macro_component.status == "unavailable":
        return {
            "level": "blocked",
            "reason_code": "source_unavailable",
            "human_reason": "核心宏观分析暂不可用。",
            "recovery_action": "打开宏观工具核验数据后，重新读取总览。",
            "conclusion": {"stance": "暂停形成今日判断", "tone": "missing"},
            "evidence": evidence,
            "issues": [],
        }
    issues = _build_gate_issues(_component_result(macro_component))
    if macro_component.status == "degraded" or issues:
        if not issues:
            issues = [{
                "key": "core_quality",
                "label": "核心分析质量待复核",
                "reason": "核心分析未通过全部质量校验，当前响应未提供更细的原因。",
                "impact": "当前结论需结合来源证据复核。",
                "route": "/macro-toolkit",
            }]
        directional_missing = any(item["key"] == "directional_coverage" for item in issues)
        return {
            "level": "review",
            "reason_code": "directional_inputs_missing" if directional_missing else "quality_warning",
            "human_reason": issues[0]["reason"],
            "recovery_action": "按复核项核验来源或更新材料后，重新读取总览。",
            "conclusion": conclusion,
            "evidence": evidence,
            "issues": issues,
        }
    return {
        "level": "ok",
        "reason_code": "none",
        "human_reason": "刷新回执与核心组件均通过当前读取校验。",
        "recovery_action": "无需操作",
        "conclusion": conclusion,
        "evidence": evidence,
        "issues": [],
    }


def _build_gate_issues(result: Mapping[str, object]) -> list[dict[str, str]]:
    """Expose bounded business reasons without forwarding arbitrary warning text."""
    issues: list[dict[str, str]] = []
    basis = _mapping_or_empty(_mapping_or_empty(result.get("conclusion")).get("basis"))
    coverage = _mapping_or_empty(basis.get("directional_coverage"))
    if coverage and coverage.get("status") != "complete":
        labels = {"liquidity": "流动性", "risk_appetite": "风险偏好", "credit": "信用"}
        missing = [labels[key] for key in _sequence_or_empty(coverage.get("missing_keys")) if key in labels]
        issues.append({
            "key": "directional_coverage",
            "label": "方向信号不完整",
            "reason": f"{'、'.join(missing)}方向信号缺失或无效。" if missing else "方向信号尚未齐备。",
            "impact": "暂不形成完整的宏观方向判断；已取得的信号仍保留供核验。",
            "route": "/macro-toolkit",
        })
    stock = _mapping_or_empty(result.get("choice_stock_refresh"))
    for key, label, date_key in (
        ("daily_observation", "股票行情", "latest_trade_date"),
        ("factor_snapshot", "股票因子", "as_of_date"),
    ):
        source = _mapping_or_empty(stock.get(key))
        if source.get("freshness_status") not in {"lagging", "stale", "missing", "unknown", "unavailable"}:
            continue
        observed = _parse_iso_date(source.get(date_key))
        issues.append({
            "key": f"stock_{key}",
            "label": f"{label}输入待更新",
            "reason": f"{label}最近观测日为 {observed.isoformat()}。" if observed else f"{label}尚无可核验的观测日期。",
            "impact": "影响股票策略及相关风险分析的时效，不代表宏观方向信号缺失。",
            "route": "/macro-toolkit",
        })
    models = [
        item for item in _sequence_or_empty(result.get("model_readiness"))
        if isinstance(item, Mapping) and item.get("readiness") in {
            "stale", "degraded", "missing_output", "unknown", "registered_only",
        }
    ]
    if models:
        issues.append({
            "key": "model_artifacts",
            "label": "模型产物待复核",
            "reason": f"{len(models)} 项模型产物尚未通过当前完整性或时效校验。",
            "impact": "影响附属模型材料的当前使用；宏观方向依据单独列示。",
            "route": "/macro-toolkit#macro-toolkit-model-readiness-detail",
        })
    elif _mapping_or_empty(result.get("hason_strategy")).get("status") in {"degraded", "unavailable"}:
        issues.append({
            "key": "strategy_materials",
            "label": "策略研究材料待复核",
            "reason": "策略研究材料尚未通过当前完整性或时效校验。",
            "impact": "相关材料仅供保留观察，不应作为当前完整策略依据。",
            "route": "/macro-toolkit",
        })
    report = _mapping_or_empty(result.get("report_bundle"))
    if _sequence_or_empty(report.get("warnings")):
        issues.append({
            "key": "research_boundary",
            "label": "研究材料使用限制",
            "reason": "研究材料含使用限制，材料日、曲线日与账户报告日需分别核对。",
            "impact": "材料仅供研究观察，不构成正式指标、限额依据或交易信号。",
            "route": "/macro-toolkit",
        })
    return issues


def _build_dates(
    components: Mapping[str, _Component],
    *,
    tape: Mapping[str, object] | None,
) -> dict[str, object]:
    today = date.today()
    surfaces = [
        _surface_date(
            key="rates_formal",
            source="market_rates",
            component=components.get("market_rates"),
            latest=_latest_series_date(components.get("market_rates")),
            today=today,
        ),
        _surface_date(
            key="choice_latest",
            source="choice_latest",
            component=components.get("choice_latest"),
            latest=_latest_series_date(components.get("choice_latest")),
            today=today,
        ),
        _surface_date(
            key="macro_analysis",
            source="macro_analysis_core",
            component=components.get("macro_analysis_core"),
            latest=_result_date(components.get("macro_analysis_core")),
            today=today,
        ),
        _surface_date(
            key="news",
            source="choice_news",
            component=components.get("choice_news"),
            latest=_latest_news_date(components.get("choice_news")),
            today=today,
            basis="received_at",
        ),
        _surface_date(
            key="strategy",
            source="macro_strategy_summaries",
            component=components.get("macro_strategy_summaries"),
            latest=_result_date(components.get("macro_strategy_summaries")),
            today=today,
        ),
    ]
    trade_dates = [
        str(slot["trade_date"])
        for slot in _sequence_or_empty(tape.get("slots") if isinstance(tape, Mapping) else None)
        if isinstance(slot, Mapping) and slot.get("trade_date")
    ]
    normalized_trade_dates = [item.isoformat() for value in trade_dates if (item := _parse_iso_date(value)) is not None]
    tape_span = {
        "earliest": min(normalized_trade_dates) if normalized_trade_dates else None,
        "latest": max(normalized_trade_dates) if normalized_trade_dates else None,
    }
    available_count = sum(1 for surface in surfaces if surface["latest"] is not None)
    degraded = any(str(surface["status"]) != "ok" for surface in surfaces)
    return {
        "status": "unavailable" if available_count == 0 else "degraded" if degraded else "ok",
        "surfaces": surfaces,
        "tape_span": tape_span,
        "computed_on": today.isoformat(),
        "date_basis": "calendar_day",
    }


def _surface_date(
    *,
    key: str,
    source: str,
    component: _Component | None,
    latest: str | None,
    today: date,
    basis: str = "trade_date",
) -> dict[str, object]:
    latest_date = _parse_iso_date(latest)
    return {
        "key": key,
        "source": source,
        "status": component.status if component is not None else "unavailable",
        "reason": component.reason if component is not None else "component not loaded",
        "latest": latest_date.isoformat() if latest_date is not None else None,
        "age_days": max(0, (today - latest_date).days) if latest_date is not None else None,
        "basis": basis,
    }


def _build_tape(components: Mapping[str, _Component]) -> dict[str, object]:
    choice_component = components.get("choice_latest")
    rates_component = components.get("market_rates")
    choice_points = _choice_points(choice_component)
    rates_points = _choice_points(rates_component)
    slots: list[dict[str, object]] = []
    for slot in MARKET_OVERVIEW_TAPE_SLOTS:
        component = rates_component if slot.prefer == "rates" else choice_component
        source_points = rates_points if slot.prefer == "rates" else choice_points
        if component is None or component.status == "unavailable":
            reason = component.reason if component is not None else f"{slot.prefer} component not loaded"
            slots.append(_unavailable_tape_slot(slot, reason))
            continue
        point = _latest_choice_macro_point(
            source_points,
            slot.key,
            aliases_by_field={slot.key: slot.aliases},
            allowed_units=None,
        )
        if point is None:
            slots.append(_unresolved_tape_slot(slot, component))
            continue
        change_point = None
        if slot.change_key and slot.change_aliases:
            change_point = _latest_choice_macro_point(
                choice_points,
                slot.change_key,
                aliases_by_field={slot.change_key: slot.change_aliases},
                allowed_units=None,
            )
        raw_value = point.value_numeric
        value = _number_or_none(raw_value)
        raw_change = change_point.value_numeric if change_point is not None else point.latest_change
        change = _number_or_none(raw_change)
        change_unit = change_point.unit if change_point is not None else point.unit
        non_finite_value = value is None
        non_finite_change = raw_change is not None and change is None
        point_status = (
            "unavailable"
            if non_finite_value
            else "degraded"
            if component.status != "ok" or point.quality_flag != "ok" or non_finite_change
            else "ok"
        )
        point_reason = (
            "market value is non-finite"
            if non_finite_value
            else "market change is non-finite"
            if non_finite_change
            else component.reason
            if component.status != "ok"
            else f"quality_flag={point.quality_flag}"
            if point.quality_flag != "ok"
            else None
        )
        slots.append(
            {
                "key": slot.key,
                "label": slot.label,
                "kind": slot.kind,
                "status": point_status,
                "reason": point_reason,
                "value": value,
                "unit": point.unit,
                "change": change,
                "change_unit": change_unit,
                "trade_date": _normalized_iso_date(point.trade_date),
                "series_id": point.series_id,
                "series_name": point.series_name,
                "vendor": point.vendor_name,
                "basis": _component_meta(component).get("basis"),
                **_component_use_metadata(component),
                "quality_flag": "error" if non_finite_value else "warning" if non_finite_change else point.quality_flag,
                "tone_hint": _tone_hint(change),
            }
        )
        if slot.key == "dr007" and (
            point.vendor_name == "public_repo_rate_query"
            or "not the exact" in str(point.policy_note or "")
        ):
            slots[-1].update(
                label="FDR007（DR007代理参考）", status="degraded", formal_use_allowed=False,
                basis="analytical", reason="实际来源为FDR007定盘利率，不能替代DR007加权利率判断。",
            )
    status = (
        "unavailable"
        if all(slot["status"] == "unavailable" for slot in slots)
        else "degraded"
        if any(slot["status"] != "ok" for slot in slots)
        else "ok"
    )
    return {"status": status, "reason": None, "slots": slots}


def _unavailable_tape_slot(
    slot: MarketOverviewTapeSlot,
    reason: str | None,
) -> dict[str, object]:
    return {
        "key": slot.key,
        "label": slot.label,
        "kind": slot.kind,
        "status": "unavailable",
        "reason": reason,
        "value": None,
        "unit": None,
        "change": None,
        "change_unit": None,
        "trade_date": None,
        "series_id": None,
        "series_name": None,
        "vendor": None,
        "basis": None,
        **_component_use_metadata(None),
        "quality_flag": "error",
        "tone_hint": "unavailable",
    }


def _unresolved_tape_slot(
    slot: MarketOverviewTapeSlot,
    component: _Component,
) -> dict[str, object]:
    return {
        "key": slot.key,
        "label": slot.label,
        "kind": slot.kind,
        "status": "unresolved",
        "reason": "no configured alias landed on the latest valid date",
        "value": None,
        "unit": None,
        "change": None,
        "change_unit": None,
        "trade_date": None,
        "series_id": None,
        "series_name": None,
        "vendor": None,
        "basis": _component_meta(component).get("basis"),
        **_component_use_metadata(component),
        "quality_flag": "warning",
        "tone_hint": "unavailable",
    }


def _build_pulse(macro_component: _Component | None) -> dict[str, object]:
    if macro_component is None or macro_component.status == "unavailable":
        reason = macro_component.reason if macro_component is not None else "宏观脉冲数据未加载"
        return {
            "status": "unavailable",
            "reason": reason,
            "items": [_unavailable_pulse_item(key, label, reason) for key, label in _PULSE_SLOTS],
        }
    indicators = {
        str(item.get("key")): item
        for item in _sequence_or_empty(_component_result(macro_component).get("indicators"))
        if isinstance(item, Mapping) and item.get("key")
    }
    items: list[dict[str, object]] = []
    missing = False
    for key, label in _PULSE_SLOTS:
        indicator = indicators.get(key)
        if indicator is None:
            missing = True
            items.append(
                _unavailable_pulse_item(
                    key,
                    label,
                    "本地宏观序列暂不可用",
                )
            )
            continue
        quality = str(indicator.get("quality") or "warning")
        unit = str(indicator.get("unit") or "").strip() or None
        unit = None if unit == "unknown" else unit
        previous_value = _number_or_none(indicator.get("previous_value"))
        latest_value = _number_or_none(indicator.get("latest_value"))
        change = _number_or_none(indicator.get("change"))
        non_finite_latest = indicator.get("latest_value") is not None and latest_value is None
        non_finite_auxiliary = any(
            indicator.get(field) is not None and normalized is None
            for field, normalized in (("previous_value", previous_value), ("change", change))
        )
        item_status = (
            "unavailable"
            if latest_value is None
            else "ok"
            if quality == "ok" and unit is not None and not non_finite_auxiliary
            else "degraded"
        )
        items.append(
            {
                "key": key,
                "label": label,
                "status": item_status,
                "reason": "宏观序列数值非有限" if non_finite_latest else "本地宏观序列暂不可用" if item_status == "unavailable" else "宏观序列变动值非有限" if non_finite_auxiliary else "单位未确认" if unit is None else None if item_status == "ok" else f"quality={quality}",
                "previous_value": previous_value,
                "latest_value": latest_value,
                "change": change,
                "change_kind": "absolute",
                "unit": unit,
                "change_unit": "百分点" if unit in {"%", "pct"} else "点" if unit in {"index", "point", "点"} else unit,
                "latest_date": indicator.get("latest_date"),
                "source": indicator.get("source"),
            }
        )
    return {
        "status": "unavailable" if all(item["status"] == "unavailable" for item in items) else "degraded" if missing or any(item["status"] != "ok" for item in items) else "ok",
        "reason": (
            "部分本地宏观序列暂不可用"
            if missing
            else macro_component.reason
        ),
        "items": items,
    }


def _unavailable_pulse_item(key: str, label: str, reason: str | None) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "status": "unavailable",
        "reason": reason,
        "previous_value": None,
        "latest_value": None,
        "change": None,
        "change_kind": "absolute",
        "unit": None,
        "change_unit": None,
        "latest_date": None,
        "source": None,
    }


def _build_crisis(macro_component: _Component | None) -> dict[str, object]:
    if macro_component is None or macro_component.status == "unavailable":
        return _empty_crisis_partition(
            status="unavailable",
            reason=(
                macro_component.reason
                if macro_component is not None
                else "macro_analysis_full component not loaded"
            ),
        )
    capability = next(
        (
            item
            for item in _sequence_or_empty(_component_result(macro_component).get("capability_results"))
            if isinstance(item, Mapping) and item.get("key") == "crisis_score_cn"
        ),
        None,
    )
    if not isinstance(capability, Mapping):
        return _empty_crisis_partition(
            status="degraded",
            reason="macro_analysis_full does not include crisis_score_cn in capability_results",
        )

    result = _mapping_or_empty(capability.get("result"))
    data_status = _crisis_data_status(result.get("data_status"))
    dependency_gate = _crisis_dependency_gate(capability.get("dependency_gate"))
    # A dependency gate is only attached by the upstream capability when the
    # dependency is blocked. Unknown or malformed gate states therefore remain
    # fail-closed until the contract explicitly defines a healthy state.
    dependency_blocked = dependency_gate is not None
    history = _crisis_history(result.get("score_history"))
    score_trend, score_trends, trend_contract_valid = _crisis_trends(result)
    risk_gate, risk_gate_contract_valid = _crisis_risk_gate(
        result.get("risk_gate"),
        data_status=data_status,
        dependency_gate=dependency_gate,
    )

    # The card score is a two-decimal presentation field. Preserve the formal
    # result precision when it is present, but never reveal raw score through a
    # capability dependency gate that deliberately suppressed presentation.
    if dependency_blocked or data_status == "unavailable":
        score = None
    elif "crisis_score" in result:
        score = _number_or_none(result.get("crisis_score"))
    else:
        score = _number_or_none(capability.get("score"))

    # Explicit null is meaningful: only a genuinely absent percentile field
    # may use the latest history point as a compatibility fallback.
    if "percentile" in result:
        percentile = _number_or_none(result.get("percentile"))
    else:
        percentile = history[-1]["percentile"] if history else None
    current_available = score is not None and data_status != "unavailable" and not dependency_blocked
    if not current_available:
        percentile = None
        if risk_gate["eligible"] or risk_gate["triggered"]:
            risk_gate = {
                **risk_gate,
                "eligible": False,
                "triggered": False,
                "reason_code": "crisis_score_current_unavailable",
            }
            risk_gate_contract_valid = False

    report_date = _normalized_iso_date(result.get("report_date"))
    requested_report_date = _normalized_iso_date(result.get("requested_report_date"))
    rule_version = str(result.get("rule_version") or "").strip() or None
    warnings = _crisis_string_list(
        [
            *_sequence_or_empty(result.get("warnings")),
            *_sequence_or_empty(capability.get("warnings")),
        ]
    )
    input_evidence = _crisis_input_evidence(
        result.get("input_evidence")
        if isinstance(result.get("input_evidence"), Mapping)
        else capability.get("input_evidence")
    )
    date_contract_valid = report_date is not None and requested_report_date is not None
    status = (
        "ok"
        if data_status == "complete"
        and current_available
        and not dependency_blocked
        and risk_gate_contract_valid
        and trend_contract_valid
        and score_trend["window_points"] > 0
        and date_contract_valid
        and rule_version is not None
        else "degraded"
    )
    return {
        "status": status,
        "reason": _crisis_reason(
            status=status,
            data_status=data_status,
            dependency_gate=dependency_gate,
            risk_gate_contract_valid=risk_gate_contract_valid,
            trend_contract_valid=trend_contract_valid,
            trend_window_points=int(score_trend["window_points"]),
            date_contract_valid=date_contract_valid,
            rule_version=rule_version,
        ),
        "report_date": report_date,
        "requested_report_date": requested_report_date,
        "rule_version": rule_version,
        "score": score,
        "regime": result.get("regime") if current_available else None,
        "current_available": current_available,
        "history_only": bool(history) and not current_available,
        "percentile": percentile,
        "data_status": data_status,
        "score_trend": score_trend,
        "score_trends": score_trends,
        "score_history": history,
        "warnings": warnings,
        "available_component_count": _integer_or_none(
            result.get("available_component_count")
        ),
        "component_count": _integer_or_none(result.get("component_count")),
        "input_evidence": input_evidence,
        "dependency_gate": dependency_gate,
        "delta": {
            "window_points": score_trend["window_points"],
            "score_delta": score_trend["score_change"],
            "percentile_delta": score_trend["percentile_change"],
        },
        "risk_gate": risk_gate,
    }


def _empty_crisis_partition(*, status: str, reason: str | None) -> dict[str, object]:
    return {
        "status": status,
        "reason": reason,
        "report_date": None,
        "requested_report_date": None,
        "rule_version": None,
        "score": None,
        "current_available": False,
        "history_only": False,
        "regime": None,
        "percentile": None,
        "data_status": "unavailable",
        "score_trend": _empty_crisis_trend(),
        "score_trends": [],
        "score_history": [],
        "warnings": [],
        "available_component_count": None,
        "component_count": None,
        "input_evidence": _empty_crisis_input_evidence(),
        "dependency_gate": None,
        "delta": _empty_crisis_delta(),
        "risk_gate": _empty_crisis_risk_gate(),
    }


def _crisis_data_status(value: object) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in {"complete", "degraded", "unavailable"} else "degraded"


def _crisis_trends(
    result: Mapping[str, object],
) -> tuple[_CrisisTrend, list[_CrisisTrend], bool]:
    raw_plural = result.get("score_trends")
    plural_declared = "score_trends" in result
    raw_plural_items = list(_sequence_or_empty(raw_plural))
    raw_trends = [
        item
        for item in raw_plural_items
        if isinstance(item, Mapping)
    ]
    legacy = result.get("score_trend")
    if not plural_declared and isinstance(legacy, Mapping):
        raw_trends = [legacy]

    normalized: list[_CrisisTrend] = []
    if plural_declared:
        contract_valid = (
            isinstance(raw_plural, (list, tuple))
            and len(raw_plural_items) == len(raw_trends) == 2
            and [
                _integer_or_zero(item.get("requested_window_points"))
                for item in raw_trends
            ]
            == [20, 60]
        )
    else:
        contract_valid = bool(raw_trends)
    for raw in raw_trends:
        trend, valid = _crisis_trend(raw)
        normalized.append(trend)
        contract_valid = contract_valid and valid

    legacy_trend = _mapping_or_empty(legacy)
    if legacy_trend:
        primary, primary_valid = _crisis_trend(legacy_trend)
        if plural_declared:
            primary_valid = (
                primary_valid
                and bool(normalized)
                and primary == normalized[0]
            )
    else:
        primary = next(
            (
                item
                for item in normalized
                if item["requested_window_points"] == 20
            ),
            normalized[0] if normalized else _empty_crisis_trend(),
        )
        primary_valid = bool(normalized) and primary["window_points"] > 0
    return primary, normalized, contract_valid and primary_valid


def _crisis_trend(raw: Mapping[str, object]) -> tuple[_CrisisTrend, bool]:
    requested_window_points = _integer_or_zero(raw.get("requested_window_points"))
    window_points = _integer_or_zero(raw.get("window_points"))
    direction = str(raw.get("direction") or "").strip().lower()
    direction_valid = direction in {"rising", "falling", "flat", "insufficient"}
    if not direction_valid:
        direction = "insufficient"
    trend: _CrisisTrend = {
        "requested_window_points": requested_window_points,
        "window_points": window_points,
        "start_date": _normalized_iso_date(raw.get("start_date")),
        "end_date": _normalized_iso_date(raw.get("end_date")),
        "start_score": _number_or_none(raw.get("start_score")),
        "end_score": _number_or_none(raw.get("end_score")),
        "score_change": _number_or_none(raw.get("score_change")),
        "start_percentile": _number_or_none(raw.get("start_percentile")),
        "end_percentile": _number_or_none(raw.get("end_percentile")),
        "percentile_change": _number_or_none(raw.get("percentile_change")),
        "direction": direction,
    }
    window_fields_valid = (
        window_points == 0
        or (
            trend["start_date"] is not None
            and trend["end_date"] is not None
            and trend["start_score"] is not None
            and trend["end_score"] is not None
        )
    )
    return trend, requested_window_points > 0 and direction_valid and window_fields_valid


def _empty_crisis_trend() -> _CrisisTrend:
    return {
        "requested_window_points": 20,
        "window_points": 0,
        "start_date": None,
        "end_date": None,
        "start_score": None,
        "end_score": None,
        "score_change": None,
        "start_percentile": None,
        "end_percentile": None,
        "percentile_change": None,
        "direction": "insufficient",
    }


def _crisis_history(value: object) -> list[_CrisisHistoryPoint]:
    history: list[_CrisisHistoryPoint] = []
    for item in _sequence_or_empty(value):
        if not isinstance(item, Mapping):
            continue
        point_date = _normalized_iso_date(item.get("date"))
        score = _number_or_none(item.get("crisis_score"))
        if point_date is None or score is None:
            continue
        history.append(
            {
                "date": point_date,
                "crisis_score": score,
                "percentile": _number_or_none(item.get("percentile")),
                "available_component_count": _integer_or_none(
                    item.get("available_component_count")
                ),
                "component_count": _integer_or_none(item.get("component_count")),
                "available_weight": _number_or_none(item.get("available_weight")),
                "data_status": str(item.get("data_status") or "").strip() or None,
            }
        )
    return history[-MARKET_OVERVIEW_CRISIS_HISTORY_LIMIT:]


def _crisis_dependency_gate(value: object) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    status = str(value.get("status") or "").strip().lower()
    reason_code = str(value.get("reason_code") or "").strip()
    return {
        "status": "blocked" if status == "blocked" else "unknown",
        "blocked_by": _crisis_string_list(value.get("blocked_by")),
        "reason_code": reason_code or "crisis_score_dependency_status_unknown",
    }


def _crisis_risk_gate(
    value: object,
    *,
    data_status: str,
    dependency_gate: Mapping[str, object] | None,
) -> tuple[dict[str, object], bool]:
    raw = _mapping_or_empty(value)
    threshold = _number_or_none(raw.get("threshold"))
    reason_code = str(raw.get("reason_code") or "").strip()
    eligible_is_bool = isinstance(raw.get("eligible"), bool)
    triggered_is_bool = isinstance(raw.get("triggered"), bool)
    contract_valid = (
        bool(raw)
        and eligible_is_bool
        and triggered_is_bool
        and threshold is not None
        and threshold > 0
        and bool(reason_code)
    )
    source_eligible = raw.get("eligible") is True
    source_triggered = raw.get("triggered") is True
    inconsistent = source_triggered and not source_eligible
    if isinstance(dependency_gate, Mapping):
        reason_code = str(
            dependency_gate.get("reason_code") or "crisis_score_dependency_blocked"
        )
        eligible = False
        triggered = False
    elif data_status != "complete":
        reason_code = "crisis_score_data_not_complete"
        eligible = False
        triggered = False
    elif not contract_valid:
        reason_code = "crisis_score_risk_gate_contract_invalid"
        eligible = False
        triggered = False
    elif inconsistent:
        reason_code = "crisis_score_risk_gate_inconsistent"
        eligible = False
        triggered = False
        contract_valid = False
    else:
        eligible = source_eligible
        triggered = source_triggered

    return (
        {
            "eligible": eligible,
            "triggered": triggered,
            "threshold": (
                threshold
                if threshold is not None and threshold > 0
                else CRISIS_SCORE_RISK_GATE_THRESHOLD
            ),
            "reason_code": reason_code,
        },
        contract_valid and not inconsistent,
    )


def _crisis_input_evidence(value: object) -> dict[str, object]:
    raw = _mapping_or_empty(value)
    inputs: list[dict[str, object]] = []
    for item in _sequence_or_empty(raw.get("inputs")):
        if not isinstance(item, Mapping):
            continue
        field = str(item.get("field") or "").strip()
        if not field:
            continue
        stale = item.get("stale")
        inputs.append(
            {
                "field": field,
                "label": str(item.get("label") or field),
                "aliases": _crisis_string_list(item.get("aliases")),
                "warning": str(item.get("warning") or "").strip() or None,
                "required": item.get("required") is True,
                "available": item.get("available") is True,
                "row_count": _integer_or_zero(item.get("row_count")),
                "latest_date": _normalized_iso_date(item.get("latest_date")),
                "series_id": str(item.get("series_id") or "").strip() or None,
                "source": str(item.get("source") or "").strip() or None,
                "stale": stale if isinstance(stale, bool) else None,
                "stale_days": _integer_or_none(item.get("stale_days")),
            }
        )
    return {
        "inputs": inputs,
        "missing_inputs": _crisis_string_list(raw.get("missing_inputs")),
        "stale_inputs": _crisis_string_list(raw.get("stale_inputs")),
        "sources": _crisis_string_list(raw.get("sources")),
        "latest_dates": [
            normalized
            for item in _crisis_string_list(raw.get("latest_dates"))
            if (normalized := _normalized_iso_date(item)) is not None
        ],
    }


def _empty_crisis_input_evidence() -> dict[str, object]:
    return {
        "inputs": [],
        "missing_inputs": [],
        "stale_inputs": [],
        "sources": [],
        "latest_dates": [],
    }


def _crisis_string_list(value: object) -> list[str]:
    values = value if isinstance(value, (list, tuple, set)) else ()
    resolved: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if text and text not in resolved:
            resolved.append(text)
    return resolved


def _crisis_reason(
    *,
    status: str,
    data_status: str,
    dependency_gate: Mapping[str, object] | None,
    risk_gate_contract_valid: bool,
    trend_contract_valid: bool,
    trend_window_points: int,
    date_contract_valid: bool,
    rule_version: str | None,
) -> str | None:
    if status == "ok":
        return None
    if dependency_gate is not None:
        return f"crisis dependency gate blocked: {dependency_gate.get('reason_code')}"
    if data_status != "complete":
        return f"crisis data_status={data_status}"
    if not risk_gate_contract_valid:
        return "crisis risk_gate contract is missing, invalid, or inconsistent"
    if not trend_contract_valid or trend_window_points <= 0:
        return "crisis score trend contract is unavailable or invalid"
    if not date_contract_valid:
        return "crisis report date contract is unavailable or invalid"
    if rule_version is None:
        return "crisis rule_version is unavailable"
    return "crisis result is degraded"


def _empty_crisis_delta() -> dict[str, object]:
    return {"window_points": 0, "score_delta": None, "percentile_delta": None}


def _empty_crisis_risk_gate() -> dict[str, object]:
    return {
        "eligible": False,
        "triggered": False,
        "threshold": CRISIS_SCORE_RISK_GATE_THRESHOLD,
        "reason_code": "crisis_score_data_not_complete",
    }


def _build_signals(macro_component: _Component | None) -> dict[str, object]:
    if macro_component is None or macro_component.status == "unavailable":
        return {
            "status": "unavailable",
            "reason": (
                macro_component.reason if macro_component is not None else "macro_analysis_core component not loaded"
            ),
            "cards": [],
        }
    cards: list[dict[str, object]] = []
    had_non_finite = False
    for card in _sequence_or_empty(_component_result(macro_component).get("signal_cards")):
        if not isinstance(card, Mapping):
            continue
        row = {
            **dict(card),
            "kind": "ops_status" if card.get("key") == "outputs" else "market_signal",
        }
        if "score" in row:
            raw_score = row.get("score")
            normalized_score = _number_or_none(raw_score)
            if raw_score is not None and normalized_score is None:
                had_non_finite = True
            row["score"] = normalized_score
        cards.append(row)
    return {
        "status": "ok" if macro_component.status == "ok" and not had_non_finite else "degraded",
        "reason": (
            "signal cards contain non-finite numeric values"
            if had_non_finite
            else macro_component.reason
        ),
        "cards": cards,
    }


def _build_news(component: _Component | None) -> dict[str, object]:
    if component is None or component.status == "unavailable":
        return {
            "status": "unavailable",
            "reason": component.reason if component is not None else "choice_news component not loaded",
            "sample": _empty_news_sample(),
            "granularity": {"datetime_rows": 0, "date_only_rows": 0},
            "density": _empty_news_density(),
            "latest": [],
            "compare": _empty_news_compare(),
        }
    result = _component_result(component)
    events = [item for item in _sequence_or_empty(result.get("events")) if isinstance(item, Mapping)]
    topic_cells: dict[str, list[int]] = {}
    datetime_rows = 0
    date_only_rows = 0
    latest_timestamp: datetime | None = None
    normalized_events: list[tuple[datetime, Mapping[str, object]]] = []
    for event in events:
        received_at = _parse_timestamp(event.get("received_at"))
        if received_at is None:
            continue
        local = received_at.astimezone(MARKET_OVERVIEW_TIMEZONE)
        normalized_events.append((local, event))
        if latest_timestamp is None or local > latest_timestamp:
            latest_timestamp = local
        group_id = str(event.get("group_id") or "")
        if group_id in MARKET_OVERVIEW_NEWS_DATE_ONLY_GROUPS and _is_midnight(local):
            date_only_rows += 1
            continue
        datetime_rows += 1
        topic_key = str(event.get("topic_code") or "unclassified")
        cells = topic_cells.setdefault(topic_key, [0] * (24 // MARKET_OVERVIEW_NEWS_BUCKET_HOURS))
        cells[local.hour // MARKET_OVERVIEW_NEWS_BUCKET_HOURS] += 1
    topics = [{"key": key, "label": key, "cells": cells} for key, cells in sorted(topic_cells.items())]
    compare = _mapping_or_empty(result.get("compare"))
    review_items = _sequence_or_empty(compare.get("review_needed"))[:5]
    latest_events = [
        _news_event_summary(event, received_at=received_at)
        for received_at, event in sorted(normalized_events, key=lambda item: item[0], reverse=True)[:3]
    ]
    latest_received_at = latest_timestamp.isoformat() if latest_timestamp is not None else None
    stale_days = max(0, (date.today() - latest_timestamp.date()).days) if latest_timestamp is not None else None
    return {
        "status": "ok" if component.status == "ok" else "degraded",
        "reason": component.reason,
        "sample": {
            "requested": MARKET_OVERVIEW_NEWS_LIMIT,
            "returned": len(events),
            "total_rows": _integer_or_zero(result.get("total_rows")),
            "excluded_future_rows": _integer_or_zero(result.get("excluded_future_rows")),
            "latest_received_at": latest_received_at,
            "stale_days": stale_days,
        },
        "granularity": {"datetime_rows": datetime_rows, "date_only_rows": date_only_rows},
        "density": {
            "tz": "Asia/Shanghai",
            "bucket_hours": MARKET_OVERVIEW_NEWS_BUCKET_HOURS,
            "topics": topics,
            "max_count": max((max(cells) for cells in topic_cells.values()), default=0),
        },
        "latest": latest_events,
        "compare": {
            "same_direction": len(_sequence_or_empty(compare.get("same_direction"))),
            "conflicting": len(_sequence_or_empty(compare.get("conflicting"))),
            "review_needed": len(_sequence_or_empty(compare.get("review_needed"))),
            "candidate_scenarios": len(_sequence_or_empty(compare.get("candidate_scenarios"))),
            "review_items": [dict(item) for item in review_items if isinstance(item, Mapping)],
        },
    }


def _empty_news_sample() -> dict[str, object]:
    return {
        "requested": MARKET_OVERVIEW_NEWS_LIMIT,
        "returned": 0,
        "total_rows": 0,
        "excluded_future_rows": 0,
        "latest_received_at": None,
        "stale_days": None,
    }


def _empty_news_density() -> dict[str, object]:
    return {
        "tz": "Asia/Shanghai",
        "bucket_hours": MARKET_OVERVIEW_NEWS_BUCKET_HOURS,
        "topics": [],
        "max_count": 0,
    }


def _empty_news_compare() -> dict[str, object]:
    return {
        "same_direction": 0,
        "conflicting": 0,
        "review_needed": 0,
        "candidate_scenarios": 0,
        "review_items": [],
    }


def _news_event_summary(
    event: Mapping[str, object],
    *,
    received_at: datetime,
) -> dict[str, object]:
    return {
        "event_key": event.get("event_key"),
        "received_at": received_at.isoformat(),
        "topic_code": event.get("topic_code"),
        "group_id": event.get("group_id"),
        "summary": event.get("display_text") or event.get("payload_text"),
    }


def _build_actions(
    *,
    gate: Mapping[str, object] | None,
    dates: Mapping[str, object] | None,
    tape: Mapping[str, object] | None,
    crisis: Mapping[str, object] | None,
    news: Mapping[str, object] | None,
) -> dict[str, object]:
    items: list[dict[str, object]] = []
    if isinstance(gate, Mapping) and gate.get("level") == "blocked":
        items.append(
            {
                "priority": "P0",
                "key": "refresh_gate_blocked",
                "label": "恢复核心宏观分析" if gate.get("reason_code") == "source_unavailable" else "恢复宏观刷新并复核回执",
                "route": "/macro-toolkit",
                "basis": "analytical",
                "evidence": {
                    "reason_code": gate.get("reason_code"),
                    "receipt_status": _mapping_or_empty(gate.get("evidence")).get("receipt_status"),
                },
            }
        )
    if isinstance(gate, Mapping) and gate.get("level") == "review":
        for issue in _sequence_or_empty(gate.get("issues")):
            if not isinstance(issue, Mapping):
                continue
            items.append({
                "priority": "P1",
                "key": f"gate_review_{issue.get('key')}",
                "label": str(issue.get("label") or "复核宏观分析依据"),
                "route": str(issue.get("route") or "/macro-toolkit"),
                "basis": "analytical",
                "evidence": {"reason": issue.get("reason"), "impact": issue.get("impact")},
            })
    news_compare = _mapping_or_empty(news).get("compare")
    review_count = _integer_or_zero(
        news_compare.get("review_needed") if isinstance(news_compare, Mapping) else 0
    )
    if review_count > 0:
        items.append(
            {
                "priority": "P1",
                "key": "news_human_review",
                "label": "复核新闻事件的人工判断项",
                "route": "/news-events",
                "basis": "analytical",
                "evidence": {"review_needed": review_count},
            }
        )
    for slot in _sequence_or_empty(_mapping_or_empty(tape).get("slots")):
        if not isinstance(slot, Mapping) or slot.get("kind") != "rate":
            continue
        change_bp = _rate_change_bp(slot.get("change"), slot.get("change_unit"))
        if change_bp is None or abs(change_bp) < MARKET_OVERVIEW_RATE_ACTION_BP:
            continue
        items.append(
            {
                "priority": "P1",
                "key": f"rate_move_{slot.get('key')}",
                "label": f"核验 {slot.get('label')} 的大幅变动",
                "route": "/market-data",
                "basis": "analytical",
                "evidence": {"change_bp": change_bp, "threshold_bp": MARKET_OVERVIEW_RATE_ACTION_BP},
            }
        )
    if isinstance(crisis, Mapping):
        risk_gate = _mapping_or_empty(crisis.get("risk_gate"))
        eligible = risk_gate.get("eligible") is True
        triggered = risk_gate.get("triggered") is True
        if not eligible or triggered:
            items.append(
                {
                    "priority": "P2",
                    "key": "crisis_regime_review",
                    "label": (
                        "复核 Crisis Score 高风险状态"
                        if triggered
                        else "复核 Crisis Score 数据完整性"
                    ),
                    "route": "/macro-toolkit",
                    "basis": "analytical",
                    "evidence": {
                        "eligible": eligible,
                        "triggered": triggered,
                        "threshold": risk_gate.get("threshold"),
                        "reason_code": risk_gate.get("reason_code"),
                        "score": crisis.get("score"),
                        "regime": crisis.get("regime"),
                        "percentile": crisis.get("percentile"),
                        "data_status": crisis.get("data_status"),
                    },
                }
            )
    for surface in _sequence_or_empty(_mapping_or_empty(dates).get("surfaces")):
        if not isinstance(surface, Mapping):
            continue
        age_days = _number_or_none(surface.get("age_days"))
        if age_days is None or age_days < 5:
            continue
        items.append(
            {
                "priority": "P2",
                "key": f"surface_stale_{surface.get('key')}",
                "label": "核验 " + {
                    "rates_formal": "正式利率", "choice_latest": "市场行情",
                    "macro_analysis": "宏观分析", "news": "新闻", "strategy": "策略",
                }.get(str(surface.get("key")), "来源") + " 数据时效",
                "route": _surface_drill_route(str(surface.get("key") or "")),
                "basis": "analytical",
                "evidence": {"surface": surface.get("key"), "age_days": age_days},
            }
        )
    return {"status": "ok", "items": items}


def _surface_drill_route(key: str) -> str:
    if key == "news":
        return "/news-events"
    if key in {"macro_analysis", "strategy"}:
        return "/macro-toolkit"
    return "/market-data"


def _snapshot_quality_flag(
    components: Mapping[str, _Component],
    gate: Mapping[str, object] | None,
) -> QualityFlag:
    choice_unavailable = components.get("choice_latest", _missing_component()).status == "unavailable"
    rates_unavailable = components.get("market_rates", _missing_component()).status == "unavailable"
    if "choice_latest" in components and "market_rates" in components and choice_unavailable and rates_unavailable:
        return "error"
    if any(component.status != "ok" for component in components.values()):
        return "warning"
    if isinstance(gate, Mapping) and gate.get("level") != "ok":
        return "warning"
    return "ok"


def _snapshot_vendor_status(components: Mapping[str, _Component]) -> VendorStatus:
    statuses = [str(_component_meta(component).get("vendor_status") or "") for component in components.values()]
    if any(component.status == "unavailable" for component in components.values()) or "vendor_unavailable" in statuses:
        return "vendor_unavailable"
    if "vendor_stale" in statuses:
        return "vendor_stale"
    return "ok"


def _aggregate_lineage_value(
    components: Iterable[_Component],
    field: str,
    *,
    empty_value: str,
) -> tuple[str, int]:
    segments: list[str] = []
    seen: set[str] = set()
    for component in components:
        value = _component_meta(component).get(field)
        for raw_segment in str(value or "").split("__"):
            segment = raw_segment.strip()
            if segment and segment not in seen:
                seen.add(segment)
                segments.append(segment)
    if not segments:
        return empty_value, 0
    if len(segments) > 8:
        digest = hashlib.sha256("__".join(segments).encode("utf-8")).hexdigest()[:12]
        return f"sha256:{digest}", len(segments)
    return "__".join(segments), len(segments)


def _tables_used(components: Iterable[_Component]) -> list[str]:
    tables: list[str] = []
    for component in components:
        for table in _sequence_or_empty(_component_meta(component).get("tables_used")):
            name = str(table).strip()
            if name and name not in tables:
                tables.append(name)
    return tables


def _evidence_rows(components: Iterable[_Component]) -> int | None:
    values = [
        value
        for component in components
        if (value := _number_or_none(_component_meta(component).get("evidence_rows"))) is not None
    ]
    return int(sum(values)) if values else None


def _component_result(component: _Component | None) -> Mapping[str, object]:
    if component is None or component.envelope is None:
        return {}
    return _mapping_or_empty(component.envelope.get("result"))


def _component_meta(component: _Component) -> Mapping[str, object]:
    if component.envelope is None:
        return {}
    return _mapping_or_empty(component.envelope.get("result_meta"))


def _choice_points(component: _Component | None) -> list[ChoiceMacroLatestPoint]:
    points: list[ChoiceMacroLatestPoint] = []
    for item in _sequence_or_empty(_component_result(component).get("series")):
        if not isinstance(item, Mapping):
            continue
        try:
            points.append(ChoiceMacroLatestPoint.model_validate(item))
        except ValueError:
            continue
    return points


def _latest_series_date(component: _Component | None) -> str | None:
    dates = [
        normalized
        for point in _choice_points(component)
        if (normalized := _normalized_iso_date(point.trade_date)) is not None
    ]
    return max(dates) if dates else None


def _result_date(component: _Component | None) -> str | None:
    result = _component_result(component)
    for candidate in (result.get("as_of_date"), _component_meta(component).get("as_of_date") if component else None):
        normalized = _normalized_iso_date(candidate)
        if normalized is not None:
            return normalized
    return None


def _latest_news_date(component: _Component | None) -> str | None:
    timestamps = [
        timestamp.astimezone(MARKET_OVERVIEW_TIMEZONE).date().isoformat()
        for event in _sequence_or_empty(_component_result(component).get("events"))
        if isinstance(event, Mapping)
        if (timestamp := _parse_timestamp(event.get("received_at"))) is not None
    ]
    return max(timestamps) if timestamps else None


def _parse_iso_date(value: object) -> date | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _normalized_iso_date(value: object) -> str | None:
    parsed = _parse_iso_date(value)
    return parsed.isoformat() if parsed is not None else None


def _parse_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def _is_midnight(value: datetime) -> bool:
    return value.hour == 0 and value.minute == 0 and value.second == 0 and value.microsecond == 0


def _tone_hint(value: object) -> str:
    numeric = _number_or_none(value)
    if numeric is None:
        return "unavailable"
    if numeric > 0:
        return "up"
    if numeric < 0:
        return "down"
    return "flat"


def _rate_change_bp(change: object, unit: object) -> float | None:
    numeric = _number_or_none(change)
    if numeric is None:
        return None
    normalized_unit = str(unit or "").strip().lower()
    if normalized_unit in {"%", "pct", "percent", "percentage"}:
        return _number_or_none(pct_to_bp(numeric))
    return numeric


def _numeric_difference(last: object, first: object) -> float | None:
    last_number = _number_or_none(last)
    first_number = _number_or_none(first)
    if last_number is None or first_number is None:
        return None
    difference = _number_or_none(last_number - first_number)
    return round(difference, 4) if difference is not None else None


def _number_or_none(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        # Preserve float's conversion and rejection behavior for dynamic inputs;
        # the cast adds no runtime filter, including for buffer-like objects.
        converted = float(cast(str | bytes | bytearray | SupportsFloat | SupportsIndex, value))
    except (TypeError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def _integer_or_zero(value: object) -> int:
    numeric = _number_or_none(value)
    return int(numeric) if numeric is not None else 0


def _integer_or_none(value: object) -> int | None:
    numeric = _number_or_none(value)
    return int(numeric) if numeric is not None else None


def _mapping_or_empty(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _sequence_or_empty(value: object) -> Sequence[object]:
    return value if isinstance(value, (list, tuple)) else ()


def _missing_component() -> _Component:
    return _Component(
        name="missing",
        cache_key=None,
        envelope=None,
        status="unavailable",
        reason="component not loaded",
    )
