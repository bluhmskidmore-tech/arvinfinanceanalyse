from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from backend.app.core_finance.macro.toolkit.system_sources import load_series_by_alias


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


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


w = _SystemChoiceTushareWind()
