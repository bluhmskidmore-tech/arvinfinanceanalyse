from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

from backend.app.core_finance.macro.macro_etf_strategy import (
    DEFAULT_CONFIG,
    DEFAULT_MACRO_STATE,
    build_macro_etf_strategy_snapshot,
    deep_merge,
)
from backend.app.services.formal_result_runtime import build_result_envelope

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = ROOT / "config" / "macro_etf_strategy.json"
DEFAULT_MACRO_STATE_PATH = ROOT / "config" / "macro_etf_macro_state.json"

RESULT_KIND = "market_data.macro_etf_strategy"
RULE_VERSION = "rv_macro_etf_strategy_observation_v1"
CACHE_VERSION = "cv_macro_etf_strategy_observation_v1"
SOURCE_VERSION = "sv_macro_etf_strategy_config_v1"
VENDOR_VERSION = "vv_local_config"


def macro_etf_strategy_envelope(
    *,
    as_of_date: str | None = None,
    config_path: str | Path | None = None,
    macro_state_path: str | Path | None = None,
    quotes_path: str | Path | None = None,
    portfolio_state_path: str | Path | None = None,
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
    if fallback_defaults_used and data_status.get("status") == "ready":
        data_status["status"] = "warning"
    result["data_status"] = data_status
    result["input_files"] = {
        "config_path": str(Path(config_path or DEFAULT_CONFIG_PATH)),
        "macro_state_path": str(Path(macro_state_path or DEFAULT_MACRO_STATE_PATH)),
        "quotes_path": str(Path(quotes_path)) if quotes_path else None,
        "portfolio_state_path": str(Path(portfolio_state_path)) if portfolio_state_path else None,
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
        tables_used=[],
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
    return len(universe) if isinstance(universe, Mapping) else 0


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
