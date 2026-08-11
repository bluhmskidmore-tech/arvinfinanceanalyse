from __future__ import annotations

from datetime import date
from decimal import Decimal

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.app.core_finance.pnl_bridge import build_pnl_bridge_rows
from backend.app.governance.formal_compute_lineage import FormalLineageMalformedError
from backend.app.governance.settings import get_settings
from backend.app.repositories.balance_analysis_repo import BalanceAnalysisRepository
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.repositories.pnl_repo import PnlRepository
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.repositories.yield_curve_repo import (
    FORMAL_FACT_TABLE,
    YieldCurveRepository,
    ensure_yield_curve_tables,
)
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from backend.app.services.campisi_attribution_service import _formal_bridge_bond_rows
from backend.app.services.pnl_bridge_service import (
    _curve_points,
    _resolve_pnl_lineage,
    pnl_bridge_envelope,
)
from tests.helpers import load_module
from tests.test_pnl_api_contract import (
    _append_balance_build_run,
    _append_manifest_override,
    _grant_pnl_read_scope,
    _materialize_three_pnl_dates,
    _seed_pnl_bridge_balance_rows,
)


@pytest.fixture(autouse=True)
def seed_pnl_bridge_curve_read_scope(tmp_path, monkeypatch):
    sqlite_path = tmp_path / "pnl-bridge-curve-read-scope.db"
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
              trade_date, curve_type, tenor, rate_pct, vendor_name, vendor_version, source_version, rule_version
            ) values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    finally:
        conn.close()


def test_curve_points_accepts_real_repository_mapping_and_strictly_converts_values(tmp_path):
    duckdb_path = tmp_path / "curve-contract.duckdb"
    _seed_curve_rows(
        duckdb_path,
        [
            (
                "2025-12-31",
                "treasury",
                "3Y",
                Decimal("2.75"),
                "choice",
                "vv_curve",
                "sv_curve",
                "rv_curve",
            ),
        ],
    )

    snapshot = YieldCurveRepository(str(duckdb_path)).fetch_curve_snapshot(
        "2025-12-31",
        "treasury",
    )

    assert snapshot is not None
    assert isinstance(snapshot["curve"], dict)
    assert _curve_points(snapshot) == {"3Y": Decimal("2.75")}
    assert _curve_points({"curve": {"1Y": "2.10", "2Y": 3}}) == {
        "1Y": Decimal("2.10"),
        "2Y": Decimal("3"),
    }


@pytest.mark.parametrize(
    "curve",
    [
        [{"tenor": "1Y", "rate": "2.10"}],
        {"": Decimal("2.10")},
        {1: Decimal("2.10")},
        {"BOGUS": Decimal("2.10")},
        {"12X": Decimal("2.10")},
        {"1Y": "not-a-rate"},
        {"1Y": Decimal("NaN")},
        {"1Y": Decimal("Infinity")},
    ],
)
def test_curve_points_fails_closed_for_legacy_or_invalid_curve_shapes(curve):
    assert _curve_points({"curve": curve}) is None


def test_pnl_bridge_lineage_propagates_manifest_repository_failure_with_exact_build(
    monkeypatch,
):
    build = {"source_version": "sv", "vendor_version": "vv", "rule_version": "rv"}
    monkeypatch.setattr(
        GovernanceRepository,
        "read_latest_completed_run",
        lambda *args, **kwargs: build,
    )

    def fail_manifest_read(*args, **kwargs):
        raise RuntimeError("manifest repository unavailable")

    monkeypatch.setattr(GovernanceRepository, "read_latest_manifest", fail_manifest_read)
    with pytest.raises(RuntimeError, match="manifest repository unavailable"):
        _resolve_pnl_lineage(governance_dir="unused", report_date="2025-12-31")


def test_pnl_bridge_lineage_propagates_malformed_manifest_with_exact_build(
    monkeypatch,
):
    build = {"source_version": "sv", "vendor_version": "vv", "rule_version": "rv"}
    malformed = {
        "source_version": "sv_manifest",
        "vendor_version": "vv_manifest",
        "rule_version": "",
    }
    monkeypatch.setattr(
        GovernanceRepository,
        "read_latest_completed_run",
        lambda *args, **kwargs: build,
    )
    monkeypatch.setattr(
        GovernanceRepository,
        "read_latest_manifest",
        lambda *args, **kwargs: malformed,
    )

    with pytest.raises(FormalLineageMalformedError, match="missing rule_version"):
        _resolve_pnl_lineage(governance_dir="unused", report_date="2025-12-31")


