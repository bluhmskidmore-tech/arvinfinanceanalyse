from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import pandas as pd

RiskLevel = Literal["green", "yellow", "orange", "red", "unknown"]

_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CONFIG_PATH = _REPO_ROOT / "config" / "a_share_stampede_risk.json"


DEFAULT_A_SHARE_STAMPEDE_RISK_CONFIG: dict[str, Any] = {
    "risk_levels": {
        "green": [0, 29],
        "yellow": [30, 49],
        "orange": [50, 69],
        "red": [70, 100],
    },
    "weights": {
        "breadth": 30,
        "limit_stress": 25,
        "turnover_stress": 15,
        "reversal": 15,
        "theme_crowding": 15,
    },
    "universe": {"include_bse_in_core": False},
    "breadth": {
        "yellow_up_count": 1000,
        "orange_up_count": 700,
        "red_up_count": 500,
        "yellow_up_ratio": 0.25,
        "orange_up_ratio": 0.18,
        "red_up_ratio": 0.12,
        "orange_median_return": -1.5,
        "red_median_return": -2.5,
        "orange_drop_3_ratio": 0.35,
        "red_drop_5_ratio": 0.18,
    },
    "limit_stress": {
        "yellow_limit_down_count": 30,
        "orange_limit_down_count": 50,
        "red_limit_down_count": 80,
        "yellow_down_up_ratio": 1.0,
        "orange_down_up_ratio": 2.0,
        "orange_near_down_count": 100,
    },
    "turnover_stress": {
        "yellow_amount_ratio": 1.3,
        "orange_amount_ratio": 1.5,
        "yellow_index_return": 0.005,
        "orange_index_return": 0.0,
        "red_close_location": 0.2,
    },
    "reversal": {
        "yellow_drawdown": 0.01,
        "orange_drawdown": 0.015,
        "red_drawdown": 0.02,
        "low_close_location": 0.25,
    },
    "theme_crowding": {
        "orange_theme_down_ratio": 0.6,
        "red_theme_down_ratio": 0.75,
        "orange_leader_break_ma5_ratio": 0.5,
    },
    "index_mask": {
        "yellow_up_count": 1500,
        "orange_up_count": 1000,
        "bad_up_ratio": 0.35,
        "bad_median_return": -1.0,
        "stable_index_return_floor": -0.01,
    },
    "position_rules": {
        "green": "正常交易，总仓位按策略自身规则。",
        "yellow": "总仓位上限70%，单一主题上限35%，限制追高，盈利票启用移动止盈。",
        "orange": "总仓位上限50%，单一主题上限25%，高位主线不再加仓，午后不做冲高追买。",
        "red": "总仓位上限30%，高位题材只减不加，不做午后跳水抄底。",
    },
}

_RISK_NAMES: Mapping[str, str] = {
    "green": "绿色风险",
    "yellow": "黄色风险",
    "orange": "橙色风险",
    "red": "红色风险",
    "unknown": "数据不足",
}


@dataclass(frozen=True)
class _CategorySignal:
    score: int = 0
    severe: bool = False
    triggered_rules: list[str] = field(default_factory=list)


def load_a_share_stampede_risk_config(path: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return dict(DEFAULT_A_SHARE_STAMPEDE_RISK_CONFIG)
    try:
        loaded = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_A_SHARE_STAMPEDE_RISK_CONFIG)
    if not isinstance(loaded, dict):
        return dict(DEFAULT_A_SHARE_STAMPEDE_RISK_CONFIG)
    return _deep_merge(DEFAULT_A_SHARE_STAMPEDE_RISK_CONFIG, loaded)


