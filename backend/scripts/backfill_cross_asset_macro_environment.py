from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.choice_client import ChoiceClient
from backend.app.repositories.duckdb_migrations import (
    apply_pending_migrations_on_connection,
    ensure_choice_macro_schema_if_missing,
)
from backend.app.repositories.tushare_adapter import (
    import_tushare_pro,
    resolve_tushare_token_with_settings_fallback,
)


RULE_VERSION = "rv_cross_asset_macro_environment_backfill_v1"
CATALOG_VERSION = "2026-05-15.cross-asset-macro-environment.v1"
LOCK = LockDefinition(key="lock:duckdb:cross-asset-macro-environment-backfill", ttl_seconds=900)


@dataclass(frozen=True)
class SeriesMeta:
    series_id: str
    series_name: str
    vendor_name: str
    vendor_series_code: str
    frequency: str
    unit: str
    theme: str
    tags: tuple[str, ...]
    refresh_tier: str
    request_options: str
    fetch_mode: str
    fetch_granularity: str
    policy_note: str


@dataclass(frozen=True)
class MacroRow:
    series_id: str
    series_name: str
    vendor_series_code: str
    vendor_name: str
    trade_date: str
    value_numeric: float
    frequency: str
    unit: str
    source_version: str
    vendor_version: str


CHOICE_SERIES: dict[str, SeriesMeta] = {
    "EMM00166458": SeriesMeta(
        "EMM00166458",
        "中债国债到期收益率:1年",
        "choice",
        "EMM00166458",
        "daily",
        "%",
        "macro_environment",
        ("choice", "macro", "rates", "cross_asset"),
        "stable",
        "IsLatest=0,StartDate=__START_DATE__,EndDate=__END_DATE__,Ispandas=1,RECVtimeout=20",
        "date_slice",
        "batch",
        "Choice EDB historical backfill for cross-asset macro environment rate score.",
    ),
    "EMM00166462": SeriesMeta(
        "EMM00166462",
        "中债国债到期收益率:5年",
        "choice",
        "EMM00166462",
        "daily",
        "%",
        "macro_environment",
        ("choice", "macro", "rates", "cross_asset"),
        "stable",
        "IsLatest=0,StartDate=__START_DATE__,EndDate=__END_DATE__,Ispandas=1,RECVtimeout=20",
        "date_slice",
        "batch",
        "Choice EDB historical backfill for cross-asset macro environment rate score.",
    ),
    "EMM00166466": SeriesMeta(
        "EMM00166466",
        "中债国债到期收益率:10年",
        "choice",
        "EMM00166466",
        "daily",
        "%",
        "macro_environment",
        ("choice", "macro", "rates", "cross_asset"),
        "stable",
        "IsLatest=0,StartDate=__START_DATE__,EndDate=__END_DATE__,Ispandas=1,RECVtimeout=20",
        "date_slice",
        "batch",
        "Choice EDB historical backfill for cross-asset macro environment rate score.",
    ),
    "EMM00008445": SeriesMeta(
        "EMM00008445",
        "工业增加值:当月同比",
        "choice",
        "EMM00008445",
        "monthly",
        "%",
        "macro_environment",
        ("choice", "macro", "growth", "cross_asset"),
        "stable",
        "IsLatest=0,StartDate=__START_DATE__,EndDate=__END_DATE__,Ispandas=1,RECVtimeout=20",
        "date_slice",
        "batch",
        "Choice EDB historical backfill for cross-asset macro environment growth score.",
    ),
    "EMM00619381": SeriesMeta(
        "EMM00619381",
        "中国:GDP:现价:当季值",
        "choice",
        "EMM00619381",
        "quarterly",
        "亿元",
        "macro_environment",
        ("choice", "macro", "growth", "cross_asset"),
        "stable",
        "IsLatest=0,StartDate=__START_DATE__,EndDate=__END_DATE__,Ispandas=1,RECVtimeout=20",
        "date_slice",
        "batch",
        "Choice EDB historical backfill for cross-asset macro environment growth score.",
    ),
    "EMM00072301": SeriesMeta(
        "EMM00072301",
        "CPI:当月同比",
        "choice",
        "EMM00072301",
        "monthly",
        "%",
        "macro_environment",
        ("choice", "macro", "inflation", "cross_asset"),
        "stable",
        "IsLatest=0,StartDate=__START_DATE__,EndDate=__END_DATE__,Ispandas=1,RECVtimeout=20",
        "date_slice",
        "batch",
        "Choice EDB historical backfill for cross-asset macro environment inflation score.",
    ),
}


