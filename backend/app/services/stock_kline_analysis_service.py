from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path
from typing import Any, cast

import duckdb
from backend.app.core_finance.field_normalization import TRADING_STATUS_SQL_IN_LIST
from backend.app.services.formal_result_runtime import (
    FallbackMode,
    QualityFlag,
    VendorStatus,
    build_result_envelope,
)

RESULT_KIND = "market_data.stock_analysis.kline"
RULE_VERSION = "rv_stock_kline_analysis_observation_v1"
CACHE_VERSION = "cv_stock_kline_analysis_observation_v1"
EMPTY_SOURCE_VERSION = "sv_stock_kline_analysis_empty"
EMPTY_VENDOR_VERSION = "vv_none"

TABLE_OBS = "choice_stock_daily_observation"
MIN_USABLE_BARS = 30
RECOMMENDED_BARS = 60


def stock_kline_analysis_envelope(
    *,
    duckdb_path: str,
    stock_code: str,
    as_of_date: date | None,
    lookback: int,
) -> dict[str, object]:
    """Analyze daily OHLCV observations for one stock; read-only DuckDB SELECT only."""
    requested_iso = None if as_of_date is None else as_of_date.isoformat()
    path = Path(duckdb_path)
    if not path.is_file():
        return _missing_envelope(
            stock_code=stock_code,
            requested_as_of_date=requested_iso,
            lookback=lookback,
            reason_code="duckdb_missing",
        )

    try:
        conn = duckdb.connect(str(path), read_only=True)
        try:
            end_bound = _resolve_end_trade_date(conn, stock_code=stock_code, as_of_date=as_of_date)
            if end_bound is None:
                return _missing_envelope(
                    stock_code=stock_code,
                    requested_as_of_date=requested_iso,
                    lookback=lookback,
                    reason_code="stock_ohlcv_missing",
                )
            rows = _fetch_candles(
                conn,
                stock_code=stock_code,
                end_trade_date=end_bound,
                lookback=lookback,
            )
        finally:
            conn.close()
    except duckdb.Error:
        return _missing_envelope(
            stock_code=stock_code,
            requested_as_of_date=requested_iso,
            lookback=lookback,
            reason_code="source_table_unavailable",
        )

    candles = [_normalize_candle_row(row) for row in reversed(rows)]
    if not candles:
        return _missing_envelope(
            stock_code=stock_code,
            requested_as_of_date=requested_iso,
            lookback=lookback,
            resolved_as_of_date=end_bound.isoformat(),
            reason_code="stock_ohlcv_missing",
        )

    source_version = _first_non_empty(
        *[row.get("source_version") for row in candles],
        default=EMPTY_SOURCE_VERSION,
    )
    vendor_version = _first_non_empty(
        *[row.get("vendor_version") for row in candles],
        default=EMPTY_VENDOR_VERSION,
    )
    public_candles = [
        {key: value for key, value in candle.items() if key not in {"source_version", "vendor_version"}}
        for candle in candles
    ]
    analysis = _analyze_candles(public_candles)
    state = str(analysis["state"])
    quality_flag = "ok" if state == "ok" else "warning"

    result_payload: dict[str, object] = {
        "basis": "analytical",
        "state": state,
        "contract_status": "observational_only",
        "formal_use_allowed": False,
        "trading_instruction_allowed": False,
        "stock_code": stock_code,
        "requested_as_of_date": requested_iso,
        "as_of_date": end_bound.isoformat(),
        "lookback": lookback,
        "engine": {
            "name": "moss_stock_kline_analysis",
            "source": "kline-analysis zip deterministic OHLCV subset",
            "rule_version": RULE_VERSION,
            "coverage": ["daily_patterns", "moving_average_trend", "volume_context", "validity_check"],
        },
        "latest_candle": public_candles[-1],
        "indicators": analysis["indicators"],
        "patterns": analysis["patterns"],
        "validity": analysis["validity"],
        "observation_signal": analysis["observation_signal"],
        "diagnostics": analysis["diagnostics"],
    }
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_stock_kline_analysis_{uuid.uuid4().hex[:12]}",
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        source_version=str(source_version),
        rule_version=RULE_VERSION,
        quality_flag=cast(QualityFlag, quality_flag),
        vendor_version=str(vendor_version),
        vendor_status=cast(VendorStatus, "ok"),
        fallback_mode=cast(FallbackMode, "none"),
        filters_applied={
            "requested_as_of_date": requested_iso,
            "as_of_date": end_bound.isoformat(),
            "stock_code": stock_code,
            "lookback": lookback,
        },
        tables_used=[TABLE_OBS],
        evidence_rows=len(public_candles),
        result_payload=result_payload,
    )


