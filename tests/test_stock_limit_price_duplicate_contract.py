"""MS-012: actual ingestion/writer contracts with synthetic owned DuckDB only.

These are task-pipeline tests, not a provider integration or helper-only replay.
The real task, schema, file locks, SQL writer, DQ and single-date wrapper run;
the supplier is inert and the rollback case injects one DuckDB write failure.
"""

from __future__ import annotations

import copy
import importlib
import math
import socket
from contextlib import contextmanager

import duckdb
import pytest

pytestmark = [pytest.mark.excluded_surface_acceptance, pytest.mark.surface_market_data]

DAY = "2026-09-29"
NEXT_DAY = "2026-09-30"
OLDER_DAY = "2026-09-28"
CODE_A = "000001.SZ"
CODE_B = "600001.SH"
CODE_C = "430001.BJ"


class InertClient:
    def __init__(self, payloads, *, on_fetch=None):
        self.payloads = payloads
        self.calls = []
        self.on_fetch = on_fetch

    def stk_limit(self, **kwargs):
        self.calls.append(dict(kwargs))
        if self.on_fetch is not None:
            self.on_fetch()
        return copy.deepcopy(self.payloads[kwargs["trade_date"]])


@pytest.fixture
def task(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError("Live network/default supplier access is forbidden in MS-012 tests")

    monkeypatch.setenv("MOSS_CLOUD_SYNTHETIC", "1")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)
    module = importlib.import_module("backend.app.tasks.stock_limit_price_ingest")
    monkeypatch.setattr(module, "_DefaultTushareStkLimitClient", deny)
    monkeypatch.setattr(module, "import_tushare_pro", deny)
    monkeypatch.setattr(module, "resolve_tushare_token_with_settings_fallback", deny)
    return module


@pytest.fixture
def database(tmp_path, task):
    path = tmp_path / "synthetic-limit-prices.duckdb"
    with duckdb.connect(str(path)) as conn:
        task.ensure_stock_limit_price_daily_schema(conn)
        conn.execute(
            "create table choice_stock_daily_observation (trade_date varchar, stock_code varchar)"
        )
        conn.executemany(
            "insert into stock_limit_price_daily values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (day, code, 8.8, 7.2, 8.0, "old-source", "old-vendor", "old-rule", "old-run")
                for day in (OLDER_DAY, DAY, NEXT_DAY)
                for code in (CODE_A, CODE_B)
            ],
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?)",
            [(day, code) for day in (DAY, NEXT_DAY) for code in (CODE_A, CODE_B)],
        )
    return path


def snapshot(path):
    with duckdb.connect(str(path), read_only=True) as conn:
        return conn.execute(
            "select * from stock_limit_price_daily order by trade_date, stock_code"
        ).fetchall()


def row(*, code=CODE_A, day=DAY, up=11, down=9, pre=10):
    return {"trade_date": day, "ts_code": code, "up_limit": up, "down_limit": down, "pre_close": pre}


def run(task, path, payloads, **kwargs):
    client = InertClient({day.replace("-", ""): rows for day, rows in payloads.items()})
    result = task.ingest_stock_limit_prices(
        duckdb_path=path,
        start_date=DAY,
        client=client,
        run_id="synthetic-ms012",
        retry_sleep_seconds=0,
        **kwargs,
    )
    return result, client


def observe_write_boundaries(task, monkeypatch):
    events = {"locks": [], "writes": [], "schemas": []}
    original_lock = task.acquire_lock
    original_writer = task._replace_rows_by_date
    original_schema = task.ensure_stock_limit_price_daily_schema

    @contextmanager
    def observed_lock(definition, **kwargs):
        events["locks"].append(definition.key)
        with original_lock(definition, **kwargs) as value:
            yield value

    def observed_writer(*args, **kwargs):
        events["writes"].append("replace")
        return original_writer(*args, **kwargs)

    def observed_schema(*args, **kwargs):
        events["schemas"].append("ensure")
        return original_schema(*args, **kwargs)

    monkeypatch.setattr(task, "acquire_lock", observed_lock)
    monkeypatch.setattr(task, "_replace_rows_by_date", observed_writer)
    monkeypatch.setattr(task, "ensure_stock_limit_price_daily_schema", observed_schema)
    return events


CONFLICTS = [
    pytest.param({"up": 12}, id="up-price"),
    pytest.param({"down": 8}, id="down-price"),
    pytest.param({"up": 12, "down": 8}, id="both-prices"),
    pytest.param({"pre": 10.5}, id="preclose-price"),
    pytest.param({"pre": None}, id="preclose-absent"),
    pytest.param({"up": math.nextafter(11.0, math.inf)}, id="up-one-ulp"),
]


