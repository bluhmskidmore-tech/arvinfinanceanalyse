from __future__ import annotations

import json
import sys
from decimal import Decimal

import duckdb
import pytest

from tests.helpers import load_module


def _load_yield_curve_task_module():
    task_mod = sys.modules.get("backend.app.tasks.yield_curve_materialize")
    if task_mod is None:
        task_mod = load_module(
            "backend.app.tasks.yield_curve_materialize",
            "backend/app/tasks/yield_curve_materialize.py",
        )
    return task_mod


def _read_jsonl(path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _curve_snapshot(schema_module, *, curve_type: str, vendor_name: str, source_version: str, vendor_version: str):
    return schema_module.YieldCurveSnapshot(
        curve_type=curve_type,
        trade_date="2026-04-10",
        points=[
            schema_module.YieldCurvePoint("1Y", Decimal("1.10")),
            schema_module.YieldCurvePoint("3Y", Decimal("1.30")),
            schema_module.YieldCurvePoint("5Y", Decimal("1.50")),
            schema_module.YieldCurvePoint("10Y", Decimal("1.80")),
            schema_module.YieldCurvePoint("20Y", Decimal("2.10")),
            schema_module.YieldCurvePoint("30Y", Decimal("2.40")),
            schema_module.YieldCurvePoint("6M", Decimal("1.00")),
        ],
        vendor_name=vendor_name,
        vendor_version=vendor_version,
        source_version=source_version,
    )


def test_materialize_yield_curve_aaa_credit_fail_closed_when_fetch_fails(tmp_path, monkeypatch):
    task_mod = _load_yield_curve_task_module()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setattr(
        task_mod,
        "_load_aaa_credit_curve_from_choice_snapshot",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        task_mod.VendorAdapter,
        "_fetch_akshare_curve",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        task_mod.VendorAdapter,
        "_fetch_choice_curve",
        lambda *_args, **_kwargs: None,
    )

    with pytest.raises(RuntimeError, match="Failed to materialize aaa_credit curve"):
        task_mod.materialize_yield_curve.fn(
            trade_date="2026-04-10",
            curve_types=["aaa_credit"],
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )


def test_materialize_yield_curve_treasury_akshare_unavailable_choice_fallback_persists(tmp_path, monkeypatch):
    """Regression: treasury primary is AkShare; when AkShare returns no snapshot, Choice must succeed."""
    task_mod = _load_yield_curve_task_module()
    schema_mod = load_module(
        "backend.app.schemas.yield_curve",
        "backend/app/schemas/yield_curve.py",
    )

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"

    def akshare_empty(self, *, curve_type: str, trade_date: str):
        return None

    def choice_ok(self, *, curve_type: str, trade_date: str):
        return _curve_snapshot(
            schema_mod,
            curve_type=curve_type,
            vendor_name="choice",
            source_version="sv_treasury_choice_fb",
            vendor_version="vv_choice_fb",
        )

    monkeypatch.setattr(task_mod.VendorAdapter, "_fetch_akshare_curve", akshare_empty)
    monkeypatch.setattr(task_mod.VendorAdapter, "_fetch_choice_curve", choice_ok)

    payload = task_mod.materialize_yield_curve.fn(
        trade_date="2026-04-10",
        curve_types=["treasury"],
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert payload["status"] == "completed"
    assert payload["curve_types"] == ["treasury"]
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        row = conn.execute(
            """
            select vendor_name, source_version
            from fact_formal_yield_curve_daily
            where curve_type = 'treasury'
            limit 1
            """
        ).fetchone()
    finally:
        conn.close()
    assert row == ("choice", "sv_treasury_choice_fb")


def test_materialize_yield_curve_cdb_akshare_unavailable_choice_fallback_persists(tmp_path, monkeypatch):
    """Regression: cdb tries AkShare, then Choice, then ChinaBond gkh; stop after Choice when it succeeds."""
    task_mod = _load_yield_curve_task_module()
    schema_mod = load_module(
        "backend.app.schemas.yield_curve",
        "backend/app/schemas/yield_curve.py",
    )

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"

    def akshare_empty(self, *, curve_type: str, trade_date: str):
        return None

    def choice_ok(self, *, curve_type: str, trade_date: str):
        return _curve_snapshot(
            schema_mod,
            curve_type=curve_type,
            vendor_name="choice",
            source_version="sv_cdb_choice_fb",
            vendor_version="vv_cdb_choice_fb",
        )

    def gkh_must_not_run(self, trade_date: str):
        raise AssertionError("ChinaBond gkh must not run when Choice fallback succeeds")

    monkeypatch.setattr(task_mod.VendorAdapter, "_fetch_akshare_curve", akshare_empty)
    monkeypatch.setattr(task_mod.VendorAdapter, "_fetch_choice_curve", choice_ok)
    monkeypatch.setattr(task_mod.VendorAdapter, "_fetch_chinabond_gkh_curve", gkh_must_not_run)

    payload = task_mod.materialize_yield_curve.fn(
        trade_date="2026-04-10",
        curve_types=["cdb"],
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert payload["status"] == "completed"
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        row = conn.execute(
            """
            select vendor_name, source_version
            from fact_formal_yield_curve_daily
            where curve_type = 'cdb'
            limit 1
            """
        ).fetchone()
    finally:
        conn.close()
    assert row == ("choice", "sv_cdb_choice_fb")


def test_materialize_yield_curve_unsupported_curve_type_fails_closed(tmp_path):
    task_mod = _load_yield_curve_task_module()
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"

    with pytest.raises(task_mod.FormalComputeMaterializeFailure, match="Unsupported curve_type"):
        task_mod.materialize_yield_curve.fn(
            trade_date="2026-04-10",
            curve_types=["not_a_supported_curve"],
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )


def test_materialize_aaa_credit_live_choice_before_akshare(tmp_path, monkeypatch):
    """Follow-on: Choice primary — live EDB before exact-family AkShare when DuckDB has no landed AAA."""
    task_mod = _load_yield_curve_task_module()
    schema_mod = load_module(
        "backend.app.schemas.yield_curve",
        "backend/app/schemas/yield_curve.py",
    )
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"

    monkeypatch.setattr(
        task_mod,
        "_load_aaa_credit_curve_from_choice_snapshot",
        lambda **_kwargs: None,
    )

    snap = schema_mod.YieldCurveSnapshot(
        curve_type="aaa_credit",
        trade_date="2026-04-10",
        points=[
            schema_mod.YieldCurvePoint("6M", Decimal("1.00")),
            schema_mod.YieldCurvePoint("1Y", Decimal("1.10")),
            schema_mod.YieldCurvePoint("2Y", Decimal("1.20")),
            schema_mod.YieldCurvePoint("3Y", Decimal("1.30")),
            schema_mod.YieldCurvePoint("5Y", Decimal("1.50")),
            schema_mod.YieldCurvePoint("7Y", Decimal("1.70")),
            schema_mod.YieldCurvePoint("10Y", Decimal("2.00")),
        ],
        vendor_name="choice",
        vendor_version="vv_choice_live",
        source_version="sv_choice_live_aaa",
    )

    def choice_live(self, *, curve_type: str, trade_date: str):
        assert curve_type == "aaa_credit"
        assert trade_date == "2026-04-10"
        return snap

    def akshare_must_not_run(self, *, curve_type: str, trade_date: str):
        raise AssertionError("AkShare must not run when live Choice returns aaa_credit")

    monkeypatch.setattr(task_mod.VendorAdapter, "_fetch_choice_curve", choice_live)
    monkeypatch.setattr(task_mod.VendorAdapter, "_fetch_akshare_curve", akshare_must_not_run)

    payload = task_mod.materialize_yield_curve.fn(
        trade_date="2026-04-10",
        curve_types=["aaa_credit"],
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert payload["status"] == "completed"
    assert payload["source_version"] == "sv_choice_live_aaa"
    assert payload["vendor_version"] == "vv_choice_live"


def test_materialize_yield_curve_dual_failure_writes_no_rows(tmp_path, monkeypatch):
    task_mod = _load_yield_curve_task_module()

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"

    def fail_fetch(*, curve_type: str, trade_date: str):
        raise RuntimeError(f"{curve_type} unavailable")

    monkeypatch.setattr(task_mod.VendorAdapter, "fetch_yield_curve", fail_fetch)

    with pytest.raises(RuntimeError, match="Failed to materialize treasury curve"):
        task_mod.materialize_yield_curve.fn(
            trade_date="2026-04-10",
            curve_types=["treasury", "cdb"],
            duckdb_path=str(duckdb_path),
            governance_dir=str(governance_dir),
        )

    if duckdb_path.exists():
        conn = duckdb.connect(str(duckdb_path), read_only=True)
        try:
            row = conn.execute(
                """
                select count(*)
                from information_schema.tables
                where table_name = 'fact_formal_yield_curve_daily'
                """
            ).fetchone()
            if row and row[0]:
                count = conn.execute(
                    "select count(*) from fact_formal_yield_curve_daily"
                ).fetchone()[0]
                assert count == 0
        finally:
            conn.close()

    build_runs = _read_jsonl(governance_dir / "cache_build_run.jsonl")
    manifests = _read_jsonl(governance_dir / "cache_manifest.jsonl")
    assert [record["status"] for record in build_runs] == ["queued", "running", "failed"]
    assert build_runs[-1]["failure_category"] == "materialize_failure"
    assert manifests == []


def test_materialize_yield_curve_persists_supported_curves(tmp_path, monkeypatch):
    task_mod = _load_yield_curve_task_module()
    schema_mod = load_module(
        "backend.app.schemas.yield_curve",
        "backend/app/schemas/yield_curve.py",
    )

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"

    def fetch_curve(self, *, curve_type: str, trade_date: str):
        if curve_type == "treasury":
            return _curve_snapshot(
                schema_mod,
                curve_type=curve_type,
                vendor_name="akshare",
                source_version="sv_treasury",
                vendor_version="vv_treasury",
            )
        return _curve_snapshot(
            schema_mod,
            curve_type=curve_type,
            vendor_name="choice",
            source_version="sv_cdb",
            vendor_version="vv_cdb",
        )

    monkeypatch.setattr(task_mod.VendorAdapter, "fetch_yield_curve", fetch_curve)

    payload = task_mod.materialize_yield_curve.fn(
        trade_date="2026-04-10",
        curve_types=["treasury", "cdb"],
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert payload["status"] == "completed"
    assert payload["curve_types"] == ["treasury", "cdb"]
    assert payload["point_count"] == 14

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select curve_type, count(*), min(vendor_name), max(source_version)
            from fact_formal_yield_curve_daily
            group by curve_type
            order by curve_type
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [
        ("cdb", 7, "choice", "sv_cdb"),
        ("treasury", 7, "akshare", "sv_treasury"),
    ]


def test_materialize_yield_curve_supports_single_curve_request(tmp_path, monkeypatch):
    task_mod = _load_yield_curve_task_module()
    schema_mod = load_module(
        "backend.app.schemas.yield_curve",
        "backend/app/schemas/yield_curve.py",
    )

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"

    def fetch_curve(self, *, curve_type: str, trade_date: str):
        assert curve_type == "treasury"
        return _curve_snapshot(
            schema_mod,
            curve_type=curve_type,
            vendor_name="akshare",
            source_version="sv_treasury",
            vendor_version="vv_treasury",
        )

    monkeypatch.setattr(task_mod.VendorAdapter, "fetch_yield_curve", fetch_curve)

    payload = task_mod.materialize_yield_curve.fn(
        trade_date="2026-04-10",
        curve_types=["treasury"],
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert payload["status"] == "completed"
    assert payload["curve_types"] == ["treasury"]
    assert payload["point_count"] == 7

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select distinct curve_type
            from fact_formal_yield_curve_daily
            order by curve_type
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [("treasury",)]


def test_materialize_yield_curve_supports_aaa_credit_request(tmp_path, monkeypatch):
    task_mod = _load_yield_curve_task_module()
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table phase1_macro_vendor_catalog (
              series_id varchar,
              series_name varchar,
              vendor_name varchar,
              vendor_version varchar,
              frequency varchar,
              unit varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_market_snapshot (
              series_id varchar,
              series_name varchar,
              vendor_series_code varchar,
              vendor_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.executemany(
            """
            insert into phase1_macro_vendor_catalog values (?, ?, ?, ?, ?, ?)
            """,
            [
                ("EMM00166654", "中债企业债到期收益率(AAA):6个月", "choice", "vv_choice_batch", "daily", "pct"),
                ("EMM00166655", "中债企业债到期收益率(AAA):1年", "choice", "vv_choice_batch", "daily", "pct"),
                ("EMM00166656", "中债企业债到期收益率(AAA):2年", "choice", "vv_choice_batch", "daily", "pct"),
                ("EMM00166657", "中债企业债到期收益率(AAA):3年", "choice", "vv_choice_batch", "daily", "pct"),
                ("EMM00166659", "中债企业债到期收益率(AAA):5年", "choice", "vv_choice_batch", "daily", "pct"),
                ("EMM00168470", "中债企业债到期收益率(AAA):6年", "choice", "vv_choice_batch", "daily", "pct"),
                ("EMM00166661", "中债企业债到期收益率(AAA):10年", "choice", "vv_choice_batch", "daily", "pct"),
            ],
        )
        conn.executemany(
            """
            insert into choice_market_snapshot values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("EMM00166654", "中债企业债到期收益率(AAA):6个月", "EMM00166654", "choice", "2026-04-10", 1.20, "daily", "pct", "sv_choice_macro", "vv_choice_batch", "rv_choice_macro", "run-1"),
                ("EMM00166655", "中债企业债到期收益率(AAA):1年", "EMM00166655", "choice", "2026-04-10", 1.30, "daily", "pct", "sv_choice_macro", "vv_choice_batch", "rv_choice_macro", "run-1"),
                ("EMM00166656", "中债企业债到期收益率(AAA):2年", "EMM00166656", "choice", "2026-04-10", 1.40, "daily", "pct", "sv_choice_macro", "vv_choice_batch", "rv_choice_macro", "run-1"),
                ("EMM00166657", "中债企业债到期收益率(AAA):3年", "EMM00166657", "choice", "2026-04-10", 1.50, "daily", "pct", "sv_choice_macro", "vv_choice_batch", "rv_choice_macro", "run-1"),
                ("EMM00166659", "中债企业债到期收益率(AAA):5年", "EMM00166659", "choice", "2026-04-10", 1.70, "daily", "pct", "sv_choice_macro", "vv_choice_batch", "rv_choice_macro", "run-1"),
                ("EMM00168470", "中债企业债到期收益率(AAA):6年", "EMM00168470", "choice", "2026-04-10", 1.80, "daily", "pct", "sv_choice_macro", "vv_choice_batch", "rv_choice_macro", "run-1"),
                ("EMM00166661", "中债企业债到期收益率(AAA):10年", "EMM00166661", "choice", "2026-04-10", 2.00, "daily", "pct", "sv_choice_macro", "vv_choice_batch", "rv_choice_macro", "run-1"),
            ],
        )
    finally:
        conn.close()

    monkeypatch.setattr(
        task_mod.VendorAdapter,
        "fetch_yield_curve",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("live vendor path should not be used")),
    )

    payload = task_mod.materialize_yield_curve.fn(
        trade_date="2026-04-10",
        curve_types=["aaa_credit"],
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert payload["status"] == "completed"
    assert payload["curve_types"] == ["aaa_credit"]
    assert payload["point_count"] == 8
    assert payload["source_version"] == "sv_choice_macro"
    assert payload["vendor_version"] == "vv_choice_batch"


def test_materialize_yield_curve_uses_fact_table_when_snapshot_table_has_no_requested_date(tmp_path, monkeypatch):
    task_mod = _load_yield_curve_task_module()
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table phase1_macro_vendor_catalog (
              series_id varchar,
              series_name varchar,
              vendor_name varchar,
              vendor_version varchar,
              frequency varchar,
              unit varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_market_snapshot (
              series_id varchar,
              series_name varchar,
              vendor_series_code varchar,
              vendor_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.executemany(
            "insert into phase1_macro_vendor_catalog values (?, ?, ?, ?, ?, ?)",
            [
                ("EMM00166654", "中债企业债到期收益率(AAA):6个月", "choice", "vv_choice_batch", "daily", "pct"),
                ("EMM00166655", "中债企业债到期收益率(AAA):1年", "choice", "vv_choice_batch", "daily", "pct"),
                ("EMM00166656", "中债企业债到期收益率(AAA):2年", "choice", "vv_choice_batch", "daily", "pct"),
                ("EMM00166657", "中债企业债到期收益率(AAA):3年", "choice", "vv_choice_batch", "daily", "pct"),
                ("EMM00166659", "中债企业债到期收益率(AAA):5年", "choice", "vv_choice_batch", "daily", "pct"),
                ("EMM00168470", "中债企业债到期收益率(AAA):6年", "choice", "vv_choice_batch", "daily", "pct"),
                ("EMM00166661", "中债企业债到期收益率(AAA):10年", "choice", "vv_choice_batch", "daily", "pct"),
            ],
        )
        conn.execute(
            """
            insert into choice_market_snapshot values
            ('EMM00166655','中债企业债到期收益率(AAA):1年','EMM00166655','choice','2026-04-09',1.30,'daily','pct','sv_old','vv_old','rv_old','run-old')
            """
        )
        conn.executemany(
            """
            insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("EMM00166654", "中债企业债到期收益率(AAA):6个月", "2026-04-10", 1.20, "daily", "pct", "sv_choice_fact", "vv_choice_fact", "rv_choice_macro", "ok", "run-1"),
                ("EMM00166655", "中债企业债到期收益率(AAA):1年", "2026-04-10", 1.30, "daily", "pct", "sv_choice_fact", "vv_choice_fact", "rv_choice_macro", "ok", "run-1"),
                ("EMM00166656", "中债企业债到期收益率(AAA):2年", "2026-04-10", 1.40, "daily", "pct", "sv_choice_fact", "vv_choice_fact", "rv_choice_macro", "ok", "run-1"),
                ("EMM00166657", "中债企业债到期收益率(AAA):3年", "2026-04-10", 1.50, "daily", "pct", "sv_choice_fact", "vv_choice_fact", "rv_choice_macro", "ok", "run-1"),
                ("EMM00166659", "中债企业债到期收益率(AAA):5年", "2026-04-10", 1.70, "daily", "pct", "sv_choice_fact", "vv_choice_fact", "rv_choice_macro", "ok", "run-1"),
                ("EMM00168470", "中债企业债到期收益率(AAA):6年", "2026-04-10", 1.80, "daily", "pct", "sv_choice_fact", "vv_choice_fact", "rv_choice_macro", "ok", "run-1"),
                ("EMM00166661", "中债企业债到期收益率(AAA):10年", "2026-04-10", 2.00, "daily", "pct", "sv_choice_fact", "vv_choice_fact", "rv_choice_macro", "ok", "run-1"),
            ],
        )
    finally:
        conn.close()

    monkeypatch.setattr(
        task_mod.VendorAdapter,
        "fetch_yield_curve",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("live vendor path should not be used")),
    )

    payload = task_mod.materialize_yield_curve.fn(
        trade_date="2026-04-10",
        curve_types=["aaa_credit"],
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert payload["status"] == "completed"
    assert payload["source_version"] == "sv_choice_fact"
    assert payload["vendor_version"] == "vv_choice_fact"


def test_materialize_yield_curve_prefers_complete_fact_when_same_day_snapshot_is_partial(tmp_path, monkeypatch):
    task_mod = _load_yield_curve_task_module()
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    conn = duckdb.connect(str(duckdb_path), read_only=False)
    try:
        conn.execute(
            """
            create table phase1_macro_vendor_catalog (
              series_id varchar,
              series_name varchar,
              vendor_name varchar,
              vendor_version varchar,
              frequency varchar,
              unit varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_market_snapshot (
              series_id varchar,
              series_name varchar,
              vendor_series_code varchar,
              vendor_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            create table fact_choice_macro_daily (
              series_id varchar,
              series_name varchar,
              trade_date varchar,
              value_numeric double,
              frequency varchar,
              unit varchar,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              quality_flag varchar,
              run_id varchar
            )
            """
        )
        conn.executemany(
            "insert into phase1_macro_vendor_catalog values (?, ?, ?, ?, ?, ?)",
            [
                ("EMM00166654", "中债企业债到期收益率(AAA):6个月", "choice", "vv_choice_batch", "daily", "pct"),
                ("EMM00166655", "中债企业债到期收益率(AAA):1年", "choice", "vv_choice_batch", "daily", "pct"),
                ("EMM00166656", "中债企业债到期收益率(AAA):2年", "choice", "vv_choice_batch", "daily", "pct"),
                ("EMM00166657", "中债企业债到期收益率(AAA):3年", "choice", "vv_choice_batch", "daily", "pct"),
                ("EMM00166659", "中债企业债到期收益率(AAA):5年", "choice", "vv_choice_batch", "daily", "pct"),
                ("EMM00168470", "中债企业债到期收益率(AAA):6年", "choice", "vv_choice_batch", "daily", "pct"),
                ("EMM00166661", "中债企业债到期收益率(AAA):10年", "choice", "vv_choice_batch", "daily", "pct"),
            ],
        )
        conn.executemany(
            """
            insert into choice_market_snapshot values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("EMM00166655", "中债企业债到期收益率(AAA):1年", "EMM00166655", "choice", "2026-04-10", 1.30, "daily", "pct", "sv_partial", "vv_partial", "rv_choice_macro", "run-1"),
                ("EMM00166657", "中债企业债到期收益率(AAA):3年", "EMM00166657", "choice", "2026-04-10", 1.50, "daily", "pct", "sv_partial", "vv_partial", "rv_choice_macro", "run-1"),
            ],
        )
        conn.executemany(
            """
            insert into fact_choice_macro_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("EMM00166654", "中债企业债到期收益率(AAA):6个月", "2026-04-10", 1.20, "daily", "pct", "sv_choice_fact", "vv_choice_fact", "rv_choice_macro", "ok", "run-1"),
                ("EMM00166655", "中债企业债到期收益率(AAA):1年", "2026-04-10", 1.30, "daily", "pct", "sv_choice_fact", "vv_choice_fact", "rv_choice_macro", "ok", "run-1"),
                ("EMM00166656", "中债企业债到期收益率(AAA):2年", "2026-04-10", 1.40, "daily", "pct", "sv_choice_fact", "vv_choice_fact", "rv_choice_macro", "ok", "run-1"),
                ("EMM00166657", "中债企业债到期收益率(AAA):3年", "2026-04-10", 1.50, "daily", "pct", "sv_choice_fact", "vv_choice_fact", "rv_choice_macro", "ok", "run-1"),
                ("EMM00166659", "中债企业债到期收益率(AAA):5年", "2026-04-10", 1.70, "daily", "pct", "sv_choice_fact", "vv_choice_fact", "rv_choice_macro", "ok", "run-1"),
                ("EMM00168470", "中债企业债到期收益率(AAA):6年", "2026-04-10", 1.80, "daily", "pct", "sv_choice_fact", "vv_choice_fact", "rv_choice_macro", "ok", "run-1"),
                ("EMM00166661", "中债企业债到期收益率(AAA):10年", "2026-04-10", 2.00, "daily", "pct", "sv_choice_fact", "vv_choice_fact", "rv_choice_macro", "ok", "run-1"),
            ],
        )
    finally:
        conn.close()

    monkeypatch.setattr(
        task_mod.VendorAdapter,
        "_fetch_akshare_curve",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("exact-family akshare fallback should not be used")),
    )

    payload = task_mod.materialize_yield_curve.fn(
        trade_date="2026-04-10",
        curve_types=["aaa_credit"],
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert payload["status"] == "completed"
    assert payload["source_version"] == "sv_choice_fact"
    assert payload["vendor_version"] == "vv_choice_fact"


def test_materialize_yield_curve_aaa_credit_uses_exact_family_akshare_only_when_no_landed_choice(tmp_path, monkeypatch):
    task_mod = _load_yield_curve_task_module()
    schema_mod = load_module(
        "backend.app.schemas.yield_curve",
        "backend/app/schemas/yield_curve.py",
    )
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"

    monkeypatch.setattr(
        task_mod.VendorAdapter,
        "_fetch_choice_curve",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        task_mod.VendorAdapter,
        "_fetch_akshare_curve",
        lambda _self, curve_type, trade_date: schema_mod.YieldCurveSnapshot(
            curve_type="aaa_credit",
            trade_date=trade_date,
            points=[
                schema_mod.YieldCurvePoint("6M", Decimal("1.20")),
                schema_mod.YieldCurvePoint("1Y", Decimal("1.30")),
                schema_mod.YieldCurvePoint("2Y", Decimal("1.40")),
                schema_mod.YieldCurvePoint("3Y", Decimal("1.50")),
                schema_mod.YieldCurvePoint("5Y", Decimal("1.70")),
                schema_mod.YieldCurvePoint("7Y", Decimal("1.85")),
                schema_mod.YieldCurvePoint("10Y", Decimal("2.00")),
            ],
            vendor_name="akshare",
            vendor_version="vv_aaa_akshare",
            source_version="sv_aaa_akshare",
        ),
    )

    payload = task_mod.materialize_yield_curve.fn(
        trade_date="2026-04-10",
        curve_types=["aaa_credit"],
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )

    assert payload["status"] == "completed"
    assert payload["vendor_version"] == "vv_aaa_akshare"


def test_yield_curve_module_declares_chinabond_gkh_input_source():
    task_mod = _load_yield_curve_task_module()

    assert "chinabond_gkh_yield_curve" in task_mod.YIELD_CURVE_MODULE.input_sources
    assert "choice_macro_snapshot" in task_mod.YIELD_CURVE_MODULE.input_sources


def test_backfill_yield_curve_month_end_uses_task_layer_and_preserves_resolved_trade_date(tmp_path, monkeypatch):
    task_mod = _load_yield_curve_task_module()
    schema_mod = load_module(
        "backend.app.schemas.yield_curve",
        "backend/app/schemas/yield_curve.py",
    )

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path))
    try:
        conn.execute("create table zqtz_bond_daily_snapshot (report_date varchar)")
        conn.execute("insert into zqtz_bond_daily_snapshot values ('2026-05-31')")
    finally:
        conn.close()

    requested_dates: list[str] = []

    def fetch_curve(self, *, curve_type: str, trade_date: str):
        requested_dates.append(f"{curve_type}:{trade_date}")
        if trade_date == "2026-05-31":
            raise RuntimeError("market closed")
        if trade_date == "2026-05-30":
            raise RuntimeError("market closed")
        return schema_mod.YieldCurveSnapshot(
            curve_type=curve_type,
            trade_date=trade_date,
            points=[
                schema_mod.YieldCurvePoint("6M", Decimal("1.00")),
                schema_mod.YieldCurvePoint("1Y", Decimal("1.10")),
                schema_mod.YieldCurvePoint("3Y", Decimal("1.30")),
                schema_mod.YieldCurvePoint("5Y", Decimal("1.50")),
                schema_mod.YieldCurvePoint("10Y", Decimal("1.80")),
                schema_mod.YieldCurvePoint("30Y", Decimal("2.40")),
            ],
            vendor_name="test_vendor",
            vendor_version=f"vv_{curve_type}",
            source_version=f"sv_{curve_type}",
        )

    monkeypatch.setattr(task_mod.VendorAdapter, "fetch_yield_curve", fetch_curve)

    payload = task_mod.backfill_yield_curve_month_ends(
        duckdb_path=str(duckdb_path),
        start_date="2026-05-01",
        end_date="2026-05-31",
        curve_types=("treasury",),
        max_backtrack_days=3,
    )

    assert payload == {
        "status": "completed",
        "duckdb_path": str(duckdb_path),
        "start_date": "2026-05-01",
        "end_date": "2026-05-31",
        "month_end_dates": ["2026-05-31"],
        "curve_types": ["treasury"],
        "total_tasks": 1,
        "written": 1,
        "skipped": 0,
        "failed": 0,
        "failures": [],
        "resolved_trade_dates": ["2026-05-29"],
        "resolved_snapshots": [
            {"anchor_date": "2026-05-31", "curve_type": "treasury", "trade_date": "2026-05-29"}
        ],
    }
    assert requested_dates == [
        "treasury:2026-05-31",
        "treasury:2026-05-30",
        "treasury:2026-05-29",
    ]

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select distinct trade_date, curve_type, source_version, rule_version
            from fact_formal_yield_curve_daily
            order by trade_date, curve_type
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [("2026-05-29", "treasury", "sv_treasury", task_mod.RULE_VERSION)]

    requested_dates.clear()
    rerun_payload = task_mod.backfill_yield_curve_month_ends(
        duckdb_path=str(duckdb_path),
        start_date="2026-05-01",
        end_date="2026-05-31",
        curve_types=("treasury",),
        max_backtrack_days=3,
    )

    assert rerun_payload["written"] == 0
    assert rerun_payload["skipped"] == 1
    assert requested_dates == [
        "treasury:2026-05-31",
        "treasury:2026-05-30",
        "treasury:2026-05-29",
    ]


def test_backfill_yield_curve_month_end_does_not_skip_stale_existing_snapshot(tmp_path, monkeypatch):
    task_mod = _load_yield_curve_task_module()
    schema_mod = load_module(
        "backend.app.schemas.yield_curve",
        "backend/app/schemas/yield_curve.py",
    )

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path))
    try:
        conn.execute("create table zqtz_bond_daily_snapshot (report_date varchar)")
        conn.execute("insert into zqtz_bond_daily_snapshot values ('2026-05-31')")
    finally:
        conn.close()

    stale_snapshot = schema_mod.YieldCurveSnapshot(
        curve_type="treasury",
        trade_date="2026-05-15",
        points=[
            schema_mod.YieldCurvePoint("6M", Decimal("0.90")),
            schema_mod.YieldCurvePoint("1Y", Decimal("1.00")),
        ],
        vendor_name="old_vendor",
        vendor_version="vv_old",
        source_version="sv_old",
    )
    repo = task_mod.YieldCurveRepository(str(duckdb_path))
    with task_mod.repository_task_write_scope(task_mod.__name__):
        repo.replace_curve_snapshots(
            trade_date=stale_snapshot.trade_date,
            snapshots=[stale_snapshot],
            rule_version=task_mod.RULE_VERSION,
        )

    requested_dates: list[str] = []

    def fetch_curve(self, *, curve_type: str, trade_date: str):
        requested_dates.append(f"{curve_type}:{trade_date}")
        if trade_date != "2026-05-29":
            raise RuntimeError("market closed")
        return schema_mod.YieldCurveSnapshot(
            curve_type=curve_type,
            trade_date=trade_date,
            points=[
                schema_mod.YieldCurvePoint("6M", Decimal("1.00")),
                schema_mod.YieldCurvePoint("1Y", Decimal("1.10")),
            ],
            vendor_name="fresh_vendor",
            vendor_version="vv_fresh",
            source_version="sv_fresh",
        )

    monkeypatch.setattr(task_mod.VendorAdapter, "fetch_yield_curve", fetch_curve)

    payload = task_mod.backfill_yield_curve_month_ends(
        duckdb_path=str(duckdb_path),
        start_date="2026-05-01",
        end_date="2026-05-31",
        curve_types=("treasury",),
        max_backtrack_days=20,
    )

    assert payload["written"] == 1
    assert payload["skipped"] == 0
    assert requested_dates == [
        "treasury:2026-05-31",
        "treasury:2026-05-30",
        "treasury:2026-05-29",
    ]

    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select distinct trade_date, curve_type, source_version
            from fact_formal_yield_curve_daily
            order by trade_date, curve_type
            """
        ).fetchall()
    finally:
        conn.close()

    assert rows == [
        ("2026-05-15", "treasury", "sv_old"),
        ("2026-05-29", "treasury", "sv_fresh"),
    ]


def test_ensure_yield_curve_inputs_rejects_stale_existing_snapshot_outside_backtrack(
    tmp_path,
    monkeypatch,
):
    task_mod = _load_yield_curve_task_module()
    schema_mod = load_module(
        "backend.app.schemas.yield_curve",
        "backend/app/schemas/yield_curve.py",
    )

    duckdb_path = tmp_path / "moss.duckdb"
    stale_snapshot = schema_mod.YieldCurveSnapshot(
        curve_type="treasury",
        trade_date="2026-05-01",
        points=[
            schema_mod.YieldCurvePoint("6M", Decimal("0.90")),
            schema_mod.YieldCurvePoint("1Y", Decimal("1.00")),
        ],
        vendor_name="old_vendor",
        vendor_version="vv_old",
        source_version="sv_old",
    )
    repo = task_mod.YieldCurveRepository(str(duckdb_path))
    with task_mod.repository_task_write_scope(task_mod.__name__):
        repo.replace_curve_snapshots(
            trade_date=stale_snapshot.trade_date,
            snapshots=[stale_snapshot],
            rule_version=task_mod.RULE_VERSION,
        )

    requested_dates: list[str] = []

    def fetch_curve(self, *, curve_type: str, trade_date: str):
        requested_dates.append(f"{curve_type}:{trade_date}")
        raise RuntimeError("vendor down")

    monkeypatch.setattr(task_mod.VendorAdapter, "fetch_yield_curve", fetch_curve)

    with pytest.raises(RuntimeError, match="vendor down"):
        task_mod.ensure_yield_curve_inputs_on_or_before(
            anchor_dates=("2026-05-31",),
            duckdb_path=str(duckdb_path),
            curve_types=("treasury",),
            max_backtrack_days=3,
        )

    assert requested_dates == [
        "treasury:2026-05-31",
        "treasury:2026-05-30",
        "treasury:2026-05-29",
        "treasury:2026-05-28",
    ]


def test_execute_yield_curve_month_end_backfill_summarizes_resolved_dates_outside_input_range(
    tmp_path,
    monkeypatch,
):
    task_mod = _load_yield_curve_task_module()
    schema_mod = load_module(
        "backend.app.schemas.yield_curve",
        "backend/app/schemas/yield_curve.py",
    )

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path))
    try:
        conn.execute("create table zqtz_bond_daily_snapshot (report_date varchar)")
        conn.execute("insert into zqtz_bond_daily_snapshot values ('2026-05-31')")
    finally:
        conn.close()

    def fetch_curve(self, *, curve_type: str, trade_date: str):
        if trade_date != "2026-04-30":
            raise RuntimeError("market closed")
        return schema_mod.YieldCurveSnapshot(
            curve_type=curve_type,
            trade_date=trade_date,
            points=[
                schema_mod.YieldCurvePoint("6M", Decimal("1.00")),
                schema_mod.YieldCurvePoint("1Y", Decimal("1.10")),
            ],
            vendor_name="fallback_vendor",
            vendor_version="vv_fallback",
            source_version="sv_fallback",
        )

    monkeypatch.setattr(task_mod.VendorAdapter, "fetch_yield_curve", fetch_curve)

    result = task_mod._execute_yield_curve_month_end_backfill(
        duckdb_path=str(duckdb_path),
        start_date="2026-05-31",
        end_date="2026-05-31",
        curve_types=("treasury",),
        max_backtrack_days=31,
    )

    assert result.source_version == "sv_fallback"
    assert result.vendor_version == "vv_fallback"
    assert result.payload["resolved_trade_dates"] == ["2026-04-30"]


def test_execute_yield_curve_month_end_backfill_summarizes_exact_resolved_curve_pairs(tmp_path, monkeypatch):
    task_mod = _load_yield_curve_task_module()
    schema_mod = load_module(
        "backend.app.schemas.yield_curve",
        "backend/app/schemas/yield_curve.py",
    )

    duckdb_path = tmp_path / "moss.duckdb"
    conn = duckdb.connect(str(duckdb_path))
    try:
        conn.execute("create table zqtz_bond_daily_snapshot (report_date varchar)")
        conn.execute("insert into zqtz_bond_daily_snapshot values ('2026-05-31')")
    finally:
        conn.close()

    stale_cdb = schema_mod.YieldCurveSnapshot(
        curve_type="cdb",
        trade_date="2026-05-29",
        points=[
            schema_mod.YieldCurvePoint("6M", Decimal("1.20")),
            schema_mod.YieldCurvePoint("1Y", Decimal("1.30")),
        ],
        vendor_name="stale_cdb_vendor",
        vendor_version="vv_cdb_stale",
        source_version="sv_cdb_stale",
    )
    repo = task_mod.YieldCurveRepository(str(duckdb_path))
    with task_mod.repository_task_write_scope(task_mod.__name__):
        repo.replace_curve_snapshots(
            trade_date=stale_cdb.trade_date,
            snapshots=[stale_cdb],
            rule_version=task_mod.RULE_VERSION,
        )

    def fetch_curve(self, *, curve_type: str, trade_date: str):
        if curve_type == "treasury" and trade_date == "2026-05-29":
            return schema_mod.YieldCurveSnapshot(
                curve_type=curve_type,
                trade_date=trade_date,
                points=[
                    schema_mod.YieldCurvePoint("6M", Decimal("1.00")),
                    schema_mod.YieldCurvePoint("1Y", Decimal("1.10")),
                ],
                vendor_name="treasury_vendor",
                vendor_version="vv_treasury_resolved",
                source_version="sv_treasury_resolved",
            )
        if curve_type == "cdb" and trade_date == "2026-05-28":
            return schema_mod.YieldCurveSnapshot(
                curve_type=curve_type,
                trade_date=trade_date,
                points=[
                    schema_mod.YieldCurvePoint("6M", Decimal("1.40")),
                    schema_mod.YieldCurvePoint("1Y", Decimal("1.50")),
                ],
                vendor_name="cdb_vendor",
                vendor_version="vv_cdb_resolved",
                source_version="sv_cdb_resolved",
            )
        raise RuntimeError("market closed")

    monkeypatch.setattr(task_mod.VendorAdapter, "fetch_yield_curve", fetch_curve)

    result = task_mod._execute_yield_curve_month_end_backfill(
        duckdb_path=str(duckdb_path),
        start_date="2026-05-31",
        end_date="2026-05-31",
        curve_types=("treasury", "cdb"),
        max_backtrack_days=3,
    )

    assert result.source_version == "sv_cdb_resolved__sv_treasury_resolved"
    assert result.vendor_version == "vv_cdb_resolved__vv_treasury_resolved"
    assert result.payload["resolved_snapshots"] == [
        {"anchor_date": "2026-05-31", "curve_type": "cdb", "trade_date": "2026-05-28"},
        {"anchor_date": "2026-05-31", "curve_type": "treasury", "trade_date": "2026-05-29"},
    ]


def test_materialize_yield_curve_month_end_backfill_records_governance(tmp_path, monkeypatch):
    task_mod = _load_yield_curve_task_module()
    schema_mod = load_module(
        "backend.app.schemas.yield_curve",
        "backend/app/schemas/yield_curve.py",
    )

    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    conn = duckdb.connect(str(duckdb_path))
    try:
        conn.execute("create table zqtz_bond_daily_snapshot (report_date varchar)")
        conn.execute("insert into zqtz_bond_daily_snapshot values ('2026-05-31')")
    finally:
        conn.close()

    def fetch_curve(self, *, curve_type: str, trade_date: str):
        if trade_date != "2026-05-29":
            raise RuntimeError("market closed")
        return schema_mod.YieldCurveSnapshot(
            curve_type=curve_type,
            trade_date=trade_date,
            points=[
                schema_mod.YieldCurvePoint("6M", Decimal("1.00")),
                schema_mod.YieldCurvePoint("1Y", Decimal("1.10")),
                schema_mod.YieldCurvePoint("3Y", Decimal("1.30")),
                schema_mod.YieldCurvePoint("5Y", Decimal("1.50")),
                schema_mod.YieldCurvePoint("10Y", Decimal("1.80")),
                schema_mod.YieldCurvePoint("30Y", Decimal("2.40")),
            ],
            vendor_name="test_vendor",
            vendor_version=f"vv_{curve_type}",
            source_version=f"sv_{curve_type}",
        )

    monkeypatch.setattr(task_mod.VendorAdapter, "fetch_yield_curve", fetch_curve)

    payload = task_mod.materialize_yield_curve_month_end_backfill.fn(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
        start_date="2026-05-01",
        end_date="2026-05-31",
        curve_types=["treasury"],
        max_backtrack_days=2,
        run_id="yield-backfill-test",
    )

    assert payload["status"] == "completed"
    assert payload["report_date"] == "2026-05-31"
    assert payload["written"] == 1
    assert payload["month_end_dates"] == ["2026-05-31"]

    build_runs = _read_jsonl(governance_dir / "cache_build_run.jsonl")
    manifests = _read_jsonl(governance_dir / "cache_manifest.jsonl")
    assert [record["status"] for record in build_runs] == ["queued", "running", "completed"]
    assert build_runs[-1]["run_id"] == "yield-backfill-test"
    assert build_runs[-1]["report_date"] == "2026-05-31"
    assert manifests[0]["run_id"] == "yield-backfill-test"
    assert manifests[0]["report_date"] == "2026-05-31"