def test_pnl_bridge_lineage_allows_exact_build_when_manifest_does_not_exist(
    monkeypatch,
):
    build = {"source_version": "sv", "vendor_version": "vv", "rule_version": "rv"}
    monkeypatch.setattr(
        GovernanceRepository,
        "read_latest_completed_run",
        lambda *args, **kwargs: build,
    )
    monkeypatch.setattr(
        GovernanceRepository,
        "read_latest_manifest",
        lambda *args, **kwargs: None,
    )

    assert _resolve_pnl_lineage(
        governance_dir="unused",
        report_date="2025-12-31",
    ) == build


def test_pnl_bridge_api_fails_closed_when_manifest_repository_is_unavailable(
    tmp_path,
    monkeypatch,
):
    _materialize_three_pnl_dates(tmp_path, monkeypatch)
    bridge_service = load_module(
        "backend.app.services.pnl_bridge_service",
        "backend/app/services/pnl_bridge_service.py",
    )

    def fail_lineage_resolution(**kwargs):
        raise RuntimeError("manifest repository unavailable")

    monkeypatch.setattr(
        bridge_service,
        "resolve_formal_manifest_lineage_with_completed_build",
        fail_lineage_resolution,
    )
    client = TestClient(
        load_module("backend.app.main", "backend/app/main.py").app,
        raise_server_exceptions=False,
    )

    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 503
    assert response.json()["detail"] == "manifest repository unavailable"


def test_pnl_bridge_envelope_marks_required_curve_conversion_failure_unavailable(
    tmp_path,
    monkeypatch,
):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_pnl_curve_conversion_failure",
        vendor_version="vv_pnl_curve_conversion_failure",
        rule_version="rv_pnl_curve_conversion_failure",
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
    # 互斥分解后（审计 PNL-01），带非零 516 且曲线转换失败的 FVTPL 行会诚实产生
    # 残差与 error。本测试只验证 vendor_unavailable 标记与告警文案，需要健康
    # summary 背景，故把共享夹具行的 516 清零（等价于"本期无待解释的公允变动"）。
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

    assert envelope["result"]["summary"]["quality_flag"] == "ok"
    assert envelope["result_meta"]["vendor_status"] == "vendor_unavailable"
    assert envelope["result_meta"]["quality_flag"] == "warning"
    assert (
        "Required treasury curve snapshot for trade_date=2025-12-31 could not be "
        "converted to validated curve points; curve effect remains 0."
        in envelope["result"]["warnings"]
    )


