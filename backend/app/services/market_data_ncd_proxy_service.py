from __future__ import annotations

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
LANDED_PROXY_WARNING = "Using landed external warehouse Shibor; quote medians unavailable."
REQUIRED_SHIBOR_TENORS = ("1M", "3M", "6M", "9M", "1Y")


def load_ncd_funding_proxy_payload() -> NcdFundingProxyPayload:
    settings = get_settings()
    landed_payload = _load_landed_ncd_funding_proxy_payload(str(settings.duckdb_path))
    if landed_payload is not None:
        return landed_payload

    return NcdFundingProxyPayload(
        proxy_label="Tushare Shibor funding proxy",
        rows=[],
        warnings=[f"{PROXY_WARNING} Landed Shibor proxy data unavailable; refresh the external data warehouse."],
    )


def _load_landed_ncd_funding_proxy_payload(duckdb_path: str) -> NcdFundingProxyPayload | None:
    duckdb_file = Path(duckdb_path)
    if not duckdb_file.exists():
        return None
    try:
        conn = duckdb.connect(str(duckdb_file), read_only=True)
    except duckdb.Error:
        return None

    try:
        latest = _load_landed_shibor_latest(conn)
    finally:
        conn.close()

    if not all(tenor in latest for tenor in REQUIRED_SHIBOR_TENORS):
        return None

    as_of_date = max(latest[tenor][0] for tenor in REQUIRED_SHIBOR_TENORS).date().isoformat()
    return NcdFundingProxyPayload(
        as_of_date=as_of_date,
        proxy_label="Tushare Shibor funding proxy",
        rows=[
            _build_proxy_row(
                row_key="shibor_fixing",
                label="Shibor fixing",
                values={tenor: latest[tenor][1] for tenor in REQUIRED_SHIBOR_TENORS},
                quote_count=None,
            ),
        ],
        warnings=[PROXY_WARNING, LANDED_PROXY_WARNING],
    )


def _load_landed_shibor_latest(conn: duckdb.DuckDBPyConnection) -> dict[str, tuple[datetime, float]]:
    latest: dict[str, tuple[datetime, float]] = {}
    for relation in ("choice_market_snapshot", "fact_choice_macro_daily"):
        if not _relation_exists(conn, relation):
            continue
        try:
            rows = conn.execute(
                f"""
                select
                  series_id,
                  series_name,
                  cast(trade_date as timestamp) as trade_date,
                  cast(value_numeric as double) as value_numeric
                from {relation}
                where value_numeric is not null
                  and (
                    lower(series_id) like '%shibor%'
                    or lower(series_name) like '%shibor%'
                  )
                """
            ).fetchall()
        except duckdb.Error:
            continue
        for series_id, series_name, trade_date, value_numeric in rows:
            tenor = _shibor_tenor_from_text(f"{series_id} {series_name}")
            if tenor is None:
                continue
            current = latest.get(tenor)
            point = (trade_date, float(value_numeric))
            if current is None or point[0] > current[0]:
                latest[tenor] = point
    return latest


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


def ncd_funding_proxy_envelope() -> dict[str, object]:
    payload = load_ncd_funding_proxy_payload()
    quality_flag: QualityFlag = "ok" if payload.rows else "warning"
    vendor_status: VendorStatus = "ok" if payload.rows else "vendor_unavailable"
    source_version = "sv_ncd_proxy_landed" if payload.rows else "sv_ncd_proxy_empty"
    vendor_version = "vv_landed_shibor" if payload.rows else "vv_none"
    return build_result_envelope(
        basis="analytical",
        trace_id="tr_ncd_funding_proxy",
        result_kind="market_data.ncd_proxy",
        cache_version=CACHE_VERSION,
        source_version=source_version,
        rule_version=RULE_VERSION,
        quality_flag=quality_flag,
        vendor_version=vendor_version,
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
