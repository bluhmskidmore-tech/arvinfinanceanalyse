from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import duckdb
from backend.app.governance.settings import get_settings
from backend.app.schemas.ncd_proxy import NcdFundingProxyPayload, NcdFundingProxyRow
from backend.app.services.formal_result_runtime import (
    QualityFlag,
    VendorStatus,
    build_result_envelope,
)

RULE_VERSION = "rv_ncd_proxy_v1"
CACHE_VERSION = "cv_ncd_proxy_v1"
PROXY_WARNING = "Proxy only; not actual NCD issuance matrix."
REQUIRED_SHIBOR_TENORS = ("1M", "3M", "6M", "9M", "1Y")
SOURCE_VENDOR_PREFERENCE = {"choice": 2, "tushare": 1}


@dataclass(frozen=True)
class _ProxyPoint:
    trade_date: datetime
    value_numeric: float
    source_version: str | None
    vendor_version: str | None


@dataclass(frozen=True)
class _ProxyCandidate:
    vendor_name: str
    points_by_tenor: dict[str, _ProxyPoint]


@dataclass(frozen=True)
class _ProxyPayloadResult:
    payload: NcdFundingProxyPayload
    source_version: str
    vendor_version: str


def load_ncd_funding_proxy_payload() -> NcdFundingProxyPayload:
    return _load_ncd_funding_proxy_result().payload


def _load_ncd_funding_proxy_result() -> _ProxyPayloadResult:
    settings = get_settings()
    landed_result = _load_landed_ncd_funding_proxy_result(str(settings.duckdb_path))
    if landed_result is not None:
        return landed_result

    return _ProxyPayloadResult(
        payload=NcdFundingProxyPayload(
            proxy_label="Choice/Tushare Shibor funding proxy",
            rows=[],
            warnings=[
                f"{PROXY_WARNING} Landed Choice/Tushare Shibor proxy data unavailable; "
                "refresh the external data warehouse."
            ],
        ),
        source_version="sv_ncd_proxy_empty",
        vendor_version="vv_none",
    )


def _load_landed_ncd_funding_proxy_result(duckdb_path: str) -> _ProxyPayloadResult | None:
    duckdb_file = Path(duckdb_path)
    if not duckdb_file.exists():
        return None
    try:
        conn = duckdb.connect(str(duckdb_file), read_only=True)
    except duckdb.Error:
        return None

    try:
        candidate = _load_landed_shibor_candidate(conn)
    finally:
        conn.close()

    if candidate is None:
        return None

    selected_points = candidate.points_by_tenor
    as_of_date = max(selected_points[tenor].trade_date for tenor in REQUIRED_SHIBOR_TENORS).date().isoformat()
    display_vendor = _display_vendor_name(candidate.vendor_name)
    source_version = _combine_versions(
        selected_points[tenor].source_version for tenor in REQUIRED_SHIBOR_TENORS
    )
    vendor_version = _combine_versions(
        selected_points[tenor].vendor_version for tenor in REQUIRED_SHIBOR_TENORS
    )
    return _ProxyPayloadResult(
        payload=NcdFundingProxyPayload(
            as_of_date=as_of_date,
            proxy_label=f"{display_vendor} Shibor funding proxy",
            rows=[
                _build_proxy_row(
                    row_key="shibor_fixing",
                    label="Shibor fixing",
                    values={tenor: selected_points[tenor].value_numeric for tenor in REQUIRED_SHIBOR_TENORS},
                    quote_count=None,
                ),
            ],
            warnings=[PROXY_WARNING, f"Using landed {display_vendor} Shibor; quote medians unavailable."],
        ),
        source_version=source_version,
        vendor_version=vendor_version,
    )


def _load_landed_shibor_candidate(conn: duckdb.DuckDBPyConnection) -> _ProxyCandidate | None:
    candidates = _load_landed_shibor_candidates(conn)
    complete_candidates = [
        candidate
        for candidate in candidates.values()
        if all(tenor in candidate.points_by_tenor for tenor in REQUIRED_SHIBOR_TENORS)
    ]
    if not complete_candidates:
        return None
    return max(
        complete_candidates,
        key=lambda candidate: (
            max(candidate.points_by_tenor[tenor].trade_date for tenor in REQUIRED_SHIBOR_TENORS),
            SOURCE_VENDOR_PREFERENCE.get(candidate.vendor_name, 0),
        ),
    )


def _load_landed_shibor_candidates(conn: duckdb.DuckDBPyConnection) -> dict[str, _ProxyCandidate]:
    latest: dict[str, dict[str, _ProxyPoint]] = {"choice": {}, "tushare": {}}
    for row in _iter_landed_shibor_rows(conn):
        series_id = str(row["series_id"] or "")
        series_name = str(row["series_name"] or "")
        tenor = _shibor_tenor_from_text(f"{series_id} {series_name}")
        if tenor is None:
            continue
        vendor_name = _canonical_proxy_vendor(
            row["vendor_name"],
            series_id=series_id,
            source_version=row["source_version"],
            vendor_version=row["vendor_version"],
        )
        if vendor_name not in latest:
            continue
        point = _ProxyPoint(
            trade_date=row["trade_date"],
            value_numeric=float(row["value_numeric"]),
            source_version=_optional_text(row["source_version"]),
            vendor_version=_optional_text(row["vendor_version"]),
        )
        current = latest[vendor_name].get(tenor)
        if current is None or point.trade_date > current.trade_date:
            latest[vendor_name][tenor] = point
    return {
        vendor_name: _ProxyCandidate(vendor_name=vendor_name, points_by_tenor=points)
        for vendor_name, points in latest.items()
        if points
    }


