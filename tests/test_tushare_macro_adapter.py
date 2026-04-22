"""Tests for the Tushare vendor adapter scaffold.

Mirrors the structure of `tests.test_macro_vendor_preflight` for the akshare adapter:
- vendor_name is declared
- fetch_snapshot returns a typed VendorSnapshot with the right vendor_name
- preflight reports the three documented branches
  (no token / token but no tushare package / token + tushare importable)
"""

from __future__ import annotations

import builtins

from tests.helpers import load_module


_ADAPTER_MODULE_NAME = "backend.app.repositories.tushare_adapter"
_ADAPTER_RELATIVE_PATH = "backend/app/repositories/tushare_adapter.py"
_SCHEMA_MODULE_NAME = "backend.app.schemas.vendor"
_SCHEMA_RELATIVE_PATH = "backend/app/schemas/vendor.py"
_TOKEN_ENV = "MOSS_TUSHARE_TOKEN"


def _load_adapter_module():
    return load_module(_ADAPTER_MODULE_NAME, _ADAPTER_RELATIVE_PATH)


def _load_schema_module():
    return load_module(_SCHEMA_MODULE_NAME, _SCHEMA_RELATIVE_PATH)


def test_tushare_vendor_adapter_declares_vendor_name():
    module = _load_adapter_module()
    instance = module.VendorAdapter()
    assert instance.vendor_name == "tushare"


def test_tushare_fetch_snapshot_returns_typed_snapshot():
    schema = _load_schema_module()
    module = _load_adapter_module()

    snapshot = module.VendorAdapter().fetch_snapshot()
    assert isinstance(snapshot, schema.VendorSnapshot)
    assert snapshot.vendor_name == "tushare"
    assert snapshot.vendor_version == "vv_none"
    assert snapshot.mode == "skeleton"


def test_tushare_preflight_reports_missing_config_when_token_absent(monkeypatch):
    schema = _load_schema_module()
    module = _load_adapter_module()

    monkeypatch.delenv(_TOKEN_ENV, raising=False)

    result = module.VendorAdapter().preflight()

    assert isinstance(result, schema.VendorPreflightResult)
    assert result.vendor_name == "tushare"
    assert result.ok is False
    assert result.status == "missing_config"
    assert result.supports_live_fetch is False
    assert _TOKEN_ENV in (result.detail or "")


def test_tushare_preflight_reports_missing_config_when_local_import_unavailable(monkeypatch):
    module = _load_adapter_module()

    monkeypatch.setenv(_TOKEN_ENV, "test-token")
    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "tushare":
            raise ImportError("tushare missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    result = module.VendorAdapter().preflight()

    assert result.ok is False
    assert result.status == "missing_config"
    assert result.supports_live_fetch is False


def test_tushare_preflight_ok_when_token_and_import_available(monkeypatch):
    module = _load_adapter_module()

    monkeypatch.setenv(_TOKEN_ENV, "test-token")
    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "tushare":
            return object()
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    result = module.VendorAdapter().preflight()

    assert result.ok is True
    assert result.status == "config_present"
    assert result.supports_live_fetch is True
