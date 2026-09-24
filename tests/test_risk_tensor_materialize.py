from __future__ import annotations

from contextlib import nullcontext
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.helpers import load_module
from tests.test_bond_analytics_materialize_flow import (
    REPORT_DATE,
    _seed_bond_snapshot_rows,
    seed_yield_curves_for_bond_analytics_tests,
)


def _read_jsonl(path):
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _configure_upstream(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_bond_snapshot_rows(str(duckdb_path))
    seed_yield_curves_for_bond_analytics_tests(str(duckdb_path))
    bond_task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    bond_task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    return duckdb_path, governance_dir, bond_task_mod


def _configure_upstream_with_semiannual_coupon(tmp_path):
    duckdb_path = tmp_path / "moss.semiannual.duckdb"
    governance_dir = tmp_path / "governance.semiannual"
    _seed_bond_snapshot_rows(str(duckdb_path))
    seed_yield_curves_for_bond_analytics_tests(str(duckdb_path))

    import duckdb

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update zqtz_bond_daily_snapshot
            set maturity_date = ?, coupon_rate = ?, interest_mode = ?, next_call_date = ?
            where report_date = ?
              and instrument_code = 'CB-001'
            """,
            ["2028-12-15", "8.0", "semi-annual", "2026-05-15", REPORT_DATE],
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
    return duckdb_path, governance_dir, bond_task_mod


def _base_discount_ncd_row() -> dict[str, object]:
    return {
        "instrument_code": "NCD-001",
        "bond_type": "同业存单",
        "maturity_date": "2026-06-30",
        "market_value": Decimal("98.5"),
        "face_value": Decimal("100"),
        "coupon_rate": None,
        "ytm": Decimal("0.018"),
        "accrued_interest": Decimal("0"),
        "modified_duration": Decimal("0.25"),
        "convexity": Decimal("0.01"),
        "dv01": Decimal("0.02"),
        "spread_dv01": Decimal("0.01"),
        "interest_payment_frequency_fallback_used": False,
    }


def _execute_risk_tensor_with_rows(monkeypatch, rows):
    task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )
    captured = {
        "compute_rows": None,
        "replace_calls": [],
    }

    monkeypatch.setattr(
        task_mod,
        "load_latest_bond_analytics_lineage",
        lambda **_kwargs: {
            "source_version": "sv_bond_snap_1",
            "rule_version": "rv_bond_analytics_formal_materialize_v2",
            "cache_version": "cv_bond_analytics_formal__rv_bond_analytics_formal_materialize_v2",
        },
    )
    monkeypatch.setattr(
        task_mod.BondAnalyticsRepository,
        "fetch_bond_analytics_rows",
        lambda self, *, report_date: rows,
    )
    monkeypatch.setattr(task_mod, "_load_liability_rows", lambda **_kwargs: [])
    monkeypatch.setattr(task_mod, "repository_task_write_scope", lambda *_args, **_kwargs: nullcontext())

    def _capture_compute(rows_arg, report_date_arg, *, liability_rows):
        captured["compute_rows"] = rows_arg
        assert report_date_arg.isoformat() == REPORT_DATE
        assert liability_rows == []
        return SimpleNamespace(
            bond_count=len(rows_arg),
            quality_flag="ok",
        )

    def _capture_replace(self, **kwargs):
        captured["replace_calls"].append(kwargs)

    monkeypatch.setattr(task_mod, "compute_portfolio_risk_tensor", _capture_compute)
    monkeypatch.setattr(task_mod.RiskTensorRepository, "replace_risk_tensor_row", _capture_replace)

    result = task_mod._execute_risk_tensor_materialization(
        report_date=REPORT_DATE,
        duckdb_file=Path("ignored.duckdb"),
        governance_dir="ignored-governance",
    )
    return task_mod, result, captured


def test_risk_tensor_materialize_writes_fact_and_governance_records(tmp_path):
    duckdb_path, governance_dir, bond_task_mod = _configure_upstream(tmp_path)
    risk_task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )
    repo_mod = load_module(
        "backend.app.repositories.risk_tensor_repo",
        "backend/app/repositories/risk_tensor_repo.py",
    )

    payload = risk_task_mod.materialize_risk_tensor_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    row = repo_mod.RiskTensorRepository(str(duckdb_path)).fetch_risk_tensor_row(REPORT_DATE)
    build_runs = _read_jsonl(governance_dir / "cache_build_run.jsonl")
    manifests = _read_jsonl(governance_dir / "cache_manifest.jsonl")

    assert payload["status"] == "completed"
    assert payload["cache_key"] == risk_task_mod.CACHE_KEY
    assert payload["rule_version"] == risk_task_mod.RULE_VERSION
    assert payload["source_version"] == "sv_risk_tensor__sv_bond_snap_1"
    assert payload["payload"]["run"]["status"] == "completed"
    assert payload["payload"]["lineage"]["module_name"] == "risk_tensor"
    assert payload["payload"]["lineage"]["basis"] == "formal"
    assert payload["payload"]["lineage"]["source_version"] == payload["source_version"]
    assert payload["payload"]["lineage"]["rule_version"] == payload["rule_version"]
    assert payload["payload"]["lineage"]["vendor_version"] == payload["vendor_version"]
    assert payload["payload"]["result"]["bond_count"] == 3
    assert row is not None
    assert row["source_version"] == "sv_risk_tensor__sv_bond_snap_1"
    assert row["upstream_source_version"] == "sv_bond_snap_1"
    assert row["upstream_rule_version"] == bond_task_mod.RULE_VERSION
    assert row["upstream_cache_version"] == bond_task_mod.CACHE_VERSION
    assert row["cache_version"] == risk_task_mod.CACHE_VERSION
    assert row["bond_count"] == 3
    assert row["regulatory_dv01"] == row["portfolio_dv01"]
    assert row["asset_cashflow_30d"] == row["liquidity_gap_30d"]
    assert row["asset_cashflow_90d"] == row["liquidity_gap_90d"]
    assert row["liability_cashflow_30d"] == 0
    assert row["liability_cashflow_90d"] == 0
    assert row["liquidity_gap_30d"] == row["asset_cashflow_30d"] - row["liability_cashflow_30d"]
    projection_quality_fields = (
        "missing_maturity_market_value",
        "missing_maturity_count",
        "floating_rate_proxy_market_value",
        "floating_rate_proxy_count",
        "payment_frequency_fallback_market_value",
        "payment_frequency_fallback_count",
        "bullet_value_date_fallback_market_value",
        "bullet_value_date_fallback_count",
    )
    assert all(row[field_name] is not None for field_name in projection_quality_fields)
    assert any(record["cache_key"] == bond_task_mod.CACHE_KEY for record in build_runs)
    assert any(record["cache_key"] == risk_task_mod.CACHE_KEY and record["status"] == "completed" for record in build_runs)
    assert any(record["cache_key"] == risk_task_mod.CACHE_KEY and record["cache_version"] == risk_task_mod.CACHE_VERSION for record in manifests)


def test_risk_tensor_materialize_requires_completed_upstream_lineage(tmp_path):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    risk_task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )

    with pytest.raises(RuntimeError, match="requires completed bond_analytics lineage"):
        risk_task_mod.materialize_risk_tensor_facts.fn(
            report_date=REPORT_DATE,
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )


@pytest.mark.parametrize(
    "missing_field",
    ("source_version", "rule_version", "cache_version"),
)
def test_risk_tensor_materialize_requires_complete_upstream_lineage_triple(
    tmp_path,
    monkeypatch,
    missing_field,
):
    duckdb_path, governance_dir, bond_task_mod = _configure_upstream(tmp_path)
    risk_task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )
    repo_mod = load_module(
        "backend.app.repositories.risk_tensor_repo",
        "backend/app/repositories/risk_tensor_repo.py",
    )
    upstream_lineage = {
        "source_version": "sv_bond_snap_1",
        "rule_version": bond_task_mod.RULE_VERSION,
        "cache_version": bond_task_mod.CACHE_VERSION,
    }
    upstream_lineage[missing_field] = ""
    monkeypatch.setattr(
        risk_task_mod,
        "load_latest_bond_analytics_lineage",
        lambda **_kwargs: upstream_lineage,
    )

    with pytest.raises(RuntimeError, match="requires complete.*bond_analytics lineage"):
        risk_task_mod.materialize_risk_tensor_facts.fn(
            report_date=REPORT_DATE,
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )

    row = repo_mod.RiskTensorRepository(str(duckdb_path)).fetch_risk_tensor_row(REPORT_DATE)
    risk_runs = [
        record
        for record in _read_jsonl(governance_dir / "cache_build_run.jsonl")
        if record["cache_key"] == risk_task_mod.CACHE_KEY
    ]
    assert row is None
    assert risk_runs
    assert risk_runs[-1]["status"] == "failed"
    assert all(record["status"] != "completed" for record in risk_runs)


def test_risk_tensor_materialize_fails_closed_on_pct_style_bond_rates(tmp_path):
    duckdb_path, governance_dir, _bond_task_mod = _configure_upstream(tmp_path)
    risk_task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )

    import duckdb

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update fact_formal_bond_analytics_daily
            set coupon_rate = ?
            where report_date = ?
              and instrument_code = 'CB-001'
            """,
            ["2.5", REPORT_DATE],
        )
    finally:
        conn.close()

    with pytest.raises(RuntimeError, match="decimal-form bond analytics rates"):
        risk_task_mod.materialize_risk_tensor_facts.fn(
            report_date=REPORT_DATE,
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )


