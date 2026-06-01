from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import duckdb
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.news_warehouse_repo import ensure_news_warehouse_schema, upsert_news_event
from tests.helpers import load_module

REPORT_DATE = "2026-03-31"
PREV_REPORT_DATE = "2026-03-30"


def _make_bond_row(
    *,
    report_date: str,
    instrument_code: str,
    instrument_name: str,
    market_value: Decimal,
) -> Any:
    from backend.app.core_finance.bond_analytics.engine import BondAnalyticsRow

    return BondAnalyticsRow(
        report_date=date.fromisoformat(report_date),
        instrument_code=instrument_code,
        instrument_name=instrument_name,
        portfolio_name="P1",
        cost_center="C1",
        asset_class_raw="rate",
        asset_class_std="rate",
        bond_type="policy",
        issuer_name="Issuer",
        industry_name="bank",
        rating="AAA",
        accounting_class="OCI",
        accounting_rule_id="r1",
        currency_code="CNY",
        face_value=Decimal("1000"),
        market_value_native=market_value,
        market_value=market_value,
        amortized_cost=market_value,
        accrued_interest=Decimal("0"),
        coupon_rate=Decimal("0.025"),
        interest_mode="fixed",
        interest_payment_frequency="annual",
        interest_rate_style="fixed",
        ytm=Decimal("0.02"),
        maturity_date=date(2030, 1, 1),
        next_call_date=None,
        years_to_maturity=Decimal("3.8"),
        tenor_bucket="3-5Y",
        macaulay_duration=Decimal("4.0"),
        modified_duration=Decimal("3.9"),
        convexity=Decimal("0.01"),
        dv01=Decimal("0.39"),
        is_credit=False,
        spread_dv01=Decimal("0"),
        source_version="sv_home_change_test",
        rule_version="rv_home_change_test",
        ingest_batch_id="ib_home_change_test",
        trace_id="tr_home_change_test",
    )


