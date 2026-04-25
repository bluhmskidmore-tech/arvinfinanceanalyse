from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from backend.app.governance.settings import get_settings
from backend.app.repositories.tushare_adapter import import_tushare_pro, resolve_tushare_token_with_settings_fallback
from backend.app.schemas.ncd_proxy import NcdFundingProxyPayload, NcdFundingProxyRow
from backend.app.services.formal_result_runtime import (
    QualityFlag,
    VendorStatus,
    build_result_envelope,
)

RULE_VERSION = "rv_ncd_proxy_v1"
CACHE_VERSION = "cv_ncd_proxy_v1"
PROXY_WARNING = "Proxy only; not actual NCD issuance matrix."


def _iso_date(date_text: str | None) -> str | None:
    raw = str(date_text or "").strip()
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"
    return raw or None


def _latest_shibor_row(frame: Any) -> dict[str, Any] | None:
    if frame is None or len(frame) == 0:
        return None
    records = frame.to_dict(orient="records")
    rows = [row for row in records if isinstance(row, dict) and row.get("date")]
    if not rows:
        return None
    rows.sort(key=lambda row: str(row.get("date", "")), reverse=True)
    return rows[0]


def _median_quote_row(frame: Any) -> tuple[dict[str, float | None], int]:
    if frame is None or len(frame) == 0:
        return (
            {"1M": None, "3M": None, "6M": None, "9M": None, "1Y": None},
            0,
        )

    columns = {
        "1M": ("1m_b", "1m_a"),
        "3M": ("3m_b", "3m_a"),
        "6M": ("6m_b", "6m_a"),
        "9M": ("9m_b", "9m_a"),
        "1Y": ("1y_b", "1y_a"),
    }
    result: dict[str, float | None] = {}
    for tenor, (bid_col, ask_col) in columns.items():
        sample = frame[[bid_col, ask_col]].dropna(how="all")
        if len(sample) == 0:
            result[tenor] = None
            continue
        midpoint = (sample[bid_col].astype(float) + sample[ask_col].astype(float)) / 2.0
        result[tenor] = float(midpoint.median()) if len(midpoint) else None
    return result, int(len(frame))


def load_ncd_funding_proxy_payload() -> NcdFundingProxyPayload:
    settings = get_settings()
    token = resolve_tushare_token_with_settings_fallback(settings)
    if not token:
        return NcdFundingProxyPayload(
            proxy_label="Tushare Shibor funding proxy",
            rows=[],
            warnings=[f"{PROXY_WARNING} Missing Tushare token."],
        )

    try:
        ts = import_tushare_pro()
        pro = ts.pro_api(token)
        end_date = datetime.now(UTC).strftime("%Y%m%d")
        start_date = (datetime.now(UTC) - timedelta(days=10)).strftime("%Y%m%d")
        shibor_df = pro.shibor(start_date=start_date, end_date=end_date)
        latest_row = _latest_shibor_row(shibor_df)
        if latest_row is None:
            return NcdFundingProxyPayload(
                proxy_label="Tushare Shibor funding proxy",
                rows=[],
                warnings=[f"{PROXY_WARNING} Shibor returned no rows."],
            )
        as_of_date = _iso_date(str(latest_row.get("date")))
        quote_df = pro.shibor_quote(start_date=str(latest_row.get("date")), end_date=str(latest_row.get("date")))
        median_row, quote_count = _median_quote_row(quote_df)
        rows = [
            _build_proxy_row(
                row_key="shibor_fixing",
                label="Shibor fixing",
                values={
                    "1M": _coerce_float(latest_row.get("1m")),
                    "3M": _coerce_float(latest_row.get("3m")),
                    "6M": _coerce_float(latest_row.get("6m")),
                    "9M": _coerce_float(latest_row.get("9m")),
                    "1Y": _coerce_float(latest_row.get("1y")),
                },
                quote_count=None,
            ),
        ]
        if quote_count > 0:
            rows.append(
                _build_proxy_row(
                    row_key="quote_median",
                    label="Quote median",
                    values=median_row,
                    quote_count=quote_count,
                ),
            )
        warnings = [PROXY_WARNING]
        if quote_count == 0:
            warnings.append("Shibor quote row unavailable; displaying fixing only.")
        return NcdFundingProxyPayload(
            as_of_date=as_of_date,
            proxy_label="Tushare Shibor funding proxy",
            rows=rows,
            warnings=warnings,
        )
    except Exception as exc:
        return NcdFundingProxyPayload(
            proxy_label="Tushare Shibor funding proxy",
            rows=[],
            warnings=[f"{PROXY_WARNING} {exc}"],
        )


def ncd_funding_proxy_envelope() -> dict[str, object]:
    payload = load_ncd_funding_proxy_payload()
    quality_flag: QualityFlag = "ok" if payload.rows else "warning"
    vendor_status: VendorStatus = "ok" if payload.rows else "vendor_unavailable"
    return build_result_envelope(
        basis="analytical",
        trace_id="tr_ncd_funding_proxy",
        result_kind="market_data.ncd_proxy",
        cache_version=CACHE_VERSION,
        source_version="sv_ncd_proxy_tushare",
        rule_version=RULE_VERSION,
        quality_flag=quality_flag,
        vendor_version="vv_tushare_shibor",
        vendor_status=vendor_status,
        fallback_mode="none",
        result_payload=payload.model_dump(mode="json", by_alias=True),
    )


def _coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