@pytest.mark.parametrize("change", CONFLICTS)
@pytest.mark.parametrize("reverse", [False, True], ids=["forward", "reverse"])
def test_conflicting_accepted_rows_abort_before_writer(task, database, monkeypatch, change, reverse):
    before = snapshot(database)
    events = observe_write_boundaries(task, monkeypatch)
    payload = [row(), row(**change)]
    if reverse:
        payload.reverse()
    error = None
    try:
        run(task, database, {DAY: payload})
    except RuntimeError as exc:
        error = exc
    assert snapshot(database) == before, "conflicting rows must preserve all prices and lineage"
    assert events == {"locks": [], "writes": [], "schemas": []}
    assert error is not None, "a conflicting accepted duplicate must be an explicit error"
    assert "conflicting" in str(error) and CODE_A in str(error) and DAY in str(error)


@pytest.mark.parametrize("reverse", [False, True], ids=["forward", "reverse"])
def test_later_date_conflict_aborts_entire_collected_batch(task, database, monkeypatch, reverse):
    before = snapshot(database)
    events = observe_write_boundaries(task, monkeypatch)
    later = [row(day=NEXT_DAY), row(day=NEXT_DAY, pre=None)]
    if reverse:
        later.reverse()
    client = InertClient({DAY.replace("-", ""): [row()], NEXT_DAY.replace("-", ""): later})
    error = None
    try:
        task.ingest_stock_limit_prices(
            duckdb_path=database, start_date=DAY, end_date=NEXT_DAY,
            client=client, run_id="synthetic-later-conflict", retry_sleep_seconds=0,
        )
    except RuntimeError as exc:
        error = exc
    assert [call["trade_date"] for call in client.calls] == ["20260929", "20260930"]
    assert snapshot(database) == before, "later conflict must prevent earlier collected-date writes"
    assert events == {"locks": [], "writes": [], "schemas": []}
    assert error is not None and "conflicting" in str(error) and NEXT_DAY in str(error)


@pytest.mark.parametrize("reverse", [False, True], ids=["forward", "reverse"])
def test_daily_conflict_allows_only_read_preflight_lock(task, database, monkeypatch, reverse):
    before = snapshot(database)
    events = observe_write_boundaries(task, monkeypatch)
    duplicates = [row(), row(up=12)]
    if reverse:
        duplicates.reverse()
    error = None
    try:
        run(task, database, {DAY: duplicates + [row(code=CODE_B)]}, require_observation_coverage=True)
    except RuntimeError as exc:
        error = exc
    assert snapshot(database) == before
    assert events["writes"] == events["schemas"] == []
    assert events["locks"] == [task.resolve_duckdb_writer_lock(database).key]
    assert error is not None and "conflicting" in str(error)


@pytest.mark.parametrize("reverse", [False, True], ids=["forward", "reverse"])
def test_identical_normalized_duplicates_preserve_warning_counts_and_lineage(task, database, reverse):
    payload = [row(), row(code=" 000001.sz ", day="20260929", up="11.000", down="9e0", pre="10.0")]
    if reverse:
        payload.reverse()
    result, client = run(task, database, {DAY: payload})
    after = snapshot(database)
    stored = [item for item in after if item[0] == DAY]
    assert len(stored) == 1 and stored[0][:5] == (DAY, CODE_A, 11.0, 9.0, 10.0)
    expected_source = task._source_version([
        {"trade_date": DAY, "stock_code": CODE_A, "up_limit": 11.0, "down_limit": 9.0, "pre_close": 10.0}
    ])
    assert stored[0][5:] == (
        expected_source, task._vendor_version("20260929", run_id="synthetic-ms012"),
        task.RULE_VERSION, "synthetic-ms012",
    )
    assert result["status"] == "completed_with_warnings"
    assert result["inserted_row_count"] == result["skipped_invalid_row_count"] == 1
    assert result["date_results"][0]["skipped_invalid_row_count"] == 1
    assert result["dq"]["hard_violation_count"] == 0
    assert result["dq"]["issues"] == [
        "1 vendor rows rejected before write (nonpositive limits, up_limit <= down_limit, or malformed rows)"
    ]
    assert client.calls == [{"trade_date": "20260929", "fields": task.TUSHARE_STK_LIMIT_FIELDS}]


