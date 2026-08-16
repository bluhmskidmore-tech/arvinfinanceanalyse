from __future__ import annotations

from dataclasses import dataclass

import duckdb
import pandas as pd
from backend.app.core_finance.macro.toolkit.cffex_member_rank_shared import (
    load_member_rank_frame,
    normalize_cffex_contract,
    normalize_trade_date,
)
from backend.app.core_finance.macro.toolkit.system_sources import load_series_by_alias, resolve_system_duckdb_path


@dataclass
class _WindResult:
    ErrorCode: int = 0
    Codes: list[str] | None = None
    Fields: list[str] | None = None
    Times: list[pd.Timestamp] | None = None
    Data: list[list[float | None]] | None = None
    ErrorMsg: str = ""

    def __eq__(self, other: object) -> bool:
        if isinstance(other, int):
            return self.ErrorCode == other
        return super().__eq__(other)


class _SystemChoiceTushareWind:
    def __init__(self) -> None:
        self._connected = False

    def start(self, *args, **kwargs) -> _WindResult:
        self._connected = True
        return _WindResult(ErrorCode=0, ErrorMsg="choice/tushare system source ready")

    def stop(self) -> _WindResult:
        self._connected = False
        return _WindResult(ErrorCode=0)

    def isconnected(self) -> bool:
        return self._connected

    def wsd(self, codes: str, fields: str, start: str, end: str, options: str = "") -> _WindResult:
        return _series_result(codes, fields, start, end)

    def edb(self, codes: str, start: str, end: str, options: str = "") -> _WindResult:
        return _series_result(codes, "close", start, end)

    def wset(self, name: str, options: str = "") -> _WindResult:
        if str(name or "").strip().lower() == "cffexmemberrank":
            return _cffex_member_rank_result(options)
        return _WindResult(
            ErrorCode=501,
            Fields=[],
            Data=[],
            ErrorMsg=f"{name} is not materialized in the system Choice/Tushare DuckDB sources",
        )


def _series_result(codes: str, fields: str, start: str, end: str) -> _WindResult:
    code_list = _split_csv(codes)
    field_list = _split_csv(fields)
    if not code_list:
        return _WindResult(ErrorCode=404, Codes=[], Fields=field_list, Times=[], Data=[], ErrorMsg="no codes")

    if len(code_list) == 1 and _is_bond_futures_code(code_list[0]) and set(_normalize_field(item) for item in field_list).issubset({"close", "oi", "volume"}):
        result = _bond_futures_result(code_list[0], field_list, start, end)
        if result.ErrorCode == 0:
            return result

    series_by_code = {code: load_series_by_alias(code, start=start, end=end) for code in code_list}
    if all(frame.empty for frame in series_by_code.values()):
        return _WindResult(
            ErrorCode=404,
            Codes=code_list,
            Fields=field_list,
            Times=[],
            Data=[],
            ErrorMsg="no Choice/Tushare rows matched requested codes",
        )

    all_dates = sorted(
        {
            pd.Timestamp(date)
            for frame in series_by_code.values()
            if not frame.empty
            for date in frame["date"].tolist()
        }
    )
    if len(code_list) == 1 and len(field_list) > 1:
        frame = series_by_code[code_list[0]]
        values = _values_by_date(frame)
        data = [[values.get(date) if field.lower() == "close" else None for date in all_dates] for field in field_list]
    else:
        data = []
        for code in code_list:
            values = _values_by_date(series_by_code[code])
            data.append([values.get(date) for date in all_dates])

    return _WindResult(
        ErrorCode=0,
        Codes=code_list,
        Fields=field_list,
        Times=all_dates,
        Data=data,
        ErrorMsg="choice/tushare system source",
    )


def _values_by_date(frame: pd.DataFrame) -> dict[pd.Timestamp, float]:
    if frame.empty:
        return {}
    return {pd.Timestamp(row["date"]): float(row["value"]) for _, row in frame.iterrows()}


def _bond_futures_result(code: str, fields: list[str], start: str, end: str) -> _WindResult:
    frame = _load_bond_futures_frame(code, start=start, end=end)
    if frame.empty:
        return _WindResult(
            ErrorCode=404,
            Codes=[code],
            Fields=fields,
            Times=[],
            Data=[],
            ErrorMsg=f"no Choice/Tushare bond-futures rows matched {code}",
        )

    times = [pd.Timestamp(item) for item in frame["trade_date"].tolist()]
    field_map = {
        "close": "close_value",
        "oi": "open_interest",
        "volume": "volume",
    }
    data = []
    for field in fields:
        column = field_map[_normalize_field(field)]
        data.append(_frame_numeric_values(frame, column))
    return _WindResult(
        ErrorCode=0,
        Codes=[code],
        Fields=fields,
        Times=times,
        Data=data,
        ErrorMsg="choice/tushare bond-futures daily source",
    )


