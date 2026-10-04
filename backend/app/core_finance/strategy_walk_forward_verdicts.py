"""Walk-forward out-of-sample verdicts for the page strategy pools.

Source: ``docs/strategy-reports/walk-forward-rerun-20260813.md`` §0.1 / §5
(primary split, equal-weight fixed_20d). These are static report-anchored
facts, not request-time computations: the page must be able to disclose
which strategy pools have (or lack) out-of-sample support without loading
the report. Update this table only when a newer walk-forward rerun lands,
and keep the judgement thresholds of the report (windows < 3 => not
assessable; positive-excess ratio >= 2/3 and chained excess > 0 =>
supported; ratio <= 1/3 or chained excess < 0 => weakened).
"""

from __future__ import annotations

from typing import Any

WALK_FORWARD_VERDICT_CONTRACT_VERSION = "rv_strategy_walk_forward_verdict_v1"
WALK_FORWARD_REPORT = "docs/strategy-reports/walk-forward-rerun-20260813.md"
WALK_FORWARD_JUDGED_AT = "2026-08-13"
WALK_FORWARD_SPLIT = "primary_equal_weight_fixed_20d"

VERDICT_SUPPORTED = "supported"
VERDICT_WEAKENED = "weakened"
VERDICT_NOT_ASSESSABLE = "not_assessable"

_NOT_ASSESSABLE_REASON = "主切割有效验证窗不足 3 个，样本外未被检验。"

_VERDICTS: dict[str, dict[str, Any]] = {
    "stock_candidate": {
        "verdict": VERDICT_WEAKENED,
        "verdict_label": "样本外削弱",
        "oos_windows": 5,
        "positive_excess_windows": 1,
        "chained_excess_return": -0.5458,
        "reason": "5 个验证窗仅 1 窗正超额，链式超额 -54.58%。",
    },
    "theme_breakout": {
        "verdict": VERDICT_SUPPORTED,
        "verdict_label": "样本外支持",
        "oos_windows": 5,
        "positive_excess_windows": 5,
        "chained_excess_return": 1.5378,
        "reason": "5/5 个验证窗正超额，链式超额 +153.78%。",
    },
    "mean_reversion": {
        "verdict": VERDICT_WEAKENED,
        "verdict_label": "样本外削弱",
        "oos_windows": 4,
        "positive_excess_windows": 1,
        "chained_excess_return": -0.117,
        "reason": "4 个验证窗仅 1 窗正超额，链式超额 -11.70%。",
    },
    "uptrend_momentum": {
        "verdict": VERDICT_NOT_ASSESSABLE,
        "verdict_label": "样本外未检验",
        "oos_windows": None,
        "positive_excess_windows": None,
        "chained_excess_return": None,
        "reason": _NOT_ASSESSABLE_REASON,
    },
    "fresh_trend_watchlist": {
        "verdict": VERDICT_NOT_ASSESSABLE,
        "verdict_label": "样本外未检验",
        "oos_windows": None,
        "positive_excess_windows": None,
        "chained_excess_return": None,
        "reason": _NOT_ASSESSABLE_REASON,
    },
    "factor_screen": {
        "verdict": VERDICT_NOT_ASSESSABLE,
        "verdict_label": "样本外未检验",
        "oos_windows": None,
        "positive_excess_windows": None,
        "chained_excess_return": None,
        "reason": _NOT_ASSESSABLE_REASON + "全窗口样本内收益为 -8.06%。",
    },
    "hybrid_fusion": {
        "verdict": VERDICT_NOT_ASSESSABLE,
        "verdict_label": "样本外未检验",
        "oos_windows": None,
        "positive_excess_windows": None,
        "chained_excess_return": None,
        "reason": _NOT_ASSESSABLE_REASON,
    },
}


def walk_forward_verdict(signal_kind: str) -> dict[str, Any] | None:
    """Return the report-anchored walk-forward verdict for a signal kind."""
    entry = _VERDICTS.get(signal_kind)
    if entry is None:
        return None
    return {
        "contract_version": WALK_FORWARD_VERDICT_CONTRACT_VERSION,
        "signal_kind": signal_kind,
        **entry,
        "split": WALK_FORWARD_SPLIT,
        "report": WALK_FORWARD_REPORT,
        "judged_at": WALK_FORWARD_JUDGED_AT,
    }
