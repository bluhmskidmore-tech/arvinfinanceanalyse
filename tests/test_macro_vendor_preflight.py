import pytest

from tests.helpers import load_module


@pytest.mark.parametrize(
    ("module_name", "relative_path", "expected_vendor", "env_vars"),
    [
        (
            "backend.app.repositories.choice_adapter",
            "backend/app/repositories/choice_adapter.py",
            "choice",
            ("CHOICE_EMQUANT_PARENT", "CHOICE_MACRO_CHOICE_START_OPTIONS"),
        ),
        (
            "backend.app.repositories.akshare_adapter",
            "backend/app/repositories/akshare_adapter.py",
            "akshare",
            ("MOSS_AKSHARE_BASE_URL",),
        ),
    ],
)
def test_vendor_preflight_reports_typed_missing_config_state(
    monkeypatch,
    module_name: str,
    relative_path: str,
    expected_vendor: str,
    env_vars: tuple[str, ...],
):
    schema_module = load_module("backend.app.schemas.vendor", "backend/app/schemas/vendor.py")
    module = load_module(module_name, relative_path)

    preflight_model = getattr(schema_module, "VendorPreflightResult", None)
    if preflight_model is None:
        pytest.fail("backend.app.schemas.vendor must define VendorPreflightResult")

    for env_var in env_vars:
        monkeypatch.delenv(env_var, raising=False)

    instance = module.VendorAdapter()
    result = instance.preflight()

    assert isinstance(result, preflight_model)
    assert result.vendor_name == expected_vendor
    assert result.ok is False
    assert result.status == "missing_config"
    assert result.supports_live_fetch is False


def test_choice_preflight_uses_settings_emquant_parent_without_env(monkeypatch):
    adapter_module = load_module(
        "backend.app.repositories.choice_adapter",
        "backend/app/repositories/choice_adapter.py",
    )
    runtime_module = load_module(
        "backend.app.config.choice_runtime",
        "backend/app/config/choice_runtime.py",
    )

    called: dict[str, object] = {}
    monkeypatch.delenv("CHOICE_EMQUANT_PARENT", raising=False)
    monkeypatch.delenv("CHOICE_MACRO_CHOICE_START_OPTIONS", raising=False)
    monkeypatch.setattr(
        adapter_module,
        "load_settings",
        lambda: runtime_module.AppSettings(
            choice_emquant_parent="F:/EMQuantAPI_Python/python3",
            choice_start_options="UserName=demo,PassWord=demo,ForceLogin=1",
            choice_request_options="",
            log_level="INFO",
            log_path="",
        ),
    )
    monkeypatch.setattr(
        adapter_module,
        "configure_emquant_parent",
        lambda path: called.setdefault("emquant_parent", path),
    )
    monkeypatch.setattr(adapter_module, "_get_em_c", lambda: object())

    result = adapter_module.VendorAdapter().preflight()

    assert result.ok is True
    assert result.status == "config_present"
    assert called["emquant_parent"] == "F:/EMQuantAPI_Python/python3"