def _load_bond_futures_frame(code: str, *, start: str, end: str) -> pd.DataFrame:
    path = resolve_system_duckdb_path()
    if not path.exists():
        return pd.DataFrame()
    try:
        conn = duckdb.connect(str(path), read_only=True)
    except duckdb.Error:
        return pd.DataFrame()
    try:
        if not _table_exists(conn, "fact_commodity_futures_daily"):
            return pd.DataFrame()
        frame = conn.execute(
            """
            select
              trade_date,
              close_value,
              open_interest,
              volume
            from fact_commodity_futures_daily
            where upper(product_code) = ?
              and trade_date between ? and ?
              and close_value is not null
            order by trade_date
            """,
            [_bond_futures_product(code), _normalize_date_arg(start), _normalize_date_arg(end)],
        ).fetchdf()
    except duckdb.Error:
        return pd.DataFrame()
    finally:
        conn.close()
    return frame


def _table_exists(conn: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    try:
        return bool(
            conn.execute(
                """
                select count(*)
                from information_schema.tables
                where table_schema = 'main' and table_name = ?
                """,
                [table_name],
            ).fetchone()[0]
        )
    except duckdb.Error:
        return False


def _frame_numeric_values(frame: pd.DataFrame, column: str) -> list[float | None]:
    values: list[float | None] = []
    for value in frame[column].tolist():
        values.append(None if pd.isna(value) else float(value))
    return values


def _is_bond_futures_code(code: str) -> bool:
    return _bond_futures_product(code) in {"TS", "TF", "T", "TL"}


def _bond_futures_product(code: str) -> str:
    raw = str(code or "").strip().upper()
    if raw.startswith("CFFEX.") or raw.startswith("CFE.") or raw.startswith("CFX."):
        raw = raw.split(".", 1)[1]
    if "." in raw:
        raw = raw.split(".", 1)[0]
    return "".join(ch for ch in raw if ch.isalpha())


def _normalize_field(value: str) -> str:
    return str(value or "").strip().lower()


def _normalize_date_arg(value: str) -> str:
    text = str(value or "").strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text[:10]


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _cffex_member_rank_result(options: str) -> _WindResult:
    opts = _parse_wind_options(options)
    trade_date = normalize_trade_date(opts.get("date", ""))
    contract = normalize_cffex_contract(opts.get("windcode", "T.CFE"))
    rankby = str(opts.get("rankby", "volume") or "volume").strip().lower()
    if not trade_date:
        return _WindResult(ErrorCode=400, Fields=[], Data=[], ErrorMsg="cffexmemberrank requires date=YYYY-MM-DD")

    duckdb_path = resolve_system_duckdb_path()
    frame = load_member_rank_frame(duckdb_path, trade_date=trade_date, contract=contract)
    if frame.empty:
        return _WindResult(
            ErrorCode=404,
            Fields=[],
            Data=[],
            ErrorMsg=f"no Choice/Tushare CFFEX member-rank rows for {trade_date} {contract}",
        )

    field_map = {
        "longholdingvolume": ("long_holding", ["membername", "longholdingvolume", "longholdingchange"]),
        "shortholdingvolume": ("short_holding", ["membername", "shortholdingvolume", "shortholdingchange"]),
        "volume": ("volume", ["membername", "volume"]),
    }
    metric, fields = field_map.get(rankby, field_map["volume"])
    ordered = frame.sort_values(metric, ascending=False, na_position="last").head(20)
    data = [_field_values(ordered, field) for field in fields]
    return _WindResult(
        ErrorCode=0,
        Codes=[contract],
        Fields=fields,
        Times=[pd.Timestamp(trade_date)],
        Data=data,
        ErrorMsg="choice/tushare CFFEX member-rank source",
    )


def _field_values(frame: pd.DataFrame, field: str) -> list[str | float | None]:
    if field == "membername":
        return [str(item) for item in frame["member_name"].tolist()]
    if field == "longholdingvolume":
        return _numeric_values(frame, "long_holding")
    if field == "longholdingchange":
        return _numeric_values(frame, "long_change")
    if field == "shortholdingvolume":
        return _numeric_values(frame, "short_holding")
    if field == "shortholdingchange":
        return _numeric_values(frame, "short_change")
    if field == "volume":
        return _numeric_values(frame, "volume")
    return [None for _ in range(len(frame))]


def _numeric_values(frame: pd.DataFrame, column: str) -> list[float | None]:
    values: list[float | None] = []
    for value in frame[column].tolist():
        values.append(None if pd.isna(value) else float(value))
    return values


def _parse_wind_options(options: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in str(options or "").split(";"):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        out[key.strip().lower()] = value.strip()
    return out


w = _SystemChoiceTushareWind()