def compute_a_share_stampede_risk(
    observations: pd.DataFrame,
    *,
    config: Mapping[str, Any] | None = None,
    theme_frame: pd.DataFrame | None = None,
) -> dict[str, Any]:
    active_config = _deep_merge(DEFAULT_A_SHARE_STAMPEDE_RISK_CONFIG, dict(config or {}))
    frame = _clean_observations(observations)
    if frame.empty:
        return _unavailable_payload("choice_stock_daily_observation 无可用日线股票观察。")

    latest_date = frame["trade_date"].max()
    latest = frame[frame["trade_date"] == latest_date].copy()
    if latest.empty:
        return _unavailable_payload("choice_stock_daily_observation 最新交易日无可用股票观察。")

    latest = _apply_universe_flags(latest)
    core = latest[latest["core_eligible"]].copy()
    warnings: list[str] = []
    if latest["is_st"].any():
        warnings.append("ST 股票已从普通核心风险统计剔除，并单独统计。")
    if (~latest["has_price_limit"]).any():
        warnings.append("存在无涨跌幅限制股票，已从普通核心风险统计剔除。")
    if latest["is_bse"].any() and not _bool(active_config, "universe", "include_bse_in_core", default=False):
        warnings.append("北交所股票默认不纳入沪深核心风险统计。")
    if core.empty:
        payload = _unavailable_payload("核心股票池为空，无法形成 A 股踩踏风险判断。")
        payload["trade_date"] = latest_date.date().isoformat()
        payload["warnings"] = warnings + payload["warnings"]
        return payload

    history_core = frame[frame["stock_code"].isin(set(core["stock_code"]))].copy()
    metrics = _build_metrics(core, latest, history_core, theme_frame)
    breadth = _score_breadth(metrics, active_config)
    limit_stress = _score_limit_stress(metrics, active_config)
    turnover = _score_turnover(metrics, active_config)
    reversal = _score_reversal(metrics, active_config)
    theme = _score_theme(metrics, active_config)
    index_mask = _score_index_mask(metrics, active_config)

    category_scores = {
        "breadth": breadth.score,
        "limit_stress": limit_stress.score,
        "turnover_stress": turnover.score,
        "reversal": reversal.score,
        "theme_crowding": theme.score,
        "index_mask": index_mask.score,
    }
    risk_score = int(
        min(
            100,
            breadth.score
            + limit_stress.score
            + turnover.score
            + reversal.score
            + theme.score,
        )
    )
    severe_categories = [
        name
        for name, signal in (
            ("breadth_severe", breadth),
            ("limit_stress_severe", limit_stress),
            ("turnover_reversal_severe", _CategorySignal(severe=turnover.severe or reversal.severe)),
            ("theme_severe", theme),
            ("index_mask_severe", index_mask),
        )
        if signal.severe
    ]
    risk_level = _risk_level(risk_score, severe_categories)
    triggered_rules = _dedupe(
        [
            *breadth.triggered_rules,
            *limit_stress.triggered_rules,
            *turnover.triggered_rules,
            *reversal.triggered_rules,
            *theme.triggered_rules,
            *index_mask.triggered_rules,
        ]
    )
    status = "complete"
    if metrics["limit_price_coverage"] < 0.8:
        warnings.append("涨跌停价覆盖不足，跌停压力按可用样本降级计算。")
        status = "degraded"
    if metrics["core_stock_count"] < metrics["valid_stock_count"] * 0.8:
        status = "degraded"
    if theme_frame is None or theme_frame.empty:
        warnings.append("主题拥挤 V1 未命中主题/行业输入，主题项按可用股票行业证据降级。")
        status = "degraded"

    return {
        "trade_date": latest_date.date().isoformat(),
        "status": status,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_name": _RISK_NAMES[risk_level],
        "category_scores": category_scores,
        "severe_categories": severe_categories,
        "summary": _summary(triggered_rules, risk_level),
        "position_rule": _position_rule(risk_level, active_config),
        "metrics": _json_metrics(metrics),
        "triggered_rules": triggered_rules,
        "watch_next": _watch_next(risk_level, metrics),
        "warnings": _dedupe(warnings),
        "tables_used": ["choice_stock_daily_observation"],
    }


