from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from backend.app.governance.settings import get_settings
from tests.helpers import load_module
from tests.test_bond_analytics_curve_effects import _seed_curve_rows
from tests.test_bond_analytics_materialize_flow import REPORT_DATE, _seed_bond_snapshot_rows


def _configure_and_materialize(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    _seed_bond_snapshot_rows(str(duckdb_path))
    task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    return duckdb_path, governance_dir, task_mod


def _numeric_raw(value: dict[str, object]) -> Decimal:
    return Decimal(str(value["raw"]))


def test_bond_analytics_service_returns_empty_warning_without_fact_data(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_return_decomposition(date(2026, 3, 31), "MoM", "all", "all")

    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result"]["bond_count"] == 0
    assert "not yet populated" in payload["result"]["warnings"][0]
    get_settings.cache_clear()


def test_apply_vendor_meta_update_merges_lineage_and_status(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )
    meta = service_mod.build_formal_result_meta(
        trace_id="tr_test_vendor_state",
        result_kind="bond_analytics.return_decomposition",
        cache_version="cv_base",
        source_version="sv_base",
        rule_version="rv_base",
        vendor_version="vv_base",
        source_surface="bond_analytics",
    )

    updated = service_mod._apply_vendor_meta_update(
        meta,
        curve_snapshots=[
            {
                "source_version": "sv_curve",
                "rule_version": "rv_curve",
                "vendor_version": "vv_curve",
                "vendor_name": "choice",
            }
        ],
        cache_version_suffix=service_mod.YIELD_CURVE_CACHE_VERSION,
        curve_unavailable=False,
        curve_latest_fallback=True,
        fx_unavailable=False,
        fx_latest_fallback=False,
    )

    assert updated.source_version == "choice__sv_base__sv_curve"
    assert updated.rule_version == "rv_base__rv_curve"
    assert updated.vendor_version == "vv_base__vv_curve"
    assert updated.cache_version == f"cv_base__{service_mod.YIELD_CURVE_CACHE_VERSION}"
    assert updated.vendor_status == "vendor_stale"
    assert updated.fallback_mode == "latest_snapshot"
    get_settings.cache_clear()


def test_bond_analytics_service_returns_available_report_dates(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.bond_analytics_dates_envelope()

    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["result_kind"] == "bond_analytics.dates"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["result"]["report_dates"] == [REPORT_DATE]
    assert payload["result_meta"]["source_version"]
    assert payload["result_meta"]["rule_version"]
    get_settings.cache_clear()


def test_bond_analytics_service_uses_shared_formal_result_runtime_helper():
    path = Path(__file__).resolve().parents[1] / "backend" / "app" / "services" / "bond_analytics_service.py"
    src = path.read_text(encoding="utf-8")

    assert "backend.app.services.formal_result_runtime" in src
    assert "build_formal_result_meta_from_lineage" in src


def test_bond_analytics_service_keeps_intentional_local_meta_for_complex_vendor_lineage_paths():
    path = Path(__file__).resolve().parents[1] / "backend" / "app" / "services" / "bond_analytics_service.py"
    src = path.read_text(encoding="utf-8")

    assert "def _meta(" in src
    assert "def _apply_vendor_meta_update(" in src
    assert "bond_analytics.return_decomposition" in src
    assert "bond_analytics.credit_spread_migration" in src


def test_bond_analytics_dates_envelope_resolves_manifest_lineage_not_only_latest_row_date(
    tmp_path,
    monkeypatch,
):
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )
    calls: list[dict[str, str]] = []

    def _capture(**kwargs):
        calls.append(kwargs)
        return {
            "source_version": "sv_manifest_test",
            "rule_version": "rv_manifest_test",
            "cache_version": service_mod.CACHE_VERSION,
            "vendor_version": "vv_none",
        }

    monkeypatch.setattr(service_mod, "resolve_formal_dates_lineage", _capture)

    payload = service_mod.bond_analytics_dates_envelope()

    assert len(calls) == 1
    assert calls[0]["cache_key"] == service_mod.CACHE_KEY
    assert calls[0]["report_dates"] == [REPORT_DATE]
    assert Path(str(calls[0]["governance_dir"])).resolve() == (tmp_path / "governance").resolve()
    assert payload["result_meta"]["source_version"] == "sv_manifest_test"
    get_settings.cache_clear()


def test_bond_analytics_dates_envelope_falls_back_to_local_lineage_when_manifest_missing(
    tmp_path,
    monkeypatch,
):
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    def _fallback_dates_lineage(**kwargs):
        report_dates = kwargs["report_dates"]
        return kwargs["fallback_lineage_loader"](report_dates[0])

    monkeypatch.setattr(service_mod, "resolve_formal_dates_lineage", _fallback_dates_lineage)

    payload = service_mod.bond_analytics_dates_envelope()

    assert payload["result_meta"]["source_version"] == "sv_bond_snap_1"
    assert payload["result_meta"]["rule_version"] == service_mod.RULE_VERSION
    assert payload["result_meta"]["cache_version"] == service_mod.CACHE_VERSION
    assert payload["result"]["report_dates"] == [REPORT_DATE]
    get_settings.cache_clear()


def test_bond_analytics_return_decomposition_aggregates_carry_and_buckets(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_return_decomposition(date(2026, 3, 31), "MoM", "all", "all")
    result = payload["result"]

    expected_days = Decimal("31")
    expected_carry = (
        Decimal("0.02") * Decimal("100") * expected_days / Decimal("365")
        + Decimal("0.03") * Decimal("200") * expected_days / Decimal("365")
        + Decimal("0.04") * Decimal("150") * expected_days / Decimal("365")
    )

    assert payload["result_meta"]["source_version"] == "sv_bond_snap_1"
    assert payload["result_meta"]["rule_version"] == "rv_bond_analytics_formal_materialize_v1"
    assert result["bond_count"] == 3
    assert _numeric_raw(result["total_market_value"]) == Decimal("429")
    assert _numeric_raw(result["carry"]).quantize(Decimal("0.00000001")) == expected_carry.quantize(Decimal("0.00000001"))
    assert result["actual_pnl"]["raw"] == result["carry"]["raw"]
    assert result["explained_pnl"]["raw"] == result["carry"]["raw"]
    assert {row["asset_class"] for row in result["by_asset_class"]} == {"credit", "rate"}
    assert {row["asset_class"] for row in result["by_accounting_class"]} == {"AC", "OCI", "TPL"}
    assert len(result["bond_details"]) == 3
    assert any("Phase 3 placeholder" in warning for warning in result["warnings"])
    get_settings.cache_clear()


def test_benchmark_excess_with_curve_data(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    _seed_curve_rows(str(tmp_path / "moss.duckdb"))
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_benchmark_excess(date(2026, 3, 31), "MoM", "TREASURY_INDEX")
    result = payload["result"]

    assert _numeric_raw(result["portfolio_duration"]) > Decimal("0")
    assert _numeric_raw(result["benchmark_duration"]) > Decimal("0")
    assert _numeric_raw(result["portfolio_return"]) != Decimal("0")
    assert _numeric_raw(result["benchmark_return"]) != Decimal("0")
    assert _numeric_raw(result["excess_return"]) != Decimal("0")
    assert _numeric_raw(result["explained_excess"]) != Decimal("0")
    assert any(
        _numeric_raw(result[field]) != Decimal("0")
        for field in ("duration_effect", "curve_effect", "selection_effect")
    )
    assert result["warnings"] == []
    get_settings.cache_clear()


def test_benchmark_excess_with_cdb_curve_data(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    _seed_curve_rows(str(tmp_path / "moss.duckdb"))
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_benchmark_excess(date(2026, 3, 31), "MoM", "CDB_INDEX")
    result = payload["result"]

    assert _numeric_raw(result["benchmark_duration"]) > Decimal("0")
    assert _numeric_raw(result["benchmark_return"]) != Decimal("0")
    assert _numeric_raw(result["excess_return"]) != Decimal("0")
    assert payload["result_meta"].get("vendor_status", "ok") == "ok"
    assert "sv_cdb_current" in payload["result_meta"]["source_version"]
    assert result["warnings"] == []
    get_settings.cache_clear()


def test_benchmark_excess_with_aaa_curve_data(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    _seed_curve_rows(str(tmp_path / "moss.duckdb"))
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_benchmark_excess(date(2026, 3, 31), "MoM", "AAA_CREDIT_INDEX")
    result = payload["result"]

    assert _numeric_raw(result["benchmark_duration"]) > Decimal("0")
    assert _numeric_raw(result["benchmark_return"]) != Decimal("0")
    assert _numeric_raw(result["spread_effect"]) != Decimal("0")
    assert payload["result_meta"].get("vendor_status", "ok") == "ok"
    assert "sv_aaa_current" in payload["result_meta"]["source_version"]
    assert result["warnings"] == []
    get_settings.cache_clear()


def test_benchmark_excess_portfolio_return_is_invariant_across_benchmarks(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    _seed_curve_rows(str(tmp_path / "moss.duckdb"))
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    treasury_payload = service_mod.get_benchmark_excess(date(2026, 3, 31), "MoM", "TREASURY_INDEX")
    cdb_payload = service_mod.get_benchmark_excess(date(2026, 3, 31), "MoM", "CDB_INDEX")
    aaa_payload = service_mod.get_benchmark_excess(date(2026, 3, 31), "MoM", "AAA_CREDIT_INDEX")

    assert treasury_payload["result"]["portfolio_return"] == cdb_payload["result"]["portfolio_return"]
    assert cdb_payload["result"]["portfolio_return"] == aaa_payload["result"]["portfolio_return"]
    get_settings.cache_clear()


def test_benchmark_excess_without_curve_data_returns_zero_with_warning(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_benchmark_excess(date(2026, 3, 31), "MoM", "TREASURY_INDEX")
    result = payload["result"]

    assert _numeric_raw(result["portfolio_duration"]) > Decimal("0")
    assert _numeric_raw(result["benchmark_duration"]) == Decimal("0")
    assert _numeric_raw(result["portfolio_return"]) == Decimal("0")
    assert _numeric_raw(result["benchmark_return"]) == Decimal("0")
    assert _numeric_raw(result["excess_return"]) == Decimal("0")
    assert any("Benchmark" in warning or "curve" in warning for warning in result["warnings"])
    get_settings.cache_clear()


def test_bond_analytics_krd_curve_risk_aggregates_dv01_and_scenarios(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_krd_curve_risk(date(2026, 3, 31), "standard")
    result = payload["result"]

    assert _numeric_raw(result["portfolio_duration"]) > Decimal("0")
    assert _numeric_raw(result["portfolio_modified_duration"]) > Decimal("0")
    assert _numeric_raw(result["portfolio_dv01"]) > Decimal("0")
    assert len(result["krd_buckets"]) == 3
    assert {row["tenor"] for row in result["krd_buckets"]} == {"1Y", "5Y", "10Y"}
    assert len(result["scenarios"]) == len(service_mod.STANDARD_SCENARIOS)
    assert {row["asset_class"] for row in result["by_asset_class"]} == {"credit", "rate"}
    get_settings.cache_clear()


def test_bond_analytics_credit_spread_migration_uses_credit_subset_and_concentration(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_credit_spread_migration(date(2026, 3, 31), "10,25")
    result = payload["result"]

    assert result["credit_bond_count"] == 2
    assert _numeric_raw(result["credit_market_value"]) == Decimal("330")
    assert _numeric_raw(result["credit_weight"]).quantize(Decimal("0.00000001")) == Decimal("0.76923077")
    assert _numeric_raw(result["rating_aa_and_below_weight"]) == Decimal("0")
    assert _numeric_raw(result["spread_dv01"]) > Decimal("0")
    assert _numeric_raw(result["weighted_avg_spread"]) == Decimal("0")
    assert len(result["spread_scenarios"]) == 4
    assert _numeric_raw(result["oci_credit_exposure"]) == Decimal("190")
    assert result["concentration_by_issuer"]["dimension"] == "issuer"
    assert any("No aaa_credit curve available" in warning or "No treasury curve available" in warning for warning in result["warnings"])
    assert any("Spread level input unavailable" in warning for warning in result["warnings"])
    get_settings.cache_clear()


def test_bond_analytics_accounting_audit_uses_fact_rows(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_accounting_class_audit(date(2026, 3, 31))
    result = payload["result"]

    assert result["total_positions"] == 3
    assert result["distinct_asset_classes"] == 2
    assert result["divergent_asset_classes"] == 0
    assert len(result["rows"]) == 2
    assert result["rows"][0]["asset_class"] in {"信用债", "利率债"}
    get_settings.cache_clear()


def test_bond_analytics_empty_date_uses_empty_lineage_not_latest_manifest(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_return_decomposition(date(2026, 4, 30), "MoM", "all", "all")

    assert payload["result_meta"]["source_version"] == "sv_bond_analytics_empty"
    assert payload["result"]["bond_count"] == 0
    get_settings.cache_clear()


def _minimal_return_summary_for_trading_overlay() -> dict:
    z = Decimal("0")
    one = Decimal("1")
    row = {
        "instrument_code": "TB-001",
        "instrument_name": "T",
        "asset_class_std": "rate",
        "accounting_class": "AC",
        "portfolio_name": "组合利率",
        "cost_center": "CC-RATE",
        "market_value": Decimal("100"),
        "carry": one,
        "roll_down": z,
        "rate_effect": z,
        "spread_effect": z,
        "convexity_effect": z,
        "fx_effect": z,
        "trading": z,
        "total": one,
    }
    return {
        "carry_total": one,
        "roll_down_total": z,
        "rate_effect_total": z,
        "spread_effect_total": z,
        "convexity_effect_total": z,
        "fx_effect_total": z,
        "trading_total": z,
        "total_market_value": Decimal("100"),
        "bond_count": 1,
        "bond_details": [row],
        "by_asset_class": [],
        "by_accounting_class": [],
    }


def test_overlay_return_decomposition_trading_pnl517_mom_single_report_date(tmp_path, monkeypatch):
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )
    key = "TB-001::组合利率::CC-RATE"

    class FakePnl:
        def __init__(self, _path: str) -> None:
            pass

        def list_union_report_dates(self) -> list[str]:
            return ["2026-03-31"]

        def merged_capital_gain_517_by_position_for_dates(self, dates: list[str]) -> dict[str, Decimal]:
            assert dates == ["2026-03-31"]
            return {key: Decimal("2.5")}

    monkeypatch.setattr(service_mod, "PnlRepository", FakePnl)
    summary = _minimal_return_summary_for_trading_overlay()
    out, _warnings, wd = service_mod._overlay_return_decomposition_trading_pnl517(
        summary,
        period_type="MoM",
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        duckdb_path=str(tmp_path / "moss.duckdb"),
    )
    assert out["bond_details"][0]["trading"] == Decimal("2.5")
    assert out["trading_total"] == Decimal("2.5")
    assert out["bond_details"][0]["total"] == Decimal("3.5")
    rate = next(b for b in out["by_asset_class"] if b["key"] == "rate")
    assert rate["trading"] == Decimal("2.5")
    codes = [d.get("code") for d in wd]
    assert "return_decomposition_trading_pnl517_formal" in codes
    assert "return_decomposition_trading_pnl517_multi_month_aggregate" not in codes


def test_overlay_return_decomposition_trading_pnl517_ytd_sums_multiple_report_dates(tmp_path, monkeypatch):
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )
    key = "TB-001::组合利率::CC-RATE"

    class FakePnl:
        def __init__(self, _path: str) -> None:
            pass

        def list_union_report_dates(self) -> list[str]:
            return ["2026-03-31", "2026-02-28", "2026-01-31", "2025-12-31"]

        def merged_capital_gain_517_by_position_for_dates(self, dates: list[str]) -> dict[str, Decimal]:
            assert set(dates) == {"2026-01-31", "2026-02-28", "2026-03-31"}
            return {key: Decimal("9")}

    monkeypatch.setattr(service_mod, "PnlRepository", FakePnl)
    summary = _minimal_return_summary_for_trading_overlay()
    out, _warnings, wd = service_mod._overlay_return_decomposition_trading_pnl517(
        summary,
        period_type="YTD",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
        duckdb_path=str(tmp_path / "moss.duckdb"),
    )
    assert out["bond_details"][0]["trading"] == Decimal("9")
    assert out["trading_total"] == Decimal("9")
    codes = [d.get("code") for d in wd]
    assert "return_decomposition_trading_pnl517_formal" in codes
    assert "return_decomposition_trading_pnl517_multi_month_aggregate" in codes


def test_overlay_return_decomposition_trading_pnl517_ttm_sums_multiple_report_dates(tmp_path, monkeypatch):
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )
    key = "TB-001::组合利率::CC-RATE"

    class FakePnl:
        def __init__(self, _path: str) -> None:
            pass

        def list_union_report_dates(self) -> list[str]:
            return ["2026-03-31", "2025-03-31"]

        def merged_capital_gain_517_by_position_for_dates(self, dates: list[str]) -> dict[str, Decimal]:
            assert set(dates) == {"2025-03-31", "2026-03-31"}
            return {key: Decimal("4")}

    monkeypatch.setattr(service_mod, "PnlRepository", FakePnl)
    summary = _minimal_return_summary_for_trading_overlay()
    out, _warnings, wd = service_mod._overlay_return_decomposition_trading_pnl517(
        summary,
        period_type="TTM",
        period_start=date(2025, 3, 31),
        period_end=date(2026, 3, 31),
        duckdb_path=str(tmp_path / "moss.duckdb"),
    )
    assert out["bond_details"][0]["trading"] == Decimal("4")
    assert "return_decomposition_trading_pnl517_multi_month_aggregate" in {d.get("code") for d in wd}


def test_overlay_return_decomposition_trading_pnl517_ytd_degrades_when_no_report_dates_in_period(
    tmp_path, monkeypatch,
):
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    class FakePnl:
        def __init__(self, _path: str) -> None:
            pass

        def list_union_report_dates(self) -> list[str]:
            return ["2025-12-31"]

        def merged_capital_gain_517_by_position_for_dates(self, dates: list[str]) -> dict[str, Decimal]:
            raise AssertionError("merge should not run when date list is empty")

    monkeypatch.setattr(service_mod, "PnlRepository", FakePnl)
    summary = _minimal_return_summary_for_trading_overlay()
    out, _warnings, wd = service_mod._overlay_return_decomposition_trading_pnl517(
        summary,
        period_type="YTD",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 3, 31),
        duckdb_path=str(tmp_path / "moss.duckdb"),
    )
    assert out["bond_details"][0]["trading"] == Decimal("0")
    assert out["trading_total"] == Decimal("0")
    codes = {d.get("code") for d in wd}
    assert "return_decomposition_trading_pnl517_no_fact_dates_in_period" in codes
