from __future__ import annotations

import ast
from contextlib import closing
from decimal import Decimal
import inspect
import multiprocessing
from pathlib import Path

import duckdb
import pytest

from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.repositories import bond_analytics_repo, pnl_repo, product_category_pnl_repo, risk_tensor_repo
from backend.app.repositories.duckdb_read_context import (
    DuckDBOnlineReadRequiredError,
    DuckDBReadSelection,
    duckdb_read_scope,
)
from backend.app.repositories.liability_analytics_repo import LiabilityAnalyticsRepository


def _database(path: Path, report_date: str) -> None:
    with closing(duckdb.connect(str(path))) as conn:
        conn.execute("CREATE TABLE sentinel(value VARCHAR)")
        conn.execute("INSERT INTO sentinel VALUES (?)", [report_date])
        conn.execute("CREATE TABLE fact_formal_pnl_fi(report_date VARCHAR)")
        conn.execute("INSERT INTO fact_formal_pnl_fi VALUES (?)", [report_date])
        conn.execute("""CREATE TABLE product_category_pnl_formal_read_model(
            report_date VARCHAR, view VARCHAR, category_id VARCHAR, business_net_income DECIMAL(18,2))""")
        conn.execute("INSERT INTO product_category_pnl_formal_read_model VALUES (?, 'ytd', 'grand_total', 1.25)",
                     [report_date])


def _hold_writer(path: str, lock_dir: str, ready, release, result) -> None:
    try:
        with acquire_lock(resolve_duckdb_writer_lock(path), base_dir=Path(lock_dir), timeout_seconds=5):
            with closing(duckdb.connect(path)) as conn:
                conn.execute("UPDATE sentinel SET value='writer-open'")
                ready.set()
                if not release.wait(15):
                    raise TimeoutError("parent did not release test writer")
                conn.execute("UPDATE sentinel SET value='writer-completed'")
        result.send("completed")
    except Exception as exc:
        result.send(type(exc).__name__)
    finally:
        result.close()


def _assert_representative_reads(active: Path) -> None:
    for connect in (
        bond_analytics_repo._connect_read_only,
        risk_tensor_repo._connect_read_only,
        lambda path: LiabilityAnalyticsRepository(path)._connect(),
    ):
        conn = connect(str(active))
        assert conn is not None
        with closing(conn):
            assert conn.execute("SELECT value FROM sentinel").fetchone() == ("2026-01-01",)
    assert pnl_repo.PnlRepository(str(active)).list_formal_fi_report_dates() == ["2026-01-01"]
    product = product_category_pnl_repo.ProductCategoryPnlRepository(str(active))
    assert product.list_report_dates() == ["2026-01-01"]
    assert product.fetch_home_headline_values(report_date="2026-01-01", views=["ytd"]) == {
        "ytd": {"grand_total": Decimal("1.25")},
    }


def test_five_repositories_read_snapshot_while_another_process_owns_active_writer(tmp_path):
    active, snapshot = tmp_path / "active.duckdb", tmp_path / "r0.duckdb"
    _database(active, "2026-01-02")
    _database(snapshot, "2026-01-01")
    context = multiprocessing.get_context("spawn")
    ready, release = context.Event(), context.Event()
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=_hold_writer, args=(str(active), str(tmp_path / "locks"), ready, release, sender))
    process.start()
    sender.close()
    try:
        assert ready.wait(8), "writer never opened the active database"
        with duckdb_read_scope(DuckDBReadSelection(active, snapshot, "r0"), required_online=True):
            _assert_representative_reads(active)
        release.set()
        assert receiver.poll(8), "writer did not report completion"
        assert receiver.recv() == "completed"
        process.join(5)
        assert process.exitcode == 0
    finally:
        release.set()
        receiver.close()
        if process.is_alive():
            process.terminate()
            process.join(5)
    with closing(duckdb.connect(str(active), read_only=True)) as conn:
        assert conn.execute("SELECT value FROM sentinel").fetchone() == ("writer-completed",)


@pytest.mark.parametrize("read", [
    bond_analytics_repo._connect_read_only,
    risk_tensor_repo._connect_read_only,
    lambda path: LiabilityAnalyticsRepository(path)._connect(),
    lambda path: pnl_repo.PnlRepository(path).list_formal_fi_report_dates(),
    lambda path: product_category_pnl_repo.ProductCategoryPnlRepository(path).list_report_dates(),
])
def test_required_selection_error_is_not_swallowed_as_empty_data(tmp_path, read):
    active = tmp_path / "active.duckdb"
    _database(active, "2026-01-02")
    with duckdb_read_scope(None, required_online=True, active_path=active):
        with pytest.raises(DuckDBOnlineReadRequiredError):
            read(str(active))


@pytest.mark.parametrize("module", [pnl_repo, product_category_pnl_repo])
def test_every_inline_read_connect_resolves_the_snapshot_path(module):
    calls = []
    for node in ast.walk(ast.parse(inspect.getsource(module))):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if not isinstance(node.func.value, ast.Name) or node.func.value.id != "duckdb" or node.func.attr != "connect":
            continue
        if any(item.arg == "read_only" and isinstance(item.value, ast.Constant) and item.value.value is True
               for item in node.keywords):
            calls.append(node)
            assert isinstance(node.args[0], ast.Call)
            assert isinstance(node.args[0].func, ast.Name)
            assert node.args[0].func.id == "resolve_effective_read_path"
    assert calls
