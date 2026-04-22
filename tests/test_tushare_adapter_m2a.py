"""M2a tests for TushareAdapter.fetch_macro_snapshot (mocked tushare pro API)."""

from __future__ import annotations

import builtins
import importlib
import sys
import types

import pandas as pd
import pytest
from backend.app.repositories.tushare_adapter import VendorAdapter

_TOKEN_ENV = "MOSS_TUSHARE_TOKEN"

_SERIES = "tushare.macro.cn_cpi.monthly"


def _install_fake_tushare(pro: _FakePro, monkeypatch) -> None:
    mod = types.ModuleType("tushare")

    def pro_api(_token: str) -> _FakePro:
        return pro

    mod.pro_api = pro_api
    monkeypatch.setitem(sys.modules, "tushare", mod)
    importlib.invalidate_caches()


def test_fetch_macro_snapshot_normalizes_cpi_dataframe(monkeypatch):
    monkeypatch.setenv(_TOKEN_ENV, "test-token")
    frame = pd.DataFrame(
        [
            {"month": "202401", "nt_yoy": 1.2, "nt_mom": 0.0},
            {"month": "202402", "nt_yoy": 0.5, "nt_mom": 0.0},
        ]
    )
    pro = _FakePro(frame, kind="cn_cpi")
    _install_fake_tushare(pro, monkeypatch)

    adapter = VendorAdapter()
    out = adapter.fetch_macro_snapshot(_SERIES)
    assert out["vendor_kind"] == "tushare_macro"
    assert out["series_id"] == _SERIES
    assert "fetched_at" in out
    rows = out["rows"]
    assert len(rows) == 2
    assert rows[0]["trade_date"] == "2024-01-01"
    assert rows[0]["value"] == pytest.approx(1.2)
    assert rows[1]["value"] == pytest.approx(0.5)


def test_fetch_macro_snapshot_no_token_raises(monkeypatch):
    monkeypatch.delenv(_TOKEN_ENV, raising=False)
    adapter = VendorAdapter()
    with pytest.raises(RuntimeError) as exc:
        adapter.fetch_macro_snapshot(_SERIES)
    assert _TOKEN_ENV in str(exc.value)


def test_fetch_macro_snapshot_tushare_import_failure_raises(monkeypatch):
    monkeypatch.setenv(_TOKEN_ENV, "test-token")
    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "tushare":
            raise ImportError("no tushare")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    adapter = VendorAdapter()
    with pytest.raises(RuntimeError) as exc:
        adapter.fetch_macro_snapshot(_SERIES)
    assert "tushare" in str(exc.value).lower()


def test_fetch_macro_snapshot_unknown_series_raises():
    adapter = VendorAdapter()
    with pytest.raises(ValueError):
        adapter.fetch_macro_snapshot("unknown.series.id")


def test_fetch_macro_snapshot_skeleton_unchanged():
    """M1 fixture path remains for offline tests and backward compatibility."""
    adapter = VendorAdapter()
    s = adapter.fetch_macro_snapshot_skeleton()
    assert s["vendor_kind"] == "tushare_macro"
    assert s["rows"]
    assert "Fixture" in s.get("note", "") or "fixture" in str(s).lower()


class _FakePro:
    def __init__(self, frame: pd.DataFrame, kind: str) -> None:
        self._frame = frame
        self._kind = kind

    def cn_cpi(self, **_kwargs: object) -> pd.DataFrame:
        if self._kind == "cn_cpi":
            return self._frame
        raise AssertionError

    def cn_gdp(self, **_kwargs: object) -> pd.DataFrame:
        if self._kind == "cn_gdp":
            return self._frame
        raise AssertionError
