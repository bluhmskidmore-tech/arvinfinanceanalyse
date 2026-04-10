import pytest

from tests.helpers import load_module


@pytest.mark.parametrize(
    ("module_name", "relative_path", "expected_vendor"),
    [
        ("backend.app.repositories.choice_adapter", "backend/app/repositories/choice_adapter.py", "choice"),
        ("backend.app.repositories.akshare_adapter", "backend/app/repositories/akshare_adapter.py", "akshare"),
    ],
)
def test_vendor_adapter_exists_and_declares_vendor_name(module_name: str, relative_path: str, expected_vendor: str):
    module = load_module(module_name, relative_path)
    adapter = getattr(module, "VendorAdapter", None)
    if adapter is None:
        pytest.fail(f"{relative_path} must define VendorAdapter")

    instance = adapter()
    assert instance.vendor_name == expected_vendor


@pytest.mark.parametrize(
    ("module_name", "relative_path"),
    [
        ("backend.app.repositories.choice_adapter", "backend/app/repositories/choice_adapter.py"),
        ("backend.app.repositories.akshare_adapter", "backend/app/repositories/akshare_adapter.py"),
    ],
)
def test_vendor_adapter_returns_typed_snapshot_and_preflight(module_name: str, relative_path: str):
    schema_module = load_module("backend.app.schemas.vendor", "backend/app/schemas/vendor.py")
    module = load_module(module_name, relative_path)
    adapter = getattr(module, "VendorAdapter", None)
    if adapter is None:
        pytest.fail(f"{relative_path} must define VendorAdapter")

    contract = getattr(schema_module, "VendorAdapter", None)
    if contract is None:
        pytest.fail("backend.app.schemas.vendor must define VendorAdapter contract")

    snapshot_model = getattr(schema_module, "VendorSnapshot", None)
    preflight_model = getattr(schema_module, "VendorPreflightResult", None)
    if snapshot_model is None or preflight_model is None:
        pytest.fail("backend.app.schemas.vendor must define typed vendor models")

    instance = adapter()
    snapshot = instance.fetch_snapshot()
    preflight = instance.preflight()

    assert isinstance(snapshot, snapshot_model)
    assert snapshot.vendor_name == instance.vendor_name
    assert isinstance(preflight, preflight_model)
    assert preflight.vendor_name == instance.vendor_name
    assert preflight.mode == "skeleton"
