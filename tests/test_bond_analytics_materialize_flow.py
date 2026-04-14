from __future__ import annotations

import json
import sys
from decimal import Decimal

import duckdb
import pytest

from tests.helpers import load_module


REPORT_DATE = "2026-03-31"


def _load_modules():
    repo_mod = sys.modules.get("backend.app.repositories.bond_analytics_repo")
    if repo_mod is None:
        repo_mod = load_module(
            "backend.app.repositories.bond_analytics_repo",
            "backend/app/repositories/bond_analytics_repo.py",
        )
    task_mod = sys.modules.get("backend.app.tasks.bond_analytics_materialize")
    if task_mod is None:
        task_mod = load_module(
            "backend.app.tasks.bond_analytics_materialize",
            "backend/app/tasks/bond_analytics_materialize.py",
        )
    return repo_mod, task_mod


def _seed_bond_snapshot_rows(duckdb_path: str) -> None:
    snapshot_mod = sys.modules.get("backend.app.repositories.snapshot_repo")
    if snapshot_mod is None:
        snapshot_mod = load_module(
            "backend.app.repositories.snapshot_repo",
            "backend/app/repositories/snapshot_repo.py",
        )

    conn = duckdb.connect(duckdb_path, read_only=False)
    try:
        snapshot_mod.ensure_snapshot_tables(conn)
        rows = [
            [
                REPORT_DATE,
                "TB-001",
                "国债1号",
                "组合利率",
                "CC-RATE",
                "持有至到期投资",
                "利率债",
                "国债",
                "财政部",
                "政府",
                "AAA",
                "CNY",
                Decimal("100"),
                Decimal("99"),
                Decimal("98.5"),
                Decimal("1.0"),
                Decimal("0.02"),
                Decimal("0.018"),
                "2027-03-31",
                None,
                0,
                False,
                "固定",
                "sv_bond_snap_1",
                "rv_bond_snap_1",
                "ib_bond_1",
                "trace_tb_1",
            ],
            [
                REPORT_DATE,
                "CB-001",
                "企业债1号",
                "组合信用",
                "CC-CREDIT",
                "可供出售类资产",
                "信用债",
                "企业债",
                "发行人甲",
                "工业",
                "AAA",
                "CNY",
                Decimal("200"),
                Decimal("190"),
                Decimal("188"),
                Decimal("2.0"),
                Decimal("0.03"),
                Decimal("0.032"),
                "2031-03-31",
                None,
                0,
                False,
                "固定",
                "sv_bond_snap_1",
                "rv_bond_snap_1",
                "ib_bond_1",
                "trace_cb_1",
            ],
            [
                REPORT_DATE,
                "CB-002",
                "公司债2号",
                "组合交易",
                "CC-TPL",
                "交易性金融资产",
                "信用债",
                "公司债",
                "发行人乙",
                "地产",
                "AA+",
                "CNY",
                Decimal("150"),
                Decimal("140"),
                Decimal("138"),
                Decimal("1.5"),
                Decimal("0.04"),
                Decimal("0.045"),
                "2036-03-31",
                None,
                0,
                False,
                "固定",
                "sv_bond_snap_1",
                "rv_bond_snap_1",
                "ib_bond_1",
                "trace_cb_2",
            ],
            [
                REPORT_DATE,
                "ISS-001",
                "发行类债券",
                "组合发行",
                "CC-ISSUE",
                "持有至到期投资",
                "发行类",
                "同业存单",
                "本行",
                "金融",
                "AAA",
                "CNY",
                Decimal("120"),
                Decimal("120"),
                Decimal("120"),
                Decimal("0"),
                Decimal("0.02"),
                Decimal("0.021"),
                "2027-03-31",
                None,
                0,
                True,
                "固定",
                "sv_bond_snap_1",
                "rv_bond_snap_1",
                "ib_bond_1",
                "trace_issue_1",
            ],
        ]
        conn.executemany(
            """
            insert into zqtz_bond_daily_snapshot (
              report_date, instrument_code, instrument_name, portfolio_name, cost_center,
              account_category, asset_class, bond_type, issuer_name, industry_name, rating,
              currency_code, face_value_native, market_value_native, amortized_cost_native,
              accrued_interest_native, coupon_rate, ytm_value, maturity_date, next_call_date,
              overdue_days, is_issuance_like, interest_mode, source_version, rule_version,
              ingest_batch_id, trace_id
            ) values (
              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            rows,
        )
    finally:
        conn.close()


BOND_ANALYTICS_TEST_YIELD_ANCHORS = ("2026-03-01", "2026-03-30", "2026-03-31")


def seed_yield_curves_for_bond_analytics_tests(duckdb_path: str) -> None:
    """Minimal formal yield curves so refresh-time `ensure_yield_curve_inputs_on_or_before` skips network fetches."""
    from backend.app.repositories.yield_curve_repo import YieldCurveRepository
    from backend.app.schemas.yield_curve import YieldCurvePoint, YieldCurveSnapshot
    from backend.app.tasks.yield_curve_materialize import RULE_VERSION

    repo = YieldCurveRepository(duckdb_path)
    points = [
        YieldCurvePoint("3M", Decimal("1.0")),
        YieldCurvePoint("6M", Decimal("1.1")),
        YieldCurvePoint("1Y", Decimal("1.5")),
        YieldCurvePoint("2Y", Decimal("1.6")),
        YieldCurvePoint("3Y", Decimal("1.8")),
        YieldCurvePoint("5Y", Decimal("2.0")),
        YieldCurvePoint("7Y", Decimal("2.2")),
        YieldCurvePoint("10Y", Decimal("2.5")),
        YieldCurvePoint("20Y", Decimal("2.8")),
        YieldCurvePoint("30Y", Decimal("3.0")),
    ]
    for trade_date in BOND_ANALYTICS_TEST_YIELD_ANCHORS:
        snapshots = [
            YieldCurveSnapshot(
                curve_type=curve_type,
                trade_date=trade_date,
                points=points,
                vendor_name="test_vendor",
                vendor_version="vv_test_yield",
                source_version="sv_test_yield",
            )
            for curve_type in ("treasury", "cdb", "aaa_credit")
        ]
        repo.replace_curve_snapshots(trade_date=trade_date, snapshots=snapshots, rule_version=RULE_VERSION)


def _materialize_sample_facts(tmp_path):
    repo_mod, task_mod = _load_modules()
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_bond_snapshot_rows(str(duckdb_path))
    payload = task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    repo = repo_mod.BondAnalyticsRepository(str(duckdb_path))
    return repo_mod, task_mod, duckdb_path, governance_dir, payload, repo


def test_bond_analytics_materialize_writes_fact_table_and_governance_records(tmp_path):
    repo_mod, task_mod = _load_modules()
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_bond_snapshot_rows(str(duckdb_path))

    payload = task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert payload["status"] == "completed"
    assert payload["report_date"] == REPORT_DATE
    assert payload["row_count"] == 3
    assert payload["source_version"] == "sv_bond_snap_1"
    assert payload["rule_version"] == task_mod.RULE_VERSION

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select instrument_code, asset_class_std, accounting_class, tenor_bucket, is_credit, source_version
            from fact_formal_bond_analytics_daily
            order by instrument_code
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [
        ("CB-001", "credit", "OCI", "5Y", True, "sv_bond_snap_1"),
        ("CB-002", "credit", "TPL", "10Y", True, "sv_bond_snap_1"),
        ("TB-001", "rate", "AC", "1Y", False, "sv_bond_snap_1"),
    ]

    repo = repo_mod.BondAnalyticsRepository(str(duckdb_path))
    assert repo.list_report_dates() == [REPORT_DATE]
    fetched_rows = repo.fetch_bond_analytics_rows(report_date=REPORT_DATE)
    assert [row["instrument_code"] for row in fetched_rows] == [
        "CB-001",
        "CB-002",
        "TB-001",
    ]
    assert {row["instrument_code"]: row["interest_mode"] for row in fetched_rows} == {
        "CB-001": "固定",
        "CB-002": "固定",
        "TB-001": "固定",
    }
    assert {row["instrument_code"]: row["interest_payment_frequency"] for row in fetched_rows} == {
        "CB-001": "annual",
        "CB-002": "annual",
        "TB-001": "annual",
    }
    assert {row["instrument_code"]: row["interest_rate_style"] for row in fetched_rows} == {
        "CB-001": "fixed",
        "CB-002": "fixed",
        "TB-001": "fixed",
    }
    assert [row["instrument_code"] for row in repo.fetch_bond_analytics_rows(report_date=REPORT_DATE, asset_class="credit")] == [
        "CB-001",
        "CB-002",
    ]
    assert [row["instrument_code"] for row in repo.fetch_bond_analytics_rows(report_date=REPORT_DATE, accounting_class="OCI")] == [
        "CB-001",
    ]

    risk = repo.fetch_portfolio_risk_summary(report_date=REPORT_DATE)
    assert risk["bond_count"] == 3
    assert risk["total_market_value"] == Decimal("429.00000000")
    assert risk["portfolio_dv01"] > Decimal("0")

    krd = repo.fetch_krd_distribution(report_date=REPORT_DATE)
    assert [row["tenor_bucket"] for row in krd] == ["10Y", "1Y", "5Y"]

    credit = repo.fetch_credit_summary(report_date=REPORT_DATE)
    assert credit["credit_bond_count"] == 2
    assert credit["credit_market_value"] == Decimal("330.00000000")
    assert credit["oci_credit_exposure"] == Decimal("190.00000000")

    audit = repo.fetch_accounting_audit(report_date=REPORT_DATE)
    assert {row["asset_class_raw"] for row in audit} == {"信用债", "利率债"}

    build_runs = [
        json.loads(line)
        for line in (governance_dir / "cache_build_run.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    manifests = [
        json.loads(line)
        for line in (governance_dir / "cache_manifest.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert build_runs[0]["status"] == "running"
    assert build_runs[-1]["status"] == "completed"
    assert build_runs[-1]["cache_key"] == task_mod.CACHE_KEY
    assert manifests[-1]["cache_key"] == task_mod.CACHE_KEY
    assert manifests[-1]["rule_version"] == task_mod.RULE_VERSION


def test_bond_analytics_materialize_preserves_lineage_when_write_fails(tmp_path, monkeypatch):
    repo_mod, task_mod = _load_modules()
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    _seed_bond_snapshot_rows(str(duckdb_path))

    def _fail_replace(self, **_kwargs):
        raise RuntimeError("synthetic bond analytics write failure")

    monkeypatch.setattr(
        repo_mod.BondAnalyticsRepository,
        "replace_bond_analytics_rows",
        _fail_replace,
    )

    with pytest.raises(RuntimeError, match="synthetic bond analytics write failure"):
        task_mod.materialize_bond_analytics_facts.fn(
            report_date=REPORT_DATE,
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )

    build_runs = [
        json.loads(line)
        for line in (governance_dir / "cache_build_run.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert build_runs[-1]["status"] == "failed"
    assert build_runs[-1]["source_version"] == "sv_bond_snap_1"


def test_bond_analytics_materialize_rerun_replaces_existing_rows_instead_of_duplicating(tmp_path):
    _repo_mod, task_mod, duckdb_path, governance_dir, first_payload, _repo = _materialize_sample_facts(tmp_path)

    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            update zqtz_bond_daily_snapshot
            set market_value_native = ?, source_version = ?
            where report_date = ? and instrument_code = ?
            """,
            [Decimal("210"), "sv_bond_snap_2", REPORT_DATE, "CB-001"],
        )
    finally:
        conn.close()

    second_payload = task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        row_count = conn.execute(
            """
            select count(*)
            from fact_formal_bond_analytics_daily
            where report_date = ?
            """,
            [REPORT_DATE],
        ).fetchone()[0]
        distinct_count = conn.execute(
            """
            select count(distinct instrument_code)
            from fact_formal_bond_analytics_daily
            where report_date = ?
            """,
            [REPORT_DATE],
        ).fetchone()[0]
        cb_001 = conn.execute(
            """
            select market_value, source_version
            from fact_formal_bond_analytics_daily
            where report_date = ? and instrument_code = ?
            """,
            [REPORT_DATE, "CB-001"],
        ).fetchone()
    finally:
        conn.close()

    assert first_payload["row_count"] == 3
    assert second_payload["row_count"] == 3
    assert second_payload["source_version"] == "sv_bond_snap_1__sv_bond_snap_2"
    assert row_count == 3
    assert distinct_count == 3
    assert cb_001 == (Decimal("210.00000000"), "sv_bond_snap_2")