TUSHARE_SHIBOR_SERIES: dict[str, tuple[SeriesMeta, str]] = {
    "EMM00166252": (
        SeriesMeta(
            "EMM00166252",
            "SHIBOR:隔夜",
            "tushare",
            "shibor:on",
            "daily",
            "%",
            "macro_environment",
            ("tushare", "macro", "liquidity", "shibor", "cross_asset"),
            "fallback",
            "pro.shibor(start_date=__START_DATE__,end_date=__END_DATE__)",
            "date_slice",
            "batch",
            "Tushare SHIBOR fallback because Choice EDB returns no rows for EMM00166252 in the local account.",
        ),
        "on",
    ),
    "EMM00166253": (
        SeriesMeta(
            "EMM00166253",
            "SHIBOR:1周",
            "tushare",
            "shibor:1w",
            "daily",
            "%",
            "macro_environment",
            ("tushare", "macro", "liquidity", "shibor", "cross_asset"),
            "fallback",
            "pro.shibor(start_date=__START_DATE__,end_date=__END_DATE__)",
            "date_slice",
            "batch",
            "Tushare SHIBOR fallback because Choice EDB returns no rows for EMM00166253 in the local account.",
        ),
        "1w",
    ),
}


PUBLIC_REPO_SERIES: dict[str, tuple[SeriesMeta, str]] = {
    "CA.DR007": (
        SeriesMeta(
            "CA.DR007",
            "存款类机构质押式回购加权利率:DR007",
            "public_repo_rate_query",
            "repo_rate_hist:FDR007",
            "daily",
            "%",
            "macro_environment",
            ("public", "macro", "liquidity", "repo", "cross_asset"),
            "stable",
            "ak.repo_rate_hist(start_date=__START_DATE__,end_date=__END_DATE__).FDR007",
            "date_slice",
            "batch",
            "Public ChinaMoney repo fixing history via AkShare; used as governed DR007 liquidity input.",
        ),
        "FDR007",
    ),
}


def backfill_cross_asset_macro_environment(
    *,
    duckdb_path: str | None = None,
    start_date: str,
    end_date: str,
) -> dict[str, object]:
    settings = get_settings()
    db_path = Path(duckdb_path or settings.duckdb_path)
    run_id = f"cross_asset_macro_environment_backfill:{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"

    choice_rows = fetch_choice_environment_rows(start_date=start_date, end_date=end_date)
    tushare_rows = fetch_tushare_shibor_rows(start_date=start_date, end_date=end_date)
    public_repo_rows = fetch_public_dr007_rows(start_date=start_date, end_date=end_date)
    rows = [*choice_rows, *tushare_rows, *public_repo_rows]
    if not rows:
        raise RuntimeError("No Choice or Tushare rows were fetched for cross-asset macro environment backfill.")

    metas = {meta.series_id: meta for meta in CHOICE_SERIES.values()}
    metas.update({meta.series_id: meta for meta, _column in TUSHARE_SHIBOR_SERIES.values()})
    metas.update({meta.series_id: meta for meta, _column in PUBLIC_REPO_SERIES.values()})
    written = persist_macro_environment_rows(
        duckdb_path=db_path,
        rows=rows,
        metas=metas,
        run_id=run_id,
        start_date=start_date,
        end_date=end_date,
    )

    coverage = profile_macro_environment_coverage(db_path)
    return {
        "run_id": run_id,
        "start_date": start_date,
        "end_date": end_date,
        "choice_rows": len(choice_rows),
        "tushare_rows": len(tushare_rows),
        "public_repo_rows": len(public_repo_rows),
        "written_rows": written,
        "coverage": coverage,
    }