def test_pnl_bridge_curve_effects_match_core_and_do_not_leak_into_campisi_selection(
    tmp_path,
    monkeypatch,
):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_pnl_curve_contract",
        vendor_version="vv_pnl_curve_contract",
        rule_version="rv_pnl_curve_contract",
    )
    _seed_pnl_bridge_balance_rows(
        duckdb_path,
        include_tyw_only_intermediate_prior=False,
    )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update fact_formal_zqtz_balance_daily
            set instrument_name = 'Bridge Credit Bond',
                asset_class = 'credit',
                bond_type = 'corporate bond',
                face_value_amount = market_value_amount,
                coupon_rate = 0,
                ytm_value = 0,
                maturity_date = '2028-12-30'
            where instrument_code = '240001.IB'
            """
        )
    finally:
        conn.close()
    _seed_curve_rows(
        duckdb_path,
        [
            ("2025-12-31", "treasury", "1Y", Decimal("2.00"), "choice", "vv_tc", "sv_tc", "rv_curve"),
            ("2025-12-31", "treasury", "2Y", Decimal("3.00"), "choice", "vv_tc", "sv_tc", "rv_curve"),
            ("2025-12-31", "treasury", "3Y", Decimal("4.00"), "choice", "vv_tc", "sv_tc", "rv_curve"),
            ("2025-10-31", "treasury", "1Y", Decimal("1.00"), "choice", "vv_tp", "sv_tp", "rv_curve"),
            ("2025-10-31", "treasury", "2Y", Decimal("2.00"), "choice", "vv_tp", "sv_tp", "rv_curve"),
            ("2025-10-31", "treasury", "3Y", Decimal("3.00"), "choice", "vv_tp", "sv_tp", "rv_curve"),
            ("2025-12-31", "aaa_credit", "1Y", Decimal("4.00"), "choice", "vv_ac", "sv_ac", "rv_curve"),
            ("2025-12-31", "aaa_credit", "2Y", Decimal("5.00"), "choice", "vv_ac", "sv_ac", "rv_curve"),
            ("2025-12-31", "aaa_credit", "3Y", Decimal("6.00"), "choice", "vv_ac", "sv_ac", "rv_curve"),
            ("2025-10-31", "aaa_credit", "1Y", Decimal("2.00"), "choice", "vv_ap", "sv_ap", "rv_curve"),
            ("2025-10-31", "aaa_credit", "2Y", Decimal("3.00"), "choice", "vv_ap", "sv_ap", "rv_curve"),
            ("2025-10-31", "aaa_credit", "3Y", Decimal("4.00"), "choice", "vv_ap", "sv_ap", "rv_curve"),
        ],
    )

    curve_repo = YieldCurveRepository(str(duckdb_path))
    treasury_current = curve_repo.fetch_curve_snapshot("2025-12-31", "treasury")
    treasury_prior = curve_repo.fetch_curve_snapshot("2025-10-31", "treasury")
    credit_current = curve_repo.fetch_curve_snapshot("2025-12-31", "aaa_credit")
    credit_prior = curve_repo.fetch_curve_snapshot("2025-10-31", "aaa_credit")
    assert all(
        snapshot is not None and isinstance(snapshot["curve"], dict)
        for snapshot in (treasury_current, treasury_prior, credit_current, credit_prior)
    )

    balance_repo = BalanceAnalysisRepository(str(duckdb_path))
    direct_rows = build_pnl_bridge_rows(
        pnl_fi_rows=PnlRepository(str(duckdb_path)).fetch_formal_fi_rows("2025-12-31"),
        balance_rows_current=balance_repo.fetch_pnl_bridge_zqtz_balance_rows(
            report_date="2025-12-31"
        ),
        balance_rows_prior=balance_repo.fetch_pnl_bridge_zqtz_balance_rows(
            report_date="2025-10-31"
        ),
        treasury_curve_current=treasury_current["curve"],
        treasury_curve_prior=treasury_prior["curve"],
        aaa_credit_curve_current=credit_current["curve"],
        aaa_credit_curve_prior=credit_prior["curve"],
    )
    envelope = pnl_bridge_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date="2025-12-31",
    )
    service_row = envelope["result"]["rows"][0]
    direct_row = direct_rows[0]

    for field in ("roll_down", "treasury_curve", "credit_spread"):
        service_value = float(service_row[field]["raw"])
        assert service_value != 0.0
        assert service_value == pytest.approx(float(getattr(direct_row, field)))

    campisi_row = _formal_bridge_bond_rows(
        bridge_envelope=envelope,
        positions=[
            {
                "instrument_code": "240001.IB",
                "portfolio_name": "FI Desk",
                "cost_center": "CC100",
                "asset_class_start": "credit",
                "maturity_date_start": "2028-12-30",
                "market_value_start": Decimal("91"),
            }
        ],
        start_date=date(2025, 10, 31),
    )[0]
    actual = Decimal(str(service_row["actual_pnl"]["raw"]))
    carry = Decimal(str(service_row["carry"]["raw"]))
    treasury = Decimal(str(service_row["roll_down"]["raw"])) + Decimal(
        str(service_row["treasury_curve"]["raw"])
    )
    spread = Decimal(str(service_row["credit_spread"]["raw"]))
    expected_selection = actual - carry - treasury - spread

    assert campisi_row["treasury_effect"] == pytest.approx(float(treasury))
    assert campisi_row["spread_effect"] == pytest.approx(float(spread))
    assert campisi_row["selection_effect"] == pytest.approx(float(expected_selection))
    assert expected_selection != actual - carry


def test_pnl_bridge_warns_when_latest_curve_fallback_is_used_and_merges_lineage(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_pnl_curve",
        vendor_version="vv_pnl_curve",
        rule_version="rv_pnl_curve",
    )
    _seed_pnl_bridge_balance_rows(
        duckdb_path,
        include_tyw_only_intermediate_prior=False,
    )
    _append_balance_build_run(
        governance_dir,
        run_id="balance-current",
        report_date="2025-12-31",
        source_version="sv_balance_current",
        vendor_version="vv_balance",
        rule_version="rv_balance_current",
    )
    _append_balance_build_run(
        governance_dir,
        run_id="balance-prior",
        report_date="2025-10-31",
        source_version="sv_balance_prior",
        vendor_version="vv_balance",
        rule_version="rv_balance_prior",
    )
    _seed_curve_rows(
        duckdb_path,
        [
            ("2025-12-30", "treasury", "1Y", Decimal("2.00"), "akshare", "vv_treasury_latest", "sv_treasury_latest", "rv_curve"),
            ("2025-12-30", "treasury", "2Y", Decimal("3.00"), "akshare", "vv_treasury_latest", "sv_treasury_latest", "rv_curve"),
            ("2025-12-30", "treasury", "3Y", Decimal("4.00"), "akshare", "vv_treasury_latest", "sv_treasury_latest", "rv_curve"),
            ("2025-12-30", "cdb", "1Y", Decimal("2.20"), "choice", "vv_cdb_latest", "sv_cdb_latest", "rv_curve"),
            ("2025-12-30", "cdb", "2Y", Decimal("3.20"), "choice", "vv_cdb_latest", "sv_cdb_latest", "rv_curve"),
            ("2025-12-30", "cdb", "3Y", Decimal("4.20"), "choice", "vv_cdb_latest", "sv_cdb_latest", "rv_curve"),
            ("2025-10-31", "treasury", "1Y", Decimal("1.00"), "akshare", "vv_treasury_prior", "sv_treasury_prior", "rv_curve"),
            ("2025-10-31", "treasury", "2Y", Decimal("2.00"), "akshare", "vv_treasury_prior", "sv_treasury_prior", "rv_curve"),
            ("2025-10-31", "treasury", "3Y", Decimal("3.00"), "akshare", "vv_treasury_prior", "sv_treasury_prior", "rv_curve"),
            ("2025-10-31", "cdb", "1Y", Decimal("1.10"), "choice", "vv_cdb_prior", "sv_cdb_prior", "rv_curve"),
            ("2025-10-31", "cdb", "2Y", Decimal("2.10"), "choice", "vv_cdb_prior", "sv_cdb_prior", "rv_curve"),
            ("2025-10-31", "cdb", "3Y", Decimal("3.10"), "choice", "vv_cdb_prior", "sv_cdb_prior", "rv_curve"),
        ],
    )

    client = load_module("backend.app.main", "backend/app/main.py").app
    from fastapi.testclient import TestClient

    response = TestClient(client).get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    warnings = payload["result"]["warnings"]
    assert any(
        "YIELD_CURVE_LATEST_FALLBACK" in warning and "2025-12-30" in warning for warning in warnings
    )
    assert "sv_treasury_latest" in payload["result_meta"]["source_version"]
    assert "sv_treasury_prior" in payload["result_meta"]["source_version"]
    assert "vv_treasury_latest" in payload["result_meta"]["vendor_version"]
    get_settings.cache_clear()


def test_pnl_bridge_keeps_fresh_metadata_when_missing_credit_curve_is_irrelevant(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_pnl_curve",
        vendor_version="vv_pnl_curve",
        rule_version="rv_pnl_curve",
    )
    _seed_pnl_bridge_balance_rows(
        duckdb_path,
        include_tyw_only_intermediate_prior=False,
    )
    _append_balance_build_run(
        governance_dir,
        run_id="fresh-balance-current",
        report_date="2025-12-31",
        source_version="sv_balance_current",
        vendor_version="vv_balance",
        rule_version="rv_balance_current",
    )
    _append_balance_build_run(
        governance_dir,
        run_id="fresh-balance-prior",
        report_date="2025-10-31",
        source_version="sv_balance_prior",
        vendor_version="vv_balance",
        rule_version="rv_balance_prior",
    )
    _seed_curve_rows(
        duckdb_path,
        [
            ("2025-12-31", "treasury", "1Y", Decimal("2.00"), "akshare", "vv_treasury_current", "sv_treasury_current", "rv_curve"),
            ("2025-12-31", "treasury", "2Y", Decimal("3.00"), "akshare", "vv_treasury_current", "sv_treasury_current", "rv_curve"),
            ("2025-12-31", "treasury", "3Y", Decimal("4.00"), "akshare", "vv_treasury_current", "sv_treasury_current", "rv_curve"),
            ("2025-10-31", "treasury", "1Y", Decimal("1.00"), "akshare", "vv_treasury_prior", "sv_treasury_prior", "rv_curve"),
            ("2025-10-31", "treasury", "2Y", Decimal("2.00"), "akshare", "vv_treasury_prior", "sv_treasury_prior", "rv_curve"),
            ("2025-10-31", "treasury", "3Y", Decimal("3.00"), "akshare", "vv_treasury_prior", "sv_treasury_prior", "rv_curve"),
        ],
    )

    from fastapi.testclient import TestClient

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["vendor_status"] == "ok"
    assert payload["result_meta"]["fallback_mode"] == "none"
    assert not any("Phase 3 partial delivery" in warning for warning in payload["result"]["warnings"])
    assert not any("aaa_credit" in warning for warning in payload["result"]["warnings"])
    get_settings.cache_clear()


def test_pnl_bridge_ignores_corrupt_irrelevant_credit_curve_lineage(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_pnl_curve",
        vendor_version="vv_pnl_curve",
        rule_version="rv_pnl_curve",
    )
    _seed_pnl_bridge_balance_rows(
        duckdb_path,
        include_tyw_only_intermediate_prior=False,
    )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.executemany(
            """
            insert into fact_formal_zqtz_balance_daily (
              report_date, instrument_code, portfolio_name, cost_center, invest_type_std,
              accounting_basis, position_scope, currency_basis, currency_code,
              market_value_amount, amortized_cost_amount, accrued_interest_amount, is_issuance_like,
              source_version, rule_version, ingest_batch_id, trace_id, asset_class, bond_type
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("2025-12-31", "CB-IRRELEVANT", "OTHER", "CC999", "A", "OCI", "asset", "CNY", "CNY", "50", "49", "1", False, "sv_irrel", "rv_irrel", "ib_irrel", "tr_irrel", "信用债", "企业债"),
                ("2025-10-31", "CB-IRRELEVANT", "OTHER", "CC999", "A", "OCI", "asset", "CNY", "CNY", "48", "47", "1", False, "sv_irrel", "rv_irrel", "ib_irrel", "tr_irrel", "信用债", "企业债"),
            ],
        )
    finally:
        conn.close()
    _seed_curve_rows(
        duckdb_path,
        [
            ("2025-12-31", "treasury", "1Y", Decimal("2.00"), "akshare", "vv_treasury_current", "sv_treasury_current", "rv_curve"),
            ("2025-12-31", "treasury", "2Y", Decimal("3.00"), "akshare", "vv_treasury_current", "sv_treasury_current", "rv_curve"),
            ("2025-12-31", "treasury", "3Y", Decimal("4.00"), "akshare", "vv_treasury_current", "sv_treasury_current", "rv_curve"),
            ("2025-10-31", "treasury", "1Y", Decimal("1.00"), "akshare", "vv_treasury_prior", "sv_treasury_prior", "rv_curve"),
            ("2025-10-31", "treasury", "2Y", Decimal("2.00"), "akshare", "vv_treasury_prior", "sv_treasury_prior", "rv_curve"),
            ("2025-10-31", "treasury", "3Y", Decimal("3.00"), "akshare", "vv_treasury_prior", "sv_treasury_prior", "rv_curve"),
            ("2025-12-31", "aaa_credit", "1Y", Decimal("4.00"), "choice", "vv_a", "sv_a", "rv_curve"),
            ("2025-12-31", "aaa_credit", "2Y", Decimal("5.00"), "other", "vv_a", "sv_a", "rv_curve"),
        ],
    )

    from fastapi.testclient import TestClient

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["vendor_status"] == "ok"
    assert payload["result_meta"]["fallback_mode"] == "none"
    get_settings.cache_clear()


