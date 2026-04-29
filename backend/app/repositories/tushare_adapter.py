"""
Tushare vendor adapter: `VendorAdapter` + `fetch_macro_snapshot(series_id)`.

`fetch_macro_snapshot` uses lazy `import tushare` and calls `pro_api` + macro helpers
(``cn_cpi``, ``cn_gdp``). Series routing comes from `tushare_catalog_seed`.

Auth: `MOSS_TUSHARE_TOKEN`. Missing token or import failure raises `RuntimeError` (no
silent fixture fallback in live fetch).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from backend.app.repositories.external_data_catalog_repo import ExternalDataCatalogRepository
from backend.app.repositories.raw_zone_repo import RawZoneRepository
from backend.app.repositories.tushare_catalog_seed import get_m2a_series_by_id
from backend.app.schemas.external_data import ExternalDataCatalogEntry
from backend.app.schemas.vendor import (
    VendorAdapter as VendorAdapterBase,
)
from backend.app.schemas.vendor import (
    VendorPreflightResult,
    VendorSnapshot,
)

TUSHARE_TOKEN_ENV = "MOSS_TUSHARE_TOKEN"
_GOVERNANCE_SETTINGS_MODULE = "backend.app.governance.settings"


def resolve_tushare_token_with_settings_fallback(settings: Any) -> str:
    """Env `MOSS_TUSHARE_TOKEN` first; then `settings.tushare_token` (config / .env).

    Shared by services that need optional Tushare calls with explicit no-token handling.
    """
    token = os.getenv(TUSHARE_TOKEN_ENV, "").strip()
    if token:
        return token
    return str(getattr(settings, "tushare_token", "") or "").strip()


def _load_settings_for_token_fallback() -> Any | None:
    try:
        from backend.app.governance.settings import get_settings
    except ModuleNotFoundError as exc:
        missing_name = str(getattr(exc, "name", "") or "")
        if missing_name in {
            "backend",
            "backend.app",
            "backend.app.governance",
            _GOVERNANCE_SETTINGS_MODULE,
        }:
            return None
        raise
    return get_settings()


def _require_tushare_token() -> str:
    token = resolve_tushare_token_with_settings_fallback(_load_settings_for_token_fallback())
    if not token:
        msg = f"{TUSHARE_TOKEN_ENV} is not set; export it or add to config/.env before calling Tushare macro fetch."
        raise RuntimeError(msg)
    return token


def _import_tushare_pro():
    try:
        import tushare as ts  # noqa: PLC0415
    except Exception as exc:
        msg = (
            "The `tushare` package is not installed or cannot be imported; "
            "install it for live Tushare vendor calls."
        )
        raise RuntimeError(msg) from exc
    return ts


def import_tushare_pro():
    """Lazy-import the tushare package. Raises :class:`RuntimeError` on import failure."""
    return _import_tushare_pro()


def _month_to_trade_date(month: str) -> str:
    m = str(month or "").strip()
    if len(m) == 6 and m.isdigit():
        return f"{m[:4]}-{m[4:6]}-01"
    return m


def _quarter_to_trade_date(quarter: str) -> str:
    q = str(quarter or "").strip().upper()
    if len(q) >= 6 and "Q" in q:
        year = int(q[:4])
        qn = q[5:6]
        ends = {"1": "-03-31", "2": "-06-30", "3": "-09-30", "4": "-12-31"}
        if qn in ends:
            return f"{year}{ends[qn]}"
    return q


def _rows_from_cn_cpi(df: Any) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for record in df.to_dict(orient="records"):
        month = record.get("month")
        value = record.get("nt_yoy")
        if value is None:
            continue
        rows.append(
            {
                "trade_date": _month_to_trade_date(str(month)),
                "value": float(value),
            }
        )
    return rows


def _rows_from_cn_gdp(df: Any) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for record in df.to_dict(orient="records"):
        quarter = record.get("quarter")
        value = record.get("gdp_yoy")
        if value is None or quarter is None:
            continue
        rows.append(
            {
                "trade_date": _quarter_to_trade_date(str(quarter)),
                "value": float(value),
            }
        )
    return rows


@dataclass
class VendorAdapter(VendorAdapterBase):
    vendor_name: str = "tushare"

    def preflight(self) -> VendorPreflightResult:
        token = resolve_tushare_token_with_settings_fallback(_load_settings_for_token_fallback())
        if not token:
            return VendorPreflightResult(
                vendor_name=self.vendor_name,
                ok=False,
                status="missing_config",
                supports_live_fetch=False,
                detail=f"{TUSHARE_TOKEN_ENV} must be set in process env or config/.env before live fetch is enabled.",
            )
        try:
            __import__("tushare")
        except Exception:
            return VendorPreflightResult(
                vendor_name=self.vendor_name,
                ok=False,
                status="missing_config",
                supports_live_fetch=False,
                detail="Install tushare locally before live fetch is enabled.",
            )
        return VendorPreflightResult(
            vendor_name=self.vendor_name,
            ok=True,
            status="config_present",
            supports_live_fetch=True,
            detail=f"{TUSHARE_TOKEN_ENV} is configured and tushare is importable.",
        )

    def fetch_snapshot(self) -> VendorSnapshot:
        return VendorSnapshot(
            vendor_name=self.vendor_name,
            vendor_version="vv_none",
        )

    def fetch_macro_snapshot_skeleton(self) -> dict[str, object]:
        """Fixture-shaped payload for M1; live Tushare macro fetch remains TODO."""
        return {
            "vendor_kind": "tushare_macro",
            "rows": [
                {"trade_date": "2026-01-01", "series_id": "GDP.Y", "value": 5.2},
            ],
            "note": "Fixture only; real Tushare API not implemented.",
        }

    def fetch_macro_snapshot(self, series_id: str) -> dict[str, object]:
        """Call Tushare pro API for a registered M2a series; returns JSON-serializable payload."""
        cfg = get_m2a_series_by_id(series_id)
        if cfg is None:
            msg = f"Unknown Tushare M2a series_id: {series_id!r}"
            raise ValueError(msg)

        token = _require_tushare_token()
        ts = _import_tushare_pro()
        pro = ts.pro_api(token)
        api = cfg["tushare_api"]
        if api == "cn_cpi":
            frame = pro.cn_cpi()
        elif api == "cn_gdp":
            frame = pro.cn_gdp()
        else:
            msg = f"Unsupported tushare_api {api!r} for {series_id}"
            raise ValueError(msg)

        if frame is None or len(frame) == 0:
            rows: list[dict[str, object]] = []
        elif api == "cn_cpi":
            rows = _rows_from_cn_cpi(frame)
        else:
            rows = _rows_from_cn_gdp(frame)

        return {
            "vendor_kind": "tushare_macro",
            "series_id": series_id,
            "fetched_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "rows": rows,
        }

    def register_to_catalog(
        self,
        catalog_repo: ExternalDataCatalogRepository,
        raw_zone_repo: RawZoneRepository,
    ) -> ExternalDataCatalogEntry:
        """Register a single scaffold series; does not call Tushare network APIs."""
        _ = raw_zone_repo  # reserved for raw-zone wiring in M2
        entry = ExternalDataCatalogEntry(
            series_id="tushare.macro.skeleton.gdp_y",
            series_name="Tushare macro skeleton (GDP-Y)",
            vendor_name=self.vendor_name,
            source_family="tushare_macro",
            domain="macro",
            frequency="daily",
            unit="pct",
            refresh_tier="on_demand",
            fetch_mode="skeleton",
            raw_zone_path="data/raw/tushare/{ingest_batch_id}/macro_snapshot.json",
            standardized_table="std_external_macro_daily",
            view_name="vw_external_macro_daily",
            access_path="select * from fact_choice_macro_daily where 1=0 /* M1 placeholder */",
            catalog_version="m1.scaffold.v1",
            created_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
        )
        return catalog_repo.register(entry)