def fetch_choice_environment_rows(*, start_date: str, end_date: str) -> list[MacroRow]:
    client = ChoiceClient()
    request_options = _choice_request_options(start_date=start_date, end_date=end_date)
    result = client.edb([meta.vendor_series_code for meta in CHOICE_SERIES.values()], request_options)
    raw_rows = choice_edb_rows(result, CHOICE_SERIES)
    source_version = _source_version("choice_environment", raw_rows)
    vendor_version = f"vv_choice_edb_{start_date.replace('-', '')}_{end_date.replace('-', '')}"
    return [
        MacroRow(
            series_id=row["series_id"],
            series_name=row["series_name"],
            vendor_series_code=row["vendor_series_code"],
            vendor_name="choice",
            trade_date=row["trade_date"],
            value_numeric=row["value_numeric"],
            frequency=row["frequency"],
            unit=row["unit"],
            source_version=source_version,
            vendor_version=vendor_version,
        )
        for row in raw_rows
    ]


def fetch_tushare_shibor_rows(*, start_date: str, end_date: str) -> list[MacroRow]:
    settings = get_settings()
    token = resolve_tushare_token_with_settings_fallback(settings)
    if not token:
        raise RuntimeError("MOSS_TUSHARE_TOKEN is not configured; cannot backfill SHIBOR fallback rows.")

    ts = import_tushare_pro()
    pro = ts.pro_api(token)
    start_text = start_date.replace("-", "")
    end_text = end_date.replace("-", "")
    frame = pro.shibor(start_date=start_text, end_date=end_text)
    records = _records_from_frame(frame)
    raw_rows = tushare_shibor_rows(records)
    source_version = _source_version("tushare_shibor_environment", raw_rows)
    vendor_version = f"vv_tushare_shibor_{start_text}_{end_text}"
    return [
        MacroRow(
            series_id=row["series_id"],
            series_name=row["series_name"],
            vendor_series_code=row["vendor_series_code"],
            vendor_name="tushare",
            trade_date=row["trade_date"],
            value_numeric=row["value_numeric"],
            frequency=row["frequency"],
            unit=row["unit"],
            source_version=source_version,
            vendor_version=vendor_version,
        )
        for row in raw_rows
    ]


def fetch_public_dr007_rows(*, start_date: str, end_date: str) -> list[MacroRow]:
    import akshare as ak  # type: ignore

    records: list[dict[str, object]] = []
    for chunk_start, chunk_end in _month_ranges(start_date, end_date):
        frame = ak.repo_rate_hist(
            start_date=chunk_start.replace("-", ""),
            end_date=chunk_end.replace("-", ""),
        )
        records.extend(_records_from_frame(frame))

    raw_rows = public_dr007_rows(records, start_date=start_date, end_date=end_date)
    source_version = _source_version("public_repo_dr007_environment", raw_rows)
    vendor_version = f"vv_public_repo_dr007_{start_date.replace('-', '')}_{end_date.replace('-', '')}"
    return [
        MacroRow(
            series_id=row["series_id"],
            series_name=row["series_name"],
            vendor_series_code=row["vendor_series_code"],
            vendor_name="public_repo_rate_query",
            trade_date=row["trade_date"],
            value_numeric=row["value_numeric"],
            frequency=row["frequency"],
            unit=row["unit"],
            source_version=source_version,
            vendor_version=vendor_version,
        )
        for row in raw_rows
    ]


def choice_edb_rows(result: object, metas: dict[str, SeriesMeta]) -> list[dict[str, Any]]:
    if _is_pandas_dataframe(result):
        return _choice_dataframe_rows(result, metas)
    return _choice_emquant_rows(result, metas)


