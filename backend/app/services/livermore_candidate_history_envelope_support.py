"""Livermore 候选历史：正式结果 envelope 包装与版本常量。

从 livermore_candidate_history_service 门面按行为等价逐字拆出：各类
result envelope 的空/汇总包装函数与 result_kind / rule_version /
cache_version 常量、来源/供应商版本选取辅助。本模块不得导入门面模块。
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any, cast
from backend.app.services.formal_result_runtime import (
    FallbackMode,
    QualityFlag,
    VendorStatus,
    build_result_envelope,
)
from backend.app.services.livermore_candidate_history_read_support import (
    TABLE_HIST,
    TABLE_OBS,
)


EMPTY_SOURCE_VERSION = "sv_livermore_candidate_history_empty"

EMPTY_VENDOR_VERSION = "vv_none"

RESULT_KIND = "market_data.livermore.candidate_history"

RULE_VERSION = "rv_livermore_candidate_history_v1"

CACHE_VERSION = "cv_livermore_candidate_history_v2"

STRATEGY_SCORE_RESULT_KIND = "market_data.livermore.strategy_score"

STRATEGY_SCORE_RULE_VERSION = "rv_livermore_strategy_score_v1"

STRATEGY_SCORE_CACHE_VERSION = "cv_livermore_strategy_score_v1"

STRATEGY_OPTIMIZATION_RESULT_KIND = "market_data.livermore.strategy_optimization"

STRATEGY_OPTIMIZATION_RULE_VERSION = "rv_livermore_strategy_optimization_v1"

STRATEGY_OPTIMIZATION_CACHE_VERSION = "cv_livermore_strategy_optimization_v1"

CYCLE_PROXY_BACKTEST_RESULT_KIND = "market_data.livermore.cycle_proxy_backtest"

CYCLE_PROXY_BACKTEST_RULE_VERSION = "rv_livermore_cycle_proxy_backtest_v1"

CYCLE_PROXY_BACKTEST_CACHE_VERSION = "cv_livermore_cycle_proxy_backtest_v1"

CANDIDATE_HISTORY_PORTFOLIO_BACKTEST_RESULT_KIND = "market_data.livermore.candidate_history_portfolio_backtest"

CANDIDATE_HISTORY_PORTFOLIO_BACKTEST_RULE_VERSION = "rv_livermore_candidate_history_portfolio_backtest_v1"

CANDIDATE_HISTORY_PORTFOLIO_BACKTEST_CACHE_VERSION = "cv_livermore_candidate_history_portfolio_backtest_v1"

def _first_nonempty_source_version(items: list[dict[str, Any]]) -> str:
    for row in items:
        text = str(row.get("source_version") or "").strip()
        if text:
            return text
    return EMPTY_SOURCE_VERSION

def _default_snapshot_from(snapshot_to: str) -> str:
    try:
        parsed = date.fromisoformat(snapshot_to[:10])
    except ValueError:
        parsed = date.today()
    return (parsed - timedelta(days=180)).isoformat()

def _first_nonempty_vendor_version(items: list[dict[str, Any]]) -> str | None:
    for row in items:
        text = str(row.get("vendor_version") or "").strip()
        if text:
            return text
    return None

def _wrap_empty_envelope(*, payload: dict[str, object]) -> dict[str, object]:
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_livermore_candidate_history_{uuid.uuid4().hex[:12]}",
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        source_version=EMPTY_SOURCE_VERSION,
        rule_version=RULE_VERSION,
        quality_flag=cast(QualityFlag, "warning"),
        vendor_version=EMPTY_VENDOR_VERSION,
        vendor_status=cast(VendorStatus, "ok"),
        fallback_mode=cast(FallbackMode, "none"),
        filters_applied={
            "stock_code": payload.get("stock_code"),
            "snapshot_from": payload.get("snapshot_from"),
            "snapshot_to": payload.get("snapshot_to"),
            "limit": payload.get("limit"),
        },
        tables_used=[TABLE_HIST],
        evidence_rows=0,
        result_payload=payload,
    )

def _wrap_strategy_score_envelope(
    *,
    payload: dict[str, object],
    source_version: str,
    vendor_version: str,
    evidence_rows: int,
    quality_flag: str,
) -> dict[str, object]:
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_livermore_strategy_score_{uuid.uuid4().hex[:12]}",
        result_kind=STRATEGY_SCORE_RESULT_KIND,
        cache_version=STRATEGY_SCORE_CACHE_VERSION,
        source_version=source_version,
        rule_version=STRATEGY_SCORE_RULE_VERSION,
        quality_flag=cast(QualityFlag, quality_flag),
        vendor_version=vendor_version or EMPTY_VENDOR_VERSION,
        vendor_status=cast(VendorStatus, "ok"),
        fallback_mode=cast(FallbackMode, "none"),
        filters_applied={
            "snapshot_from": payload.get("snapshot_from"),
            "snapshot_to": payload.get("snapshot_to"),
            "current_market_state": payload.get("current_market_state"),
            "min_sample": payload.get("min_sample"),
            "primary_horizon": payload.get("primary_horizon"),
        },
        tables_used=[TABLE_HIST],
        evidence_rows=evidence_rows,
        result_payload=payload,
    )

def _wrap_strategy_optimization_envelope(
    *,
    payload: dict[str, object],
    source_version: str,
    vendor_version: str,
    evidence_rows: int,
    quality_flag: str,
) -> dict[str, object]:
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_livermore_strategy_optimization_{uuid.uuid4().hex[:12]}",
        result_kind=STRATEGY_OPTIMIZATION_RESULT_KIND,
        cache_version=STRATEGY_OPTIMIZATION_CACHE_VERSION,
        source_version=source_version,
        rule_version=STRATEGY_OPTIMIZATION_RULE_VERSION,
        quality_flag=cast(QualityFlag, quality_flag),
        vendor_version=vendor_version or EMPTY_VENDOR_VERSION,
        vendor_status=cast(VendorStatus, "ok"),
        fallback_mode=cast(FallbackMode, "none"),
        filters_applied={
            "snapshot_from": payload.get("snapshot_from"),
            "snapshot_to": payload.get("snapshot_to"),
            "current_market_state": payload.get("current_market_state"),
            "min_sample": payload.get("min_sample"),
            "primary_horizon": payload.get("primary_horizon"),
        },
        tables_used=[TABLE_HIST],
        evidence_rows=evidence_rows,
        result_payload=payload,
    )

def _wrap_cycle_proxy_backtest_envelope(
    *,
    payload: dict[str, object],
    source_version: str,
    vendor_version: str,
    evidence_rows: int,
    quality_flag: str,
    tables_used: list[str] | None = None,
) -> dict[str, object]:
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_livermore_cycle_proxy_backtest_{uuid.uuid4().hex[:12]}",
        result_kind=CYCLE_PROXY_BACKTEST_RESULT_KIND,
        cache_version=CYCLE_PROXY_BACKTEST_CACHE_VERSION,
        source_version=source_version,
        rule_version=CYCLE_PROXY_BACKTEST_RULE_VERSION,
        quality_flag=cast(QualityFlag, quality_flag),
        vendor_version=vendor_version or EMPTY_VENDOR_VERSION,
        vendor_status=cast(VendorStatus, "ok"),
        fallback_mode=cast(FallbackMode, "none"),
        filters_applied={
            "snapshot_from": payload.get("snapshot_from"),
            "snapshot_to": payload.get("snapshot_to"),
            "proxy_signal_kind": payload.get("proxy_signal_kind"),
        },
        tables_used=tables_used or [TABLE_HIST],
        evidence_rows=evidence_rows,
        result_payload=payload,
    )

def _wrap_candidate_history_portfolio_backtest_envelope(
    *,
    payload: dict[str, object],
    source_version: str,
    vendor_version: str,
    evidence_rows: int,
    quality_flag: str,
    tables_used: list[str] | None = None,
) -> dict[str, object]:
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_livermore_candidate_history_portfolio_backtest_{uuid.uuid4().hex[:12]}",
        result_kind=CANDIDATE_HISTORY_PORTFOLIO_BACKTEST_RESULT_KIND,
        cache_version=CANDIDATE_HISTORY_PORTFOLIO_BACKTEST_CACHE_VERSION,
        source_version=source_version,
        rule_version=CANDIDATE_HISTORY_PORTFOLIO_BACKTEST_RULE_VERSION,
        quality_flag=cast(QualityFlag, quality_flag),
        vendor_version=vendor_version or EMPTY_VENDOR_VERSION,
        vendor_status=cast(VendorStatus, "ok"),
        fallback_mode=cast(FallbackMode, "none"),
        filters_applied={
            "snapshot_from": payload.get("snapshot_from"),
            "snapshot_to": payload.get("snapshot_to"),
            "signal_kind": payload.get("signal_kind"),
            "rebalance_rule": payload.get("rebalance_rule"),
        },
        tables_used=tables_used or [TABLE_HIST, TABLE_OBS],
        evidence_rows=evidence_rows,
        result_payload=payload,
    )
