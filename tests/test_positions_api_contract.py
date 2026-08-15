"""Contract tests for positions HTTP API (envelope + snapshot read behaviors)."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module

POSITIONS_READ_HEADERS = {"X-User-Id": "positions-read-user", "X-User-Role": "viewer"}


def _grant_positions_read_scope(*, settings, user_id: str = "*") -> None:
    repo_module = load_module(
        "backend.app.repositories.user_scope_repo",
        "backend/app/repositories/user_scope_repo.py",
    )
    repo_module.UserScopeRepository(settings.governance_sql_dsn or settings.postgres_dsn).grant_scope(
        user_id=user_id,
        role=None,
        resource="positions",
        action="read",
    )


def _enable_positions_read_scope(tmp_path: Path, monkeypatch) -> None:
    sqlite_path = tmp_path / "positions-read-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    _grant_positions_read_scope(settings=get_settings())


def _positions_app_client() -> TestClient:
    return TestClient(load_module("backend.app.main", "backend/app/main.py").app)


def _authorized_positions_client(tmp_path: Path, monkeypatch) -> TestClient:
    _enable_positions_read_scope(tmp_path, monkeypatch)
    return _positions_app_client()


def _configure_positions_scope_store(tmp_path: Path, monkeypatch, *, grant_read: bool) -> None:
    sqlite_path = tmp_path / "positions-read-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    if grant_read:
        _grant_positions_read_scope(settings=get_settings())


def _positions_client(tmp_path: Path, monkeypatch, *, grant_read: bool = True) -> TestClient:
    _configure_positions_scope_store(tmp_path, monkeypatch, grant_read=grant_read)
    return _positions_app_client()


def _ensure_tables(conn: duckdb.DuckDBPyConnection) -> None:
    snapshot_mod = load_module(
        "backend.app.repositories.snapshot_repo",
        "backend/app/repositories/snapshot_repo.py",
    )
    snapshot_mod.ensure_snapshot_tables(conn)


def _insert_zqtz(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    instrument_code: str,
    bond_type: str,
    issuer_name: str,
    market_value: Decimal,
    ytm: Decimal | None,
    coupon: Decimal | None,
    is_issuance_like: bool,
    face_value: Decimal | None = None,
    amortized_cost: Decimal | None = None,
    rating: str = "AAA",
    industry: str = "閾惰",
) -> None:
    conn.execute(
        """
        insert into zqtz_bond_daily_snapshot (
          report_date, instrument_code, instrument_name, portfolio_name, cost_center,
          account_category, asset_class, bond_type, issuer_name, industry_name, rating,
          currency_code, face_value_native, market_value_native, amortized_cost_native,
          accrued_interest_native, coupon_rate, ytm_value, maturity_date, next_call_date,
          overdue_days, is_issuance_like, interest_mode, source_version, rule_version,
          ingest_batch_id, trace_id
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            report_date,
            instrument_code,
            instrument_code,
            "p1",
            "cc1",
            "cat",
            "bond-asset-class",
            bond_type,
            issuer_name,
            industry,
            rating,
            "CNY",
            face_value if face_value is not None else market_value,
            market_value,
            amortized_cost if amortized_cost is not None else market_value,
            Decimal("0"),
            coupon,
            ytm,
            "2030-01-01",
            None,
            0,
            is_issuance_like,
            "鍥哄畾",
            "sv-pos-test",
            "rv-pos-test",
            "ib-pos",
            "tr-pos",
        ],
    )