def tushare_shibor_rows(records: list[dict[str, object]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        trade_date = normalize_trade_date(record.get("date"))
        if trade_date is None:
            continue
        for meta, column in TUSHARE_SHIBOR_SERIES.values():
            value = _coerce_float(record.get(column))
            if value is None:
                continue
            rows.append(_raw_row(meta, trade_date, value))
    return sorted(rows, key=lambda item: (item["series_id"], item["trade_date"]))


def public_dr007_rows(
    records: list[dict[str, object]],
    *,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    meta, column = PUBLIC_REPO_SERIES["CA.DR007"]
    rows: list[dict[str, Any]] = []
    seen_dates: set[str] = set()
    for record in records:
        trade_date = normalize_trade_date(record.get("date"))
        if trade_date is None or trade_date < start_date or trade_date > end_date:
            continue
        if trade_date in seen_dates:
            continue
        value = _coerce_float(record.get(column))
        if value is None:
            continue
        rows.append(_raw_row(meta, trade_date, value))
        seen_dates.add(trade_date)
    return sorted(rows, key=lambda item: (item["series_id"], item["trade_date"]))


def persist_macro_environment_rows(
    *,
    duckdb_path: Path,
    rows: list[MacroRow],
    metas: dict[str, SeriesMeta],
    run_id: str,
    start_date: str,
    end_date: str,
) -> int:
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    target_series = sorted({row.series_id for row in rows})
    with acquire_lock(LOCK, base_dir=duckdb_path.parent):
        conn = duckdb.connect(str(duckdb_path), read_only=False)
        try:
            apply_pending_migrations_on_connection(conn)
            ensure_choice_macro_schema_if_missing(conn)
            conn.execute("begin transaction")
            placeholders = ", ".join(["?"] * len(target_series))
            delete_params = [*target_series, start_date, end_date]
            conn.execute(
                f"""
                delete from choice_market_snapshot
                where series_id in ({placeholders}) and trade_date between ? and ?
                """,
                delete_params,
            )
            conn.execute(
                f"""
                delete from fact_choice_macro_daily
                where series_id in ({placeholders}) and trade_date between ? and ?
                """,
                delete_params,
            )
            conn.execute(f"delete from phase1_macro_vendor_catalog where series_id in ({placeholders})", target_series)
            conn.execute(f"delete from market_data_series_category where series_id in ({placeholders})", target_series)

            for row in rows:
                conn.execute(
                    """
                    insert into choice_market_snapshot values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        row.series_id,
                        row.series_name,
                        row.vendor_series_code,
                        row.vendor_name,
                        row.trade_date,
                        row.value_numeric,
                        row.frequency,
                        row.unit,
                        row.source_version,
                        row.vendor_version,
                        RULE_VERSION,
                        run_id,
                    ],
                )
                conn.execute(
                    """
                    insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        row.series_id,
                        row.series_name,
                        row.trade_date,
                        row.value_numeric,
                        row.frequency,
                        row.unit,
                        row.source_version,
                        row.vendor_version,
                        RULE_VERSION,
                        "ok",
                        run_id,
                    ],
                )

            for series_id in sorted(metas):
                if series_id not in target_series:
                    continue
                meta = metas[series_id]
                row_vendor_version = next((row.vendor_version for row in rows if row.series_id == series_id), "")
                request_options = meta.request_options.replace("__START_DATE__", start_date).replace(
                    "__END_DATE__", end_date
                )
                conn.execute(
                    """
                    insert into phase1_macro_vendor_catalog values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        meta.series_id,
                        meta.series_name,
                        meta.vendor_name,
                        row_vendor_version,
                        meta.frequency,
                        meta.unit,
                        meta.vendor_series_code,
                        "cross_asset_macro_environment_backfill",
                        CATALOG_VERSION,
                        meta.theme,
                        True,
                        json.dumps(meta.tags, ensure_ascii=False, separators=(",", ":")),
                        request_options,
                        meta.fetch_mode,
                        meta.fetch_granularity,
                        meta.refresh_tier,
                        meta.policy_note,
                    ],
                )
                conn.execute(
                    """
                    insert into market_data_series_category values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        meta.series_id,
                        meta.refresh_tier,
                        _category_label(meta.refresh_tier),
                        "choice_macro",
                        meta.fetch_mode,
                        meta.fetch_granularity,
                        meta.policy_note,
                        CATALOG_VERSION,
                        "cross_asset_macro_environment_backfill",
                        datetime.now(UTC).replace(microsecond=0).isoformat(),
                        run_id,
                    ],
                )
            conn.execute("commit")
            return len(rows)
        except Exception:
            conn.execute("rollback")
            raise
        finally:
            conn.close()


def profile_macro_environment_coverage(duckdb_path: Path) -> list[dict[str, object]]:
    series_ids = sorted({*CHOICE_SERIES.keys(), *TUSHARE_SHIBOR_SERIES.keys(), *PUBLIC_REPO_SERIES.keys()})
    placeholders = ", ".join(["?"] * len(series_ids))
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        result = conn.execute(
            f"""
            select series_id, min(trade_date), max(trade_date), count(*) as row_count,
                   count(distinct trade_date) as trade_date_count
            from fact_choice_macro_daily
            where series_id in ({placeholders})
            group by series_id
            order by series_id
            """,
            series_ids,
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "series_id": str(row[0]),
            "min_trade_date": str(row[1]),
            "max_trade_date": str(row[2]),
            "row_count": int(row[3]),
            "trade_date_count": int(row[4]),
        }
        for row in result
    ]


