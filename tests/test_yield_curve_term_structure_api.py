"""API + shape tests for formal yield-curve term-structure ladder."""
from __future__ import annotations

from decimal import Decimal
from datetime import date
from types import SimpleNamespace

import pytest
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


def _term_structure_refresh_fixture(tmp_path, monkeypatch):
    from backend.app.services.runtime_cache import InMemoryTTLCache

    service = load_module(
        "tests._term_structure_refresh",
        "backend/app/services/yield_curve_term_structure_service.py",
    )
    database = tmp_path / "cache-identity.duckdb"
    database.write_bytes(b"synthetic cache identity")
    selected = tmp_path / "selected-cache-identity.duckdb"
    selected.write_bytes(b"synthetic selected identity")
    state = {"time": 0.0, "builds": 0, "hook": None, "path": str(database),
             "selected": str(database), "scope": 1}
    monkeypatch.setattr(service, "get_settings", lambda: SimpleNamespace(duckdb_path=state["path"]))
    monkeypatch.setattr(service, "resolve_effective_read_path", lambda _path: state["selected"], raising=False)
    from backend.app.services import runtime_cache

    def identity(key):
        return ("test-scope", state["scope"], key)

    monkeypatch.setattr(runtime_cache, "system_read_cache_identity", identity)
    monkeypatch.setattr(service, "system_read_cache_identity", identity, raising=False)
    cache = InMemoryTTLCache(ttl_seconds=300, clock=lambda: state["time"])
    monkeypatch.setattr(service, "_TERM_STRUCTURE_CACHE", cache)

    def compute(**_kwargs):
        state["builds"] += 1
        result = {"result_meta": {"trace_id": "builder-trace"}, "result": {"build": state["builds"]}}
        if state["hook"]:
            state["hook"]()
        return result

    monkeypatch.setattr(service, "_compute_yield_curve_term_structure", compute)
    return service, state, database, selected


def test_term_structure_force_refresh_renews_expiry_and_retains_current_hit(tmp_path, monkeypatch):
    service, state, _database, _selected = _term_structure_refresh_fixture(tmp_path, monkeypatch)
    kwargs = {"report_date": date(2026, 4, 10), "curve_types": ("treasury", "cdb")}
    first = service.get_yield_curve_term_structure(**kwargs)
    assert service.get_yield_curve_term_structure(**kwargs)["result"] == first["result"]
    assert state["builds"] == 1
    state["time"] = 240

    def read_existing():
        assert service.get_yield_curve_term_structure(**kwargs)["result"] == first["result"]

    state["hook"] = read_existing
    refreshed = service.get_yield_curve_term_structure(**kwargs, force_refresh=True)
    assert refreshed["result"]["build"] == 2
    state["hook"] = None
    state["time"] = 301
    assert service.get_yield_curve_term_structure(**kwargs)["result"] == refreshed["result"]
    assert state["builds"] == 2
    state["time"] = 541
    assert service.get_yield_curve_term_structure(**kwargs)["result"]["build"] == 3


def test_term_structure_force_refresh_failure_preserves_cached_result(tmp_path, monkeypatch):
    service, state, _database, _selected = _term_structure_refresh_fixture(tmp_path, monkeypatch)
    kwargs = {"report_date": date(2026, 4, 10), "curve_types": ("treasury",)}
    first = service.get_yield_curve_term_structure(**kwargs)
    state["hook"] = lambda: (_ for _ in ()).throw(RuntimeError("refresh failed"))
    with pytest.raises(RuntimeError, match="refresh failed"):
        service.get_yield_curve_term_structure(**kwargs, force_refresh=True)
    assert service.get_yield_curve_term_structure(**kwargs)["result"] == first["result"]


