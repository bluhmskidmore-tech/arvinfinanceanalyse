from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

import pandas as pd

try:
    import polars as pl
except ImportError:  # pragma: no cover - fallback is covered by monkeypatch tests.
    pl = None


TabularBackend = Literal["polars", "pandas"]


def preferred_tabular_backend() -> TabularBackend:
    return "polars" if pl is not None else "pandas"


def records_to_pandas(
    records: Sequence[Mapping[str, object]],
    *,
    date_columns: Sequence[str] = (),
    float_columns: Sequence[str] = (),
    bool_columns: Sequence[str] = (),
) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()

    if pl is None:
        frame = pd.DataFrame(records)
    else:
        frame = _records_to_polars(
            records,
            float_columns=float_columns,
            bool_columns=bool_columns,
        ).to_pandas()

    _normalize_pandas_columns(
        frame,
        date_columns=date_columns,
        float_columns=float_columns,
        bool_columns=bool_columns,
    )
    return frame


def _records_to_polars(
    records: Sequence[Mapping[str, object]],
    *,
    float_columns: Sequence[str],
    bool_columns: Sequence[str],
):
    frame = pl.from_dicts(records, infer_schema_length=None)
    expressions = []

    for column in float_columns:
        if column in frame.columns:
            expressions.append(
                pl.col(column).cast(pl.Float64, strict=False).fill_null(0.0).alias(column)
            )

    for column in bool_columns:
        if column in frame.columns:
            expressions.append(
                pl.col(column).cast(pl.Boolean, strict=False).fill_null(False).alias(column)
            )

    if expressions:
        frame = frame.with_columns(expressions)
    return frame


def _normalize_pandas_columns(
    frame: pd.DataFrame,
    *,
    date_columns: Sequence[str],
    float_columns: Sequence[str],
    bool_columns: Sequence[str],
) -> None:
    for column in date_columns:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], errors="coerce")

    for column in float_columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)

    for column in bool_columns:
        if column in frame.columns:
            frame[column] = frame[column].fillna(False).astype(bool)
