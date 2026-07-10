from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest
from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import (
    CACHE_BUILD_RUN_STREAM,
    GovernanceRepository,
)
from backend.app.repositories.task_write_guard import repository_task_write_scope

from tests.helpers import load_module
from tests.test_bond_analytics_materialize_flow import (
    REPORT_DATE,
    _seed_bond_snapshot_rows,
)
from tests.test_bond_analytics_service import _configure_and_materialize


def _materialize_risk_tensor(duckdb_path, governance_dir):
    task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )
    task_mod.materialize_risk_tensor_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    return task_mod


def _configure_and_materialize_risk_tensor(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    risk_task_mod = _materialize_risk_tensor(duckdb_path, governance_dir)
    return duckdb_path, governance_dir, risk_task_mod


def _configure_and_materialize_degraded_snapshot(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.degraded.duckdb"
    governance_dir = tmp_path / "governance.degraded"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()
    _seed_bond_snapshot_rows(str(duckdb_path))

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update zqtz_bond_daily_snapshot
            set maturity_date = ?
            where report_date = ?
              and instrument_code = 'CB-001'
            """,
            ["2048-03-31", REPORT_DATE],
        )
        conn.execute(
            """
            update zqtz_bond_daily_snapshot
            set maturity_date = null
            where report_date = ?
              and instrument_code = 'TB-001'
            """,
            [REPORT_DATE],
        )
    finally:
        conn.close()

    bond_task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    bond_task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    _materialize_risk_tensor(duckdb_path, governance_dir)
    return duckdb_path, governance_dir, bond_task_mod


def _configure_and_materialize_risk_tensor_with_tyw_liability(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table if not exists fact_formal_tyw_balance_daily (
              report_date varchar,
              position_id varchar,
              product_type varchar,
              position_side varchar,
              counterparty_name varchar,
              account_type varchar,
              special_account_type varchar,
              core_customer_type varchar,
              invest_type_std varchar,
              accounting_basis varchar,
              position_scope varchar,
              currency_basis varchar,
              currency_code varchar,
              principal_amount decimal(24, 8),
              accrued_interest_amount decimal(24, 8),
              funding_cost_rate decimal(18, 8),
              maturity_date varchar,
              source_version varchar,
              rule_version varchar,
              ingest_batch_id varchar,
              trace_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_tyw_balance_daily (
              report_date, position_id, product_type, position_side, counterparty_name,
              account_type, special_account_type, core_customer_type, invest_type_std,
              accounting_basis, position_scope, currency_basis, currency_code, principal_amount,
              accrued_interest_amount, funding_cost_rate, maturity_date, source_version,
              rule_version, ingest_batch_id, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                REPORT_DATE,
                "TYW-L-1",
                "Interbank",
                "liability",
                "Bank L",
                "",
                "",
                "",
                "H",
                "AC",
                "liability",
                "CNY",
                "CNY",
                "4",
                "0",
                "0",
                "2026-04-10",
                "sv_tyw_liab_1",
                "rv_balance_analysis_formal_materialize_v1",
                "ib-liab-1",
                "trace-liab-1",
            ],
        )
    finally:
        conn.close()

    risk_task_mod = _materialize_risk_tensor(duckdb_path, governance_dir)
    return duckdb_path, governance_dir, risk_task_mod


def _replace_test_risk_tensor_row(
    *,
    repo,
    core_mod,
    report_date: str,
    source_version: str,
    upstream_source_version: str,
    regulatory_dv01: str = "0.00000000",
    krd_3y: str = "5.00000000",
    krd_10y: str = "0.30000000",
    krd_30y: str = "0.20000000",
    cs01: str = "0.75000000",
    portfolio_modified_duration: str = "1.50000000",
    liquidity_gap_30d_ratio: str = "0.01000000",
) -> None:
    tensor = core_mod.PortfolioRiskTensor(
        report_date=report_date,
        portfolio_dv01=Decimal("8.00000000"),
        regulatory_dv01=Decimal(regulatory_dv01),
        krd_1y=Decimal("1.00000000"),
        krd_3y=Decimal(krd_3y),
        krd_5y=Decimal("1.00000000"),
        krd_7y=Decimal("0.50000000"),
        krd_10y=Decimal(krd_10y),
        krd_30y=Decimal(krd_30y),
        cs01=Decimal(cs01),
        portfolio_convexity=Decimal("2.50000000"),
        portfolio_modified_duration=Decimal(portfolio_modified_duration),
        rate_risk_market_value=Decimal("100.00000000"),
        rate_risk_dv01=Decimal("8.00000000"),
        rate_risk_modified_duration=Decimal(portfolio_modified_duration),
        duration_excluded_market_value=Decimal("0.00000000"),
        duration_excluded_count=0,
        issuer_concentration_hhi=Decimal("0.50000000"),
        issuer_top5_weight=Decimal("1.00000000"),
        asset_cashflow_30d=Decimal("12.00000000"),
        asset_cashflow_90d=Decimal("12.00000000"),
        liability_cashflow_30d=Decimal("2.00000000"),
        liability_cashflow_90d=Decimal("2.00000000"),
        liquidity_gap_30d=Decimal("10.00000000"),
        liquidity_gap_90d=Decimal("10.00000000"),
        liquidity_gap_30d_ratio=Decimal(liquidity_gap_30d_ratio),
        total_market_value=Decimal("100.00000000"),
        bond_count=2,
        quality_flag="ok",
        warnings=[],
    )
    with repository_task_write_scope("backend.app.tasks.risk_tensor_service_test"):
        repo.replace_risk_tensor_row(
            report_date=report_date,
            tensor=tensor,
            source_version=source_version,
            upstream_source_version=upstream_source_version,
            upstream_rule_version="rv_bond_snap_test",
            upstream_cache_version="cv_bond_snap_test",
            liability_source_version="",
            liability_rule_version="",
            rule_version="rv_risk_tensor_formal_materialize_v3",
            cache_version="cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v3",
            trace_id=f"trace_risk_tensor_{report_date.replace('-', '')}",
        )


def test_risk_tensor_service_returns_formal_envelope_with_lineage(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize_risk_tensor(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )

    payload = service_mod.risk_tensor_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date=REPORT_DATE,
    )

    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert payload["result_meta"]["scenario_flag"] is False
    assert payload["result_meta"]["result_kind"] == "risk.tensor"
    assert payload["result_meta"]["source_version"] == "sv_risk_tensor__sv_bond_snap_1"
    assert payload["result_meta"]["rule_version"] == "rv_risk_tensor_formal_materialize_v3"
    assert payload["result_meta"]["cache_version"] == "cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v3"
    assert payload["result_meta"]["tables_used"] == ["fact_formal_risk_tensor_daily"]
    assert payload["result_meta"]["evidence_rows"] == 1
    assert payload["result_meta"]["quality_flag"] == "ok"
    assert payload["result_meta"]["requested_report_date"] == REPORT_DATE
    assert payload["result_meta"]["resolved_report_date"] == REPORT_DATE
    assert payload["result_meta"]["as_of_date"] == REPORT_DATE
    assert payload["result_meta"]["date_basis"] == "formal_snapshot"
    assert payload["result_meta"]["fallback_date"] is None

    result = payload["result"]
    materialized_row = service_mod.RiskTensorRepository(str(duckdb_path)).fetch_risk_tensor_row(REPORT_DATE)
    assert materialized_row is not None
    for field_name in (
        "rate_risk_market_value",
        "rate_risk_dv01",
        "rate_risk_modified_duration",
        "duration_excluded_market_value",
    ):
        assert Decimal(str(result[field_name]["raw"])) == materialized_row[field_name]
    assert result["duration_excluded_count"] == materialized_row["duration_excluded_count"]
    assert result["report_date"] == REPORT_DATE
    assert result["bond_count"] == 3
    assert result["quality_flag"] == "ok"
    assert result["warnings"] == []
    assert result["total_market_value"]["raw"] == 429.0
    assert result["asset_cashflow_30d"]["raw"] == 14.0
    assert result["asset_cashflow_90d"]["raw"] == 14.0
    assert result["liability_cashflow_30d"]["raw"] == 0.0
    assert result["liability_cashflow_90d"]["raw"] == 0.0
    assert result["liquidity_gap_30d"]["raw"] == 14.0
    assert result["liquidity_gap_90d"]["raw"] == 14.0
    assert (
        Decimal(str(result["liquidity_gap_30d"]["raw"]))
        == Decimal(str(result["asset_cashflow_30d"]["raw"])) - Decimal(str(result["liability_cashflow_30d"]["raw"]))
    )
    assert result["issuer_top5_weight"]["raw"] == 1.0
    assert isinstance(result["portfolio_dv01"], dict)
    assert isinstance(result["regulatory_dv01"], dict)
    assert isinstance(result["portfolio_convexity"], dict)
    assert result["portfolio_dv01"]["unit"] == "dv01"
    assert result["regulatory_dv01"]["unit"] == "dv01"
    assert result["regulatory_dv01"]["raw"] == result["portfolio_dv01"]["raw"]
    assert {"ac_dv01", "oci_dv01", "tpl_dv01", "other_dv01"}.isdisjoint(result)
    assert {"prior_period_change", "dv01_controls"}.isdisjoint(result)
    assert result["portfolio_convexity"]["unit"] == "ratio"
    assert (
        Decimal(str(result["krd_1y"]["raw"]))
        + Decimal(str(result["krd_3y"]["raw"]))
        + Decimal(str(result["krd_5y"]["raw"]))
        + Decimal(str(result["krd_7y"]["raw"]))
        + Decimal(str(result["krd_10y"]["raw"]))
        + Decimal(str(result["krd_30y"]["raw"]))
    ) == Decimal(str(result["portfolio_dv01"]["raw"]))
    assert Decimal(str(result["cs01"]["raw"])) > Decimal("0")
    assert Decimal(str(result["portfolio_convexity"]["raw"])) > Decimal("0")

    get_settings.cache_clear()


def test_formal_risk_tensor_excludes_unapproved_derivatives_even_when_prior_exists(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize_risk_tensor(tmp_path, monkeypatch)
    core_mod = load_module(
        "backend.app.core_finance.risk_tensor",
        "backend/app/core_finance/risk_tensor.py",
    )
    repo_mod = load_module(
        "backend.app.repositories.risk_tensor_repo",
        "backend/app/repositories/risk_tensor_repo.py",
    )
    repo = repo_mod.RiskTensorRepository(str(duckdb_path))
    previous_report_date = "2026-02-28"
    _replace_test_risk_tensor_row(
        repo=repo,
        core_mod=core_mod,
        report_date=previous_report_date,
        source_version="sv_risk_tensor__sv_prev_bond_snap",
        upstream_source_version="sv_prev_bond_snap",
    )

    service_mod = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )
    payload = service_mod.risk_tensor_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date=REPORT_DATE,
    )

    assert {"prior_period_change", "dv01_controls"}.isdisjoint(payload["result"])

    get_settings.cache_clear()


def test_formal_risk_tensor_read_is_stable_when_upstream_fact_changes_without_rematerialization(
    tmp_path,
    monkeypatch,
):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize_risk_tensor(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )
    read_args = {
        "duckdb_path": str(duckdb_path),
        "governance_dir": str(governance_dir),
        "report_date_value": date.fromisoformat(REPORT_DATE),
        "report_date_text": REPORT_DATE,
    }
    before = service_mod._risk_tensor_envelope_uncached(**read_args)

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update fact_formal_bond_analytics_daily
            set market_value = market_value * 10,
                dv01 = dv01 * 10
            where report_date = ?
            """,
            [REPORT_DATE],
        )
    finally:
        conn.close()

    after = service_mod._risk_tensor_envelope_uncached(**read_args)
    for field_name in (
        "rate_risk_market_value",
        "rate_risk_dv01",
        "rate_risk_modified_duration",
        "duration_excluded_market_value",
        "duration_excluded_count",
    ):
        assert after["result"][field_name] == before["result"][field_name]

    get_settings.cache_clear()


def test_risk_tensor_cache_invalidates_when_upstream_governance_lineage_changes(
    tmp_path,
    monkeypatch,
):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize_risk_tensor(
        tmp_path,
        monkeypatch,
    )
    service_mod = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )
    service_mod.invalidate_risk_tensor_read_cache()
    service_mod.risk_tensor_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date=REPORT_DATE,
    )

    governance_repo = GovernanceRepository(base_dir=governance_dir)
    completed_rows = [
        row
        for row in governance_repo.read_all(CACHE_BUILD_RUN_STREAM)
        if row.get("job_name") == "bond_analytics_materialize"
        and row.get("status") == "completed"
        and row.get("report_date") == REPORT_DATE
    ]
    assert completed_rows
    changed_lineage = dict(completed_rows[-1])
    changed_lineage.update(
        {
            "run_id": "run_bond_lineage_changed_after_risk_cache",
            "rule_version": "rv_bond_lineage_changed_after_risk_cache",
            "cache_version": "cv_bond_lineage_changed_after_risk_cache",
        }
    )
    governance_repo.append(CACHE_BUILD_RUN_STREAM, changed_lineage)

    with pytest.raises(RuntimeError, match="bond analytics rule lineage"):
        service_mod.risk_tensor_envelope(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            report_date=REPORT_DATE,
        )

    get_settings.cache_clear()


