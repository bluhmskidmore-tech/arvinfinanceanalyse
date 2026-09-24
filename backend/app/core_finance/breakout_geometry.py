from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

# ---- 观察位几何（复用 Livermore 候选现行口径，观察展示字段，非正式交易结论） ----
# 本模块是全部观察候选源（factor_screen / uptrend_momentum / mean_reversion /
# fresh_trend_watchlist / hybrid_fusion）共用的唯一 breakout 几何实现；
# 禁止在各候选模块内复制该公式。
# breakout_level 完全复用 Livermore 候选的现行公式：先导 55 个收盘的最高值，
# 剔除信号日，即 max(closes[-56:-1])
# （backend/app/core_finance/livermore_stock_candidates.py `_candidate_row`）。
# distance_to_breakout_pct 复用前端对 Livermore 候选的现行展示公式
# ((close - breakout_level) / breakout_level) * 100
# （frontend/src/features/stock-analysis/lib/stockAnalysisPageModel.ts
#  `formatDistanceToBreakoutPct`），单位为百分数（3.0 表示 +3.00%）。
# pattern 复用同文件 `deriveCandidatePattern` 的现行有效映射：其换手/跳空分支
# 两侧输出相同标签，等效为仅按 close/breakout 比值分档；标签沿用「（参考）」
# 后缀的观察降级语义。fail-closed：K 线缺失/长度不足/含非有限值/突破位非正时
# 四个字段保持 None，禁止输出 0 或近似值。
BREAKOUT_GEOMETRY_PRIOR_WINDOW = 55
# 55 个先导收盘 + 1 个信号日收盘；不足时不得缩窗改算（那会变成另一种口径）。
BREAKOUT_GEOMETRY_MIN_HISTORY = BREAKOUT_GEOMETRY_PRIOR_WINDOW + 1
PATTERN_BREAKOUT_MIN_RATIO = 1.0025
PATTERN_PULLBACK_MAX_RATIO = 0.985
PATTERN_BREAKOUT_LABEL = "突破（参考）"
PATTERN_PULLBACK_LABEL = "回踩（参考）"
PATTERN_CONSOLIDATION_LABEL = "缩量盘整（参考）"

# attach 输出的四个几何键；对已带同名键（值非 None）的 item 只补缺失键，不覆盖。
BREAKOUT_GEOMETRY_FIELD_KEYS = (
    "close",
    "breakout_level",
    "distance_to_breakout_pct",
    "pattern",
)


def attach_breakout_geometry(
    payload: dict[str, object],
    *,
    close_history_by_code: Mapping[str, Sequence[object]],
    price_as_of_date: str,
    last_trade_date_by_code: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """为观察候选 payload 补充观察位几何字段（close/breakout_level/distance_to_breakout_pct/pattern）。

    - close_history_by_code 必须与 Livermore 候选同源同序：升序收盘序列，
      锚定 price_as_of_date（策略日），服务层复用 fetch_stock_candidate_history_rows
      装载，保证同一只股票在任意来源下几何值逐位一致。
    - 不覆盖既有键：item 已带非 None 的同名键（如动量/超跌/新趋势自带的策略日
      close）时保留原值，几何只补缺失键。
    - 冲突 fail-closed：item 自带 close 时，若几何推导的 close 与其不等
      （同股同日不同价），或几何价格锚定日早于策略日（item 自身 close 已是
      策略日价，二者证据日期矛盾），则该 item 的几何字段整体不可用，缺失键
      一律补 None，禁止择一采信。
    - 停牌披露：仅对自身不带 close 的 item（如多因子/融合候选）生效——
      close 实际锚定最近可得交易日时补 price_as_of_date（实际价格日）与
      price_stale=True，防止消费方把旧价当作策略日价格。
    - 不修改传入 payload/items（返回新对象）；各源候选选择与评分口径不变。
    """
    last_dates = last_trade_date_by_code or {}

    def _item_with_geometry(item: dict[str, object]) -> dict[str, object]:
        stock_code = str(item.get("stock_code") or "")
        fields = _breakout_geometry_fields(close_history_by_code.get(stock_code))
        existing_close = _finite_float(item.get("close"))
        anchor_date = str(last_dates.get(stock_code) or "").strip()
        if existing_close is not None:
            geometry_close = fields["close"]
            conflicting = geometry_close is not None and (
                round(existing_close, 6) != geometry_close
                or (bool(anchor_date) and anchor_date != price_as_of_date)
            )
            if conflicting:
                fields = dict.fromkeys(BREAKOUT_GEOMETRY_FIELD_KEYS)
        elif fields["close"] is not None and anchor_date and anchor_date != price_as_of_date:
            fields = {
                **fields,
                "price_as_of_date": anchor_date,
                "price_stale": True,
            }
        merged = dict(item)
        for key, value in fields.items():
            if merged.get(key) is None:
                merged[key] = value
        return merged

    items = [_item_with_geometry(item) for item in _payload_item_dicts(payload)]
    return {
        **payload,
        "items": items,
        "breakout_geometry": {
            # 几何锚定日：与 Livermore 候选相同的策略 as_of_date；来源自身
            # as_of_date（如因子快照日）滞后时两者不同，须以本字段核对价格证据日期。
            "price_as_of_date": price_as_of_date,
            "breakout_basis": "prior_55d_close_high",
            "distance_basis": "close_over_breakout_minus_one_pct",
        },
    }


def _payload_item_dicts(payload: dict[str, object]) -> list[dict[str, object]]:
    items = payload.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _breakout_geometry_fields(
    close_history: Sequence[object] | None,
) -> dict[str, float | str | None]:
    empty: dict[str, float | str | None] = {
        "close": None,
        "breakout_level": None,
        "distance_to_breakout_pct": None,
        "pattern": None,
    }
    if close_history is None or len(close_history) < BREAKOUT_GEOMETRY_MIN_HISTORY:
        return empty
    closes: list[float] = []
    for value in close_history:
        try:
            as_float = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            # 与 livermore_stock_candidates._float_series 同口径：序列中任一
            # 元素无效即整体视为不可用，不做局部剔除后的缩窗改算。
            return empty
        if not math.isfinite(as_float):
            return empty
        closes.append(as_float)
    breakout_level = max(closes[-BREAKOUT_GEOMETRY_MIN_HISTORY:-1])
    close = closes[-1]
    if breakout_level <= 0:
        # 突破位非正（脏数据）时距离无定义，fail-closed 保持 None。
        return empty
    ratio = close / breakout_level
    if ratio > PATTERN_BREAKOUT_MIN_RATIO:
        pattern = PATTERN_BREAKOUT_LABEL
    elif ratio < PATTERN_PULLBACK_MAX_RATIO:
        pattern = PATTERN_PULLBACK_LABEL
    else:
        pattern = PATTERN_CONSOLIDATION_LABEL
    return {
        # 6 位小数与 Livermore 候选 item 的 close/breakout_level 舍入一致。
        "close": round(close, 6),
        "breakout_level": round(breakout_level, 6),
        "distance_to_breakout_pct": round((close - breakout_level) / breakout_level * 100.0, 4),
        "pattern": pattern,
    }


def _finite_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    as_float = float(value)
    return as_float if math.isfinite(as_float) else None
