from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import time
from datetime import date
from decimal import Decimal
import uuid

from backend.app.governance.settings import get_settings
from tests.helpers import load_module
from tests.test_bond_analytics_curve_effects import _seed_curve_rows
from tests.test_bond_analytics_materialize_flow import REPORT_DATE, _seed_bond_snapshot_rows


def test_compute_bond_spreads_basic():
    module = load_module(
        f"tests._credit_spread_analysis.core_{uuid.uuid4().hex}",
        "backend/app/core_finance/credit_spread_analysis.py",
    )

    rows = module.compute_bond_spreads(
        bond_rows=[
            {
                "instrument_code": "CB-001",
                "instrument_name": "企业债1号",
                "asset_class_std": "credit",
                "rating": "AAA",
                "tenor_bucket": "3Y",
                "ytm": Decimal("0.035"),
                "modified_duration": Decimal("2.5"),
                "market_value": Decimal("100"),
            },
            {
                "instrument_code": "TB-001",
                "instrument_name": "国债1号",
                "asset_class_std": "rate",
                "rating": "AAA",
                "tenor_bucket": "3Y",
                "ytm": Decimal("0.020"),
                "modified_duration": Decimal("2.0"),
                "market_value": Decimal("200"),
            },
        ],
        treasury_curve={
            "1Y": Decimal("2.00"),
            "5Y": Decimal("3.00"),
        },
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.instrument_code == "CB-001"
    assert row.ytm == Decimal("3.50")
    assert row.benchmark_yield == Decimal("2.50")
    assert row.credit_spread == Decimal("100.00")
    assert row.spread_duration == Decimal("2.5")
    assert row.spread_dv01 == Decimal("0.025")
    assert row.weight == Decimal("1")


def test_spread_term_structure_aggregation():
    module = load_module(
        f"tests._credit_spread_analysis.core_{uuid.uuid4().hex}",
        "backend/app/core_finance/credit_spread_analysis.py",
    )

    rows = [
        module.BondSpreadRow(
            instrument_code="CB-001",
            instrument_name="企业债1号",
            rating="AAA",
            tenor_bucket="3Y",
            ytm=Decimal("3.50"),
            benchmark_yield=Decimal("2.50"),
            credit_spread=Decimal("100"),
            spread_duration=Decimal("2.5"),
            spread_dv01=Decimal("0.025"),
            market_value=Decimal("100"),
            weight=Decimal("0.25"),
        ),
        module.BondSpreadRow(
            instrument_code="CB-002",
            instrument_name="公司债2号",
            rating="AA+",
            tenor_bucket="3Y",
            ytm=Decimal("4.20"),
            benchmark_yield=Decimal("2.50"),
            credit_spread=Decimal("170"),
            spread_duration=Decimal("2.7"),
            spread_dv01=Decimal("0.054"),
            market_value=Decimal("200"),
            weight=Decimal("0.50"),
        ),
        module.BondSpreadRow(
            instrument_code="CB-003",
            instrument_name="中票3号",
            rating="AAA",
            tenor_bucket="5Y",
            ytm=Decimal("4.00"),
            benchmark_yield=Decimal("3.00"),
            credit_spread=Decimal("100"),
            spread_duration=Decimal("4.0"),
            spread_dv01=Decimal("0.040"),
            market_value=Decimal("100"),
            weight=Decimal("0.25"),
        ),
    ]

    points = module.build_spread_term_structure(rows)

    assert [point.tenor_bucket for point in points] == ["3Y", "5Y"]
    assert points[0].avg_spread_bps == Decimal("146.66666667")
    assert points[0].min_spread_bps == Decimal("100")
    assert points[0].max_spread_bps == Decimal("170")
    assert points[0].bond_count == 2
    assert points[0].total_market_value == Decimal("300")
    assert points[1].avg_spread_bps == Decimal("100")


def test_historical_percentile_calculation():
    module = load_module(
        f"tests._credit_spread_analysis.core_{uuid.uuid4().hex}",
        "backend/app/core_finance/credit_spread_analysis.py",
    )

    context = module.compute_spread_historical_context(
        current_avg_spread=Decimal("120"),
        historical_spreads=[
            (date(2026, 3, 31), Decimal("120")),
            (date(2026, 2, 28), Decimal("100")),
            (date(2025, 12, 31), Decimal("130")),
            (date(2024, 6, 30), Decimal("90")),
            (date(2022, 12, 31), Decimal("80")),
        ],
    )

    assert context.current_spread_bps == Decimal("120")
    assert context.percentile_1y == Decimal("66.66666667")
    assert context.percentile_3y == Decimal("75.00000000")
    assert context.median_1y == Decimal("120")
    assert context.median_3y == Decimal("110")
    assert context.min_1y == Decimal("100")
    assert context.max_1y == Decimal("130")


def test_api_returns_real_data(tmp_path, monkeypatch):
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_dir))
    get_settings.cache_clear()

    _seed_bond_snapshot_rows(str(duckdb_path))
    _seed_curve_rows(str(duckdb_path))

    task_mod = load_module(
        f"tests._credit_spread_analysis.task_{uuid.uuid4().hex}",
        "backend/app/tasks/bond_analytics_materialize.py",
    )
    task_mod.materialize_bond_analytics_facts.fn(
        report_date=REPORT_DATE,
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_dir),
    )
    completed = None
    for attempt in range(5):
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                textwrap.dedent(
                    f"""
                    import json
                    from fastapi.testclient import TestClient
                    from tests.helpers import load_module

                    app = load_module(
                        "tests._credit_spread_analysis.main_subprocess",
                        "backend/app/main.py",
                    ).app
                    response = TestClient(app).get(
                        "/api/credit-spread-analysis/detail",
                        params={{"report_date": "{REPORT_DATE}"}},
                    )
                    print(json.dumps({{"status_code": response.status_code, "payload": response.json()}}, ensure_ascii=False))
                    """
                ),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            env={
                **os.environ,
                "MOSS_DUCKDB_PATH": str(duckdb_path),
                "MOSS_GOVERNANCE_PATH": str(governance_dir),
            },
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        if completed.returncode == 0:
            break
        time.sleep(0.05 * (attempt + 1))
    assert completed is not None
    assert completed.returncode == 0, completed.stderr
    response_payload = json.loads(completed.stdout.strip())
    assert response_payload["status_code"] == 200
    payload = response_payload["payload"]
    assert payload["result_meta"]["basis"] == "formal"
    assert payload["result_meta"]["result_kind"] == "credit_spread_analysis.detail"
    assert payload["result_meta"]["formal_use_allowed"] is True
    assert "sv_bond_snap_1" in payload["result_meta"]["source_version"]
    assert "sv_curve_current" in payload["result_meta"]["source_version"]
    assert payload["result_meta"]["vendor_status"] == "ok"
    assert payload["result_meta"]["fallback_mode"] == "none"

    result = payload["result"]
    assert result["report_date"] == REPORT_DATE
    assert result["credit_bond_count"] == 2
    assert result["total_credit_market_value"] == "330.00000000"
    assert result["weighted_avg_spread_bps"] == "-24.84848485"
    assert [row["instrument_code"] for row in result["top_spread_bonds"]] == ["CB-002", "CB-001"]
    assert [row["instrument_code"] for row in result["bottom_spread_bonds"]] == ["CB-001", "CB-002"]
    assert [row["tenor_bucket"] for row in result["spread_term_structure"]] == ["5Y", "10Y"]
    assert result["historical_context"]["percentile_1y"] == "100.00000000"
    assert result["warnings"] == []

    get_settings.cache_clear()