def test_risk_tensor_service_uses_shared_formal_result_runtime_helper():
    path = Path(__file__).resolve().parents[1] / "backend" / "app" / "services" / "risk_tensor_service.py"
    src = path.read_text(encoding="utf-8")

    assert "backend.app.services.formal_result_runtime" in src
    assert "build_formal_result_envelope_from_lineage" in src
    assert "build_formal_result_meta(" not in src


def test_formal_risk_tensor_service_has_no_live_bond_analytics_or_read_time_derivatives():
    path = Path(__file__).resolve().parents[1] / "backend" / "app" / "services" / "risk_tensor_service.py"
    src = path.read_text(encoding="utf-8")
    repo_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "app"
        / "repositories"
        / "bond_analytics_repo.py"
    )
    repo_src = repo_path.read_text(encoding="utf-8")

    assert "BondAnalyticsRepository" not in src
    assert "_fetch_rate_risk_duration_scope" not in src
    assert "_fetch_accounting_dv01_split" not in src
    assert "_build_prior_period_change" not in src
    assert "_build_dv01_controls" not in src
    assert "fetch_rate_risk_duration_scope" not in repo_src


def test_risk_tensor_freshness_requires_v3_materialized_duration_scope():
    service_mod = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )
    base_row = {
        "upstream_source_version": "sv_bond_snap_1",
        "upstream_rule_version": "rv_bond_snap_1",
        "upstream_cache_version": "cv_bond_snap_1",
        "rule_version": "rv_risk_tensor_formal_materialize_v2",
        "cache_version": "cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v2",
    }

    stale_rule = service_mod._risk_tensor_freshness_error_from_values(
        report_date_text=REPORT_DATE,
        row=base_row,
        upstream_source_version="sv_bond_snap_1",
        upstream_rule_version="rv_bond_snap_1",
        upstream_cache_version="cv_bond_snap_1",
        current_tyw_liability_source_version="",
        current_tyw_liability_rule_version="",
    )
    assert stale_rule is not None
    assert "rule version" in stale_rule.lower()

    materialized_row = base_row | {
        "rule_version": service_mod.RULE_VERSION,
        "cache_version": service_mod.CACHE_VERSION,
        "rate_risk_market_value": Decimal("0"),
        "rate_risk_dv01": Decimal("0"),
        "rate_risk_modified_duration": Decimal("0"),
        "duration_excluded_market_value": Decimal("0"),
        "duration_excluded_count": 0,
    }
    stale_cache = service_mod._risk_tensor_freshness_error_from_values(
        report_date_text=REPORT_DATE,
        row=materialized_row | {"cache_version": "cv_risk_tensor_formal_stale"},
        upstream_source_version="sv_bond_snap_1",
        upstream_rule_version="rv_bond_snap_1",
        upstream_cache_version="cv_bond_snap_1",
        current_tyw_liability_source_version="",
        current_tyw_liability_rule_version="",
    )
    assert stale_cache is not None
    assert "cache version" in stale_cache.lower()

    missing_scope = service_mod._risk_tensor_freshness_error_from_values(
        report_date_text=REPORT_DATE,
        row=base_row
        | {
            "rule_version": service_mod.RULE_VERSION,
            "cache_version": service_mod.CACHE_VERSION,
        },
        upstream_source_version="sv_bond_snap_1",
        upstream_rule_version="rv_bond_snap_1",
        upstream_cache_version="cv_bond_snap_1",
        current_tyw_liability_source_version="",
        current_tyw_liability_rule_version="",
    )
    assert missing_scope is not None
    assert "materialized duration-scope metrics missing" in missing_scope

    stale_upstream_rule = service_mod._risk_tensor_freshness_error_from_values(
        report_date_text=REPORT_DATE,
        row=materialized_row,
        upstream_source_version="sv_bond_snap_1",
        upstream_rule_version="rv_bond_snap_2",
        upstream_cache_version="cv_bond_snap_1",
        current_tyw_liability_source_version="",
        current_tyw_liability_rule_version="",
    )
    assert stale_upstream_rule is not None
    assert "bond analytics rule lineage" in stale_upstream_rule.lower()

    stale_upstream_cache = service_mod._risk_tensor_freshness_error_from_values(
        report_date_text=REPORT_DATE,
        row=materialized_row,
        upstream_source_version="sv_bond_snap_1",
        upstream_rule_version="rv_bond_snap_1",
        upstream_cache_version="cv_bond_snap_2",
        current_tyw_liability_source_version="",
        current_tyw_liability_rule_version="",
    )
    assert stale_upstream_cache is not None
    assert "bond analytics cache lineage" in stale_upstream_cache.lower()


