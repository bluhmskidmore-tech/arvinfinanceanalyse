"""Contract tests for GET /api/analysis/adb/insights (PRD 2026-08-13 §5 / §8)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module

BOND_ASSET_CLASS = "\u503a\u5238\u7c7b"
BOND_GOV = "\u56fd\u503a"
BOND_CORP = "\u4fe1\u7528\u503a\u5238-\u4f01\u4e1a"
IB_ASSET_PRODUCT = "\u62c6\u653e\u540c\u4e1a"
IB_LIABILITY_PRODUCT = "\u5356\u51fa\u56de\u8d2d\u8bc1\u5238"
POSITION_ASSET = "\u8d44\u4ea7"
POSITION_LIABILITY = "\u8d1f\u503a"

CURRENT_START = date(2026, 3, 1)
CURRENT_END = date(2026, 3, 10)
QOQ_START = date(2026, 2, 19)
YOY_START = date(2025, 3, 1)
WINDOW_DAYS = 10

INSIGHTS_PATH = "/api/analysis/adb/insights"

pytestmark = pytest.mark.integration


def _configure_adb_scope_store(tmp_path: Path, monkeypatch):
    sqlite_path = tmp_path / "adb-insights-scope.db"
    auth_dsn = f"sqlite:///{sqlite_path.as_posix()}"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", auth_dsn)
    monkeypatch.setenv("MOSS_GOVERNANCE_SQL_DSN", auth_dsn)
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    repo_mod = load_module(
        "backend.app.repositories.user_scope_repo",
        "backend/app/repositories/user_scope_repo.py",
    )
    return repo_mod.UserScopeRepository(auth_dsn)


def _seed_adb_read_scope(tmp_path: Path, monkeypatch) -> None:
    _configure_adb_scope_store(tmp_path, monkeypatch).grant_scope(
        user_id="*",
        role=None,
        resource="adb_analysis",
        action="read",
    )


def _create_formal_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table fact_formal_zqtz_balance_daily (
          report_date date,
          position_scope varchar,
          currency_basis varchar,
          market_value_amount decimal(24, 2),
          ytm_value decimal(18, 6),
          coupon_rate decimal(18, 6),
          asset_class varchar,
          bond_type varchar,
          sub_type varchar,
          is_issuance_like boolean,
          source_version varchar,
          rule_version varchar
        )
        """
    )
    conn.execute(
        """
        create table fact_formal_tyw_balance_daily (
          report_date date,
          position_scope varchar,
          position_side varchar,
          currency_basis varchar,
          principal_amount decimal(24, 2),
          funding_cost_rate decimal(18, 6),
          product_type varchar,
          source_version varchar,
          rule_version varchar
        )
        """
    )


def _insert_bond(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    bond_type: str,
    market_value: Decimal,
    ytm: Decimal,
) -> None:
    conn.execute(
        "insert into fact_formal_zqtz_balance_daily values (?, 'asset', 'CNY', ?, ?, ?, ?, ?, null, false, ?, ?)",
        [
            report_date,
            market_value,
            ytm,
            ytm,
            BOND_ASSET_CLASS,
            bond_type,
            "sv-adb-insights",
            "rv-adb-insights",
        ],
    )


def _insert_interbank(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    scope: str,
    side: str,
    product_type: str,
    principal: Decimal,
    rate: Decimal,
) -> None:
    conn.execute(
        "insert into fact_formal_tyw_balance_daily values (?, ?, ?, 'CNY', ?, ?, ?, ?, ?)",
        [
            report_date,
            scope,
            side,
            principal,
            rate,
            product_type,
            "sv-adb-insights",
            "rv-adb-insights",
        ],
    )


