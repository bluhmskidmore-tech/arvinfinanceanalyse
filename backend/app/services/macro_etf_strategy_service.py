from __future__ import annotations

import json
import math
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

from backend.app.core_finance.macro.dual_frequency_equity import (
    build_dual_frequency_equity_snapshot,
)
from backend.app.core_finance.macro.macro_etf_strategy import (
    DEFAULT_CONFIG,
    DEFAULT_MACRO_STATE,
    build_macro_etf_strategy_snapshot,
    deep_merge,
)
from backend.app.repositories.dual_frequency_equity_repo import (
    load_dual_frequency_equity_history,
)
from backend.app.services.formal_result_runtime import build_result_envelope

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = ROOT / "config" / "macro_etf_strategy.json"
DEFAULT_MACRO_STATE_PATH = ROOT / "config" / "macro_etf_macro_state.json"

RESULT_KIND = "market_data.macro_etf_strategy"
RULE_VERSION = "rv_macro_etf_strategy_observation_v2"
CACHE_VERSION = "cv_macro_etf_strategy_observation_v2"
SOURCE_VERSION = "sv_macro_etf_strategy_config_choice_history_v2"
VENDOR_VERSION = "vv_local_config+choice_duckdb"

_AMOUNT_PROXY_WARNING = (
    "Fast-layer amount is the daily SUM of all A-share observations from "
    "choice_stock_daily_observation; it is a market-wide proxy, not CSI300 constituent turnover."
)


def macro_etf_strategy_envelope(
    *,
    as_of_date: str | None = None,
    config_path: str | Path | None = None,
    macro_state_path: str | Path | None = None,
    quotes_path: str | Path | None = None,
    portfolio_state_path: str | Path | None = None,
    duckdb_path: str | Path | None = None,
) -> dict[str, object]:
    resolved_date = _normalize_date(as_of_date)
    config_payload, config_warnings, config_file_status, config_defaulted_keys = _load_json_mapping(
        config_path or DEFAULT_CONFIG_PATH,
        fallback=DEFAULT_CONFIG,
        label="config",
    )
    macro_payload, macro_warnings, macro_file_status, macro_defaulted_keys = _load_json_mapping(
        macro_state_path or DEFAULT_MACRO_STATE_PATH,
        fallback=DEFAULT_MACRO_STATE,
        label="macro_state",
    )
    quotes_payload, quote_warnings = _load_optional_json_mapping(quotes_path, label="quotes")
    state_payload, state_warnings = _load_optional_json_mapping(portfolio_state_path, label="portfolio_state")
    result = build_macro_etf_strategy_snapshot(
        config=config_payload,
        macro_state=macro_payload,
        as_of_date=resolved_date,
        quotes=quotes_payload,
        portfolio_state=state_payload,
    )
    result["dual_frequency"] = _build_dual_frequency_candidate(
        duckdb_path=duckdb_path,
        as_of_date=resolved_date,
        slow_cap=_target_total_weight(result),
        config=config_payload,
        portfolio_state=state_payload,
    )
    warnings = [
        *config_warnings,
        *macro_warnings,
        *quote_warnings,
        *state_warnings,
        *list(result.get("warnings") or []),
    ]
    result["warnings"] = warnings
    fallback_defaults_used = "builtin_defaults_used" in {config_file_status, macro_file_status}
    data_status = dict(result.get("data_status") or {})
    data_status["config_status"] = "builtin_defaults_used" if fallback_defaults_used else "files_loaded"
    data_status["config_file_status"] = config_file_status
    data_status["macro_state_file_status"] = macro_file_status
    data_status["config_defaulted_keys"] = config_defaulted_keys
    data_status["macro_state_defaulted_keys"] = macro_defaulted_keys
    dual_frequency_status = str(
        ((result.get("dual_frequency") or {}).get("data_status") or {}).get("status")
        or "not_evaluated"
    )
    data_status["dual_frequency_status"] = dual_frequency_status
    if fallback_defaults_used and data_status.get("status") == "ready":
        data_status["status"] = "warning"
    if dual_frequency_status != "ready" and data_status.get("status") == "ready":
        data_status["status"] = "warning"
    result["data_status"] = data_status
    result["input_files"] = {
        "config_path": str(Path(config_path or DEFAULT_CONFIG_PATH)),
        "macro_state_path": str(Path(macro_state_path or DEFAULT_MACRO_STATE_PATH)),
        "quotes_path": str(Path(quotes_path)) if quotes_path else None,
        "portfolio_state_path": str(Path(portfolio_state_path)) if portfolio_state_path else None,
        "duckdb_path": str(Path(duckdb_path)) if duckdb_path else None,
    }
    quality_flag = _quality_flag(result)
    vendor_status = "vendor_unavailable" if _quote_status(result) in {"quotes_missing", "quotes_incomplete"} else "ok"
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_macro_etf_strategy_{resolved_date.isoformat()}",
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        cache_key=f"macro-etf-strategy:{resolved_date.isoformat()}",
        source_version=SOURCE_VERSION,
        rule_version=RULE_VERSION,
        quality_flag=quality_flag,
        vendor_version=VENDOR_VERSION,
        vendor_status=vendor_status,
        fallback_mode="none",
        as_of_date=resolved_date.isoformat(),
        date_basis="as_of_date",
        filters_applied={"as_of_date": resolved_date.isoformat()},
        tables_used=_dual_frequency_tables(result),
        evidence_rows=_evidence_rows(result),
        next_drill=[
            {
                "label": "Macro toolkit",
                "path": "/macro-toolkit",
                "reason": "Review source macro inputs and analytical boundary.",
            }
        ],
        source_surface="market_data",
        result_payload=result,
    )


