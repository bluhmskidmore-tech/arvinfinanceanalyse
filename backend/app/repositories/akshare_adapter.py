from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
from io import StringIO
import json
import os
from decimal import Decimal

import pandas as pd
import requests

from backend.app.repositories.choice_client import ChoiceClient
from backend.app.schemas.vendor import (
    VendorAdapter as VendorAdapterBase,
    VendorPreflightResult,
    VendorSnapshot,
)
from backend.app.schemas.yield_curve import YieldCurvePoint, YieldCurveSnapshot


AKSHARE_CURVE_NAME_BY_TYPE = {
    "treasury": "中债国债收益率曲线",
    "cdb": "中债政策性金融债收益率曲线(国开行)",
    "aaa_credit": "中债企业债收益率曲线(AAA)",
}

AKSHARE_TENOR_COLUMNS = {
    "3月": "3M",
    "6月": "6M",
    "9月": "9M",
    "1年": "1Y",
    "2年": "2Y",
    "3年": "3Y",
    "5年": "5Y",
    "7年": "7Y",
    "10年": "10Y",
    "20年": "20Y",
    "30年": "30Y",
}

CHOICE_CURVE_CODES = {
    "treasury": {
        "3M": "EMM00166455",
        "6M": "EMM00166456",
        "1Y": "EMM00166458",
        "2Y": "EMM00588704",
        "3Y": "EMM00166460",
        "5Y": "EMM00166462",
        "7Y": "EMM00166464",
        "10Y": "EMM00166466",
        "20Y": "EMM00166468",
        "30Y": "EMM00166469",
    },
    "cdb": {
        "6M": "EMM00166492",
        "1Y": "EMM00166494",
        "2Y": "EMM00166495",
        "3Y": "EMM00166496",
        "5Y": "EMM00166498",
        "10Y": "EMM00166502",
        "20Y": "EMM00166504",
    },
}

CHINABOND_GKH_URL = "https://yield.chinabond.com.cn/gkh/yield"
CHINABOND_GKH_CURVE_NAME = "中债国开债收益率曲线（到期）"
CHINABOND_GKH_TENOR_MAP = {
    "1": "1Y",
    "3": "3Y",
    "5": "5Y",
    "7": "7Y",
    "10": "10Y",
}

MIN_OBSERVED_TENORS_BY_TYPE = {
    "treasury": frozenset({"6M", "1Y", "3Y", "5Y", "10Y", "30Y"}),
    "cdb": frozenset({"1Y", "3Y", "5Y", "10Y"}),
    "aaa_credit": frozenset({"1Y", "3Y", "5Y", "10Y"}),
}

MIN_REQUIRED_TENORS_BY_TYPE = {
    "treasury": frozenset({"6M", "1Y", "3Y", "5Y", "10Y", "30Y"}),
    "cdb": frozenset({"6M", "1Y", "2Y", "3Y", "5Y", "10Y", "20Y", "30Y"}),
    "aaa_credit": frozenset({"1Y", "3Y", "5Y", "10Y"}),
}