def test_position_changes_endpoint_compares_adjacent_report_dates(tmp_path, monkeypatch) -> None:
    from backend.app.repositories.bond_analytics_repo import BondAnalyticsRepository

    duckdb_path = tmp_path / "position-changes.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    try:
        repo = BondAnalyticsRepository(str(duckdb_path))
        repo.replace_bond_analytics_rows(
            report_date=PREV_REPORT_DATE,
            rows=[
                _make_bond_row(
                    report_date=PREV_REPORT_DATE,
                    instrument_code="KEEP",
                    instrument_name="存量债",
                    market_value=Decimal("100"),
                ),
                _make_bond_row(
                    report_date=PREV_REPORT_DATE,
                    instrument_code="CUT",
                    instrument_name="减仓债",
                    market_value=Decimal("80"),
                ),
            ],
        )
        repo.replace_bond_analytics_rows(
            report_date=REPORT_DATE,
            rows=[
                _make_bond_row(
                    report_date=REPORT_DATE,
                    instrument_code="KEEP",
                    instrument_name="存量债",
                    market_value=Decimal("130"),
                ),
                _make_bond_row(
                    report_date=REPORT_DATE,
                    instrument_code="CUT",
                    instrument_name="减仓债",
                    market_value=Decimal("50"),
                ),
                _make_bond_row(
                    report_date=REPORT_DATE,
                    instrument_code="NEW",
                    instrument_name="新增债",
                    market_value=Decimal("40"),
                ),
            ],
        )

        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        response = client.get(
            "/api/bond-analytics/position-changes",
            params={"report_date": REPORT_DATE, "top_n": 3},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["result_meta"]["result_kind"] == "bond_analytics.position_changes"
        result = payload["result"]
        assert result["report_date"] == REPORT_DATE
        assert result["prev_report_date"] == PREV_REPORT_DATE
        assert result["source_status"] == "ready"
        assert [item["instrument_code"] for item in result["items"]] == ["NEW", "KEEP", "CUT"]
        assert result["items"][0]["direction"] == "increase"
        assert result["items"][0]["reason_label"] == "新增"
        assert Decimal(str(result["items"][0]["change_market_value"]["raw"])) == Decimal("40")
        assert result["items"][2]["direction"] == "decrease"
        assert result["items"][2]["reason_label"] == "减持"
    finally:
        get_settings.cache_clear()


def test_home_research_reports_endpoint_reads_research_news_only(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "research-reports.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        ensure_news_warehouse_schema(conn)
        upsert_news_event(
            conn,
            source="tushare_research",
            source_kind="research",
            title="利率债周报",
            url="https://example.com/research.pdf",
            content=None,
            summary="关注久期和曲线",
            pub_time_iso="2026-03-30T09:00:00+00:00",
            extra={"category": "fixed_income"},
        )
        upsert_news_event(
            conn,
            source="tushare_news",
            source_kind="news",
            title="普通新闻",
            url="https://example.com/news",
            content=None,
            summary="不应进入研究报告列表",
            pub_time_iso="2026-03-30T10:00:00+00:00",
            extra={},
        )
    finally:
        conn.close()

    try:
        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        response = client.get(
            "/ui/home/research-reports",
            params={"report_date": REPORT_DATE, "limit": 5},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["result_meta"]["result_kind"] == "home.research_reports"
        result = payload["result"]
        assert result["report_date"] == REPORT_DATE
        assert result["source_status"] == "ready"
        assert len(result["items"]) == 1
        assert result["items"][0]["title"] == "利率债周报"
        assert result["items"][0]["category"] == "fixed_income"
        assert result["items"][0]["link"] == "https://example.com/research.pdf"
        assert result["items"][0]["source_status"] == "ready"
    finally:
        get_settings.cache_clear()


def test_home_research_reports_falls_back_to_latest_when_report_date_has_no_rows(
    tmp_path, monkeypatch
) -> None:
    duckdb_path = tmp_path / "research-reports-fallback.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        ensure_news_warehouse_schema(conn)
        upsert_news_event(
            conn,
            source="tushare_research",
            source_kind="research",
            title="6月利率债周报",
            url="https://example.com/june-research.pdf",
            content=None,
            summary="关注曲线陡峭化",
            pub_time_iso="2026-06-01T09:00:00+00:00",
            extra={"category": "fixed_income"},
        )
        upsert_news_event(
            conn,
            source="tushare_research",
            source_kind="research",
            title="6月电力设备行业跟踪周报",
            url="https://example.com/power-research.pdf",
            content=None,
            summary="锂电和工控需求持续向上",
            pub_time_iso="2026-06-02T09:00:00+00:00",
            extra={"category": "行业研报"},
        )
        upsert_news_event(
            conn,
            source="tushare_research",
            source_kind="research",
            title="证券行业报告：流动性宽松支撑业绩",
            url="https://example.com/broker-research.pdf",
            content=None,
            summary="非固收研报",
            pub_time_iso="2026-06-03T09:00:00+00:00",
            extra={"category": "行业研报"},
        )
    finally:
        conn.close()

    try:
        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        response = client.get(
            "/ui/home/research-reports",
            params={"report_date": REPORT_DATE, "limit": 5},
        )

        assert response.status_code == 200, response.text
        result = response.json()["result"]
        assert result["report_date"] == REPORT_DATE
        assert result["source_status"] == "stale"
        assert len(result["items"]) == 1
        assert result["items"][0]["title"] == "6月利率债周报"
        assert any("latest ingested" in warning for warning in result["warnings"])
    finally:
        get_settings.cache_clear()


def _seed_product_category_income_trend(duckdb_path: Any) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table product_category_pnl_formal_read_model (
              report_date varchar,
              view varchar,
              sort_order integer,
              category_id varchar,
              category_name varchar,
              side varchar,
              level integer,
              baseline_ftp_rate_pct decimal(12, 6),
              cnx_scale decimal(24, 8),
              cny_scale decimal(24, 8),
              foreign_scale decimal(24, 8),
              cnx_cash decimal(24, 8),
              cny_cash decimal(24, 8),
              foreign_cash decimal(24, 8),
              cny_ftp decimal(24, 8),
              foreign_ftp decimal(24, 8),
              cny_net decimal(24, 8),
              foreign_net decimal(24, 8),
              business_net_income decimal(24, 8),
              weighted_yield decimal(24, 8),
              is_total boolean,
              children_json varchar,
              source_version varchar,
              rule_version varchar
            )
            """
        )
        rows = [
            ("2026-01-31", Decimal("100000000")),
            ("2026-02-28", Decimal("120000000")),
            ("2026-03-31", Decimal("90000000")),
        ]
        conn.executemany(
            """
            insert into product_category_pnl_formal_read_model (
              report_date,
              view,
              sort_order,
              category_id,
              category_name,
              side,
              level,
              baseline_ftp_rate_pct,
              cnx_scale,
              cny_scale,
              foreign_scale,
              cnx_cash,
              cny_cash,
              foreign_cash,
              cny_ftp,
              foreign_ftp,
              cny_net,
              foreign_net,
              business_net_income,
              weighted_yield,
              is_total,
              children_json,
              source_version,
              rule_version
            ) values (?, 'monthly', 1, 'grand_total', 'grand_total', 'all', 0, 1.75, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ?, null, true, '[]', 'sv_income_trend_test', 'rv_income_trend_test')
            """,
            rows,
        )
    finally:
        conn.close()


def test_home_income_trend_endpoint_reads_product_category_monthly_grand_total(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "income-trend.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    _seed_product_category_income_trend(duckdb_path)

    try:
        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        response = client.get(
            "/ui/home/income-trend",
            params={"report_date": REPORT_DATE, "window": 2},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["result_meta"]["result_kind"] == "home.income_trend"
        result = payload["result"]
        assert result["report_date"] == REPORT_DATE
        assert result["source_status"] == "partial"
        assert result["missing_components"] == ["benchmark_pnl", "excess_pnl"]
        assert [point["date"] for point in result["points"]] == ["2026-02-28", "2026-03-31"]
        assert Decimal(str(result["points"][0]["portfolio_pnl"]["raw"])) == Decimal("120000000.0")
        assert result["points"][0]["benchmark_pnl"]["raw"] is None
        assert result["points"][0]["excess_pnl"]["raw"] is None
        assert result["points"][0]["basis"] == "product_category_pnl_monthly"
        assert result["points"][0]["source_status"] == "partial"
    finally:
        get_settings.cache_clear()


def test_home_income_trend_endpoint_derives_cdb_benchmark_and_excess_pnl(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "income-trend-benchmark.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    _seed_product_category_income_trend(duckdb_path)

    def numeric(raw: Decimal, unit: str = "pct") -> dict[str, object]:
        return {
            "raw": float(raw),
            "unit": unit,
            "display": str(raw),
            "precision": 8,
            "sign_aware": True,
        }

    def fake_benchmark_excess(report_date: date, period_type: str = "MoM", benchmark_id: str = "CDB_INDEX") -> dict[str, Any]:
        assert period_type == "MoM"
        assert benchmark_id == "CDB_INDEX"
        return {
            "result": {
                "report_date": report_date.isoformat(),
                "benchmark_id": benchmark_id,
                "portfolio_return": numeric(Decimal("0.012")),
                "benchmark_return": numeric(Decimal("0.008")),
                "excess_return": numeric(Decimal("40"), "bp"),
                "warnings": [],
            },
            "result_meta": {
                "source_version": "sv_cdb_curve_test",
                "rule_version": "rv_benchmark_excess_test",
                "vendor_status": "ok",
            },
        }

    service_mod = load_module(
        "backend.app.services.executive_service",
        "backend/app/services/executive_service.py",
    )
    monkeypatch.setattr(service_mod, "get_benchmark_excess", fake_benchmark_excess)

    try:
        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        response = client.get(
            "/ui/home/income-trend",
            params={"report_date": REPORT_DATE, "window": 2},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        result = payload["result"]
        assert result["source_status"] == "ready"
        assert result["missing_components"] == []
        assert result["warnings"] == []
        assert [point["source_status"] for point in result["points"]] == ["ready", "ready"]
        assert Decimal(str(result["points"][0]["portfolio_pnl"]["raw"])) == Decimal("120000000.0")
        assert Decimal(str(result["points"][0]["benchmark_pnl"]["raw"])) == Decimal("80000000.0")
        assert Decimal(str(result["points"][0]["excess_pnl"]["raw"])) == Decimal("40000000.0")
        assert (
            Decimal(str(result["points"][0]["benchmark_pnl"]["raw"]))
            + Decimal(str(result["points"][0]["excess_pnl"]["raw"]))
            - Decimal(str(result["points"][0]["portfolio_pnl"]["raw"]))
        ).copy_abs() <= Decimal("1")
        assert payload["result_meta"]["filters_applied"]["benchmark_id"] == "CDB_INDEX"
        assert "rv_benchmark_excess_test" in payload["result_meta"]["rule_version"]
    finally:
        get_settings.cache_clear()


def test_home_income_trend_endpoint_accepts_bounded_cdb_curve_fallback(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "income-trend-bounded-benchmark-fallback.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    _seed_product_category_income_trend(duckdb_path)

    def numeric(raw: Decimal, unit: str = "pct") -> dict[str, object]:
        return {
            "raw": float(raw),
            "unit": unit,
            "display": str(raw),
            "precision": 8,
            "sign_aware": True,
        }

    def fake_benchmark_excess(report_date: date, period_type: str = "MoM", benchmark_id: str = "CDB_INDEX") -> dict[str, Any]:
        requested_date = "2026-02-01" if report_date.isoformat() == "2026-02-28" else "2026-03-01"
        resolved_date = "2026-01-31" if requested_date == "2026-02-01" else "2026-02-28"
        return {
            "result": {
                "report_date": report_date.isoformat(),
                "benchmark_id": benchmark_id,
                "portfolio_return": numeric(Decimal("0.012")),
                "benchmark_return": numeric(Decimal("0.008")),
                "excess_return": numeric(Decimal("40"), "bp"),
                "warnings": [
                    "YIELD_CURVE_LATEST_FALLBACK: Using latest available cdb curve "
                    f"from trade_date={resolved_date} for requested_trade_date={requested_date}."
                ],
            },
            "result_meta": {
                "source_version": "sv_cdb_curve_test",
                "rule_version": "rv_benchmark_excess_test",
                "vendor_status": "vendor_stale",
                "fallback_mode": "latest_snapshot",
            },
        }

    service_mod = load_module(
        "backend.app.services.executive_service",
        "backend/app/services/executive_service.py",
    )
    monkeypatch.setattr(service_mod, "get_benchmark_excess", fake_benchmark_excess)

    try:
        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        response = client.get(
            "/ui/home/income-trend",
            params={"report_date": REPORT_DATE, "window": 2},
        )

        assert response.status_code == 200, response.text
        result = response.json()["result"]
        assert result["source_status"] == "ready"
        assert result["missing_components"] == []
        assert result["warnings"] == []
        assert [point["source_status"] for point in result["points"]] == ["ready", "ready"]
        assert Decimal(str(result["points"][0]["benchmark_pnl"]["raw"])) == Decimal("80000000.0")
        assert Decimal(str(result["points"][0]["excess_pnl"]["raw"])) == Decimal("40000000.0")
    finally:
        get_settings.cache_clear()


def test_home_income_trend_endpoint_accepts_flat_numeric_benchmark_returns(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "income-trend-flat-benchmark-returns.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    _seed_product_category_income_trend(duckdb_path)

    def fake_benchmark_excess(report_date: date, period_type: str = "MoM", benchmark_id: str = "CDB_INDEX") -> dict[str, Any]:
        return {
            "result": {
                "report_date": report_date.isoformat(),
                "benchmark_id": benchmark_id,
                "portfolio_return": "1.2",
                "benchmark_return": "0.8",
                "excess_return": "40",
                "warnings": [],
            },
            "result_meta": {
                "source_version": "sv_cdb_curve_test",
                "rule_version": "rv_benchmark_excess_test",
                "vendor_status": "ok",
            },
        }

    service_mod = load_module(
        "backend.app.services.executive_service",
        "backend/app/services/executive_service.py",
    )
    monkeypatch.setattr(service_mod, "get_benchmark_excess", fake_benchmark_excess)

    try:
        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        response = client.get(
            "/ui/home/income-trend",
            params={"report_date": REPORT_DATE, "window": 2},
        )

        assert response.status_code == 200, response.text
        result = response.json()["result"]
        assert result["source_status"] == "ready"
        assert result["missing_components"] == []
        assert result["warnings"] == []
        assert Decimal(str(result["points"][0]["benchmark_pnl"]["raw"])) == Decimal("80000000.0")
        assert Decimal(str(result["points"][0]["excess_pnl"]["raw"])) == Decimal("40000000.0")
    finally:
        get_settings.cache_clear()


def test_home_income_trend_endpoint_keeps_partial_when_cdb_curve_fallback_too_stale(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "income-trend-stale-benchmark-fallback.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    _seed_product_category_income_trend(duckdb_path)

    def numeric(raw: Decimal, unit: str = "pct") -> dict[str, object]:
        return {
            "raw": float(raw),
            "unit": unit,
            "display": str(raw),
            "precision": 8,
            "sign_aware": True,
        }

    def fake_benchmark_excess(report_date: date, period_type: str = "MoM", benchmark_id: str = "CDB_INDEX") -> dict[str, Any]:
        return {
            "result": {
                "report_date": report_date.isoformat(),
                "benchmark_id": benchmark_id,
                "portfolio_return": numeric(Decimal("0.012")),
                "benchmark_return": numeric(Decimal("0.008")),
                "excess_return": numeric(Decimal("40"), "bp"),
                "warnings": [
                    "YIELD_CURVE_LATEST_FALLBACK: Using latest available cdb curve "
                    "from trade_date=2025-12-31 for requested_trade_date=2026-03-01."
                ],
            },
            "result_meta": {
                "source_version": "sv_cdb_curve_test",
                "rule_version": "rv_benchmark_excess_test",
                "vendor_status": "vendor_stale",
                "fallback_mode": "latest_snapshot",
            },
        }

    service_mod = load_module(
        "backend.app.services.executive_service",
        "backend/app/services/executive_service.py",
    )
    monkeypatch.setattr(service_mod, "get_benchmark_excess", fake_benchmark_excess)

    try:
        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        response = client.get(
            "/ui/home/income-trend",
            params={"report_date": REPORT_DATE, "window": 2},
        )

        assert response.status_code == 200, response.text
        result = response.json()["result"]
        assert result["source_status"] == "partial"
        assert result["missing_components"] == ["benchmark_pnl", "excess_pnl"]
        assert result["points"][0]["benchmark_pnl"]["raw"] is None
        assert result["points"][0]["excess_pnl"]["raw"] is None
        assert any("YIELD_CURVE_LATEST_FALLBACK" in warning for warning in result["warnings"])
    finally:
        get_settings.cache_clear()


def test_home_income_trend_endpoint_keeps_partial_when_cdb_benchmark_missing(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "income-trend-missing-benchmark.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    _seed_product_category_income_trend(duckdb_path)

    def numeric(raw: Decimal, unit: str = "pct") -> dict[str, object]:
        return {
            "raw": float(raw),
            "unit": unit,
            "display": str(raw),
            "precision": 8,
            "sign_aware": True,
        }

    def fake_benchmark_excess(report_date: date, period_type: str = "MoM", benchmark_id: str = "CDB_INDEX") -> dict[str, Any]:
        return {
            "result": {
                "report_date": report_date.isoformat(),
                "benchmark_id": benchmark_id,
                "portfolio_return": numeric(Decimal("0.012")),
                "benchmark_return": numeric(Decimal("0")),
                "excess_return": numeric(Decimal("0")),
                "warnings": ["CDB_INDEX benchmark curve unavailable"],
            },
            "result_meta": {
                "source_version": "sv_cdb_curve_missing_test",
                "rule_version": "rv_benchmark_excess_test",
                "vendor_status": "vendor_unavailable",
            },
        }

    service_mod = load_module(
        "backend.app.services.executive_service",
        "backend/app/services/executive_service.py",
    )
    monkeypatch.setattr(service_mod, "get_benchmark_excess", fake_benchmark_excess)

    try:
        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        response = client.get(
            "/ui/home/income-trend",
            params={"report_date": REPORT_DATE, "window": 2},
        )

        assert response.status_code == 200, response.text
        result = response.json()["result"]
        assert result["source_status"] == "partial"
        assert result["missing_components"] == ["benchmark_pnl", "excess_pnl"]
        assert result["points"][0]["benchmark_pnl"]["raw"] is None
        assert result["points"][0]["excess_pnl"]["raw"] is None
        assert any("CDB_INDEX" in warning for warning in result["warnings"])
    finally:
        get_settings.cache_clear()