def _seed_window(
    conn: duckdb.DuckDBPyConnection,
    *,
    start: date,
    gov_base: int,
    gov_step: int,
    gov_ytm: str,
    corp_ytm: str,
    ib_asset_rate: str,
    ib_liability_rate: str,
) -> None:
    for offset in range(WINDOW_DAYS):
        report_date = (start + timedelta(days=offset)).strftime("%Y-%m-%d")
        _insert_bond(
            conn,
            report_date=report_date,
            bond_type=BOND_GOV,
            market_value=Decimal(gov_base + gov_step * offset),
            ytm=Decimal(gov_ytm),
        )
        _insert_bond(
            conn,
            report_date=report_date,
            bond_type=BOND_CORP,
            market_value=Decimal(400_000_000),
            ytm=Decimal(corp_ytm),
        )
        _insert_interbank(
            conn,
            report_date=report_date,
            scope="asset",
            side=POSITION_ASSET,
            product_type=IB_ASSET_PRODUCT,
            principal=Decimal(200_000_000),
            rate=Decimal(ib_asset_rate),
        )
        _insert_interbank(
            conn,
            report_date=report_date,
            scope="liability",
            side=POSITION_LIABILITY,
            product_type=IB_LIABILITY_PRODUCT,
            principal=Decimal(600_000_000),
            rate=Decimal(ib_liability_rate),
        )


def _build_duckdb(tmp_path: Path, *, name: str, with_comparison_windows: bool) -> Path:
    db_path = tmp_path / name
    conn = duckdb.connect(str(db_path))
    try:
        _create_formal_tables(conn)
        _seed_window(
            conn,
            start=CURRENT_START,
            gov_base=1_000_000_000,
            gov_step=10_000_000,
            gov_ytm="2.50",
            corp_ytm="3.20",
            ib_asset_rate="2.10",
            ib_liability_rate="1.80",
        )
        if with_comparison_windows:
            _seed_window(
                conn,
                start=QOQ_START,
                gov_base=900_000_000,
                gov_step=0,
                gov_ytm="2.40",
                corp_ytm="3.10",
                ib_asset_rate="2.00",
                ib_liability_rate="1.60",
            )
            _seed_window(
                conn,
                start=YOY_START,
                gov_base=800_000_000,
                gov_step=0,
                gov_ytm="2.30",
                corp_ytm="3.00",
                ib_asset_rate="1.90",
                ib_liability_rate="1.50",
            )
    finally:
        conn.close()
    return db_path


def _client(tmp_path: Path, monkeypatch, *, db_path: Path) -> TestClient:
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    service_mod = load_module(
        "backend.app.services.adb_analysis_service",
        "backend/app/services/adb_analysis_service.py",
    )
    service_mod.clear_adb_insights_cache()
    main_mod = load_module("backend.app.main", "backend/app/main.py")
    return TestClient(main_mod.app)


def _current_window_params() -> dict[str, str]:
    return {
        "start_date": CURRENT_START.strftime("%Y-%m-%d"),
        "end_date": CURRENT_END.strftime("%Y-%m-%d"),
    }


def test_adb_insights_returns_full_analytical_payload(tmp_path: Path, monkeypatch) -> None:
    _seed_adb_read_scope(tmp_path, monkeypatch)
    db_path = _build_duckdb(tmp_path, name="adb-insights-full.duckdb", with_comparison_windows=True)
    client = _client(tmp_path, monkeypatch, db_path=db_path)

    response = client.get(INSIGHTS_PATH, params=_current_window_params())

    assert response.status_code == 200, response.text
    body = response.json()
    meta = body["result_meta"]
    assert meta["basis"] == "analytical"
    assert meta["formal_use_allowed"] is False
    assert meta["scenario_flag"] is False
    assert meta["result_kind"] == "adb.insights"
    assert meta["quality_flag"] == "ok"
    assert meta["fallback_mode"] == "none"
    assert set(meta["tables_used"]) == {
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
    }
    assert meta["filters_applied"] == {"start_date": "2026-03-01", "end_date": "2026-03-10"}

    payload = body["result"]
    assert set(payload) == {
        "start_date",
        "end_date",
        "calendar_days_inclusive",
        "insufficient_window",
        "windows",
        "scale_attribution",
        "nim_attribution",
        "nim_attribution_unavailable_reason",
        "volatility",
        "concentration",
        "insights",
    }
    assert payload["start_date"] == "2026-03-01"
    assert payload["end_date"] == "2026-03-10"
    assert payload["calendar_days_inclusive"] == 10
    assert payload["insufficient_window"] is False

    windows = payload["windows"]
    assert set(windows) == {"current", "qoq", "yoy"}
    assert windows["current"]["coverage_days"] == 10
    assert windows["qoq"] == {
        "start_date": "2026-02-19",
        "end_date": "2026-02-28",
        "calendar_days_inclusive": 10,
        "coverage_days": 10,
        "available": True,
        "reason": "ok",
    }
    assert windows["yoy"]["start_date"] == "2025-03-01"
    assert windows["yoy"]["available"] is True