def _iter_landed_shibor_rows(conn: duckdb.DuckDBPyConnection) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if _relation_exists(conn, "choice_market_snapshot"):
        rows.extend(
            _fetch_landed_shibor_rows(
                conn,
                """
                select
                  series_id,
                  series_name,
                  vendor_name,
                  cast(trade_date as timestamp) as trade_date,
                  cast(value_numeric as double) as value_numeric,
                  source_version,
                  vendor_version
                from choice_market_snapshot
                where value_numeric is not null
                  and (
                    lower(series_id) like '%shibor%'
                    or lower(series_name) like '%shibor%'
                  )
                """,
            )
        )
    if _relation_exists(conn, "fact_choice_macro_daily"):
        if _relation_exists(conn, "phase1_macro_vendor_catalog"):
            fact_sql = """
                select
                  f.series_id,
                  f.series_name,
                  c.vendor_name,
                  cast(f.trade_date as timestamp) as trade_date,
                  cast(f.value_numeric as double) as value_numeric,
                  f.source_version,
                  f.vendor_version
                from fact_choice_macro_daily f
                left join phase1_macro_vendor_catalog c on c.series_id = f.series_id
                where f.value_numeric is not null
                  and (
                    lower(f.series_id) like '%shibor%'
                    or lower(f.series_name) like '%shibor%'
                  )
            """
        else:
            fact_sql = """
                select
                  series_id,
                  series_name,
                  cast(null as varchar) as vendor_name,
                  cast(trade_date as timestamp) as trade_date,
                  cast(value_numeric as double) as value_numeric,
                  source_version,
                  vendor_version
                from fact_choice_macro_daily
                where value_numeric is not null
                  and (
                    lower(series_id) like '%shibor%'
                    or lower(series_name) like '%shibor%'
                  )
            """
        rows.extend(_fetch_landed_shibor_rows(conn, fact_sql))
    return rows


def _fetch_landed_shibor_rows(conn: duckdb.DuckDBPyConnection, sql: str) -> list[dict[str, object]]:
    try:
        cursor = conn.execute(sql)
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    except duckdb.Error:
        return []


def _relation_exists(conn: duckdb.DuckDBPyConnection, relation_name: str) -> bool:
    row = conn.execute(
        """
        select 1
        from information_schema.tables
        where table_name = ?
        union all
        select 1
        from information_schema.views
        where table_name = ?
        limit 1
        """,
        [relation_name, relation_name],
    ).fetchone()
    return row is not None


def _shibor_tenor_from_text(text: str) -> str | None:
    normalized = str(text or "").lower().replace("_", "").replace("-", "").replace(".", "")
    mapping = {
        "1M": ("1m", "1月", "一个月"),
        "3M": ("3m", "3月", "三个月"),
        "6M": ("6m", "6月", "六个月"),
        "9M": ("9m", "9月", "九个月"),
        "1Y": ("1y", "1年", "一年"),
    }
    for tenor, tokens in mapping.items():
        if any(token in normalized for token in tokens):
            return tenor
    return None


def _canonical_proxy_vendor(
    raw_vendor_name: object,
    *,
    series_id: str,
    source_version: object,
    vendor_version: object,
) -> str | None:
    vendor_text = str(raw_vendor_name or "").casefold()
    version_text = f"{source_version or ''} {vendor_version or ''}".casefold()
    series_text = series_id.casefold()
    if "choice" in vendor_text or "choice" in version_text:
        return "choice"
    if "tushare" in vendor_text or "tushare" in version_text or series_text.startswith("ncd.shibor."):
        return "tushare"
    return None


def _display_vendor_name(vendor_name: str) -> str:
    return {"choice": "Choice", "tushare": "Tushare"}.get(vendor_name, vendor_name)


def _combine_versions(values: Iterable[object]) -> str:
    unique = []
    for value in values:
        text = _optional_text(value)
        if text and text not in unique:
            unique.append(text)
    return "__".join(unique) if unique else "unknown"


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def ncd_funding_proxy_envelope() -> dict[str, object]:
    result = _load_ncd_funding_proxy_result()
    payload = result.payload
    quality_flag: QualityFlag = "ok" if payload.rows else "warning"
    vendor_status: VendorStatus = "ok" if payload.rows else "vendor_unavailable"
    return build_result_envelope(
        basis="analytical",
        trace_id="tr_ncd_funding_proxy",
        result_kind="market_data.ncd_proxy",
        cache_version=CACHE_VERSION,
        source_version=result.source_version,
        rule_version=RULE_VERSION,
        quality_flag=quality_flag,
        vendor_version=result.vendor_version,
        vendor_status=vendor_status,
        fallback_mode="none",
        result_payload=payload.model_dump(mode="json", by_alias=True),
    )


def _build_proxy_row(
    *,
    row_key: str,
    label: str,
    values: dict[str, float | None],
    quote_count: int | None,
) -> NcdFundingProxyRow:
    return NcdFundingProxyRow.model_validate(
        {
            "row_key": row_key,
            "label": label,
            "1M": values.get("1M"),
            "3M": values.get("3M"),
            "6M": values.get("6M"),
            "9M": values.get("9M"),
            "1Y": values.get("1Y"),
            "quote_count": quote_count,
        }
    )
