from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)
from tests.helpers import load_module
from tests.test_bond_analytics_curve_effects import _seed_curve_rows
from tests.test_bond_analytics_materialize_flow import (
    REPORT_DATE,
    _seed_bond_snapshot_rows,
)


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


def _numeric_raw(value: dict[str, object] | str) -> Decimal:
    if isinstance(value, dict):
        return Decimal(str(value["raw"]))
    return Decimal(str(value))


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


def test_bond_analytics_refresh_status_invalidates_matching_ttl_caches(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )
    settings = get_settings()

    return_key = ("2026-03-31", "MoM", "all", "all")
    other_return_key = ("2026-04-30", "MoM", "all", "all")
    action_key = ("2026-03-31", "MoM")
    other_action_key = ("2026-04-30", "MoM")
    service_mod._return_decomposition_cache.set(return_key, {"value": "stale-return"})
    service_mod._return_decomposition_cache.set(other_return_key, {"value": "keep-return"})
    service_mod._action_attribution_cache.set(action_key, {"value": "stale-action"})
    service_mod._action_attribution_cache.set(other_action_key, {"value": "keep-action"})

    GovernanceRepository(base_dir=governance_dir).append(
        CACHE_BUILD_RUN_STREAM,
        {
            "run_id": "bond-cache-invalidate",
            "job_name": service_mod.JOB_NAME,
            "status": "completed",
            "cache_key": service_mod.CACHE_KEY,
            "report_date": "2026-03-31",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    payload = service_mod.bond_analytics_refresh_status(
        settings,
        run_id="bond-cache-invalidate",
    )

    assert payload["status"] == "completed"
    assert service_mod._return_decomposition_cache.get(return_key) == (False, None)
    assert service_mod._action_attribution_cache.get(action_key) == (False, None)
    assert service_mod._return_decomposition_cache.get(other_return_key) == (
        True,
        {"value": "keep-return"},
    )
    assert service_mod._action_attribution_cache.get(other_action_key) == (
        True,
        {"value": "keep-action"},
    )
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
    assert _numeric_raw(result["actual_pnl"]) == _numeric_raw(result["carry"])
    assert _numeric_raw(result["explained_pnl"]) == _numeric_raw(result["carry"])
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


def test_bond_analytics_dv01_risk_defaults_to_oci_scope_and_parallel_shocks(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_dv01_risk(date(2026, 3, 31))
    result = payload["result"]

    assert payload["result_meta"]["result_kind"] == "bond_analytics.dv01_risk"
    assert result["accounting_class"] == "OCI"
    assert result["position_count"] == 1
    assert _numeric_raw(result["total_face_value"]) == Decimal("200")
    assert _numeric_raw(result["total_market_value"]) == Decimal("190")
    assert _numeric_raw(result["total_dv01"]) > Decimal("0")
    assert _numeric_raw(result["face_weighted_modified_duration"]) > Decimal("0")
    assert [row["shock_bp"]["raw"] for row in result["shock_scenarios"]] == [1.0, -1.0, 10.0, -10.0, 25.0, -25.0, 50.0, -50.0]
    up_10 = next(row for row in result["shock_scenarios"] if row["shock_bp"]["raw"] == 10.0)
    down_10 = next(row for row in result["shock_scenarios"] if row["shock_bp"]["raw"] == -10.0)
    assert _numeric_raw(up_10["estimated_pnl"]) == -_numeric_raw(result["total_dv01"]) * Decimal("10")
    assert _numeric_raw(down_10["estimated_pnl"]) == _numeric_raw(result["total_dv01"]) * Decimal("10")
    assert [row["tenor_bucket"] for row in result["tenor_buckets"]] == ["5Y"]
    assert result["top_bonds"][0]["instrument_code"] == "CB-001"
    assert result["top_issuers"][0]["issuer_name"]
    get_settings.cache_clear()


def test_bond_analytics_dv01_risk_all_scope_groups_tenors_and_sorts_by_abs_dv01(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_dv01_risk(date(2026, 3, 31), accounting_class="all", top_n=2, shock_bps="5")
    result = payload["result"]

    assert result["accounting_class"] == "all"
    assert result["position_count"] == 3
    assert {row["tenor_bucket"] for row in result["tenor_buckets"]} == {"1Y", "5Y", "10Y"}
    assert len(result["top_bonds"]) == 2
    top_dv01_values = [_numeric_raw(row["dv01"]).copy_abs() for row in result["top_bonds"]]
    assert top_dv01_values == sorted(top_dv01_values, reverse=True)
    assert [row["shock_bp"]["raw"] for row in result["shock_scenarios"]] == [5.0, -5.0]
    assert _numeric_raw(result["total_face_value"]) == Decimal("450")
    get_settings.cache_clear()


def test_bond_analytics_dv01_all_scope_warns_when_unmapped_accounting_class_is_included(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )
    rows = [
        {
            "report_date": "2026-03-31",
            "instrument_code": "OCI-001",
            "instrument_name": "OCI Bond",
            "issuer_name": "Issuer O",
            "rating": "AAA",
            "tenor_bucket": "3Y",
            "accounting_class": "OCI",
            "face_value": Decimal("100"),
            "market_value": Decimal("101"),
            "modified_duration": Decimal("3"),
            "dv01": Decimal("30"),
            "source_version": "sv",
            "rule_version": "rv",
            "trace_id": "tr_oci",
        },
        {
            "report_date": "2026-03-31",
            "instrument_code": "UNK-001",
            "instrument_name": "Unmapped Bond",
            "issuer_name": "Issuer U",
            "rating": "AA",
            "tenor_bucket": "10Y",
            "accounting_class": "other",
            "face_value": Decimal("200"),
            "market_value": Decimal("202"),
            "modified_duration": Decimal("6"),
            "dv01": Decimal("120"),
            "source_version": "sv",
            "rule_version": "rv",
            "trace_id": "tr_other",
        },
    ]

    class FakeRepo:
        def fetch_bond_analytics_rows(self, *, report_date, accounting_class="all", **_kwargs):
            scoped = list(rows)
            if accounting_class != "all":
                scoped = [row for row in scoped if row["accounting_class"] == accounting_class]
            return scoped

    monkeypatch.setattr(service_mod, "_repo", lambda: FakeRepo())
    monkeypatch.setattr(
        service_mod,
        "_lineage",
        lambda _report_date, _rows: {
            "source_version": "sv_test",
            "rule_version": "rv_test",
            "cache_version": "cv_test",
            "vendor_version": "vv_test",
        },
    )

    risk_payload = service_mod.get_dv01_risk(date(2026, 3, 31), accounting_class="all")
    reconciliation_payload = service_mod.get_dv01_reconciliation(date(2026, 3, 31), accounting_class="all")

    assert risk_payload["result"]["accounting_class"] == "all"
    assert any("未映射会计分类" in warning for warning in risk_payload["result"]["warnings"])
    assert any("other" in warning for warning in risk_payload["result"]["warnings"])
    assert reconciliation_payload["result"]["accounting_class"] == "all"
    assert any("未映射会计分类" in warning for warning in reconciliation_payload["result"]["warnings"])
    assert any("other" in warning for warning in reconciliation_payload["result"]["warnings"])
    get_settings.cache_clear()


def test_bond_analytics_dv01_risk_empty_scope_returns_warning(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_dv01_risk(date(2026, 4, 30), accounting_class="OCI")
    result = payload["result"]

    assert result["accounting_class"] == "OCI"
    assert result["position_count"] == 0
    assert _numeric_raw(result["total_dv01"]) == Decimal("0")
    assert result["shock_scenarios"] == []
    assert result["tenor_buckets"] == []
    assert result["top_bonds"] == []
    assert result["top_issuers"] == []
    assert result["warnings"]
    get_settings.cache_clear()


def test_bond_analytics_dv01_reconciliation_defaults_to_oci_rows_and_totals(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_dv01_reconciliation(date(2026, 3, 31))
    result = payload["result"]

    assert payload["result_meta"]["result_kind"] == "bond_analytics.dv01_reconciliation"
    assert result["accounting_class"] == "OCI"
    assert result["position_count"] == 1
    assert result["rows"][0]["instrument_code"] == "CB-001"
    assert result["rows"][0]["accounting_class"] == "OCI"
    assert result["rows"][0]["source_version"]
    assert result["rows"][0]["rule_version"]
    assert result["rows"][0]["trace_id"]
    assert _numeric_raw(result["total_face_value"]) == sum(_numeric_raw(row["face_value"]) for row in result["rows"])
    assert _numeric_raw(result["total_market_value"]) == sum(_numeric_raw(row["market_value"]) for row in result["rows"])
    assert _numeric_raw(result["total_dv01"]) == sum(_numeric_raw(row["dv01"]) for row in result["rows"])
    get_settings.cache_clear()


def test_bond_analytics_dv01_reconciliation_all_scope_and_abs_share(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_dv01_reconciliation(date(2026, 3, 31), accounting_class="all")
    result = payload["result"]

    assert result["accounting_class"] == "all"
    assert result["position_count"] == 3
    assert {row["accounting_class"] for row in result["rows"]} == {"AC", "OCI", "TPL"}
    total_abs_dv01 = sum(_numeric_raw(row["dv01"]).copy_abs() for row in result["rows"])
    assert total_abs_dv01 > Decimal("0")
    for row in result["rows"]:
        expected_share = _numeric_raw(row["dv01"]).copy_abs() / total_abs_dv01
        assert _numeric_raw(row["dv01_share"]).quantize(Decimal("0.00000001")) == expected_share.quantize(Decimal("0.00000001"))
    get_settings.cache_clear()


def test_bond_analytics_dv01_reconciliation_empty_scope_returns_warning(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_dv01_reconciliation(date(2026, 4, 30), accounting_class="OCI")
    result = payload["result"]

    assert result["accounting_class"] == "OCI"
    assert result["position_count"] == 0
    assert result["rows"] == []
    assert _numeric_raw(result["total_dv01"]) == Decimal("0")
    assert result["warnings"]
    get_settings.cache_clear()


def test_bond_analytics_dv01_movement_explains_oci_delta_with_prior_report_date(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )
    previous_date = "2026-02-28"
    current_date = "2026-03-31"
    rows_by_date = {
        previous_date: [
            {
                "report_date": previous_date,
                "instrument_code": "A-001",
                "instrument_name": "Alpha Bond",
                "issuer_name": "Issuer A",
                "rating": "AAA",
                "tenor_bucket": "3-5Y",
                "accounting_class": "OCI",
                "face_value": Decimal("1000000"),
                "market_value": Decimal("1005000"),
                "modified_duration": Decimal("3"),
                "dv01": Decimal("300"),
                "source_version": "sv_prev",
                "rule_version": "rv_prev",
                "trace_id": "tr_prev_a",
            },
            {
                "report_date": previous_date,
                "instrument_code": "B-001",
                "instrument_name": "Beta Bond",
                "issuer_name": "Issuer B",
                "rating": "AA+",
                "tenor_bucket": "1-3Y",
                "accounting_class": "OCI",
                "face_value": Decimal("500000"),
                "market_value": Decimal("501000"),
                "modified_duration": Decimal("2"),
                "dv01": Decimal("100"),
                "source_version": "sv_prev",
                "rule_version": "rv_prev",
                "trace_id": "tr_prev_b",
            },
            {
                "report_date": previous_date,
                "instrument_code": "X-001",
                "instrument_name": "Exit Bond",
                "issuer_name": "Issuer X",
                "rating": "AA",
                "tenor_bucket": "5-7Y",
                "accounting_class": "OCI",
                "face_value": Decimal("100000"),
                "market_value": Decimal("100000"),
                "modified_duration": Decimal("5"),
                "dv01": Decimal("50"),
                "source_version": "sv_prev",
                "rule_version": "rv_prev",
                "trace_id": "tr_prev_x",
            },
            {
                "report_date": previous_date,
                "instrument_code": "C-001",
                "instrument_name": "Class Change Bond",
                "issuer_name": "Issuer C",
                "rating": "AAA",
                "tenor_bucket": "3-5Y",
                "accounting_class": "TPL",
                "face_value": Decimal("100000"),
                "market_value": Decimal("100000"),
                "modified_duration": Decimal("4"),
                "dv01": Decimal("40"),
                "source_version": "sv_prev",
                "rule_version": "rv_prev",
                "trace_id": "tr_prev_c",
            },
        ],
        current_date: [
            {
                "report_date": current_date,
                "instrument_code": "A-001",
                "instrument_name": "Alpha Bond",
                "issuer_name": "Issuer A",
                "rating": "AAA",
                "tenor_bucket": "3-5Y",
                "accounting_class": "OCI",
                "face_value": Decimal("1100000"),
                "market_value": Decimal("1110000"),
                "modified_duration": Decimal("3.5"),
                "dv01": Decimal("390"),
                "source_version": "sv_current",
                "rule_version": "rv_current",
                "trace_id": "tr_current_a",
            },
            {
                "report_date": current_date,
                "instrument_code": "B-001",
                "instrument_name": "Beta Bond",
                "issuer_name": "Issuer B",
                "rating": "AA+",
                "tenor_bucket": "1-3Y",
                "accounting_class": "OCI",
                "face_value": Decimal("500000"),
                "market_value": Decimal("502000"),
                "modified_duration": Decimal("2"),
                "dv01": Decimal("100"),
                "source_version": "sv_current",
                "rule_version": "rv_current",
                "trace_id": "tr_current_b",
            },
            {
                "report_date": current_date,
                "instrument_code": "N-001",
                "instrument_name": "New Bond",
                "issuer_name": "Issuer N",
                "rating": "AA",
                "tenor_bucket": "5-7Y",
                "accounting_class": "OCI",
                "face_value": Decimal("200000"),
                "market_value": Decimal("201000"),
                "modified_duration": Decimal("5"),
                "dv01": Decimal("100"),
                "source_version": "sv_current",
                "rule_version": "rv_current",
                "trace_id": "tr_current_n",
            },
            {
                "report_date": current_date,
                "instrument_code": "C-001",
                "instrument_name": "Class Change Bond",
                "issuer_name": "Issuer C",
                "rating": "AAA",
                "tenor_bucket": "3-5Y",
                "accounting_class": "OCI",
                "face_value": Decimal("100000"),
                "market_value": Decimal("100000"),
                "modified_duration": Decimal("4"),
                "dv01": Decimal("40"),
                "source_version": "sv_current",
                "rule_version": "rv_current",
                "trace_id": "tr_current_c",
            },
        ],
    }

    class FakeRepo:
        def list_report_dates(self):
            return [current_date, previous_date]

        def fetch_bond_analytics_rows(self, *, report_date, accounting_class="all", **_kwargs):
            rows = list(rows_by_date.get(report_date, []))
            if accounting_class != "all":
                rows = [row for row in rows if row["accounting_class"] == accounting_class]
            return rows

    monkeypatch.setattr(service_mod, "_repo", lambda: FakeRepo())
    monkeypatch.setattr(
        service_mod,
        "_lineage",
        lambda _report_date, _rows: {
            "source_version": "sv_test",
            "rule_version": "rv_test",
            "cache_version": "cv_test",
            "vendor_version": "vv_test",
        },
    )

    payload = service_mod.get_dv01_movement(date(2026, 3, 31), accounting_class="OCI", top_n=10)
    result = payload["result"]

    assert payload["result_meta"]["result_kind"] == "bond_analytics.dv01_movement"
    assert result["accounting_class"] == "OCI"
    assert result["previous_report_date"] == previous_date
    assert _numeric_raw(result["current_total_dv01"]) == Decimal("630")
    assert _numeric_raw(result["previous_total_dv01"]) == Decimal("450")
    assert _numeric_raw(result["delta_dv01"]) == Decimal("180")

    attribution = {row["driver_key"]: row for row in result["attribution"]}
    assert _numeric_raw(attribution["new_position"]["dv01_delta"]) == Decimal("100")
    assert _numeric_raw(attribution["exited_position"]["dv01_delta"]) == Decimal("-50")
    assert _numeric_raw(attribution["face_value_change"]["dv01_delta"]) == Decimal("30.00")
    assert _numeric_raw(attribution["duration_change"]["dv01_delta"]) == Decimal("50.0000")
    assert _numeric_raw(attribution["classification_change"]["dv01_delta"]) == Decimal("40")
    assert _numeric_raw(attribution["residual"]["dv01_delta"]) == Decimal("10.0000")
    assert sum(_numeric_raw(row["dv01_delta"]) for row in result["attribution"]) == _numeric_raw(result["delta_dv01"])

    top_codes = [row["instrument_code"] for row in result["anomaly_bonds"]]
    assert top_codes[:3] == ["N-001", "A-001", "X-001"]
    alpha = next(row for row in result["methodology_checks"] if row["instrument_code"] == "A-001")
    assert _numeric_raw(alpha["estimated_dv01_from_face_duration"]) == Decimal("385.00000")
    assert _numeric_raw(alpha["dv01_estimate_gap"]) == Decimal("5.00000")
    get_settings.cache_clear()


def test_bond_analytics_dv01_movement_without_prior_returns_warning(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    class FakeRepo:
        def list_report_dates(self):
            return ["2026-03-31"]

        def fetch_bond_analytics_rows(self, *, report_date, accounting_class="all", **_kwargs):
            return []

    monkeypatch.setattr(service_mod, "_repo", lambda: FakeRepo())
    monkeypatch.setattr(
        service_mod,
        "_lineage",
        lambda _report_date, _rows: {
            "source_version": "sv_empty",
            "rule_version": "rv_empty",
            "cache_version": "cv_empty",
            "vendor_version": "vv_empty",
        },
    )

    payload = service_mod.get_dv01_movement(date(2026, 3, 31))
    result = payload["result"]

    assert result["previous_report_date"] is None
    assert result["source_status"] == "empty"
    assert result["attribution"] == []
    assert result["anomaly_bonds"] == []
    assert result["methodology_checks"] == []
    assert result["warnings"]
    get_settings.cache_clear()


def test_bond_analytics_dv01_action_plan_flags_risk_and_hedge_size(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )
    report_date = "2026-03-31"
    rows = [
        {
            "report_date": report_date,
            "instrument_code": "A-001",
            "instrument_name": "Alpha Bond",
            "issuer_name": "Issuer A",
            "rating": "AAA",
            "tenor_bucket": "7-10Y",
            "accounting_class": "OCI",
            "face_value": Decimal("1000000"),
            "market_value": Decimal("1005000"),
            "modified_duration": Decimal("8"),
            "dv01": Decimal("800"),
            "source_version": "sv",
            "rule_version": "rv",
            "trace_id": "tr_a",
        },
        {
            "report_date": report_date,
            "instrument_code": "B-001",
            "instrument_name": "Beta Bond",
            "issuer_name": "Issuer A",
            "rating": "AA+",
            "tenor_bucket": "7-10Y",
            "accounting_class": "OCI",
            "face_value": Decimal("500000"),
            "market_value": Decimal("501000"),
            "modified_duration": Decimal("7"),
            "dv01": Decimal("350"),
            "source_version": "sv",
            "rule_version": "rv",
            "trace_id": "tr_b",
        },
        {
            "report_date": report_date,
            "instrument_code": "C-001",
            "instrument_name": "Gamma Bond",
            "issuer_name": "Issuer C",
            "rating": "AAA",
            "tenor_bucket": "1-3Y",
            "accounting_class": "TPL",
            "face_value": Decimal("400000"),
            "market_value": Decimal("401000"),
            "modified_duration": Decimal("2"),
            "dv01": Decimal("80"),
            "source_version": "sv",
            "rule_version": "rv",
            "trace_id": "tr_c",
        },
    ]

    class FakeRepo:
        def fetch_bond_analytics_rows(self, *, report_date, accounting_class="all", **_kwargs):
            scoped = list(rows)
            if accounting_class != "all":
                scoped = [row for row in scoped if row["accounting_class"] == accounting_class]
            return scoped

    monkeypatch.setattr(service_mod, "_repo", lambda: FakeRepo())
    monkeypatch.setattr(
        service_mod,
        "_lineage",
        lambda _report_date, _rows: {
            "source_version": "sv_test",
            "rule_version": "rv_test",
            "cache_version": "cv_test",
            "vendor_version": "vv_test",
        },
    )

    payload = service_mod.get_dv01_action_plan(
        date(2026, 3, 31),
        accounting_class="OCI",
        top_n=2,
        limit_dv01="1000",
        warning_dv01="900",
        hedge_instrument_dv01="250",
        hedge_target_dv01="900",
    )
    result = payload["result"]

    assert payload["result_meta"]["result_kind"] == "bond_analytics.dv01_action_plan"
    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["formal_use_allowed"] is False
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert result["accounting_class"] == "OCI"
    assert result["risk_level"] == "breach"
    assert result["breach_count"] == 3
    assert _numeric_raw(result["total_dv01"]) == Decimal("1150")
    assert _numeric_raw(result["limit_dv01"]) == Decimal("1000")
    assert _numeric_raw(result["warning_dv01"]) == Decimal("900")
    assert _numeric_raw(result["dv01_to_reduce"]) == Decimal("250")
    assert result["hedge_instrument_label"] == "DV01 hedge unit"
    assert _numeric_raw(result["hedge_instrument_dv01"]) == Decimal("250")
    assert _numeric_raw(result["suggested_hedge_units"]) == Decimal("1")
    assert result["scenario_breaches"][0]["scenario_name"] == "rate_up_10bp"
    assert _numeric_raw(result["scenario_breaches"][0]["estimated_loss"]) == Decimal("11500")
    assert result["scenario_breaches"][0]["risk_level"] == "breach"
    assert result["tenor_actions"][0]["tenor_bucket"] == "7-10Y"
    assert _numeric_raw(result["tenor_actions"][0]["dv01_share"]) == Decimal("1")
    assert result["issuer_actions"][0]["issuer_name"] == "Issuer A"
    assert result["bond_actions"][0]["instrument_code"] == "A-001"
    get_settings.cache_clear()


def test_bond_analytics_dv01_action_plan_uses_formal_limit_config(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    GovernanceRepository(base_dir=governance_dir).append(
        "bond_dv01_limit_config",
        {
            "report_date": "2026-03-31",
            "accounting_class": "OCI",
            "limit_dv01": "1200",
            "warning_dv01": "1000",
            "hedge_target_dv01": "1000",
            "source_version": "sv_limit_committee_202603",
            "rule_version": "rv_dv01_limit_policy_v1",
            "limit_source": "risk_committee_minutes",
            "limit_source_version": "risk_minutes_2026_03",
            "limit_rule_version": "rv_dv01_limit_policy_v1",
            "limit_effective_date": "2026-03-01",
        },
    )
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )
    rows = [
        {
            "report_date": "2026-03-31",
            "instrument_code": "A-001",
            "instrument_name": "Alpha Bond",
            "issuer_name": "Issuer A",
            "rating": "AAA",
            "tenor_bucket": "7-10Y",
            "accounting_class": "OCI",
            "face_value": Decimal("1000000"),
            "market_value": Decimal("1005000"),
            "modified_duration": Decimal("8"),
            "dv01": Decimal("900"),
            "source_version": "sv",
            "rule_version": "rv",
            "trace_id": "tr_a",
        },
        {
            "report_date": "2026-03-31",
            "instrument_code": "B-001",
            "instrument_name": "Beta Bond",
            "issuer_name": "Issuer A",
            "rating": "AA+",
            "tenor_bucket": "7-10Y",
            "accounting_class": "OCI",
            "face_value": Decimal("500000"),
            "market_value": Decimal("501000"),
            "modified_duration": Decimal("7"),
            "dv01": Decimal("300"),
            "source_version": "sv",
            "rule_version": "rv",
            "trace_id": "tr_b",
        },
    ]

    class FakeRepo:
        def fetch_bond_analytics_rows(self, *, report_date, accounting_class="all", **_kwargs):
            return [row for row in rows if row["accounting_class"] == accounting_class]

    monkeypatch.setattr(service_mod, "_repo", lambda: FakeRepo())
    monkeypatch.setattr(
        service_mod,
        "_lineage",
        lambda _report_date, _rows: {
            "source_version": "sv_test",
            "rule_version": "rv_test",
            "cache_version": "cv_test",
            "vendor_version": "vv_test",
        },
    )

    payload = service_mod.get_dv01_action_plan(date(2026, 3, 31), accounting_class="OCI")
    result = payload["result"]

    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["formal_use_allowed"] is False
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert result["policy_basis"] == "formal_limit"
    assert result["limit_source"] == "risk_committee_minutes"
    assert result["limit_source_version"] == "risk_minutes_2026_03"
    assert result["limit_rule_version"] == "rv_dv01_limit_policy_v1"
    assert result["limit_effective_date"] == "2026-03-01"
    assert "正式 DV01 限额" in result["threshold_note"]
    assert _numeric_raw(result["limit_dv01"]) == Decimal("1200")
    assert _numeric_raw(result["warning_dv01"]) == Decimal("1000")
    assert _numeric_raw(result["limit_usage"]) == Decimal("1")
    assert _numeric_raw(result["remaining_limit_dv01"]) == Decimal("0")
    assert result["warnings"] == []
    get_settings.cache_clear()


def test_bond_analytics_dv01_limit_config_status_reports_ready_missing_and_invalid(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    repo = GovernanceRepository(base_dir=governance_dir)
    repo.append(
        "bond_dv01_limit_config",
        {
            "report_date": "2026-03-31",
            "accounting_class": "OCI",
            "limit_dv01": "1200",
            "warning_dv01": "1000",
            "hedge_target_dv01": "1000",
            "limit_source": "risk_committee_minutes",
            "limit_source_version": "risk_minutes_2026_03",
            "limit_rule_version": "rv_dv01_limit_policy_v1",
            "limit_effective_date": "2026-03-01",
        },
    )
    repo.append(
        "bond_dv01_limit_config",
        {
            "report_date": "2026-03-31",
            "accounting_class": "TPL",
            "limit_dv01": "0",
            "warning_dv01": "100",
            "limit_source": "risk_committee_minutes",
            "limit_source_version": "risk_minutes_2026_03",
            "limit_rule_version": "rv_dv01_limit_policy_v1",
            "limit_effective_date": "2026-03-01",
        },
    )
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_dv01_limit_config_status(date(2026, 3, 31))
    result = payload["result"]
    rows_by_class = {row["accounting_class"]: row for row in result["rows"]}

    assert payload["result_meta"]["result_kind"] == "bond_analytics.dv01_limit_config_status"
    assert result["configured_count"] == 1
    assert result["missing_count"] == 2
    assert result["invalid_count"] == 1
    assert result["overall_status"] == "incomplete"
    assert result["config_stream"] == "bond_dv01_limit_config"
    assert result["required_accounting_classes"] == ["AC", "OCI", "TPL", "all"]
    assert "limit_dv01" in result["required_fields"]
    assert "limit_source_version" in result["required_fields"]
    assert result["missing_accounting_classes"] == ["AC", "all"]
    assert result["invalid_accounting_classes"] == ["TPL"]
    expected_business_fields = [
        "limit_dv01",
        "warning_dv01",
        "hedge_target_dv01",
        "limit_source",
        "limit_source_version",
        "limit_rule_version",
        "limit_effective_date",
    ]
    assert result["missing_business_fields_by_class"]["AC"] == expected_business_fields
    assert result["missing_business_fields_by_class"]["all"] == expected_business_fields
    assert result["review_package_command"].startswith(
        "python -m backend.app.tasks.bond_dv01_limit_config_import --review-package-dir"
    )
    assert "--report-date 2026-03-31" in result["review_package_command"]
    assert result["dry_run_command"].startswith(
        "python -m backend.app.tasks.bond_dv01_limit_config_import --config-path"
    )
    assert "bond_dv01_limit_config_review_2026-03-31.csv" in result["dry_run_command"]
    assert "--dry-run" in result["dry_run_command"]
    assert "AC, all" in result["acceptance_message"]
    assert "TPL" in result["acceptance_message"]
    assert "bond_dv01_limit_config" in result["next_action"]
    assert "limit_dv01" in result["next_action"]
    assert rows_by_class["OCI"]["status"] == "ready"
    assert _numeric_raw(rows_by_class["OCI"]["limit_dv01"]) == Decimal("1200")
    assert rows_by_class["OCI"]["limit_source"] == "risk_committee_minutes"
    assert rows_by_class["AC"]["status"] == "missing"
    assert rows_by_class["TPL"]["status"] == "invalid"
    assert "limit_dv01" in rows_by_class["TPL"]["message"]
    assert result["warnings"]
    get_settings.cache_clear()


def test_bond_analytics_dv01_limit_config_status_acceptance_requires_direct_class_configs(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    repo = GovernanceRepository(base_dir=governance_dir)
    for accounting_class in ["AC", "OCI", "TPL", "all"]:
        repo.append(
            "bond_dv01_limit_config",
            {
                "report_date": "2026-03-31",
                "accounting_class": accounting_class,
                "limit_dv01": "1200",
                "warning_dv01": "1000",
                "hedge_target_dv01": "1000",
                "limit_source": "risk_committee_minutes",
                "limit_source_version": f"risk_minutes_2026_03_{accounting_class}",
                "limit_rule_version": "rv_dv01_limit_policy_v1",
                "limit_effective_date": "2026-03-01",
            },
        )
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_dv01_limit_config_status(date(2026, 3, 31))
    result = payload["result"]

    assert result["overall_status"] == "ready"
    assert result["acceptance_status"] == "ready"
    assert result["configured_accounting_classes"] == ["AC", "OCI", "TPL", "all"]
    assert result["missing_accounting_classes"] == []
    assert result["invalid_accounting_classes"] == []
    assert result["missing_business_fields_by_class"] == {}
    assert result["review_package_command"] == ""
    assert result["dry_run_command"] == ""
    assert result["acceptance_message"] == "正式 DV01 限额配置验收通过。"
    assert result["next_action"] == "无需补充配置；动作计划将按正式限额口径计算。"
    assert result["warnings"] == []
    get_settings.cache_clear()


def test_bond_analytics_dv01_limit_config_status_does_not_accept_all_as_class_coverage(tmp_path, monkeypatch):
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    GovernanceRepository(base_dir=governance_dir).append(
        "bond_dv01_limit_config",
        {
            "report_date": "2026-03-31",
            "accounting_class": "all",
            "limit_dv01": "1200",
            "warning_dv01": "1000",
            "hedge_target_dv01": "1000",
            "limit_source": "risk_committee_minutes",
            "limit_source_version": "risk_minutes_2026_03",
            "limit_rule_version": "rv_dv01_limit_policy_v1",
            "limit_effective_date": "2026-03-01",
        },
    )
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_dv01_limit_config_status(date(2026, 3, 31))
    result = payload["result"]
    rows_by_class = {row["accounting_class"]: row for row in result["rows"]}

    assert rows_by_class["all"]["status"] == "ready"
    assert rows_by_class["AC"]["status"] == "missing"
    assert rows_by_class["OCI"]["status"] == "missing"
    assert rows_by_class["TPL"]["status"] == "missing"
    assert result["acceptance_status"] == "blocked"
    assert result["configured_accounting_classes"] == ["all"]
    assert result["missing_accounting_classes"] == ["AC", "OCI", "TPL"]
    assert "AC, OCI, TPL" in result["acceptance_message"]
    assert "bond_dv01_limit_config" in result["next_action"]
    get_settings.cache_clear()


def test_bond_analytics_dv01_action_plan_marks_page_threshold_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )
    rows = [
        {
            "report_date": "2026-03-31",
            "instrument_code": "A-001",
            "instrument_name": "Alpha Bond",
            "issuer_name": "Issuer A",
            "rating": "AAA",
            "tenor_bucket": "7-10Y",
            "accounting_class": "OCI",
            "face_value": Decimal("1000000"),
            "market_value": Decimal("1005000"),
            "modified_duration": Decimal("8"),
            "dv01": Decimal("1150"),
            "source_version": "sv",
            "rule_version": "rv",
            "trace_id": "tr_a",
        },
    ]

    class FakeRepo:
        def fetch_bond_analytics_rows(self, *, report_date, accounting_class="all", **_kwargs):
            return rows

    monkeypatch.setattr(service_mod, "_repo", lambda: FakeRepo())
    monkeypatch.setattr(
        service_mod,
        "_lineage",
        lambda _report_date, _rows: {
            "source_version": "sv_test",
            "rule_version": "rv_test",
            "cache_version": "cv_test",
            "vendor_version": "vv_test",
        },
    )

    payload = service_mod.get_dv01_action_plan(
        date(2026, 3, 31),
        accounting_class="OCI",
        limit_dv01="1000",
        warning_dv01="900",
    )
    result = payload["result"]

    assert payload["result_meta"]["basis"] == "analytical"
    assert payload["result_meta"]["formal_use_allowed"] is False
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert result["policy_basis"] == "page_threshold_fallback"
    assert result["limit_source"] == "page_threshold"
    assert result["limit_source_version"] == "unconfigured"
    assert result["limit_rule_version"] == "rv_dv01_page_threshold_v3"
    assert result["limit_effective_date"] is None
    assert "不代表正式限额" in result["threshold_note"]
    assert _numeric_raw(result["limit_usage"]) == Decimal("1.15")
    assert _numeric_raw(result["remaining_limit_dv01"]) == Decimal("-150")
    assert any("未接入正式限额源" in warning for warning in result["warnings"])
    get_settings.cache_clear()


def test_bond_analytics_dv01_action_plan_empty_scope_returns_warning(tmp_path, monkeypatch):
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(tmp_path / "governance"))
    get_settings.cache_clear()
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    class FakeRepo:
        def fetch_bond_analytics_rows(self, *, report_date, accounting_class="all", **_kwargs):
            return []

    monkeypatch.setattr(service_mod, "_repo", lambda: FakeRepo())
    monkeypatch.setattr(
        service_mod,
        "_lineage",
        lambda _report_date, _rows: {
            "source_version": "sv_empty",
            "rule_version": "rv_empty",
            "cache_version": "cv_empty",
            "vendor_version": "vv_empty",
        },
    )

    payload = service_mod.get_dv01_action_plan(date(2026, 3, 31))
    result = payload["result"]

    assert result["risk_level"] == "no_data"
    assert result["position_count"] == 0
    assert result["scenario_breaches"] == []
    assert result["tenor_actions"] == []
    assert result["issuer_actions"] == []
    assert result["bond_actions"] == []
    assert result["warnings"]
    get_settings.cache_clear()


def test_bond_analytics_credit_spread_migration_uses_credit_subset_and_concentration(tmp_path, monkeypatch):
    _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.bond_analytics_service",
        "backend/app/services/bond_analytics_service.py",
    )

    payload = service_mod.get_credit_spread_migration(date(2026, 3, 31), "10,25")
    meta = payload["result_meta"]
    result = payload["result"]

    assert meta["basis"] == "analytical"
    assert meta["formal_use_allowed"] is False
    assert meta["quality_flag"] == "warning"
    assert meta["scenario_flag"] is False
    assert meta["result_kind"] == "bond_analytics.credit_spread_migration"
    assert meta["source_surface"] == "bond_analytics"
    assert meta["requested_report_date"] == "2026-03-31"
    assert meta["resolved_report_date"] == "2026-03-31"
    assert meta["as_of_date"] == "2026-03-31"
    assert meta["date_basis"] == "bond_analytics_report_date"
    assert meta["filters_applied"] == {"report_date": "2026-03-31", "spread_scenarios": "10,25"}
    assert meta["tables_used"] == ["fact_formal_bond_analytics_daily"]
    assert meta["evidence_rows"] == 3
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