def _unavailable_payload(warning: str) -> dict[str, Any]:
    return {
        "trade_date": None,
        "status": "unavailable",
        "risk_score": None,
        "risk_level": "unknown",
        "risk_name": _RISK_NAMES["unknown"],
        "category_scores": {},
        "severe_categories": [],
        "summary": "A股踩踏风险数据不足，当前不能形成风险等级判断。",
        "position_rule": "不输出仓位权限；请先补齐股票日线与涨跌停读面。",
        "metrics": {},
        "triggered_rules": [],
        "watch_next": ["补齐 choice_stock_daily_observation 后重新计算。"],
        "warnings": [warning],
        "tables_used": [],
    }


def _clean_observations(observations: pd.DataFrame) -> pd.DataFrame:
    if observations.empty:
        return pd.DataFrame()
    frame = observations.copy()
    required = ["trade_date", "stock_code", "close_value"]
    if any(column not in frame.columns for column in required):
        return pd.DataFrame()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce")
    frame["stock_code"] = frame["stock_code"].astype(str)
    for column in (
        "open_value",
        "high_value",
        "low_value",
        "close_value",
        "amount",
        "pctchange",
        "highlimit",
        "lowlimit",
    ):
        if column not in frame.columns:
            frame[column] = pd.NA
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in ("is_st", "has_price_limit", "is_bse"):
        if column not in frame.columns:
            frame[column] = False if column != "has_price_limit" else True
        frame[column] = frame[column].map(_coerce_bool)
    return frame.dropna(subset=["trade_date", "stock_code", "close_value"])


def _apply_universe_flags(latest: pd.DataFrame) -> pd.DataFrame:
    out = latest.copy()
    tradestatus = out["tradestatus"].astype(str).str.lower() if "tradestatus" in out.columns else pd.Series("", index=out.index)
    is_suspended = tradestatus.str.contains("停牌|suspend|halt", regex=True, na=False)
    out["core_eligible"] = (
        ~out["is_st"].astype(bool)
        & out["has_price_limit"].astype(bool)
        & ~out["is_bse"].astype(bool)
        & ~is_suspended
    )
    return out


