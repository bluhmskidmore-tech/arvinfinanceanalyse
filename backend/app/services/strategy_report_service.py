"""Walk-forward 样本外验证报告的读取与展示裁剪。

数据源是 `scripts/run_walk_forward_validation.py` 落盘的机器可读报告
(默认 `docs/strategy-reports/walk-forward-first-run.json`，约 264KB)。
本服务只做纯文件读取 + 展示裁剪，不触碰 DuckDB，也不重算任何指标：
所有数值(样本内/外超额、正窗口占比、rpt 漂移统计)均来自报告本身，
仅补充"逐窗样本外超额的中位数/均值"这一层展示聚合。

裁剪目标：每 schedule(即验证 horizon 配置)每策略输出一行摘要，
响应体控制在 50KB 以内，让前端一眼判断"策略样本外是否站得住"。
"""
from __future__ import annotations

import json
import os
import uuid
from collections.abc import Mapping
from pathlib import Path
from statistics import mean, median
from typing import Any

from backend.app.services.formal_result_runtime import (
    build_analytical_result_meta,
    build_formal_result_envelope,
)

RESULT_KIND = "strategy_reports.walk_forward"
RULE_VERSION = "rv_walk_forward_display_trim_v1"
CACHE_VERSION = "cv_walk_forward_display_trim_v1"

#: 允许测试/部署覆盖报告路径；默认取仓库内的首跑报告。
WALK_FORWARD_REPORT_PATH_ENV = "MOSS_WALK_FORWARD_REPORT_PATH"
DEFAULT_WALK_FORWARD_REPORT_PATH = (
    Path(__file__).resolve().parents[3] / "docs" / "strategy-reports" / "walk-forward-first-run.json"
)


def resolve_walk_forward_report_path(report_path: str | Path | None = None) -> Path:
    if report_path is not None:
        return Path(report_path)
    override = os.environ.get(WALK_FORWARD_REPORT_PATH_ENV, "").strip()
    if override:
        return Path(override)
    return DEFAULT_WALK_FORWARD_REPORT_PATH


