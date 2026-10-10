from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from backend.app.repositories.task_write_guard import require_repository_task_write_scope
from backend.app.tasks import stock_factor_market_cap_backfill as writer
from backend.scripts import backfill_stock_factor_market_cap_tushare as module


class _FakeFrame:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows
        self.empty = not rows

    def __len__(self) -> int:
        return len(self._rows)

    def to_dict(self, orient: str) -> list[dict[str, object]]:
        assert orient == "records"
        return list(self._rows)


def _create_factor_table(path: Path) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.execute(
            """
            create table choice_stock_factor_snapshot (
              as_of_date varchar, stock_code varchar, pe double, pb double, ps double,
              roe double, gross_margin double, three_month_return double,
              twelve_month_return double, volatility double, dividend_yield double,
              total_mv double, circ_mv double, industry varchar, source_version varchar,
              vendor_version varchar, rule_version varchar, run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into choice_stock_factor_snapshot values (
              '2026-09-04', '000001.SZ', 8.0, 1.0, 2.0, 0.1, 0.2,
              0.03, 0.08, 0.15, 0.02, null, null, '银行', 'sv_existing',
              'vv_existing', 'rv_existing', 'run_existing'
            )
            """
        )
    finally:
        conn.close()


def test_run_updates_existing_and_inserts_missing_factor_rows(
    tmp_path: Path, monkeypatch
) -> None:
    duckdb_path = tmp_path / "market-cap-backfill.duckdb"
    _create_factor_table(duckdb_path)
    frame = _FakeFrame(
        [
            {
                "ts_code": "000001.SZ",
                "trade_date": "20260904",
                "total_mv": 12.5,
                "circ_mv": 10.0,
            },
            {
                "ts_code": "000002.SZ",
                "trade_date": "20260904",
                "total_mv": 20.0,
                "circ_mv": 16.0,
            },
        ]
    )
    pro = SimpleNamespace(daily_basic=lambda **_kwargs: frame)
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: SimpleNamespace(duckdb_path=duckdb_path),
    )
    monkeypatch.setattr(
        module,
        "resolve_tushare_token_with_settings_fallback",
        lambda _settings: "test-token",
    )
    monkeypatch.setattr(
        module,
        "import_tushare_pro",
        lambda: SimpleNamespace(pro_api=lambda _token: pro),
    )

    result = module.run("2026-09-04", duckdb_path=duckdb_path)

    assert result["updated"] == 1
    assert result["inserted"] == 1
    conn = duckdb.connect(str(duckdb_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select stock_code, total_mv, circ_mv, source_version
            from choice_stock_factor_snapshot
            order by stock_code
            """
        ).fetchall()
    finally:
        conn.close()
    assert rows == [
        ("000001.SZ", 125000.0, 100000.0, "sv_existing"),
        ("000002.SZ", 200000.0, 160000.0, module.SOURCE_VERSION),
    ]


def test_run_rejects_implicit_settings_database_before_vendor_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    implicit_path = tmp_path / "implicit-settings.duckdb"
    _create_factor_table(implicit_path)
    before = implicit_path.read_bytes()
    monkeypatch.setattr(module, "get_settings", lambda: SimpleNamespace(duckdb_path=implicit_path))
    monkeypatch.setattr(module, "resolve_tushare_token_with_settings_fallback", lambda _settings: "test-token")
    vendor_calls: list[object] = []

    def fetch(**kwargs: object) -> _FakeFrame:
        vendor_calls.append(kwargs)
        return _FakeFrame([{"ts_code": "000001.SZ", "total_mv": 12.5, "circ_mv": 10.0}])

    monkeypatch.setattr(
        module, "import_tushare_pro",
        lambda: SimpleNamespace(pro_api=lambda _token: SimpleNamespace(daily_basic=fetch)),
    )
    with pytest.raises(TypeError, match="duckdb_path"):
        module.run("2026-09-04")  # type: ignore[call-arg]
    assert vendor_calls == []
    assert implicit_path.read_bytes() == before


def test_cli_requires_an_explicit_database_target(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_run(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("missing target must be rejected before run")

    monkeypatch.setattr(module, "run", reject_run)
    with pytest.raises(SystemExit) as excinfo:
        module.main(["2026-09-04"])
    assert excinfo.value.code == 2


@pytest.mark.parametrize("operation", ["schema", "rows"])
def test_market_cap_writers_reject_calls_outside_task_scope(operation: str) -> None:
    class RejectConnection:
        def execute(self, *_args: object, **_kwargs: object) -> None:
            raise AssertionError("unguarded writer must not execute SQL")

    with pytest.raises(PermissionError, match="repository task write scope"):
        if operation == "schema":
            writer._ensure_market_cap_columns(RejectConnection())  # type: ignore[arg-type]
        else:
            writer._upsert_market_cap_rows(  # type: ignore[arg-type]
                RejectConnection(), as_of_date="2026-09-04", records=[],
            )


def test_market_cap_writer_opens_connection_inside_lock_and_task_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "guarded.duckdb"
    _create_factor_table(target)
    original_connect = duckdb.connect
    lock_held = False
    writer_opens: list[str] = []

    @contextmanager
    def lock(_definition: object, *, base_dir: Path):
        nonlocal lock_held
        assert base_dir == target.parent
        lock_held = True
        try:
            yield
        finally:
            lock_held = False

    def connect(database: str, *, read_only: bool):
        assert lock_held
        assert read_only is False
        require_repository_task_write_scope("market-cap-test")
        writer_opens.append(database)
        return original_connect(database, read_only=read_only)

    monkeypatch.setattr(writer, "acquire_lock", lock)
    monkeypatch.setattr(writer.duckdb, "connect", connect)
    assert writer.backfill_market_cap_rows(
        duckdb_path=target, as_of_date="2026-09-04",
        records=[{"ts_code": "000001.SZ", "total_mv": 12.5, "circ_mv": 10.0}],
        expected_identity=writer.market_cap_target_identity(target),
    ) == {"updated": 1, "inserted": 0}
    assert writer_opens == [str(target.resolve())]
    assert lock_held is False
    with pytest.raises(PermissionError):
        require_repository_task_write_scope("scope-must-be-restored")


def test_market_cap_writer_rolls_back_schema_and_rows_on_failure(tmp_path: Path) -> None:
    target = tmp_path / "rollback.duckdb"
    _create_factor_table(target)
    with duckdb.connect(str(target)) as conn:
        conn.execute("alter table choice_stock_factor_snapshot drop column total_mv")
        conn.execute("alter table choice_stock_factor_snapshot drop column circ_mv")
    with pytest.raises(ValueError):
        writer.backfill_market_cap_rows(
            duckdb_path=target, as_of_date="2026-09-04",
            expected_identity=writer.market_cap_target_identity(target),
            records=[
                {"ts_code": "000001.SZ", "total_mv": 12.5, "circ_mv": 10.0},
                {"ts_code": "000002.SZ", "total_mv": "invalid", "circ_mv": 10.0},
            ],
        )
    with duckdb.connect(str(target), read_only=True) as conn:
        columns = {row[0] for row in conn.execute("describe choice_stock_factor_snapshot").fetchall()}
        assert "total_mv" not in columns
        assert "circ_mv" not in columns
        assert conn.execute("select stock_code from choice_stock_factor_snapshot").fetchall() == [("000001.SZ",)]


def test_market_cap_writer_refuses_to_create_a_missing_target(tmp_path: Path) -> None:
    target = tmp_path / "missing.duckdb"
    with pytest.raises(FileNotFoundError):
        writer.backfill_market_cap_rows(
            duckdb_path=target, as_of_date="2026-09-04", records=[], expected_identity=(0, 0),
        )
    assert not target.exists()


def test_vendor_wait_cannot_rebind_backfill_to_a_replacement_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "target.duckdb"
    replacement = tmp_path / "replacement.duckdb"
    displaced = tmp_path / "original.duckdb"
    _create_factor_table(target)
    _create_factor_table(replacement)
    before_original = target.read_bytes()
    before_replacement = replacement.read_bytes()
    vendor_calls: list[object] = []

    def fetch(**kwargs: object) -> _FakeFrame:
        vendor_calls.append(kwargs)
        target.rename(displaced)
        replacement.rename(target)
        return _FakeFrame([{"ts_code": "000001.SZ", "total_mv": 12.5, "circ_mv": 10.0}])

    monkeypatch.setattr(module, "get_settings", lambda: SimpleNamespace(duckdb_path=target))
    monkeypatch.setattr(module, "resolve_tushare_token_with_settings_fallback", lambda _settings: "test-token")
    monkeypatch.setattr(
        module, "import_tushare_pro",
        lambda: SimpleNamespace(pro_api=lambda _token: SimpleNamespace(daily_basic=fetch)),
    )
    with pytest.raises(PermissionError, match="identity changed"):
        module.run(duckdb_path=target)
    assert len(vendor_calls) == 1
    assert displaced.read_bytes() == before_original
    assert target.read_bytes() == before_replacement


def test_backfill_rejects_target_replacement_at_connection_open_before_sql(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "target.duckdb"
    replacement = tmp_path / "replacement.duckdb"
    displaced = tmp_path / "original.duckdb"
    _create_factor_table(target)
    _create_factor_table(replacement)
    expected_identity = writer.market_cap_target_identity(target)
    before_original = target.read_bytes()
    before_replacement = replacement.read_bytes()
    original_connect = duckdb.connect
    sql_calls: list[object] = []

    class ObservedConnection:
        def __init__(self, connection: object) -> None:
            self.connection = connection

        def execute(self, *args: object, **kwargs: object):
            sql_calls.append(args)
            return self.connection.execute(*args, **kwargs)

        def close(self) -> None:
            self.connection.close()

    def connect(database: str, *, read_only: bool):
        assert read_only is False
        target.rename(displaced)
        replacement.rename(target)
        return ObservedConnection(original_connect(database, read_only=read_only))

    monkeypatch.setattr(writer.duckdb, "connect", connect)
    with pytest.raises(PermissionError, match="identity changed"):
        writer.backfill_market_cap_rows(
            duckdb_path=target, as_of_date="2026-09-04", expected_identity=expected_identity,
            records=[{"ts_code": "000001.SZ", "total_mv": 12.5, "circ_mv": 10.0}],
        )
    assert sql_calls == []
    assert displaced.read_bytes() == before_original
    assert target.read_bytes() == before_replacement
