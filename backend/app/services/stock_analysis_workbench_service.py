from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Literal, cast

from backend.app.repositories.stock_analysis_theme_overlay_reader import (
    StockAnalysisThemeOverlayReader,
)
from backend.app.services.formal_result_runtime import build_result_envelope
from backend.app.services.market_data_livermore_service import livermore_strategy_envelope_from_catalog

WORKBENCH_RESULT_KIND = "market_data.stock_analysis.workbench"
WORKBENCH_RULE_VERSION = "rv_stock_analysis_workbench_v1"
WORKBENCH_CACHE_VERSION = "cv_stock_analysis_workbench_v1"

DEFAULT_INCLUDE_KEYS = frozenset({"main", "evidence_summary"})
OPTIONAL_MODULE_ENDPOINTS: dict[str, str] = {
    "signal_confluence": "/ui/market-data/livermore/signal-confluence",
    "sector_rank_series": "/ui/market-data/livermore/sector-rank-series",
    "strategy_score": "/ui/market-data/livermore/strategy-score",
    "strategy_optimization": "/ui/market-data/livermore/strategy-optimization",
    "candidate_history_backtest": "/ui/market-data/livermore/candidate-history",
    "cycle_proxy_backtest": "/ui/market-data/livermore/cycle-proxy-backtest",
    "portfolio_backtest": "/ui/market-data/livermore/candidate-history-portfolio-backtest",
}
ALL_INCLUDE_KEYS = DEFAULT_INCLUDE_KEYS | frozenset(OPTIONAL_MODULE_ENDPOINTS)
REQUIRED_RULE_READINESS_KEYS = ("market_gate", "sector_rank", "stock_pivot", "risk_exit")
REQUIRED_GAP_FAMILIES = frozenset(
    {
        "broad_index_history",
        "breadth",
        "limit_up_quality",
        "sector_strength",
        "stock_universe",
        "position_risk",
    }
)


def stock_analysis_workbench_envelope(
    *,
    duckdb_path: str,
    as_of_date: str | None,
    choice_stock_catalog_file: object,
    include: str | None = None,
    sector_window_days: int = 20,
    top_k: int = 10,
    theme_overlay_reader: StockAnalysisThemeOverlayReader | None = None,
) -> dict[str, object]:
    strategy_kwargs: dict[str, object] = {
        "duckdb_path": duckdb_path,
        "as_of_date": as_of_date,
        "choice_stock_catalog_file": choice_stock_catalog_file,
    }
    if theme_overlay_reader is not None:
        strategy_kwargs["theme_overlay_reader"] = theme_overlay_reader
    strategy_envelope = livermore_strategy_envelope_from_catalog(**strategy_kwargs)
    return build_stock_analysis_workbench_envelope(
        strategy_envelope=strategy_envelope,
        requested_as_of_date=as_of_date,
        include=include,
        sector_window_days=sector_window_days,
        top_k=top_k,
    )