@pytest.mark.parametrize("change", ["generation", "database", "path", "selected", "selected-file", "scope"])
def test_term_structure_force_refresh_does_not_refill_changed_identity(tmp_path, monkeypatch, change):
    service, state, database, selected = _term_structure_refresh_fixture(tmp_path, monkeypatch)
    kwargs = {"report_date": date(2026, 4, 10), "curve_types": ("treasury",)}
    first = service.get_yield_curve_term_structure(**kwargs)
    cache = service._TERM_STRUCTURE_CACHE
    original_key = next(iter(cache._store))

    def invalidate():
        if change == "generation":
            cache.clear()
        elif change == "database":
            database.write_bytes(b"changed synthetic database identity")
        elif change == "selected-file":
            # Keep the configured database unchanged; the effective read file
            # alone changes while the forced producer is running.
            selected.write_bytes(b"changed selected identity")
        elif change == "scope":
            state["scope"] += 1
        else:
            state[change] = str(selected)

    if change == "selected-file":
        state["selected"] = str(selected)
    state["hook"] = invalidate
    refreshed = service.get_yield_curve_term_structure(**kwargs, force_refresh=True)
    assert refreshed["result"]["build"] == 2
    state["hook"] = None
    if change == "generation":
        assert cache._store == {}
        assert service.get_yield_curve_term_structure(**kwargs)["result"]["build"] == 3
    else:
        assert cache._store[original_key][1]["result"] == first["result"]
        assert all(entry[1]["result"] != refreshed["result"] for entry in cache._store.values())


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


def test_yield_curve_term_structure_sub_one_percent_yield_is_percent_points(tmp_path, monkeypatch) -> None:
    """A 0.85 rate_pct means 0.85% — pct raw must be 0.0085, not 0.85 (85%)."""
    duckdb_path = tmp_path / "curve_low_rate.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    _grant_bond_analytics_read_scope(tmp_path, monkeypatch)
    get_settings.cache_clear()
    try:
        repo = YieldCurveRepository(str(duckdb_path))
        with repository_task_write_scope("backend.app.tasks.yield_curve_term_structure_api_test"):
            repo.replace_curve_snapshots(
                trade_date="2026-04-10",
                snapshots=[
                    YieldCurveSnapshot(
                        curve_type="treasury",
                        trade_date="2026-04-10",
                        points=[
                            YieldCurvePoint("1Y", Decimal("0.85")),
                            YieldCurvePoint("10Y", Decimal("2.05")),
                        ],
                        vendor_name="t",
                        vendor_version="vv_low",
                        source_version="sv_low",
                    ),
                ],
                rule_version="rv_term_test",
            )
        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        response = client.get(
            "/api/bond-analytics/yield-curve-term-structure",
            params={"report_date": "2026-04-10", "curve_types": "treasury"},
        )
        assert response.status_code == 200, response.text
        by_tenor = {p["tenor"]: p for p in response.json()["result"]["curves"][0]["points"]}
        assert by_tenor["1Y"]["yield_pct"]["raw"] == pytest.approx(0.0085)
        assert by_tenor["1Y"]["yield_pct"]["display"] == "+0.85%"
        assert by_tenor["10Y"]["yield_pct"]["raw"] == pytest.approx(0.0205)
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
    # Mainline contract: divergent per-curve days never invent a unified
    # envelope date, and this endpoint does not emit date_basis.
    assert meta.get("date_basis") in (None, "")
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
    assert meta.get("date_basis") in (None, "")
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
    # Mainline date contract unifies over the non-missing curves' resolved
    # day; the missing cdb curve is surfaced via vendor_unavailable + warning.
    assert meta["resolved_report_date"] == "2026-04-10"
    assert meta["as_of_date"] == "2026-04-10"
    assert meta.get("date_basis") in (None, "")
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


