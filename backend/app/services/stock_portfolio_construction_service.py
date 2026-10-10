"""Phase 2A stock portfolio-construction projection.

This service deliberately stops at a proposal-only projection.  The source of
truth for the candidate set is the stock-analysis workbench's ``main`` module;
the service does not scan DuckDB, import a legacy position snapshot, or create
an order/rebalance command.  A scoped current-position contract is intentionally
not assumed here, so every rebalance result remains fail-closed.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from decimal import Decimal
from typing import cast

from backend.app.services.formal_result_runtime import QualityFlag, build_result_envelope

RESULT_KIND = "market_data.stock_analysis.portfolio_construction"
RULE_VERSION = "rv_stock_portfolio_construction_phase2a_v1"
CACHE_VERSION = "cv_stock_portfolio_construction_phase2a_v1"

CONTRACT_STATUS = "proposal_only"
REBALANCE_BLOCK_REASON = "blocked_missing_scoped_positions"

SUPPORTED_PORTFOLIO_ID = "SHADOW-STOCK-RESEARCH"
_ALLOWED_QUALITY_FLAGS = {"ok", "warning", "error", "stale"}
_ALLOWED_VENDOR_STATUS = {"ok", "vendor_stale", "vendor_unavailable"}
_ALLOWED_FALLBACK_MODES = {"none", "latest_snapshot"}

# The core risk function intentionally accepts only explicit target lines.  It
# must not receive portfolio or date context as hidden kwargs because those
# fields are not inputs to the descriptive risk calculation.
ShadowRiskBuilder = Callable[[Sequence[Mapping[str, object]]], Mapping[str, object]]


def stock_portfolio_construction_envelope(
    *,
    portfolio_id: str,
    workbench_envelope: Mapping[str, object],
    as_of_date: str | None = None,
    risk_builder: ShadowRiskBuilder | None = None,
) -> dict[str, object]:
    """Build a proposal-only stock portfolio projection from a workbench.

    ``risk_builder`` exists for focused tests and for the agreed
    ``core_finance.stock_portfolio_risk.compute_stock_portfolio_risk``
    boundary.  Production callers leave it unset; the implementation resolves
    that core-finance function lazily.
    """

    normalized_portfolio_id = _validate_portfolio_id(portfolio_id)
    requested_as_of_date = _validate_optional_date(as_of_date)
    workbench_result = _mapping(workbench_envelope.get("result"))
    workbench_meta = _mapping(workbench_envelope.get("result_meta"))

    resolved_as_of_date = _first_text(
        workbench_result.get("as_of_date"),
        workbench_meta.get("as_of_date"),
        requested_as_of_date,
    )
    main_result, main_status = _main_module_result(workbench_result)
    stock_candidates = _mapping(main_result.get("stock_candidates"))
    candidate_items = _list_of_mappings(stock_candidates.get("items"))
    position_size_hint = _mapping(stock_candidates.get("position_size_hint"))

    replay_closure = _mapping(workbench_result.get("replay_closure"))
    source_gate = _source_gate(
        replay_closure,
        resolved_as_of_date=resolved_as_of_date,
    )
    target_rows = _build_target_rows(
        candidate_items,
        position_size_hint=position_size_hint,
    )
    target_status = _target_status(
        source_gate=source_gate,
        candidate_rows=target_rows,
        main_status=main_status,
    )
    target_rows = _apply_target_status(
        target_rows,
        target_status=target_status,
        source_gate=source_gate,
    )

    risk_snapshot = _build_risk_snapshot(
        builder=risk_builder,
        portfolio_id=normalized_portfolio_id,
        as_of_date=resolved_as_of_date,
        target_rows=target_rows,
        source_gate=source_gate,
    )

    rebalance = {
        "status": REBALANCE_BLOCK_REASON,
        "blocked": True,
        "current_positions": [],
        "scoped_positions_available": False,
        "legacy_position_snapshot_used": False,
        "legacy_position_snapshot_status": "ignored_unscoped",
        "reason": (
            "No portfolio-scoped current-position contract is available. "
            "An unscoped legacy position snapshot is not treated as the current portfolio."
        ),
    }
    quality_flag = _enum_text(
        workbench_meta.get("quality_flag"),
        allowed=_ALLOWED_QUALITY_FLAGS,
        default="warning",
    )
    risk_status = risk_snapshot.get("data_status", risk_snapshot.get("status"))
    if risk_status == "error":
        quality_flag = "error"
    elif quality_flag == "ok" and (
        target_status != "reference_preview"
        or risk_status in {
        "unavailable",
        "blocked",
        }
        or rebalance["blocked"]
    ):
        quality_flag = "warning"

    source_version = _lineage_text(
        workbench_meta.get("source_version"),
        default="sv_stock_analysis_workbench_unknown",
    )
    vendor_version = _lineage_text(workbench_meta.get("vendor_version"), default="vv_none")
    vendor_status = _enum_text(
        workbench_meta.get("vendor_status"),
        allowed=_ALLOWED_VENDOR_STATUS,
        default="ok",
    )
    fallback_mode = _enum_text(
        workbench_meta.get("fallback_mode"),
        allowed=_ALLOWED_FALLBACK_MODES,
        default="none",
    )
    tables_used = _string_list(workbench_meta.get("tables_used"))
    payload: dict[str, object] = {
        "page_id": "GAP-STOCK-ANALYSIS-PORTFOLIO",
        "route": "/stock-analysis/portfolio",
        "portfolio_id": normalized_portfolio_id,
        "requested_as_of_date": requested_as_of_date,
        "as_of_date": resolved_as_of_date,
        "resolved_as_of_date": resolved_as_of_date,
        "basis": "analytical",
        "contract_status": CONTRACT_STATUS,
        "formal_use_allowed": False,
        "trading_instruction_allowed": False,
        "execution_approval_allowed": False,
        "proposal_status": target_status,
        "context": {
            "requested_as_of_date": requested_as_of_date,
            "resolved_as_of_date": resolved_as_of_date,
            "portfolio_id": normalized_portfolio_id,
            "source_page_id": "GAP-STOCK-ANALYSIS-PAGE",
            "source_route": "/stock-analysis",
            "source_module": "main",
            "main_module_status": main_status,
        },
        "source_gate": source_gate,
        "source_gate_status": source_gate["status"],
        "target": {
            "status": target_status,
            "blocked": target_status != "reference_preview",
            "items": target_rows,
            "candidate_count": len(target_rows),
            "weight_basis": "stock_candidates.position_size_hint.items[].equal_weight",
            "block_reason": _target_block_reason(
                target_status=target_status,
                source_gate=source_gate,
            ),
        },
        "rebalance": rebalance,
        "risk_snapshot": risk_snapshot,
        "legacy_position_snapshot": {
            "used": False,
            "status": "ignored_unscoped",
            "reason": (
                "Legacy livermore_position_snapshot is not scoped to this portfolio and "
                "cannot be used as current holdings."
            ),
        },
        "versions": {
            "source_version": source_version,
            "workbench_rule_version": _lineage_text(workbench_meta.get("rule_version")),
            "portfolio_construction_rule_version": RULE_VERSION,
            "portfolio_version": normalized_portfolio_id,
            "proposal_version": None,
            "calculation_run_id": None,
            "review_run_id": None,
        },
        "warnings": _warnings(
            source_gate=source_gate,
            target_status=target_status,
            risk_snapshot=risk_snapshot,
        ),
        "issues": _issues(
            source_gate=source_gate,
            target_status=target_status,
            main_status=main_status,
        ),
    }
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_stock_portfolio_construction_{uuid.uuid4().hex}",
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        cache_key=_cache_key(
            normalized_portfolio_id,
            requested_as_of_date or resolved_as_of_date,
        ),
        source_version=f"sv_stock_portfolio_construction:{source_version}",
        rule_version=RULE_VERSION,
        quality_flag=cast(QualityFlag, quality_flag),
        vendor_version=cast(str, vendor_version),
        vendor_status=vendor_status,  # type: ignore[arg-type]
        fallback_mode=fallback_mode,  # type: ignore[arg-type]
        filters_applied={
            "portfolio_id": normalized_portfolio_id,
            "requested_as_of_date": requested_as_of_date,
            "resolved_as_of_date": resolved_as_of_date,
            "source_route": "/stock-analysis",
        },
        tables_used=tables_used,
        evidence_rows=len(candidate_items),
        next_drill=[
            {
                "label": "Stock analysis workbench",
                "path": "/stock-analysis",
                "reason": "Review source candidates and replay-closure evidence.",
            }
        ],
        source_surface="market_data",
        requested_report_date=requested_as_of_date,
        resolved_report_date=resolved_as_of_date,
        as_of_date=resolved_as_of_date,
        date_basis="workbench_as_of_date",
        result_payload=payload,
    )


def build_stock_portfolio_construction_envelope(
    *,
    portfolio_id: str,
    workbench_envelope: Mapping[str, object],
    as_of_date: str | None = None,
    risk_builder: ShadowRiskBuilder | None = None,
) -> dict[str, object]:
    """Compatibility name for callers that use ``build_*`` service builders."""

    return stock_portfolio_construction_envelope(
        portfolio_id=portfolio_id,
        workbench_envelope=workbench_envelope,
        as_of_date=as_of_date,
        risk_builder=risk_builder,
    )


def _main_module_result(workbench_result: Mapping[str, object]) -> tuple[dict[str, object], str]:
    modules = _mapping(workbench_result.get("modules"))
    main_module = _mapping(modules.get("main"))
    main_result = _mapping(main_module.get("result"))
    if main_result:
        return main_result, _text(main_module.get("status")) or "ready"
    # The fallback only supports compact test/legacy envelopes that already
    # carry the same workbench result. It never reads a raw data source.
    if _mapping(workbench_result.get("stock_candidates")):
        return dict(workbench_result), _text(main_module.get("status")) or "ready"
    return {}, _text(main_module.get("status")) or "missing"


def _source_gate(
    replay_closure: Mapping[str, object],
    *,
    resolved_as_of_date: str | None,
) -> dict[str, object]:
    closure_status = _text(replay_closure.get("status"))
    ready = closure_status == "ready"
    reason_codes = _string_list(replay_closure.get("reason_codes"))
    blocker = _text(replay_closure.get("primary_blocker_code"))
    if not ready and not blocker:
        blocker = reason_codes[0] if reason_codes else "replay_closure_not_ready"
    return {
        "status": "ready" if ready else "blocked",
        "ready": ready,
        "source": "replay_closure",
        "closure_status": closure_status or "missing",
        "selection_status": _text(replay_closure.get("selection_status")),
        "data_availability": _text(replay_closure.get("data_availability")),
        "as_of_date": _first_text(
            replay_closure.get("evaluation_as_of_date"),
            resolved_as_of_date,
        ),
        "cohort_id": _text(replay_closure.get("cohort_id")),
        "primary_blocker_code": None if ready else blocker,
        "reason_codes": reason_codes,
        "versions": dict(_mapping(replay_closure.get("versions"))),
        "sources": dict(_mapping(replay_closure.get("sources"))),
    }


def _build_target_rows(
    candidates: Sequence[Mapping[str, object]],
    *,
    position_size_hint: Mapping[str, object],
) -> list[dict[str, object]]:
    hint_by_code = {
        _text(item.get("stock_code")): item
        for item in _list_of_mappings(position_size_hint.get("items"))
        if _text(item.get("stock_code"))
    }
    rows: list[dict[str, object]] = []
    for index, candidate in enumerate(candidates, start=1):
        code = _text(candidate.get("stock_code"))
        if not code:
            continue
        hint = hint_by_code.get(code, {})
        equal_weight = _number(hint.get("equal_weight"))
        if equal_weight is None:
            equal_weight = _number(candidate.get("equal_weight"))
        rows.append(
            {
                "status": "reference_preview",
                "stock_code": code,
                "stock_name": _text(candidate.get("stock_name")),
                "sector_name": _text(candidate.get("sector_name")),
                "rank": _number(candidate.get("rank"))
                if _number(candidate.get("rank")) is not None
                else _number(candidate.get("candidate_rank")) or index,
                "signal_kind": _text(candidate.get("signal_kind")),
                "selection_close": _number(candidate.get("selection_close")),
                "score": _number(candidate.get("score")),
                "equal_weight": equal_weight,
                "reference_weight": equal_weight,
                "target_weight": None,
                "target_weight_basis": "position_size_hint.equal_weight"
                if equal_weight is not None
                else None,
                "position_hint": dict(hint) if hint else None,
                "target_block_reason": None,
            }
        )
    return rows


def _apply_target_status(
    target_rows: Sequence[Mapping[str, object]],
    *,
    target_status: str,
    source_gate: Mapping[str, object],
) -> list[dict[str, object]]:
    released = target_status == "reference_preview"
    block_reason = _target_block_reason(
        target_status=target_status,
        source_gate=source_gate,
    )
    return [
        {
            **dict(row),
            "target_weight": row.get("reference_weight") if released else None,
            "target_block_reason": None if released else block_reason,
        }
        for row in target_rows
    ]


def _target_block_reason(
    *,
    target_status: str,
    source_gate: Mapping[str, object],
) -> str | None:
    if target_status == "reference_preview":
        return None
    if target_status == "blocked_source_gate":
        return _text(source_gate.get("primary_blocker_code")) or target_status
    return target_status


def _target_status(
    *,
    source_gate: Mapping[str, object],
    candidate_rows: Sequence[Mapping[str, object]],
    main_status: str,
) -> str:
    if source_gate.get("ready") is not True:
        return "blocked_source_gate"
    if main_status in {"missing", "error"}:
        return "blocked_main_module"
    if not candidate_rows:
        return "blocked_no_candidates"
    return "reference_preview"


def _build_risk_snapshot(
    *,
    builder: ShadowRiskBuilder | None,
    portfolio_id: str,
    as_of_date: str | None,
    target_rows: Sequence[Mapping[str, object]],
    source_gate: Mapping[str, object],
) -> dict[str, object]:
    active_builder = builder or _load_shadow_risk_builder()
    if active_builder is None:
        return {
            "status": "unavailable",
            "basis": "read_only_shadow",
            "portfolio_id": portfolio_id,
            "as_of_date": as_of_date,
            "source_gate_status": source_gate.get("status"),
            "headline": "股票组合风险影子快照暂不可用",
            "metrics": {},
            "warnings": [
                "stock_portfolio_risk_builder_unavailable",
                "Risk snapshot is descriptive only; no formal risk result was produced.",
            ],
        }
    try:
        # A blocked replay closure still permits a descriptive risk preview.
        # Use the explicit target weight when it is released; otherwise use
        # the candidate's equal-weight reference only for this analytical
        # snapshot.  The reference is never copied into ``target``.
        risk_lines = [
            {
                "stock_code": row.get("stock_code"),
                # Do not invent a sector for an incomplete candidate.  The
                # core contract must surface ``missing_sector_name`` and make
                # the descriptive risk snapshot unavailable instead of
                # silently grouping unknown data into a real-looking bucket.
                "sector_name": row.get("sector_name"),
                "target_weight": (
                    row.get("target_weight")
                    if row.get("target_weight") is not None
                    else row.get("reference_weight")
                ),
            }
            for row in target_rows
            if (
                row.get("target_weight") is not None
                or row.get("reference_weight") is not None
            )
        ]
        raw = active_builder(risk_lines)
    # This optional panel reports its own failure and must not break the proposal page.
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "basis": "read_only_shadow",
            "portfolio_id": portfolio_id,
            "as_of_date": as_of_date,
            "source_gate_status": source_gate.get("status"),
            "headline": "股票组合风险影子快照计算失败",
            "metrics": {},
            "warnings": [f"stock_portfolio_risk_builder_failed:{type(exc).__name__}"],
        }
    snapshot = dict(raw)
    snapshot.setdefault("portfolio_id", portfolio_id)
    snapshot.setdefault("as_of_date", as_of_date)
    snapshot.setdefault("source_gate_status", source_gate.get("status"))
    snapshot.setdefault("basis", "read_only_shadow")
    snapshot.setdefault("measurement_basis", "reference_preview")
    snapshot.setdefault("formal_use_allowed", False)
    snapshot.setdefault("warnings", [])
    return snapshot


def _load_shadow_risk_builder() -> ShadowRiskBuilder | None:
    try:
        from backend.app.core_finance.stock_portfolio_risk import (
            compute_stock_portfolio_risk,
        )
    except (ImportError, ModuleNotFoundError):
        return None
    return compute_stock_portfolio_risk


def _warnings(
    *,
    source_gate: Mapping[str, object],
    target_status: str,
    risk_snapshot: Mapping[str, object],
) -> list[str]:
    warnings = [
        "Proposal-only projection; it does not create a trading instruction or approval.",
        "Rebalance remains blocked until a portfolio-scoped current-position contract is available.",
    ]
    if source_gate.get("ready") is not True:
        warnings.append(
            "Source replay closure is not ready; reference rows remain visible but target weights are withheld."
        )
    if target_status != "reference_preview":
        warnings.append(f"Target projection is fail-closed: {target_status}.")
    for warning in _string_list(risk_snapshot.get("warnings")):
        if warning not in warnings:
            warnings.append(warning)
    return warnings


def _issues(
    *,
    source_gate: Mapping[str, object],
    target_status: str,
    main_status: str,
) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    if source_gate.get("ready") is not True:
        issues.append(
            {
                "severity": "blocking",
                "code": "source_gate_not_ready",
                "message": "Replay closure is not ready; target projection is fail-closed.",
                "source": "replay_closure",
                "blocker": source_gate.get("primary_blocker_code"),
            }
        )
    if target_status not in {"reference_preview"}:
        issues.append(
            {
                "severity": "blocking",
                "code": target_status,
                "message": "No formal target is available under the current source contract.",
                "source": "stock_candidates",
            }
        )
    if main_status not in {"ready", "stale"}:
        issues.append(
            {
                "severity": "warning",
                "code": "main_module_not_ready",
                "message": f"Workbench main module status is {main_status}.",
                "source": "workbench.main",
            }
        )
    issues.append(
        {
            "severity": "blocking",
            "code": REBALANCE_BLOCK_REASON,
            "message": "Portfolio-scoped current positions are required before calculating rebalance deltas.",
            "source": "portfolio_scope",
        }
    )
    return issues


def _cache_key(portfolio_id: str, as_of_date: str | None) -> str:
    return f"stock-portfolio-construction:{portfolio_id}:{as_of_date or 'latest'}"


def _validate_portfolio_id(value: str) -> str:
    normalized = str(value or "").strip()
    if normalized != SUPPORTED_PORTFOLIO_ID:
        raise ValueError(f"portfolio_id must be {SUPPORTED_PORTFOLIO_ID} for Phase 2A.")
    return normalized


def _validate_optional_date(value: str | None) -> str | None:
    if value is None or not str(value).strip():
        return None
    normalized = str(value).strip()
    try:
        return date.fromisoformat(normalized).isoformat()
    except ValueError as exc:
        raise ValueError("as_of_date must use YYYY-MM-DD.") from exc


def _mapping(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list_of_mappings(value: object) -> list[dict[str, object]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [str(item) for item in value if str(item).strip()]


def _text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _first_text(*values: object) -> str | None:
    for value in values:
        text = _text(value)
        if text:
            return text
    return None


def _number(value: object) -> float | int | Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Decimal) and not value.is_finite():
        return None
    return value


def _lineage_text(value: object, *, default: str | None = None) -> str | None:
    return _first_text(value, default)


def _enum_text(value: object, *, allowed: set[str], default: str) -> str:
    text = _text(value)
    return text if text in allowed else default