def test_pnl_bridge_fails_closed_when_same_day_curve_snapshot_lineage_is_corrupt(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_pnl_curve",
        vendor_version="vv_pnl_curve",
        rule_version="rv_pnl_curve",
    )
    _seed_pnl_bridge_balance_rows(
        duckdb_path,
        include_tyw_only_intermediate_prior=False,
    )
    _seed_curve_rows(
        duckdb_path,
        [
            ("2025-12-31", "treasury", "1Y", Decimal("2.00"), "akshare", "vv_curve", "sv_curve", "rv_curve"),
            ("2025-12-31", "treasury", "2Y", Decimal("3.00"), "choice", "vv_curve", "sv_curve", "rv_curve"),
            ("2025-10-31", "treasury", "1Y", Decimal("1.00"), "akshare", "vv_prior", "sv_prior", "rv_curve"),
            ("2025-10-31", "treasury", "2Y", Decimal("2.00"), "akshare", "vv_prior", "sv_prior", "rv_curve"),
        ],
    )

    service_mod = load_module(
        "backend.app.services.pnl_bridge_service",
        "backend/app/services/pnl_bridge_service.py",
    )

    with pytest.raises(RuntimeError, match="corrupt|inconsistent|lineage"):
        service_mod.pnl_bridge_envelope(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            report_date="2025-12-31",
        )
    get_settings.cache_clear()