def _missing_envelope(
    *,
    stock_code: str,
    requested_as_of_date: str | None,
    lookback: int,
    reason_code: str,
    resolved_as_of_date: str | None = None,
) -> dict[str, object]:
    result_payload: dict[str, object] = {
        "basis": "analytical",
        "state": "missing",
        "contract_status": "observational_only",
        "formal_use_allowed": False,
        "trading_instruction_allowed": False,
        "stock_code": stock_code,
        "requested_as_of_date": requested_as_of_date,
        "as_of_date": resolved_as_of_date,
        "lookback": lookback,
        "engine": {
            "name": "moss_stock_kline_analysis",
            "source": "kline-analysis zip deterministic OHLCV subset",
            "rule_version": RULE_VERSION,
            "coverage": ["daily_patterns", "moving_average_trend", "volume_context", "validity_check"],
        },
        "latest_candle": None,
        "indicators": {},
        "patterns": [],
        "validity": {
            "state": "missing",
            "usable": False,
            "bar_count": 0,
            "required_bar_count": MIN_USABLE_BARS,
            "recommended_bar_count": RECOMMENDED_BARS,
            "data_health": {"state": "missing", "invalid_candle_count": 0, "zero_volume_count": 0},
            "liquidity": {"state": "missing", "latest_volume": None, "average_volume_20d": None},
            "warnings": [reason_code],
        },
        "observation_signal": {
            "level": "not_applicable",
            "label": "not_applicable",
            "score": None,
            "confidence": "low",
            "reasons": [],
            "risks": [reason_code],
        },
        "diagnostics": [
            {
                "severity": "warning",
                "code": reason_code,
                "message": "Daily OHLCV evidence is unavailable for this k-line observation.",
            }
        ],
    }
    return build_result_envelope(
        basis="analytical",
        trace_id=f"tr_stock_kline_analysis_{uuid.uuid4().hex[:12]}",
        result_kind=RESULT_KIND,
        cache_version=CACHE_VERSION,
        source_version=EMPTY_SOURCE_VERSION,
        rule_version=RULE_VERSION,
        quality_flag=cast(QualityFlag, "warning"),
        vendor_version=EMPTY_VENDOR_VERSION,
        vendor_status=cast(VendorStatus, "ok"),
        fallback_mode=cast(FallbackMode, "none"),
        filters_applied={
            "requested_as_of_date": requested_as_of_date,
            "as_of_date": resolved_as_of_date,
            "stock_code": stock_code,
            "lookback": lookback,
        },
        tables_used=[TABLE_OBS],
        evidence_rows=0,
        result_payload=result_payload,
    )


def _resolve_end_trade_date(conn: duckdb.DuckDBPyConnection, *, stock_code: str, as_of_date: date | None) -> date | None:
    if as_of_date is None:
        row = conn.execute(
            f"""
            select max(trade_date) as mx
            from {TABLE_OBS}
            where stock_code = ?
              and lower(trim(coalesce(tradestatus, ''))) in {TRADING_STATUS_SQL_IN_LIST}
            """,
            [stock_code],
        ).fetchone()
    else:
        row = conn.execute(
            f"""
            select max(trade_date) as mx
            from {TABLE_OBS}
            where stock_code = ?
              and trade_date <= ?
              and lower(trim(coalesce(tradestatus, ''))) in {TRADING_STATUS_SQL_IN_LIST}
            """,
            [stock_code, as_of_date.isoformat()],
        ).fetchone()
    if row is None or row[0] is None:
        return None
    try:
        return date.fromisoformat(str(row[0]).strip()[:10])
    except ValueError:
        return None