def test_risk_tensor_materialize_fails_closed_on_malformed_numeric_inputs(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _bond_task_mod = _configure_upstream(tmp_path)
    risk_task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )

    def _malformed_rows(self, *, report_date, asset_class="all", accounting_class="all"):
        return [
            {
                "instrument_code": "BAD-DV01",
                "market_value": Decimal("100"),
                "face_value": Decimal("100"),
                "coupon_rate": Decimal("0.03"),
                "modified_duration": Decimal("1.5"),
                "convexity": Decimal("0.2"),
                "dv01": "not-a-decimal",
                "spread_dv01": Decimal("0"),
                "tenor_bucket": "5Y",
                "is_credit": False,
                "maturity_date": "2030-01-01",
                "interest_mode": "annual",
                "issuer_name": "Issuer Bad",
                "interest_payment_frequency_fallback_used": False,
            }
        ]

    monkeypatch.setattr(
        risk_task_mod.BondAnalyticsRepository,
        "fetch_bond_analytics_rows",
        _malformed_rows,
    )

    with pytest.raises(RuntimeError, match="parseable numeric formal inputs"):
        risk_task_mod.materialize_risk_tensor_facts.fn(
            report_date=REPORT_DATE,
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),

        )


def test_risk_tensor_materialize_normalizes_eligible_discount_ncd_coupon_locally(monkeypatch):
    source_row = _base_discount_ncd_row()

    task_mod, result, captured = _execute_risk_tensor_with_rows(monkeypatch, [source_row])

    assert source_row["coupon_rate"] is None
    assert captured["compute_rows"] is not None
    assert captured["compute_rows"] != [source_row]
    assert captured["compute_rows"][0] is not source_row
    assert captured["compute_rows"][0]["coupon_rate"] == Decimal("0")
    assert captured["replace_calls"]
    assert result.source_version == "sv_risk_tensor__sv_bond_snap_1"
    assert result.payload["bond_count"] == 1
    assert result.payload["quality_flag"] == "ok"
    assert result.payload["upstream_cache_key"] == task_mod.BOND_ANALYTICS_CACHE_KEY
    assert result.payload["coupon_normalization_rule_id"] == "ncd_zero_coupon_coupon_rate_v1"
    assert result.payload["coupon_normalized_row_count"] == 1
    assert result.payload["coupon_normalized_market_value"] == "98.5"