@pytest.mark.parametrize("reverse", [False, True], ids=["valid-first", "invalid-first"])
def test_invalid_rows_still_skip_without_creating_duplicate_conflicts(task, database, reverse):
    invalid = [
        row(day=NEXT_DAY, up=12), row(code=""), row(up=0), row(down=-1),
        row(up=float("nan")), row(down=float("inf")), row(up=float("-inf")),
        row(up="not-a-price"), row(up=None), row(up=9), row(up=8), {},
    ]
    payload = [row()] + invalid
    if reverse:
        payload.reverse()
    result, _ = run(task, database, {DAY: payload + [None, "not-a-record", 7]})
    assert result["inserted_row_count"] == 1
    assert result["skipped_invalid_row_count"] == len(invalid)
    assert result["status"] == "completed_with_warnings"
    assert [item[:5] for item in snapshot(database) if item[0] == DAY] == [
        (DAY, CODE_A, 11.0, 9.0, 10.0)
    ]


def test_invalid_optional_preclose_remains_none_and_deduplicates(task, database):
    absent = row()
    del absent["pre_close"]
    payload = [absent] + [row(pre=value) for value in (None, "", 0, -1, float("nan"), float("inf"), "bad")]
    result, _ = run(task, database, {DAY: payload})
    assert result["skipped_invalid_row_count"] == len(payload) - 1
    assert [item[:5] for item in snapshot(database) if item[0] == DAY] == [
        (DAY, CODE_A, 11.0, 9.0, None)
    ]
    assert result["dq"]["ratio_sampled_count"] == 0


def test_distinct_codes_and_dates_keep_separate_prices_and_old_date(task, database):
    before = snapshot(database)
    result, _ = run(task, database, {
        DAY: [row(code=CODE_B, up=22, down=18, pre=20), row()],
        NEXT_DAY: [row(day=NEXT_DAY, up=33, down=27, pre=30)],
    }, end_date=NEXT_DAY)
    after = snapshot(database)
    assert result["status"] == "completed"
    assert result["inserted_row_count"] == 3 and result["written_date_count"] == 2
    assert [item[:5] for item in after if item[0] != OLDER_DAY] == [
        (DAY, CODE_A, 11.0, 9.0, 10.0), (DAY, CODE_B, 22.0, 18.0, 20.0),
        (NEXT_DAY, CODE_A, 33.0, 27.0, 30.0),
    ]
    assert [item for item in after if item[0] == OLDER_DAY] == [item for item in before if item[0] == OLDER_DAY]
    assert result["write_scope"] == task.BACKFILL_WRITE_SCOPE


def test_daily_missing_required_code_rejects_before_write(task, database, monkeypatch):
    before = snapshot(database)
    events = observe_write_boundaries(task, monkeypatch)
    with pytest.raises(RuntimeError, match="missing required stock limit prices"):
        run(task, database, {DAY: [row()]}, require_observation_coverage=True)
    assert snapshot(database) == before
    assert events["writes"] == events["schemas"] == []
    assert len(events["locks"]) == 1


def test_daily_domain_growth_is_rechecked_under_writer_lock(task, database, monkeypatch):
    before = snapshot(database)
    events = observe_write_boundaries(task, monkeypatch)

    def grow_observation_domain():
        with duckdb.connect(str(database)) as conn:
            conn.execute("insert into choice_stock_daily_observation values (?, ?)", [DAY, CODE_C])

    client = InertClient({"20260929": [row(), row(code=CODE_B)]}, on_fetch=grow_observation_domain)
    with pytest.raises(RuntimeError, match=CODE_C):
        task.ingest_stock_limit_prices(
            duckdb_path=database, start_date=DAY, client=client,
            require_observation_coverage=True, run_id="synthetic-domain-growth",
        )
    assert snapshot(database) == before
    assert events["writes"] == events["schemas"] == []
    assert events["locks"] == [
        task.resolve_duckdb_writer_lock(database).key,
        task.resolve_duckdb_writer_lock(database).key,
        task.STOCK_LIMIT_PRICE_LOCK.key,
    ]


def test_daily_extra_code_scope_and_source_hash_are_preserved(task, database):
    result, _ = run(task, database, {DAY: [row(code=CODE_C), row(code=CODE_B), row()]},
                    require_observation_coverage=True)
    stored = [item for item in snapshot(database) if item[0] == DAY]
    assert [item[1] for item in stored] == [CODE_A, CODE_B]
    assert result["status"] == "completed"
    assert result["inserted_row_count"] == result["required_code_count"] == 2
    assert result["required_cells_covered"] is True
    assert result["write_scope"] == task.DAILY_WRITE_SCOPE
    assert result["date_results"][0]["vendor_valid_row_count"] == 3
    assert result["date_results"][0]["extra_code_count"] == 1
    normalized = [
        {"trade_date": DAY, "stock_code": code, "up_limit": 11.0, "down_limit": 9.0, "pre_close": 10.0}
        for code in (CODE_A, CODE_B)
    ]
    assert {item[5] for item in stored} == {task._source_version(normalized)}