def test_adb_insights_payload_satisfies_frozen_closure_identities(tmp_path: Path, monkeypatch) -> None:
    _seed_adb_read_scope(tmp_path, monkeypatch)
    db_path = _build_duckdb(tmp_path, name="adb-insights-closure.duckdb", with_comparison_windows=True)
    client = _client(tmp_path, monkeypatch, db_path=db_path)

    payload = client.get(INSIGHTS_PATH, params=_current_window_params()).json()["result"]

    for basis in ("qoq", "yoy"):
        attribution = payload["scale_attribution"][basis]
        assert attribution is not None, basis
        for side_key, rows_key, side_label in (
            ("assets", "asset_contributions", "asset"),
            ("liabilities", "liability_contributions", "liability"),
        ):
            totals = attribution["side_totals"][side_key]
            rows = attribution[rows_key]
            assert rows, f"{basis}/{side_key} must expose category rows"
            assert sum(row["delta"] for row in rows) == pytest.approx(totals["delta"], rel=1e-6, abs=1e-6)
            assert {row["side"] for row in rows} == {side_label}

    nim = payload["nim_attribution"]
    assert nim is not None
    assert payload["nim_attribution_unavailable_reason"] is None
    assert nim["basis"] == "qoq"
    for side_key in ("asset_side", "liability_side"):
        side = nim[side_key]
        assert side["rate_effect_bp"] + side["mix_effect_bp"] + side["residual_bp"] == pytest.approx(
            side["total_effect_bp"], abs=1e-6
        )
    assert nim["nim_delta_bp"] == pytest.approx(
        nim["asset_side"]["total_effect_bp"] - nim["liability_side"]["total_effect_bp"], abs=1e-6
    )
    # 负债成本 +20bp、资产收益率仅小幅走高 → NIM 环比收窄。
    assert nim["liability_side"]["total_effect_bp"] == pytest.approx(20.0, abs=1e-6)
    assert nim["nim_delta_bp"] < 0

    volatility = payload["volatility"]
    assert volatility is not None
    assert volatility["assets"]["max"]["date"] == "2026-03-10"
    assert volatility["assets"]["min"]["date"] == "2026-03-01"
    assert volatility["liabilities"]["std"] == pytest.approx(0.0)
    # 观测日仅 10 天且日变动恒定 → z-score 不可计算，必须显式披露而不是给空数组充数。
    assert volatility["anomaly_detection_available"] is False
    assert volatility["anomalies"] == []
    assert volatility["month_end_effect"]["assets"]["months_observed"] == 1

    concentration = payload["concentration"]
    assert concentration["reason"] is None
    assert concentration["assets"]["start_observation_date"] == "2026-03-01"
    assert concentration["assets"]["end_observation_date"] == "2026-03-10"
    assert 0 < concentration["assets"]["hhi_end"] <= 1
    assert concentration["liabilities"]["hhi_end"] == pytest.approx(1.0)

    insight_ids = [item["id"] for item in payload["insights"]]
    assert insight_ids
    assert "scale_qoq_move" in insight_ids
    assert "nim_compression" in insight_ids
    for item in payload["insights"]:
        assert set(item) == {"id", "severity", "dimension", "title", "detail", "evidence"}
        assert item["severity"] in {"info", "notice", "warning"}
        assert item["dimension"] in {"scale", "nim", "volatility", "concentration", "quality"}
        assert item["title"] and item["detail"]