def test_risk_tensor_materialize_fails_closed_on_unknown_payment_frequency_provenance(monkeypatch):
    source_row = _base_discount_ncd_row()
    source_row["interest_payment_frequency_fallback_used"] = None
    task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )
    monkeypatch.setattr(
        task_mod,
        "load_latest_bond_analytics_lineage",
        lambda **_kwargs: {
            "source_version": "sv_bond_snap_1",
            "rule_version": "rv_bond_analytics_formal_materialize_v2",
            "cache_version": "cv_bond_analytics_formal__rv_bond_analytics_formal_materialize_v2",
        },
    )
    monkeypatch.setattr(
        task_mod.BondAnalyticsRepository,
        "fetch_bond_analytics_rows",
        lambda self, *, report_date: [source_row],
    )
    monkeypatch.setattr(task_mod, "_load_liability_rows", lambda **_kwargs: [])

    with pytest.raises(RuntimeError, match="payment-frequency fallback provenance"):
        task_mod._execute_risk_tensor_materialization(
            report_date=REPORT_DATE,
            duckdb_file=Path("ignored.duckdb"),
            governance_dir="ignored-governance",
        )

def test_risk_tensor_materialize_leaves_non_null_coupon_unchanged(monkeypatch):
    source_row = _base_discount_ncd_row()
    source_row["coupon_rate"] = Decimal("0.021")

    _task_mod, result, captured = _execute_risk_tensor_with_rows(monkeypatch, [source_row])

    assert source_row["coupon_rate"] == Decimal("0.021")
    assert captured["compute_rows"] is not None
    assert captured["compute_rows"][0]["coupon_rate"] == Decimal("0.021")
    assert result.payload["coupon_normalized_row_count"] == 0
    assert result.payload["coupon_normalized_market_value"] == "0"


