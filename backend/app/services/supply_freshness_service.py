"""Read-only freshness checks for stock-analysis supply inputs.

The calendar intentionally skips weekends only.  Statutory holidays are not
available in this repository's current refresh convention, so callers should
interpret holiday-period lag with that limitation in mind.
"""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb
from backend.app.core_finance.cycle_macro_score import (
    CN10Y_SERIES_ID,
    CSI300_PE_SERIES_ID,
)
from backend.app.repositories.duckdb_repo import read_only_connection
from backend.app.repositories.stock_analysis_theme_overlay_reader import (
    THEME_OVERLAY_CACHE_KEY,
    ThemeOverlayManifestAccessor,
)

BROAD_INDEX_SERIES_ID = "CA.CSI300"
DEFAULT_STALE_AFTER_TRADING_DAYS = 1
DEFAULT_CRITICAL_AFTER_TRADING_DAYS = 5


@dataclass(frozen=True)
class _DuckDBSeriesSpec:
    name: str
    table_name: str
    date_column: str
    query: str
    parameters: tuple[object, ...] = ()
    series_id: str | None = None


_DUCKDB_SERIES_SPECS = (
    _DuckDBSeriesSpec(
        name="csi300_index",
        table_name="fact_choice_macro_daily",
        date_column="trade_date",
        query=(
            "select max(try_cast(trade_date as date)) "
            "from fact_choice_macro_daily "
            "where series_id = ? and value_numeric is not null"
        ),
        parameters=(BROAD_INDEX_SERIES_ID,),
        series_id=BROAD_INDEX_SERIES_ID,
    ),
    _DuckDBSeriesSpec(
        name="csi300_pe",
        table_name="fact_choice_macro_daily",
        date_column="trade_date",
        query=(
            "select max(try_cast(trade_date as date)) "
            "from fact_choice_macro_daily "
            "where series_id = ? and value_numeric is not null"
        ),
        parameters=(CSI300_PE_SERIES_ID,),
        series_id=CSI300_PE_SERIES_ID,
    ),
    _DuckDBSeriesSpec(
        name="cn10y_yield",
        table_name="fact_choice_macro_daily",
        date_column="trade_date",
        query=(
            "select max(try_cast(trade_date as date)) "
            "from fact_choice_macro_daily "
            "where series_id = ? and value_numeric is not null"
        ),
        parameters=(CN10Y_SERIES_ID,),
        series_id=CN10Y_SERIES_ID,
    ),
    _DuckDBSeriesSpec(
        name="choice_stock_daily",
        table_name="choice_stock_daily_observation",
        date_column="trade_date",
        query=(
            "select max(try_cast(trade_date as date)) "
            "from choice_stock_daily_observation "
            "where close_value is not null and close_value > 0"
        ),
    ),
    _DuckDBSeriesSpec(
        name="choice_stock_factor_snapshot",
        table_name="choice_stock_factor_snapshot",
        date_column="as_of_date",
        query=(
            "select max(try_cast(as_of_date as date)) "
            "from choice_stock_factor_snapshot"
        ),
    ),
    _DuckDBSeriesSpec(
        name="livermore_gate_supplement",
        table_name="fact_livermore_gate_supplement_daily",
        date_column="trade_date",
        query=(
            "select max(try_cast(trade_date as date)) "
            "from fact_livermore_gate_supplement_daily "
            "where breadth_5d is not null or limit_up_quality_ok is not null"
        ),
    ),
    _DuckDBSeriesSpec(
        name="livermore_position_snapshot",
        table_name="livermore_position_snapshot",
        date_column="as_of_date",
        query=(
            "select max(try_cast(as_of_date as date)) "
            "from livermore_position_snapshot"
        ),
    ),
)

_STATUS_PRIORITY = {
    "fresh": 0,
    "stale": 1,
    "missing": 2,
    "critical": 3,
    "unavailable": 4,
}


def resolve_expected_trading_date(value: date | datetime | str | None = None) -> date:
    """Resolve the latest expected weekday on or before ``value``."""

    if value is None:
        resolved = date.today()
    elif isinstance(value, datetime):
        resolved = value.date()
    elif isinstance(value, date):
        resolved = value
    else:
        resolved = date.fromisoformat(str(value).strip())
    while resolved.weekday() >= 5:
        resolved -= timedelta(days=1)
    return resolved


