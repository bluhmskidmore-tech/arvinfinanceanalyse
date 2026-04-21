"""
Tushare vendor adapter skeleton.

Status: scaffold only. Implements `VendorAdapter` contract (`preflight`, `fetch_snapshot`)
so that the Tushare vendor is recognised by the system. No `fetch_macro_snapshot` yet —
it will be added together with the Choice EDB code -> Tushare API mapping table in a
follow-up task.

Auth: reads `MOSS_TUSHARE_TOKEN` from the environment (aligned with the akshare adapter's
env-driven pattern). Tushare itself is imported lazily, so the package is not required
unless live fetch is exercised.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime

from backend.app.repositories.external_data_catalog_repo import ExternalDataCatalogRepository
from backend.app.repositories.raw_zone_repo import RawZoneRepository
from backend.app.schemas.external_data import ExternalDataCatalogEntry
from backend.app.schemas.vendor import (
    VendorAdapter as VendorAdapterBase,
)
from backend.app.schemas.vendor import (
    VendorPreflightResult,
    VendorSnapshot,
)

TUSHARE_TOKEN_ENV = "MOSS_TUSHARE_TOKEN"


@dataclass
class VendorAdapter(VendorAdapterBase):
    vendor_name: str = "tushare"

    def preflight(self) -> VendorPreflightResult:
        token = os.getenv(TUSHARE_TOKEN_ENV, "").strip()
        if not token:
            return VendorPreflightResult(
                vendor_name=self.vendor_name,
                ok=False,
                status="missing_config",
                supports_live_fetch=False,
                detail=f"{TUSHARE_TOKEN_ENV} must be set before live fetch is enabled.",
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