def _insert_tyw(
    conn: duckdb.DuckDBPyConnection,
    *,
    report_date: str,
    position_id: str,
    product_type: str,
    position_side: str,
    counterparty: str,
    principal: Decimal,
    rate: Decimal | None,
) -> None:
    conn.execute(
        """
        insert into tyw_interbank_daily_snapshot (
          report_date, position_id, product_type, position_side, counterparty_name,
          account_type, special_account_type, core_customer_type, currency_code,
          principal_native, accrued_interest_native, funding_cost_rate, maturity_date,
          pledged_bond_code, source_version, rule_version, ingest_batch_id, trace_id
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            report_date,
            position_id,
            product_type,
            position_side,
            counterparty,
            "a",
            "s",
            "c",
            "CNY",
            principal,
            Decimal("0"),
            rate,
            "2030-06-01",
            None,
            "sv-pos-tyw",
            "rv-pos-test",
            "ib-pos-t",
            "tr-pos-t",
        ],
    )


def _seed_positions_db(path: Path) -> None:
    # zqtz 快照的 ytm_value / coupon_rate 落库为百分数口径（3.0 = 3%），与
    # rate_units.normalize_percent_rate_to_decimal 的取证裁决一致。
    conn = duckdb.connect(str(path), read_only=False)
    try:
        _ensure_tables(conn)
        conn.execute("delete from zqtz_bond_daily_snapshot")
        conn.execute("delete from tyw_interbank_daily_snapshot")
        _insert_zqtz(
            conn,
            report_date="2026-01-10",
            instrument_code="B001",
            bond_type="GOV",
            issuer_name="发行人甲",
            market_value=Decimal("100"),
            ytm=Decimal("3.0"),
            coupon=Decimal("2.5"),
            is_issuance_like=False,
        )
        _insert_zqtz(
            conn,
            report_date="2026-01-12",
            instrument_code="B001",
            bond_type="GOV",
            issuer_name="发行人甲",
            market_value=Decimal("120"),
            ytm=Decimal("3.1"),
            coupon=Decimal("2.5"),
            is_issuance_like=False,
        )
        _insert_zqtz(
            conn,
            report_date="2026-01-10",
            instrument_code="B002",
            bond_type="CREDIT",
            issuer_name="发行人乙",
            market_value=Decimal("200"),
            ytm=Decimal("4.0"),
            coupon=Decimal("3.5"),
            is_issuance_like=True,
        )
        _insert_zqtz(
            conn,
            report_date="2026-01-10",
            instrument_code="B003",
            bond_type="CREDIT",
            issuer_name="发行人乙",
            market_value=Decimal("50"),
            ytm=Decimal("4.5"),
            coupon=Decimal("4.0"),
            is_issuance_like=False,
        )
        _insert_tyw(
            conn,
            report_date="2026-01-10",
            position_id="T1",
            product_type="REPO",
            position_side="Asset",
            counterparty="CP_ASSET",
            principal=Decimal("1000"),
            rate=Decimal("0.02"),
        )
        _insert_tyw(
            conn,
            report_date="2026-01-12",
            position_id="T2",
            product_type="REPO",
            position_side="Liability",
            counterparty="CP_LIAB",
            principal=Decimal("500"),
            rate=Decimal("0.025"),
        )
    finally:
        conn.close()


def _assert_envelope(payload: dict[str, Any], *, result_kind: str) -> None:
    assert "result_meta" in payload
    assert "result" in payload
    meta = payload["result_meta"]
    for key in ("trace_id", "basis", "source_version", "rule_version", "cache_version", "result_kind"):
        assert key in meta, f"result_meta missing {key!r}"
        assert meta[key] not in (None, ""), f"result_meta.{key} must be non-empty"
    # 快照聚合面无正式化批准记录（docs/metric_dictionary.md：positions 仅
    # MTR-POS-001/002 candidate，"列表与统计 DTO 未升为 MTR-*"，GAP-POS-LIST 开放），
    # 与列表端点一致锁定 analytical 候选语义。
    assert meta["basis"] == "analytical"
    assert meta["formal_use_allowed"] is False
    assert meta["scenario_flag"] is False
    assert meta["quality_flag"] == "warning"
    assert meta["result_kind"] == result_kind


def _assert_candidate_list_envelope(
    payload: dict[str, Any],
    *,
    result_kind: str,
    report_date: str,
    table_name: str,
    evidence_rows: int,
) -> None:
    _assert_envelope_shape(payload, result_kind=result_kind)
    meta = payload["result_meta"]
    assert meta["basis"] == "analytical"
    assert meta["formal_use_allowed"] is False
    assert meta["scenario_flag"] is False
    assert meta["quality_flag"] == "warning"
    assert meta["requested_report_date"] == report_date
    assert meta["resolved_report_date"] == report_date
    assert meta["as_of_date"] == report_date
    assert meta["date_basis"] == "positions_snapshot_report_date"
    assert meta["filters_applied"]["report_date"] == report_date
    assert meta["tables_used"] == [table_name]
    assert meta["evidence_rows"] == evidence_rows


def _assert_envelope_shape(payload: dict[str, Any], *, result_kind: str) -> None:
    assert "result_meta" in payload
    assert "result" in payload
    meta = payload["result_meta"]
    for key in ("trace_id", "basis", "source_version", "rule_version", "cache_version", "result_kind"):
        assert key in meta, f"result_meta missing {key!r}"
        assert meta[key] not in (None, ""), f"result_meta.{key} must be non-empty"
    assert meta["result_kind"] == result_kind


def test_positions_read_surfaces_require_explicit_read_scope(tmp_path, monkeypatch) -> None:
    db = tmp_path / "pos.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = _positions_client(tmp_path, monkeypatch, grant_read=False)

    read_requests = (
        ("/api/positions/bonds/sub_types", {"report_date": "2026-01-10"}),
        ("/api/positions/bonds", {"report_date": "2026-01-10", "page": 1, "page_size": 10}),
        (
            "/api/positions/counterparty/bonds",
            {"start_date": "2026-01-01", "end_date": "2026-01-31", "page": 1, "page_size": 10},
        ),
        ("/api/positions/interbank/product_types", {"report_date": "2026-01-10"}),
        ("/api/positions/interbank", {"report_date": "2026-01-10", "page": 1, "page_size": 10}),
        (
            "/api/positions/counterparty/interbank/split",
            {"start_date": "2026-01-01", "end_date": "2026-01-31"},
        ),
        ("/api/positions/stats/rating", {"start_date": "2026-01-01", "end_date": "2026-01-31"}),
        ("/api/positions/stats/industry", {"start_date": "2026-01-01", "end_date": "2026-01-31"}),
        ("/api/positions/customer/details", {"customer_name": "发行人甲", "report_date": "2026-01-10"}),
        ("/api/positions/customer/trend", {"customer_name": "发行人甲", "end_date": "2026-01-10"}),
    )

    for path, params in read_requests:
        response = client.get(path, params=params, headers=POSITIONS_READ_HEADERS)
        assert response.status_code == 403, f"{path}: {response.status_code} {response.text}"


def test_positions_envelope_runtime_cache_reuses_result_with_fresh_trace(
    tmp_path, monkeypatch
) -> None:
    """同参重复调用只算一次（TTL 缓存命中），但每次响应刷新 trace_id。

    与 balance_analysis.read_models 同款：键含 DuckDB 文件身份，文件变更自然失效。
    """
    from backend.app.services.runtime_cache import clear_runtime_cache

    svc = load_module(
        "backend.app.services.positions_service",
        "backend/app/services/positions_service.py",
    )
    clear_runtime_cache("positions.read_models")
    db = tmp_path / "positions-cache.duckdb"
    db.write_bytes(b"")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    get_settings.cache_clear()

    calls = {"n": 0}

    class _StubRepo:
        def list_bond_sub_types(self, report_date: str) -> list[str]:
            calls["n"] += 1
            return ["利率债"]

        def collect_lineage_versions(self, **_kwargs: object) -> tuple[list[str], list[str]]:
            return (["sv_stub"], ["rv_stub"])

    monkeypatch.setattr(svc, "_repo", lambda: _StubRepo())

    first = svc.bond_sub_types_envelope("2026-01-10")
    second = svc.bond_sub_types_envelope("2026-01-10")
    assert calls["n"] == 1, "同参第二次调用应命中缓存，不再触发仓储查询"
    assert first["result"] == second["result"]
    assert first["result_meta"]["trace_id"] != second["result_meta"]["trace_id"]
    meta_first = {k: v for k, v in first["result_meta"].items() if k != "trace_id"}
    meta_second = {k: v for k, v in second["result_meta"].items() if k != "trace_id"}
    assert meta_first == meta_second

    svc.bond_sub_types_envelope("2026-01-11")
    assert calls["n"] == 2, "不同参数是不同缓存键"
    clear_runtime_cache("positions.read_models")


def test_positions_read_surface_allows_development_fallback_without_explicit_scope(
    tmp_path, monkeypatch
) -> None:
    """development 环境 + 匿名 viewer 回退身份可读（与 balance_analysis 读路由对齐）。

    显式头部身份缺 scope 时仍 403，由上面的契约测试锁定。
    """
    route_mod = load_module(
        "backend.app.api.routes.positions",
        "backend/app/api/routes/positions.py",
    )
    monkeypatch.setattr(
        route_mod.positions_service,
        "bond_sub_types_envelope",
        lambda report_date: {
            "result_meta": {"result_kind": "positions.bonds.sub_types"},
            "result": {"sub_types": []},
        },
    )
    sqlite_path = tmp_path / "positions-dev-fallback.db"
    monkeypatch.setenv("MOSS_ENVIRONMENT", "development")
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv("MOSS_GOVERNANCE_SQL_DSN", "")
    monkeypatch.delenv("MOSS_USER_ID", raising=False)
    monkeypatch.delenv("MOSS_USER_ROLE", raising=False)
    monkeypatch.delenv(ROLE_HEADER_TRUST_ENV, raising=False)
    get_settings.cache_clear()
    app = FastAPI()
    app.include_router(route_mod.router)
    client = TestClient(app)

    response = client.get("/api/positions/bonds/sub_types")

    assert response.status_code == 200
    assert response.json()["result_meta"]["result_kind"] == "positions.bonds.sub_types"


def test_positions_endpoints_envelope_and_empty_db(tmp_path, monkeypatch) -> None:
    db = tmp_path / "pos.duckdb"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = _authorized_positions_client(tmp_path, monkeypatch)

    r = client.get("/api/positions/bonds/sub_types", params={"report_date": "2026-01-10"})
    assert r.status_code == 200
    _assert_envelope(r.json(), result_kind="positions.bonds.sub_types")
    assert r.json()["result"]["sub_types"] == []

    r2 = client.get(
        "/api/positions/bonds",
        params={"report_date": "2026-01-10", "sub_type": "GOV", "page": 1, "page_size": 10},
    )
    assert r2.status_code == 200
    _assert_candidate_list_envelope(
        r2.json(),
        result_kind="positions.bonds.list",
        report_date="2026-01-10",
        table_name="zqtz_bond_daily_snapshot",
        evidence_rows=0,
    )
    assert r2.json()["result"]["items"] == []
    assert r2.json()["result"]["total"] == 0


def test_positions_bonds_filters_issuance_and_pagination(tmp_path, monkeypatch) -> None:
    db = tmp_path / "pos.duckdb"
    _seed_positions_db(db)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = _authorized_positions_client(tmp_path, monkeypatch)

    sub = client.get("/api/positions/bonds/sub_types", params={"report_date": "2026-01-10"})
    assert sub.status_code == 200
    assert set(sub.json()["result"]["sub_types"]) == {"GOV", "CREDIT"}

    with_issued = client.get(
        "/api/positions/bonds",
        params={
            "report_date": "2026-01-10",
            "sub_type": "CREDIT",
            "page": 1,
            "page_size": 10,
            "include_issued": "true",
        },
    )
    assert with_issued.status_code == 200
    assert with_issued.json()["result"]["total"] == 2

    no_issued = client.get(
        "/api/positions/bonds",
        params={
            "report_date": "2026-01-10",
            "sub_type": "CREDIT",
            "page": 1,
            "page_size": 10,
        },
    )
    assert no_issued.status_code == 200
    assert no_issued.json()["result"]["total"] == 1
    assert no_issued.json()["result"]["items"][0]["bond_code"] == "B003"

    page2 = client.get(
        "/api/positions/bonds",
        params={
            "report_date": "2026-01-10",
            "sub_type": "GOV",
            "page": 2,
            "page_size": 1,
        },
    )
    assert page2.status_code == 200
    assert page2.json()["result"]["total"] == 1
    assert page2.json()["result"]["items"] == []


def test_positions_counterparty_and_interbank(tmp_path, monkeypatch) -> None:
    db = tmp_path / "pos.duckdb"
    _seed_positions_db(db)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = _authorized_positions_client(tmp_path, monkeypatch)

    cp = client.get(
        "/api/positions/counterparty/bonds",
        params={
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "sub_type": "GOV",
            "top_n": 10,
            "page": 1,
            "page_size": 10,
        },
    )
    assert cp.status_code == 200
    _assert_envelope(cp.json(), result_kind="positions.counterparty.bonds")
    body = cp.json()["result"]
    assert body["num_days"] == 2
    assert body["total_customers"] == 1
    assert len(body["items"]) == 1
    assert body["cr10_ratio"] == "100.00%"

    pt = client.get("/api/positions/interbank/product_types", params={"report_date": "2026-01-10"})
    assert pt.status_code == 200
    assert pt.json()["result"]["product_types"] == ["REPO"]

    ib = client.get(
        "/api/positions/interbank",
        params={
            "report_date": "2026-01-10",
            "product_type": "REPO",
            "direction": "Asset",
            "page": 1,
            "page_size": 10,
        },
    )
    assert ib.status_code == 200
    _assert_candidate_list_envelope(
        ib.json(),
        result_kind="positions.interbank.list",
        report_date="2026-01-10",
        table_name="tyw_interbank_daily_snapshot",
        evidence_rows=1,
    )
    assert ib.json()["result"]["total"] == 1
    assert ib.json()["result"]["items"][0]["direction"] == "Asset"

    split = client.get(
        "/api/positions/counterparty/interbank/split",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31", "product_type": "REPO"},
    )
    assert split.status_code == 200
    sp = split.json()["result"]
    assert sp["num_days"] == 2
    assert len(sp["asset_items"]) >= 1
    assert len(sp["liability_items"]) >= 1


def test_positions_counterparty_bonds_excludes_issuance_like_from_asset_scope(tmp_path, monkeypatch) -> None:
    db = tmp_path / "pos.duckdb"
    _seed_positions_db(db)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = _authorized_positions_client(tmp_path, monkeypatch)

    cp = client.get(
        "/api/positions/counterparty/bonds",
        params={
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "top_n": 10,
            "page": 1,
            "page_size": 10,
        },
    )
    assert cp.status_code == 200
    body = cp.json()["result"]

    assert body["total_amount"] == "270.00000000"
    assert body["total_avg_daily"] == "135.00000000"
    assert body["total_customers"] == 2
    items_by_customer = {item["customer_name"]: item for item in body["items"]}
    assert set(items_by_customer) == {"发行人甲", "发行人乙"}
    assert items_by_customer["发行人甲"]["total_amount"] == "220.00000000"
    assert items_by_customer["发行人乙"]["total_amount"] == "50.00000000"
    assert items_by_customer["发行人乙"]["avg_daily_balance"] == "25.00000000"
    assert body["cr10_ratio"] == "100.00%"


def test_positions_stats_rating_industry_customer(tmp_path, monkeypatch) -> None:
    db = tmp_path / "pos.duckdb"
    _seed_positions_db(db)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = _authorized_positions_client(tmp_path, monkeypatch)

    rt = client.get(
        "/api/positions/stats/rating",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31", "sub_type": "CREDIT"},
    )
    assert rt.status_code == 200
    assert rt.json()["result"]["items"]

    ind = client.get(
        "/api/positions/stats/industry",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31", "top_n": 5},
    )
    assert ind.status_code == 200
    assert ind.json()["result"]["items"]

    det = client.get(
        "/api/positions/customer/details",
        params={"customer_name": "发行人乙", "report_date": "2026-01-10"},
    )
    assert det.status_code == 200
    # B002 是发行腿（is_issuance_like），与聚合口径一致地从资产对手方钻取中排除。
    assert det.json()["result"]["bond_count"] == 1

    tr = client.get(
        "/api/positions/customer/trend",
        params={"customer_name": "发行人甲", "end_date": "2026-01-12", "days": 30},
    )
    assert tr.status_code == 200
    assert len(tr.json()["result"]["items"]) == 2



def test_positions_rating_and_industry_stats_exclude_issuance_like_from_asset_scope(tmp_path, monkeypatch) -> None:
    db = tmp_path / "pos.duckdb"
    conn = duckdb.connect(str(db), read_only=False)
    try:
        _ensure_tables(conn)
        conn.execute("delete from zqtz_bond_daily_snapshot")
        conn.execute("delete from tyw_interbank_daily_snapshot")
        _insert_zqtz(
            conn,
            report_date="2026-01-10",
            instrument_code="A001",
            bond_type="TEST",
            issuer_name="Issuer-Asset",
            market_value=Decimal("100"),
            ytm=Decimal("0.03"),
            coupon=Decimal("0.02"),
            is_issuance_like=False,
            rating="AAA",
            industry="Bank",
        )
        _insert_zqtz(
            conn,
            report_date="2026-01-11",
            instrument_code="A001",
            bond_type="TEST",
            issuer_name="Issuer-Asset",
            market_value=Decimal("120"),
            ytm=Decimal("0.031"),
            coupon=Decimal("0.02"),
            is_issuance_like=False,
            rating="AAA",
            industry="Bank",
        )
        _insert_zqtz(
            conn,
            report_date="2026-01-10",
            instrument_code="L001",
            bond_type="TEST",
            issuer_name="Issuer-Liability",
            market_value=Decimal("200"),
            ytm=Decimal("0.08"),
            coupon=Decimal("0.07"),
            is_issuance_like=True,
            rating="BBB",
            industry="Broker",
        )
    finally:
        conn.close()
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = _authorized_positions_client(tmp_path, monkeypatch)

    rating = client.get(
        "/api/positions/stats/rating",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31", "sub_type": "TEST"},
    )
    assert rating.status_code == 200
    rating_body = rating.json()["result"]
    assert rating_body["total_amount"] == "220.00000000"
    assert rating_body["total_avg_daily"] == "110.00000000"
    assert [item["rating"] for item in rating_body["items"]] == ["AAA"]
    assert rating_body["items"][0]["bond_count"] == 2

    industry = client.get(
        "/api/positions/stats/industry",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31", "sub_type": "TEST", "top_n": 5},
    )
    assert industry.status_code == 200
    industry_body = industry.json()["result"]
    assert industry_body["total_amount"] == "220.00000000"
    assert industry_body["total_avg_daily"] == "110.00000000"
    items_by_industry = {item["industry"]: item for item in industry_body["items"]}
    assert set(items_by_industry) == {"Bank"}
    assert items_by_industry["Bank"]["bond_count"] == 2

def test_positions_routes_registered() -> None:
    from backend.app.main import app

    paths = {getattr(r, "path", None) for r in app.routes}
    assert "/api/positions/bonds/sub_types" in paths
    assert "/api/positions/bonds" in paths
    assert "/api/positions/counterparty/bonds" in paths
    assert "/api/positions/interbank/product_types" in paths
    assert "/api/positions/interbank" in paths
    assert "/api/positions/counterparty/interbank/split" in paths
    assert "/api/positions/stats/rating" in paths
    assert "/api/positions/stats/industry" in paths
    assert "/api/positions/customer/details" in paths
    assert "/api/positions/customer/trend" in paths

def test_positions_rating_order_follows_business_priority_not_amount_order(tmp_path, monkeypatch) -> None:
    db = tmp_path / "pos.duckdb"
    conn = duckdb.connect(str(db), read_only=False)
    try:
        _ensure_tables(conn)
        conn.execute("delete from zqtz_bond_daily_snapshot")
        conn.execute("delete from tyw_interbank_daily_snapshot")
        _insert_zqtz(
            conn,
            report_date="2026-01-10",
            instrument_code="R1",
            bond_type="Credit",
            issuer_name="Issuer-AAA",
            market_value=Decimal("10"),
            ytm=Decimal("0.03"),
            coupon=Decimal("0.03"),
            is_issuance_like=False,
            rating="AAA",
        )
        _insert_zqtz(
            conn,
            report_date="2026-01-10",
            instrument_code="R2",
            bond_type="Credit",
            issuer_name="Issuer-AA",
            market_value=Decimal("200"),
            ytm=Decimal("0.04"),
            coupon=Decimal("0.04"),
            is_issuance_like=False,
            rating="AA",
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = _authorized_positions_client(tmp_path, monkeypatch)

    response = client.get(
        "/api/positions/stats/rating",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31", "sub_type": "Credit"},
    )
    assert response.status_code == 200
    items = response.json()["result"]["items"]
    assert [item["rating"] for item in items] == ["AAA", "AA"]


def test_positions_reads_normalize_percentage_rates_and_compute_net_price_from_market_over_face(
    tmp_path,
    monkeypatch,
) -> None:
    db = tmp_path / "pos.duckdb"
    conn = duckdb.connect(str(db), read_only=False)
    try:
        _ensure_tables(conn)
        conn.execute("delete from zqtz_bond_daily_snapshot")
        conn.execute("delete from tyw_interbank_daily_snapshot")
        _insert_zqtz(
            conn,
            report_date="2026-01-10",
            instrument_code="PX1",
            bond_type="Gov",
            issuer_name="Issuer-Gov",
            market_value=Decimal("120"),
            face_value=Decimal("100"),
            amortized_cost=Decimal("80"),
            ytm=Decimal("3.25"),
            coupon=Decimal("2.50"),
            is_issuance_like=False,
        )
        _insert_tyw(
            conn,
            report_date="2026-01-10",
            position_id="T100",
            product_type="IB",
            position_side="Asset",
            counterparty="CP-A",
            principal=Decimal("1000"),
            rate=Decimal("2.5"),
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = _authorized_positions_client(tmp_path, monkeypatch)

    bond_response = client.get(
        "/api/positions/bonds",
        params={"report_date": "2026-01-10", "sub_type": "Gov", "page": 1, "page_size": 10},
    )
    assert bond_response.status_code == 200
    bond_item = bond_response.json()["result"]["items"][0]
    assert bond_item["yield_rate"] == "0.03250000"
    assert bond_item["valuation_net_price"] == "120.00000000"

    rating_response = client.get(
        "/api/positions/stats/rating",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31", "sub_type": "Gov"},
    )
    assert rating_response.status_code == 200
    rating_item = rating_response.json()["result"]["items"][0]
    assert rating_item["weighted_rate"] == "0.03250000"

    counterparty_response = client.get(
        "/api/positions/counterparty/bonds",
        params={
            "start_date": "2026-01-01",
            "end_date": "2026-01-31",
            "sub_type": "Gov",
            "top_n": 10,
            "page": 1,
            "page_size": 10,
        },
    )
    assert counterparty_response.status_code == 200
    counterparty_body = counterparty_response.json()["result"]
    assert counterparty_body["total_weighted_rate"] == "0.03250000"
    assert counterparty_body["total_weighted_coupon_rate"] == "0.02500000"

    details_response = client.get(
        "/api/positions/customer/details",
        params={"customer_name": "Issuer-Gov", "report_date": "2026-01-10"},
    )
    assert details_response.status_code == 200
    details_item = details_response.json()["result"]["items"][0]
    assert details_item["yield_rate"] == "0.03250000"

    ib_response = client.get(
        "/api/positions/interbank",
        params={
            "report_date": "2026-01-10",
            "product_type": "IB",
            "direction": "Asset",
            "page": 1,
            "page_size": 10,
        },
    )
    assert ib_response.status_code == 200
    ib_item = ib_response.json()["result"]["items"][0]
    assert ib_item["interest_rate"] == "0.02500000"

    ib_split_response = client.get(
        "/api/positions/counterparty/interbank/split",
        params={"start_date": "2026-01-01", "end_date": "2026-01-31", "product_type": "IB"},
    )
    assert ib_split_response.status_code == 200
    assert ib_split_response.json()["result"]["asset_total_weighted_rate"] == "0.02500000"


def test_positions_bond_weighted_rates_exclude_missing_rate_denominator(
    tmp_path,
    monkeypatch,
) -> None:
    db = tmp_path / "pos-missing-rate.duckdb"
    conn = duckdb.connect(str(db), read_only=False)
    try:
        _ensure_tables(conn)
        _insert_zqtz(
            conn,
            report_date="2026-01-10",
            instrument_code="RATE-KNOWN",
            bond_type="Gov",
            issuer_name="Issuer-Gov",
            market_value=Decimal("100"),
            ytm=Decimal("3.0"),
            coupon=Decimal("4.0"),
            is_issuance_like=False,
        )
        _insert_zqtz(
            conn,
            report_date="2026-01-10",
            instrument_code="RATE-MISSING",
            bond_type="Gov",
            issuer_name="Issuer-Gov",
            market_value=Decimal("300"),
            ytm=None,
            coupon=None,
            is_issuance_like=False,
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = _authorized_positions_client(tmp_path, monkeypatch)

    counterparty_response = client.get(
        "/api/positions/counterparty/bonds",
        params={
            "start_date": "2026-01-10",
            "end_date": "2026-01-10",
            "sub_type": "Gov",
            "top_n": 10,
            "page": 1,
            "page_size": 10,
        },
    )
    assert counterparty_response.status_code == 200
    counterparty_body = counterparty_response.json()["result"]
    assert counterparty_body["total_weighted_rate"] == "0.03000000"
    assert counterparty_body["total_weighted_coupon_rate"] == "0.04000000"
    assert counterparty_body["items"][0]["weighted_rate"] == "0.03000000"
    assert counterparty_body["items"][0]["weighted_coupon_rate"] == "0.04000000"
    assert counterparty_body["ytm_rate_coverage"] == {
        "policy": "exclude_missing_rate_from_denominator",
        "covered_amount": "100.00000000",
        "missing_amount": "300.00000000",
        "missing_count": 1,
        "coverage_ratio": "25.00000000",
    }
    assert counterparty_body["coupon_rate_coverage"] == {
        "policy": "exclude_missing_rate_from_denominator",
        "covered_amount": "100.00000000",
        "missing_amount": "300.00000000",
        "missing_count": 1,
        "coverage_ratio": "25.00000000",
    }

    rating_response = client.get(
        "/api/positions/stats/rating",
        params={"start_date": "2026-01-10", "end_date": "2026-01-10", "sub_type": "Gov"},
    )
    assert rating_response.status_code == 200
    rating_body = rating_response.json()["result"]
    assert rating_body["items"][0]["weighted_rate"] == "0.03000000"
    assert rating_body["ytm_rate_coverage"]["coverage_ratio"] == "25.00000000"


def test_positions_interbank_rates_treat_low_values_as_percent(tmp_path, monkeypatch) -> None:
    db = tmp_path / "pos-low-interbank-rate.duckdb"
    conn = duckdb.connect(str(db), read_only=False)
    try:
        _ensure_tables(conn)
        _insert_tyw(
            conn,
            report_date="2026-01-10",
            position_id="IB-A-LOW",
            product_type="IB",
            position_side="Asset",
            counterparty="CP-A",
            principal=Decimal("1000"),
            rate=Decimal("0.8"),
        )
        _insert_tyw(
            conn,
            report_date="2026-01-10",
            position_id="IB-L-LOW",
            product_type="IB",
            position_side="Liability",
            counterparty="CP-L",
            principal=Decimal("2000"),
            rate=Decimal("0.72"),
        )
        _insert_tyw(
            conn,
            report_date="2026-01-10",
            position_id="IB-A-MISSING-RATE",
            product_type="IB",
            position_side="Asset",
            counterparty="CP-MISSING",
            principal=Decimal("500"),
            rate=None,
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = _authorized_positions_client(tmp_path, monkeypatch)

    ib_response = client.get(
        "/api/positions/interbank",
        params={
            "report_date": "2026-01-10",
            "direction": "Asset",
            "page": 1,
            "page_size": 10,
        },
    )
    assert ib_response.status_code == 200
    assert ib_response.json()["result"]["items"][0]["interest_rate"] == "0.00800000"

    ib_split_response = client.get(
        "/api/positions/counterparty/interbank/split",
        params={"start_date": "2026-01-10", "end_date": "2026-01-10"},
    )
    assert ib_split_response.status_code == 200
    split_result = ib_split_response.json()["result"]
    assert split_result["asset_total_weighted_rate"] == "0.00800000"
    assert split_result["liability_total_weighted_rate"] == "0.00720000"


def test_positions_bond_rates_low_percent_not_passthrough_and_dirty_values_rejected(
    tmp_path,
    monkeypatch,
) -> None:
    """百分数口径无条件 /100：0.5（=0.5%）→ 0.005；>20% 与负值按脏数据置空并从加权分母剔除。

    旧 `>1 and <=100` 启发式会把 0.5 当作小数 50% 直通，使低票息券按百倍计入
    加权收益率；权威口径见 rate_units.normalize_percent_rate_to_decimal。
    """
    db = tmp_path / "pos-low-percent-rate.duckdb"
    conn = duckdb.connect(str(db), read_only=False)
    try:
        _ensure_tables(conn)
        _insert_zqtz(
            conn,
            report_date="2026-01-10",
            instrument_code="LOW-PCT",
            bond_type="Conv",
            issuer_name="Issuer-Conv",
            market_value=Decimal("100"),
            ytm=Decimal("0.5"),
            coupon=Decimal("0.2"),
            is_issuance_like=False,
        )
        _insert_zqtz(
            conn,
            report_date="2026-01-10",
            instrument_code="DIRTY-HIGH",
            bond_type="Conv",
            issuer_name="Issuer-Conv",
            market_value=Decimal("100"),
            ytm=Decimal("20720.93"),
            coupon=Decimal("25.0"),
            is_issuance_like=False,
        )
        _insert_zqtz(
            conn,
            report_date="2026-01-10",
            instrument_code="DIRTY-NEG",
            bond_type="Conv",
            issuer_name="Issuer-Conv",
            market_value=Decimal("100"),
            ytm=Decimal("-3.0"),
            coupon=Decimal("-1.0"),
            is_issuance_like=False,
        )
    finally:
        conn.close()

    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = _authorized_positions_client(tmp_path, monkeypatch)

    bond_response = client.get(
        "/api/positions/bonds",
        params={"report_date": "2026-01-10", "sub_type": "Conv", "page": 1, "page_size": 10},
    )
    assert bond_response.status_code == 200
    items = {item["bond_code"]: item for item in bond_response.json()["result"]["items"]}
    assert items["LOW-PCT"]["yield_rate"] == "0.00500000"
    assert items["DIRTY-HIGH"]["yield_rate"] is None
    assert items["DIRTY-NEG"]["yield_rate"] is None

    counterparty_response = client.get(
        "/api/positions/counterparty/bonds",
        params={
            "start_date": "2026-01-10",
            "end_date": "2026-01-10",
            "sub_type": "Conv",
            "top_n": 10,
            "page": 1,
            "page_size": 10,
        },
    )
    assert counterparty_response.status_code == 200
    counterparty_body = counterparty_response.json()["result"]
    assert counterparty_body["total_weighted_rate"] == "0.00500000"
    assert counterparty_body["total_weighted_coupon_rate"] == "0.00200000"
    assert counterparty_body["ytm_rate_coverage"]["covered_amount"] == "100.00000000"
    assert counterparty_body["ytm_rate_coverage"]["missing_amount"] == "200.00000000"
    assert counterparty_body["ytm_rate_coverage"]["missing_count"] == 2
    assert counterparty_body["coupon_rate_coverage"]["missing_count"] == 2


def test_positions_customer_drilldowns_exclude_issuance_like_rows(tmp_path, monkeypatch) -> None:
    """customer/details 与 customer/trend 与聚合口径一致：发行腿属负债口径不计入资产对手方。"""
    db = tmp_path / "pos.duckdb"
    _seed_positions_db(db)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = _authorized_positions_client(tmp_path, monkeypatch)

    details = client.get(
        "/api/positions/customer/details",
        params={"customer_name": "发行人乙", "report_date": "2026-01-10"},
    )
    assert details.status_code == 200
    details_body = details.json()["result"]
    assert details_body["bond_count"] == 1
    assert details_body["items"][0]["bond_code"] == "B003"
    assert details_body["total_market_value"] == "50.00000000"

    trend = client.get(
        "/api/positions/customer/trend",
        params={"customer_name": "发行人乙", "end_date": "2026-01-10", "days": 5},
    )
    assert trend.status_code == 200
    trend_items = trend.json()["result"]["items"]
    assert trend_items == [{"date": "2026-01-10", "balance": "50.00000000"}]


def test_positions_optional_report_date_routes_fall_back_to_latest_snapshot_date(tmp_path, monkeypatch) -> None:
    db = tmp_path / "pos.duckdb"
    _seed_positions_db(db)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = _authorized_positions_client(tmp_path, monkeypatch)

    subtypes = client.get("/api/positions/bonds/sub_types")
    assert subtypes.status_code == 200
    assert subtypes.json()["result"]["sub_types"] == ["GOV"]

    details = client.get(
        "/api/positions/customer/details",
        params={"customer_name": "发行人甲"},
    )
    assert details.status_code == 200
    assert details.json()["result"]["report_date"] == "2026-01-12"
    assert details.json()["result"]["bond_count"] == 1


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/api/positions/bonds", {"report_date": "not-a-date"}),
        (
            "/api/positions/counterparty/bonds",
            {"start_date": "2026-99-01", "end_date": "2026-01-31"},
        ),
        ("/api/positions/bonds/sub_types", {"report_date": "2026-02-30"}),
        (
            "/api/positions/customer/details",
            {"customer_name": "发行人甲", "report_date": "bad"},
        ),
        (
            "/api/positions/customer/trend",
            {"customer_name": "发行人甲", "end_date": "2026-13-01"},
        ),
    ],
)
def test_positions_routes_reject_malformed_dates_with_422(
    tmp_path,
    monkeypatch,
    path: str,
    params: dict[str, str],
) -> None:
    db = tmp_path / "pos.duckdb"
    _seed_positions_db(db)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = _authorized_positions_client(tmp_path, monkeypatch)

    response = client.get(path, params=params)

    assert response.status_code == 422


@pytest.mark.parametrize(
    "path",
    [
        "/api/positions/counterparty/bonds",
        "/api/positions/counterparty/interbank/split",
        "/api/positions/stats/rating",
        "/api/positions/stats/industry",
    ],
)
def test_positions_range_routes_reject_start_after_end(
    tmp_path,
    monkeypatch,
    path: str,
) -> None:
    db = tmp_path / "pos.duckdb"
    _seed_positions_db(db)
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(db))
    client = _authorized_positions_client(tmp_path, monkeypatch)

    response = client.get(
        path,
        params={"start_date": "2026-02-01", "end_date": "2026-01-31"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "start_date must be on or before end_date."