def build_stock_analysis_workbench_envelope(
    *,
    strategy_envelope: dict[str, object],
    requested_as_of_date: str | None,
    include: str | None = None,
    sector_window_days: int = 20,
    top_k: int = 10,
) -> dict[str, object]:
    include_keys, unknown_include_keys = _parse_include(include)
    strategy_meta = _mapping(strategy_envelope.get("result_meta"))
    strategy_result = _mapping(strategy_envelope.get("result"))
    resolved_as_of_date = _optional_text(strategy_result.get("as_of_date")) or _optional_text(
        strategy_meta.get("as_of_date")
    )
    fallback_date = _fallback_date(
        requested_as_of_date=requested_as_of_date,
        resolved_as_of_date=resolved_as_of_date,
        meta=strategy_meta,
        result=strategy_result,
    )
    first_screen = _first_screen(strategy_result, top_k=top_k)
    data_status = _data_status(strategy_meta)
    main_module = _module_from_envelope(
        key="main",
        label="Livermore strategy snapshot",
        endpoint="/ui/market-data/livermore",
        envelope=strategy_envelope,
    )
    modules: dict[str, object] = {"main": main_module}
    for key, endpoint in OPTIONAL_MODULE_ENDPOINTS.items():
        if key in include_keys:
            modules[key] = _deferred_module(
                key=key,
                endpoint=endpoint,
                as_of_date=resolved_as_of_date,
                reason=(
                    "Deferred from the default workbench response to keep the first-screen contract bounded; "
                    "use the linked detail endpoint for the full diagnostic payload."
                ),
            )

    issues = _workbench_issues(
        strategy_meta=strategy_meta,
        strategy_result=strategy_result,
        unknown_include_keys=unknown_include_keys,
    )
    decision_summary = _decision_summary(
        first_screen=first_screen,
        strategy_meta=strategy_meta,
        issues=issues,
    )
    payload = {
        "page_id": "GAP-STOCK-ANALYSIS-PAGE",
        "route": "/stock-analysis",
        "basis": "analytical",
        "contract_status": "observational_only",
        "formal_use_allowed": False,
        "requested_as_of_date": _optional_text(requested_as_of_date),
        "as_of_date": resolved_as_of_date,
        "fallback_date": fallback_date,
        "stale": _is_stale(strategy_meta, fallback_date=fallback_date),
        "page_question": _page_question(decision_summary=decision_summary, issues=issues),
        "decision_summary": decision_summary,
        "data_status": data_status,
        "first_screen": first_screen,
        "modules": modules,
        "endpoint_evidence": _endpoint_evidence(
            modules=modules,
            as_of_date=resolved_as_of_date,
            evidence_rows=data_status["evidence_rows"],
        ),
        "issues": issues,
        "links": _workbench_links(),
        "include": {
            "requested": sorted(include_keys),
            "unknown": sorted(unknown_include_keys),
            "sector_window_days": sector_window_days,
            "top_k": top_k,
        },
    }
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_stock_analysis_workbench_{date.today().strftime('%Y%m%d')}",
        result_kind=WORKBENCH_RESULT_KIND,
        cache_version=WORKBENCH_CACHE_VERSION,
        cache_key=_cache_key(resolved_as_of_date),
        source_version=_lineage_text(strategy_meta.get("source_version"), "sv_stock_analysis_workbench_empty"),
        rule_version=WORKBENCH_RULE_VERSION,
        quality_flag=_quality_flag(strategy_meta.get("quality_flag")),
        vendor_version=_lineage_text(strategy_meta.get("vendor_version"), "vv_none"),
        vendor_status=_vendor_status(strategy_meta.get("vendor_status")),
        fallback_mode=_fallback_mode(strategy_meta.get("fallback_mode")),
        filters_applied={
            "requested_as_of_date": _optional_text(requested_as_of_date),
            "resolved_as_of_date": resolved_as_of_date,
            "include": sorted(include_keys),
            "unknown_include": sorted(unknown_include_keys),
            "sector_window_days": sector_window_days,
            "top_k": top_k,
        },
        tables_used=_string_list(strategy_meta.get("tables_used")),
        evidence_rows=_optional_int(strategy_meta.get("evidence_rows")),
        source_surface="market_data",
        as_of_date=resolved_as_of_date,
        fallback_date=fallback_date,
        result_payload=payload,
    )


def _parse_include(include: str | None) -> tuple[set[str], set[str]]:
    if not _optional_text(include):
        return set(DEFAULT_INCLUDE_KEYS), set()
    requested = {text.strip() for text in str(include or "").split(",") if text.strip()}
    known = {key for key in requested if key in ALL_INCLUDE_KEYS}
    unknown = requested - known
    return set(DEFAULT_INCLUDE_KEYS) | known, unknown


def _first_screen(result: dict[str, object], *, top_k: int) -> dict[str, object]:
    return {
        "market_gate": _mapping(result.get("market_gate")) or None,
        "review_queue": _candidate_queue(result, top_k=top_k),
        "sector_snapshot": _ranked_items(result.get("sector_rank"), top_k=top_k),
        "risk_exit_snapshot": _risk_exit_snapshot(result.get("risk_exit"), top_k=top_k),
        "data_gaps": _classified_data_gaps(result.get("data_gaps")),
        "diagnostics": _list_of_mappings(result.get("diagnostics")),
        "supported_outputs": _string_list(result.get("supported_outputs")),
        "unsupported_outputs": _list_of_mappings(result.get("unsupported_outputs")),
    }


