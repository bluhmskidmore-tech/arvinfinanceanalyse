"""Contract tests for `backend.app.schemas.vendor`."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.schemas.vendor import (
    VendorAdapter,
    VendorFailure,
    VendorPreflightResult,
    VendorSnapshot,
    VendorSnapshotManifest,
)


def test_vendor_snapshot_defaults() -> None:
    s = VendorSnapshot(vendor_name="v", vendor_version="1")
    assert s.mode == "skeleton"
    assert s.snapshot_kind == "macro"
    assert s.read_target == "duckdb"
    assert s.record_count == 0


def test_vendor_preflight_result_defaults() -> None:
    p = VendorPreflightResult(vendor_name="v", ok=False)
    assert p.status == "missing_config"
    assert p.mode == "skeleton"
    assert p.supports_live_fetch is False


def test_vendor_failure_defaults() -> None:
    f = VendorFailure(vendor_name="v", stage="fetch", message="m")
    assert f.retryable is False
    assert f.mode == "skeleton"


def test_vendor_snapshot_manifest_defaults() -> None:
    m = VendorSnapshotManifest(
        vendor_name="v",
        vendor_version="1",
        snapshot_kind="macro",
        archive_mode="a",
        archived_path="/p",
    )
    assert m.capture_mode == "skeleton"
    assert m.read_target == "duckdb"


@pytest.mark.parametrize(
    "model,kwargs",
    [
        (VendorSnapshot, {"vendor_name": "v", "vendor_version": "1", "extra": 1}),
        (VendorPreflightResult, {"vendor_name": "v", "ok": True, "bad": 2}),
        (VendorFailure, {"vendor_name": "v", "stage": "s", "message": "m", "x": 3}),
        (
            VendorSnapshotManifest,
            {
                "vendor_name": "v",
                "vendor_version": "1",
                "snapshot_kind": "k",
                "archive_mode": "a",
                "archived_path": "p",
                "oops": 4,
            },
        ),
    ],
)
def test_vendor_models_forbid_extra_fields(model, kwargs: dict) -> None:
    with pytest.raises(ValidationError):
        model(**kwargs)  # type: ignore[arg-type]


class _ConcreteAdapter(VendorAdapter):
    vendor_name = "test_vendor"

    def preflight(self) -> VendorPreflightResult:
        return VendorPreflightResult(vendor_name=self.vendor_name, ok=True, status="config_present")

    def fetch_snapshot(self) -> VendorSnapshot:
        return VendorSnapshot(vendor_name=self.vendor_name, vendor_version="1.0.0")


def test_vendor_adapter_subclass_can_implement_abstract_methods() -> None:
    a = _ConcreteAdapter()
    pre = a.preflight()
    assert pre.ok is True
    snap = a.fetch_snapshot()
    assert snap.vendor_version == "1.0.0"


def test_vendor_adapter_without_overrides_cannot_instantiate() -> None:
    class Incomplete(VendorAdapter):
        vendor_name = "x"

    with pytest.raises(TypeError):
        Incomplete()
