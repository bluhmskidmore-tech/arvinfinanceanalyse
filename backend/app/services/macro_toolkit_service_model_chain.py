"""宏观工具箱模型链结果拼装（观察口径只读面）。

代码自 macro_toolkit_service.py 门面拆分逐字迁入；语义与行为不变。
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pandas as pd
from backend.app.core_finance.macro.toolkit.paths import OUTPUT_DIR
from backend.app.services.macro_toolkit_service_support import (
    MACRO_TOOLKIT_FORMAL_USE_ALLOWED,
    MACRO_TOOLKIT_OBSERVATION_ONLY,
    MACRO_TOOLKIT_OUTPUT_DATE_COLUMNS,
    _float_or_none,
)


# ---------------------------------------------------------------------------
# Model chain results (observation-only read surface over artifact CSVs)
# ---------------------------------------------------------------------------

_MODEL_CHAIN_MISSING_HEADLINE = "产物缺失"
_MODEL_CHAIN_DETAIL_HEADLINE = "详见明细"
_MODEL_CHAIN_NA_TEXT = "—"
_MODEL_CHAIN_FINAL_SIGNAL_ARTIFACT = "final_signal.csv"
# dcc_latest.csv 宽表中除配对列以外的元信息列。
_MODEL_CHAIN_DCC_META_COLUMNS = ("日期", "平均相关系数", "预警状态")


def _model_chain_cell_text(value: object) -> str:
    """Render one CSV cell as display text; NaN/blank become the em-dash placeholder."""
    if value is None:
        return _MODEL_CHAIN_NA_TEXT
    try:
        if pd.isna(value):
            return _MODEL_CHAIN_NA_TEXT
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text if text else _MODEL_CHAIN_NA_TEXT


def _model_chain_contains(value: object, keyword: str) -> bool:
    text = _model_chain_cell_text(value)
    if text == _MODEL_CHAIN_NA_TEXT:
        return False
    return keyword in text


def _model_chain_max_row(frame: pd.DataFrame, column: str) -> pd.Series | None:
    """Row holding the largest parseable numeric value in ``column``; None when nothing parses."""
    if column not in frame.columns:
        return None
    best_row: pd.Series | None = None
    best_value: float | None = None
    for _, row in frame.iterrows():
        parsed = _float_or_none(row.get(column))
        if parsed is None:
            continue
        if best_value is None or parsed > best_value:
            best_value = parsed
            best_row = row
    return best_row


def _load_model_chain_frame(path: Path) -> pd.DataFrame | None:
    """Load one artifact CSV keeping every value as its original text; None when missing/empty/unreadable."""
    if not path.is_file():
        return None
    try:
        frame = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    except (OSError, UnicodeError, ValueError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return None
    if frame.empty:
        return None
    return frame


def _model_chain_latest_date_text(frame: pd.DataFrame) -> str | None:
    date_column = next(
        (column for column in MACRO_TOOLKIT_OUTPUT_DATE_COLUMNS if column in frame.columns),
        None,
    )
    if date_column is None:
        return None
    texts = [
        text
        for text in (_model_chain_cell_text(value) for value in frame[date_column])
        if text != _MODEL_CHAIN_NA_TEXT
    ]
    if not texts:
        return None
    # 产物日期均为 ISO 风格（YYYY-MM / YYYY-MM-DD），字符串序即时间序；保留原始文本粒度。
    return max(texts)


def _model_chain_as_of(frame: pd.DataFrame, path: Path) -> str | None:
    latest = _model_chain_latest_date_text(frame)
    if latest is not None:
        return latest
    try:
        modified_at = path.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(modified_at, UTC).date().isoformat()


def _model_chain_table(
    frame: pd.DataFrame,
    model_def: Mapping[str, object],
) -> tuple[list[str], list[list[str]]]:
    mode = str(model_def.get("table_mode") or "select")
    if mode == "dcc_pairs":
        # dcc_latest.csv 是单行宽表：把 10 个配对列转置成「资产对/相关系数」两列表格，取最末行为最新值。
        pair_columns = [
            str(column) for column in frame.columns if str(column) not in _MODEL_CHAIN_DCC_META_COLUMNS
        ]
        latest = frame.iloc[-1]
        return ["资产对", "相关系数"], [
            [column, _model_chain_cell_text(latest.get(column))] for column in pair_columns
        ]
    if mode == "all":
        selected = [(str(column), str(column)) for column in frame.columns]
    else:
        declared = model_def.get("columns") or ()
        # 列名以产物文件实际表头为准；声明列缺失时跳过该列，保持 columns 与 rows 对齐。
        selected = [
            (str(source), str(label))
            for source, label in declared
            if str(source) in frame.columns
        ]
    if mode == "tail":
        # 事件日志类产物随时间累积，仅展示尾部窗口（保持行序，最新在最后）。
        tail_rows = int(model_def.get("tail_rows") or _MODEL_CHAIN_MONITOR_LOG_TAIL_ROWS)
        frame = frame.tail(tail_rows)
    columns = [label for _, label in selected]
    rows = [
        [_model_chain_cell_text(row.get(source)) for source, _ in selected]
        for _, row in frame.iterrows()
    ]
    return columns, rows


def _model_chain_merrill_headline(frame: pd.DataFrame) -> str:
    # *_latest.csv 为单行产物；多行时取最末行为最新，不重排。
    row = frame.iloc[-1]
    quadrant = _model_chain_cell_text(row.get("传统象限"))
    direction = _model_chain_cell_text(row.get("bond_direction"))
    return f"象限 {quadrant} · 债券方向 {direction}"


def _model_chain_garch_headline(frame: pd.DataFrame) -> str:
    if "波动率状态" not in frame.columns:
        return _MODEL_CHAIN_DETAIL_HEADLINE
    high_count = sum(1 for value in frame["波动率状态"] if _model_chain_contains(value, "高波动"))
    top_row = _model_chain_max_row(frame, "年化波动率%")
    if top_row is None:
        return _MODEL_CHAIN_DETAIL_HEADLINE
    asset = _model_chain_cell_text(top_row.get("资产"))
    volatility = _model_chain_cell_text(top_row.get("年化波动率%"))
    return f"高波动 {high_count}/{len(frame)} · 最高 {asset} {volatility}%"


def _model_chain_dcc_headline(frame: pd.DataFrame) -> str:
    row = frame.iloc[-1]
    average = _model_chain_cell_text(row.get("平均相关系数"))
    status = _model_chain_cell_text(row.get("预警状态"))
    return f"平均相关 {average} · {status}"


def _model_chain_regime_headline(frame: pd.DataFrame) -> str:
    if "当前状态" not in frame.columns:
        return _MODEL_CHAIN_DETAIL_HEADLINE
    high_count = sum(1 for value in frame["当前状态"] if _model_chain_contains(value, "高波动"))
    return f"高波动 {high_count}/{len(frame)}"


def _model_chain_cta_headline(frame: pd.DataFrame) -> str:
    if "操作建议" not in frame.columns or "资产" not in frame.columns:
        return _MODEL_CHAIN_DETAIL_HEADLINE

    def _assets_for(keyword: str) -> str:
        assets = [
            _model_chain_cell_text(row.get("资产"))
            for _, row in frame.iterrows()
            if _model_chain_contains(row.get("操作建议"), keyword)
        ]
        return "、".join(assets) if assets else "无"

    return f"强多头 {_assets_for('强多头')} · 强空头 {_assets_for('强空头')}"


def _model_chain_risk_parity_headline(frame: pd.DataFrame) -> str:
    top_row = _model_chain_max_row(frame, "风险平价权重%")
    if top_row is None:
        return _MODEL_CHAIN_DETAIL_HEADLINE
    asset = _model_chain_cell_text(top_row.get("资产"))
    weight = _model_chain_cell_text(top_row.get("风险平价权重%"))
    return f"风险平价最大权重 {asset} {weight}%"


def _model_chain_crisis_headline(frame: pd.DataFrame) -> str:
    row = frame.iloc[-1]
    score = _model_chain_cell_text(row.get("Crisis Score"))
    state = _model_chain_cell_text(row.get("市场状态"))
    return f"{score} · {state}"


def _model_chain_risk_monitor_headline(frame: pd.DataFrame) -> str:
    cooling = _model_chain_cell_text(frame.iloc[-1].get("cooling_until"))
    if cooling == _MODEL_CHAIN_NA_TEXT:
        return "无冷却 · 正常运行"
    return f"冷却至 {cooling}"


_MODEL_CHAIN_MONITOR_LOG_TAIL_ROWS = 6


def _model_chain_monitor_alerts_headline(frame: pd.DataFrame) -> str:
    if "event_type" not in frame.columns:
        return _MODEL_CHAIN_DETAIL_HEADLINE
    tail = frame.tail(_MODEL_CHAIN_MONITOR_LOG_TAIL_ROWS)
    alert_counts: dict[str, int] = {}
    for value in tail["event_type"]:
        text = _model_chain_cell_text(value)
        if text.endswith("_ALERT"):
            alert_counts[text] = alert_counts.get(text, 0) + 1
    if not alert_counts:
        return "近 6 条事件无告警"
    parts = " · ".join(f"{event} {count}" for event, count in alert_counts.items())
    return f"告警 {sum(alert_counts.values())} 条 · {parts}"


def _model_chain_rebalance_headline(frame: pd.DataFrame) -> str:
    top_row = _model_chain_max_row(frame, "夏普比率")
    if top_row is None:
        return _MODEL_CHAIN_DETAIL_HEADLINE
    strategy = _model_chain_cell_text(top_row.get("策略"))
    sharpe = _model_chain_cell_text(top_row.get("夏普比率"))
    return f"最优 {strategy} · 夏普 {sharpe}"


def _model_chain_performance_headline(frame: pd.DataFrame) -> str:
    top_row = _model_chain_max_row(frame, "夏普比率")
    if top_row is None:
        return _MODEL_CHAIN_DETAIL_HEADLINE
    # 第一列即「资产/组合」标识列（以实际表头为准）。
    best = _model_chain_cell_text(top_row.get(str(frame.columns[0])))
    sharpe = _model_chain_cell_text(top_row.get("夏普比率"))
    return f"最佳 {best} · 夏普 {sharpe}"


def _model_chain_backtest_headline(frame: pd.DataFrame) -> str:
    top_row = _model_chain_max_row(frame, "夏普比率")
    if top_row is None:
        return _MODEL_CHAIN_DETAIL_HEADLINE
    strategy = _model_chain_cell_text(top_row.get("策略"))
    sharpe = _model_chain_cell_text(top_row.get("夏普比率"))
    return f"最优 {strategy} · 夏普 {sharpe}"


def _model_chain_final_signal_headline(frame: pd.DataFrame) -> str:
    if "最终信号" not in frame.columns:
        return _MODEL_CHAIN_DETAIL_HEADLINE
    counts: dict[str, int] = {}
    for value in frame["最终信号"]:
        text = _model_chain_cell_text(value)
        if text == _MODEL_CHAIN_NA_TEXT:
            continue
        counts[text] = counts.get(text, 0) + 1
    if not counts:
        return _MODEL_CHAIN_DETAIL_HEADLINE
    total = sum(counts.values())
    if len(counts) == 1:
        value, count = next(iter(counts.items()))
        return f"{value} {count}/{total}"
    return " · ".join(f"{value} {count}" for value, count in counts.items())


# ---------------------------------------------------------------------------
# Model chain trend series (optional per-model history line charts)
# ---------------------------------------------------------------------------

_MODEL_CHAIN_TREND_MAX_POINTS = 120
_MODEL_CHAIN_TREND_SIGNAL_SYMBOLS = ("TS", "TF", "T", "TL")


def _model_chain_trend_column(frame: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    """列名以历史产物实际表头为准：按候选顺序（中文名优先，英文名兜底）取首个存在列。"""
    for name in candidates:
        if str(name) in frame.columns:
            return str(name)
    return None


def _model_chain_trend_points(
    frame: pd.DataFrame, date_column: str, value_column: str
) -> list[list[object]]:
    """按 CSV 行序提取 [日期原文, float 值] 点；数值不可解析或日期空白的行跳过，仅保留尾部 120 点。"""
    points: list[list[object]] = []
    for _, row in frame.iterrows():
        date_text = _model_chain_cell_text(row.get(date_column))
        if date_text == _MODEL_CHAIN_NA_TEXT:
            continue
        value = _float_or_none(row.get(value_column))
        if value is None:
            continue
        points.append([date_text, value])
    return points[-_MODEL_CHAIN_TREND_MAX_POINTS:]


def _model_chain_merrill_trend_series(frame: pd.DataFrame) -> list[dict[str, object]]:
    date_column = _model_chain_trend_column(frame, MACRO_TOOLKIT_OUTPUT_DATE_COLUMNS)
    if date_column is None:
        return []
    series: list[dict[str, object]] = []
    for name, candidates in (
        ("增长动量", ("增长动量", "growth_momentum", "growth")),
        ("通胀动量", ("通胀动量", "inflation_momentum", "inflation")),
        ("流动性动量", ("流动性动量", "liquidity_momentum", "liquidity")),
    ):
        column = _model_chain_trend_column(frame, candidates)
        if column is None:
            continue
        series.append(
            {"name": name, "points": _model_chain_trend_points(frame, date_column, column)}
        )
    return series


def _model_chain_dcc_trend_series(frame: pd.DataFrame) -> list[dict[str, object]]:
    date_column = _model_chain_trend_column(frame, MACRO_TOOLKIT_OUTPUT_DATE_COLUMNS)
    value_column = _model_chain_trend_column(frame, ("平均相关系数", "avg_corr"))
    if date_column is None or value_column is None:
        return []
    return [
        {
            "name": "平均相关系数",
            "points": _model_chain_trend_points(frame, date_column, value_column),
        }
    ]


def _model_chain_crisis_trend_series(frame: pd.DataFrame) -> list[dict[str, object]]:
    date_column = _model_chain_trend_column(frame, MACRO_TOOLKIT_OUTPUT_DATE_COLUMNS)
    value_column = _model_chain_trend_column(frame, ("Crisis Score", "crisis_score"))
    if date_column is None or value_column is None:
        return []
    return [
        {
            "name": "Crisis Score",
            "points": _model_chain_trend_points(frame, date_column, value_column),
        }
    ]


def _model_chain_signal_trend_value(value: object) -> float | None:
    """信号文本数值化：含「多」= +1；含「空仓」或「观望」= 0；含「空」（且非空仓）= -1；其他跳过。"""
    text = _model_chain_cell_text(value)
    if text == _MODEL_CHAIN_NA_TEXT:
        return None
    if "多" in text:
        return 1.0
    if "空仓" in text or "观望" in text:
        return 0.0
    if "空" in text:
        return -1.0
    return None


def _model_chain_final_signal_trend_series(frame: pd.DataFrame) -> list[dict[str, object]]:
    date_column = _model_chain_trend_column(frame, MACRO_TOOLKIT_OUTPUT_DATE_COLUMNS)
    symbol_column = _model_chain_trend_column(frame, ("品种", "symbol"))
    signal_column = _model_chain_trend_column(frame, ("最终信号", "final_signal"))
    if date_column is None or symbol_column is None or signal_column is None:
        return []
    series: list[dict[str, object]] = []
    for symbol in _MODEL_CHAIN_TREND_SIGNAL_SYMBOLS:
        points: list[list[object]] = []
        for _, row in frame.iterrows():
            if _model_chain_cell_text(row.get(symbol_column)) != symbol:
                continue
            date_text = _model_chain_cell_text(row.get(date_column))
            if date_text == _MODEL_CHAIN_NA_TEXT:
                continue
            value = _model_chain_signal_trend_value(row.get(signal_column))
            if value is None:
                continue
            points.append([date_text, value])
        series.append({"name": symbol, "points": points[-_MODEL_CHAIN_TREND_MAX_POINTS:]})
    return series


def _model_chain_trend_payload(
    model_def: Mapping[str, object],
    *,
    output_dir: Path,
) -> dict[str, object] | None:
    """构建模型卡 trend 序列；无 trend 数据源 / 历史文件缺失或损坏 / 每条线有效点 <2 → None，不抛错。"""
    trend_def = model_def.get("trend")
    if not isinstance(trend_def, Mapping):
        return None
    frame = _load_model_chain_frame(output_dir / str(trend_def["artifact"]))
    if frame is None:
        return None
    series_builder = cast(
        "Callable[[pd.DataFrame], list[dict[str, object]]]", trend_def["series"]
    )
    series: list[dict[str, object]] = []
    for item in series_builder(frame):
        points = item.get("points")
        if isinstance(points, list) and len(points) >= 2:
            series.append(item)
    if not series:
        return None
    return {"label": str(trend_def["label"]), "series": series}


_MODEL_CHAIN_STEP_DEFINITIONS: tuple[dict[str, object], ...] = (
    {
        "key": "market_state",
        "step_no": 1,
        "label": "市场状态识别",
        "models": (
            {
                "id": "merrill_clock",
                "label": "美林时钟（中国版）",
                "script_name": "merrill_clock_cn",
                "artifact": "merrill_clock_latest.csv",
                "table_mode": "select",
                "columns": (
                    ("日期", "日期"),
                    ("增长动量", "增长动量"),
                    ("通胀动量", "通胀动量"),
                    ("流动性动量", "流动性动量"),
                    ("传统象限", "传统象限"),
                    ("bond_direction", "债券方向"),
                ),
                "headline": _model_chain_merrill_headline,
                "trend": {
                    "artifact": "merrill_clock_history.csv",
                    "label": "三维动量（月度）",
                    "series": _model_chain_merrill_trend_series,
                },
            },
            {
                "id": "garch",
                "label": "GARCH 波动率",
                "script_name": "garch_multi_asset",
                "artifact": "garch_results.csv",
                "table_mode": "select",
                "columns": (
                    ("资产", "资产"),
                    ("最优模型", "最优模型"),
                    ("年化波动率%", "年化波动率%"),
                    ("波动率状态", "波动率状态"),
                    ("操作建议", "操作建议"),
                ),
                "headline": _model_chain_garch_headline,
            },
            {
                "id": "dcc_garch",
                "label": "DCC-GARCH 动态相关",
                "script_name": "dcc_garch_cn",
                "artifact": "dcc_latest.csv",
                "table_mode": "dcc_pairs",
                "headline": _model_chain_dcc_headline,
                "trend": {
                    "artifact": "dcc_results.csv",
                    "label": "平均相关系数（日度）",
                    "series": _model_chain_dcc_trend_series,
                },
            },
            {
                "id": "regime",
                "label": "市场状态转换",
                "script_name": "regime_switch_cn",
                "artifact": "regime_results.csv",
                "table_mode": "select",
                "columns": (
                    ("资产", "资产"),
                    ("当前状态", "当前状态"),
                    ("策略建议", "策略建议"),
                    ("年化波动率%", "年化波动率%"),
                ),
                "headline": _model_chain_regime_headline,
            },
        ),
    },
    {
        "key": "strategy_selection",
        "step_no": 2,
        "label": "策略选择",
        "models": (
            {
                "id": "cta_trend",
                "label": "CTA 趋势跟踪",
                "script_name": "cta_trend_cn",
                "artifact": "cta_results.csv",
                "table_mode": "select",
                "columns": (
                    ("资产", "资产"),
                    ("合成信号", "合成信号"),
                    ("趋势强度", "趋势强度"),
                    ("操作建议", "操作建议"),
                    ("策略年化收益%", "策略年化收益%"),
                    ("策略夏普比率", "策略夏普比率"),
                    ("止损次数", "止损次数"),
                    ("减仓天数", "减仓天数"),
                ),
                "headline": _model_chain_cta_headline,
            },
        ),
    },
    {
        "key": "allocation",
        "step_no": 3,
        "label": "资产配置",
        "models": (
            {
                "id": "risk_parity",
                "label": "风险平价 + 风险预算",
                "script_name": "risk_parity_cn",
                "artifact": "risk_parity_results.csv",
                "table_mode": "select",
                "columns": (
                    ("资产", "资产"),
                    ("风险平价权重%", "风险平价权重%"),
                    ("风险预算权重%", "风险预算权重%"),
                    ("年化波动率%", "年化波动率%"),
                ),
                "headline": _model_chain_risk_parity_headline,
            },
        ),
    },
    {
        "key": "risk_management",
        "step_no": 4,
        "label": "风险管理",
        "models": (
            {
                "id": "crisis_score",
                "label": "Crisis Score 危机评分",
                "script_name": "crisis_score_cn",
                "artifact": "crisis_score_latest.csv",
                "table_mode": "all",
                "headline": _model_chain_crisis_headline,
                "trend": {
                    "artifact": "crisis_score_history.csv",
                    "label": "危机评分（日度）",
                    "series": _model_chain_crisis_trend_series,
                },
            },
            {
                "id": "risk_monitor",
                "label": "导航仪风控",
                "script_name": "risk_monitor",
                "artifact": "risk_state.csv",
                "table_mode": "all",
                "headline": _model_chain_risk_monitor_headline,
            },
            {
                "id": "monitor_alerts",
                "label": "导航仪监测告警",
                "script_name": "risk_monitor",
                "artifact": "risk_log.csv",
                # 事件日志随时间累积，只展示尾部窗口。
                "table_mode": "tail",
                "tail_rows": _MODEL_CHAIN_MONITOR_LOG_TAIL_ROWS,
                "columns": (
                    ("datetime", "时间"),
                    ("event_type", "事件"),
                    ("symbol", "对象"),
                    ("detail", "说明"),
                ),
                "headline": _model_chain_monitor_alerts_headline,
            },
        ),
    },
    {
        "key": "rebalance",
        "step_no": 5,
        "label": "再平衡",
        "models": (
            {
                "id": "rebalance",
                "label": "再平衡策略对比",
                "script_name": "rebalance_cn",
                "artifact": "rebalance_results.csv",
                "table_mode": "select",
                "columns": (
                    ("策略", "策略"),
                    ("年化收益%", "年化收益%"),
                    ("年化波动%", "年化波动%"),
                    ("夏普比率", "夏普比率"),
                    ("再平衡次数", "再平衡次数"),
                    ("累计收益%", "累计收益%"),
                ),
                "headline": _model_chain_rebalance_headline,
            },
        ),
    },
    {
        "key": "performance",
        "step_no": 6,
        "label": "绩效评估",
        "models": (
            {
                "id": "performance",
                "label": "夏普/索提诺绩效",
                "script_name": "performance_metrics_cn",
                "artifact": "performance_results.csv",
                "table_mode": "all",
                "headline": _model_chain_performance_headline,
            },
            {
                "id": "backtest",
                "label": "策略回测",
                "script_name": "backtest_cn",
                "artifact": "backtest_results.csv",
                "table_mode": "select",
                # 契约要求“策略名 + 年化收益/夏普/最大回撤/胜率/累计收益”；
                # 按实际表头映射为：策略/年化收益%/夏普比率/最大回撤%/胜率%/累计收益%。
                "columns": (
                    ("策略", "策略"),
                    ("年化收益%", "年化收益%"),
                    ("夏普比率", "夏普比率"),
                    ("最大回撤%", "最大回撤%"),
                    ("胜率%", "胜率%"),
                    ("累计收益%", "累计收益%"),
                ),
                "headline": _model_chain_backtest_headline,
            },
        ),
    },
    {
        "key": "final_signal",
        "step_no": 7,
        "label": "决策链输出",
        "models": (
            {
                "id": "final_signal",
                "label": "最终信号聚合",
                "script_name": "signal_aggregator",
                "artifact": _MODEL_CHAIN_FINAL_SIGNAL_ARTIFACT,
                "table_mode": "select",
                "columns": (
                    ("品种", "品种"),
                    ("日期", "日期"),
                    ("第一层_方向", "第一层_方向"),
                    ("最终信号", "最终信号"),
                    ("仓位比例", "仓位比例"),
                    ("置信度", "置信度"),
                    ("信号说明", "信号说明"),
                ),
                "headline": _model_chain_final_signal_headline,
                "trend": {
                    "artifact": "final_signal_history.csv",
                    "label": "信号轨迹（+1 多 / 0 观望 / -1 空）",
                    "series": _model_chain_final_signal_trend_series,
                },
            },
        ),
    },
)


def _model_chain_model_payload(
    model_def: Mapping[str, object],
    *,
    output_dir: Path,
) -> dict[str, object]:
    artifact = str(model_def["artifact"])
    payload: dict[str, object] = {
        "id": model_def["id"],
        "label": model_def["label"],
        "script_name": model_def["script_name"],
        "artifact": artifact,
        # trend 独立于快照产物：全部模型恒有该键（无历史数据源时为 None），保证前端类型统一。
        "trend": _model_chain_trend_payload(model_def, output_dir=output_dir),
    }
    path = output_dir / artifact
    frame = _load_model_chain_frame(path)
    if frame is None:
        payload.update(
            {
                "artifact_status": "missing",
                "as_of": None,
                "headline": _MODEL_CHAIN_MISSING_HEADLINE,
                "columns": [],
                "rows": [],
            }
        )
        return payload
    columns, rows = _model_chain_table(frame, model_def)
    headline_builder = model_def["headline"]
    payload.update(
        {
            "artifact_status": "ok",
            "as_of": _model_chain_as_of(frame, path),
            "headline": headline_builder(frame),
            "columns": columns,
            "rows": rows,
        }
    )
    return payload


def _model_chain_final_signal_as_of_date(output_dir: Path) -> str | None:
    frame = _load_model_chain_frame(output_dir / _MODEL_CHAIN_FINAL_SIGNAL_ARTIFACT)
    if frame is None:
        return None
    return _model_chain_latest_date_text(frame)


# ---------------------------------------------------------------------------
# Model chain scheduler health (Windows scheduled-task receipt summaries)
# ---------------------------------------------------------------------------

_MODEL_CHAIN_DAILY_CHAIN_RECEIPT_NAME = "macro_toolkit_daily_chain_receipt.json"
_MODEL_CHAIN_FRESHNESS_RECEIPT_NAME = "macro_toolkit_freshness_refresh_receipt.json"


def _model_chain_daily_chain_summary(result: Mapping[str, object]) -> str:
    """一句话摘要：``链 <result.chain.status> · 链外脚本 <completed>/<total> 完成``。"""
    chain = result.get("chain")
    chain_status = _model_chain_cell_text(
        chain.get("status") if isinstance(chain, Mapping) else None
    )
    extra_scripts = result.get("extra_scripts")
    items = (
        [item for item in extra_scripts if isinstance(item, Mapping)]
        if isinstance(extra_scripts, list)
        else []
    )
    completed = sum(1 for item in items if str(item.get("status") or "") == "completed")
    return f"链 {chain_status} · 链外脚本 {completed}/{len(items)} 完成"


def _model_chain_freshness_summary(result: Mapping[str, object]) -> str:
    """一句话摘要：``步骤 <success> 成功 / <failed> 失败[ / <degraded> 降级]``。"""
    steps = result.get("steps")
    items = (
        [item for item in steps if isinstance(item, Mapping)] if isinstance(steps, list) else []
    )
    statuses = [str(item.get("status") or "") for item in items]
    success = sum(1 for status in statuses if status == "success")
    failed = sum(1 for status in statuses if status == "failed")
    degraded = sum(1 for status in statuses if status == "degraded")
    summary = f"步骤 {success} 成功 / {failed} 失败"
    if degraded:
        summary += f" / {degraded} 降级"
    return summary


def _model_chain_receipt_summary(
    path: Path,
    summary_builder: Callable[[Mapping[str, object]], str],
) -> dict[str, object] | None:
    """读取一个调度回执 JSON 并压缩为 ReceiptSummary；文件缺失/解析失败/非对象 → None，不抛错。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None
    if not isinstance(data, Mapping):
        return None
    exit_code = data.get("exit_code")
    result = data.get("result")
    return {
        "task_name": str(data.get("task_name") or ""),
        "status": str(data.get("status") or ""),
        "exit_code": exit_code if isinstance(exit_code, int) else None,
        "generated_at": str(data.get("generated_at") or ""),
        "run_kind": str(data.get("run_kind") or ""),
        "summary": summary_builder(result if isinstance(result, Mapping) else {}),
    }


