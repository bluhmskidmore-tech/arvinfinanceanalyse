from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from tests.helpers import load_module

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_livermore,
]


class _AdjFactorClient:
    def __init__(self, rows_by_date: dict[str, list[dict[str, object]]]) -> None:
        self.rows_by_date = rows_by_date
        self.calls: list[dict[str, object]] = []

    def adj_factor(self, **kwargs: object) -> list[dict[str, object]]:
        self.calls.append(dict(kwargs))
        return list(self.rows_by_date.get(str(kwargs.get("trade_date")), []))


class _FakeDate(date):
    fixed: date = date(2026, 8, 11)

    @classmethod
    def today(cls) -> date:
        return cls.fixed


def _create_observation_fixture(db_path: Path) -> None:
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              open_value double,
              close_value double
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?)",
            [
                ("2026-08-11", "000001.SZ", 10.0, 10.5),
                ("2026-08-11", "000002.SZ", 8.0, 8.2),
                ("2026-08-11", "000003.SZ", 7.5, 0.0),
                ("2026-08-11", "000004.SZ", 7.0, None),
                ("2026-08-10", "999999.SH", 1.0, 1.0),
            ],
        )
        conn.execute(
            """
            create table stock_adjustment_factor (
              stock_code varchar,
              trade_date varchar,
              adj_factor double,
              source_version varchar,
              run_id varchar
            )
            """
        )
    finally:
        conn.close()


def _load_rows(db_path: Path) -> list[tuple[object, ...]]:
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        return conn.execute(
            """
            select stock_code, trade_date, adj_factor
            from stock_adjustment_factor
            order by trade_date, stock_code
            """
        ).fetchall()
    finally:
        conn.close()