def load_walk_forward_report(report_path: str | Path | None = None) -> dict[str, Any] | None:
    """读取原始 walk-forward JSON；文件缺失或不可解析时返回 None。"""
    path = resolve_walk_forward_report_path(report_path)
    try:
        raw_text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    try:
        parsed = json.loads(raw_text)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _number(value: object) -> float | int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _round6(value: float | int | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def _sign_consistency_fields(node: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "observed_windows": _number(node.get("observed_windows")),
        "positive_windows": _number(node.get("positive_windows")),
        "negative_windows": _number(node.get("negative_windows")),
        "positive_ratio": _round6(_number(node.get("positive_ratio"))),
    }


def _oos_excess_series(windows: object) -> list[float]:
    values: list[float] = []
    if not isinstance(windows, list):
        return values
    for window in windows:
        value = _number(_mapping(window).get("excess_vs_gate"))
        if value is not None:
            values.append(float(value))
    return values


def _risk_budget_summary(node: Mapping[str, Any]) -> dict[str, Any] | None:
    """rpt(risk-per-trade 预算参数)维度的裁剪：逐窗最优序列 + 漂移统计。"""
    if not node:
        return None
    drift = _mapping(node.get("drift"))
    selected = _mapping(node.get("selected"))
    window_params: list[dict[str, Any]] = []
    windows = node.get("windows")
    if isinstance(windows, list):
        for window in windows:
            row = _mapping(window)
            window_params.append(
                {
                    "window_id": row.get("window_id"),
                    "selected": _number(row.get("selected")),
                    "oracle": _number(row.get("oracle")),
                }
            )
    grid = node.get("grid")
    return {
        "grid": grid if isinstance(grid, list) else [],
        "policy_param": _number(node.get("policy_param")),
        "selected_verdict": selected.get("verdict"),
        "selected_oos_chain_excess": _round6(_number(selected.get("oos_chain_excess"))),
        "window_params": window_params,
        "switch_rate": _round6(_number(drift.get("switch_rate"))),
        "switch_count": _number(drift.get("switch_count")),
        "mode_value": _number(drift.get("mode_value")),
        "mode_share": _round6(_number(drift.get("mode_share"))),
        "observed_windows": _number(drift.get("observed_windows")),
        "distinct_values": _number(drift.get("distinct_values")),
    }


def _strategy_summary(name: str, equal_weight_node: Mapping[str, Any], risk_budget_node: Mapping[str, Any]) -> dict[str, Any]:
    in_sample = _mapping(equal_weight_node.get("in_sample"))
    excess_sign = _mapping(equal_weight_node.get("excess_sign_consistency"))
    decay = _mapping(equal_weight_node.get("decay_cumulative"))
    oos_excess = _oos_excess_series(equal_weight_node.get("windows"))
    return {
        "strategy": name,
        "verdict": equal_weight_node.get("verdict"),
        "verdict_reason": equal_weight_node.get("verdict_reason"),
        "oos_window_count": _number(equal_weight_node.get("oos_window_count")),
        # 样本内为全训练期单值口径(报告未输出逐窗样本内序列)。
        "in_sample_excess": _round6(_number(in_sample.get("excess_vs_gate"))),
        "oos_excess_median": _round6(median(oos_excess)) if oos_excess else None,
        "oos_excess_mean": _round6(mean(oos_excess)) if oos_excess else None,
        "oos_chain_excess": _round6(_number(equal_weight_node.get("oos_chain_excess"))),
        "excess_sign_consistency": _sign_consistency_fields(excess_sign),
        "decay_cumulative_status": decay.get("status"),
        "decay_cumulative_ratio": _round6(_number(decay.get("ratio"))),
        "risk_budget": _risk_budget_summary(_mapping(risk_budget_node)),
    }


def build_walk_forward_summary(raw: Mapping[str, Any]) -> dict[str, Any]:
    """把完整报告裁剪成展示摘要(纯函数，便于合成 JSON 测试)。"""
    schedules_out: list[dict[str, Any]] = []
    schedules = raw.get("schedules")
    for entry in schedules if isinstance(schedules, list) else []:
        entry_map = _mapping(entry)
        schedule = _mapping(entry_map.get("schedule"))
        equal_weight = _mapping(entry_map.get("equal_weight"))
        risk_budget = _mapping(entry_map.get("risk_budget"))
        windows = entry_map.get("windows")
        strategy_names = sorted(set(equal_weight) | set(risk_budget))
        strategies = [
            _strategy_summary(name, _mapping(equal_weight.get(name)), _mapping(risk_budget.get(name)))
            for name in strategy_names
        ]
        schedules_out.append(
            {
                "label": schedule.get("label"),
                "train_months": _number(schedule.get("train_months")),
                "valid_months": _number(schedule.get("valid_months")),
                "step_months": _number(schedule.get("step_months")),
                "objective": schedule.get("objective"),
                "min_windows_for_verdict": _number(schedule.get("min_windows_for_verdict")),
                "window_count": len(windows) if isinstance(windows, list) else 0,
                "strategies": strategies,
            }
        )
    issues = raw.get("issues")
    return {
        "generated_at": raw.get("generated_at"),
        "engine_version": raw.get("engine_version"),
        "mode": raw.get("mode"),
        "issue_count": len(issues) if isinstance(issues, list) else 0,
        "schedules": schedules_out,
    }


def walk_forward_summary_envelope(report_path: str | Path | None = None) -> dict[str, Any] | None:
    """读取 + 裁剪 + 打包 result_meta；报告缺失时返回 None(由路由映射为 404)。"""
    raw = load_walk_forward_report(report_path)
    if raw is None:
        return None
    summary = build_walk_forward_summary(raw)
    engine_version = str(raw.get("engine_version") or "unknown")
    meta = build_analytical_result_meta(
        trace_id=uuid.uuid4().hex,
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        source_version=f"sv_walk_forward_report_{engine_version}",
        rule_version=RULE_VERSION,
        quality_flag="warning" if summary["issue_count"] else "ok",
        generated_at=str(raw.get("generated_at")) if raw.get("generated_at") else None,
    )
    return build_formal_result_envelope(result_meta=meta, result_payload=summary)