def test_adb_insights_sparse_window_ties_out_to_existing_comparison_average(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _seed_adb_read_scope(tmp_path, monkeypatch)
    db_path = _build_duckdb(tmp_path, name="adb-insights-sparse.duckdb", with_comparison_windows=True)
    conn = duckdb.connect(str(db_path))
    try:
        for table in ("fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"):
            conn.execute(
                f"""
                delete from {table}
                where report_date between ? and ?
                  and extract(day from report_date) % 2 = 0
                """,
                [CURRENT_START, CURRENT_END],
            )
        conn.execute(
            """
            update fact_formal_zqtz_balance_daily
            set market_value_amount = null
            where report_date = ?
            """,
            [CURRENT_START],
        )
        conn.execute(
            """
            update fact_formal_tyw_balance_daily
            set principal_amount = null
            where report_date = ?
            """,
            [CURRENT_START],
        )
    finally:
        conn.close()
    client = _client(tmp_path, monkeypatch, db_path=db_path)

    comparison_response = client.get(
        "/api/analysis/adb/comparison",
        params={**_current_window_params(), "top_n": 200},
    )
    insights_response = client.get(INSIGHTS_PATH, params=_current_window_params())

    assert comparison_response.status_code == 200, comparison_response.text
    assert insights_response.status_code == 200, insights_response.text
    comparison = comparison_response.json()["result"]
    insights = insights_response.json()["result"]
    assert comparison["sample_fill_method"] == "observed_days_scaled_to_calendar"
    assert comparison["coverage_days"] == 4
    assert insights["windows"]["current"]["coverage_days"] == comparison["coverage_days"]
    qoq_totals = insights["scale_attribution"]["qoq"]["side_totals"]
    assert qoq_totals["assets"]["current_avg"] == pytest.approx(comparison["total_avg_assets"])
    assert qoq_totals["liabilities"]["current_avg"] == pytest.approx(
        comparison["total_avg_liabilities"]
    )


def test_adb_insights_treats_all_invalid_current_balances_as_unavailable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _seed_adb_read_scope(tmp_path, monkeypatch)
    db_path = _build_duckdb(
        tmp_path,
        name="adb-insights-invalid-current.duckdb",
        with_comparison_windows=True,
    )
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            update fact_formal_zqtz_balance_daily
            set market_value_amount = null
            where report_date between ? and ?
            """,
            [CURRENT_START, CURRENT_END],
        )
        conn.execute(
            """
            update fact_formal_tyw_balance_daily
            set principal_amount = null
            where report_date between ? and ?
            """,
            [CURRENT_START, CURRENT_END],
        )
    finally:
        conn.close()
    client = _client(tmp_path, monkeypatch, db_path=db_path)

    response = client.get(INSIGHTS_PATH, params=_current_window_params())

    assert response.status_code == 200, response.text
    payload = response.json()["result"]
    assert payload["windows"]["current"]["available"] is False
    assert payload["windows"]["current"]["coverage_days"] == 0
    assert payload["scale_attribution"] == {"qoq": None, "yoy": None}
    assert payload["nim_attribution"] is None
    assert payload["nim_attribution_unavailable_reason"] == "current_unavailable"
    assert payload["volatility"] is None
    assert payload["concentration"] is None
    assert any(item["id"] == "current_unavailable" for item in payload["insights"])


def test_adb_insights_returns_200_with_null_attribution_when_comparison_windows_are_empty(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _seed_adb_read_scope(tmp_path, monkeypatch)
    db_path = _build_duckdb(tmp_path, name="adb-insights-no-prior.duckdb", with_comparison_windows=False)
    client = _client(tmp_path, monkeypatch, db_path=db_path)

    response = client.get(INSIGHTS_PATH, params=_current_window_params())

    assert response.status_code == 200, response.text
    payload = response.json()["result"]
    assert payload["windows"]["current"]["available"] is True
    assert payload["windows"]["qoq"] == {
        "start_date": "2026-02-19",
        "end_date": "2026-02-28",
        "calendar_days_inclusive": 10,
        "coverage_days": 0,
        "available": False,
        "reason": "no_data",
    }
    assert payload["windows"]["yoy"]["available"] is False
    assert payload["scale_attribution"] == {"qoq": None, "yoy": None}
    assert payload["nim_attribution"] is None
    assert payload["nim_attribution_unavailable_reason"] == "comparison_unavailable"
    # 本期仍有数据：波动与集中度不受对比期缺数影响。
    assert payload["volatility"] is not None
    assert payload["concentration"] is not None
    assert any(item["id"] == "comparison_unavailable" for item in payload["insights"])


def test_adb_insights_single_day_window_nulls_analysis_blocks(tmp_path: Path, monkeypatch) -> None:
    _seed_adb_read_scope(tmp_path, monkeypatch)
    db_path = _build_duckdb(tmp_path, name="adb-insights-single-day.duckdb", with_comparison_windows=True)
    client = _client(tmp_path, monkeypatch, db_path=db_path)

    response = client.get(
        INSIGHTS_PATH,
        params={"start_date": "2026-03-05", "end_date": "2026-03-05"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()["result"]
    assert payload["calendar_days_inclusive"] == 1
    assert payload["insufficient_window"] is True
    assert payload["scale_attribution"] == {"qoq": None, "yoy": None}
    assert payload["nim_attribution"] is None
    assert payload["nim_attribution_unavailable_reason"] == "insufficient_window"
    assert payload["volatility"] is None
    assert payload["concentration"] is None
    assert payload["insights"] == []
    assert payload["windows"]["current"]["available"] is True


@pytest.mark.parametrize(
    "params,expected_status",
    [
        ({"start_date": "2026-03-01"}, 422),
        ({"start_date": "not-a-date", "end_date": "2026-03-10"}, 422),
        ({"start_date": "2026-03-10", "end_date": "2026-03-01"}, 400),
    ],
)
def test_adb_insights_rejects_invalid_windows(
    params: dict[str, str],
    expected_status: int,
    tmp_path: Path,
    monkeypatch,
) -> None:
    _seed_adb_read_scope(tmp_path, monkeypatch)
    db_path = _build_duckdb(tmp_path, name="adb-insights-errors.duckdb", with_comparison_windows=False)
    client = _client(tmp_path, monkeypatch, db_path=db_path)

    response = client.get(INSIGHTS_PATH, params=params)

    assert response.status_code == expected_status, response.text


def test_adb_insights_maps_service_errors_without_leaking_internal_detail(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """RuntimeError→503、ValueError→422；其余异常 500 固定文案且不回显内部文本。"""
    _seed_adb_read_scope(tmp_path, monkeypatch)
    db_path = _build_duckdb(tmp_path, name="adb-insights-boom.duckdb", with_comparison_windows=False)
    client = _client(tmp_path, monkeypatch, db_path=db_path)
    route_mod = load_module(
        "backend.app.api.routes.adb_analysis",
        "backend/app/api/routes/adb_analysis.py",
    )

    def _raiser(exc: Exception):
        def _boom(*_args, **_kwargs):
            raise exc

        return _boom

    monkeypatch.setattr(
        route_mod.adb_analysis_service,
        "adb_insights_envelope",
        _raiser(RuntimeError("adb insights backend unavailable")),
    )
    unavailable = client.get(INSIGHTS_PATH, params=_current_window_params())
    assert unavailable.status_code == 503, unavailable.text
    assert unavailable.json()["detail"] == "adb insights backend unavailable"

    monkeypatch.setattr(
        route_mod.adb_analysis_service,
        "adb_insights_envelope",
        _raiser(ValueError("adb insights window invalid")),
    )
    invalid = client.get(INSIGHTS_PATH, params=_current_window_params())
    assert invalid.status_code == 422, invalid.text
    assert invalid.json()["detail"] == "adb insights window invalid"

    monkeypatch.setattr(
        route_mod.adb_analysis_service,
        "adb_insights_envelope",
        _raiser(Exception("Binder Error: secret_table at C:\\secret\\moss.duckdb")),
    )
    broken = client.get(INSIGHTS_PATH, params=_current_window_params())
    assert broken.status_code == 500, broken.text
    assert broken.json()["detail"] == "Failed to get adb insights."
    assert "secret" not in broken.text