def _build_dual_frequency_candidate(
    *,
    duckdb_path: str | Path | None,
    as_of_date: date,
    slow_cap: float | None,
    config: Mapping[str, Any],
    portfolio_state: Mapping[str, Any] | None,
) -> dict[str, Any]:
    history = _load_dual_frequency_history(
        duckdb_path=duckdb_path,
        as_of_date=as_of_date,
    )
    state = dict(portfolio_state or {})
    dual_config = config.get("dual_frequency")
    nav_history = state.get("dual_frequency_nav_history")
    nav_history_authoritative_complete = (
        state.get("dual_frequency_nav_history_authoritative_complete") is True
    )
    try:
        snapshot = build_dual_frequency_equity_snapshot(
            daily_rows=_mapping_rows(history.get("rows")),
            slow_cap=slow_cap,
            as_of_date=as_of_date,
            fast_state=(
                dict(state["dual_frequency_fast_state"])
                if isinstance(state.get("dual_frequency_fast_state"), Mapping)
                else None
            ),
            nav_rows=_mapping_rows(nav_history) or None,
            nav_history_authoritative_complete=nav_history_authoritative_complete,
            survival_state=(
                dict(state["dual_frequency_survival_state"])
                if isinstance(state.get("dual_frequency_survival_state"), Mapping)
                else None
            ),
            resume_temperature=_optional_float(
                state.get("dual_frequency_resume_temperature")
            ),
            config=dict(dual_config) if isinstance(dual_config, Mapping) else None,
        )
    except Exception as exc:  # defensive: candidate analytics must not block the base snapshot
        snapshot = _degraded_dual_frequency_snapshot(
            as_of_date=as_of_date,
            reason=f"dual_frequency_calculation_failed:{exc.__class__.__name__}",
        )
    return _attach_dual_frequency_history(snapshot=snapshot, history=history)


def _load_dual_frequency_history(
    *,
    duckdb_path: str | Path | None,
    as_of_date: date,
) -> dict[str, Any]:
    if duckdb_path is None:
        return _unavailable_dual_frequency_history(
            as_of_date=as_of_date,
            warning="duckdb_path_not_supplied",
        )
    try:
        return load_dual_frequency_equity_history(
            duckdb_path=duckdb_path,
            as_of_date=as_of_date,
        )
    except Exception as exc:  # defensive: read-only candidate data must degrade locally
        return _unavailable_dual_frequency_history(
            as_of_date=as_of_date,
            warning=f"history_load_failed:{exc.__class__.__name__}",
        )


def _unavailable_dual_frequency_history(
    *,
    as_of_date: date,
    warning: str,
) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "quality": "unavailable",
        "series_id": "CA.CSI300",
        "date_basis": "CA.CSI300_trade_date_lte_requested_as_of_date",
        "requested_as_of_date": as_of_date.isoformat(),
        "effective_as_of_date": None,
        "earliest_trade_date": None,
        "latest_trade_date": None,
        "lookback_rows": 260,
        "row_count": 0,
        "rows": [],
        "tables_used": [],
        "sources": {},
        "warnings": [warning],
    }


def _degraded_dual_frequency_snapshot(
    *,
    as_of_date: date,
    reason: str,
) -> dict[str, Any]:
    return {
        "strategy_name": "a_share_dual_frequency_equity_candidate",
        "boundary": "observation_only",
        "execution_enabled": False,
        "formula_version": "a_share_dual_frequency_v6_moss_v1",
        "rule_version": "dual_frequency_equity_candidate_v1",
        "as_of_date": as_of_date.isoformat(),
        "slow": {"status": "not_evaluated"},
        "fast": {"status": "not_evaluated"},
        "survival": {"status": "not_evaluated"},
        "pre_survival_target_total_weight": None,
        "final_target_total_weight": None,
        "events": [],
        "warnings": [reason],
        "data_status": {"status": "degraded"},
        "methodology": {},
        "provenance": {
            "integration_mode": "ported_read_only_candidate",
        },
    }


