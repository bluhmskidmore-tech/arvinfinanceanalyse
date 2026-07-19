"""API + shape tests for formal yield-curve term-structure ladder."""
from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.repositories.yield_curve_repo import (
    YIELD_CURVE_LATEST_FALLBACK_PREFIX,
    YieldCurveRepository,
)
from backend.app.schemas.yield_curve import YieldCurvePoint, YieldCurveSnapshot
from backend.app.services.yield_curve_term_structure_service import (
    YIELD_CURVE_TERM_STRUCTURE_TENORS,
)
from tests.helpers import load_module


def _seed_two_day_treasury_curve(duckdb_path: str) -> None:
    repo = YieldCurveRepository(duckdb_path)
    common = [
        YieldCurvePoint("1Y", Decimal("1.00")),
        YieldCurvePoint("10Y", Decimal("2.00")),
    ]
    with repository_task_write_scope("backend.app.tasks.yield_curve_term_structure_api_test"):
        repo.replace_curve_snapshots(
            trade_date="2026-04-09",
            snapshots=[
                YieldCurveSnapshot(
                    curve_type="treasury",
                    trade_date="2026-04-09",
                    points=common,
                    vendor_name="t",
                    vendor_version="vv_a",
                    source_version="sv_a",
                ),
            ],
            rule_version="rv_term_test",
        )
        repo.replace_curve_snapshots(
            trade_date="2026-04-10",
            snapshots=[
                YieldCurveSnapshot(
                    curve_type="treasury",
                    trade_date="2026-04-10",
                    points=[
                        YieldCurvePoint("1Y", Decimal("1.10")),
                        YieldCurvePoint("10Y", Decimal("2.05")),
                    ],
                    vendor_name="t",
                    vendor_version="vv_b",
                    source_version="sv_b",
                ),
            ],
            rule_version="rv_term_test",
        )


def _seed_low_rate_treasury_curve(duckdb_path: str) -> None:
    repo = YieldCurveRepository(duckdb_path)
    with repository_task_write_scope("backend.app.tasks.yield_curve_term_structure_api_test"):
        repo.replace_curve_snapshots(
            trade_date="2026-04-08",
            snapshots=[
                YieldCurveSnapshot(
                    curve_type="treasury",
                    trade_date="2026-04-08",
                    points=[
                        YieldCurvePoint("1Y", Decimal("0.80")),
                        YieldCurvePoint("10Y", Decimal("1.00")),
                    ],
                    vendor_name="t",
                    vendor_version="vv_low",
                    source_version="sv_low",
                ),
            ],
            rule_version="rv_term_test",
        )


def _seed_curve_types_by_date(
    duckdb_path: str,
    curve_types_by_date: dict[str, tuple[str, ...]],
) -> None:
    repo = YieldCurveRepository(duckdb_path)
    with repository_task_write_scope("backend.app.tasks.yield_curve_term_structure_api_test"):
        for trade_date, curve_types in curve_types_by_date.items():
            repo.replace_curve_snapshots(
                trade_date=trade_date,
                snapshots=[
                    YieldCurveSnapshot(
                        curve_type=curve_type,
                        trade_date=trade_date,
                        points=[
                            YieldCurvePoint("1Y", Decimal("2.00")),
                            YieldCurvePoint("10Y", Decimal("2.50")),
                        ],
                        vendor_name="t",
                        vendor_version=f"vv_{curve_type}_{trade_date}",
                        source_version=f"sv_{curve_type}_{trade_date}",
                    )
                    for curve_type in curve_types
                ],
                rule_version="rv_term_test",
            )


def _grant_bond_analytics_read_scope(tmp_path, monkeypatch) -> None:
    sqlite_path = tmp_path / "bond-analytics-read-scope.db"
    scope_dsn = f"sqlite:///{sqlite_path.as_posix()}"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", scope_dsn)
    monkeypatch.setenv("MOSS_GOVERNANCE_SQL_DSN", scope_dsn)
    UserScopeRepository(scope_dsn).grant_scope(
        user_id="*",
        role=None,
        resource="bond_analytics",
        action="read",
    )