def test_bond_analytics_materialize_computes_expected_duration_for_one_year_rate_bond(tmp_path):
    _repo_mod, _task_mod, duckdb_path, _governance_dir, _payload, _repo = _materialize_sample_facts(tmp_path)

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        tb_001 = conn.execute(
            """
            select years_to_maturity, macaulay_duration, modified_duration, dv01, spread_dv01
            from fact_formal_bond_analytics_daily
            where report_date = ? and instrument_code = ?
            """,
            [REPORT_DATE, "TB-001"],
        ).fetchone()
    finally:
        conn.close()

    expected_modified_duration = (Decimal("1") / Decimal("1.018")).quantize(Decimal("0.00000001"))
    expected_dv01 = (Decimal("99") * expected_modified_duration / Decimal("10000")).quantize(Decimal("0.00000001"))

    assert tb_001 == (
        Decimal("1.00000000"),
        Decimal("1.00000000"),
        expected_modified_duration,
        expected_dv01,
        Decimal("0E-8"),
    )


def test_bond_analytics_materialize_krd_distribution_has_expected_bucket_shape_and_totals(tmp_path):
    _repo_mod, _task_mod, _duckdb_path, _governance_dir, _payload, repo = _materialize_sample_facts(tmp_path)

    risk = repo.fetch_portfolio_risk_summary(report_date=REPORT_DATE)
    krd = repo.fetch_krd_distribution(report_date=REPORT_DATE)

    assert krd == [
        {
            "tenor_bucket": "10Y",
            "market_value": Decimal("140.00000000"),
            "dv01": Decimal("0.11250583"),
            "krd": Decimal("8.03613072"),
        },
        {
            "tenor_bucket": "1Y",
            "market_value": Decimal("99.00000000"),
            "dv01": Decimal("0.00972495"),
            "krd": Decimal("0.98231827"),
        },
        {
            "tenor_bucket": "5Y",
            "market_value": Decimal("190.00000000"),
            "dv01": Decimal("0.08681798"),
            "krd": Decimal("4.56936732"),
        },
    ]
    assert sum((row["market_value"] for row in krd), Decimal("0")) == risk["total_market_value"]
    assert sum((row["dv01"] for row in krd), Decimal("0")) == risk["portfolio_dv01"]