def _coupon_bond_fact_row(
    code: str,
    *,
    coupon_rate,
    ytm,
    market_value,
) -> dict[str, object]:
    return {
        "instrument_code": code,
        "bond_type": "企业债",
        "maturity_date": "2036-01-15",
        "market_value": market_value,
        "face_value": Decimal("100"),
        "coupon_rate": coupon_rate,
        "ytm": ytm,
        "accrued_interest": Decimal("0"),
        "modified_duration": Decimal("8.53"),
        "convexity": Decimal("81"),
        "dv01": Decimal("0.0853"),
        "spread_dv01": Decimal("0.0853"),
        "interest_payment_frequency_fallback_used": False,
    }


def test_risk_tensor_materialize_reports_ytm_par_fallback_aggregate(monkeypatch):
    """W-fi-2026-08 P1：有票息但 ytm 缺失/非正的行（上游按 par 假设算久期/DV01）
    在物化结果元数据中做聚合披露；无行级 provenance 列，schema 不变。"""
    rows = [
        # 有票息 + ytm 缺失 → 计入
        _coupon_bond_fact_row(
            "PAR-FB-001", coupon_rate=Decimal("0.03"), ytm=None, market_value=Decimal("120")
        ),
        # 有票息 + ytm 非正 → 计入
        _coupon_bond_fact_row(
            "PAR-FB-002", coupon_rate=Decimal("0.028"), ytm=Decimal("0"), market_value=Decimal("80")
        ),
        # 有票息 + ytm 正常 → 不计入
        _coupon_bond_fact_row(
            "NORMAL-001", coupon_rate=Decimal("0.03"), ytm=Decimal("0.025"), market_value=Decimal("500")
        ),
        # 零票息 + ytm 缺失（零息回退口径本就正确）→ 不计入
        _coupon_bond_fact_row(
            "ZERO-001", coupon_rate=Decimal("0"), ytm=None, market_value=Decimal("300")
        ),
    ]

    _task_mod, result, _captured = _execute_risk_tensor_with_rows(monkeypatch, rows)

    assert result.payload["ytm_par_fallback_rule_id"] == "ytm_par_fallback_duration_v1"
    assert result.payload["ytm_par_fallback_row_count"] == 2
    assert result.payload["ytm_par_fallback_market_value"] == "200"


