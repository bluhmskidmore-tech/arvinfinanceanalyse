"""A4 披露：`_curve_points` 解析失败时，失败原因必须进入 warnings。

归零 fallback（曲线贡献置 0）是设计内行为，本文件只验证披露语义：
- 单元层：`_curve_points_with_reason` 对坏 snapshot 返回 (None, 原因摘要)。
- 服务层：`pnl_bridge_envelope` 的 warnings 同时包含原有归零披露与
  `curve_snapshot_error: ...` 原因条目，且曲线贡献仍为 0。
"""

from __future__ import annotations

from decimal import Decimal

import duckdb
import pytest

from backend.app.governance.settings import get_settings
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.repositories.yield_curve_repo import YieldCurveRepository
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from backend.app.services.pnl_bridge_service import (
    _curve_points,
    _curve_points_with_reason,
    pnl_bridge_envelope,
)
from tests.test_pnl_api_contract import (
    _append_manifest_override,
    _grant_pnl_read_scope,
    _materialize_three_pnl_dates,
    _seed_pnl_bridge_balance_rows,
)
from tests.test_pnl_bridge_curve_effects import _seed_curve_rows


@pytest.fixture(autouse=True)
def seed_pnl_bridge_curve_disclosure_read_scope(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "pnl-bridge-curve-disclosure-scope.db"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", f"sqlite:///{sqlite_path.as_posix()}")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    _grant_pnl_read_scope(UserScopeRepository(f"sqlite:///{sqlite_path.as_posix()}"))
    yield
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("curve", "expected_reason_fragment"),
    [
        ([{"tenor": "1Y", "rate": "2.10"}], "curve payload is not a mapping (got list)"),
        ({"": Decimal("2.10")}, "unknown tenor label ''"),
        ({1: Decimal("2.10")}, "unknown tenor label 1"),
        ({"BOGUS": Decimal("2.10")}, "unknown tenor label 'BOGUS'"),
        ({"12X": Decimal("2.10")}, "unknown tenor label '12X'"),
        ({"1Y": "not-a-rate"}, "invalid rate 'not-a-rate' for tenor '1Y'"),
        ({"1Y": Decimal("NaN")}, "non-finite rate"),
        ({"1Y": Decimal("Infinity")}, "non-finite rate"),
    ],
)
def test_curve_points_with_reason_reports_failure_cause(curve, expected_reason_fragment):
    points, reason = _curve_points_with_reason({"curve": curve})

    assert points is None
    assert reason is not None
    assert expected_reason_fragment in reason
    # 归零 fallback 契约不变：包装函数仍对坏 snapshot 返回 None。
    assert _curve_points({"curve": curve}) is None


def test_curve_points_with_reason_is_silent_for_valid_or_absent_snapshot():
    assert _curve_points_with_reason(None) == (None, None)
    assert _curve_points_with_reason({"curve": {"1Y": "2.10", "2Y": 3}}) == (
        {"1Y": Decimal("2.10"), "2Y": Decimal("3")},
        None,
    )


def test_pnl_bridge_envelope_discloses_curve_snapshot_error_reason_and_zeroed_effects(
    tmp_path,
    monkeypatch,
):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_pnl_curve_disclosure",
        vendor_version="vv_pnl_curve_disclosure",
        rule_version="rv_pnl_curve_disclosure",
    )
    _seed_pnl_bridge_balance_rows(
        duckdb_path,
        include_tyw_only_intermediate_prior=False,
    )
    _seed_curve_rows(
        duckdb_path,
        [
            ("2025-12-31", "treasury", "1Y", Decimal("2.00"), "choice", "vv_current", "sv_current", "rv_curve"),
            ("2025-10-31", "treasury", "1Y", Decimal("1.00"), "choice", "vv_prior", "sv_prior", "rv_curve"),
        ],
    )
    # 与 test_pnl_bridge_curve_effects 的转换失败用例同构：清零 516 保持健康 summary，
    # 使本测试只聚焦披露语义。
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update fact_formal_pnl_fi
            set total_pnl = total_pnl - fair_value_change_516,
                fair_value_change_516 = 0
            where report_date = '2025-12-31'
            """
        )
    finally:
        conn.close()

    original_fetch_snapshot = YieldCurveRepository.fetch_curve_snapshot

    def fetch_snapshot_with_invalid_required_curve(self, trade_date, curve_type):
        snapshot = original_fetch_snapshot(self, trade_date, curve_type)
        if trade_date == "2025-12-31" and curve_type == "treasury":
            assert snapshot is not None
            return {**snapshot, "curve": {"1Y": "not-a-rate"}}
        return snapshot

    monkeypatch.setattr(
        YieldCurveRepository,
        "fetch_curve_snapshot",
        fetch_snapshot_with_invalid_required_curve,
    )

    envelope = pnl_bridge_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2025-12-31",
    )

    warnings = envelope["result"]["warnings"]
    # 既有归零披露原文不变。
    assert (
        "Required treasury curve snapshot for trade_date=2025-12-31 could not be "
        "converted to validated curve points; curve effect remains 0."
        in warnings
    )
    # 新增披露：失败原因进 warnings。
    assert [warning for warning in warnings if warning.startswith("curve_snapshot_error:")] == [
        "curve_snapshot_error: treasury curve snapshot for trade_date=2025-12-31 "
        "rejected: invalid rate 'not-a-rate' for tenor '1Y'; curve effect remains 0."
    ]
    # 曲线贡献仍按归零披露，数值路径与元数据语义不变。
    row = envelope["result"]["rows"][0]
    assert [
        float(row[field]["raw"])
        for field in ("roll_down", "treasury_curve", "credit_spread")
    ] == [0.0, 0.0, 0.0]
    assert envelope["result_meta"]["vendor_status"] == "vendor_unavailable"
    assert envelope["result_meta"]["quality_flag"] == "warning"