def _fetch_candles(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str,
    end_trade_date: date,
    lookback: int,
) -> list[dict[str, Any]]:
    result = conn.execute(
        f"""
        select
          trade_date,
          open_value,
          high_value,
          low_value,
          close_value,
          volume,
          amount,
          pctchange,
          turn,
          amplitude,
          source_version,
          vendor_version
        from {TABLE_OBS}
        where stock_code = ?
          and trade_date <= ?
          and lower(trim(coalesce(tradestatus, ''))) in {TRADING_STATUS_SQL_IN_LIST}
        order by trade_date desc
        limit ?
        """,
        [stock_code, end_trade_date.isoformat(), lookback],
    )
    cols = [d[0] for d in result.description]
    return [dict(zip(cols, row, strict=True)) for row in result.fetchall()]


def _analyze_candles(candles: list[dict[str, object]]) -> dict[str, object]:
    bar_count = len(candles)
    indicators = _indicators(candles)
    patterns = _patterns(candles)
    validity = _validity(candles)
    signal = _observation_signal(indicators=indicators, patterns=patterns, validity=validity)
    state = "ok" if validity["usable"] else ("insufficient" if bar_count > 0 else "missing")
    diagnostics = [
        {
            "severity": "info",
            "code": "observation_only",
            "message": "K-line output is observational evidence only and is not a trading instruction.",
        }
    ]
    for warning in validity["warnings"]:
        diagnostics.append(
            {
                "severity": "warning",
                "code": str(warning),
                "message": "Validity warning detected for this K-line observation.",
            }
        )
    return {
        "state": state,
        "indicators": indicators,
        "patterns": patterns,
        "validity": validity,
        "observation_signal": signal,
        "diagnostics": diagnostics,
    }


def _indicators(candles: list[dict[str, object]]) -> dict[str, object]:
    closes = [_maybe_float(c.get("close_value")) for c in candles]
    volumes = [_maybe_float(c.get("volume")) for c in candles]
    latest = candles[-1] if candles else {}
    latest_close = _maybe_float(latest.get("close_value"))
    latest_volume = _maybe_float(latest.get("volume"))
    average_volume_20d = _mean_tail(volumes[:-1], 20)
    volume_ratio_20d = (
        latest_volume / average_volume_20d
        if latest_volume is not None and average_volume_20d is not None and average_volume_20d > 0
        else None
    )
    return {
        "latest_close": latest_close,
        "ma5": _mean_tail(closes, 5),
        "ma20": _mean_tail(closes, 20),
        "ma60": _mean_tail(closes, 60),
        "return_5d": _return_over(closes, 5),
        "return_20d": _return_over(closes, 20),
        "volume_ratio_20d": volume_ratio_20d,
        "latest_turnover": _maybe_float(latest.get("turn")),
        "latest_amplitude": _maybe_float(latest.get("amplitude")),
    }


