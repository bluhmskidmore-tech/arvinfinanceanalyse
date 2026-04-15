"""Contract tests for bond-dashboard HTTP API (envelope + empty DB behavior)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from tests.helpers import load_module

REPORT_DATE = "2026-03-31"

_BOND_DASHBOARD_CASES: list[tuple[str, dict[str, str | int]]] = [
    ("/api/bond-dashboard/dates", {}),
    ("/api/bond-dashboard/headline-kpis", {"report_date": REPORT_DATE}),
    ("/api/bond-dashboard/asset-structure", {"report_date": REPORT_DATE, "group_by": "bond_type"}),
    ("/api/bond-dashboard/yield-distribution", {"report_date": REPORT_DATE}),
    ("/api/bond-dashboard/portfolio-comparison", {"report_date": REPORT_DATE}),
    ("/api/bond-dashboard/spread-analysis", {"report_date": REPORT_DATE}),
    ("/api/bond-dashboard/maturity-structure", {"report_date": REPORT_DATE}),
    ("/api/bond-dashboard/industry-distribution", {"report_date": REPORT_DATE, "top_n": 10}),
    ("/api/bond-dashboard/risk-indicators", {"report_date": REPORT_DATE}),
]


def _assert_formal_envelope(payload: dict[str, Any]) -> None:
    assert "result_meta" in payload
    assert "result" in payload
    meta = payload["result_meta"]
    assert meta.get("basis") == "formal"
    assert meta.get("formal_use_allowed") is True
    for key in ("trace_id", "source_version", "rule_version", "result_kind"):
        assert key in meta, f"result_meta missing {key!r}"
        assert meta[key] not in (None, ""), f"result_meta.{key} must be non-empty"


def _check_all_on_empty_db() -> None:
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    for path, params in _BOND_DASHBOARD_CASES:
        response = client.get(path, params=params)
        assert response.status_code == 200, (
            f"{path} {params} -> {response.status_code}: {response.text}"
        )
        payload = response.json()
        _assert_formal_envelope(payload)
        result = payload["result"]
        if path.endswith("/dates"):
            assert result.get("report_dates") == []
        elif path.endswith("/headline-kpis"):
            assert result.get("report_date") == REPORT_DATE
            assert result.get("kpis") is not None
            cur = result["kpis"]
            assert cur["bond_count"] == 0
            assert cur["total_market_value"] == "0.00000000"
            assert result.get("prev_report_date") is None
            assert result.get("prev_kpis") is None
        elif path.endswith("/yield-distribution"):
            assert result.get("items") == []
            assert result.get("weighted_ytm") == "0.00000000"
        elif path.endswith("/industry-distribution"):
            assert result.get("items") == []
        elif path.endswith("/risk-indicators"):
            assert result.get("total_market_value") == "0.00000000"
        else:
            assert result.get("items") == []


def test_bond_dashboard_endpoints_envelope_empty_duckdb(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "empty.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    _check_all_on_empty_db()
    get_settings.cache_clear()


def test_bond_dashboard_service_uses_shared_lineage_and_meta_helpers() -> None:
    path = Path(__file__).resolve().parents[1] / "backend" / "app" / "services" / "bond_dashboard_service.py"
    src = path.read_text(encoding="utf-8")

    assert "resolve_formal_facts_lineage" in src
    assert "build_formal_result_meta_from_lineage" in src
    assert "build_formal_result_envelope_from_lineage" in src


def test_bond_dashboard_dates_falls_back_to_facts_lineage_when_manifest_missing(tmp_path, monkeypatch) -> None:
    from backend.app.core_finance.bond_analytics.engine import BondAnalyticsRow
    from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository

    duckdb_path = tmp_path / "dash-fallback.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()

    repo = BondAnalyticsRepository(str(duckdb_path))
    repo.replace_bond_analytics_rows(
        report_date=REPORT_DATE,
        rows=[
            BondAnalyticsRow(
                report_date=date.fromisoformat(REPORT_DATE),
                instrument_code="B1",
                instrument_name="B1",
                portfolio_name="P1",
                cost_center="C1",
                asset_class_raw="x",
                asset_class_std="rate",
                bond_type="国债",
                issuer_name="I",
                industry_name="银行",
                rating="AAA",
                accounting_class="AC",
                accounting_rule_id="r1",
                currency_code="CNY",
                face_value=Decimal("1000000"),
                market_value_native=Decimal("1000000"),
                market_value=Decimal("1000000"),
                amortized_cost=Decimal("1000000"),
                accrued_interest=Decimal("0"),
                coupon_rate=Decimal("0.025"),
                interest_mode="fixed",
                interest_payment_frequency="annual",
                interest_rate_style="fixed",
                ytm=Decimal("0.03"),
                maturity_date=date(2030, 1, 1),
                next_call_date=None,
                years_to_maturity=Decimal("2.5"),
                tenor_bucket="1-3年",
                macaulay_duration=Decimal("2"),
                modified_duration=Decimal("1.9"),
                convexity=Decimal("0.01"),
                dv01=Decimal("100"),
                is_credit=False,
                spread_dv01=Decimal("0"),
                source_version="sv_dash_row",
                rule_version="rv_dash_row",
                ingest_batch_id="ib",
                trace_id="tr",
            )
        ],
    )

    payload = load_module(
        "backend.app.services.bond_dashboard_service",
        "backend/app/services/bond_dashboard_service.py",
    ).get_bond_dashboard_dates()

    assert payload["result_meta"]["source_version"] == "sv_dash_row"
    assert payload["result_meta"]["rule_version"] == "rv_bond_analytics_formal_materialize_v1"
    assert payload["result_meta"]["cache_version"] == "cv_bond_analytics_formal__rv_bond_analytics_formal_materialize_v1"
    assert payload["result"]["report_dates"] == [REPORT_DATE]
    get_settings.cache_clear()


def test_bond_dashboard_group_by_validation_422(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "empty.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get(
        "/api/bond-dashboard/asset-structure",
        params={"report_date": REPORT_DATE, "group_by": "not_a_column"},
    )
    assert response.status_code == 422
    get_settings.cache_clear()


def test_bond_dashboard_headline_kpis_shape_with_seeded_facts(tmp_path, monkeypatch) -> None:
    from decimal import Decimal

    from backend.app.core_finance.bond_analytics.engine import BondAnalyticsRow
    from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository

    duckdb_path = tmp_path / "dash.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()

    repo = BondAnalyticsRepository(str(duckdb_path))
    d1 = "2026-03-30"
    d2 = "2026-03-31"
    for rd, mv, ytm in [
        (d1, Decimal("1000000"), Decimal("0.03")),
        (d2, Decimal("1100000"), Decimal("0.032")),
    ]:
        row = BondAnalyticsRow(
            report_date=date.fromisoformat(rd),
            instrument_code="B1",
            instrument_name="B1",
            portfolio_name="P1",
            cost_center="C1",
            asset_class_raw="x",
            asset_class_std="rate",
            bond_type="国债",
            issuer_name="I",
            industry_name="银行",
            rating="AAA",
            accounting_class="AC",
            accounting_rule_id="r1",
            currency_code="CNY",
            face_value=Decimal("1000000"),
            market_value_native=mv,
            market_value=mv,
            amortized_cost=mv,
            accrued_interest=Decimal("0"),
            coupon_rate=Decimal("0.025"),
            interest_mode="fixed",
            interest_payment_frequency="annual",
            interest_rate_style="fixed",
            ytm=ytm,
            maturity_date=date(2030, 1, 1),
            next_call_date=None,
            years_to_maturity=Decimal("2.5"),
            tenor_bucket="1-3年",
            macaulay_duration=Decimal("2"),
            modified_duration=Decimal("1.9"),
            convexity=Decimal("0.01"),
            dv01=Decimal("100"),
            is_credit=False,
            spread_dv01=Decimal("0"),
            source_version="sv",
            rule_version="rv",
            ingest_batch_id="ib",
            trace_id="tr",
        )
        repo.replace_bond_analytics_rows(report_date=rd, rows=[row])

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/bond-dashboard/headline-kpis", params={"report_date": d2})
    assert response.status_code == 200
    payload = response.json()
    _assert_formal_envelope(payload)
    res = payload["result"]
    assert res["prev_report_date"] == d1
    assert res["kpis"]["bond_count"] == 1
    assert res["prev_kpis"] is not None
    assert res["prev_kpis"]["bond_count"] == 1
    assert res["kpis"]["total_market_value"] != res["prev_kpis"]["total_market_value"]
    get_settings.cache_clear()