def _get_term_structure_payload(
    tmp_path,
    monkeypatch,
    *,
    database_name: str,
    curve_types_by_date: dict[str, tuple[str, ...]],
    requested_date: str,
    requested_curve_types: str,
) -> dict:
    duckdb_path = tmp_path / database_name
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    _grant_bond_analytics_read_scope(tmp_path, monkeypatch)
    get_settings.cache_clear()
    try:
        _seed_curve_types_by_date(str(duckdb_path), curve_types_by_date)
        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        response = client.get(
            "/api/bond-analytics/yield-curve-term-structure",
            params={
                "report_date": requested_date,
                "curve_types": requested_curve_types,
            },
        )
        assert response.status_code == 200, response.text
        return response.json()
    finally:
        get_settings.cache_clear()


def test_yield_curve_term_structure_points_order_and_delta_bp(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "curve.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    _grant_bond_analytics_read_scope(tmp_path, monkeypatch)
    get_settings.cache_clear()
    try:
        _seed_two_day_treasury_curve(str(duckdb_path))
        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        response = client.get(
            "/api/bond-analytics/yield-curve-term-structure",
            params={"report_date": "2026-04-10", "curve_types": "treasury"},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["result_meta"]["result_kind"] == "bond_analytics.yield_curve_term_structure"
        result = payload["result"]
        assert result["report_date"] == "2026-04-10"
        curves = result["curves"]
        assert len(curves) == 1
        c0 = curves[0]
        assert c0["curve_type"] == "treasury"
        assert c0["trade_date_resolved"] == "2026-04-10"
        tenors = [p["tenor"] for p in c0["points"]]
        assert tenors == list(YIELD_CURVE_TERM_STRUCTURE_TENORS)
        by_tenor = {p["tenor"]: p for p in c0["points"]}
        assert by_tenor["1Y"]["delta_bp_prev"]["raw"] == 10.0
        assert by_tenor["10Y"]["delta_bp_prev"]["raw"] == 5.0
        assert by_tenor["2Y"]["yield_pct"] is None
    finally:
        get_settings.cache_clear()


def test_yield_curve_term_structure_normalizes_sub_one_percent_rates(
    tmp_path, monkeypatch
) -> None:
    duckdb_path = tmp_path / "curve_low.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    _grant_bond_analytics_read_scope(tmp_path, monkeypatch)
    get_settings.cache_clear()
    try:
        _seed_low_rate_treasury_curve(str(duckdb_path))
        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        response = client.get(
            "/api/bond-analytics/yield-curve-term-structure",
            params={"report_date": "2026-04-08", "curve_types": "treasury"},
        )
        assert response.status_code == 200, response.text
        points = {
            point["tenor"]: point
            for point in response.json()["result"]["curves"][0]["points"]
        }
        assert points["1Y"]["yield_pct"]["raw"] == 0.008
        assert points["1Y"]["yield_pct"]["display"] == "+0.80%"
        assert points["10Y"]["yield_pct"]["raw"] == 0.01
        assert points["10Y"]["yield_pct"]["display"] == "+1.00%"
    finally:
        get_settings.cache_clear()


def test_yield_curve_term_structure_fallback_warning(tmp_path, monkeypatch) -> None:
    duckdb_path = tmp_path / "curve2.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    _grant_bond_analytics_read_scope(tmp_path, monkeypatch)
    get_settings.cache_clear()
    try:
        _seed_two_day_treasury_curve(str(duckdb_path))
        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        response = client.get(
            "/api/bond-analytics/yield-curve-term-structure",
            params={"report_date": "2026-04-11", "curve_types": "treasury"},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["result_meta"]["fallback_mode"] == "latest_snapshot"
        assert payload["result_meta"]["vendor_status"] == "vendor_stale"
        warnings = " ".join(payload["result"]["warnings"])
        assert YIELD_CURVE_LATEST_FALLBACK_PREFIX in warnings
        assert payload["result"]["curves"][0]["trade_date_resolved"] == "2026-04-10"
    finally:
        get_settings.cache_clear()


def test_yield_curve_term_structure_marks_mixed_resolved_dates_in_meta(
    tmp_path, monkeypatch
) -> None:
    payload = _get_term_structure_payload(
        tmp_path,
        monkeypatch,
        database_name="curve_mixed.duckdb",
        curve_types_by_date={
            "2026-04-09": ("cdb",),
            "2026-04-10": ("treasury",),
        },
        requested_date="2026-04-10",
        requested_curve_types="treasury,cdb",
    )

    meta = payload["result_meta"]
    assert meta["requested_report_date"] == "2026-04-10"
    assert meta["resolved_report_date"] is None
    assert meta["as_of_date"] is None
    assert meta["date_basis"] == "yield_curve_trade_date_per_curve"
    assert meta["fallback_date"] is None
    assert meta["fallback_mode"] == "latest_snapshot"
    assert meta["vendor_status"] == "vendor_stale"
    resolved_by_type = {
        curve["curve_type"]: curve["trade_date_resolved"]
        for curve in payload["result"]["curves"]
    }
    assert resolved_by_type == {"treasury": "2026-04-10", "cdb": "2026-04-09"}


def test_yield_curve_term_structure_sets_shared_fallback_date_in_meta(
    tmp_path, monkeypatch
) -> None:
    payload = _get_term_structure_payload(
        tmp_path,
        monkeypatch,
        database_name="curve_shared_fallback.duckdb",
        curve_types_by_date={"2026-04-10": ("treasury", "cdb")},
        requested_date="2026-04-11",
        requested_curve_types="treasury,cdb",
    )

    meta = payload["result_meta"]
    assert meta["requested_report_date"] == "2026-04-11"
    assert meta["resolved_report_date"] == "2026-04-10"
    assert meta["as_of_date"] == "2026-04-10"
    assert meta["date_basis"] == "yield_curve_trade_date_shared"
    assert meta["fallback_date"] == "2026-04-10"
    assert meta["fallback_mode"] == "latest_snapshot"
    assert meta["vendor_status"] == "vendor_stale"


def test_yield_curve_term_structure_marks_partial_missing_vendor_unavailable(
    tmp_path, monkeypatch
) -> None:
    payload = _get_term_structure_payload(
        tmp_path,
        monkeypatch,
        database_name="curve_partial_missing.duckdb",
        curve_types_by_date={"2026-04-10": ("treasury",)},
        requested_date="2026-04-10",
        requested_curve_types="treasury,cdb",
    )

    meta = payload["result_meta"]
    assert meta["requested_report_date"] == "2026-04-10"
    assert meta["resolved_report_date"] is None
    assert meta["as_of_date"] is None
    assert meta["date_basis"] == "yield_curve_trade_date_per_curve"
    assert meta["fallback_date"] is None
    assert meta["fallback_mode"] == "none"
    assert meta["vendor_status"] == "vendor_unavailable"
    assert meta["quality_flag"] == "warning"
    resolved_by_type = {
        curve["curve_type"]: curve["trade_date_resolved"]
        for curve in payload["result"]["curves"]
    }
    assert resolved_by_type == {"treasury": "2026-04-10", "cdb": None}


def test_yield_curve_repo_fetches_tenor_on_or_before_many(tmp_path) -> None:
    duckdb_path = tmp_path / "curve_batch.duckdb"
    _seed_two_day_treasury_curve(str(duckdb_path))

    repo = YieldCurveRepository(str(duckdb_path))
    values = repo.fetch_tenor_on_or_before_many(
        curve_type="treasury",
        tenor="10Y",
        trade_dates=["2026-04-10", "2026-04-11", "2026-04-08"],
    )

    assert values["2026-04-10"] == (Decimal("2.05"), "2026-04-10")
    assert values["2026-04-11"] == (Decimal("2.05"), "2026-04-10")
    assert values["2026-04-08"] == (None, None)


def test_yield_curve_term_structure_invalid_curve_type_400(tmp_path, monkeypatch) -> None:
    _grant_bond_analytics_read_scope(tmp_path, monkeypatch)
    get_settings.cache_clear()
    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    try:
        response = client.get(
            "/api/bond-analytics/yield-curve-term-structure",
            params={"report_date": "2026-04-10", "curve_types": "foo"},
        )
        assert response.status_code == 400
    finally:
        get_settings.cache_clear()