def test_refresh_inserts_missing_required_rows_ignores_extra_vendor_codes_and_is_idempotent(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "moss.duckdb"
    _create_observation_fixture(db_path)
    module = load_module(
        "backend.app.tasks.stock_adjustment_factor_daily_refresh",
        "backend/app/tasks/stock_adjustment_factor_daily_refresh.py",
    )
    client = _AdjFactorClient(
        {
            "20260811": [
                {"ts_code": "000001.SZ", "trade_date": "20260811", "adj_factor": 1.1},
                {"ts_code": "000001.SZ", "trade_date": "20260811", "adj_factor": 1.1},
                {"ts_code": "000002.SZ", "trade_date": "20260811", "adj_factor": 2.2},
                {"ts_code": "000099.SH", "trade_date": "20260811", "adj_factor": 9.9},
            ]
        }
    )

    first = module.refresh_stock_adjustment_factors_for_trade_date(
        duckdb_path=db_path,
        trade_date="2026-08-11",
        tushare_client=client,
    )
    second = module.refresh_stock_adjustment_factors_for_trade_date(
        duckdb_path=db_path,
        trade_date="2026-08-11",
        tushare_client=client,
    )

    assert first["status"] == "completed"
    assert first["required_code_count"] == 2
    assert first["raw_vendor_row_count"] == 4
    assert first["returned_exact_row_count"] == 3
    assert first["vendor_valid_row_count"] == 3
    assert first["scoped_vendor_row_count"] == 2
    assert first["write_scope"] == "positive_close_observation_codes"
    assert first["extra_code_count"] == 1
    assert first["inserted_count"] == 2
    assert first["existing_same_count"] == 0
    assert first["required_cells_covered"] is True
    assert first["vendor_endpoint"] == "tushare.pro.adj_factor"
    assert first["vendor_version"] == "vv_tushare_adj_factor_20260811"
    assert str(first["run_id"]).startswith("stock_adjustment_factor_daily_refresh:2026-08-11:")
    assert second["status"] == "completed"
    assert second["inserted_count"] == 0
    assert second["existing_same_count"] == 2
    assert client.calls == [
        {"trade_date": "20260811", "fields": "ts_code,trade_date,adj_factor"},
        {"trade_date": "20260811", "fields": "ts_code,trade_date,adj_factor"},
    ]
    assert _load_rows(db_path) == [
        ("000001.SZ", "2026-08-11", pytest.approx(1.1)),
        ("000002.SZ", "2026-08-11", pytest.approx(2.2)),
    ]


def test_refresh_rejects_incomplete_required_coverage_without_writing(tmp_path: Path) -> None:
    db_path = tmp_path / "moss.duckdb"
    _create_observation_fixture(db_path)
    original_rows = _load_rows(db_path)
    module = load_module(
        "backend.app.tasks.stock_adjustment_factor_daily_refresh_incomplete",
        "backend/app/tasks/stock_adjustment_factor_daily_refresh.py",
    )

    with pytest.raises(RuntimeError, match="missing required cells"):
        module.refresh_stock_adjustment_factors_for_trade_date(
            duckdb_path=db_path,
            trade_date="2026-08-11",
            tushare_client=_AdjFactorClient(
                {
                    "20260811": [
                        {"ts_code": "000001.SZ", "trade_date": "20260811", "adj_factor": 1.1},
                    ]
                }
            ),
        )

    assert _load_rows(db_path) == original_rows


def test_refresh_rejects_invalid_required_stock_code_without_writing(tmp_path: Path) -> None:
    db_path = tmp_path / "moss.duckdb"
    _create_observation_fixture(db_path)
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute("insert into choice_stock_daily_observation values ('2026-08-11', 'BAD', 1.0, 1.0)")
    finally:
        conn.close()
    original_rows = _load_rows(db_path)
    module = load_module(
        "backend.app.tasks.stock_adjustment_factor_daily_refresh_invalid_required_code",
        "backend/app/tasks/stock_adjustment_factor_daily_refresh.py",
    )

    with pytest.raises(RuntimeError, match="canonical A-share stock code"):
        module.refresh_stock_adjustment_factors_for_trade_date(
            duckdb_path=db_path,
            trade_date="2026-08-11",
            tushare_client=_AdjFactorClient({"20260811": []}),
        )

    assert _load_rows(db_path) == original_rows


def test_refresh_rejects_duplicate_existing_key_without_writing(tmp_path: Path) -> None:
    db_path = tmp_path / "moss.duckdb"
    _create_observation_fixture(db_path)
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.executemany(
            "insert into stock_adjustment_factor values (?, ?, ?, ?, ?)",
            [
                ("000001.SZ", "2026-08-11", 1.1, "sv_old", "run_old"),
                ("000001.SZ", "2026-08-11", 1.1, "sv_old2", "run_old2"),
            ],
        )
    finally:
        conn.close()
    original_rows = _load_rows(db_path)
    module = load_module(
        "backend.app.tasks.stock_adjustment_factor_daily_refresh_duplicate_existing",
        "backend/app/tasks/stock_adjustment_factor_daily_refresh.py",
    )

    with pytest.raises(RuntimeError, match="duplicate natural keys"):
        module.refresh_stock_adjustment_factors_for_trade_date(
            duckdb_path=db_path,
            trade_date="2026-08-11",
            tushare_client=_AdjFactorClient(
                {
                    "20260811": [
                        {"ts_code": "000001.SZ", "trade_date": "20260811", "adj_factor": 1.1},
                        {"ts_code": "000002.SZ", "trade_date": "20260811", "adj_factor": 2.2},
                    ]
                }
            ),
        )

    assert _load_rows(db_path) == original_rows


def test_refresh_rejects_conflicting_existing_value_without_overwrite(tmp_path: Path) -> None:
    db_path = tmp_path / "moss.duckdb"
    _create_observation_fixture(db_path)
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            "insert into stock_adjustment_factor values ('000002.SZ', '2026-08-11', 8.8, 'sv_old', 'run_old')"
        )
    finally:
        conn.close()
    original_rows = _load_rows(db_path)
    module = load_module(
        "backend.app.tasks.stock_adjustment_factor_daily_refresh_conflict",
        "backend/app/tasks/stock_adjustment_factor_daily_refresh.py",
    )

    with pytest.raises(RuntimeError, match="conflicting existing factor"):
        module.refresh_stock_adjustment_factors_for_trade_date(
            duckdb_path=db_path,
            trade_date="2026-08-11",
            tushare_client=_AdjFactorClient(
                {
                    "20260811": [
                        {"ts_code": "000001.SZ", "trade_date": "20260811", "adj_factor": 1.1},
                        {"ts_code": "000002.SZ", "trade_date": "20260811", "adj_factor": 2.2},
                    ]
                }
            ),
        )

    assert _load_rows(db_path) == original_rows