def test_pnl_bridge_marks_result_meta_unavailable_when_credit_curve_missing(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_pnl_curve",
        vendor_version="vv_pnl_curve",
        rule_version="rv_pnl_curve",
    )
    _seed_pnl_bridge_balance_rows(
        duckdb_path,
        include_tyw_only_intermediate_prior=False,
    )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update fact_formal_zqtz_balance_daily
            set instrument_name = 'Bridge Credit Bond',
                asset_class = 'credit',
                bond_type = 'corporate bond'
            where instrument_code = '240001.IB'
            """
        )
    finally:
        conn.close()
    _seed_curve_rows(
        duckdb_path,
        [
            ("2025-12-31", "treasury", "1Y", Decimal("2.00"), "choice", "vv_t_current", "sv_t_current", "rv_curve"),
            ("2025-10-31", "treasury", "1Y", Decimal("1.00"), "choice", "vv_t_prior", "sv_t_prior", "rv_curve"),
        ],
    )

    from fastapi.testclient import TestClient

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["vendor_status"] == "vendor_unavailable"
    assert payload["result_meta"]["fallback_mode"] == "none"
    row = payload["result"]["rows"][0]
    assert [
        row[field]["raw"]
        for field in ("roll_down", "treasury_curve", "credit_spread")
    ] == [0.0, 0.0, 0.0]
    warnings = payload["result"]["warnings"]
    assert any("No aaa_credit curve available" in warning for warning in warnings)
    assert not any("No treasury curve available" in warning for warning in warnings)
    get_settings.cache_clear()


def test_pnl_bridge_first_period_does_not_mark_vendor_unavailable_when_current_curve_exists(tmp_path, monkeypatch):
    governance_dir = _materialize_three_pnl_dates(tmp_path, monkeypatch)
    duckdb_path = tmp_path / "moss.duckdb"
    _append_manifest_override(
        governance_dir,
        source_version="sv_pnl_curve",
        vendor_version="vv_pnl_curve",
        rule_version="rv_pnl_curve",
    )
    _seed_pnl_bridge_balance_rows(
        duckdb_path,
        include_tyw_only_intermediate_prior=False,
    )
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute("delete from fact_formal_zqtz_balance_daily where report_date = '2025-10-31'")
    finally:
        conn.close()
    _seed_curve_rows(
        duckdb_path,
        [
            ("2025-12-31", "treasury", "1Y", Decimal("2.00"), "akshare", "vv_treasury_current", "sv_treasury_current", "rv_curve"),
            ("2025-12-31", "treasury", "2Y", Decimal("3.00"), "akshare", "vv_treasury_current", "sv_treasury_current", "rv_curve"),
            ("2025-12-31", "treasury", "3Y", Decimal("4.00"), "akshare", "vv_treasury_current", "sv_treasury_current", "rv_curve"),
        ],
    )

    from fastapi.testclient import TestClient

    client = TestClient(load_module("backend.app.main", "backend/app/main.py").app)
    response = client.get("/api/pnl/bridge", params={"report_date": "2025-12-31"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["result_meta"]["vendor_status"] == "ok"
    get_settings.cache_clear()