def _build_metrics(
    core: pd.DataFrame,
    latest: pd.DataFrame,
    history_core: pd.DataFrame,
    theme_frame: pd.DataFrame | None,
) -> dict[str, float | int | None]:
    pct = pd.to_numeric(core["pctchange"], errors="coerce").dropna()
    valid_stock_count = int(len(latest))
    core_stock_count = int(len(core))
    up_count = int((pct > 0).sum())
    down_count = int((pct < 0).sum())
    flat_count = int((pct == 0).sum())
    drop_3_count = int((pct <= -3).sum())
    drop_5_count = int((pct <= -5).sum())
    up_limit = pd.to_numeric(core["highlimit"], errors="coerce")
    down_limit = pd.to_numeric(core["lowlimit"], errors="coerce")
    close = pd.to_numeric(core["close_value"], errors="coerce")
    has_limit_price = up_limit.notna() & down_limit.notna() & (up_limit > 0) & (down_limit > 0)
    is_limit_down = has_limit_price & (close <= down_limit * 1.001)
    is_limit_up = has_limit_price & (close >= up_limit * 0.999)
    if "is_limit_down_flag" in core.columns:
        flag = core["is_limit_down_flag"].map(_coerce_bool)
        is_limit_down = is_limit_down | flag
        has_limit_price = has_limit_price | flag
    if "is_limit_up_flag" in core.columns:
        flag = core["is_limit_up_flag"].map(_coerce_bool)
        is_limit_up = is_limit_up | flag
        has_limit_price = has_limit_price | flag
    is_near_down = has_limit_price & ~is_limit_down & (close <= down_limit * 1.003)
    st_latest = latest[latest["is_st"].astype(bool)]
    st_lowlimit = pd.to_numeric(st_latest.get("lowlimit", pd.Series(dtype=float)), errors="coerce")
    st_close = pd.to_numeric(st_latest.get("close_value", pd.Series(dtype=float)), errors="coerce")
    st_limit_down_count = int(((st_lowlimit.notna()) & (st_close <= st_lowlimit * 1.001)).sum())
    daily_amount = history_core.groupby("trade_date")["amount"].sum(min_count=1).dropna().sort_index()
    market_amount = float(daily_amount.iloc[-1]) if not daily_amount.empty else None
    amount_ma20 = float(daily_amount.tail(20).mean()) if len(daily_amount) >= 2 else None
    amount_ratio = market_amount / amount_ma20 if market_amount is not None and amount_ma20 and amount_ma20 > 0 else None
    index_series = history_core.groupby("trade_date")["close_value"].mean().dropna().sort_index()
    index_return = None
    if len(index_series) >= 2 and float(index_series.iloc[-2]) > 0:
        index_return = float(index_series.iloc[-1] / index_series.iloc[-2] - 1)
    high = pd.to_numeric(core["high_value"], errors="coerce")
    low = pd.to_numeric(core["low_value"], errors="coerce")
    avg_high = float(high.mean()) if high.notna().any() else None
    avg_low = float(low.mean()) if low.notna().any() else None
    avg_close = float(close.mean()) if close.notna().any() else None
    drawdown_from_high = None
    close_location = None
    if avg_high and avg_high > 0 and avg_close is not None:
        drawdown_from_high = max(0.0, avg_high / avg_close - 1)
    if avg_high is not None and avg_low is not None and avg_close is not None and avg_high > avg_low:
        close_location = (avg_close - avg_low) / (avg_high - avg_low)
    theme_metrics = _theme_metrics(core, theme_frame)
    return {
        "valid_stock_count": valid_stock_count,
        "core_stock_count": core_stock_count,
        "up_count": up_count,
        "down_count": down_count,
        "flat_count": flat_count,
        "up_ratio": _ratio(up_count, core_stock_count),
        "median_return": float(pct.median()) if not pct.empty else None,
        "drop_3_count": drop_3_count,
        "drop_5_count": drop_5_count,
        "drop_3_ratio": _ratio(drop_3_count, core_stock_count),
        "drop_5_ratio": _ratio(drop_5_count, core_stock_count),
        "limit_down_count": int(is_limit_down.sum()),
        "limit_up_count": int(is_limit_up.sum()),
        "limit_down_up_ratio": int(is_limit_down.sum()) / max(int(is_limit_up.sum()), 1),
        "near_down_count": int(is_near_down.sum()),
        "limit_price_coverage": _ratio(int(has_limit_price.sum()), core_stock_count),
        "st_limit_down_count": st_limit_down_count,
        "no_limit_stock_count": int((~latest["has_price_limit"].astype(bool)).sum()),
        "bse_stock_count": int(latest["is_bse"].astype(bool).sum()),
        "market_amount": market_amount,
        "amount_ma20": amount_ma20,
        "turnover_ratio_ma20": amount_ratio,
        "index_return": index_return,
        "index_drawdown_from_high": drawdown_from_high,
        "close_location": close_location,
        **theme_metrics,
    }


def _theme_metrics(core: pd.DataFrame, theme_frame: pd.DataFrame | None) -> dict[str, float | int | None]:
    if theme_frame is None or theme_frame.empty or "stock_code" not in theme_frame.columns:
        return {
            "hot_theme_down_ratio": None,
            "leader_break_ma5_ratio": None,
            "theme_member_count": 0,
        }
    joined = core.merge(theme_frame, on="stock_code", how="inner")
    if joined.empty:
        return {
            "hot_theme_down_ratio": None,
            "leader_break_ma5_ratio": None,
            "theme_member_count": 0,
        }
    pct = pd.to_numeric(joined["pctchange"], errors="coerce").dropna()
    leaders = joined[joined.get("is_leader", False).astype(bool)] if "is_leader" in joined.columns else joined.head(0)
    leader_break = 0
    if not leaders.empty and "close_value" in leaders.columns and "ma5" in leaders.columns:
        leader_break = int((pd.to_numeric(leaders["close_value"], errors="coerce") < pd.to_numeric(leaders["ma5"], errors="coerce")).sum())
    return {
        "hot_theme_down_ratio": _ratio(int((pct < 0).sum()), len(pct)) if len(pct) else None,
        "leader_break_ma5_ratio": _ratio(leader_break, len(leaders)) if len(leaders) else None,
        "theme_member_count": int(len(joined)),
    }