def test_refresh_vendor_fetch_happens_before_global_writer_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "moss.duckdb"
    _create_observation_fixture(db_path)
    module = load_module(
        "backend.app.tasks.stock_adjustment_factor_daily_refresh_lock_order",
        "backend/app/tasks/stock_adjustment_factor_daily_refresh.py",
    )
    lock_state = {"held": False}

    @contextmanager
    def fake_lock(*_args: object, **_kwargs: object):
        assert lock_state["held"] is False
        lock_state["held"] = True
        try:
            yield
        finally:
            lock_state["held"] = False

    class _LockAwareClient:
        def adj_factor(self, **kwargs: object) -> list[dict[str, object]]:
            assert lock_state["held"] is False
            return [
                {"ts_code": "000001.SZ", "trade_date": "20260811", "adj_factor": 1.1},
                {"ts_code": "000002.SZ", "trade_date": "20260811", "adj_factor": 2.2},
            ]

    monkeypatch.setattr(module, "acquire_lock", fake_lock)

    result = module.refresh_stock_adjustment_factors_for_trade_date(
        duckdb_path=db_path,
        trade_date="2026-08-11",
        tushare_client=_LockAwareClient(),
    )

    assert result["status"] == "completed"
    assert _load_rows(db_path) == [
        ("000001.SZ", "2026-08-11", pytest.approx(1.1)),
        ("000002.SZ", "2026-08-11", pytest.approx(2.2)),
    ]


def test_refresh_fails_closed_when_required_codes_expand_inside_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "moss.duckdb"
    _create_observation_fixture(db_path)
    module = load_module(
        "backend.app.tasks.stock_adjustment_factor_daily_refresh_required_race",
        "backend/app/tasks/stock_adjustment_factor_daily_refresh.py",
    )
    original_loader = module._load_required_codes
    call_counter = {"count": 0}

    def fake_load_required_codes(conn: duckdb.DuckDBPyConnection, *, trade_date: str) -> list[str]:
        call_counter["count"] += 1
        current = original_loader(conn, trade_date=trade_date)
        if call_counter["count"] == 1:
            return current
        return [*current, "000005.SZ"]

    monkeypatch.setattr(module, "_load_required_codes", fake_load_required_codes)

    with pytest.raises(RuntimeError, match="missing required cells"):
        module.refresh_stock_adjustment_factors_for_trade_date(
            duckdb_path=db_path,
            trade_date="2026-08-11",
            tushare_client=_AdjFactorClient(
                {
                    "20260811": [
                        {"ts_code": "000001.SZ", "trade_date": "20260811", "adj_factor": 1.1},
                        {"ts_code": "000002.SZ", "trade_date": "20260811", "adj_factor": 2.2},
                    ]
                }
            ),
        )

    assert _load_rows(db_path) == []


@pytest.mark.parametrize(
    ("vendor_rows", "message"),
    [
        (
            [
                {"ts_code": "000001.SZ", "trade_date": "20260810", "adj_factor": 1.1},
                {"ts_code": "000002.SZ", "trade_date": "20260811", "adj_factor": 2.2},
            ],
            "expected 2026-08-11",
        ),
        (
            [
                {"ts_code": "000001.SZ", "trade_date": "20260811", "adj_factor": 0.0},
                {"ts_code": "000002.SZ", "trade_date": "20260811", "adj_factor": 2.2},
            ],
            "positive finite number",
        ),
        (
            [
                {"ts_code": "000001.SZ", "trade_date": "20260811", "adj_factor": "NaN"},
                {"ts_code": "000002.SZ", "trade_date": "20260811", "adj_factor": 2.2},
            ],
            "positive finite number",
        ),
        (
            [
                {"ts_code": "000001.SZ", "trade_date": "20260811", "adj_factor": 1.1},
                {"ts_code": "000001.SZ", "trade_date": "20260811", "adj_factor": 1.2},
                {"ts_code": "000002.SZ", "trade_date": "20260811", "adj_factor": 2.2},
            ],
            "conflicting vendor duplicate",
        ),
        (
            [
                {"ts_code": "BAD", "trade_date": "20260811", "adj_factor": 1.1},
                {"ts_code": "000002.SZ", "trade_date": "20260811", "adj_factor": 2.2},
            ],
            "canonical A-share stock code",
        ),
        (
            [
                {"ts_code": "000099.SH", "trade_date": "20261340", "adj_factor": 9.9},
                {"ts_code": "000001.SZ", "trade_date": "20260811", "adj_factor": 1.1},
                {"ts_code": "000002.SZ", "trade_date": "20260811", "adj_factor": 2.2},
            ],
            "valid YYYY-MM-DD date",
        ),
    ],
    ids=["wrong-date", "nonpositive", "nonfinite", "conflicting-duplicate", "bad-code", "bad-extra-date"],
)
def test_refresh_invalid_vendor_input_writes_nothing(
    tmp_path: Path,
    vendor_rows: list[dict[str, object]],
    message: str,
) -> None:
    db_path = tmp_path / "moss.duckdb"
    _create_observation_fixture(db_path)
    original_rows = _load_rows(db_path)
    module = load_module(
        "backend.app.tasks.stock_adjustment_factor_daily_refresh_invalid_vendor",
        "backend/app/tasks/stock_adjustment_factor_daily_refresh.py",
    )

    with pytest.raises(RuntimeError, match=message):
        module.refresh_stock_adjustment_factors_for_trade_date(
            duckdb_path=db_path,
            trade_date="2026-08-11",
            tushare_client=_AdjFactorClient({"20260811": vendor_rows}),
        )

    assert _load_rows(db_path) == original_rows