def test_risk_tensor_materialize_ytm_par_fallback_zero_when_all_ytm_present(monkeypatch):
    rows = [
        _coupon_bond_fact_row(
            "NORMAL-001", coupon_rate=Decimal("0.03"), ytm=Decimal("0.025"), market_value=Decimal("500")
        ),
    ]

    _task_mod, result, _captured = _execute_risk_tensor_with_rows(monkeypatch, rows)

    assert result.payload["ytm_par_fallback_row_count"] == 0
    assert result.payload["ytm_par_fallback_market_value"] == "0"


@pytest.mark.parametrize(
    ("case_name", "mutate_row"),
    [
        ("wrong_bond_type", lambda row: row.update({"bond_type": "政策性金融债"})),
        ("nonfuture_maturity", lambda row: row.update({"maturity_date": REPORT_DATE})),
        ("bad_maturity", lambda row: row.update({"maturity_date": "not-a-date"})),
        ("missing_ytm", lambda row: row.update({"ytm": None})),
        ("nonpositive_ytm", lambda row: row.update({"ytm": Decimal("0")})),
        ("nonfinite_ytm", lambda row: row.update({"ytm": Decimal("NaN")})),
        ("out_of_bound_ytm", lambda row: row.update({"ytm": Decimal("1.2")})),
        ("nonzero_accrued_interest", lambda row: row.update({"accrued_interest": Decimal("0.01")})),
        ("invalid_accrued_interest", lambda row: row.update({"accrued_interest": "bad"})),
        ("nonpositive_face_value", lambda row: row.update({"face_value": Decimal("0")})),
        ("nonpositive_market_value", lambda row: row.update({"market_value": Decimal("0")})),
        ("market_value_not_below_face", lambda row: row.update({"market_value": Decimal("100")})),
    ],
    ids=lambda value: value if isinstance(value, str) else None,
)
def test_risk_tensor_materialize_fails_closed_when_discount_ncd_predicate_not_fully_met(
    monkeypatch,
    case_name,
    mutate_row,
):
    task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )
    source_row = _base_discount_ncd_row()
    mutate_row(source_row)
    compute_calls = []
    replace_calls = []

    monkeypatch.setattr(
        task_mod,
        "load_latest_bond_analytics_lineage",
        lambda **_kwargs: {
            "source_version": "sv_bond_snap_1",
            "rule_version": "rv_bond_analytics_formal_materialize_v2",
            "cache_version": "cv_bond_analytics_formal__rv_bond_analytics_formal_materialize_v2",
        },
    )
    monkeypatch.setattr(
        task_mod.BondAnalyticsRepository,
        "fetch_bond_analytics_rows",
        lambda self, *, report_date: [source_row],
    )
    monkeypatch.setattr(task_mod, "_load_liability_rows", lambda **_kwargs: [])
    monkeypatch.setattr(task_mod, "repository_task_write_scope", lambda *_args, **_kwargs: nullcontext())

    def _unexpected_compute(*_args, **_kwargs):
        compute_calls.append(case_name)
        raise AssertionError("compute should not be called")

    def _unexpected_replace(self, **_kwargs):
        replace_calls.append(case_name)
        raise AssertionError("write should not be called")

    monkeypatch.setattr(task_mod, "compute_portfolio_risk_tensor", _unexpected_compute)
    monkeypatch.setattr(task_mod.RiskTensorRepository, "replace_risk_tensor_row", _unexpected_replace)

    with pytest.raises(RuntimeError, match="parseable numeric formal inputs"):
        task_mod._execute_risk_tensor_materialization(
            report_date=REPORT_DATE,
            duckdb_file=Path("ignored.duckdb"),
            governance_dir="ignored-governance",
        )

    assert compute_calls == []
    assert replace_calls == []