def _model_chain_scheduler_payload(logs_dir: Path) -> dict[str, object]:
    return {
        "daily_chain": _model_chain_receipt_summary(
            logs_dir / _MODEL_CHAIN_DAILY_CHAIN_RECEIPT_NAME,
            _model_chain_daily_chain_summary,
        ),
        "freshness": _model_chain_receipt_summary(
            logs_dir / _MODEL_CHAIN_FRESHNESS_RECEIPT_NAME,
            _model_chain_freshness_summary,
        ),
    }


def build_model_chain_results(
    output_dir: Path | str = OUTPUT_DIR,
    logs_dir: Path | str | None = None,
) -> dict[str, object]:
    """观察口径：把十个模型脚本的最新产物 CSV 按尽调笔记决策链组装为只读结构。

    仅做文本透传与 headline 摘要拼装，不含任何业务计算；产物缺失/为空/解析失败时
    对应模型降级为 ``artifact_status="missing"``，不抛异常、不影响其他模型。

    ``logs_dir`` 指向调度回执目录（默认从 ``output_dir`` 推导：
    ``data/macro_toolkit/output`` → ``data/logs``），用于组装顶层 ``scheduler`` 键；
    回执缺失/损坏时对应键为 None，顶层 ``scheduler`` 恒存在。
    """
    directory = Path(output_dir)
    if logs_dir is not None:
        logs_directory = Path(logs_dir)
    elif len(directory.parents) >= 2:
        logs_directory = directory.parents[1] / "logs"
    else:
        logs_directory = directory / "logs"
    steps: list[dict[str, object]] = []
    for step_def in _MODEL_CHAIN_STEP_DEFINITIONS:
        models = [
            _model_chain_model_payload(model_def, output_dir=directory)
            for model_def in step_def["models"]
        ]
        steps.append(
            {
                "key": step_def["key"],
                "step_no": step_def["step_no"],
                "label": step_def["label"],
                "models": models,
            }
        )
    return {
        "as_of_date": _model_chain_final_signal_as_of_date(directory),
        "observation_only": MACRO_TOOLKIT_OBSERVATION_ONLY,
        "formal_use_allowed": MACRO_TOOLKIT_FORMAL_USE_ALLOWED,
        "scheduler": _model_chain_scheduler_payload(logs_directory),
        "steps": steps,
    }