def build_supply_freshness_report(
    *,
    governance_path: Path | str,
    duckdb_path: Path | str | None = None,
    connection: duckdb.DuckDBPyConnection | None = None,
    as_of_date: date | datetime | str | None = None,
    stale_after_trading_days: int = DEFAULT_STALE_AFTER_TRADING_DAYS,
    critical_after_trading_days: int = DEFAULT_CRITICAL_AFTER_TRADING_DAYS,
) -> dict[str, object]:
    """Return a JSON-serializable report without mutating DuckDB or governance."""

    _validate_thresholds(
        stale_after_trading_days=stale_after_trading_days,
        critical_after_trading_days=critical_after_trading_days,
    )
    expected_date = resolve_expected_trading_date(as_of_date)
    series = _read_duckdb_series(
        expected_date=expected_date,
        duckdb_path=duckdb_path,
        connection=connection,
        stale_after_trading_days=stale_after_trading_days,
        critical_after_trading_days=critical_after_trading_days,
    )
    series.append(
        _read_theme_overlay_series(
            governance_path=governance_path,
            expected_date=expected_date,
            stale_after_trading_days=stale_after_trading_days,
            critical_after_trading_days=critical_after_trading_days,
        )
    )
    overall_status = max(
        (str(item["status"]) for item in series),
        key=lambda status: _STATUS_PRIORITY[status],
    )
    return {
        "status": overall_status,
        "expected_date": expected_date.isoformat(),
        "thresholds": {
            "stale_after_trading_days": stale_after_trading_days,
            "critical_after_trading_days": critical_after_trading_days,
        },
        "calendar": {
            "basis": "weekday_only",
            "holiday_aware": False,
            "limitation": (
                "Weekends are excluded; statutory holidays are not recognized "
                "because no exchange calendar dependency is configured."
            ),
        },
        "series": series,
    }


def _validate_thresholds(
    *,
    stale_after_trading_days: int,
    critical_after_trading_days: int,
) -> None:
    if (
        isinstance(stale_after_trading_days, bool)
        or not isinstance(stale_after_trading_days, int)
        or stale_after_trading_days < 0
    ):
        raise ValueError("stale_after_trading_days must be a non-negative integer")
    if (
        isinstance(critical_after_trading_days, bool)
        or not isinstance(critical_after_trading_days, int)
        or critical_after_trading_days <= stale_after_trading_days
    ):
        raise ValueError(
            "critical_after_trading_days must be an integer greater than "
            "stale_after_trading_days"
        )


def _read_duckdb_series(
    *,
    expected_date: date,
    duckdb_path: Path | str | None,
    connection: duckdb.DuckDBPyConnection | None,
    stale_after_trading_days: int,
    critical_after_trading_days: int,
) -> list[dict[str, object]]:
    with ExitStack() as stack:
        conn = connection
        if conn is None:
            if duckdb_path is None:
                return _all_duckdb_unavailable(
                    expected_date=expected_date,
                    reason="duckdb_path_not_configured",
                )
            path = Path(duckdb_path)
            if not path.is_file():
                return _all_duckdb_unavailable(
                    expected_date=expected_date,
                    reason="duckdb_path_missing",
                )
            try:
                conn = stack.enter_context(read_only_connection(str(path)))
            except Exception as exc:  # noqa: BLE001 - lock/unavailability is report data
                return _all_duckdb_unavailable(
                    expected_date=expected_date,
                    reason=_duckdb_error_reason(exc, fallback="duckdb_unavailable"),
                    detail=_error_detail(exc),
                )

        try:
            tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
        except Exception as exc:  # noqa: BLE001 - query failure must not crash the sentinel
            return _all_duckdb_unavailable(
                expected_date=expected_date,
                reason=_duckdb_error_reason(exc, fallback="duckdb_query_failed"),
                detail=_error_detail(exc),
            )

        records: list[dict[str, object]] = []
        for spec in _DUCKDB_SERIES_SPECS:
            if spec.table_name not in tables:
                records.append(
                    _missing_record(
                        spec=spec,
                        expected_date=expected_date,
                        reason="table_missing",
                    )
                )
                continue
            try:
                row = conn.execute(spec.query, list(spec.parameters)).fetchone()
            except Exception as exc:  # noqa: BLE001 - isolate one bad relation
                records.append(
                    _unavailable_record(
                        spec=spec,
                        expected_date=expected_date,
                        reason=_duckdb_error_reason(exc, fallback="duckdb_query_failed"),
                        detail=_error_detail(exc),
                    )
                )
                continue
            latest_date = _coerce_date(row[0] if row else None)
            if latest_date is None:
                records.append(
                    _missing_record(
                        spec=spec,
                        expected_date=expected_date,
                        reason="series_missing" if spec.series_id else "no_valid_rows",
                    )
                )
                continue
            records.append(
                _dated_record(
                    name=spec.name,
                    source_kind="duckdb",
                    table_name=spec.table_name,
                    date_column=spec.date_column,
                    series_id=spec.series_id,
                    latest_date=latest_date,
                    expected_date=expected_date,
                    stale_after_trading_days=stale_after_trading_days,
                    critical_after_trading_days=critical_after_trading_days,
                )
            )
        return records


