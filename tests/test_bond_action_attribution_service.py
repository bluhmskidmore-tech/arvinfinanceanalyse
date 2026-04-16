from __future__ import annotations

from datetime import date

from tests.helpers import load_module


def test_bond_action_attribution_service_computes_result_when_positions_exist(monkeypatch):
    service_module = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )
    result_meta_module = load_module(
        "backend.app.schemas.result_meta",
        "backend/app/schemas/result_meta.py",
    )

    class FakeRepo:
        def fetch_bond_analytics_rows(self, *, report_date: str, asset_class: str = "all", accounting_class: str = "all"):
            if report_date == "2026-03-01":
                return [
                    {
                        "instrument_code": "240001.IB",
                        "portfolio_name": "rate-book",
                        "cost_center": "desk-a",
                        "market_value": "100",
                        "modified_duration": "2.0",
                        "accounting_class": "AC",
                        "source_version": "sv_bond",
                        "rule_version": "rv_bond",
                    }
                ]
            if report_date == "2026-03-31":
                return [
                    {
                        "instrument_code": "240001.IB",
                        "portfolio_name": "rate-book",
                        "cost_center": "desk-a",
                        "market_value": "120",
                        "modified_duration": "2.4",
                        "accounting_class": "AC",
                        "source_version": "sv_bond",
                        "rule_version": "rv_bond",
                    }
                ]
            return []

    class FakePnlRepo:
        def __init__(self, _path: str) -> None:
            pass

        def fetch_formal_fi_rows(self, report_date: str):
            assert report_date == "2026-03-31"
            return [
                {
                    "instrument_code": "240001.IB",
                    "portfolio_name": "rate-book",
                    "cost_center": "desk-a",
                    "total_pnl": "12.50",
                }
            ]

    def _boom_placeholder(_query):
        raise AssertionError("placeholder path must not be used when rows exist")

    monkeypatch.setattr(service_module, "_repo", lambda: FakeRepo())
    monkeypatch.setattr(service_module, "PnlRepository", FakePnlRepo)
    monkeypatch.setattr(service_module, "build_bond_action_attribution_placeholder_envelope", _boom_placeholder)
    monkeypatch.setattr(
        service_module,
        "_meta",
        lambda result_kind, report_date, rows: result_meta_module.ResultMeta(
            trace_id="tr_action_real",
            basis="formal",
            result_kind=result_kind,
            formal_use_allowed=True,
            source_version="sv_bond",
            vendor_version="vv_none",
            rule_version="rv_bond",
            cache_version="cv_bond",
            quality_flag="ok",
            scenario_flag=False,
        ),
    )

    payload = service_module.get_action_attribution(date(2026, 3, 31), "MoM")

    assert payload["result_meta"]["result_kind"] == "bond_analytics.action_attribution"
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result"]["status"] == "ready"
    assert payload["result"]["total_actions"] == 1
    assert payload["result"]["total_pnl_from_actions"] == "12.5"
    assert payload["result"]["missing_inputs"] == []
    assert payload["result"]["blocked_components"] == []
    assert payload["result"]["by_action_type"][0]["action_type"] == "TIMING_BUY"
    assert any("heuristic" in warning.lower() for warning in payload["result"]["warnings"])
