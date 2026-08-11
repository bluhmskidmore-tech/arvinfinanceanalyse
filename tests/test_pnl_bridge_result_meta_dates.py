"""PnL bridge result_meta date / fallback closure (PAGE-BRIDGE-001).

Contract evidence (local docs; moss-metric-contracts MCP unavailable):
- docs/page_contracts.md §8.D PAGE-BRIDGE-001:
  requested_report_date = request report_date
  resolved_report_date = backend payload report_date
  as_of_date = temporarily same as report_date
- fallback_date only when resolved != requested; never invent from multi-curve
  trade dates (service requires exact fact_formal_pnl_fi report_date).
- Curve latest_snapshot / vendor_unavailable stay on fallback_mode + vendor_status;
  quality_flag merges summary with latest_snapshot→stale (yield_curve + macro_vendor
  severity order); vendor_unavailable alone does not override (GS-BRIDGE-WARN-B).
"""

from __future__ import annotations

from decimal import Decimal

import duckdb
import pytest

from backend.app.governance.settings import get_settings
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.repositories.yield_curve_repo import (
    FORMAL_FACT_TABLE,
    ensure_yield_curve_tables,
)
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module
from tests.test_pnl_api_contract import (
    _append_balance_build_run,
    _append_manifest_override,
    _grant_pnl_read_scope,
    _materialize_three_pnl_dates,
    _seed_pnl_bridge_balance_rows,
)


REPORT_DATE = "2025-12-31"
PRIOR_DATE = "2025-10-31"


@pytest.fixture(autouse=True)
def seed_pnl_bridge_date_meta_read_scope(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "pnl-bridge-date-meta-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    _grant_pnl_read_scope(UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}"))
    yield
    get_settings.cache_clear()


def _seed_curve_rows(duckdb_path, rows: list[tuple[object, ...]]) -> None:
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        ensure_yield_curve_tables(conn)
        conn.executemany(
            f"""
            insert into {FORMAL_FACT_TABLE} (
              trade_date, curve_type, tenor, rate_pct, vendor_name, vendor_version,
              source_version, rule_version
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    finally:
        conn.close()


def _exact_treasury_curves() -> list[tuple[object, ...]]:
    return [
        (REPORT_DATE, "treasury", "1Y", Decimal("2.00"), "akshare", "vv_t_cur", "sv_t_cur", "rv_curve"),
        (REPORT_DATE, "treasury", "2Y", Decimal("3.00"), "akshare", "vv_t_cur", "sv_t_cur", "rv_curve"),
        (REPORT_DATE, "treasury", "3Y", Decimal("4.00"), "akshare", "vv_t_cur", "sv_t_cur", "rv_curve"),
        (PRIOR_DATE, "treasury", "1Y", Decimal("1.00"), "akshare", "vv_t_pri", "sv_t_pri", "rv_curve"),
        (PRIOR_DATE, "treasury", "2Y", Decimal("2.00"), "akshare", "vv_t_pri", "sv_t_pri", "rv_curve"),
        (PRIOR_DATE, "treasury", "3Y", Decimal("3.00"), "akshare", "vv_t_pri", "sv_t_pri", "rv_curve"),
    ]


def _latest_fallback_treasury_curves() -> list[tuple[object, ...]]:
    return [
        ("2025-12-30", "treasury", "1Y", Decimal("2.00"), "akshare", "vv_t_fb", "sv_t_fb", "rv_curve"),
        ("2025-12-30", "treasury", "2Y", Decimal("3.00"), "akshare", "vv_t_fb", "sv_t_fb", "rv_curve"),
        ("2025-12-30", "treasury", "3Y", Decimal("4.00"), "akshare", "vv_t_fb", "sv_t_fb", "rv_curve"),
        (PRIOR_DATE, "treasury", "1Y", Decimal("1.00"), "akshare", "vv_t_pri", "sv_t_pri", "rv_curve"),
        (PRIOR_DATE, "treasury", "2Y", Decimal("2.00"), "akshare", "vv_t_pri", "sv_t_pri", "rv_curve"),
        (PRIOR_DATE, "treasury", "3Y", Decimal("3.00"), "akshare", "vv_t_pri", "sv_t_pri", "rv_curve"),
    ]


def _prepare_bridge_fixture(tmp_path, monkeypatch, *, curve_rows: list[tuple[object, ...]] | None):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_pnl_bridge_dates",
        vendor_version="vv_pnl_bridge_dates",
        rule_version="rv_pnl_bridge_dates",
    )
    _seed_pnl_bridge_balance_rows(
        duckdb_path,
        include_tyw_only_intermediate_prior=False,
    )
    _append_balance_build_run(
        governance_dir,
        run_id="balance-current",
        report_date=REPORT_DATE,
        source_version="sv_balance_current",
        vendor_version="vv_balance",
        rule_version="rv_balance_current",
    )
    _append_balance_build_run(
        governance_dir,
        run_id="balance-prior",
        report_date=PRIOR_DATE,
        source_version="sv_balance_prior",
        vendor_version="vv_balance",
        rule_version="rv_balance_prior",
    )
    if curve_rows:
        _seed_curve_rows(duckdb_path, curve_rows)
    return duckdb_path


def _get_bridge(report_date: str = REPORT_DATE) -> dict[str, object]:
    from fastapi.testclient import TestClient

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": report_date})
    assert response.status_code == 200
    return response.json()


def test_pnl_bridge_result_meta_dates_no_fallback(tmp_path, monkeypatch):
    _prepare_bridge_fixture(tmp_path, monkeypatch, curve_rows=_exact_treasury_curves())

    payload = _get_bridge()
    meta = payload["result_meta"]

    assert meta["requested_report_date"] == REPORT_DATE
    assert meta["resolved_report_date"] == REPORT_DATE
    assert meta["as_of_date"] == REPORT_DATE
    assert meta["fallback_date"] is None
    assert meta["fallback_mode"] == "none"
    assert meta["vendor_status"] == "ok"
    assert meta["quality_flag"] == payload["result"]["summary"]["quality_flag"]
    assert meta.get("date_basis") in (None, "")
    get_settings.cache_clear()


def _zero_out_516_for_report_date(duckdb_path) -> None:
    """把共享夹具行的 516 归零，保持 summary 健康。

    互斥分解后（审计 PNL-01），带非零 516 且无可用曲线的 FVTPL 行会诚实地
    产生残差与 error 标记；本测试的目的只是验证 stale 合并语义，需要一个
    quality=ok 的背景 summary，故将公允价值变动清零（业务上等价于
    "本期无待解释的公允变动"）。
    """
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update fact_formal_pnl_fi
            set total_pnl = total_pnl - fair_value_change_516,
                fair_value_change_516 = 0
            where report_date = ?
            """,
            [REPORT_DATE],
        )
    finally:
        conn.close()


