from pydantic import BaseModel


class VendorSnapshot(BaseModel):
    vendor_name: str
    vendor_version: str
    mode: str = "skeleton"