def _read_theme_overlay_series(
    *,
    governance_path: Path | str,
    expected_date: date,
    stale_after_trading_days: int,
    critical_after_trading_days: int,
) -> dict[str, object]:
    base = {
        "name": "stock_analysis_theme_overlay",
        "source_kind": "governance_jsonl",
        "table_name": None,
        "date_column": "report_date",
        "cache_key": THEME_OVERLAY_CACHE_KEY,
        "latest_date": None,
        "expected_date": expected_date.isoformat(),
        "lag_trading_days": None,
    }
    try:
        manifest = ThemeOverlayManifestAccessor(governance_path).read_latest_manifest(
            THEME_OVERLAY_CACHE_KEY
        )
    except Exception as exc:  # noqa: BLE001 - governance degradation is report data
        return {
            **base,
            "status": "unavailable",
            "reason": "governance_manifest_unavailable",
            "detail": _error_detail(exc),
        }
    if manifest is None:
        return {
            **base,
            "status": "missing",
            "reason": "governance_manifest_missing",
        }
    try:
        latest_date = date.fromisoformat(str(manifest.get("report_date") or "").strip())
    except ValueError as exc:
        return {
            **base,
            "status": "unavailable",
            "reason": "governance_report_date_invalid",
            "detail": _error_detail(exc),
        }
    return _dated_record(
        name=str(base["name"]),
        source_kind=str(base["source_kind"]),
        table_name=None,
        date_column=str(base["date_column"]),
        series_id=None,
        latest_date=latest_date,
        expected_date=expected_date,
        stale_after_trading_days=stale_after_trading_days,
        critical_after_trading_days=critical_after_trading_days,
        cache_key=THEME_OVERLAY_CACHE_KEY,
    )


def _dated_record(
    *,
    name: str,
    source_kind: str,
    table_name: str | None,
    date_column: str,
    series_id: str | None,
    latest_date: date,
    expected_date: date,
    stale_after_trading_days: int,
    critical_after_trading_days: int,
    cache_key: str | None = None,
) -> dict[str, object]:
    lag = _trading_day_lag(latest_date, expected_date)
    if lag > critical_after_trading_days:
        status = "critical"
        reason = "lag_exceeds_critical_threshold"
    elif lag > stale_after_trading_days:
        status = "stale"
        reason = "lag_exceeds_stale_threshold"
    else:
        status = "fresh"
        reason = "within_freshness_threshold"
    record: dict[str, object] = {
        "name": name,
        "source_kind": source_kind,
        "table_name": table_name,
        "date_column": date_column,
        "latest_date": latest_date.isoformat(),
        "expected_date": expected_date.isoformat(),
        "lag_trading_days": lag,
        "status": status,
        "reason": reason,
    }
    if series_id is not None:
        record["series_id"] = series_id
    if cache_key is not None:
        record["cache_key"] = cache_key
    return record


def _missing_record(
    *,
    spec: _DuckDBSeriesSpec,
    expected_date: date,
    reason: str,
) -> dict[str, object]:
    return {
        **_spec_identity(spec),
        "latest_date": None,
        "expected_date": expected_date.isoformat(),
        "lag_trading_days": None,
        "status": "missing",
        "reason": reason,
    }


def _unavailable_record(
    *,
    spec: _DuckDBSeriesSpec,
    expected_date: date,
    reason: str,
    detail: str | None = None,
) -> dict[str, object]:
    record: dict[str, object] = {
        **_spec_identity(spec),
        "latest_date": None,
        "expected_date": expected_date.isoformat(),
        "lag_trading_days": None,
        "status": "unavailable",
        "reason": reason,
    }
    if detail:
        record["detail"] = detail
    return record


def _all_duckdb_unavailable(
    *,
    expected_date: date,
    reason: str,
    detail: str | None = None,
) -> list[dict[str, object]]:
    return [
        _unavailable_record(
            spec=spec,
            expected_date=expected_date,
            reason=reason,
            detail=detail,
        )
        for spec in _DUCKDB_SERIES_SPECS
    ]


def _spec_identity(spec: _DuckDBSeriesSpec) -> dict[str, object]:
    identity: dict[str, object] = {
        "name": spec.name,
        "source_kind": "duckdb",
        "table_name": spec.table_name,
        "date_column": spec.date_column,
    }
    if spec.series_id is not None:
        identity["series_id"] = spec.series_id
    return identity


def _trading_day_lag(latest_date: date, expected_date: date) -> int:
    if latest_date >= expected_date:
        return 0
    lag = 0
    cursor = latest_date + timedelta(days=1)
    while cursor <= expected_date:
        if cursor.weekday() < 5:
            lag += 1
        cursor += timedelta(days=1)
    return lag


def _coerce_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def _duckdb_error_reason(exc: BaseException, *, fallback: str) -> str:
    message = str(exc).casefold()
    if isinstance(exc, duckdb.Error) and any(
        token in message
        for token in (
            "already open",
            "database is locked",
            "could not set lock",
            "conflicting lock",
            "lock on file",
        )
    ):
        return "duckdb_locked"
    return fallback


def _error_detail(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"[:500]
