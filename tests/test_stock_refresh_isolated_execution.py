from __future__ import annotations

import builtins
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import _duckdb
import _pytest_duckdb_guard as pytest_duckdb_guard
import duckdb
import pandas as pd
import pytest
import requests

from backend.app.services import macro_toolkit_service
from backend.app.tasks import choice_stock_materialize
from backend.app.tasks.choice_stock_refresh import run_choice_stock_refresh
from scripts.choice_stock_daily_refresh import _parser as _choice_stock_daily_parser

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_market_data,
]

_REPORT_DATE = "2026-09-15"
_OUTSIDE_DATE = "2026-09-12"
_RUN_ID = "choice_stock_refresh:2026-09-15:isolated-boundary"


class _WriteBoundaryViolation(AssertionError):
    pass


class _ForbiddenDownstreamCall(BaseException):
    pass


class _UnexpectedHttpRequest(BaseException):
    pass


class _FakeChoiceStockClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], str]] = []

    def sector(self, *args: object, options: str = "") -> object:
        self.calls.append(("sector", args, options))
        return SimpleNamespace(
            ErrorCode=0,
            Indicators=["SECUCODE", "SECURITYSHORTNAME"],
            Data={"001004": [{"SECUCODE": "000001.SZ", "SECURITYSHORTNAME": "PAB"}]},
        )

    def css(self, *args: object, options: str = "") -> object:
        self.calls.append(("css", args, options))
        indicators = str(args[1]).split(",")
        if "SW2021" in indicators:
            values: list[object] = ["Bank", "801780"]
        else:
            values = ["0", "0", 0, 0]
        return SimpleNamespace(
            ErrorCode=0,
            Indicators=indicators,
            Data={"000001.SZ": values},
        )

    def csd(self, *args: object, options: str = "") -> object:
        self.calls.append(("csd", args, options))
        indicators = str(args[1]).split(",")
        values_by_indicator: dict[str, list[object]] = {
            "OPEN": [10.0],
            "HIGH": [11.0],
            "LOW": [9.5],
            "CLOSE": [10.5],
            "VOLUME": [1000.0],
            "AMOUNT": [10500.0],
            "PCTCHANGE": [1.2],
            "TURN": [0.8],
            "AMPLITUDE": [2.1],
            "TRADESTATUS": ["Trading"],
            "HIGHLIMIT": ["N"],
            "LOWLIMIT": ["N"],
        }
        return SimpleNamespace(
            ErrorCode=0,
            Indicators=indicators,
            Dates=[_REPORT_DATE],
            Data={
                "000001.SZ": [values_by_indicator[indicator] for indicator in indicators]
            },
        )


class _GapRepairChoiceStockClient(_FakeChoiceStockClient):
    def csd(self, *args: object, options: str = "") -> object:
        self.calls.append(("csd", args, options))
        raise _ForbiddenDownstreamCall("choice_csd_in_gap_repair")


class _FakeTushareGapRepairClient:
    def __init__(self, *, fail_daily_basic: bool = False) -> None:
        self.fail_daily_basic = fail_daily_basic
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def _request(
        self,
        api_name: str,
        *,
        fields: str = "",
        **kwargs: object,
    ) -> pd.DataFrame:
        self.calls.append((api_name, fields, dict(kwargs)))
        if api_name == "trade_cal":
            return pd.DataFrame([{"cal_date": "20260915", "is_open": "1"}])
        if api_name == "daily":
            return pd.DataFrame(
                [
                    {
                        "ts_code": "000001.SZ",
                        "trade_date": "20260915",
                        "open": 12.0,
                        "high": 13.0,
                        "low": 11.5,
                        "close": 12.5,
                        "pre_close": 11.8,
                        "vol": 2000.0,
                        "amount": 25000.0,
                        "pct_chg": 5.9,
                    }
                ]
            )
        if api_name == "daily_basic":
            if self.fail_daily_basic:
                raise requests.ConnectionError("synthetic daily_basic transport failure")
            return pd.DataFrame(
                [
                    {
                        "ts_code": "000001.SZ",
                        "trade_date": "20260915",
                        "turnover_rate": 1.1,
                        "turnover_rate_f": 1.2,
                    }
                ]
            )
        if api_name == "stk_limit":
            return pd.DataFrame(
                [
                    {
                        "ts_code": "000001.SZ",
                        "trade_date": "20260915",
                        "up_limit": 13.75,
                        "down_limit": 11.25,
                    }
                ]
            )
        raise AssertionError(f"Unexpected synthetic Tushare operation: {api_name}")

    def trade_cal(self, **kwargs: object) -> pd.DataFrame:
        return self._request("trade_cal", **kwargs)

    def daily(self, **kwargs: object) -> pd.DataFrame:
        return self._request("daily", **kwargs)

    def daily_basic(self, **kwargs: object) -> pd.DataFrame:
        return self._request("daily_basic", **kwargs)

    def stk_limit(self, **kwargs: object) -> pd.DataFrame:
        return self._request("stk_limit", **kwargs)


