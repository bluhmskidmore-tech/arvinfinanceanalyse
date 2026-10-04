from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import time
import uuid
from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from tests.helpers import load_module
from tests.test_bond_analytics_curve_effects import _seed_curve_rows
from tests.test_bond_analytics_materialize_flow import (
    REPORT_DATE,
    _seed_bond_snapshot_rows,
)

CREDIT_SPREAD_READ_HEADERS = {"X-User-Id": "credit-spread-read-user", "X-User-Role": "viewer"}


def _credit_spread_scope_repo(tmp_path: Path, monkeypatch) -> UserScopeRepository:
    sqlite_path = tmp_path / "credit-spread-read-scope.db"
    dsn = f"sqlite:///{sqlite_path.as_posix()}"
    monkeypatch.setenv("MOSS_POSTGRES_DSN", dsn)
    monkeypatch.setenv("MOSS_GOVERNANCE_SQL_DSN", "")
    monkeypatch.setenv(ROLE_HEADER_TRUST_ENV, "1")
    get_settings.cache_clear()
    return UserScopeRepository(dsn)


def _grant_credit_spread_read(tmp_path: Path, monkeypatch) -> None:
    _credit_spread_scope_repo(tmp_path, monkeypatch).grant_scope(
        user_id="*",
        role=None,
        resource="credit_spread_analysis",
        action="read",
    )


def test_credit_spread_detail_requires_explicit_read_scope(tmp_path, monkeypatch):
    route_module = load_module(
        "backend.app.api.routes.credit_spread_analysis",
        "backend/app/api/routes/credit_spread_analysis.py",
    )
    monkeypatch.setattr(
        route_module,
        "get_credit_spread_analysis",
        lambda _report_date: {"result_meta": {"result_kind": "credit_spread_analysis.detail"}, "result": {}},
    )
    _credit_spread_scope_repo(tmp_path, monkeypatch)
    app = FastAPI()
    app.include_router(route_module.router)
    client = TestClient(app)

    response = client.get(
        "/api/credit-spread-analysis/detail",
        params={"report_date": REPORT_DATE},
        headers=CREDIT_SPREAD_READ_HEADERS,
    )

    assert response.status_code == 403


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


def test_compute_bond_spreads_interpolates_benchmark_at_actual_remaining_maturity():
    module = load_module(
        f"tests._credit_spread_analysis.actual_maturity_{uuid.uuid4().hex}",
        "backend/app/core_finance/credit_spread_analysis.py",
    )

    rows = module.compute_bond_spreads(
        bond_rows=[
            {
                "instrument_code": "CB-4Y",
                "instrument_name": "4Y credit bond",
                "asset_class_std": "credit",
                "rating": "AAA",
                "tenor_bucket": "3Y",
                "years_to_maturity": Decimal("4"),
                "ytm": Decimal("0.035"),
                "modified_duration": Decimal("3.5"),
                "market_value": Decimal("100"),
            },
        ],
        treasury_curve={
            "3Y": Decimal("2.00"),
            "5Y": Decimal("3.00"),
        },
    )

    row = rows[0]
    assert row.benchmark_yield == Decimal("2.50")
    assert row.credit_spread == Decimal("100.00")


