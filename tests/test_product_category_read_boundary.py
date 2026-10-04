from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from backend.app.core_finance.product_category_pnl import CanonicalFactRow
from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import GovernanceRepository
from backend.app.repositories.product_category_pnl_repo import (
    PRODUCT_CATEGORY_ADJUSTMENT_STREAM,
    load_product_category_manual_adjustments,
)
from backend.app.services.product_category_pnl_service import (
    product_category_pnl_envelope,
    resolve_product_category_ytd_payload_for_home_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]


def _materialize_synthetic_months(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    from backend.app.tasks import product_category_pnl as task

    duckdb_path = tmp_path / "canonical.duckdb"
    governance_path = tmp_path / "governance"
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(duckdb_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance_path))
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    get_settings.cache_clear()
    facts = {
        day: [
            CanonicalFactRow(
                report_date=day,
                account_code="50204000001",
                currency="CNX",
                account_name="Synthetic income",
                beginning_balance=Decimal("0"),
                ending_balance=Decimal("0"),
                monthly_pnl=Decimal(amount),
                daily_avg_balance=Decimal("0"),
                annual_avg_balance=Decimal("0"),
                days_in_period=day.day,
            )
        ]
        for day, amount in ((date(2026, 1, 31), "100"), (date(2026, 2, 28), "200"))
    }
    pairs = [SimpleNamespace(report_date=day, source_version=f"synthetic-{day}") for day in facts]
    monkeypatch.setattr(task, "discover_source_pairs", lambda _path: pairs)
    monkeypatch.setattr(task, "build_canonical_facts", lambda pair: facts[pair.report_date])
    assert task.materialize_product_category_pnl_sync(
        duckdb_path=str(duckdb_path),
        governance_dir=str(governance_path),
        source_dir=str(tmp_path),
    )["status"] == "completed"
    return duckdb_path, governance_path


def _append_adjustment(governance_path: Path, **changes: object) -> None:
    record = {
        "adjustment_id": "synthetic-adjustment",
        "created_at": "2026-03-01T00:00:00Z",
        "report_date": "2026-01-31",
        "operator": "DELTA",
        "approval_status": "approved",
        "account_code": "50204000001",
        "currency": "CNX",
        "monthly_pnl": "25",
    }
    GovernanceRepository(base_dir=governance_path).append(
        PRODUCT_CATEGORY_ADJUSTMENT_STREAM, record | changes,
    )


def _delete_persisted_ytd(duckdb_path: Path) -> None:
    with duckdb.connect(str(duckdb_path)) as conn:
        conn.execute("delete from product_category_pnl_formal_read_model where view = 'ytd'")


@pytest.mark.parametrize("operator,expected", [("DELTA", "325"), ("OVERRIDE", "225")])
def test_canonical_fallback_does_not_apply_materialized_adjustments_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operator: str, expected: str,
) -> None:
    _append_adjustment(tmp_path / "governance", operator=operator)
    duckdb_path, governance_path = _materialize_synthetic_months(tmp_path, monkeypatch)
    formal = product_category_pnl_envelope(str(duckdb_path), "2026-02-28", "ytd")
    assert Decimal(str(formal["result"]["grand_total"]["business_net_income"])) == Decimal(expected)
    _delete_persisted_ytd(duckdb_path)

    fallback = resolve_product_category_ytd_payload_for_home_snapshot(
        str(duckdb_path), str(governance_path), "2026-02-28", 1.6,
    )

    assert fallback is not None
    # No balances or FTP: January 100 (+25 or replaced by25) plus February 200.
    assert fallback.grand_total.business_net_income == Decimal(expected)
    assert fallback.rows == [type(row).model_validate(item) for row, item in zip(
        fallback.rows, formal["result"]["rows"], strict=True,
    )]
    get_settings.cache_clear()


@pytest.mark.parametrize("latest_event,refreshed_total", [
    ({"monthly_pnl": "75"}, "375"),
    ({"approval_status": "rejected"}, "300"),
    ({"report_date": "2026-02-28"}, "325"),
])
def test_fallback_uses_last_materialization_until_adjustment_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    latest_event: dict[str, object], refreshed_total: str,
) -> None:
    _append_adjustment(tmp_path / "governance")
    duckdb_path, governance_path = _materialize_synthetic_months(tmp_path, monkeypatch)
    _append_adjustment(governance_path, created_at="2026-03-02T00:00:00Z", **latest_event)
    _delete_persisted_ytd(duckdb_path)

    fallback = resolve_product_category_ytd_payload_for_home_snapshot(
        str(duckdb_path), str(governance_path), "2026-02-28", 1.6,
    )

    assert fallback is not None
    assert fallback.grand_total.business_net_income == Decimal("325")

    _materialize_synthetic_months(tmp_path, monkeypatch)
    _delete_persisted_ytd(duckdb_path)
    refreshed = resolve_product_category_ytd_payload_for_home_snapshot(
        str(duckdb_path), str(governance_path), "2026-02-28", 1.6,
    )
    assert refreshed is not None
    assert refreshed.grand_total.business_net_income == Decimal(refreshed_total)
    if "report_date" in latest_event:
        january = product_category_pnl_envelope(str(duckdb_path), "2026-01-31", "monthly")
        assert Decimal(str(january["result"]["grand_total"]["business_net_income"])) == Decimal("100")
    get_settings.cache_clear()