def _candidate_queue(result: dict[str, object], *, top_k: int) -> list[dict[str, object]]:
    keys = (
        "stock_candidates",
        "factor_screen_candidates",
        "hybrid_fusion_candidates",
        "uptrend_momentum_candidates",
        "fresh_trend_watchlist",
        "mean_reversion_candidates",
        "theme_breakout",
    )
    rows: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for key in keys:
        module_items = (
            _theme_breakout_candidate_rows(result.get(key))
            if key == "theme_breakout"
            else _items_from_container(result.get(key))
        )
        for item in module_items:
            stock_code = str(item.get("stock_code") or "").strip()
            source_key = key
            dedupe_key = (source_key, stock_code)
            if stock_code and dedupe_key in seen:
                continue
            if stock_code:
                seen.add(dedupe_key)
            row = dict(item)
            row["source_module"] = source_key
            rows.append(row)
            if len(rows) >= top_k:
                return rows
    return rows


def _theme_breakout_candidate_rows(value: object) -> list[dict[str, object]]:
    by_stock: dict[str, dict[str, object]] = {}
    for theme in _items_from_container(value):
        theme_membership = {
            "theme_key": theme.get("theme_key"),
            "theme_name": theme.get("theme_name"),
            "rank": theme.get("rank"),
            "source_kind": theme.get("source_kind"),
        }
        for member_position, member in enumerate(
            _list_of_mappings(theme.get("items")),
            start=1,
        ):
            stock_code = str(member.get("stock_code") or "").strip()
            if not stock_code:
                continue
            member_rank = member.get("rank") or member_position
            membership = {
                **theme_membership,
                "member_rank": member_rank,
            }
            current = by_stock.get(stock_code)
            if current is None:
                current = {
                    **member,
                    "theme_key": theme_membership["theme_key"],
                    "theme_name": theme_membership["theme_name"],
                    "theme_rank": theme_membership["rank"],
                    "source_kind": theme_membership["source_kind"],
                    "member_rank": member_rank,
                    "theme_memberships": [membership],
                }
                by_stock[stock_code] = current
                continue
            memberships = cast(list[dict[str, object]], current["theme_memberships"])
            if membership not in memberships:
                memberships.append(membership)
    return list(by_stock.values())


def _ranked_items(value: object, *, top_k: int) -> list[dict[str, object]]:
    rows = [dict(item) for item in _items_from_container(value)]
    return rows[:top_k]


def _risk_exit_snapshot(value: object, *, top_k: int) -> list[dict[str, object]]:
    payload = _mapping(value)
    rows: list[dict[str, object]] = []
    for key in ("items", "watch_items"):
        for item in _list_of_mappings(payload.get(key)):
            row = dict(item)
            row["source_module"] = "risk_exit"
            row["risk_exit_bucket"] = key
            rows.append(row)
            if len(rows) >= top_k:
                return rows
    return rows


def _decision_summary(
    *,
    first_screen: dict[str, object],
    strategy_meta: dict[str, object],
    issues: list[dict[str, object]],
) -> dict[str, object]:
    market_gate = _mapping(first_screen.get("market_gate"))
    review_queue = _list_of_mappings(first_screen.get("review_queue"))
    top_candidate = review_queue[0] if review_queue else {}
    blocking_issue = next((item for item in issues if item.get("severity") == "blocking"), None)
    warning_issue = next((item for item in issues if item.get("severity") == "warning"), None)
    return {
        "gate_state": _optional_text(market_gate.get("state")),
        "gate_label": _optional_text(market_gate.get("state")) or "unknown",
        "can_review_candidates": bool(review_queue) and blocking_issue is None,
        "top_review_stock_code": _optional_text(top_candidate.get("stock_code")),
        "top_review_stock_name": _optional_text(top_candidate.get("stock_name")),
        "review_queue_count": len(review_queue),
        "evidence_closure_label": "needs_review" if blocking_issue or warning_issue else "review_ready",
        "primary_blocker": _optional_text(blocking_issue.get("message")) if blocking_issue else None,
        "quality_flag": _optional_text(strategy_meta.get("quality_flag")),
    }


def _page_question(
    *,
    decision_summary: dict[str, object],
    issues: list[dict[str, object]],
) -> dict[str, object]:
    if not decision_summary.get("review_queue_count"):
        answer_state = "no_data"
        reason = "No review candidates are present in the current Livermore snapshot."
    elif decision_summary.get("primary_blocker"):
        answer_state = "blocked"
        reason = str(decision_summary["primary_blocker"])
    elif any(item.get("severity") == "warning" for item in issues):
        answer_state = "limited_review"
        reason = "Candidates are present, but at least one data quality or boundary warning remains visible."
    else:
        answer_state = "review_ready"
        reason = "Candidates and first-screen evidence are available for observational review."
    return {
        "question": "Can the stock analysis workbench continue candidate review today, and who should be reviewed first?",
        "answer_state": answer_state,
        "answer_label": answer_state,
        "reason": reason,
    }