def test_risk_tensor_repository_does_not_backfill_missing_regulatory_dv01_from_portfolio(tmp_path):
    repo_mod = load_module(
        "backend.app.repositories.risk_tensor_repo",
        "backend/app/repositories/risk_tensor_repo.py",
    )
    duckdb_path = tmp_path / "legacy-risk.duckdb"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table fact_formal_risk_tensor_daily (
              report_date varchar,
              portfolio_dv01 decimal(24, 8),
              krd_1y decimal(24, 8),
              krd_3y decimal(24, 8),
              krd_5y decimal(24, 8),
              krd_7y decimal(24, 8),
              krd_10y decimal(24, 8),
              krd_30y decimal(24, 8),
              cs01 decimal(24, 8),
              portfolio_convexity decimal(24, 8),
              portfolio_modified_duration decimal(24, 8),
              issuer_concentration_hhi decimal(24, 8),
              issuer_top5_weight decimal(24, 8),
              liquidity_gap_30d decimal(24, 8),
              liquidity_gap_90d decimal(24, 8),
              liquidity_gap_30d_ratio decimal(24, 8),
              total_market_value decimal(24, 8),
              bond_count integer,
              quality_flag varchar,
              warnings_json varchar,
              source_version varchar,
              upstream_source_version varchar,
              rule_version varchar,
              cache_version varchar,
              trace_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into fact_formal_risk_tensor_daily (
              report_date, portfolio_dv01, krd_1y, krd_3y, krd_5y, krd_7y,
              krd_10y, krd_30y, cs01, portfolio_convexity, portfolio_modified_duration,
              issuer_concentration_hhi, issuer_top5_weight, liquidity_gap_30d,
              liquidity_gap_90d, liquidity_gap_30d_ratio, total_market_value,
              bond_count, quality_flag, warnings_json, source_version,
              upstream_source_version, rule_version, cache_version, trace_id
            ) values (
              ?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 100,
              1, 'ok', '[]', 'sv_legacy', 'sv_bond_snap_1',
              'rv_risk_tensor_formal_materialize_v2',
              'cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v2',
              'tr_legacy'
            )
            """,
            [REPORT_DATE, Decimal("12.34")],
        )
    finally:
        conn.close()

    row = repo_mod.RiskTensorRepository(str(duckdb_path)).fetch_risk_tensor_row(REPORT_DATE)

    assert row is not None
    assert row["portfolio_dv01"] == Decimal("12.34000000")
    assert row["regulatory_dv01"] is None


def test_risk_tensor_dates_envelope_uses_risk_tensor_manifest_lineage(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize_risk_tensor(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )
    lineage_mod = load_module(
        "backend.app.governance.formal_compute_lineage",
        "backend/app/governance/formal_compute_lineage.py",
    )
    calls: list[dict[str, str]] = []

    def _capture(**kwargs):
        calls.append(kwargs)
        return lineage_mod.resolve_formal_manifest_lineage(**kwargs)

    monkeypatch.setattr(service_mod, "resolve_formal_manifest_lineage", _capture)

    payload = service_mod.risk_tensor_dates_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert len(calls) == 1
    assert calls[0]["cache_key"] == service_mod.CACHE_KEY
    assert Path(str(calls[0]["governance_dir"])).resolve() == Path(str(governance_dir)).resolve()
    assert payload["result_meta"]["result_kind"] == "risk.tensor.dates"
    assert payload["result_meta"]["source_version"]
    assert payload["result_meta"]["requested_report_date"] == REPORT_DATE
    assert payload["result_meta"]["resolved_report_date"] == REPORT_DATE
    assert payload["result_meta"]["as_of_date"] == REPORT_DATE
    assert payload["result_meta"]["date_basis"] == "formal_snapshot"
    assert payload["result"]["report_dates"] == [REPORT_DATE]
    get_settings.cache_clear()


def test_risk_tensor_dates_envelope_wraps_governance_lock_timeout_as_service_unavailable(
    tmp_path,
    monkeypatch,
):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize_risk_tensor(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )
    monkeypatch.setattr(
        service_mod,
        "load_latest_bond_analytics_lineage_by_report_date",
        lambda **_kwargs: (_ for _ in ()).throw(
            TimeoutError("Timed out acquiring lock lock:governance:jsonl:test")
        ),
    )

    try:
        service_mod.risk_tensor_dates_envelope(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )
    except RuntimeError as exc:
        assert str(exc) == "Risk tensor lineage store is temporarily unavailable."
    else:
        raise AssertionError("Expected RuntimeError for governance lock timeout")

    get_settings.cache_clear()


def test_risk_tensor_dates_envelope_fails_closed_when_manifest_missing(
    tmp_path,
    monkeypatch,
):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize_risk_tensor(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )

    monkeypatch.setattr(
        service_mod,
        "resolve_formal_manifest_lineage",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("missing manifest")),
    )

    with pytest.raises(RuntimeError, match="missing manifest"):
        service_mod.risk_tensor_dates_envelope(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )
    get_settings.cache_clear()


def test_risk_tensor_dates_envelope_blocks_stale_report_dates(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize_risk_tensor(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update zqtz_bond_daily_snapshot
            set source_version = ?
            where report_date = ?
              and instrument_code = 'CB-001'
            """,
            ["sv_bond_snap_2", REPORT_DATE],
        )
    finally:
        conn.close()

    bond_task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    bond_task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    payload = service_mod.risk_tensor_dates_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert payload["result"]["report_dates"] == []
    assert payload["result_meta"]["requested_report_date"] is None
    assert payload["result_meta"]["resolved_report_date"] is None
    assert payload["result_meta"]["as_of_date"] is None
    assert payload["result"]["blocked_report_dates"] == [
        {
            "report_date": REPORT_DATE,
            "reason": f"Risk tensor stale against bond analytics lineage for report_date={REPORT_DATE}.",
        }
    ]
    get_settings.cache_clear()


