from dataclasses import dataclass


@dataclass
class VendorAdapter:
    vendor_name: str = "akshare"

    def fetch_snapshot(self) -> dict[str, str]:
        return {"vendor": self.vendor_name, "mode": "skeleton"}
