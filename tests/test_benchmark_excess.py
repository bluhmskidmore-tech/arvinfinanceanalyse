from __future__ import annotations

from decimal import Decimal

import pytest

from backend.app.core_finance.benchmark_excess import compute_benchmark_excess


def _summary() -> dict[str, object]:
    # port_ret = 20 / 1000 = 0.02
    # dy = +0.002 (parallel shift up), d_bench (CDB) = 7.0
    # bench_ret = -7.0 * 0.002 = -0.014
    # excess_bp = (0.02 - (-0.014)) * 10000 = 340
    # dur_diff = 5 - 7 = -2 ; duration_effect_bp = -(-2) * 0.002 * 10000 = 40
    # curve = spread = 0 (placeholder) -> selection(residual) = 340 - 40 = 300
    # M3（2026-08 审计）：模块已弃用（无生产调用方），每次调用必须伴随 DeprecationWarning。
    with pytest.warns(DeprecationWarning, match="无生产调用方"):
        return compute_benchmark_excess(
            period_pnl=Decimal("20"),
            start_total_mv=Decimal("1000"),
            portfolio_mod_duration=Decimal("5"),
            gov_curve_start={"1Y": Decimal("0.03"), "3Y": Decimal("0.03"), "5Y": Decimal("0.03"), "10Y": Decimal("0.03")},
            gov_curve_end={"1Y": Decimal("0.032"), "3Y": Decimal("0.032"), "5Y": Decimal("0.032"), "10Y": Decimal("0.032")},
            benchmark_id="CDB_INDEX",
        )


def test_compute_benchmark_excess_is_deprecated_dead_code() -> None:
    """M3：core 版 compute_benchmark_excess 是危险死代码——生产用 read_models
    同名实现（入参与单位约定不同）。锁定：调用即抛 DeprecationWarning，
    且警告信息指向 read_models 替代实现。"""
    with pytest.warns(DeprecationWarning, match="read_models"):
        compute_benchmark_excess(
            period_pnl=Decimal("0"),
            start_total_mv=Decimal("1"),
            portfolio_mod_duration=Decimal("5"),
            gov_curve_start={},
            gov_curve_end={},
        )


def test_selection_effect_is_unexplained_residual_and_can_be_nonzero() -> None:
    summary = _summary()
    assert summary["duration_effect_bp"] == pytest.approx(40.0)
    assert summary["curve_effect_bp"] == 0.0
    assert summary["spread_effect_bp"] == 0.0
    # selection is the honest unexplained residual (excess - explained factors), non-zero here
    assert summary["selection_effect_bp"] == pytest.approx(300.0)
    assert summary["selection_effect_bp"] != 0.0


def test_no_fake_zero_reconciliation_field() -> None:
    summary = _summary()
    # The always-zero fake reconciliation field must be gone.
    assert "recon_error_bp" not in summary


def test_explained_excess_excludes_residual_so_it_is_not_trivially_excess() -> None:
    summary = _summary()
    # explained = duration + curve + spread only (does NOT swallow the residual)
    assert summary["explained_excess_bp"] == pytest.approx(40.0)
    assert summary["explained_excess_bp"] != summary["excess_return_bp"]
    # excess = explained + residual holds by construction
    assert summary["explained_excess_bp"] + summary["selection_effect_bp"] == pytest.approx(
        summary["excess_return_bp"]
    )


def test_curve_and_spread_placeholder_zero_is_surfaced_in_warnings() -> None:
    summary = _summary()
    warnings = summary["warnings"]
    assert any("CURVE_SPREAD" in str(w) for w in warnings)
