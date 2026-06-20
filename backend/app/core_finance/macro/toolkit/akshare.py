from __future__ import annotations

import pandas as pd
from backend.app.core_finance.macro.toolkit.system_sources import load_series_by_alias


def stock_zh_index_daily(symbol: str) -> pd.DataFrame:
    frame = load_series_by_alias(symbol)
    return _date_close_frame(frame)


def futures_main_sina(symbol: str, start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
    frame = load_series_by_alias(symbol, start=start_date, end=end_date)
    out = _date_close_frame(frame)
    out["日期"] = out["date"]
    out["收盘价"] = out["close"]
    return out


def fund_etf_hist_em(
    symbol: str,
    period: str = "daily",
    start_date: str | None = None,
    end_date: str | None = None,
    adjust: str = "",
) -> pd.DataFrame:
    _ = period, adjust
    frame = load_series_by_alias(symbol, start=start_date, end=end_date)
    out = _date_close_frame(frame)
    out["日期"] = out["date"]
    out["收盘"] = out["close"]
    return out


def _date_close_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["date", "close"])
    out = frame[["date", "value"]].copy()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    out["close"] = pd.to_numeric(out["value"], errors="coerce")
    return out.drop(columns=["value"]).reset_index(drop=True)
