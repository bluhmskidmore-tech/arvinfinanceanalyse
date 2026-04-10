from dataclasses import dataclass
import os

from backend.app.schemas.vendor import (
    VendorAdapter as VendorAdapterBase,
    VendorPreflightResult,
    VendorSnapshot,
)


@dataclass
class VendorAdapter(VendorAdapterBase):
    vendor_name: str = "akshare"

    def preflight(self) -> VendorPreflightResult:
        base_url = os.getenv("MOSS_AKSHARE_BASE_URL")
        if not base_url:
            return VendorPreflightResult(
                vendor_name=self.vendor_name,
                ok=False,
                status="missing_config",
                detail="MOSS_AKSHARE_BASE_URL must be set before live fetch is enabled.",
            )

        return VendorPreflightResult(
            vendor_name=self.vendor_name,
            ok=True,
            status="config_present",
            detail="Configuration is present, but live vendor fetch remains disabled in Phase 1.",
        )

    def fetch_snapshot(self) -> VendorSnapshot:
        return VendorSnapshot(
            vendor_name=self.vendor_name,
            vendor_version="vv_none",
        )