def _score_breadth(metrics: Mapping[str, Any], config: Mapping[str, Any]) -> _CategorySignal:
    score = 0
    rules: list[str] = []
    severe = False
    up_count = _number(metrics.get("up_count"), 0)
    up_ratio = _number(metrics.get("up_ratio"), 1)
    median_return = metrics.get("median_return")
    drop_3_ratio = _number(metrics.get("drop_3_ratio"), 0)
    drop_5_ratio = _number(metrics.get("drop_5_ratio"), 0)
    if up_count < _number(_cfg(config, "breadth", "red_up_count"), 500) or up_ratio < _number(_cfg(config, "breadth", "red_up_ratio"), 0.12):
        score = 30
        severe = True
        rules.append(f"上涨家数低于{int(_cfg(config, 'breadth', 'red_up_count') or 500)}或上涨比例低于红色阈值")
    elif up_count < _number(_cfg(config, "breadth", "orange_up_count"), 700) or up_ratio < _number(_cfg(config, "breadth", "orange_up_ratio"), 0.18):
        score = 24
        severe = True
        rules.append("上涨家数低于700或上涨比例低于18%")
    elif up_count < _number(_cfg(config, "breadth", "yellow_up_count"), 1000) or up_ratio < _number(_cfg(config, "breadth", "yellow_up_ratio"), 0.25):
        score = 15
        rules.append("上涨家数低于1000或上涨比例低于25%")
    if median_return is not None and float(median_return) < _number(_cfg(config, "breadth", "red_median_return"), -2.5):
        score = max(score, 30)
        severe = True
        rules.append("涨跌幅中位数低于-2.5%")
    elif median_return is not None and float(median_return) < _number(_cfg(config, "breadth", "orange_median_return"), -1.5):
        score = max(score, 24)
        severe = True
        rules.append("涨跌幅中位数低于-1.5%")
    if drop_5_ratio > _number(_cfg(config, "breadth", "red_drop_5_ratio"), 0.18):
        score = max(score, 30)
        severe = True
        rules.append("跌超5%比例超过18%")
    elif drop_3_ratio > _number(_cfg(config, "breadth", "orange_drop_3_ratio"), 0.35):
        score = max(score, 24)
        severe = True
        rules.append("跌超3%比例超过35%")
    return _CategorySignal(score=score, severe=severe, triggered_rules=rules)


def _score_limit_stress(metrics: Mapping[str, Any], config: Mapping[str, Any]) -> _CategorySignal:
    limit_down = _number(metrics.get("limit_down_count"), 0)
    ratio = _number(metrics.get("limit_down_up_ratio"), 0)
    near_down = _number(metrics.get("near_down_count"), 0)
    score = 0
    rules: list[str] = []
    severe = False
    if limit_down > _number(_cfg(config, "limit_stress", "red_limit_down_count"), 80):
        score = 25
        severe = True
        rules.append("跌停家数超过80")
    elif limit_down > _number(_cfg(config, "limit_stress", "orange_limit_down_count"), 50):
        score = 21
        severe = True
        rules.append("跌停家数超过50")
    elif limit_down > _number(_cfg(config, "limit_stress", "yellow_limit_down_count"), 30):
        score = 13
        rules.append("跌停家数超过30")
    if ratio > _number(_cfg(config, "limit_stress", "orange_down_up_ratio"), 2.0):
        score = max(score, 21)
        severe = True
        rules.append("跌停/涨停比超过2")
    elif ratio > _number(_cfg(config, "limit_stress", "yellow_down_up_ratio"), 1.0):
        score = max(score, 13)
        rules.append("跌停/涨停比超过1")
    if near_down > _number(_cfg(config, "limit_stress", "orange_near_down_count"), 100):
        score = max(score, 21)
        severe = True
        rules.append("近跌停家数超过100")
    return _CategorySignal(score=score, severe=severe, triggered_rules=rules)