def test_pnl_bridge_result_meta_dates_latest_snapshot_fallback(tmp_path, monkeypatch):
    duckdb_path = _prepare_bridge_fixture(
        tmp_path, monkeypatch, curve_rows=_latest_fallback_treasury_curves()
    )
    _zero_out_516_for_report_date(duckdb_path)

    payload = _get_bridge()
    meta = payload["result_meta"]
    summary_quality = payload["result"]["summary"]["quality_flag"]

    assert meta["requested_report_date"] == REPORT_DATE
    assert meta["resolved_report_date"] == REPORT_DATE
    assert meta["as_of_date"] == REPORT_DATE
    # Report date did not fall back; do not invent a curve trade_date as fallback_date.
    assert meta["fallback_date"] is None
    assert meta["fallback_mode"] == "latest_snapshot"
    assert meta["vendor_status"] == "vendor_stale"
    # Fixture keeps summary healthy so stale must come from latest_snapshot merge.
    assert summary_quality == "ok"
    assert meta["quality_flag"] == "stale"
    assert any("YIELD_CURVE_LATEST_FALLBACK" in warning for warning in payload["result"]["warnings"])
    get_settings.cache_clear()


def test_pnl_bridge_result_meta_dates_vendor_unavailable(tmp_path, monkeypatch):
    _prepare_bridge_fixture(tmp_path, monkeypatch, curve_rows=[])

    payload = _get_bridge()
    meta = payload["result_meta"]
    summary_quality = payload["result"]["summary"]["quality_flag"]

    assert meta["requested_report_date"] == REPORT_DATE
    assert meta["resolved_report_date"] == REPORT_DATE
    assert meta["as_of_date"] == REPORT_DATE
    assert meta["fallback_date"] is None
    assert meta["fallback_mode"] == "none"
    assert meta["vendor_status"] == "vendor_unavailable"
    # vendor_unavailable alone does not upgrade quality (GS-BRIDGE-WARN-B).
    assert meta["quality_flag"] == summary_quality
    assert any("No treasury curve available" in warning for warning in payload["result"]["warnings"])
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("summary_quality", "curve_latest_fallback", "expected"),
    [
        # Pure matrix: ok/warning/error × latest_fallback; severity error > stale > warning > ok.
        ("ok", False, "ok"),
        ("ok", True, "stale"),
        ("warning", False, "warning"),
        ("warning", True, "stale"),
        ("error", False, "error"),
        ("error", True, "error"),
        # Extra: summary already stale is preserved either way.
        ("stale", False, "stale"),
        ("stale", True, "stale"),
    ],
)
def test_merge_bridge_quality_flag_matrix(summary_quality, curve_latest_fallback, expected):
    from backend.app.services.pnl_bridge_service import _merge_bridge_quality_flag

    assert (
        _merge_bridge_quality_flag(
            summary_quality=summary_quality,
            curve_latest_fallback=curve_latest_fallback,
        )
        == expected
    )