def _data_status(meta: dict[str, object]) -> dict[str, object]:
    return {
        "quality_flag": _optional_text(meta.get("quality_flag")),
        "vendor_status": _optional_text(meta.get("vendor_status")),
        "fallback_mode": _optional_text(meta.get("fallback_mode")),
        "source_version": _optional_text(meta.get("source_version")),
        "rule_version": _optional_text(meta.get("rule_version")),
        "cache_version": _optional_text(meta.get("cache_version")),
        "tables_used": _string_list(meta.get("tables_used")),
        "evidence_rows": _optional_int(meta.get("evidence_rows")),
    }


def _module_from_envelope(
    *,
    key: str,
    label: str,
    endpoint: str,
    envelope: dict[str, object],
) -> dict[str, object]:
    meta = _mapping(envelope.get("result_meta"))
    result = _mapping(envelope.get("result"))
    return {
        "key": key,
        "label": label,
        "endpoint": endpoint,
        "status": _module_status(meta),
        "result": result,
        "summary": _module_summary(result),
        "meta": _compact_meta(meta),
        "issues": _module_issues(meta),
    }


def _deferred_module(
    *,
    key: str,
    endpoint: str,
    as_of_date: str | None,
    reason: str,
) -> dict[str, object]:
    return {
        "key": key,
        "label": key.replace("_", " "),
        "endpoint": endpoint,
        "status": "deferred",
        "result": None,
        "summary": {"as_of_date": as_of_date},
        "meta": _empty_meta(as_of_date=as_of_date),
        "issues": [
            {
                "severity": "info",
                "code": "module_deferred",
                "message": reason,
                "source_module": key,
            }
        ],
    }


def _module_status(meta: dict[str, object]) -> Literal["ready", "stale", "error"]:
    quality = str(meta.get("quality_flag") or "").strip().lower()
    fallback = str(meta.get("fallback_mode") or "").strip().lower()
    if quality == "error":
        return "error"
    if quality == "stale" or fallback not in {"", "none"}:
        return "stale"
    return "ready"


def _module_summary(result: dict[str, object]) -> dict[str, object]:
    summary = _mapping(result.get("workbench_summary"))
    if summary:
        return summary
    return {
        "as_of_date": _optional_text(result.get("as_of_date")),
        "candidate_count": len(_candidate_queue(result, top_k=100)),
        "sector_count": len(_items_from_container(result.get("sector_rank"))),
        "data_gap_count": len(_list_of_mappings(result.get("data_gaps"))),
        "diagnostic_count": len(_list_of_mappings(result.get("diagnostics"))),
    }


def _compact_meta(meta: dict[str, object]) -> dict[str, object]:
    return {
        "trace_id": _optional_text(meta.get("trace_id")),
        "source_version": _optional_text(meta.get("source_version")),
        "rule_version": _optional_text(meta.get("rule_version")),
        "cache_version": _optional_text(meta.get("cache_version")),
        "quality_flag": _optional_text(meta.get("quality_flag")),
        "vendor_status": _optional_text(meta.get("vendor_status")),
        "fallback_mode": _optional_text(meta.get("fallback_mode")),
        "tables_used": _string_list(meta.get("tables_used")),
        "evidence_rows": _optional_int(meta.get("evidence_rows")),
    }


def _empty_meta(*, as_of_date: str | None) -> dict[str, object]:
    return {
        "trace_id": None,
        "source_version": None,
        "rule_version": None,
        "cache_version": None,
        "quality_flag": None,
        "vendor_status": None,
        "fallback_mode": None,
        "tables_used": [],
        "evidence_rows": None,
        "as_of_date": as_of_date,
    }


def _module_issues(meta: dict[str, object]) -> list[dict[str, object]]:
    status = _module_status(meta)
    if status == "ready":
        return []
    return [
        {
            "severity": "warning" if status == "stale" else "blocking",
            "code": f"module_{status}",
            "message": f"Module status is {status}.",
            "source_module": "main",
        }
    ]