def _write_catalog(path: Path) -> None:
    fields = [
        ("stock_universe", "a_share_universe_sector_001004", "001004", "sector", {}),
        (
            "sector_membership",
            "sw2021_industry_membership",
            "SW2021,SW2021CODE",
            "css",
            {"EndDate": "__AS_OF_DATE__", "ClassiFication": 1},
        ),
        (
            "sector_strength",
            "daily_return_turnover_amplitude",
            "PCTCHANGE,TURN,AMPLITUDE",
            "csd",
            {"RowIndex": 1, "period": 1},
        ),
        (
            "stock_ohlcv",
            "daily_ohlcv_amount",
            "OPEN,HIGH,LOW,CLOSE,VOLUME,AMOUNT",
            "csd",
            {"RowIndex": 1, "period": 1},
        ),
        (
            "stock_status",
            "daily_trade_status",
            "TRADESTATUS",
            "csd",
            {"RowIndex": 1, "period": 1},
        ),
        (
            "limit_up_quality",
            "daily_limit_flags",
            "HIGHLIMIT,LOWLIMIT",
            "csd",
            {"RowIndex": 1, "period": 1},
        ),
        (
            "limit_up_quality",
            "point_in_time_limit_streaks",
            "ISSURGEDLIMIT,ISDECLINELIMIT,HLIMITEDAYS,LLIMITEDDAYS",
            "css",
            {"TradeDate": "__AS_OF_DATE__"},
        ),
    ]
    path.write_text(
        json.dumps(
            {
                "catalog_version": "isolated_stock_history_boundary_v1",
                "vendor_name": "choice",
                "generated_from": "synthetic_test",
                "fields": [
                    {
                        "input_family": family,
                        "field_key": field_key,
                        "vendor_indicator": indicator,
                        "call": call,
                        "request_options": {**options, "Ispandas": 0},
                        "confirmed": True,
                        "confirmation_source": "isolated synthetic fixture",
                        "confirmed_at": _REPORT_DATE,
                    }
                    for family, field_key, indicator, call, options in fields
                ],
            }
        ),
        encoding="utf-8",
    )