def test_risk_tensor_materialize_preserves_computed_source_version_when_write_fails(tmp_path, monkeypatch):
    duckdb_path, governance_dir, _bond_task_mod = _configure_upstream(tmp_path)
    risk_task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )
    def _fail_replace(self, **_kwargs):
        raise RuntimeError("synthetic risk tensor write failure")

    monkeypatch.setattr(
        risk_task_mod.RiskTensorRepository,
        "replace_risk_tensor_row",
        _fail_replace,
    )

    with pytest.raises(RuntimeError, match="synthetic risk tensor write failure"):
        risk_task_mod.materialize_risk_tensor_facts.fn(
            report_date=REPORT_DATE,
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )

    build_runs = _read_jsonl(governance_dir / "cache_build_run.jsonl")
    risk_runs = [row for row in build_runs if row["cache_key"] == risk_task_mod.CACHE_KEY]
    assert risk_runs[-1]["status"] == "failed"
    assert risk_runs[-1]["source_version"] == "sv_risk_tensor__sv_bond_snap_1"
    assert risk_runs[-1]["finished_at"]
    assert risk_runs[-1]["failure_category"] == "materialize_failure"


def test_risk_tensor_module_descriptor_registers_without_collision():
    registry_mod = load_module(
        "backend.app.core_finance.module_registry",
        "backend/app/core_finance/module_registry.py",
    )
    bond_task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    risk_task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )

    descriptor = registry_mod.get_formal_module("risk_tensor")

    assert descriptor.cache_key == risk_task_mod.CACHE_KEY
    assert descriptor.cache_key != bond_task_mod.CACHE_KEY
    assert descriptor.lock_key != bond_task_mod.BOND_ANALYTICS_LOCK.key
    assert descriptor.rule_version == "rv_risk_tensor_formal_materialize_v6"
    assert (
        descriptor.cache_version == "cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v6"
    )


def test_risk_tensor_materialize_uses_materialized_interest_mode_for_coupon_windows(tmp_path):
    duckdb_path, governance_dir, _bond_task_mod = _configure_upstream_with_semiannual_coupon(tmp_path)
    risk_task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )
    repo_mod = load_module(
        "backend.app.repositories.risk_tensor_repo",
        "backend/app/repositories/risk_tensor_repo.py",
    )

    risk_task_mod.materialize_risk_tensor_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    row = repo_mod.RiskTensorRepository(str(duckdb_path)).fetch_risk_tensor_row(REPORT_DATE)

    assert row is not None
    assert row["liquidity_gap_30d"] == 8
    assert row["liquidity_gap_90d"] == 16
    assert row["asset_cashflow_30d"] == 8
    assert row["asset_cashflow_90d"] == 16
    assert row["liability_cashflow_30d"] == 0
    assert row["liability_cashflow_90d"] == 0
    assert any("Embedded optionality" in warning for warning in row["warnings"])


def test_risk_tensor_materialize_nets_formal_tyw_liability_cashflows(tmp_path):
    duckdb_path, governance_dir, _bond_task_mod = _configure_upstream(tmp_path)
    risk_task_mod = load_module(
        "backend.app.tasks.risk_tensor_materialize",
        "backend/app/tasks/risk_tensor_materialize.py",
    )
    repo_mod = load_module(
        "backend.app.repositories.risk_tensor_repo",
        "backend/app/repositories/risk_tensor_repo.py",
    )

    import duckdb

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
                Decimal("4"),
                Decimal("0"),
                Decimal("0"),
                "2026-04-10",
                "sv_tyw_liab_1",
                "rv_balance_analysis_formal_materialize_v1",
                "ib-liab-1",
                "trace-liab-1",
            ],
        )
    finally:
        conn.close()

    risk_task_mod.materialize_risk_tensor_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    row = repo_mod.RiskTensorRepository(str(duckdb_path)).fetch_risk_tensor_row(REPORT_DATE)

    assert row is not None
    assert row["liability_source_version"] == "sv_tyw_liab_1"
    assert row["liability_rule_version"] == "rv_balance_analysis_formal_materialize_v1"
    assert row["source_version"] == "sv_risk_tensor__sv_bond_snap_1__sv_tyw_liab_1"
    assert row["asset_cashflow_30d"] == 14
    assert row["asset_cashflow_90d"] == 14
    assert row["liability_cashflow_30d"] == 4
    assert row["liability_cashflow_90d"] == 4
    assert row["liquidity_gap_30d"] == 10
    assert row["liquidity_gap_90d"] == 10
    assert row["liquidity_gap_30d"] == row["asset_cashflow_30d"] - row["liability_cashflow_30d"]