def _patterns(candles: list[dict[str, object]]) -> list[dict[str, object]]:
    if not candles:
        return []
    latest = candles[-1]
    previous = candles[-2] if len(candles) >= 2 else None
    if not _valid_ohlc(latest):
        return []

    patterns: list[dict[str, object]] = []
    o = cast(float, _maybe_float(latest.get("open_value")))
    h = cast(float, _maybe_float(latest.get("high_value")))
    low = cast(float, _maybe_float(latest.get("low_value")))
    c = cast(float, _maybe_float(latest.get("close_value")))
    candle_range = h - low
    body = abs(c - o)
    upper_shadow = h - max(o, c)
    lower_shadow = min(o, c) - low

    if candle_range > 0 and body / candle_range <= 0.1:
        patterns.append(_pattern("doji", "doji", "neutral", "body/range <= 10%"))
    if candle_range > 0 and lower_shadow >= body * 2 and upper_shadow <= candle_range * 0.3:
        patterns.append(_pattern("hammer_like", "hammer_like", "positive", "lower shadow dominates latest candle"))
    if candle_range > 0 and upper_shadow >= body * 2 and lower_shadow <= candle_range * 0.3:
        patterns.append(_pattern("shooting_star_like", "shooting_star_like", "negative", "upper shadow dominates latest candle"))
    if candle_range > 0 and body / candle_range >= 0.65:
        tone = "positive" if c > o else "negative"
        patterns.append(_pattern("wide_body", "wide_body", tone, "body/range >= 65%"))

    if previous is not None and _valid_ohlc(previous):
        po = cast(float, _maybe_float(previous.get("open_value")))
        pc = cast(float, _maybe_float(previous.get("close_value")))
        if pc < po and c > o and o <= pc and c >= po:
            patterns.append(_pattern("bullish_engulfing", "bullish_engulfing", "positive", "latest body engulfs prior down body"))
        if pc > po and c < o and o >= pc and c <= po:
            patterns.append(_pattern("bearish_engulfing", "bearish_engulfing", "negative", "latest body engulfs prior up body"))
    return patterns


