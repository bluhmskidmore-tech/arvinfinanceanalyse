from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.app.services import pnl_bridge_service as bridge
from backend.app.services.runtime_cache import clear_runtime_cache


@pytest.fixture(autouse=True)
def _clear_bridge_cache():
    clear_runtime_cache("pnl_bridge.envelope")
    yield
    clear_runtime_cache("pnl_bridge.envelope")


def _install_bridge_fakes(monkeypatch, *, report_dates: list[str], calls: list[tuple[str, str]]) -> None:
    def pnl_repo(_path: str):
        return SimpleNamespace(
            list_formal_fi_report_dates=lambda: calls.append(("dates", "")) or list(report_dates),
            fetch_formal_fi_rows=lambda report_date: calls.append(("pnl", report_date)) or [],
        )

    def balance_repo(_path: str):
        return SimpleNamespace(
            fetch_pnl_bridge_zqtz_balance_rows=lambda *, report_date: calls.append(
                ("balance", report_date)
            )
            or [],
            resolve_prior_pnl_bridge_balance_report_date=lambda *, report_date: calls.append(
                ("prior", report_date)
            )
            or None,
            resolve_formal_fx_mid_rates_map=lambda **_: {},
        )

    monkeypatch.setattr(bridge, "PnlRepository", pnl_repo)
    monkeypatch.setattr(bridge, "BalanceAnalysisRepository", balance_repo)
    monkeypatch.setattr(bridge, "YieldCurveRepository", lambda _path: SimpleNamespace())
    monkeypatch.setattr(bridge, "_attach_native_exposure_fields", lambda **kwargs: kwargs["balance_rows"])
    monkeypatch.setattr(bridge, "_resolve_bridge_lineage", lambda **_: ({
        "source_version": "sv_test",
        "rule_version": "rv_test",
        "vendor_version": "vv_test",
    }, []))


def _seed_cache_inputs(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    duckdb_path.write_bytes(b"duckdb-fingerprint-v1")
    governance_dir = tmp_path / "governance"
    governance_dir.mkdir()
    (governance_dir / "cache_build_run.jsonl").write_text("", encoding="utf-8", newline="\n")
    (governance_dir / "cache_manifest.jsonl").write_text("", encoding="utf-8", newline="\n")
    return duckdb_path, governance_dir


def test_pnl_bridge_cache_reuses_envelope_for_same_inputs(tmp_path, monkeypatch):
    calls: list[tuple[str, str]] = []
    _install_bridge_fakes(monkeypatch, report_dates=["2026-08-31"], calls=calls)
    duckdb_path, governance_dir = _seed_cache_inputs(tmp_path)

    first = bridge.pnl_bridge_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2026-08-31",
    )
    second = bridge.pnl_bridge_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2026-08-31",
    )

    assert [call for call in calls if call[0] == "pnl"] == [("pnl", "2026-08-31")]
    assert first["result"] == second["result"]
    assert first["result_meta"]["trace_id"] != second["result_meta"]["trace_id"]


def test_pnl_bridge_cache_invalidates_when_duckdb_fingerprint_changes(tmp_path, monkeypatch):
    calls: list[tuple[str, str]] = []
    _install_bridge_fakes(monkeypatch, report_dates=["2026-08-31"], calls=calls)
    duckdb_path, governance_dir = _seed_cache_inputs(tmp_path)

    bridge.pnl_bridge_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2026-08-31",
    )
    bridge.pnl_bridge_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2026-08-31",
    )
    assert [call for call in calls if call[0] == "pnl"] == [("pnl", "2026-08-31")]

    duckdb_path.write_bytes(b"duckdb-fingerprint-v2")
    bridge.pnl_bridge_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2026-08-31",
    )

    assert [call for call in calls if call[0] == "pnl"] == [
        ("pnl", "2026-08-31"),
        ("pnl", "2026-08-31"),
    ]
