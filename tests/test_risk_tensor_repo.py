from __future__ import annotations

from datetime import date
from decimal import Decimal

from tests.helpers import load_module


def test_risk_tensor_repo_round_trip_preserves_lineage_and_warnings(tmp_path):
    repo_mod = load_module(
        "backend.app.repositories.risk_tensor_repo",
        "backend/app/repositories/risk_tensor_repo.py",
    )
    core_mod = load_module(
        "backend.app.core_finance.risk_tensor",
        "backend/app/core_finance/risk_tensor.py",
    )
    repo = repo_mod.RiskTensorRepository(str(tmp_path / "moss.duckdb"))

    tensor = core_mod.PortfolioRiskTensor(
        report_date=date(2026, 3, 31),
        portfolio_dv01=Decimal("1.25000000"),
        krd_1y=Decimal("0.25000000"),
        krd_3y=Decimal("0"),
        krd_5y=Decimal("1.00000000"),
        krd_7y=Decimal("0"),
        krd_10y=Decimal("0"),
        krd_30y=Decimal("0"),
        cs01=Decimal("0.75000000"),
        portfolio_convexity=Decimal("2.50000000"),
        portfolio_modified_duration=Decimal("1.50000000"),
        issuer_concentration_hhi=Decimal("0.50000000"),
        issuer_top5_weight=Decimal("1.00000000"),
        liquidity_gap_30d=Decimal("10.00000000"),
        liquidity_gap_90d=Decimal("10.00000000"),
        liquidity_gap_30d_ratio=Decimal("0.10000000"),
        total_market_value=Decimal("100.00000000"),
        bond_count=2,
        quality_flag="warning",
        warnings=["synthetic warning"],
    )

    repo.replace_risk_tensor_row(
        report_date="2026-03-31",
        tensor=tensor,
        source_version="sv_risk_tensor__sv_bond_snap_1",
        upstream_source_version="sv_bond_snap_1",
        rule_version="rv_risk_tensor_formal_materialize_v1",
        cache_version="cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v1",
        trace_id="trace_risk_tensor_20260331",
    )

    row = repo.fetch_risk_tensor_row("2026-03-31")

    assert row is not None
    assert row["source_version"] == "sv_risk_tensor__sv_bond_snap_1"
    assert row["upstream_source_version"] == "sv_bond_snap_1"
    assert row["rule_version"] == "rv_risk_tensor_formal_materialize_v1"
    assert row["cache_version"] == "cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v1"
    assert row["quality_flag"] == "warning"
    assert row["warnings"] == ["synthetic warning"]
    assert row["bond_count"] == 2
    assert row["portfolio_dv01"] == Decimal("1.25000000")
    assert row["portfolio_modified_duration"] == Decimal("1.50000000")
    assert row["liquidity_gap_30d_ratio"] == Decimal("0.10000000")