def test_yield_curve_term_structure_result_meta_dates_exact_no_fallback(tmp_path, monkeypatch) -> None:
    """Exact trade_date hit: envelope dates mirror the shared resolved day; no fallback_date."""
    duckdb_path = tmp_path / "curve_meta_exact.duckdb"
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
        meta = response.json()["result_meta"]
        assert meta["requested_report_date"] == "2026-04-10"
        assert meta["resolved_report_date"] == "2026-04-10"
        assert meta["as_of_date"] == "2026-04-10"
        assert meta["fallback_date"] is None
        assert meta["fallback_mode"] == "none"
        assert meta["vendor_status"] == "ok"
        assert meta["quality_flag"] == "ok"
        assert meta.get("date_basis") in (None, "")
    finally:
        get_settings.cache_clear()


def test_yield_curve_term_structure_result_meta_dates_single_curve_latest_snapshot(
    tmp_path, monkeypatch
) -> None:
    """Single-curve latest_snapshot: unified resolved/as_of/fallback_date = trade_date_resolved."""
    duckdb_path = tmp_path / "curve_meta_fb.duckdb"
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
        meta = payload["result_meta"]
        assert payload["result"]["curves"][0]["trade_date_resolved"] == "2026-04-10"
        assert meta["requested_report_date"] == "2026-04-11"
        assert meta["resolved_report_date"] == "2026-04-10"
        assert meta["as_of_date"] == "2026-04-10"
        assert meta["fallback_date"] == "2026-04-10"
        assert meta["fallback_mode"] == "latest_snapshot"
        assert meta["vendor_status"] == "vendor_stale"
        assert meta["quality_flag"] == "stale"
        assert meta.get("date_basis") in (None, "")
    finally:
        get_settings.cache_clear()


def test_yield_curve_term_structure_result_meta_dates_multi_curve_divergent_no_fabricated_fallback(
    tmp_path, monkeypatch
) -> None:
    """Divergent per-curve trade_date_resolved must not invent one envelope fallback_date.

    Contract gate (docs/plans/2026-07-19-frontend-audit-round3-optimization.md Task 1;
    docs/plans/2026-07-18-development-issue-remediation.md Task 6; docs/page_contracts.md
    §4.2 requested/resolved + MacroToolkit §D analogue: do not merge unequal block dates):
    rely on per-curve trade_date_resolved + envelope fallback_mode/quality_flag.
    """
    duckdb_path = tmp_path / "curve_meta_divergent.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "gov"))
    _grant_bond_analytics_read_scope(tmp_path, monkeypatch)
    get_settings.cache_clear()
    try:
        repo = YieldCurveRepository(str(duckdb_path))
        with repository_task_write_scope("backend.app.tasks.yield_curve_term_structure_api_test"):
            repo.replace_curve_snapshots(
                trade_date="2026-04-09",
                snapshots=[
                    YieldCurveSnapshot(
                        curve_type="cdb",
                        trade_date="2026-04-09",
                        points=[
                            YieldCurvePoint("1Y", Decimal("1.50")),
                            YieldCurvePoint("10Y", Decimal("2.50")),
                        ],
                        vendor_name="c",
                        vendor_version="vv_cdb",
                        source_version="sv_cdb",
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
                        vendor_version="vv_t",
                        source_version="sv_t",
                    ),
                ],
                rule_version="rv_term_test",
            )
        client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
        response = client.get(
            "/api/bond-analytics/yield-curve-term-structure",
            params={"report_date": "2026-04-11", "curve_types": "treasury,cdb"},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        curves = {c["curve_type"]: c for c in payload["result"]["curves"]}
        assert curves["treasury"]["trade_date_resolved"] == "2026-04-10"
        assert curves["cdb"]["trade_date_resolved"] == "2026-04-09"
        meta = payload["result_meta"]
        assert meta["requested_report_date"] == "2026-04-11"
        # Do not pick either curve's day as a fabricated unified envelope date.
        assert meta["resolved_report_date"] is None
        assert meta["as_of_date"] is None
        assert meta["fallback_date"] is None
        assert meta["fallback_mode"] == "latest_snapshot"
        assert meta["vendor_status"] == "vendor_stale"
        assert meta["quality_flag"] == "stale"
        assert meta.get("date_basis") in (None, "")
    finally:
        get_settings.cache_clear()