def test_cold_read_fallback_executes_without_task_broker_or_storage_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    duckdb_path, governance_path = _materialize_synthetic_months(tmp_path, monkeypatch)
    _delete_persisted_ytd(duckdb_path)
    before = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    code = r'''
import importlib.abc
import sys
from decimal import Decimal

class NoTasksOrBroker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "dramatiq" or fullname.startswith(("dramatiq.", "backend.app.tasks")):
            raise AssertionError("Read fallback attempted task/broker import: " + fullname)

sys.meta_path.insert(0, NoTasksOrBroker())
import duckdb
connect = duckdb.connect
def read_only_connect(*args, **kwargs):
    assert kwargs.get("read_only") is True, "Read fallback attempted a writable connection"
    return connect(*args, **kwargs)
duckdb.connect = read_only_connect

from backend.app.services.product_category_pnl_service import resolve_product_category_ytd_payload_for_home_snapshot
result = resolve_product_category_ytd_payload_for_home_snapshot(sys.argv[1], sys.argv[2], "2026-02-28", 1.6)
assert result is not None
assert result.grand_total.business_net_income == Decimal("300")
assert not any(name.startswith(("backend.app.tasks", "dramatiq")) for name in sys.modules)
print(result.model_dump_json())
'''
    result = subprocess.run(
        [sys.executable, "-c", code, str(duckdb_path), str(governance_path)],
        cwd=ROOT,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=45,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["report_date"] == "2026-02-28"
    after = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    assert after == before
    get_settings.cache_clear()


def test_adjustment_snapshot_reduces_versions_before_month_filter(tmp_path: Path) -> None:
    events = [
        {"adjustment_id": "moved", "created_at": "2026-03-02", "report_date": "2026-02-28", "monthly_pnl": "7"},
        {"adjustment_id": "moved", "created_at": "2026-03-01", "report_date": "2026-01-31", "monthly_pnl": "9"},
        {"report_date": "2026-01-31", "monthly_pnl": "3"},
        {"report_date": "2026-01-31", "monthly_pnl": "4"},
    ]
    adjustments = load_product_category_manual_adjustments(tmp_path, date(2026, 1, 31), events=events)
    assert [item.monthly_pnl for item in adjustments] == [Decimal("3"), Decimal("4")]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("anchor", ["invalid", "20260228", "2026-03-31", "2025-12-31"])
def test_fallback_requires_existing_canonical_iso_anchor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, anchor: str,
) -> None:
    duckdb_path, governance_path = _materialize_synthetic_months(tmp_path, monkeypatch)
    fallback = resolve_product_category_ytd_payload_for_home_snapshot(
        str(duckdb_path), str(governance_path), anchor, 1.6,
    )
    assert fallback is None
    get_settings.cache_clear()


@pytest.mark.parametrize("failure_kind", ["pydantic", "custom_validator"])
def test_home_ytd_validation_fallback_log_omits_private_input(monkeypatch, caplog, failure_kind):
    from unittest.mock import Mock
    from backend.app.services import product_category_pnl_service as service
    marker = "PRIVATE_TOKEN_987"
    monkeypatch.setattr(service, "product_category_pnl_envelope", Mock(return_value={"result": {"report_date": marker}}))
    if failure_kind == "custom_validator":
        monkeypatch.setattr(service.ProductCategoryPnlPayload, "model_validate", Mock(side_effect=TypeError(marker)))
    canonical = Mock(return_value=None)
    monkeypatch.setattr(service, "product_category_pnl_payload_from_canonical_ytd_anchor", canonical)
    result = service.resolve_product_category_ytd_payload_for_home_snapshot("unused.duckdb", "unused-governance", "2026-08-31", 1.6)
    assert result is None
    canonical.assert_called_once_with("unused.duckdb", "unused-governance", "2026-08-31", 1.6)
    assert "2026-08-31" in caplog.text
    assert "falling back to canonical recompute" in caplog.text
    assert marker not in caplog.text
    assert ("ValidationError" if failure_kind == "pydantic" else "TypeError") in caplog.text
    assert not any(record.exc_info for record in caplog.records)