@dataclass
class VendorAdapter(VendorAdapterBase):
    vendor_name: str = "akshare"

    def preflight(self) -> VendorPreflightResult:
        base_url = os.getenv("MOSS_AKSHARE_BASE_URL", "").strip()
        if base_url:
            return VendorPreflightResult(
                vendor_name=self.vendor_name,
                ok=True,
                status="config_present",
                supports_live_fetch=True,
                detail="MOSS_AKSHARE_BASE_URL is configured for HTTP proxy fetch.",
            )
        try:
            __import__("akshare")
        except Exception:
            return VendorPreflightResult(
                vendor_name=self.vendor_name,
                ok=False,
                status="missing_config",
                supports_live_fetch=False,
                detail="Install akshare locally or set MOSS_AKSHARE_BASE_URL before live fetch is enabled.",
            )
        return VendorPreflightResult(
            vendor_name=self.vendor_name,
            ok=True,
            status="config_present",
            supports_live_fetch=True,
            detail="Local akshare import is available for direct fetch.",
        )

    def fetch_snapshot(self) -> VendorSnapshot:
        return VendorSnapshot(
            vendor_name=self.vendor_name,
            vendor_version="vv_none",
        )

    def fetch_yield_curve(
        self,
        curve_type: str,
        trade_date: str,
    ) -> YieldCurveSnapshot:
        normalized_curve_type = _normalize_curve_type(curve_type)
        normalized_trade_date = date.fromisoformat(str(trade_date)).isoformat()

        primary_error: Exception | None = None
        try:
            primary = self._fetch_akshare_curve(
                curve_type=normalized_curve_type,
                trade_date=normalized_trade_date,
            )
            if primary is not None:
                return primary
        except Exception as exc:
            primary_error = exc

        fallback_error: Exception | None = None
        try:
            fallback = self._fetch_choice_curve(
                curve_type=normalized_curve_type,
                trade_date=normalized_trade_date,
            )
            if fallback is not None:
                return fallback
        except Exception as exc:
            fallback_error = exc

        tertiary_error: Exception | None = None
        if normalized_curve_type == "cdb":
            try:
                tertiary = self._fetch_chinabond_gkh_curve(normalized_trade_date)
                if tertiary is not None:
                    return tertiary
            except Exception as exc:
                tertiary_error = exc

        errors = []
        if primary_error is not None:
            errors.append(f"AkShare failed: {primary_error}")
        else:
            errors.append("AkShare returned no matching curve snapshot.")
        if fallback_error is not None:
            errors.append(f"Choice failed: {fallback_error}")
        else:
            errors.append("Choice returned no matching curve snapshot.")
        if normalized_curve_type == "cdb":
            if tertiary_error is not None:
                errors.append(f"ChinaBond gkh failed: {tertiary_error}")
            else:
                errors.append("ChinaBond gkh returned no matching curve snapshot.")
        raise RuntimeError(" ".join(errors))

    def _fetch_akshare_curve(self, *, curve_type: str, trade_date: str) -> YieldCurveSnapshot | None:
        records = (
            self._fetch_akshare_records_via_http(trade_date)
            if os.getenv("MOSS_AKSHARE_BASE_URL", "").strip()
            else self._fetch_akshare_records_locally(trade_date)
        )
        curve_name = AKSHARE_CURVE_NAME_BY_TYPE[curve_type]
        matches = [
            record
            for record in records
            if str(record.get("曲线名称") or "").strip() == curve_name
            and _normalize_record_trade_date(record.get("日期")) == trade_date
        ]
        if not matches:
            return None
        points = _prepare_curve_points(
            curve_type=curve_type,
            points=_build_points_from_columns(matches[-1], AKSHARE_TENOR_COLUMNS),
        )
        return _snapshot_from_points(
            curve_type=curve_type,
            trade_date=trade_date,
            vendor_name="akshare",
            points=points,
        )

    def _fetch_chinabond_gkh_curve(self, trade_date: str) -> YieldCurveSnapshot | None:
        response = requests.post(
            CHINABOND_GKH_URL,
            data={"searchDate": trade_date},
            timeout=20,
        )
        response.raise_for_status()
        frames = pd.read_html(StringIO(response.text))
        target_frame = None
        for frame in frames:
            columns = {str(column) for column in frame.columns}
            if "曲线名称" in columns and "关键期限(年)" in columns and "查询日收益率(%)" in columns:
                target_frame = frame
                break
        if target_frame is None:
            return None
        points: list[YieldCurvePoint] = []
        for _, row in target_frame.iterrows():
            curve_name = str(row.get("曲线名称") or "").strip()
            if curve_name != CHINABOND_GKH_CURVE_NAME:
                continue
            tenor_key = str(row.get("关键期限(年)") or "").strip()
            tenor = CHINABOND_GKH_TENOR_MAP.get(tenor_key)
            if tenor is None:
                continue
            value = row.get("查询日收益率(%)")
            if value in (None, ""):
                continue
            points.append(
                YieldCurvePoint(
                    tenor=tenor,
                    rate_pct=Decimal(str(value)),
                )
            )
        if not points:
            return None
        points = _prepare_curve_points(curve_type="cdb", points=points)
        return _snapshot_from_points(
            curve_type="cdb",
            trade_date=trade_date,
            vendor_name="chinabond_gkh",
            points=points,
        )

    def _fetch_akshare_records_via_http(self, trade_date: str) -> list[dict[str, object]]:
        base_url = os.getenv("MOSS_AKSHARE_BASE_URL", "").strip().rstrip("/")
        if not base_url:
            raise RuntimeError("MOSS_AKSHARE_BASE_URL is required for HTTP proxy mode.")
        response = requests.get(
            f"{base_url}/api/public/bond_china_yield",
            params={
                "start_date": trade_date.replace("-", ""),
                "end_date": trade_date.replace("-", ""),
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, list):
            return [dict(item) for item in payload]
        if isinstance(payload, dict) and isinstance(payload.get("data"), list):
            return [dict(item) for item in payload["data"]]
        raise RuntimeError("Unexpected AkShare proxy payload shape.")

    def _fetch_akshare_records_locally(self, trade_date: str) -> list[dict[str, object]]:
        import akshare as ak  # type: ignore

        frame = ak.bond_china_yield(
            start_date=trade_date.replace("-", ""),
            end_date=trade_date.replace("-", ""),
        )
        return [dict(item) for item in frame.to_dict(orient="records")]

    def _fetch_choice_curve(self, *, curve_type: str, trade_date: str) -> YieldCurveSnapshot | None:
        code_map = CHOICE_CURVE_CODES.get(curve_type)
        if not code_map:
            return None
        client = ChoiceClient()
        raw_result = client.edb(
            codes=list(code_map.values()),
            options=f"IsLatest=0,StartDate={trade_date},EndDate={trade_date},Ispandas=1",
        )
        code_to_tenor = {vendor_code: tenor for tenor, vendor_code in code_map.items()}
        points = []
        for row in _choice_rows_from_result(raw_result):
            vendor_code = str(row.get("vendor_code") or "")
            if vendor_code not in code_to_tenor:
                continue
            if _normalize_record_trade_date(row.get("trade_date")) != trade_date:
                continue
            value = row.get("value")
            if value in (None, ""):
                continue
            points.append(
                YieldCurvePoint(
                    tenor=code_to_tenor[vendor_code],
                    rate_pct=Decimal(str(value)),
                )
            )
        points = _prepare_curve_points(curve_type=curve_type, points=points)
        return _snapshot_from_points(
            curve_type=curve_type,
            trade_date=trade_date,
            vendor_name="choice",
            points=points,
        )


def _normalize_curve_type(curve_type: str) -> str:
    normalized = str(curve_type or "").strip().lower()
    if normalized not in {"treasury", "cdb", "aaa_credit"}:
        raise ValueError(f"Unsupported curve_type={curve_type!r}")
    return normalized


def _build_points_from_columns(
    record: dict[str, object],
    column_map: dict[str, str],
) -> list[YieldCurvePoint]:
    points: list[YieldCurvePoint] = []
    for raw_column, tenor in column_map.items():
        value = record.get(raw_column)
        if value in (None, "", "nan"):
            continue
        try:
            points.append(YieldCurvePoint(tenor=tenor, rate_pct=Decimal(str(value))))
        except Exception:
            continue
    return points


def _validate_points(*, curve_type: str, points: list[YieldCurvePoint]) -> list[YieldCurvePoint]:
    observed = {point.tenor for point in points}
    required_observed = MIN_OBSERVED_TENORS_BY_TYPE[curve_type]
    missing_observed = sorted(required_observed - observed)
    if missing_observed:
        raise ValueError(
            f"{curve_type} curve missing minimum observed tenors: {', '.join(missing_observed)}"
        )
    return points


def _validate_standardized_points(*, curve_type: str, points: list[YieldCurvePoint]) -> list[YieldCurvePoint]:
    if not points:
        raise ValueError(f"{curve_type} curve returned no usable points.")
    available_tenors = {point.tenor for point in points}
    required = MIN_REQUIRED_TENORS_BY_TYPE[curve_type]
    missing = sorted(required - available_tenors)
    if missing:
        raise ValueError(
            f"{curve_type} curve missing required tenors: {', '.join(missing)}"
        )
    return points


def _enrich_curve_points(*, curve_type: str, points: list[YieldCurvePoint]) -> list[YieldCurvePoint]:
    if curve_type != "cdb":
        return points
    tenor_map = {point.tenor: point for point in points}
    enriched = dict(tenor_map)
    point_1y = tenor_map.get("1Y")
    point_3y = tenor_map.get("3Y")
    point_7y = tenor_map.get("7Y")
    point_10y = tenor_map.get("10Y")
    point_20y = tenor_map.get("20Y")
    if "6M" not in enriched and point_1y is not None:
        enriched["6M"] = YieldCurvePoint(tenor="6M", rate_pct=point_1y.rate_pct)
    if "2Y" not in enriched and point_1y is not None and point_3y is not None:
        enriched["2Y"] = YieldCurvePoint(
            tenor="2Y",
            rate_pct=point_1y.rate_pct + (point_3y.rate_pct - point_1y.rate_pct) / Decimal("2"),
        )
    if "20Y" not in enriched and point_7y is not None and point_10y is not None:
        slope_per_year = (point_10y.rate_pct - point_7y.rate_pct) / Decimal("3")
        enriched["20Y"] = YieldCurvePoint(
            tenor="20Y",
            rate_pct=point_10y.rate_pct + slope_per_year * Decimal("10"),
        )
        point_20y = enriched["20Y"]
    if "30Y" not in enriched and point_20y is not None and point_10y is not None:
        enriched["30Y"] = YieldCurvePoint(
            tenor="30Y",
            rate_pct=point_20y.rate_pct + (point_20y.rate_pct - point_10y.rate_pct),
        )
    return sorted(enriched.values(), key=lambda point: point.tenor)


def _prepare_curve_points(*, curve_type: str, points: list[YieldCurvePoint]) -> list[YieldCurvePoint]:
    observed = _validate_points(curve_type=curve_type, points=points)
    enriched = _enrich_curve_points(curve_type=curve_type, points=observed)
    return _validate_standardized_points(curve_type=curve_type, points=enriched)


def _choice_rows_from_result(raw_result: object) -> list[dict[str, object]]:
    if raw_result.__class__.__name__ == "DataFrame":
        rows: list[dict[str, object]] = []
        for vendor_code in getattr(raw_result, "index", []):
            frame = raw_result.loc[[vendor_code]]
            for _idx, item in frame.iterrows():
                rows.append(
                    {
                        "vendor_code": str(vendor_code),
                        "trade_date": item.get("DATES"),
                        "value": item.get("RESULT"),
                    }
                )
        return rows

    codes = [str(code) for code in getattr(raw_result, "Codes", [])]
    dates = [_normalize_record_trade_date(value) for value in getattr(raw_result, "Dates", [])]
    data = getattr(raw_result, "Data", {})
    rows = []
    for vendor_code in codes:
        values = data.get(vendor_code, [])
        indicator_values = values[0] if values else []
        if not indicator_values:
            continue
        rows.append(
            {
                "vendor_code": vendor_code,
                "trade_date": dates[-1] if dates else "",
                "value": indicator_values[-1],
            }
        )
    return rows


def _snapshot_from_points(
    *,
    curve_type: str,
    trade_date: str,
    vendor_name: str,
    points: list[YieldCurvePoint],
) -> YieldCurveSnapshot:
    digest = hashlib.sha256(
        json.dumps(
            {
                "curve_type": curve_type,
                "trade_date": trade_date,
                "vendor_name": vendor_name,
                "points": [
                    {"tenor": point.tenor, "rate_pct": format(point.rate_pct, "f")}
                    for point in points
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:12]
    return YieldCurveSnapshot(
        curve_type=curve_type,
        trade_date=trade_date,
        points=sorted(points, key=lambda point: point.tenor),
        vendor_name=vendor_name,
        vendor_version=f"vv_{vendor_name}_{curve_type}_{trade_date.replace('-', '')}_{digest}",
        source_version=f"sv_yield_curve_{curve_type}_{digest}",
    )


def _normalize_record_trade_date(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip().replace("/", "-")
    if not text:
        return ""
    if " " in text:
        text = text.split(" ", 1)[0]
    return date.fromisoformat(text).isoformat()