def test_risk_tensor_service_returns_404_when_report_date_has_no_upstream_or_downstream_artifact(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    service_mod = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )

    try:
        service_mod.risk_tensor_envelope(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            report_date=REPORT_DATE,
        )
    except ValueError as exc:
        assert str(exc) == f"No risk tensor data found for report_date={REPORT_DATE}."
    else:
        raise AssertionError("Expected ValueError for absent risk tensor artifacts")

    get_settings.cache_clear()


def test_risk_tensor_service_fails_when_upstream_exists_but_downstream_fact_is_missing(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )

    try:
        service_mod.risk_tensor_envelope(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            report_date=REPORT_DATE,
        )
    except RuntimeError as exc:
        assert "Risk tensor fact missing" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for missing downstream risk tensor fact")

    get_settings.cache_clear()


def test_risk_tensor_service_fails_when_downstream_fact_is_stale_against_newer_upstream_lineage(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize_risk_tensor(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update zqtz_bond_daily_snapshot
            set source_version = ?
            where report_date = ?
              and instrument_code = 'CB-001'
            """,
            ["sv_bond_snap_2", REPORT_DATE],
        )
    finally:
        conn.close()

    bond_task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    bond_task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    try:
        service_mod.risk_tensor_envelope(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            report_date=REPORT_DATE,
        )
    except RuntimeError as exc:
        assert "Risk tensor stale against bond analytics lineage" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for stale downstream risk tensor fact")

    get_settings.cache_clear()


def test_risk_tensor_service_returns_non_empty_degraded_tensor_when_materialized_snapshot_rows_are_partial(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize_degraded_snapshot(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )

    payload = service_mod.risk_tensor_envelope(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        report_date=REPORT_DATE,
    )

    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["quality_flag"] == "warning"
    assert payload["result_meta"]["source_version"] == "sv_risk_tensor__sv_bond_snap_1"

    result = payload["result"]
    assert result["bond_count"] == 3
    assert result["quality_flag"] == "warning"
    assert Decimal(str(result["portfolio_dv01"]["raw"])) > Decimal("0")
    assert result["duration_excluded_count"] >= 1
    assert result["duration_excluded_market_value"]["raw"] > 0
    assert result["rate_risk_market_value"]["raw"] < result["total_market_value"]["raw"]
    assert result["rate_risk_modified_duration"]["raw"] == result["portfolio_modified_duration"]["raw"]
    assert any("Non-standard tenor buckets remapped" in warning for warning in result["warnings"])
    assert any("without maturity_date" in warning for warning in result["warnings"])

    get_settings.cache_clear()


def test_risk_tensor_service_fails_when_downstream_fact_is_stale_against_newer_tyw_liability_lineage(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize_risk_tensor_with_tyw_liability(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update fact_formal_tyw_balance_daily
            set source_version = ?
            where report_date = ?
              and position_id = 'TYW-L-1'
            """,
            ["sv_tyw_liab_2", REPORT_DATE],
        )
    finally:
        conn.close()

    try:
        service_mod.risk_tensor_envelope(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            report_date=REPORT_DATE,
        )
    except RuntimeError as exc:
        assert "Risk tensor stale against TYW liability lineage" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for stale TYW liability lineage")

    get_settings.cache_clear()


def test_risk_tensor_service_fails_when_downstream_fact_is_stale_against_newer_tyw_liability_rule_version(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _task_mod = _configure_and_materialize_risk_tensor_with_tyw_liability(tmp_path, monkeypatch)
    service_mod = load_module(
        "backend.app.services.risk_tensor_service",
        "backend/app/services/risk_tensor_service.py",
    )

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update fact_formal_tyw_balance_daily
            set rule_version = ?
            where report_date = ?
              and position_id = 'TYW-L-1'
            """,
            ["rv_balance_analysis_formal_materialize_v2", REPORT_DATE],
        )
    finally:
        conn.close()

    try:
        service_mod.risk_tensor_envelope(
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
            report_date=REPORT_DATE,
        )
    except RuntimeError as exc:
        assert "Risk tensor stale against TYW liability lineage" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError for stale TYW liability rule_version")

    get_settings.cache_clear()