def _validity(candles: list[dict[str, object]]) -> dict[str, object]:
    invalid_count = sum(1 for candle in candles if not _valid_ohlc(candle))
    zero_volume_count = sum(1 for candle in candles if (_maybe_float(candle.get("volume")) or 0) <= 0)
    one_price_count = sum(1 for candle in candles if _is_one_price_candle(candle))
    latest = candles[-1] if candles else {}
    volumes = [_maybe_float(c.get("volume")) for c in candles]
    latest_volume = _maybe_float(latest.get("volume"))
    average_volume_20d = _mean_tail(volumes, 20)
    warnings: list[str] = []
    if len(candles) < MIN_USABLE_BARS:
        warnings.append("insufficient_bar_count")
    if invalid_count > 0:
        warnings.append("invalid_ohlc_rows")
    if zero_volume_count > max(0, len(candles) // 5):
        warnings.append("thin_or_missing_volume")
    if one_price_count > max(1, len(candles) // 10):
        warnings.append("one_price_candle_cluster")
    data_health_state = "ok" if invalid_count == 0 and not warnings else "warning"
    liquidity_state = "ok" if average_volume_20d is not None and average_volume_20d > 0 else "missing"
    usable = len(candles) >= MIN_USABLE_BARS and invalid_count == 0
    return {
        "state": "usable" if usable else ("limited" if candles else "missing"),
        "usable": usable,
        "bar_count": len(candles),
        "required_bar_count": MIN_USABLE_BARS,
        "recommended_bar_count": RECOMMENDED_BARS,
        "data_health": {
            "state": data_health_state,
            "invalid_candle_count": invalid_count,
            "zero_volume_count": zero_volume_count,
            "one_price_candle_count": one_price_count,
        },
        "liquidity": {
            "state": liquidity_state,
            "latest_volume": latest_volume,
            "average_volume_20d": average_volume_20d,
            "latest_turnover": _maybe_float(latest.get("turn")),
        },
        "warnings": warnings,
    }


def _observation_signal(
    *,
    indicators: dict[str, object],
    patterns: list[dict[str, object]],
    validity: dict[str, object],
) -> dict[str, object]:
    if not validity["usable"]:
        return {
            "level": "not_applicable",
            "label": "not_applicable",
            "score": None,
            "confidence": "low",
            "reasons": [],
            "risks": [str(item) for item in validity["warnings"]],
        }

    score = 50
    reasons: list[str] = []
    risks: list[str] = []
    latest = _maybe_float(indicators.get("latest_close"))
    ma20 = _maybe_float(indicators.get("ma20"))
    ma60 = _maybe_float(indicators.get("ma60"))
    ret5 = _maybe_float(indicators.get("return_5d"))
    ret20 = _maybe_float(indicators.get("return_20d"))
    volume_ratio = _maybe_float(indicators.get("volume_ratio_20d"))

    if latest is not None and ma20 is not None and latest > ma20:
        score += 6
        reasons.append("close_above_ma20")
    if ma20 is not None and ma60 is not None and ma20 > ma60:
        score += 8
        reasons.append("ma20_above_ma60")
    if ret5 is not None and ret5 > 0:
        score += 4
        reasons.append("positive_5d_return")
    if ret20 is not None and ret20 > 0:
        score += 5
        reasons.append("positive_20d_return")
    if volume_ratio is not None and volume_ratio >= 1.5 and (ret5 or 0) > 0:
        score += 5
        reasons.append("expanding_volume_with_positive_price")
    if latest is not None and ma20 is not None and latest < ma20:
        score -= 8
        risks.append("close_below_ma20")
    if ret20 is not None and ret20 < 0:
        score -= 6
        risks.append("negative_20d_return")

    for pattern in patterns:
        tone = str(pattern.get("tone") or "")
        key = str(pattern.get("key") or "")
        if tone == "positive":
            score += 6
            reasons.append(key)
        elif tone == "negative":
            score -= 6
            risks.append(key)
        elif key == "doji":
            score -= 2
            risks.append("doji_indecision")

    score = max(0, min(100, score))
    if score >= 70:
        level = "constructive_watch"
    elif score >= 55:
        level = "watch"
    elif score >= 45:
        level = "neutral"
    else:
        level = "risk_watch"
    confidence = "high" if validity["bar_count"] >= RECOMMENDED_BARS and not risks else "medium"
    if validity["warnings"]:
        confidence = "low"
    return {
        "level": level,
        "label": level,
        "score": score,
        "confidence": confidence,
        "reasons": reasons[:8],
        "risks": risks[:8],
    }


def _normalize_candle_row(row: dict[str, Any]) -> dict[str, object]:
    return {
        "trade_date": str(row.get("trade_date") or "").strip()[:10],
        "open_value": _maybe_float(row.get("open_value")),
        "high_value": _maybe_float(row.get("high_value")),
        "low_value": _maybe_float(row.get("low_value")),
        "close_value": _maybe_float(row.get("close_value")),
        "volume": _maybe_float(row.get("volume")),
        "amount": _maybe_float(row.get("amount")),
        "pctchange": _maybe_float(row.get("pctchange")),
        "turn": _maybe_float(row.get("turn")),
        "amplitude": _maybe_float(row.get("amplitude")),
        "source_version": _optional_str(row.get("source_version")),
        "vendor_version": _optional_str(row.get("vendor_version")),
    }


def _pattern(key: str, label: str, tone: str, evidence: str) -> dict[str, object]:
    return {"key": key, "label": label, "tone": tone, "evidence": evidence}


def _valid_ohlc(candle: dict[str, object]) -> bool:
    o = _maybe_float(candle.get("open_value"))
    h = _maybe_float(candle.get("high_value"))
    low = _maybe_float(candle.get("low_value"))
    c = _maybe_float(candle.get("close_value"))
    if None in {o, h, low, c}:
        return False
    assert o is not None and h is not None and low is not None and c is not None
    return h >= low and low <= o <= h and low <= c <= h


def _is_one_price_candle(candle: dict[str, object]) -> bool:
    o = _maybe_float(candle.get("open_value"))
    h = _maybe_float(candle.get("high_value"))
    low = _maybe_float(candle.get("low_value"))
    c = _maybe_float(candle.get("close_value"))
    if None in {o, h, low, c}:
        return False
    return o == h == low == c


def _return_over(values: list[float | None], periods: int) -> float | None:
    usable = [value for value in values if value is not None]
    if len(usable) <= periods:
        return None
    latest = usable[-1]
    previous = usable[-periods - 1]
    if previous == 0:
        return None
    return latest / previous - 1


def _mean_tail(values: list[float | None], periods: int) -> float | None:
    usable = [value for value in values if value is not None]
    if len(usable) < periods:
        return None
    tail = usable[-periods:]
    return sum(tail) / len(tail)


def _maybe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    return x if x == x else None


def _optional_str(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _first_non_empty(*values: object, default: str) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return default