def test_bond_analytics_materialize_credit_filters_return_expected_fact_subset(tmp_path):
    _repo_mod, _task_mod, _duckdb_path, _governance_dir, _payload, repo = _materialize_sample_facts(tmp_path)

    assert [row["instrument_code"] for row in repo.fetch_bond_analytics_rows(report_date=REPORT_DATE, asset_class="credit")] == [
        "CB-001",
        "CB-002",
    ]
    assert [
        row["instrument_code"]
        for row in repo.fetch_bond_analytics_rows(
            report_date=REPORT_DATE,
            asset_class="credit",
            accounting_class="OCI",
        )
    ] == ["CB-001"]
    assert repo.fetch_bond_analytics_rows(
        report_date=REPORT_DATE,
        asset_class="rate",
        accounting_class="TPL",
    ) == []


def test_bond_analytics_materialize_accounting_audit_exposes_rule_trace_by_asset_class(tmp_path):
    _repo_mod, _task_mod, _duckdb_path, _governance_dir, _payload, repo = _materialize_sample_facts(tmp_path)

    audit_rows = {
        row["asset_class_raw"]: row
        for row in repo.fetch_accounting_audit(report_date=REPORT_DATE)
    }

    assert audit_rows["信用债"] == {
        "asset_class_raw": "信用债",
        "position_count": 2,
        "market_value": Decimal("330.00000000"),
        "market_value_weight": Decimal("0.7692307692307692307692307692"),
        "infer_accounting_class": "OCI",
        "map_accounting_class": "OCI",
        "infer_rule_id": "R010",
        "infer_match": "accounting_rule_id:R01*",
        "map_rule_id": "R010",
        "map_match": None,
        "is_divergent": False,
        "is_map_unclassified": False,
    }
    assert audit_rows["利率债"] == {
        "asset_class_raw": "利率债",
        "position_count": 1,
        "market_value": Decimal("99.00000000"),
        "market_value_weight": Decimal("0.2307692307692307692307692308"),
        "infer_accounting_class": "AC",
        "map_accounting_class": "AC",
        "infer_rule_id": "R001",
        "infer_match": "accounting_rule_id:R00*",
        "map_rule_id": "R001",
        "map_match": None,
        "is_divergent": False,
        "is_map_unclassified": False,
    }