def _score_turnover(metrics: Mapping[str, Any], config: Mapping[str, Any]) -> _CategorySignal:
    amount_ratio = metrics.get("turnover_ratio_ma20")
    index_return = metrics.get("index_return")
    close_location = metrics.get("close_location")
    if amount_ratio is None or index_return is None:
        return _CategorySignal()
    if (
        float(amount_ratio) > _number(_cfg(config, "turnover_stress", "orange_amount_ratio"), 1.5)
        and float(index_return) < _number(_cfg(config, "turnover_stress", "orange_index_return"), 0.0)
    ):
        return _CategorySignal(score=15, severe=True, triggered_rules=["放量下跌：成交额高于20日均量1.5倍且指数收跌"])
    if (
        float(amount_ratio) > _number(_cfg(config, "turnover_stress", "orange_amount_ratio"), 1.5)
        and close_location is not None
        and float(close_location) < _number(_cfg(config, "turnover_stress", "red_close_location"), 0.2)
    ):
        return _CategorySignal(score=15, severe=True, triggered_rules=["放量滞涨：成交额高于20日均量1.5倍且收在低位"])
    if (
        float(amount_ratio) > _number(_cfg(config, "turnover_stress", "yellow_amount_ratio"), 1.3)
        and float(index_return) < _number(_cfg(config, "turnover_stress", "yellow_index_return"), 0.005)
    ):
        return _CategorySignal(score=8, triggered_rules=["放量滞涨：成交额高于20日均量1.3倍但指数推进不足"])
    return _CategorySignal()


def _score_reversal(metrics: Mapping[str, Any], config: Mapping[str, Any]) -> _CategorySignal:
    drawdown = metrics.get("index_drawdown_from_high")
    close_location = metrics.get("close_location")
    if drawdown is None:
        return _CategorySignal()
    if float(drawdown) > _number(_cfg(config, "reversal", "red_drawdown"), 0.02):
        return _CategorySignal(score=15, severe=True, triggered_rules=["指数从日内高点回落超过2%"])
    if (
        float(drawdown) > _number(_cfg(config, "reversal", "orange_drawdown"), 0.015)
        and close_location is not None
        and float(close_location) < _number(_cfg(config, "reversal", "low_close_location"), 0.25)
    ):
        return _CategorySignal(score=12, severe=True, triggered_rules=["指数从日内高点回落超过1.5%且收在低位"])
    if float(drawdown) > _number(_cfg(config, "reversal", "yellow_drawdown"), 0.01):
        return _CategorySignal(score=8, triggered_rules=["指数从日内高点回落超过1%"])
    return _CategorySignal()


def _score_theme(metrics: Mapping[str, Any], config: Mapping[str, Any]) -> _CategorySignal:
    theme_down = metrics.get("hot_theme_down_ratio")
    leader_break = metrics.get("leader_break_ma5_ratio")
    rules: list[str] = []
    score = 0
    severe = False
    if theme_down is not None and float(theme_down) > _number(_cfg(config, "theme_crowding", "red_theme_down_ratio"), 0.75):
        score = 15
        severe = True
        rules.append("热门主线下跌比例超过75%")
    elif theme_down is not None and float(theme_down) > _number(_cfg(config, "theme_crowding", "orange_theme_down_ratio"), 0.6):
        score = 12
        severe = True
        rules.append("热门主线下跌比例超过60%")
    if leader_break is not None and float(leader_break) > _number(_cfg(config, "theme_crowding", "orange_leader_break_ma5_ratio"), 0.5):
        score = max(score, 12)
        severe = True
        rules.append("主题龙头跌破5日线比例超过50%")
    return _CategorySignal(score=score, severe=severe, triggered_rules=rules)