def test_cli_run_once_writes_receipt_and_masks_sensitive_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = load_module(
        "scripts.stock_adjustment_factor_daily_refresh",
        "scripts/stock_adjustment_factor_daily_refresh.py",
    )
    receipt_path = tmp_path / "receipt.json"
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "moss.duckdb",
        tushare_token="SECRET-TOKEN",
    )
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(module, "_resolve_commit_sha", lambda: ("test-sha", None))

    def boom(**_kwargs: object) -> dict[str, object]:
        raise RuntimeError("upstream SECRET-TOKEN failure api_key=LEAK")

    monkeypatch.setattr(module, "refresh_stock_adjustment_factors_for_trade_date", boom)

    exit_code = module.main(
        [
            "--run-once",
            "--as-of-date",
            "2026-08-11",
            "--receipt-path",
            str(receipt_path),
        ]
    )

    assert exit_code == 1
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == "failed"
    assert receipt["exit_code"] == 1
    assert receipt["commit_sha"] == "test-sha"
    assert "SECRET-TOKEN" not in json.dumps(receipt, ensure_ascii=False)
    assert "LEAK" not in json.dumps(receipt, ensure_ascii=False)
    assert "***" in str(receipt["result"]["error"])


def test_cli_requires_explicit_mode_even_with_scheduler_style_args(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = load_module(
        "scripts.stock_adjustment_factor_daily_refresh_scheduler_style",
        "scripts/stock_adjustment_factor_daily_refresh.py",
    )
    receipt_path = tmp_path / "receipt.json"
    duckdb_path = tmp_path / "moss.duckdb"
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "default.duckdb",
        tushare_token="",
    )
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(module, "_resolve_commit_sha", lambda: ("test-sha", None))
    monkeypatch.setattr(module, "refresh_stock_adjustment_factors_for_trade_date", lambda **kwargs: calls.append(dict(kwargs)))

    with pytest.raises(SystemExit) as excinfo:
        module.main(
            [
                "--trade-date",
                "2026-08-11",
                "--db-path",
                str(duckdb_path),
                "--run-kind",
                "scheduled",
                "--receipt-path",
                str(receipt_path),
            ]
        )

    assert excinfo.value.code == 2
    assert calls == []
    assert not receipt_path.exists()


def test_cli_forwards_db_path_and_default_weekday_date(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = load_module(
        "scripts.stock_adjustment_factor_daily_refresh_forwarding",
        "scripts/stock_adjustment_factor_daily_refresh.py",
    )
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "settings.duckdb",
        tushare_token="SECRET-TOKEN",
    )
    forwarded: dict[str, object] = {}
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(module, "date", _FakeDate)
    _FakeDate.fixed = date(2026, 8, 11)

    def fake_refresh(**kwargs: object) -> dict[str, object]:
        forwarded.update(kwargs)
        return {"status": "completed", "trade_date": str(kwargs["trade_date"])}

    monkeypatch.setattr(module, "refresh_stock_adjustment_factors_for_trade_date", fake_refresh)

    exit_code = module.main(
        [
            "--run-once",
            "--db-path",
            str(tmp_path / "override.duckdb"),
        ]
    )

    assert exit_code == 0
    assert forwarded == {
        "duckdb_path": str(tmp_path / "override.duckdb"),
        "trade_date": "2026-08-11",
    }