def test_real_writer_rolls_back_first_date_when_second_insert_fails(task, database, monkeypatch):
    before = snapshot(database)
    original_writer = task._replace_rows_by_date
    events = []

    class FailingConnection:
        def __init__(self, conn):
            self.conn = conn
            self.inserts = 0

        def execute(self, statement, *args, **kwargs):
            events.append(statement.split()[0].lower())
            return self.conn.execute(statement, *args, **kwargs)

        def executemany(self, statement, parameters):
            self.inserts += 1
            if self.inserts == 2:
                events.append("injected-duckdb-error")
                return self.conn.execute("select cast('synthetic-write-failure' as integer)")
            result = self.conn.executemany(statement, parameters)
            events.append("inserted-first-date")
            return result

    def failing_writer(conn, *args, **kwargs):
        return original_writer(FailingConnection(conn), *args, **kwargs)

    monkeypatch.setattr(task, "_replace_rows_by_date", failing_writer)
    with pytest.raises(duckdb.ConversionException, match="synthetic-write-failure"):
        run(task, database, {DAY: [row()], NEXT_DAY: [row(day=NEXT_DAY)]}, end_date=NEXT_DAY)
    assert events == ["begin", "delete", "inserted-first-date", "delete", "injected-duckdb-error", "rollback"]
    assert snapshot(database) == before


@pytest.mark.parametrize("daily", [False, True], ids=["backfill", "daily"])
def test_dry_run_never_constructs_client_calls_supplier_or_writes(task, database, monkeypatch, daily):
    before = snapshot(database)
    events = observe_write_boundaries(task, monkeypatch)
    result = task.ingest_stock_limit_prices(
        duckdb_path=database, start_date=DAY, dry_run=True, require_observation_coverage=daily,
    )
    assert result["status"] == "dry_run"
    assert result["existing_row_count_in_range"] == 2
    assert snapshot(database) == before
    assert events["writes"] == events["schemas"] == []
    inert = InertClient({"20260929": [row()]})
    second = task.ingest_stock_limit_prices(
        duckdb_path=database, start_date=DAY, client=inert,
        dry_run=True, require_observation_coverage=daily,
    )
    assert second == result and inert.calls == []
    assert snapshot(database) == before


def test_single_day_wrapper_keeps_strict_coverage(task, database):
    wrapper = importlib.import_module("backend.app.tasks.stock_limit_price_daily_refresh")
    before = snapshot(database)
    client = InertClient({"20260929": [row()]})
    with pytest.raises(RuntimeError, match="missing required stock limit prices"):
        wrapper.refresh_stock_limit_prices_for_trade_date(
            duckdb_path=database, trade_date=DAY, dry_run=False, client=client, run_id="synthetic-wrapper-missing",
        )
    assert snapshot(database) == before
    assert len(client.calls) == 1


def test_single_day_wrapper_executes_real_guarded_write(task, database):
    wrapper = importlib.import_module("backend.app.tasks.stock_limit_price_daily_refresh")
    client = InertClient({"20260929": [row(), row(code=CODE_B), row(code=CODE_C)]})
    result = wrapper.refresh_stock_limit_prices_for_trade_date(
        duckdb_path=database, trade_date=DAY, dry_run=False, client=client, run_id="synthetic-wrapper-write",
    )
    assert result["status"] == "completed" and result["inserted_row_count"] == 2
    assert result["write_scope"] == task.DAILY_WRITE_SCOPE and result["required_cells_covered"] is True
    assert [item[1] for item in snapshot(database) if item[0] == DAY] == [CODE_A, CODE_B]


def test_single_day_wrapper_remains_dry_run_by_default(task, database):
    wrapper = importlib.import_module("backend.app.tasks.stock_limit_price_daily_refresh")
    before = snapshot(database)
    client = InertClient({"20260929": [row()]})
    result = wrapper.refresh_stock_limit_prices_for_trade_date(
        duckdb_path=database, trade_date=DAY, client=client, run_id="synthetic-wrapper-dry",
    )
    assert result["status"] == "dry_run" and result["required_code_count"] == 2
    assert snapshot(database) == before and client.calls == []
