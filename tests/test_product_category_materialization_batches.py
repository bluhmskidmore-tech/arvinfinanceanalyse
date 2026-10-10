from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from backend.app.core_finance.product_category_pnl import CanonicalFactRow
from backend.app.governance.settings import get_settings
from backend.app.repositories.governance_repo import CACHE_BUILD_RUN_STREAM, GovernanceRepository
from backend.app.services.product_category_source_service import SourcePair
from backend.app.tasks import product_category_pnl as task


@pytest.fixture
def materialization(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Other suites evict this task after collection. Keep patched execution and
    # the implementation fingerprint bound to the same module.
    monkeypatch.setitem(sys.modules, task.__name__, task)
    parent_name, _, child_name = task.__name__.rpartition(".")
    monkeypatch.setitem(vars(sys.modules[parent_name]), child_name, task)
    database = tmp_path / "isolated.duckdb"
    governance = tmp_path / "governance"
    monkeypatch.setenv("MOSS_ENVIRONMENT", "development")
    monkeypatch.setenv("MOSS_GOVERNANCE_BACKEND", "jsonl")
    monkeypatch.setenv("MOSS_DUCKDB_PATH", str(database))
    monkeypatch.setenv("MOSS_GOVERNANCE_PATH", str(governance))
    get_settings.cache_clear()
    pair = SourcePair(
        month_key="202608",
        report_date=date(2026, 8, 31),
        ledger_path=tmp_path / "ledger.xlsx",
        avg_path=tmp_path / "average.xlsx",
        source_version="synthetic-source-v1",
    )
    monkeypatch.setattr(task, "discover_source_pairs", lambda _path: [pair])
    # This suite certifies persistence, not financial formulas or Excel parsing.
    monkeypatch.setattr(task, "calculate_read_model", lambda *_args: {"rows": []})
    yield database, governance
    get_settings.cache_clear()


def _facts(count: int) -> list[CanonicalFactRow]:
    return [
        CanonicalFactRow(
            report_date=date(2026, 8, 31),
            account_code=f"synthetic-{index:04d}",
            currency="CNX" if index % 2 == 0 else "CNY",
            account_name=f"精度与批次测试 {index}",
            beginning_balance=Decimal("12345678901234.12345678") + index,
            ending_balance=Decimal("-12345678901234.87654321") - index,
            monthly_pnl=Decimal("0.00000001") * (index + 1),
            daily_avg_balance=Decimal("100.12345678"),
            annual_avg_balance=Decimal("0"),
            days_in_period=31,
        )
        for index in range(count)
    ]


@pytest.mark.parametrize("count", [0, 1001])
def test_fact_batches_preserve_exact_values_and_repeat_without_duplicates(
    materialization, monkeypatch: pytest.MonkeyPatch, count: int,
) -> None:
    database, governance = materialization
    monkeypatch.setattr(task, "build_canonical_facts", lambda _pair: _facts(count))
    results = []
    for attempt in range(2):
        receipt = task.materialize_product_category_pnl_sync(
            duckdb_path=str(database), governance_dir=str(governance), run_id=f"batch-{attempt}",
        )
        assert receipt["report_dates"] == ["2026-08-31"]
        with duckdb.connect(str(database), read_only=True) as connection:
            rows = connection.execute(
                "select * from product_category_pnl_canonical_fact order by account_code"
            ).fetchall()
        assert len(rows) == count
        for index, row in enumerate(rows):
            assert row == (
                "2026-08-31", f"synthetic-{index:04d}", "CNX" if index % 2 == 0 else "CNY",
                f"精度与批次测试 {index}",
                Decimal("12345678901234.12345678") + index,
                Decimal("-12345678901234.87654321") - index,
                Decimal("0.00000001") * (index + 1),
                Decimal("100.12345678"), Decimal("0"), 31,
                "synthetic-source-v1", task.RULE_VERSION,
            )
        results.append(rows)
    assert results[0] == results[1]


def test_late_batch_failure_restores_all_existing_product_category_tables(
    materialization, monkeypatch: pytest.MonkeyPatch,
) -> None:
    database, governance = materialization
    monkeypatch.setattr(task, "build_canonical_facts", lambda _pair: _facts(1))
    task.materialize_product_category_pnl_sync(
        duckdb_path=str(database), governance_dir=str(governance), run_id="seed",
    )
    tables = (
        "product_category_pnl_canonical_fact",
        "product_category_pnl_formal_read_model",
        "product_category_pnl_scenario_read_model",
    )
    with duckdb.connect(str(database)) as connection:
        for table in tables[1:]:
            connection.execute(
                f"insert into {table} (report_date, category_id, cnx_cash) values (?, ?, ?)",
                ["2026-08-31", "rollback-sentinel", Decimal("12.34567891")],
            )
        before = {table: connection.execute(f"select * from {table} order by all").fetchall() for table in tables}

    facts = _facts(1001)
    # Overflow is deliberately in the final, incomplete batch, after prior writes.
    facts[-1].monthly_pnl = Decimal("10000000000000000")
    monkeypatch.setattr(task, "build_canonical_facts", lambda _pair: facts)
    with pytest.raises(duckdb.ConversionException):
        task.materialize_product_category_pnl_sync(
            duckdb_path=str(database), governance_dir=str(governance), run_id="late-batch-failure",
        )

    with duckdb.connect(str(database), read_only=True) as connection:
        after = {table: connection.execute(f"select * from {table} order by all").fetchall() for table in tables}
    assert after == before
    records = GovernanceRepository(base_dir=governance).read_all(CACHE_BUILD_RUN_STREAM)
    assert records[-1]["run_id"] == "late-batch-failure"
    assert records[-1]["status"] == "failed"
