"""Same-date balance update acceptance with isolated formal finance persistence."""

from __future__ import annotations

import os
import time
from decimal import Decimal

import duckdb
import pytest
from fastapi.testclient import TestClient

from backend.app.governance.settings import get_settings
from backend.app.repositories.user_scope_repo import UserScopeRepository
from backend.app.security.auth_context import ROLE_HEADER_TRUST_ENV
from backend.app.services import data_update_service
from backend.app.tasks import balance_analysis_materialize, data_update_center
from backend.app.tasks import formal_balance_pipeline
from tests.test_balance_analysis_materialize_flow import _seed_snapshot_and_fx_tables


pytestmark = [pytest.mark.integration, pytest.mark.materialize]

REPORT_DATE = "2025-12-31"


def test_balance_daily_request_materializes_same_date_and_serves_amounts(
    tmp_path, monkeypatch, request
):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    duckdb_path = tmp_path / "moss.duckdb"
    governance_dir = tmp_path / "governance"
    archive_dir = tmp_path / "archive"
    scope_dsn = f"sqlite:///{(tmp_path / 'scopes.db').as_posix()}"
    for key, value in {
        "MOSS_ENVIRONMENT": "development",
        "MOSS_GOVERNANCE_BACKEND": "jsonl",
        "MOSS_DUCKDB_PATH": str(duckdb_path),
        "MOSS_GOVERNANCE_PATH": str(governance_dir),
        "MOSS_DATA_INPUT_ROOT": str(input_dir),
        "MOSS_LOCAL_ARCHIVE_PATH": str(archive_dir),
        "MOSS_POSTGRES_DSN": scope_dsn,
        "MOSS_GOVERNANCE_SQL_DSN": "",
        "MOSS_FX_OFFICIAL_SOURCE_PATH": "",
        "MOSS_FX_MID_CSV_PATH": "",
        "MOSS_AUTH_SCOPE_CACHE_TTL_SECONDS": "0",
        ROLE_HEADER_TRUST_ENV: "1",
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    request.addfinalizer(get_settings.cache_clear)
    settings = get_settings()

    # The source boundary is preloaded with two synthetic USD positions and a
    # 7.2 CNY/USD fixing. Formal balance, bond and risk materializers stay real.
    _seed_snapshot_and_fx_tables(str(duckdb_path))
    with duckdb.connect(str(duckdb_path), read_only=True) as conn:
        # Schema migration may create the fact tables, but no D facts exist yet.
        before_tables = {row[0] for row in conn.execute("show tables").fetchall()}
        for table in (
            "fact_formal_zqtz_balance_daily",
            "fact_formal_tyw_balance_daily",
            "fact_formal_bond_analytics_daily",
            "fact_formal_risk_tensor_daily",
        ):
            if table in before_tables:
                assert conn.execute(
                    f'SELECT COUNT(*) FROM "{table}" WHERE report_date = ?', [REPORT_DATE]
                ).fetchone()[0] == 0
        assert conn.execute(
            "select market_value_native from zqtz_bond_daily_snapshot where report_date = ?",
            [REPORT_DATE],
        ).fetchone()[0] == Decimal("100")
        assert conn.execute(
            "select principal_native from tyw_interbank_daily_snapshot where report_date = ?",
            [REPORT_DATE],
        ).fetchone()[0] == Decimal("10")
        assert conn.execute(
            "select mid_rate from fx_daily_mid where trade_date = ?",
            [REPORT_DATE],
        ).fetchone()[0] == Decimal("7.2")

    for name in ("ZQTZSHOW-20251231.xls", "TYWLSHOW-20251231.xls"):
        source_path = input_dir / name
        source_path.write_bytes(b"synthetic source boundary; snapshots are preloaded")
        settled = time.time() - 120
        os.utime(source_path, (settled, settled))

    scopes = UserScopeRepository(scope_dsn)
    for resource, action in (
        ("balance_analysis", "read"),
        ("balance_analysis", "refresh"),
        ("bond_analytics", "refresh"),
        ("data_health", "read"),
    ):
        scopes.grant_scope(
            user_id="daily-operator", role=None, resource=resource, action=action
        )

    # Only external file/scheduler boundaries are replaced. The real pipeline
    # still calls formal balance, bond analytics and risk materialization.
    source_calls: list[tuple[str, str | None]] = []

    def supplied_source(**kwargs):
        source_calls.append(("ingest", kwargs.get("data_root")))
        return {"status": "completed", "source_families": ["zqtz", "tyw"]}

    def supplied_snapshot(**kwargs):
        source_calls.append(("snapshot", kwargs.get("report_date")))
        return {"status": "completed", "report_date": kwargs["report_date"]}

    monkeypatch.setattr(data_update_service, "require_scheduler", lambda _task: None)
    monkeypatch.setattr(
        data_update_service,
        "scheduled_updates",
        lambda: {"status": "available", "tasks": []},
    )
    monkeypatch.setattr(formal_balance_pipeline.ingest_demo_manifest, "fn", supplied_source)
    monkeypatch.setattr(
        formal_balance_pipeline.materialize_standard_snapshots, "fn", supplied_snapshot
    )
    monkeypatch.setattr(
        balance_analysis_materialize.materialize_fx_mid_for_report_date,
        "fn",
        lambda **_kwargs: {"status": "completed", "row_count": 0},
    )

    from backend.app.main import app

    headers = {
        "X-User-Id": "daily-operator",
        "X-User-Role": "operator",
        "Idempotency-Key": "synthetic-daily-20251231",
    }
    try:
        client = TestClient(app)
        before_dates = client.get("/ui/balance-analysis/dates", headers=headers)
        # PAGE-BALANCE-001 fails closed until formal build lineage is present.
        assert before_dates.status_code == 503, before_dates.text
        assert "Canonical formal lineage unavailable" in before_dates.json()["detail"]

        submitted = client.post(
            "/api/data-updates/core",
            json={
                "report_date": REPORT_DATE,
                "workflow": "balance_daily",
                "wait_for_inputs": False,
            },
            headers=headers,
        )
        assert submitted.status_code == 202, submitted.text
        assert submitted.json()["status"] == "queued"
        run_id = submitted.json()["run_id"]

        assert data_update_center.drain_updates(settings) == 0
        assert source_calls == [("ingest", str(input_dir)), ("snapshot", REPORT_DATE)]

        update_response = client.get("/api/data-updates", headers=headers)
        assert update_response.status_code == 200, update_response.text
        receipt = next(
            row for row in update_response.json()["runs"] if row["run_id"] == run_id
        )
        assert receipt["status"] == "completed"
        assert receipt["report_date"] == REPORT_DATE
        assert [step["status"] for step in receipt["steps"]] == [
            "completed", "completed"
        ]

        with duckdb.connect(str(duckdb_path), read_only=True) as conn:
            assert conn.execute(
                "select count(*) from fact_formal_zqtz_balance_daily where report_date = ?",
                [REPORT_DATE],
            ).fetchone()[0] > 0
            assert conn.execute(
                "select count(*) from fact_formal_tyw_balance_daily where report_date = ?",
                [REPORT_DATE],
            ).fetchone()[0] > 0
            assert conn.execute(
                "select count(*) from fact_formal_bond_analytics_daily where report_date = ?",
                [REPORT_DATE],
            ).fetchone()[0] == 1
            assert conn.execute(
                "select count(*) from fact_formal_risk_tensor_daily where report_date = ?",
                [REPORT_DATE],
            ).fetchone()[0] == 1

        dates = client.get("/ui/balance-analysis/dates", headers=headers)
        assert dates.status_code == 200, dates.text
        assert dates.json()["result_meta"]["basis"] == "formal"
        assert dates.json()["result"]["report_dates"] == [REPORT_DATE]

        overview = client.get(
            "/ui/balance-analysis/overview",
            params={
                "report_date": REPORT_DATE,
                "position_scope": "all",
                "currency_basis": "CNY",
            },
            headers=headers,
        )
        assert overview.status_code == 200, overview.text
        envelope = overview.json()
        result_meta = envelope["result_meta"]
        assert result_meta["basis"] == "formal"
        assert result_meta["formal_use_allowed"] is True
        assert result_meta["fallback_mode"] == "none"
        assert result_meta["requested_report_date"] == REPORT_DATE
        assert result_meta["resolved_report_date"] == REPORT_DATE
        assert result_meta["as_of_date"] == REPORT_DATE
        assert result_meta["evidence_rows"] == 2
        result = envelope["result"]
        assert result["report_date"] == REPORT_DATE
        assert result["detail_row_count"] == 2
        assert result["asset_total_market_value_amount"] == "720.00000000"
        assert result["liability_total_market_value_amount"] == "72.00000000"
        assert result["total_market_value_amount"] == "792.00000000"
    finally:
        get_settings.cache_clear()
