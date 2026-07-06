from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, get_args

import duckdb
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.news_warehouse_repo import (
    ensure_news_warehouse_schema,
    upsert_news_event,
)
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.schemas.executive_dashboard import (
    HomeIncomeTrendPointSourceStatus,
    HomeIncomeTrendSourceStatus,
)
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module

REPORT_DATE = "2026-03-31"
PREV_REPORT_DATE = "2026-03-30"
READ_HEADERS = {"X-User-Id": "dashboard-home-read-user", "X-User-Role": "viewer"}


def _grant_read_scope(tmp_path, monkeypatch, *, resource: str) -> None:
    sqlite_path = tmp_path / "auth-scope.db"
    dsn = f"sqlite:///{sqlite_path.as_posix()}"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", dsn)
    monkeypatch.setenv("MOSS_GOVERNANCE_SQL_DSN", dsn)
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    repo_module = load_module(
        "backend.app.repositories.user_scope_repo",
        "backend/app/repositories/user_scope_repo.py",
    )
    repo_module.UserScopeRepository(dsn).grant_scope(
        user_id="*",
        role=None,
        resource=resource,
        action="read",
    )


def _authorized_client():
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    client.headers.update(READ_HEADERS)
    return client


def _replace_dashboard_home_bond_rows(repo: Any, *, report_date: str, rows: list[Any]) -> None:
    with repository_task_write_scope("backend.app.tasks.dashboard_home_backend_blocks_test"):
        repo.replace_bond_analytics_rows(report_date=report_date, rows=rows)
    if rows:
        _append_bond_analytics_completed_build(
            report_date=report_date,
            source_version=_first_row_source_version(rows),
        )


def _first_row_source_version(rows: list[Any]) -> str:
    for row in rows:
        value = row.get("source_version") if isinstance(row, dict) else getattr(row, "source_version", "")
        text = str(value or "").strip()
        if text:
            return text
    return "sv_dashboard_home_test"