def _score_index_mask(metrics: Mapping[str, Any], config: Mapping[str, Any]) -> _CategorySignal:
    up_count = _number(metrics.get("up_count"), 0)
    up_ratio = _number(metrics.get("up_ratio"), 1)
    median = metrics.get("median_return")
    index_return = metrics.get("index_return")
    breadth_bad = up_ratio < _number(_cfg(config, "index_mask", "bad_up_ratio"), 0.35) or (
        median is not None and float(median) < _number(_cfg(config, "index_mask", "bad_median_return"), -1.0)
    )
    if (
        index_return is not None
        and float(index_return) >= _number(_cfg(config, "index_mask", "stable_index_return_floor"), -0.01)
        and breadth_bad
    ):
        if up_count < _number(_cfg(config, "index_mask", "orange_up_count"), 1000):
            return _CategorySignal(score=0, severe=True, triggered_rules=["指数与宽度背离：指数较稳但上涨家数低于1000"])
        if up_count < _number(_cfg(config, "index_mask", "yellow_up_count"), 1500):
            return _CategorySignal(score=0, triggered_rules=["指数与宽度背离：指数较稳但上涨家数低于1500"])
    return _CategorySignal()


def _risk_level(risk_score: int, severe_categories: list[str]) -> RiskLevel:
    if risk_score >= 70 and len(severe_categories) >= 2:
        return "red"
    if risk_score >= 50:
        return "orange"
    if risk_score >= 30:
        return "yellow"
    return "green"


def _summary(triggered_rules: list[str], risk_level: str) -> str:
    if not triggered_rules:
        return "A股核心宽度和流动性压力未触发主要踩踏风险。"
    if risk_level == "red":
        prefix = "踩踏风险触发"
    elif risk_level == "orange":
        prefix = "拥挤交易松动"
    elif risk_level == "yellow":
        prefix = "市场出现分化"
    else:
        prefix = "风险信号轻微"
    return f"{prefix}：" + " + ".join(triggered_rules[:4])


def _position_rule(risk_level: str, config: Mapping[str, Any]) -> str:
    rules = config.get("position_rules")
    if isinstance(rules, Mapping):
        return str(rules.get(risk_level) or rules.get("unknown") or "")
    return ""


def _watch_next(risk_level: str, metrics: Mapping[str, Any]) -> list[str]:
    if risk_level == "green":
        return ["继续观察上涨家数、跌停家数和成交额是否维持稳定。"]
    return [
        "跌停家数是否收敛到30只以内。",
        "上涨家数是否恢复到1500只以上。",
        "主题核心是否重新站回短期均线。",
        "午后是否再次放量下杀。",
    ]


def _json_metrics(metrics: Mapping[str, Any]) -> dict[str, int | float | None]:
    out: dict[str, int | float | None] = {}
    for key, value in metrics.items():
        if value is None:
            out[key] = None
        elif isinstance(value, (int, float)):
            out[key] = round(float(value), 6) if isinstance(value, float) else int(value)
    return out


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in base.items():
        if isinstance(value, Mapping):
            out[key] = _deep_merge(value, {})
        else:
            out[key] = value
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _cfg(config: Mapping[str, Any], section: str, key: str) -> Any:
    section_value = config.get(section)
    if isinstance(section_value, Mapping):
        return section_value.get(key)
    return None


def _bool(config: Mapping[str, Any], section: str, key: str, *, default: bool) -> bool:
    value = _cfg(config, section, key)
    if value is None:
        return default
    return _coerce_bool(value)


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y", "是", "交易", "trading"}:
        return True
    if text in {"0", "false", "no", "n", "否", "停牌", "suspended"}:
        return False
    return bool(value)


def _number(value: object, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(parsed):
        return default
    return parsed


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out