def test_compute_bond_spreads_uses_face_value_for_spread_dv01():
    module = load_module(
        f"tests._credit_spread_analysis.core_{uuid.uuid4().hex}",
        "backend/app/core_finance/credit_spread_analysis.py",
    )

    rows = module.compute_bond_spreads(
        bond_rows=[
            {
                "instrument_code": "CB-FACE",
                "instrument_name": "credit bond",
                "asset_class_std": "credit",
                "rating": "AAA",
                "tenor_bucket": "3Y",
                "ytm": Decimal("0.035"),
                "modified_duration": Decimal("2.5"),
                "market_value": Decimal("100"),
                "face_value": Decimal("1000"),
            },
        ],
        treasury_curve={
            "1Y": Decimal("2.00"),
            "5Y": Decimal("3.00"),
        },
    )

    row = rows[0]
    assert row.spread_dv01 == Decimal("0.25")
    assert row.spread_dv01 != Decimal("0.025")


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
    _grant_credit_spread_read(tmp_path, monkeypatch)

    _seed_bond_snapshot_rows(str(duckdb_path))
    _seed_curve_rows(str(duckdb_path))

    task_mod = load_module(
        "backend.app.tasks.bond_analytics_materialize",
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
                    client = TestClient(app)
                    client.headers.update({CREDIT_SPREAD_READ_HEADERS!r})
                    response = client.get(
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
                "MOSS_POSTGRES_DSN": os.environ["MOSS_POSTGRES_DSN"],
                "MOSS_GOVERNANCE_SQL_DSN": os.environ.get("MOSS_GOVERNANCE_SQL_DSN", ""),
                ROLE_HEADER_TRUST_ENV: os.environ[ROLE_HEADER_TRUST_ENV],
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
    # 只有 1 个历史观测：分位数照常出数，但服务层按 60 观测阈值追加样本不足告警。
    assert result["warnings"] == [
        "SPREAD_HISTORY_OBSERVATIONS_LT_60:1y=1",
        "SPREAD_HISTORY_OBSERVATIONS_LT_60:3y=1",
    ]

    get_settings.cache_clear()


def _service_with_fake_repos(monkeypatch, *, curve: dict[str, Decimal], credit_rows: list[dict]):
    service = load_module(
        f"tests._credit_spread_analysis.service_{uuid.uuid4().hex}",
        "backend/app/services/credit_spread_analysis_service.py",
    )

    class _FakeBondRepo:
        def __init__(self, _path: str) -> None:
            pass

        def fetch_bond_analytics_rows(self, *, report_date: str, asset_class: str | None = None):
            return list(credit_rows)

        def list_report_dates(self):
            return []

    class _FakeCurveRepo:
        def __init__(self, _path: str) -> None:
            pass

    snapshot = {
        "curve": curve,
        "source_version": "sv_curve_fake",
        "rule_version": "rv_curve_fake",
        "vendor_version": "vv_fake",
    }
    monkeypatch.setattr(service, "BondAnalyticsRepository", _FakeBondRepo)
    monkeypatch.setattr(service, "YieldCurveRepository", _FakeCurveRepo)
    monkeypatch.setattr(service, "get_settings", lambda: type("S", (), {"duckdb_path": "unused"})())
    monkeypatch.setattr(
        service,
        "resolve_curve_snapshot",
        lambda _repo, *, requested_trade_date, curve_type: (snapshot, None),
    )
    return service


_CREDIT_ROW = {
    "instrument_code": "CB-001",
    "instrument_name": "信用债A",
    "rating": "AAA",
    "asset_class_std": "credit",
    "tenor_bucket": "3Y",
    "ytm": Decimal("0.0312"),
    "years_to_maturity": None,
    "market_value": Decimal("1000000"),
    "face_value": Decimal("1000000"),
    "modified_duration": Decimal("2.5"),
    "source_version": "sv_bond_fake",
    "rule_version": "rv_bond_fake",
}


@pytest.mark.parametrize(
    "curve",
    [{"8Y": Decimal("3.0")}, {"3Y": None}, {"3Y": Decimal("NaN")}, {"3Y": Decimal("Infinity")}, {"3Y": "bad"}],
)
def test_service_marks_curve_without_usable_tenors_as_vendor_unavailable(monkeypatch, curve):
    """快照节点的期限或收益率不可用时，必须标为曲线不可用。"""
    service = _service_with_fake_repos(
        monkeypatch,
        curve=curve,
        credit_rows=[_CREDIT_ROW],
    )

    envelope = service.get_credit_spread_analysis(date(2026, 3, 31))

    assert envelope["result_meta"]["vendor_status"] == "vendor_unavailable"
    assert envelope["result_meta"]["cache_version"] == "cv_credit_spread_analysis_formal_v3"
    assert "rv_credit_spread_analysis_formal_v3" in envelope["result_meta"]["rule_version"]
    assert envelope["result_meta"]["fallback_mode"] == "none"
    assert envelope["result"]["credit_bond_count"] == 1
    assert Decimal(envelope["result"]["total_credit_market_value"]) == Decimal("1000000")
    assert envelope["result"]["spread_bond_count"] == 0
    assert envelope["result"]["weighted_avg_spread_bps"] is None
    assert service.CURVE_NO_USABLE_TENORS_WARNING in envelope["result"]["warnings"]
    assert service.EMPTY_WARNING not in envelope["result"]["warnings"]


def test_service_keeps_vendor_ok_when_curve_has_usable_tenors(monkeypatch):
    """对照：同一持仓换成可用曲线时正常出数，只保留历史样本不足告警。"""
    service = _service_with_fake_repos(
        monkeypatch,
        curve={"1Y": Decimal("2.0"), "5Y": Decimal("3.0")},
        credit_rows=[_CREDIT_ROW],
    )

    envelope = service.get_credit_spread_analysis(date(2026, 3, 31))

    assert envelope["result_meta"]["vendor_status"] == "ok"
    assert envelope["result_meta"]["cache_version"] == "cv_credit_spread_analysis_formal_v3"
    assert "rv_credit_spread_analysis_formal_v3" in envelope["result_meta"]["rule_version"]
    assert envelope["result"]["credit_bond_count"] == 1
    assert service.CURVE_NO_USABLE_TENORS_WARNING not in envelope["result"]["warnings"]
    assert envelope["result"]["warnings"] == [
        "SPREAD_HISTORY_OBSERVATIONS_LT_60:1y=0",
        "SPREAD_HISTORY_OBSERVATIONS_LT_60:3y=0",
    ]


@pytest.mark.parametrize("ytm_value", [None, "bad", Decimal("NaN"), Decimal("Infinity")])
def test_missing_ytm_keeps_credit_holdings_and_nulls_current_spread_with_full_history(monkeypatch, ytm_value):
    from backend.app.core_finance.bond_analytics.engine import compute_bond_analytics_rows

    report_date = date(2026, 3, 31)
    credit_row = asdict(compute_bond_analytics_rows([{
        "instrument_code": "YTM-MISSING-001",
        "asset_class": "债券资产",
        "bond_type": "企业债",
        "currency_code": "CNY",
        "accounting_basis": "FVOCI",
        "face_value_native": Decimal("100000000"),
        "market_value_native": Decimal("100000000"),
        "coupon_rate": Decimal("3"),
        "ytm_value": ytm_value,
        "maturity_date": date(2031, 3, 31),
        "interest_mode": "annual",
    }], report_date)[0])
    service = _service_with_fake_repos(
        monkeypatch, curve={"5Y": Decimal("2.5")}, credit_rows=[credit_row],
    )
    monkeypatch.setattr(service, "_build_historical_spreads", lambda **_: [
        (report_date - timedelta(days=index + 1), Decimal("50")) for index in range(60)
    ])

    envelope = service.get_credit_spread_analysis(report_date)
    result = envelope["result"]
    assert result["credit_bond_count"] == 1
    assert Decimal(result["total_credit_market_value"]) == Decimal("100000000")
    assert result["spread_bond_count"] == 0
    assert Decimal(result["spread_market_value"]) == 0
    assert result["missing_ytm_count"] == 1
    assert Decimal(result["missing_ytm_market_value"]) == Decimal("100000000")
    assert result["spread_coverage_status"] == "unavailable"
    assert result["weighted_avg_spread_bps"] is None
    assert result["historical_context"]["current_spread_bps"] is None
    assert result["historical_context"]["percentile_1y"] is None
    assert result["historical_context"]["percentile_3y"] is None
    assert result["historical_context"]["median_1y"] == "50"
    assert envelope["result_meta"]["quality_flag"] == "warning"
    assert envelope["result_meta"]["formal_use_allowed"] is False
    assert any("YTM" in warning for warning in result["warnings"])
    assert not any(warning.startswith("SPREAD_HISTORY_OBSERVATIONS_LT_") for warning in result["warnings"])


def test_partial_ytm_coverage_discloses_holdings_and_keeps_observed_zero(monkeypatch):
    service = _service_with_fake_repos(
        monkeypatch,
        curve={"3Y": Decimal("0")},
        credit_rows=[
            {**_CREDIT_ROW, "ytm": Decimal("0"), "market_value": Decimal("1000000")},
            {**_CREDIT_ROW, "instrument_code": "YTM-MISSING", "ytm": None, "market_value": Decimal("3000000")},
        ],
    )
    result = service.get_credit_spread_analysis(date(2026, 3, 31))["result"]
    assert result["credit_bond_count"] == 2
    assert Decimal(result["total_credit_market_value"]) == Decimal("4000000")
    assert result["spread_bond_count"] == 1
    assert Decimal(result["spread_market_value"]) == Decimal("1000000")
    assert result["missing_ytm_count"] == 1
    assert Decimal(result["missing_ytm_market_value"]) == Decimal("3000000")
    assert result["spread_coverage_status"] == "partial"
    assert Decimal(result["weighted_avg_spread_bps"]) == 0
    assert Decimal(result["top_spread_bonds"][0]["ytm"]) == 0
    assert any("YTM" in warning for warning in result["warnings"])


def test_empty_credit_holdings_do_not_publish_observed_zero_spread(monkeypatch):
    service = _service_with_fake_repos(monkeypatch, curve={"3Y": Decimal("2")}, credit_rows=[])
    result = service.get_credit_spread_analysis(date(2026, 3, 31))["result"]
    assert result["credit_bond_count"] == 0
    assert Decimal(result["total_credit_market_value"]) == 0
    assert result["weighted_avg_spread_bps"] is None
    assert result["spread_coverage_status"] == "empty"


def test_observed_zero_ytm_and_spread_keep_complete_coverage_and_history_percentile(monkeypatch):
    report_date = date(2026, 3, 31)
    service = _service_with_fake_repos(
        monkeypatch, curve={"3Y": Decimal("0")}, credit_rows=[{**_CREDIT_ROW, "ytm": Decimal("0")}],
    )
    monkeypatch.setattr(service, "_build_historical_spreads", lambda **_: [
        (report_date - timedelta(days=index + 1), Decimal("0")) for index in range(60)
    ])
    envelope = service.get_credit_spread_analysis(report_date)
    result = envelope["result"]
    assert result["spread_bond_count"] == result["credit_bond_count"] == 1
    assert result["spread_coverage_status"] == "complete"
    assert result["missing_ytm_count"] == 0
    assert Decimal(result["weighted_avg_spread_bps"]) == 0
    assert Decimal(result["historical_context"]["percentile_1y"]) == 100
    assert result["warnings"] == []
    assert envelope["result_meta"]["formal_use_allowed"] is True
    assert envelope["result_meta"]["quality_flag"] == "ok"