def _choice_request_options(*, start_date: str, end_date: str) -> str:
    return f"IsLatest=0,StartDate={start_date},EndDate={end_date},Ispandas=1,RECVtimeout=20"


def _choice_dataframe_rows(frame: object, metas: dict[str, SeriesMeta]) -> list[dict[str, Any]]:
    frame_any = frame
    rows: list[dict[str, Any]] = []
    for meta in metas.values():
        if meta.vendor_series_code not in frame_any.index:
            continue
        code_rows = frame_any.loc[[meta.vendor_series_code]]
        for record in code_rows.to_dict(orient="records"):
            trade_date = normalize_trade_date(record.get("DATES"))
            value = _coerce_float(record.get("RESULT"))
            if trade_date is None or value is None:
                continue
            rows.append(_raw_row(meta, trade_date, value))
    return sorted(rows, key=lambda item: (item["series_id"], item["trade_date"]))


def _choice_emquant_rows(result: object, metas: dict[str, SeriesMeta]) -> list[dict[str, Any]]:
    error_code = int(getattr(result, "ErrorCode", 0) or 0)
    if error_code != 0:
        raise RuntimeError(getattr(result, "ErrorMsg", f"Choice edb failed: {error_code}"))

    codes = [str(code) for code in getattr(result, "Codes", [])]
    dates = [normalize_trade_date(item) for item in getattr(result, "Dates", [])]
    data = getattr(result, "Data", {}) or {}
    meta_by_code = {meta.vendor_series_code: meta for meta in metas.values()}
    rows: list[dict[str, Any]] = []
    for code in codes:
        meta = meta_by_code.get(code)
        if meta is None:
            continue
        value_groups = data.get(code, [])
        values = value_groups[0] if value_groups else []
        for trade_date, raw_value in zip(dates, values, strict=False):
            value = _coerce_float(raw_value)
            if trade_date is None or value is None:
                continue
            rows.append(_raw_row(meta, trade_date, value))
    return sorted(rows, key=lambda item: (item["series_id"], item["trade_date"]))


def _raw_row(meta: SeriesMeta, trade_date: str, value: float) -> dict[str, Any]:
    return {
        "series_id": meta.series_id,
        "series_name": meta.series_name,
        "vendor_series_code": meta.vendor_series_code,
        "trade_date": trade_date,
        "value_numeric": value,
        "frequency": meta.frequency,
        "unit": meta.unit,
    }


def _records_from_frame(frame: object) -> list[dict[str, object]]:
    if frame is None:
        return []
    if len(frame) == 0:  # type: ignore[arg-type]
        return []
    return list(frame.to_dict(orient="records"))  # type: ignore[attr-defined]


def _month_ranges(start_date: str, end_date: str) -> list[tuple[str, str]]:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    ranges: list[tuple[str, str]] = []
    current = start
    while current <= end:
        if current.month == 12:
            next_month = date(current.year + 1, 1, 1)
        else:
            next_month = date(current.year, current.month + 1, 1)
        chunk_end = min(end, next_month - timedelta(days=1))
        ranges.append((current.isoformat(), chunk_end.isoformat()))
        current = chunk_end + timedelta(days=1)
    return ranges


def normalize_trade_date(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    normalized = text.replace("/", "-")
    if len(normalized) >= 10 and normalized[4] == "-" and normalized[7] == "-":
        return normalized[:10]
    return normalized


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    return float(text)


def _source_version(prefix: str, rows: list[dict[str, object]]) -> str:
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"sv_{prefix}_{digest}"


def _category_label(refresh_tier: str) -> str:
    return {
        "stable": "Stable governed series",
        "fallback": "Fallback latest-only series",
        "isolated": "Isolated vendor-pending series",
    }.get(refresh_tier, refresh_tier)


def _is_pandas_dataframe(value: object) -> bool:
    return value.__class__.__name__ == "DataFrame"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill cross-asset macro environment inputs into DuckDB.")
    parser.add_argument("--duckdb-path", default=None)
    parser.add_argument("--start-date", default="2025-01-01")
    parser.add_argument("--end-date", default=date.today().isoformat())
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = backfill_cross_asset_macro_environment(
        duckdb_path=args.duckdb_path,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
