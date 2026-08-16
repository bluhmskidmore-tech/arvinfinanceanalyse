from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb
import pytest

from backend.app.repositories.nbs_gdp_release_adapter import NbsGdpReleaseError
from backend.app.tasks.nbs_gdp_release_ingest import (
    refresh_nbs_gdp_release,
    run_nbs_gdp_release_ingest_once,
)


@dataclass
class _Settings:
    duckdb_path: str
    governance_path: str


def test_nbs_gdp_task_runs_migrations_and_returns_structured_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "nbs-task.duckdb"
    governance_path = tmp_path / "governance"
    captured: dict[str, object] = {}

    def get_settings() -> _Settings:
        return _Settings(str(db_path), str(governance_path))

    class ServiceStub:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def ingest_release(self, ingest_batch_id: str, *, reference_date: date):
            conn = captured["catalog_repo"]._conn
            assert conn is captured["etl_service"]._conn
            tables = {
                row[0]
                for row in conn.execute(
                    "select table_name from information_schema.tables"
                ).fetchall()
            }
            assert "external_data_catalog" in tables
            assert "std_external_macro_daily" in tables
            assert reference_date == date(2026, 7, 17)
            return {
                "status": "success",
                "series_id": "nbs.macro.cn_gdp.quarterly",
                "release_url": "https://www.stats.gov.cn/release.html",
                "latest_observation": "2026-06-30",
                "materialized_rows": 2,
                "source_version": "nbs_gdp_release_sha256_deadbeef",
                "vendor_version": "vv_nbs_gdp_release_sha256_deadbeef",
                "rule_version": "rv_nbs_gdp_release_v1",
                "html_raw_zone_path": "raw/release.html",
                "normalized_raw_zone_path": "raw/gdp.json",
            }

    globals_ = run_nbs_gdp_release_ingest_once.__globals__
    monkeypatch.setitem(globals_, "get_settings", get_settings)
    monkeypatch.setitem(globals_, "NbsGdpReleaseIngestService", ServiceStub)

    result = run_nbs_gdp_release_ingest_once(
        "nbs-task-batch-1",
        reference_date=date(2026, 7, 17),
    )

    assert result["status"] == "success"
    assert result["ingest_batch_id"] == "nbs-task-batch-1"
    assert result["release_url"] == "https://www.stats.gov.cn/release.html"
    assert result["latest_observation"] == "2026-06-30"
    assert result["materialized_rows"] == 2
    assert result["elapsed_seconds"] >= 0
    assert governance_path.is_dir()
    conn = captured["catalog_repo"]._conn
    with pytest.raises(duckdb.ConnectionException):
        conn.execute("select 1")


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (NbsGdpReleaseError("release unavailable"), "blocked"),
        (OSError("write failed"), "error"),
    ],
)
def test_nbs_gdp_task_returns_structured_failure_and_closes_connection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    status: str,
) -> None:
    db_path = tmp_path / f"{status}.duckdb"
    captured: dict[str, object] = {}

    def get_settings() -> _Settings:
        return _Settings(str(db_path), str(tmp_path / "gov"))

    class ServiceStub:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def ingest_release(self, *_args, **_kwargs):
            raise error

    globals_ = run_nbs_gdp_release_ingest_once.__globals__
    monkeypatch.setitem(globals_, "get_settings", get_settings)
    monkeypatch.setitem(globals_, "NbsGdpReleaseIngestService", ServiceStub)

    result = run_nbs_gdp_release_ingest_once(
        "nbs-failed-batch",
        reference_date=date(2026, 7, 17),
    )

    assert result["status"] == status
    assert result["ingest_batch_id"] == "nbs-failed-batch"
    assert str(error) in str(result["error"])
    conn = captured["catalog_repo"]._conn
    with pytest.raises(duckdb.ConnectionException):
        conn.execute("select 1")


def test_nbs_gdp_actor_name_is_stable_and_module_has_no_scheduler_loop() -> None:
    assert refresh_nbs_gdp_release.actor_name == "refresh_nbs_gdp_release"
    task_path = (
        Path(__file__).resolve().parents[1]
        / "backend"
        / "app"
        / "tasks"
        / "nbs_gdp_release_ingest.py"
    )
    text = task_path.read_text(encoding="utf-8")
    assert "register_actor_once" in text
    assert "schtasks" not in text.lower()
    assert "while True" not in text
    assert "schedule." not in text