def _canonical(path: os.PathLike[str] | str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    return candidate.resolve(strict=False)


def _is_write_mode(mode: str) -> bool:
    return any(flag in mode for flag in ("w", "a", "x", "+"))


@contextmanager
def _owned_storage_boundary(
    monkeypatch: pytest.MonkeyPatch,
    *,
    owned_root: Path,
    allowed_database: Path,
) -> Iterator[tuple[list[tuple[Path, bool]], list[str]]]:
    root = _canonical(owned_root)
    database = _canonical(allowed_database)
    technical_receipt = root / "pytest-duckdb-guard-attempts.jsonl"
    database_opens: list[tuple[Path, bool]] = []
    boundary_denials: list[str] = []

    def require_owned(path: os.PathLike[str] | str) -> Path:
        resolved = _canonical(path)
        if not resolved.is_relative_to(root):
            boundary_denials.append("foreign_write")
            raise _WriteBoundaryViolation("write target is outside the test-owned root")
        return resolved

    original_builtin_open = builtins.open
    original_path_open = Path.open
    original_path_mkdir = Path.mkdir
    original_os_open = os.open
    original_os_replace = os.replace
    original_os_rename = os.rename
    original_duckdb_connect = duckdb.connect
    original_native_connect = _duckdb.connect

    def guarded_builtin_open(file: object, mode: str = "r", *args: object, **kwargs: object):
        if _is_write_mode(mode) and isinstance(file, (str, os.PathLike)):
            require_owned(file)
        return original_builtin_open(file, mode, *args, **kwargs)

    def guarded_path_open(
        path: Path,
        mode: str = "r",
        *args: object,
        **kwargs: object,
    ):
        if _is_write_mode(mode):
            require_owned(path)
        return original_path_open(path, mode, *args, **kwargs)

    def guarded_mkdir(path: Path, *args: object, **kwargs: object) -> None:
        require_owned(path)
        original_path_mkdir(path, *args, **kwargs)

    def guarded_os_open(path: object, flags: int, *args: object, **kwargs: object) -> int:
        write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
        if flags & write_flags and isinstance(path, (str, os.PathLike)):
            require_owned(path)
        return original_os_open(path, flags, *args, **kwargs)

    def guarded_replace(
        source: os.PathLike[str] | str,
        destination: os.PathLike[str] | str,
        *args: object,
        **kwargs: object,
    ) -> None:
        require_owned(source)
        require_owned(destination)
        original_os_replace(source, destination, *args, **kwargs)

    def guarded_rename(
        source: os.PathLike[str] | str,
        destination: os.PathLike[str] | str,
        *args: object,
        **kwargs: object,
    ) -> None:
        require_owned(source)
        require_owned(destination)
        original_os_rename(source, destination, *args, **kwargs)

    def guarded_connect(database_path: object = ":memory:", *args: object, **kwargs: object):
        read_only = bool(kwargs.get("read_only", False))
        resolved = _canonical(str(database_path))
        database_opens.append((resolved, read_only))
        if resolved != database:
            boundary_denials.append("foreign_duckdb")
            raise _WriteBoundaryViolation("DuckDB target is not the exact test-owned database")
        return original_duckdb_connect(str(resolved), *args, **kwargs)

    def guarded_native_connect(database_path: object = ":memory:", *args: object, **kwargs: object):
        read_only = bool(kwargs.get("read_only", False))
        resolved = _canonical(str(database_path))
        database_opens.append((resolved, read_only))
        if resolved != database:
            boundary_denials.append("foreign_native_duckdb")
            raise _WriteBoundaryViolation("native DuckDB target is not test-owned")
        return original_native_connect(str(resolved), *args, **kwargs)

    with monkeypatch.context() as boundary:
        # Keep audit persistence inside the same boundary without changing admission.
        # Restoring the global cursor leaves these attempts pending in its receipt.
        boundary.setattr(pytest_duckdb_guard._GUARD, "_receipt_path", technical_receipt)
        boundary.setattr(pytest_duckdb_guard._GUARD, "_persisted_attempt_count", 0)
        boundary.setattr(builtins, "open", guarded_builtin_open)
        boundary.setattr(Path, "open", guarded_path_open)
        boundary.setattr(Path, "mkdir", guarded_mkdir)
        boundary.setattr(os, "open", guarded_os_open)
        boundary.setattr(os, "replace", guarded_replace)
        boundary.setattr(os, "rename", guarded_rename)
        boundary.setattr(duckdb, "connect", guarded_connect)
        boundary.setattr(_duckdb, "connect", guarded_native_connect)
        yield database_opens, boundary_denials


@pytest.mark.parametrize(
    "synthetic_failure",
    [False, True],
    ids=["normal-exit", "synthetic-exception-exit"],
)
def test_owned_storage_boundary_scopes_guard_receipt_and_restores_global_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_failure: bool,
) -> None:
    from contextlib import nullcontext

    class _SyntheticBoundaryExit(Exception):
        pass

    owned_root = tmp_path / "owned"
    owned_root.mkdir()
    database = owned_root / "isolated.duckdb"
    outer_receipt = tmp_path / "outer" / "pytest-duckdb-guard-attempts.jsonl"
    outer_receipt.parent.mkdir()
    guard = pytest_duckdb_guard._GUARD
    allowed_roots = tuple(guard.allowed_roots)
    protected_paths = guard.protected_paths
    original_receipt = guard._receipt_path
    original_cursor = guard._persisted_attempt_count
    original_write_hooks = (
        builtins.open,
        Path.open,
        Path.mkdir,
        os.open,
        os.replace,
        os.rename,
        duckdb.connect,
        _duckdb.connect,
    )

    with monkeypatch.context() as receipt_config:
        receipt_config.setattr(guard, "_receipt_path", outer_receipt)
        receipt_config.setattr(guard, "_persisted_attempt_count", 0)
        with duckdb.connect(":memory:") as connection:
            assert connection.execute("select 1").fetchone() == (1,)
        initial_records = list(pytest_duckdb_guard.get_pytest_duckdb_guard_attempts())
        initial_cursor = guard._persisted_attempt_count
        assert initial_cursor == len(initial_records) > 0
        assert initial_records[-1]["canonical_path"] == ":memory:"
        assert initial_records[-1]["decision"] == "allow"
        initial_receipt_bytes = outer_receipt.read_bytes()
        assert [
            json.loads(line) for line in initial_receipt_bytes.decode("utf-8").splitlines()
        ] == initial_records

        expected_exit = (
            pytest.raises(_SyntheticBoundaryExit, match="synthetic owned-storage boundary exit")
            if synthetic_failure
            else nullcontext()
        )
        with expected_exit:
            with _owned_storage_boundary(
                monkeypatch,
                owned_root=owned_root,
                allowed_database=database,
            ) as (database_opens, boundary_denials):
                with duckdb.connect(os.fspath(database), read_only=False) as connection:
                    assert connection.execute("select 1").fetchone() == (1,)
                local_receipt = owned_root / "pytest-duckdb-guard-attempts.jsonl"
                local_records = [
                    json.loads(line)
                    for line in local_receipt.read_text(encoding="utf-8").splitlines()
                ]
                assert local_records == list(pytest_duckdb_guard.get_pytest_duckdb_guard_attempts())
                assert len(local_records) == initial_cursor + 1
                assert local_records[-1]["canonical_path"] == os.fspath(_canonical(database))
                assert local_records[-1]["decision"] == "allow"
                if synthetic_failure:
                    raise _SyntheticBoundaryExit("synthetic owned-storage boundary exit")

        assert guard._receipt_path == outer_receipt
        assert guard._persisted_attempt_count == initial_cursor
        assert tuple(guard.allowed_roots) == allowed_roots
        assert guard.protected_paths == protected_paths
        assert (
            builtins.open,
            Path.open,
            Path.mkdir,
            os.open,
            os.replace,
            os.rename,
            duckdb.connect,
            _duckdb.connect,
        ) == original_write_hooks
        assert database_opens == [(_canonical(database), False)]
        assert boundary_denials == []
        assert outer_receipt.read_bytes() == initial_receipt_bytes
        assert pytest_duckdb_guard.get_pytest_duckdb_guard_receipt_path() == outer_receipt
        global_records = [
            json.loads(line)
            for line in outer_receipt.read_text(encoding="utf-8").splitlines()
        ]
        assert global_records == list(pytest_duckdb_guard.get_pytest_duckdb_guard_attempts())
        assert global_records == local_records
        assert global_records[:initial_cursor] == initial_records
        assert guard._persisted_attempt_count == len(global_records)
        appended_receipt_bytes = outer_receipt.read_bytes()
        assert appended_receipt_bytes.startswith(initial_receipt_bytes)
        assert pytest_duckdb_guard.get_pytest_duckdb_guard_receipt_path() == outer_receipt
        assert outer_receipt.read_bytes() == appended_receipt_bytes

    assert guard._receipt_path == original_receipt
    assert guard._persisted_attempt_count == original_cursor