def _append_bond_analytics_completed_build(*, report_date: str, source_version: str) -> None:
    governance_path = Path(str(get_settings().governance_path))
    governance_path.mkdir(parents=True, exist_ok=True)
    record = {
        "run_id": f"dashboard-home-test:{report_date}",
        "job_name": "bond_analytics_materialize",
        "status": "completed",
        "cache_key": "bond_analytics:materialize:formal",
        "cache_version": "cv_bond_analytics_formal__rv_bond_analytics_formal_materialize_v1",
        "source_version": source_version,
        "vendor_version": "vv_none",
        "rule_version": "rv_bond_analytics_formal_materialize_v1",
        "report_date": report_date,
    }
    with (governance_path / "cache_build_run.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


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
        _replace_dashboard_home_bond_rows(
            repo,
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
        _replace_dashboard_home_bond_rows(
            repo,
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

        _grant_read_scope(tmp_path, monkeypatch, resource="bond_analytics")
        client = _authorized_client()
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
        with repository_task_write_scope("backend.app.tasks.dashboard_home_test_seed"):
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
        _grant_read_scope(tmp_path, monkeypatch, resource="executive")
        client = _authorized_client()
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


def test_home_research_reports_does_not_fallback_to_future_rows(
    tmp_path, monkeypatch
) -> None:
    duckdb_path = tmp_path / "research-reports-fallback.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        ensure_news_warehouse_schema(conn)
        with repository_task_write_scope("backend.app.tasks.dashboard_home_test_seed"):
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
        _grant_read_scope(tmp_path, monkeypatch, resource="executive")
        client = _authorized_client()
        response = client.get(
            "/ui/home/research-reports",
            params={"report_date": REPORT_DATE, "limit": 5},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        result = payload["result"]
        assert result["report_date"] == REPORT_DATE
        assert result["source_status"] == "empty"
        assert result["items"] == []
        assert any("on or before report_date" in warning for warning in result["warnings"])
        assert not any("latest ingested" in warning for warning in result["warnings"])
        assert payload["result_meta"]["filters_applied"]["research_date_mode"] == "on_or_before_report_date"
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


def _patch_home_income_batch_from_single(service_mod: Any, monkeypatch: Any, single_fetch: Any) -> None:
    def fake_batch(report_dates, period_type: str = "MoM", benchmark_id: str = "CDB_INDEX") -> dict[str, Any]:
        return {
            value.isoformat(): single_fetch(value, period_type, benchmark_id)
            for value in report_dates
        }

    monkeypatch.setattr(service_mod, "get_benchmark_excess_many", fake_batch)
    monkeypatch.setattr(service_mod, "get_benchmark_excess", single_fetch)


def test_home_income_trend_endpoint_reads_product_category_monthly_grand_total(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "income-trend.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    _seed_product_category_income_trend(duckdb_path)

    try:
        _grant_read_scope(tmp_path, monkeypatch, resource="executive")
        client = _authorized_client()
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


def test_home_income_trend_service_source_status_value_domain_matches_schema(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "income-trend-source-status.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    _seed_product_category_income_trend(duckdb_path)

    service_mod = load_module(
        "backend.app.services.executive_service",
        "backend/app/services/executive_service.py",
    )
    allowed_point_statuses = set(get_args(HomeIncomeTrendPointSourceStatus))
    allowed_payload_statuses = set(get_args(HomeIncomeTrendSourceStatus))

    try:
        service_mod.invalidate_home_snapshot_cache()
        payload = service_mod.home_income_trend_envelope(report_date=REPORT_DATE, window=2)
        point_statuses = [point["source_status"] for point in payload["result"]["points"]]

        assert allowed_point_statuses == {"ready", "partial"}
        assert allowed_payload_statuses == {"ready", "partial", "empty"}
        assert payload["result"]["source_status"] in allowed_payload_statuses
        assert point_statuses
        assert set(point_statuses) <= allowed_point_statuses
        assert "partial" in point_statuses
    finally:
        service_mod.invalidate_home_snapshot_cache()
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
    _patch_home_income_batch_from_single(service_mod, monkeypatch, fake_benchmark_excess)

    try:
        _grant_read_scope(tmp_path, monkeypatch, resource="executive")
        client = _authorized_client()
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
    _patch_home_income_batch_from_single(service_mod, monkeypatch, fake_benchmark_excess)

    try:
        _grant_read_scope(tmp_path, monkeypatch, resource="executive")
        client = _authorized_client()
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


def test_home_income_trend_keeps_benchmark_when_only_amount_disclosure_warning_blocks(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "income-trend-disclosure-warning.duckdb"
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
                    f"from trade_date={resolved_date} for requested_trade_date={requested_date}.",
                    "Foreign-currency bond positions are disclosed on a CNY/RMB basis where formal CNY closure is available. "
                    "The current API model does not expose row-level fallback markers; if upstream formal CNY closure is missing "
                    "for some positions, derived amount fields may fall back to native currency values. Detected foreign currencies: USD.",
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
    _patch_home_income_batch_from_single(service_mod, monkeypatch, fake_benchmark_excess)

    try:
        _grant_read_scope(tmp_path, monkeypatch, resource="executive")
        client = _authorized_client()
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
    _patch_home_income_batch_from_single(service_mod, monkeypatch, fake_benchmark_excess)

    try:
        _grant_read_scope(tmp_path, monkeypatch, resource="executive")
        client = _authorized_client()
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
    _patch_home_income_batch_from_single(service_mod, monkeypatch, fake_benchmark_excess)

    try:
        _grant_read_scope(tmp_path, monkeypatch, resource="executive")
        client = _authorized_client()
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
    _patch_home_income_batch_from_single(service_mod, monkeypatch, fake_benchmark_excess)

    try:
        _grant_read_scope(tmp_path, monkeypatch, resource="executive")
        client = _authorized_client()
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


def test_home_income_trend_fetches_benchmark_points_in_one_batch(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "income-trend-concurrent-benchmark.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    _seed_product_category_income_trend(duckdb_path)

    called_dates: list[str] = []

    def numeric(raw: Decimal, unit: str = "pct") -> dict[str, object]:
        return {
            "raw": float(raw),
            "unit": unit,
            "display": str(raw),
            "precision": 8,
            "sign_aware": True,
        }

    def fake_benchmark_excess_many(report_dates, period_type: str = "MoM", benchmark_id: str = "CDB_INDEX") -> dict[str, Any]:
        assert period_type == "MoM"
        assert benchmark_id == "CDB_INDEX"
        called_dates.extend(value.isoformat() for value in report_dates)
        return {
            value.isoformat(): {
                "result": {
                    "report_date": value.isoformat(),
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
            for value in report_dates
        }

    service_mod = load_module(
        "backend.app.services.executive_service",
        "backend/app/services/executive_service.py",
    )
    monkeypatch.setattr(service_mod, "get_benchmark_excess_many", fake_benchmark_excess_many)

    try:
        payload = service_mod.home_income_trend_envelope(
            report_date=REPORT_DATE,
            window=3,
        )

        assert payload["result"]["source_status"] == "ready"
        assert called_dates == ["2026-01-31", "2026-02-28", "2026-03-31"]
    finally:
        get_settings.cache_clear()


def test_home_income_trend_reuses_cached_envelope_for_same_window(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "income-trend-cache.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    _seed_product_category_income_trend(duckdb_path)

    service_mod = load_module(
        "backend.app.services.executive_service",
        "backend/app/services/executive_service.py",
    )
    service_mod.invalidate_home_snapshot_cache()

    original_repo = service_mod.ProductCategoryPnlRepository

    class CountingProductCategoryPnlRepository(original_repo):
        list_report_dates_calls = 0
        fetch_rows_calls = 0

        def list_report_dates(self):
            type(self).list_report_dates_calls += 1
            return super().list_report_dates()

        def fetch_rows(self, report_date: str, view: str):
            type(self).fetch_rows_calls += 1
            return super().fetch_rows(report_date, view)

    benchmark_calls = 0

    def fake_benchmark_excess_many(report_dates, period_type: str = "MoM", benchmark_id: str = "CDB_INDEX") -> dict[str, Any]:
        nonlocal benchmark_calls
        benchmark_calls += 1
        return {
            value.isoformat(): {
                "result": {
                    "report_date": value.isoformat(),
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
            for value in report_dates
        }

    monkeypatch.setattr(service_mod, "ProductCategoryPnlRepository", CountingProductCategoryPnlRepository)
    monkeypatch.setattr(service_mod, "get_benchmark_excess_many", fake_benchmark_excess_many)

    try:
        first = service_mod.home_income_trend_envelope(report_date=REPORT_DATE, window=2)
        first["result"]["points"][0]["portfolio_pnl"]["display"] = "mutated"
        second = service_mod.home_income_trend_envelope(report_date=REPORT_DATE, window=2)

        assert second["result"]["source_status"] == "ready"
        assert second["result"]["points"][0]["portfolio_pnl"]["display"] != "mutated"
        assert CountingProductCategoryPnlRepository.list_report_dates_calls == 1
        assert CountingProductCategoryPnlRepository.fetch_rows_calls == 2
        assert benchmark_calls == 1
    finally:
        service_mod.invalidate_home_snapshot_cache()
        get_settings.cache_clear()


def test_home_income_trend_uses_batch_benchmark_fetch_when_available(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "income-trend-batch-benchmark.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    get_settings.cache_clear()
    _seed_product_category_income_trend(duckdb_path)

    service_mod = load_module(
        "backend.app.services.executive_service",
        "backend/app/services/executive_service.py",
    )
    service_mod.invalidate_home_snapshot_cache()

    batch_calls: list[list[str]] = []

    def fake_batch(report_dates, period_type: str = "MoM", benchmark_id: str = "CDB_INDEX") -> dict[str, Any]:
        batch_calls.append([value.isoformat() for value in report_dates])
        return {
            value.isoformat(): {
                "result": {
                    "report_date": value.isoformat(),
                    "benchmark_id": benchmark_id,
                    "portfolio_return": "1.2",
                    "benchmark_return": "0.8",
                    "excess_return": "40",
                    "warnings": [],
                },
                "result_meta": {
                    "source_version": "sv_cdb_curve_test",
                    "rule_version": "rv_benchmark_excess_batch_test",
                    "vendor_status": "ok",
                },
            }
            for value in report_dates
        }

    def fail_single(*_args, **_kwargs):
        raise AssertionError("income trend should use batch benchmark fetch for windows")

    monkeypatch.setattr(service_mod, "get_benchmark_excess_many", fake_batch)
    monkeypatch.setattr(service_mod, "get_benchmark_excess", fail_single)

    try:
        payload = service_mod.home_income_trend_envelope(report_date=REPORT_DATE, window=3)

        assert payload["result"]["source_status"] == "ready"
        assert batch_calls == [["2026-01-31", "2026-02-28", "2026-03-31"]]
        assert "rv_benchmark_excess_batch_test" in payload["result_meta"]["rule_version"]
    finally:
        service_mod.invalidate_home_snapshot_cache()
        get_settings.cache_clear()