def _workbench_issues(
    *,
    strategy_meta: dict[str, object],
    strategy_result: dict[str, object],
    unknown_include_keys: set[str],
) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for key in sorted(unknown_include_keys):
        issues.append(
            {
                "severity": "warning",
                "code": "unknown_include",
                "message": f"Unknown include key ignored: {key}",
                "source_module": None,
            }
        )
    if _module_status(strategy_meta) != "ready":
        issues.extend(_module_issues(strategy_meta))
    issues.extend(_rule_readiness_issues(strategy_result.get("rule_readiness")))
    for item in _classified_data_gaps(strategy_result.get("data_gaps")):
        status = _data_gap_issue_status(item)
        if item["blocks_review"] or status != "ready":
            issues.append(
                {
                    "severity": "blocking" if item["blocks_review"] else "warning",
                    "code": f"data_gap_{status}",
                    "message": _optional_text(item.get("evidence"))
                    or _optional_text(item.get("message"))
                    or _optional_text(item.get("reason"))
                    or f"Data gap status is {status}.",
                    "source_module": "main",
                }
            )
    return issues


def _rule_readiness_issues(value: object) -> list[dict[str, object]]:
    by_key: dict[str, list[dict[str, object]]] = {}
    issues: list[dict[str, object]] = []
    if not isinstance(value, list):
        issues.append(
            {
                "severity": "blocking",
                "code": "rule_readiness_malformed_collection",
                "message": "Rule readiness must be a list.",
                "source_module": "main",
            }
        )
    else:
        for index, item in enumerate(value):
            if not isinstance(item, Mapping):
                issues.append(
                    {
                        "severity": "blocking",
                        "code": "rule_readiness_malformed_row",
                        "message": f"Rule readiness row {index} must be an object.",
                        "source_module": "main",
                    }
                )
                continue
            row = dict(item)
            key = str(row.get("key") or "").strip()
            if not key:
                issues.append(
                    {
                        "severity": "blocking",
                        "code": "rule_readiness_missing_key",
                        "message": f"Rule readiness row {index} is missing a non-empty key.",
                        "source_module": "main",
                    }
                )
                continue
            by_key.setdefault(key, []).append(row)
    for key in REQUIRED_RULE_READINESS_KEYS:
        rows = by_key.get(key, [])
        if len(rows) > 1:
            message = f"Duplicate rule readiness rows: {key}."
            issues.append(
                {
                    "severity": "blocking",
                    "code": f"rule_readiness_duplicate_{key}",
                    "message": message,
                    "source_module": "main",
                }
            )
        if not rows:
            message = f"Required rule readiness is missing: {key}."
            issues.append(
                {
                    "severity": "blocking",
                    "code": f"rule_readiness_missing_{key}",
                    "message": message,
                    "source_module": "main",
                }
            )
            continue
        for item in rows:
            status = str(item.get("status") or "").strip().lower()
            if status != "ready":
                message = (
                    _optional_text(item.get("summary"))
                    or _optional_text(item.get("evidence"))
                    or f"Required rule readiness is {status or 'unavailable'}: {key}."
                )
                issues.append(
                    {
                        "severity": "blocking",
                        "code": f"rule_readiness_{status or 'unavailable'}_{key}",
                        "message": message,
                        "source_module": "main",
                    }
                )
    for key, rows in by_key.items():
        if key in REQUIRED_RULE_READINESS_KEYS:
            continue
        for item in rows:
            status = str(item.get("status") or "").strip().lower()
            if status != "ready":
                message = (
                    _optional_text(item.get("summary"))
                    or _optional_text(item.get("evidence"))
                    or f"Returned rule readiness is {status or 'unavailable'}: {key}."
                )
                issues.append(
                    {
                        "severity": "blocking",
                        "code": f"rule_readiness_{status or 'unavailable'}_{key}",
                        "message": message,
                        "source_module": "main",
                    }
                )
    return issues


def _data_gap_issue_status(item: dict[str, object]) -> str:
    status = str(item.get("status") or "").strip().lower() or "unavailable"
    age_days = item.get("age_days")
    if isinstance(age_days, int) and age_days < 0:
        return "look_ahead"
    tier = str(item.get("tier") or "").strip().lower()
    if status == "ready" and tier in {"stale", "expired"}:
        return tier
    return status