def _attach_dual_frequency_history(
    *,
    snapshot: Mapping[str, Any],
    history: Mapping[str, Any],
) -> dict[str, Any]:
    result = dict(snapshot)
    result["boundary"] = "observation_only"
    result["execution_enabled"] = False
    history_meta = {
        str(key): value
        for key, value in history.items()
        if key != "rows"
    }
    data_status = dict(result.get("data_status") or {})
    data_status["history"] = history_meta
    if (
        str(history.get("status") or "unavailable") != "ready"
        and data_status.get("status") == "ready"
    ):
        data_status["status"] = "degraded"
    result["data_status"] = data_status
    provenance = dict(result.get("provenance") or {})
    provenance["history"] = history_meta
    # unit/unit_normalization 跟随仓储层 market_amount 源元数据,避免与
    # sources.market_amount.unit(按 vendor 代际归一化为元)自相矛盾。
    market_amount_source = (history.get("sources") or {}).get("market_amount") or {}
    provenance["amount_methodology"] = {
        "source_table": "choice_stock_daily_observation",
        "field": "amount",
        "aggregation": "daily_sum_all_a_share_observations",
        "scope": "all_a_share_market_proxy",
        "is_csi300_constituent_turnover": False,
        "unit": str(market_amount_source.get("unit") or "source_native_unit_unconfirmed"),
        "unit_normalization": market_amount_source.get("unit_normalization"),
    }
    result["provenance"] = provenance
    result["warnings"] = _unique_texts(
        [
            *[str(item) for item in result.get("warnings") or []],
            *[str(item) for item in history.get("warnings") or []],
            _AMOUNT_PROXY_WARNING,
        ]
    )
    return result


def _target_total_weight(result: Mapping[str, Any]) -> float | None:
    position = result.get("position")
    if not isinstance(position, Mapping):
        return None
    return _optional_float(position.get("target_total_weight"))


def _mapping_rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list | tuple):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _optional_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def _dual_frequency_tables(result: Mapping[str, Any]) -> list[str]:
    dual_frequency = result.get("dual_frequency")
    if not isinstance(dual_frequency, Mapping):
        return []
    provenance = dual_frequency.get("provenance")
    if not isinstance(provenance, Mapping):
        return []
    history = provenance.get("history")
    if not isinstance(history, Mapping):
        return []
    tables = history.get("tables_used")
    if not isinstance(tables, list | tuple):
        return []
    return _unique_texts([str(table) for table in tables])


def _unique_texts(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _quality_flag(result: Mapping[str, Any]) -> str:
    status = str((result.get("data_status") or {}).get("status") or "")
    if status == "ready":
        return "ok"
    if status == "blocked":
        return "warning"
    return "warning"


def _quote_status(result: Mapping[str, Any]) -> str:
    return str((result.get("data_status") or {}).get("quote_status") or "")


def _evidence_rows(result: Mapping[str, Any]) -> int:
    universe = (result.get("position") or {}).get("target_weights") if isinstance(result.get("position"), Mapping) else None
    universe_rows = len(universe) if isinstance(universe, Mapping) else 0
    dual_frequency = result.get("dual_frequency")
    if not isinstance(dual_frequency, Mapping):
        return universe_rows
    data_status = dual_frequency.get("data_status")
    history = data_status.get("history") if isinstance(data_status, Mapping) else None
    history_rows = int(history.get("row_count") or 0) if isinstance(history, Mapping) else 0
    return universe_rows + history_rows


def _load_json_mapping(
    path: str | Path, *, fallback: Mapping[str, Any], label: str
) -> tuple[dict[str, Any], list[str], str, list[str]]:
    source = Path(path)
    all_keys = sorted(fallback)
    if not source.exists():
        return (
            dict(fallback),
            [f"{label} file missing at {source}; built-in defaults used"],
            "builtin_defaults_used",
            all_keys,
        )
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return (
            dict(fallback),
            [f"{label} file failed to load at {source}: {exc.__class__.__name__}; defaults used"],
            "builtin_defaults_used",
            all_keys,
        )
    if not isinstance(payload, Mapping):
        return (
            dict(fallback),
            [f"{label} file at {source} is not a JSON object; defaults used"],
            "builtin_defaults_used",
            all_keys,
        )
    defaulted_keys = sorted(set(fallback) - set(payload))
    warnings = (
        [f"{label} file at {source} missing top-level keys {defaulted_keys}; built-in defaults backfilled those keys"]
        if defaulted_keys
        else []
    )
    return deep_merge(fallback, payload), warnings, "loaded", defaulted_keys


def _load_optional_json_mapping(path: str | Path | None, *, label: str) -> tuple[dict[str, Any] | None, list[str]]:
    if path is None:
        return None, []
    source = Path(path)
    if not source.exists():
        return None, [f"{label} file missing at {source}"]
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"{label} file failed to load at {source}: {exc.__class__.__name__}"]
    if not isinstance(payload, Mapping):
        return None, [f"{label} file at {source} is not a JSON object"]
    return dict(payload), []


def _normalize_date(value: str | None) -> date:
    text = str(value or "").strip()
    if not text:
        return date.today()
    return date.fromisoformat(text[:10])