def test_cli_dry_run_validates_db_and_does_not_call_vendor(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = load_module(
        "scripts.stock_adjustment_factor_daily_refresh_dry_run",
        "scripts/stock_adjustment_factor_daily_refresh.py",
    )
    db_path = tmp_path / "moss.duckdb"
    _create_observation_fixture(db_path)
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "settings.duckdb",
        tushare_token="SECRET-TOKEN",
    )
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    calls: list[dict[str, object]] = []

    def fake_refresh(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {
            "status": "dry_run",
            "trade_date": "2026-08-11",
            "required_code_count": 2,
            "would_call_tushare": True,
        }

    monkeypatch.setattr(module, "refresh_stock_adjustment_factors_for_trade_date", fake_refresh)

    exit_code = module.main(["--dry-run", "--db-path", str(db_path), "--as-of-date", "2026-08-11"])

    assert exit_code == 0
    assert calls == [
        {
            "duckdb_path": str(db_path),
            "trade_date": "2026-08-11",
            "dry_run": True,
        }
    ]


def test_cli_default_weekend_date_is_skipped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = load_module(
        "scripts.stock_adjustment_factor_daily_refresh_default_weekend",
        "scripts/stock_adjustment_factor_daily_refresh.py",
    )
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "settings.duckdb",
        tushare_token="SECRET-TOKEN",
    )
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(module, "date", _FakeDate)
    _FakeDate.fixed = date(2026, 8, 9)

    def boom(**_kwargs: object) -> dict[str, object]:
        raise AssertionError("default weekend date must not call refresh")

    monkeypatch.setattr(module, "refresh_stock_adjustment_factors_for_trade_date", boom)

    exit_code = module.main(["--run-once"])

    assert exit_code == 0


def test_cli_dry_run_default_weekend_returns_plan_not_skip(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = load_module(
        "scripts.stock_adjustment_factor_daily_refresh_dry_run_weekend",
        "scripts/stock_adjustment_factor_daily_refresh.py",
    )
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "settings.duckdb",
        tushare_token="SECRET-TOKEN",
    )
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(module, "date", _FakeDate)
    _FakeDate.fixed = date(2026, 8, 9)
    calls: list[dict[str, object]] = []

    def fake_refresh(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {
            "status": "dry_run",
            "trade_date": "2026-08-09",
            "required_code_count": 0,
            "would_call_tushare": False,
        }

    monkeypatch.setattr(module, "refresh_stock_adjustment_factors_for_trade_date", fake_refresh)

    exit_code = module.main(["--dry-run"])

    assert exit_code == 0
    assert calls == [
        {
            "duckdb_path": str(settings.duckdb_path),
            "trade_date": "2026-08-09",
            "dry_run": True,
        }
    ]


def test_cli_explicit_weekend_still_runs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = load_module(
        "scripts.stock_adjustment_factor_daily_refresh_explicit_weekend",
        "scripts/stock_adjustment_factor_daily_refresh.py",
    )
    settings = SimpleNamespace(
        duckdb_path=tmp_path / "settings.duckdb",
        tushare_token="SECRET-TOKEN",
    )
    forwarded: dict[str, object] = {}
    monkeypatch.setattr(module, "get_settings", lambda: settings)
    monkeypatch.setattr(module, "date", _FakeDate)
    _FakeDate.fixed = date(2026, 8, 9)

    def fake_refresh(**kwargs: object) -> dict[str, object]:
        forwarded.update(kwargs)
        return {"status": "not_ready", "trade_date": str(kwargs["trade_date"])}

    monkeypatch.setattr(module, "refresh_stock_adjustment_factors_for_trade_date", fake_refresh)

    exit_code = module.main(["--run-once", "--as-of-date", "2026-08-09"])

    assert exit_code == 1
    assert forwarded == {
        "duckdb_path": str(settings.duckdb_path),
        "trade_date": "2026-08-09",
    }


def test_task_rejects_trade_date_with_trailing_characters(tmp_path: Path) -> None:
    db_path = tmp_path / "moss.duckdb"
    _create_observation_fixture(db_path)
    module = load_module(
        "backend.app.tasks.stock_adjustment_factor_daily_refresh_invalid_date",
        "backend/app/tasks/stock_adjustment_factor_daily_refresh.py",
    )

    with pytest.raises(RuntimeError, match="valid YYYY-MM-DD"):
        module.refresh_stock_adjustment_factors_for_trade_date(
            duckdb_path=db_path,
            trade_date="2026-08-11junk",
            tushare_client=_AdjFactorClient({}),
        )


def test_cli_rejects_trade_date_with_trailing_characters() -> None:
    module = load_module(
        "scripts.stock_adjustment_factor_daily_refresh_invalid_date",
        "scripts/stock_adjustment_factor_daily_refresh.py",
    )

    with pytest.raises(SystemExit) as exc_info:
        module.main(["--dry-run", "--as-of-date", "2026-08-11junk"])

    assert exc_info.value.code == 2