def _install_supplier_and_downstream_sentinels(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[_FakeChoiceStockClient, list[str]]:
    client = _FakeChoiceStockClient()
    forbidden_calls: list[str] = []
    monkeypatch.setattr(choice_stock_materialize, "_DefaultChoiceStockClient", lambda: client)

    def forbidden(name: str):
        def fail(*_args: object, **_kwargs: object) -> None:
            forbidden_calls.append(name)
            raise _ForbiddenDownstreamCall(name)

        return fail

    monkeypatch.setattr(
        choice_stock_materialize,
        "_DefaultTushareStockClient",
        forbidden("tushare_client"),
    )
    monkeypatch.setattr(
        choice_stock_materialize,
        "get_runtime_cache",
        forbidden("runtime_cache"),
    )
    for name in (
        "materialize_choice_stock_factor_snapshot",
        "run_livermore_daily_pretrade_refresh",
        "refresh_choice_stock_theme_overlay",
        "publish_choice_stock_observation_manifest",
    ):
        monkeypatch.setattr(macro_toolkit_service, name, forbidden(name))
    return client, forbidden_calls


def _install_gap_repair_suppliers_and_downstream_sentinels(
    monkeypatch: pytest.MonkeyPatch,
    *,
    fail_daily_basic: bool = False,
) -> tuple[
    _GapRepairChoiceStockClient,
    _FakeTushareGapRepairClient,
    list[str],
    list[dict[str, object]],
    list[str],
]:
    _unused_client, forbidden_calls = _install_supplier_and_downstream_sentinels(
        monkeypatch
    )
    choice_client = _GapRepairChoiceStockClient()
    tushare_client = _FakeTushareGapRepairClient(
        fail_daily_basic=fail_daily_basic
    )
    monkeypatch.setattr(
        choice_stock_materialize,
        "_DefaultChoiceStockClient",
        lambda: choice_client,
    )
    monkeypatch.setattr(
        choice_stock_materialize,
        "_DefaultTushareStockClient",
        lambda: tushare_client,
    )
    materialize_observations: list[dict[str, object]] = []
    http_requests: list[str] = []
    actual_materialize = macro_toolkit_service.materialize_choice_stock_inputs

    def forbid_http_request(
        _session: requests.Session,
        method: str | None = None,
        url: str | None = None,
        *_args: object,
        **_kwargs: object,
    ) -> object:
        del method, url
        http_requests.append("requests.Session.request")
        raise _UnexpectedHttpRequest("Synthetic gap-repair test forbids native HTTP")

    monkeypatch.setattr(requests.Session, "request", forbid_http_request)

    def observe_materialize(
        *args: object,
        **kwargs: object,
    ) -> object:
        observation: dict[str, object] = {"kwargs": dict(kwargs)}
        materialize_observations.append(observation)
        result = actual_materialize(*args, **kwargs)
        if not isinstance(result, dict):
            raise AssertionError("Actual stock materializer returned a non-object payload")
        observation["result"] = dict(result)
        return result

    monkeypatch.setattr(
        macro_toolkit_service,
        "materialize_choice_stock_inputs",
        observe_materialize,
    )
    return (
        choice_client,
        tushare_client,
        forbidden_calls,
        materialize_observations,
        http_requests,
    )


def _seed_gap_repair_business_rows(duckdb_path: Path) -> None:
    conn = duckdb.connect(os.fspath(duckdb_path), read_only=False)
    try:
        choice_stock_materialize.ensure_choice_stock_schema(conn)
        choice_stock_materialize._insert_daily_observations(
            conn,
            rows=[
                {
                    "trade_date": trade_date,
                    "stock_code": "000001.SZ",
                    "open_value": 1.0,
                    "high_value": 2.0,
                    "low_value": 0.5,
                    "close_value": close_value,
                    "volume": 10.0,
                    "amount": 15.0,
                }
                for trade_date, close_value in (
                    (_OUTSIDE_DATE, 1.25),
                    (_REPORT_DATE, 1.5),
                )
            ],
            run_id="synthetic-tushare-seed",
            source_version="synthetic_tushare_seed_source",
            vendor_version="synthetic_tushare_seed_vendor",
        )
    finally:
        conn.close()


_BUSINESS_FACT_TABLES = (
    "choice_stock_universe",
    "choice_stock_sector_membership",
    "choice_stock_daily_observation",
    "choice_stock_limit_quality",
    "choice_stock_concept_membership",
    "choice_stock_intraday_movement_event",
)


def _business_fact_snapshot(
    conn: duckdb.DuckDBPyConnection,
) -> dict[str, list[tuple[object, ...]]]:
    return {
        table: conn.execute(f"select * from {table} order by all").fetchall()
        for table in _BUSINESS_FACT_TABLES
    }


def _gap_repair_cli_args() -> object:
    return _choice_stock_daily_parser().parse_args(
        [
            "--run-once",
            "--as-of-date",
            _REPORT_DATE,
            "--tushare-gap-repair",
            "--history-start-date",
            _REPORT_DATE,
        ]
    )


def _run_gap_repair_history_segment(
    *,
    duckdb_path: Path,
    catalog_path: Path,
    governance_path: Path,
    archive_root: Path,
    run_id: str,
) -> None:
    args = _gap_repair_cli_args()
    assert getattr(args, "tushare_gap_repair") is True
    assert getattr(args, "history_start_date") == _REPORT_DATE
    run_choice_stock_refresh(
        duckdb_path=os.fspath(duckdb_path),
        catalog_path=os.fspath(catalog_path),
        governance_path=os.fspath(governance_path),
        archive_root=os.fspath(archive_root),
        run_id=run_id,
        as_of_date=str(getattr(args, "as_of_date")),
        queued_at=datetime(2026, 9, 15, tzinfo=UTC).isoformat(),
        refresh_history=True,
        refresh_factors=False,
        factor_max_stock_count=None,
        theme_overlay_mode="off",
        permission={"scope": "isolated_synthetic_gap_repair"},
        complete_livermore_chain=False,
        retry_managed_by_broker=False,
        history_start_date=str(getattr(args, "history_start_date")),
        allow_cross_era_backfill=bool(getattr(args, "tushare_gap_repair")),
    )


def _run_history_segment(
    *,
    duckdb_path: Path,
    catalog_path: Path,
    governance_path: Path,
    archive_root: Path,
) -> None:
    run_choice_stock_refresh(
        duckdb_path=os.fspath(duckdb_path),
        catalog_path=os.fspath(catalog_path),
        governance_path=os.fspath(governance_path),
        archive_root=os.fspath(archive_root),
        run_id=_RUN_ID,
        as_of_date=_REPORT_DATE,
        queued_at=datetime(2026, 9, 15, tzinfo=UTC).isoformat(),
        refresh_history=True,
        refresh_factors=False,
        factor_max_stock_count=None,
        theme_overlay_mode="off",
        permission={"scope": "isolated_synthetic_history_segment"},
        complete_livermore_chain=False,
        retry_managed_by_broker=False,
        history_start_date=_REPORT_DATE,
        allow_cross_era_backfill=False,
    )


def test_choice_stock_history_segment_pins_date_and_all_writes_to_owned_storage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog_path = tmp_path / "choice_stock_catalog.json"
    duckdb_path = tmp_path / "isolated.duckdb"
    governance_path = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    _write_catalog(catalog_path)
    client, forbidden_calls = _install_supplier_and_downstream_sentinels(monkeypatch)

    with _owned_storage_boundary(
        monkeypatch,
        owned_root=tmp_path,
        allowed_database=duckdb_path,
    ) as (database_opens, boundary_denials):
        _run_history_segment(
            duckdb_path=duckdb_path,
            catalog_path=catalog_path,
            governance_path=governance_path,
            archive_root=archive_root,
        )

        conn = duckdb.connect(os.fspath(duckdb_path), read_only=True)
        try:
            facts = conn.execute(
                """
                select stock_code, cast(trade_date as varchar), close_value, tradestatus
                from choice_stock_daily_observation
                order by stock_code
                """
            ).fetchall()
            table_counts = {
                table: int(conn.execute(f"select count(*) from {table}").fetchone()[0])
                for table in (
                    "choice_stock_materialize_run",
                    "choice_stock_request_audit",
                    "choice_stock_universe",
                    "choice_stock_sector_membership",
                    "choice_stock_daily_observation",
                    "choice_stock_limit_quality",
                )
            }
        finally:
            conn.close()

        terminal = macro_toolkit_service.choice_stock_refresh_status(
            os.fspath(governance_path)
        )
        run_records = [
            json.loads(line)
            for line in (governance_path / "cache_build_run.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        completed_record = run_records[-1]

    assert client.calls[0][0] == "sector"
    sector_calls = [call for call in client.calls if call[0] == "sector"]
    assert len(sector_calls) == 1
    assert sector_calls[0][1] == ("001004", _REPORT_DATE)
    membership_css_calls = [
        call
        for call in client.calls
        if call[0] == "css" and "SW2021" in str(call[1][1])
    ]
    assert len(membership_css_calls) == 1
    assert f"EndDate={_REPORT_DATE}" in membership_css_calls[0][2]
    limit_css_calls = [
        call
        for call in client.calls
        if call[0] == "css" and "HLIMITEDAYS" in str(call[1][1])
    ]
    assert len(limit_css_calls) == 1
    assert f"TradeDate={_REPORT_DATE}" in limit_css_calls[0][2]
    assert all(
        call[0] != "csd" or call[1][2:] == (_REPORT_DATE, _REPORT_DATE)
        for call in client.calls
    )
    assert facts == [("000001.SZ", _REPORT_DATE, 10.5, "Trading")]
    assert table_counts == {
        "choice_stock_materialize_run": 1,
        "choice_stock_request_audit": 7,
        "choice_stock_universe": 1,
        "choice_stock_sector_membership": 1,
        "choice_stock_daily_observation": 1,
        "choice_stock_limit_quality": 1,
    }
    assert terminal["status"] == "completed"
    assert terminal["run_id"] == _RUN_ID
    assert terminal["report_date"] == _REPORT_DATE
    assert terminal["refresh_history"] is True
    assert terminal["refresh_factors"] is False
    assert [record["status"] for record in run_records] == ["running", "completed"]
    assert completed_record["run_id"] == _RUN_ID
    assert completed_record["report_date"] == _REPORT_DATE
    assert completed_record["history_start_date"] == _REPORT_DATE
    assert completed_record["history_row_count"] == 4
    assert governance_path.exists()
    assert any(path.is_file() for path in governance_path.rglob("*"))
    assert not archive_root.exists()
    assert database_opens
    assert {path for path, _read_only in database_opens} == {_canonical(duckdb_path)}
    assert forbidden_calls == []
    assert boundary_denials == []


def test_foreign_governance_output_is_rejected_before_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog_path = tmp_path / "choice_stock_catalog.json"
    duckdb_path = tmp_path / "isolated.duckdb"
    foreign_governance = tmp_path.parent / "foreign-governance"
    _write_catalog(catalog_path)
    _client, forbidden_calls = _install_supplier_and_downstream_sentinels(monkeypatch)

    with _owned_storage_boundary(
        monkeypatch,
        owned_root=tmp_path,
        allowed_database=duckdb_path,
    ) as (database_opens, boundary_denials):
        with pytest.raises(_WriteBoundaryViolation):
            _run_history_segment(
                duckdb_path=duckdb_path,
                catalog_path=catalog_path,
                governance_path=foreign_governance,
                archive_root=tmp_path / "archive",
            )

    assert database_opens == []
    assert boundary_denials
    assert set(boundary_denials) == {"foreign_write"}
    assert forbidden_calls == []
    assert not foreign_governance.exists()
    assert not duckdb_path.exists()


def test_non_exact_duckdb_target_is_rejected_before_native_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog_path = tmp_path / "choice_stock_catalog.json"
    allowed_database = tmp_path / "isolated.duckdb"
    foreign_database = tmp_path / "other.duckdb"
    _write_catalog(catalog_path)
    client, forbidden_calls = _install_supplier_and_downstream_sentinels(monkeypatch)

    with _owned_storage_boundary(
        monkeypatch,
        owned_root=tmp_path,
        allowed_database=allowed_database,
    ) as (database_opens, boundary_denials):
        with pytest.raises(_WriteBoundaryViolation):
            choice_stock_materialize.materialize_choice_stock_inputs(
                as_of_date=_REPORT_DATE,
                duckdb_path=os.fspath(foreign_database),
                catalog_path=os.fspath(catalog_path),
                client=client,
                history_start_date=_REPORT_DATE,
            )

    assert database_opens == [(_canonical(foreign_database), False)]
    assert boundary_denials == ["foreign_duckdb"]
    assert forbidden_calls == []
    assert not foreign_database.exists()
    assert not allowed_database.exists()


def test_tushare_gap_repair_replaces_exact_day_and_preserves_outside_fact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog_path = tmp_path / "choice_stock_catalog.json"
    duckdb_path = tmp_path / "isolated.duckdb"
    governance_path = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    run_id = f"{_RUN_ID}:gap-repair-success"
    _write_catalog(catalog_path)
    (
        choice_client,
        tushare_client,
        forbidden_calls,
        materialize_observations,
        http_requests,
    ) = _install_gap_repair_suppliers_and_downstream_sentinels(monkeypatch)

    with _owned_storage_boundary(
        monkeypatch,
        owned_root=tmp_path,
        allowed_database=duckdb_path,
    ) as (database_opens, boundary_denials):
        _seed_gap_repair_business_rows(duckdb_path)
        conn = duckdb.connect(os.fspath(duckdb_path), read_only=True)
        try:
            outside_before = conn.execute(
                "select * from choice_stock_daily_observation where trade_date = ?",
                [_OUTSIDE_DATE],
            ).fetchall()
        finally:
            conn.close()

        _run_gap_repair_history_segment(
            duckdb_path=duckdb_path,
            catalog_path=catalog_path,
            governance_path=governance_path,
            archive_root=archive_root,
            run_id=run_id,
        )

        conn = duckdb.connect(os.fspath(duckdb_path), read_only=True)
        try:
            target_rows = conn.execute(
                """
                select cast(trade_date as varchar), stock_code, open_value, high_value,
                       low_value, close_value, turn, tradestatus
                from choice_stock_daily_observation
                where trade_date = ?
                order by stock_code
                """,
                [_REPORT_DATE],
            ).fetchall()
            outside_after = conn.execute(
                "select * from choice_stock_daily_observation where trade_date = ?",
                [_OUTSIDE_DATE],
            ).fetchall()
            materialize_runs = conn.execute(
                """
                select run_id, status, cast(as_of_date as varchar), request_count,
                       row_count
                from choice_stock_materialize_run
                order by completed_at
                """
            ).fetchall()
            assert len(materialize_runs) == 1
            materialize_run_id = str(materialize_runs[0][0])
            request_audits = conn.execute(
                """
                select field_key, status, row_count, run_id
                from choice_stock_request_audit
                where run_id = ?
                order by field_key, status
                """,
                [materialize_run_id],
            ).fetchall()
        finally:
            conn.close()

        governance_records = [
            json.loads(line)
            for line in (governance_path / "cache_build_run.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]

    assert target_rows == [
        (_REPORT_DATE, "000001.SZ", 12.0, 13.0, 11.5, 12.5, 1.2, "Trading")
    ]
    assert outside_before
    assert outside_after == outside_before
    assert materialize_runs == [
        (materialize_run_id, "completed", _REPORT_DATE, 7, 4)
    ]
    assert len(request_audits) == 7
    assert {str(row[3]) for row in request_audits} == {materialize_run_id}
    gap_audits = [
        row[0:3]
        for row in request_audits
        if row[1] == "completed_tushare_gap_repair"
    ]
    assert gap_audits == [
        ("daily_limit_flags", "completed_tushare_gap_repair", 1),
        ("daily_ohlcv_amount", "completed_tushare_gap_repair", 1),
        ("daily_return_turnover_amplitude", "completed_tushare_gap_repair", 1),
        ("daily_trade_status", "completed_tushare_gap_repair", 1),
    ]
    assert [call[0] for call in choice_client.calls] == ["sector", "css", "css"]
    assert tushare_client.calls == [
        (
            "trade_cal",
            "cal_date,is_open",
            {
                "exchange": "SSE",
                "is_open": "1",
                "start_date": "20260915",
                "end_date": "20260915",
            },
        ),
        (
            "daily",
            "ts_code,trade_date,open,high,low,close,pre_close,vol,amount,pct_chg",
            {"trade_date": "20260915"},
        ),
        (
            "daily_basic",
            "ts_code,trade_date,turnover_rate,turnover_rate_f",
            {"trade_date": "20260915"},
        ),
        (
            "stk_limit",
            "ts_code,trade_date,up_limit,down_limit",
            {"trade_date": "20260915"},
        ),
    ]
    assert len(materialize_observations) == 1
    materialize_kwargs = materialize_observations[0]["kwargs"]
    assert isinstance(materialize_kwargs, dict)
    assert materialize_kwargs["history_start_date"] == _REPORT_DATE
    assert materialize_kwargs["allow_cross_era_backfill"] is True
    materialize_result = materialize_observations[0]["result"]
    assert isinstance(materialize_result, dict)
    assert materialize_result["gap_repair_mode"] is True
    assert materialize_result["history_start_date"] == _REPORT_DATE
    assert materialize_result["history_end_date"] == _REPORT_DATE
    assert materialize_result["history_trade_dates"] == [_REPORT_DATE]
    gap_preflight = materialize_result["gap_repair_preflight"]
    assert isinstance(gap_preflight, dict)
    assert gap_preflight["status"] == "passed"
    assert gap_preflight["existing_daily_row_count"] == 1
    assert materialize_result["run_id"] == materialize_run_id
    assert [record["status"] for record in governance_records] == [
        "running",
        "completed",
    ]
    assert {record["run_id"] for record in governance_records} == {run_id}
    assert governance_records[-1]["history_row_count"] == materialize_runs[0][4]
    assert governance_records[-1]["source_version"] == materialize_result["source_version"]
    assert governance_records[-1]["vendor_version"] == materialize_result["vendor_version"]
    assert governance_records[-1]["history_start_date"] == _REPORT_DATE
    assert governance_records[-1]["allow_cross_era_backfill"] is True
    assert len(database_opens) == 6
    assert {path for path, _read_only in database_opens} == {_canonical(duckdb_path)}
    assert http_requests == []
    with pytest.raises(_UnexpectedHttpRequest):
        requests.Session().request(method="GET", url="https://synthetic.invalid")
    assert http_requests == ["requests.Session.request"]
    assert forbidden_calls == []
    assert boundary_denials == []
    assert not archive_root.exists()


def test_tushare_gap_repair_daily_basic_failure_keeps_business_facts_and_receipts_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog_path = tmp_path / "choice_stock_catalog.json"
    duckdb_path = tmp_path / "isolated.duckdb"
    governance_path = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    run_id = f"{_RUN_ID}:gap-repair-daily-basic-failure"
    _write_catalog(catalog_path)
    (
        choice_client,
        tushare_client,
        forbidden_calls,
        materialize_observations,
        http_requests,
    ) = _install_gap_repair_suppliers_and_downstream_sentinels(
        monkeypatch,
        fail_daily_basic=True,
    )
    sleep_delays: list[float] = []
    monkeypatch.setattr(
        choice_stock_materialize.time,
        "sleep",
        lambda seconds: sleep_delays.append(float(seconds)),
    )

    with _owned_storage_boundary(
        monkeypatch,
        owned_root=tmp_path,
        allowed_database=duckdb_path,
    ) as (database_opens, boundary_denials):
        _seed_gap_repair_business_rows(duckdb_path)
        conn = duckdb.connect(os.fspath(duckdb_path), read_only=True)
        try:
            business_before = _business_fact_snapshot(conn)
        finally:
            conn.close()

        with pytest.raises(
            requests.ConnectionError,
            match="synthetic daily_basic transport failure",
        ):
            _run_gap_repair_history_segment(
                duckdb_path=duckdb_path,
                catalog_path=catalog_path,
                governance_path=governance_path,
                archive_root=archive_root,
                run_id=run_id,
            )

        conn = duckdb.connect(os.fspath(duckdb_path), read_only=True)
        try:
            business_after = _business_fact_snapshot(conn)
            failed_materializations = conn.execute(
                """
                select run_id, status, cast(as_of_date as varchar), request_count,
                       row_count, error_message
                from choice_stock_materialize_run
                order by completed_at
                """
            ).fetchall()
            assert len(failed_materializations) == 1
            failed_materialize_run_id = str(failed_materializations[0][0])
            failed_audits = conn.execute(
                """
                select field_key, status, row_count, run_id
                from choice_stock_request_audit
                where run_id = ?
                order by field_key, status
                """,
                [failed_materialize_run_id],
            ).fetchall()
        finally:
            conn.close()

        governance_records = [
            json.loads(line)
            for line in (governance_path / "cache_build_run.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]

    assert business_before["choice_stock_daily_observation"]
    assert business_after == business_before
    assert failed_materializations[0][0:5] == (
        failed_materialize_run_id,
        "failed",
        _REPORT_DATE,
        3,
        0,
    )
    assert "synthetic daily_basic transport failure" in failed_materializations[0][5]
    assert len(failed_audits) == 3
    assert {str(row[3]) for row in failed_audits} == {failed_materialize_run_id}
    assert (
        "a_share_universe_sector_001004",
        "completed",
        1,
        failed_materialize_run_id,
    ) in failed_audits
    assert (
        "sw2021_industry_membership",
        "completed",
        1,
        failed_materialize_run_id,
    ) in failed_audits
    assert (
        "daily_return_turnover_amplitude",
        "failed",
        0,
        failed_materialize_run_id,
    ) in failed_audits
    assert [record["status"] for record in governance_records] == [
        "running",
        "failed",
    ]
    assert {record["run_id"] for record in governance_records} == {run_id}
    assert governance_records[-1]["history_row_count"] is None
    assert governance_records[-1]["source_version"] is None
    assert governance_records[-1]["vendor_version"] is None
    assert governance_records[-1]["failure_category"] == "ConnectionError"
    assert governance_records[-1]["history_start_date"] == _REPORT_DATE
    assert governance_records[-1]["allow_cross_era_backfill"] is True
    assert [call[0] for call in choice_client.calls] == ["sector", "css"]
    expected_daily_basic_call = (
        "daily_basic",
        "ts_code,trade_date,turnover_rate,turnover_rate_f",
        {"trade_date": "20260915"},
    )
    assert tushare_client.calls == [
        (
            "trade_cal",
            "cal_date,is_open",
            {
                "exchange": "SSE",
                "is_open": "1",
                "start_date": "20260915",
                "end_date": "20260915",
            },
        ),
        (
            "daily",
            "ts_code,trade_date,open,high,low,close,pre_close,vol,amount,pct_chg",
            {"trade_date": "20260915"},
        ),
        expected_daily_basic_call,
        expected_daily_basic_call,
        expected_daily_basic_call,
    ]
    assert sleep_delays == [1.0, 1.0]
    assert len(materialize_observations) == 1
    failure_kwargs = materialize_observations[0]["kwargs"]
    assert isinstance(failure_kwargs, dict)
    assert failure_kwargs["history_start_date"] == _REPORT_DATE
    assert failure_kwargs["allow_cross_era_backfill"] is True
    assert "result" not in materialize_observations[0]
    assert len(database_opens) == 5
    assert {path for path, _read_only in database_opens} == {_canonical(duckdb_path)}
    assert http_requests == []
    with pytest.raises(_UnexpectedHttpRequest):
        requests.Session().request(method="GET", url="https://synthetic.invalid")
    assert http_requests == ["requests.Session.request"]
    assert forbidden_calls == []
    assert boundary_denials == []
    assert not archive_root.exists()
