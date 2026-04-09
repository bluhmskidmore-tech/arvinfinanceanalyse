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