def _classified_data_gaps(value: object) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in _list_of_mappings(value):
        row = dict(item)
        family = str(row.get("input_family") or "").strip().lower()
        status = str(row.get("status") or "").strip().lower()
        tier = str(row.get("tier") or "").strip().lower()
        age_days = row.get("age_days")
        row["blocks_review"] = bool(
            (family in REQUIRED_GAP_FAMILIES and status != "ready")
            or status in {"stale", "look_ahead", "blocked", "error", "unsupported"}
            or tier in {"stale", "expired"}
            or (isinstance(age_days, int) and age_days < 0)
        )
        rows.append(row)
    return rows


def _endpoint_evidence(
    *,
    modules: dict[str, object],
    as_of_date: str | None,
    evidence_rows: object,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for module in modules.values():
        item = _mapping(module)
        rows.append(
            {
                "key": item.get("key"),
                "label": item.get("label"),
                "endpoint": item.get("endpoint"),
                "status": item.get("status"),
                "as_of_date": as_of_date,
                "rows": evidence_rows if item.get("key") == "main" else None,
                "warning": _first_issue_message(item.get("issues")),
            }
        )
    return rows


def _workbench_links() -> dict[str, str]:
    return {
        "stock_detail": "/ui/market-data/livermore/stock-detail",
        "kline_analysis": "/ui/market-data/stock-analysis/kline-analysis",
        "candidate_history": "/ui/market-data/livermore/candidate-history",
        "sector_rank_series": "/ui/market-data/livermore/sector-rank-series",
        "strategy_score": "/ui/market-data/livermore/strategy-score",
        "strategy_optimization": "/ui/market-data/livermore/strategy-optimization",
        "cycle_proxy_backtest": "/ui/market-data/livermore/cycle-proxy-backtest",
        "portfolio_backtest": "/ui/market-data/livermore/candidate-history-portfolio-backtest",
    }


def _fallback_date(
    *,
    requested_as_of_date: str | None,
    resolved_as_of_date: str | None,
    meta: dict[str, object],
    result: dict[str, object],
) -> str | None:
    explicit = _optional_text(result.get("fallback_date")) or _optional_text(meta.get("fallback_date"))
    if explicit:
        return explicit
    if (
        _optional_text(requested_as_of_date)
        and resolved_as_of_date
        and _optional_text(requested_as_of_date) != resolved_as_of_date
    ):
        return resolved_as_of_date
    return None


def _is_stale(meta: dict[str, object], *, fallback_date: str | None) -> bool:
    return (
        str(meta.get("quality_flag") or "").strip().lower() == "stale"
        or str(meta.get("fallback_mode") or "").strip().lower() not in {"", "none"}
        or fallback_date is not None
    )


def _items_from_container(value: object) -> list[dict[str, object]]:
    if isinstance(value, dict) and isinstance(value.get("items"), list):
        return _list_of_mappings(value.get("items"))
    if isinstance(value, list):
        return _list_of_mappings(value)
    return []


def _list_of_mappings(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _mapping(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    return {}


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for text in (_optional_text(item) for item in value) if text]


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return None


def _lineage_text(value: object, default: str) -> str:
    return _optional_text(value) or default


def _quality_flag(value: object) -> Literal["ok", "warning", "error", "stale"]:
    text = str(value or "").strip().lower()
    if text in {"ok", "warning", "error", "stale"}:
        return cast(Literal["ok", "warning", "error", "stale"], text)
    return "warning"


def _vendor_status(value: object) -> Literal["ok", "vendor_stale", "vendor_unavailable"]:
    text = str(value or "").strip().lower()
    if text in {"ok", "vendor_stale", "vendor_unavailable"}:
        return cast(Literal["ok", "vendor_stale", "vendor_unavailable"], text)
    return "ok"


def _fallback_mode(value: object) -> Literal["none", "latest_snapshot"]:
    text = str(value or "").strip().lower()
    if text == "latest_snapshot":
        return "latest_snapshot"
    return "none"


def _cache_key(as_of_date: str | None) -> str:
    return f"stock-analysis:workbench:{as_of_date or 'latest'}"


def _first_issue_message(value: object) -> str | None:
    for item in _list_of_mappings(value):
        text = _optional_text(item.get("message"))
        if text:
            return text
    return None
