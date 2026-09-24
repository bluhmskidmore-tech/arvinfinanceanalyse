from __future__ import annotations

import duckdb
import pytest

from tests.helpers import load_module


def _create_candidate_history_fixture(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table livermore_candidate_history (
          snapshot_as_of_date varchar,
          stock_code varchar,
          stock_name varchar,
          candidate_rank integer,
          selection_close double,
          forward_trade_date_1d varchar,
          forward_trade_date_5d varchar,
          forward_trade_date_10d varchar,
          forward_trade_date_20d varchar,
          return_1d double,
          return_5d double,
          return_10d double,
          return_20d double,
          data_status varchar,
          formula_version varchar,
          source_version varchar,
          vendor_version varchar,
          rule_version varchar,
          run_id varchar,
          signal_kind varchar,
          close_strength double,
          abnormal_turnover double,
          gap_norm double,
          market_state varchar,
          signal_evidence_json varchar
        )
        """
    )
    conn.execute(
        """
        insert into livermore_candidate_history (
          snapshot_as_of_date, stock_code, stock_name, candidate_rank, selection_close,
          forward_trade_date_1d, forward_trade_date_5d, forward_trade_date_10d, forward_trade_date_20d,
          return_1d, return_5d, return_10d, return_20d,
          data_status, formula_version, source_version, vendor_version, rule_version, run_id,
          signal_kind, close_strength, abnormal_turnover, gap_norm, market_state, signal_evidence_json
        ) values (
          '2026-01-06', '000001.SZ', 'Ping', 1, 100.0,
          '2026-01-07', null, null, null,
          0.01, null, null, null,
          'pending', 'fv_old', 'sv_old', 'vv_old', 'rv_old', 'run-old',
          'stock_candidate', 0.96, 1.4, 0.02, 'HOT', '{}'
        )
        """
    )


def _create_price_and_factor_fixture(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar,
          stock_code varchar,
          close_value double
        )
        """
    )
    conn.executemany(
        "insert into choice_stock_daily_observation values (?, ?, ?)",
        [
            ("2026-01-06", "000001.SZ", 100.0),
            ("2026-01-07", "000001.SZ", 101.0),
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
    conn.executemany(
        "insert into stock_adjustment_factor values (?, ?, ?, 'sv_adj', 'run-adj')",
        [
            ("000001.SZ", "2026-01-06", 1.0),
            ("000001.SZ", "2026-01-07", 1.2),
        ],
    )


def test_backfill_adjusted_returns_updates_existing_candidate_rows(tmp_path) -> None:
    db_path = tmp_path / "adjusted-backfill.duckdb"
    report_path = tmp_path / "adjusted-report.md"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _create_candidate_history_fixture(conn)
        _create_price_and_factor_fixture(conn)
    finally:
        conn.close()

    module = load_module("scripts.backfill_adjusted_returns", "scripts/backfill_adjusted_returns.py")
    result = module.backfill_adjusted_returns(
        duckdb_path=db_path,
        start_date="2026-01-06",
        end_date="2026-01-06",
        report_path=report_path,
    )

    assert result["status"] == "completed"
    assert result["candidate_updated_count"] == 1
    assert report_path.exists()

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        row = conn.execute(
            """
            select return_1d, return_1d_adj, ex_div_in_window, signal_evidence_json
            from livermore_candidate_history
            """
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    return_1d, return_1d_adj, ex_div_in_window, signal_evidence_json = row
    assert return_1d == pytest.approx(0.01)
    assert return_1d_adj == pytest.approx((101.0 * 1.2) / (100.0 * 1.0) - 1.0)
    assert ex_div_in_window is True
    assert "partial_missing_adj_factor" not in str(signal_evidence_json)


def test_stock_adjustment_factor_backfill_dry_run_uses_history_coverage_without_fetch(tmp_path) -> None:
    db_path = tmp_path / "stock-adjustment-dry-run.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar
            )
            """
        )
        conn.executemany(
            "insert into livermore_candidate_history values (?, ?)",
            [
                ("2026-01-06", "000001.SZ"),
                ("2026-01-07", "000002.SZ"),
            ],
        )
    finally:
        conn.close()

    module = load_module("scripts.backfill_stock_adjustment_factor", "scripts/backfill_stock_adjustment_factor.py")
    result = module.backfill_stock_adjustment_factor(
        duckdb_path=db_path,
        start_date="2026-01-06",
        end_date="2026-01-07",
        dry_run=True,
    )

    assert result["status"] == "dry_run"
    assert result["code_count"] == 2
    assert result["date_count"] == 2
    assert result["would_call_tushare"] is True
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = {row[0] for row in conn.execute("show tables").fetchall()}
    finally:
        conn.close()
    assert "stock_adjustment_factor" not in tables


class _AdjFactorClient:
    def __init__(self, rows_by_date: dict[str, list[dict[str, object]]]) -> None:
        self.rows_by_date = rows_by_date
        self.call_count = 0
        self.calls: list[dict[str, object]] = []

    def adj_factor(self, **kwargs: object) -> list[dict[str, object]]:
        self.call_count += 1
        self.calls.append(dict(kwargs))
        return self.rows_by_date.get(str(kwargs.get("trade_date")), [])


def _create_adjustment_factor_backfill_fixture(db_path) -> None:
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar
            )
            """
        )
        conn.executemany(
            "insert into livermore_candidate_history values (?, ?)",
            [
                ("2026-01-06", "000001.SZ"),
                ("2026-01-06", "000002.SZ"),
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
        conn.executemany(
            "insert into stock_adjustment_factor values (?, ?, ?, 'sv_old', 'run-old')",
            [
                ("000001.SZ", "2026-01-06", 1.0),
                ("000002.SZ", "2026-01-06", 2.0),
            ],
        )
    finally:
        conn.close()


def test_stock_adjustment_factor_backfill_requires_backup_or_governance_lock(tmp_path) -> None:
    db_path = tmp_path / "stock-adjustment-guard.duckdb"
    _create_adjustment_factor_backfill_fixture(db_path)
    module = load_module("scripts.backfill_stock_adjustment_factor_guard", "scripts/backfill_stock_adjustment_factor.py")
    client = _AdjFactorClient(
        {
            "20260106": [
                {"ts_code": "000001.SZ", "trade_date": "20260106", "adj_factor": 1.1},
            ]
        }
    )

    with pytest.raises(RuntimeError, match="requires --target-backup-path or --governance-lock"):
        module.backfill_stock_adjustment_factor(
            duckdb_path=db_path,
            start_date="2026-01-06",
            end_date="2026-01-06",
            client=client,
        )
    assert client.call_count == 0


def test_stock_adjustment_factor_backfill_partial_vendor_response_preserves_existing_rows(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "stock-adjustment-partial.duckdb"
    _create_adjustment_factor_backfill_fixture(db_path)
    module = load_module("scripts.backfill_stock_adjustment_factor_partial", "scripts/backfill_stock_adjustment_factor.py")
    maturity_calls: list[dict[str, object]] = []
    maturity_module = __import__(
        "backend.app.tasks.livermore_candidate_outcome_maturity",
        fromlist=["mature_livermore_candidate_outcomes"],
    )

    def fake_maturity(*args: object, **kwargs: object) -> dict[str, object]:
        maturity_calls.append({"args": args, "kwargs": kwargs})
        return {
            "status": "completed",
            "evaluation_as_of_date": kwargs["evaluation_as_of_date"],
            "updated_row_count": 1,
        }

    monkeypatch.setattr(maturity_module, "mature_livermore_candidate_outcomes", fake_maturity)

    result = module.backfill_stock_adjustment_factor(
        duckdb_path=db_path,
        start_date="2026-01-06",
        end_date="2026-01-06",
        client=_AdjFactorClient(
            {
                "20260106": [
                    {"ts_code": "000001.SZ", "trade_date": "20260106", "adj_factor": 1.1},
                ]
            }
        ),
        governance_lock=True,
    )

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = conn.execute(
            """
            select stock_code, adj_factor
            from stock_adjustment_factor
            where trade_date = '2026-01-06'
            order by stock_code
            """
        ).fetchall()
    finally:
        conn.close()

    assert result["status"] == "partial_completed"
    assert result["requested_cell_count"] == 2
    assert result["returned_cell_count"] == 1
    assert rows == [("000001.SZ", pytest.approx(1.1)), ("000002.SZ", pytest.approx(2.0))]
    assert result["write_safety"]["status"] == "governance_lock_acknowledged"
    assert len(maturity_calls) == 1
    assert maturity_calls[0]["kwargs"]["evaluation_as_of_date"] == "2026-01-06"
    assert result["outcome_maturity"]["status"] == "completed"


def test_stock_adjustment_factor_backfill_reports_partial_when_outcome_maturity_is_noncompleted(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "stock-adjustment-maturity-failed.duckdb"
    _create_adjustment_factor_backfill_fixture(db_path)
    module = load_module(
        "scripts.backfill_stock_adjustment_factor_maturity_failed",
        "scripts/backfill_stock_adjustment_factor.py",
    )
    maturity_module = __import__(
        "backend.app.tasks.livermore_candidate_outcome_maturity",
        fromlist=["mature_livermore_candidate_outcomes"],
    )
    monkeypatch.setattr(
        maturity_module,
        "mature_livermore_candidate_outcomes",
        lambda *_args, **_kwargs: {"status": "not_ready", "reason": "missing_observation_table"},
    )

    result = module.backfill_stock_adjustment_factor(
        duckdb_path=db_path,
        start_date="2026-01-06",
        end_date="2026-01-06",
        client=_AdjFactorClient(
            {
                "20260106": [
                    {"ts_code": "000001.SZ", "trade_date": "20260106", "adj_factor": 1.1},
                ]
            }
        ),
        governance_lock=True,
    )

    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        written_factor = conn.execute(
            "select adj_factor from stock_adjustment_factor where trade_date = '2026-01-06' and stock_code = '000001.SZ'"
        ).fetchone()
    finally:
        conn.close()

    assert result["status"] == "partial_completed"
    assert result["factor_write_status"] == "completed"
    assert result["outcome_maturity"]["status"] == "not_ready"
    assert result["outcome_maturity"]["error"] == "missing_observation_table"
    assert written_factor == (pytest.approx(1.1),)


def test_stock_adjustment_factor_backfill_reports_partial_when_outcome_maturity_raises(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "stock-adjustment-maturity-error.duckdb"
    _create_adjustment_factor_backfill_fixture(db_path)
    module = load_module(
        "scripts.backfill_stock_adjustment_factor_maturity_error",
        "scripts/backfill_stock_adjustment_factor.py",
    )
    maturity_module = __import__(
        "backend.app.tasks.livermore_candidate_outcome_maturity",
        fromlist=["mature_livermore_candidate_outcomes"],
    )

    def fail_maturity(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise RuntimeError("maturity unavailable")

    monkeypatch.setattr(maturity_module, "mature_livermore_candidate_outcomes", fail_maturity)

    result = module.backfill_stock_adjustment_factor(
        duckdb_path=db_path,
        start_date="2026-01-06",
        end_date="2026-01-06",
        client=_AdjFactorClient(
            {
                "20260106": [
                    {"ts_code": "000001.SZ", "trade_date": "20260106", "adj_factor": 1.1},
                ]
            }
        ),
        governance_lock=True,
    )

    assert result["status"] == "partial_completed"
    assert result["factor_write_status"] == "completed"
    assert result["outcome_maturity"] == {
        "status": "failed",
        "error": "maturity unavailable",
    }


def test_stock_adjustment_factor_cli_returns_nonzero_for_partial_result(monkeypatch, capsys) -> None:
    module = load_module(
        "scripts.backfill_stock_adjustment_factor_partial_cli",
        "scripts/backfill_stock_adjustment_factor.py",
    )
    monkeypatch.setattr(
        module,
        "backfill_stock_adjustment_factor",
        lambda **_kwargs: {
            "status": "partial_completed",
            "factor_write_status": "completed",
            "outcome_maturity": {"status": "failed", "error": "maturity unavailable"},
        },
    )
    monkeypatch.setattr("sys.argv", ["backfill_stock_adjustment_factor.py", "--governance-lock"])

    exit_code = module.main()

    assert exit_code != 0
    assert '"factor_write_status": "completed"' in capsys.readouterr().out


def test_stock_adjustment_factor_choice_universe_scope_uses_exact_date_full_codes(tmp_path) -> None:
    db_path = tmp_path / "stock-adjustment-choice-universe.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute("create table choice_stock_universe (as_of_date varchar, stock_code varchar)")
        conn.executemany(
            "insert into choice_stock_universe values (?, ?)",
            [
                ("2026-07-21", "000002.SZ"),
                ("2026-07-21", "000001.SZ"),
                ("2026-07-21", "000002.SZ"),
                ("2026-07-20", "999999.SH"),
            ],
        )
        conn.execute(
            "create table livermore_candidate_history "
            "(snapshot_as_of_date varchar, stock_code varchar)"
        )
        conn.execute(
            "insert into livermore_candidate_history values ('2026-07-21', '600000.SH')"
        )
    finally:
        conn.close()

    module = load_module(
        "scripts.backfill_stock_adjustment_factor_choice_universe",
        "scripts/backfill_stock_adjustment_factor.py",
    )
    result = module.backfill_stock_adjustment_factor(
        duckdb_path=db_path,
        start_date="2026-07-21",
        end_date="2026-07-21",
        choice_universe_date="2026-07-21",
        dry_run=True,
    )

    assert result["status"] == "dry_run"
    assert result["code_count"] == 2
    assert result["selected_codes_preview"] == ["000001.SZ", "000002.SZ"]
    assert "600000.SH" not in result["selected_codes_preview"]
    assert "999999.SH" not in result["selected_codes_preview"]


@pytest.mark.parametrize(
    ("extra_kwargs", "message"),
    [
        ({"codes": ["000001.SZ"]}, "explicit codes"),
    ],
)
def test_stock_adjustment_factor_choice_universe_scope_rejects_other_code_scopes(
    tmp_path,
    extra_kwargs,
    message,
) -> None:
    db_path = tmp_path / "stock-adjustment-choice-universe-mutual.duckdb"
    duckdb.connect(str(db_path)).close()
    module = load_module(
        "scripts.backfill_stock_adjustment_factor_choice_universe_mutual",
        "scripts/backfill_stock_adjustment_factor.py",
    )

    with pytest.raises(ValueError, match=message):
        module.backfill_stock_adjustment_factor(
            duckdb_path=db_path,
            choice_universe_date="2026-07-21",
            dry_run=True,
            **extra_kwargs,
        )


def test_stock_adjustment_factor_choice_universe_scope_fails_when_table_missing(tmp_path) -> None:
    db_path = tmp_path / "stock-adjustment-choice-universe-missing.duckdb"
    duckdb.connect(str(db_path)).close()
    module = load_module(
        "scripts.backfill_stock_adjustment_factor_choice_universe_missing",
        "scripts/backfill_stock_adjustment_factor.py",
    )

    with pytest.raises(RuntimeError, match="choice_stock_universe table is required"):
        module.backfill_stock_adjustment_factor(
            duckdb_path=db_path,
            start_date="2026-07-21",
            end_date="2026-07-21",
            choice_universe_date="2026-07-21",
            dry_run=True,
        )


def test_stock_adjustment_factor_choice_universe_scope_fails_when_date_has_no_codes(tmp_path) -> None:
    db_path = tmp_path / "stock-adjustment-choice-universe-empty.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute("create table choice_stock_universe (as_of_date varchar, stock_code varchar)")
        conn.execute("insert into choice_stock_universe values ('2026-07-20', '000001.SZ')")
    finally:
        conn.close()
    module = load_module(
        "scripts.backfill_stock_adjustment_factor_choice_universe_empty",
        "scripts/backfill_stock_adjustment_factor.py",
    )

    with pytest.raises(RuntimeError, match="no stock codes for as_of_date 2026-07-21"):
        module.backfill_stock_adjustment_factor(
            duckdb_path=db_path,
            start_date="2026-07-21",
            end_date="2026-07-21",
            choice_universe_date="2026-07-21",
            dry_run=True,
        )


def test_stock_adjustment_factor_cli_passes_choice_universe_date(monkeypatch, capsys) -> None:
    module = load_module(
        "scripts.backfill_stock_adjustment_factor_choice_universe_cli",
        "scripts/backfill_stock_adjustment_factor.py",
    )
    captured: dict[str, object] = {}

    def fake_backfill(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"status": "dry_run"}

    monkeypatch.setattr(module, "backfill_stock_adjustment_factor", fake_backfill)
    monkeypatch.setattr(
        "sys.argv",
        [
            "backfill_stock_adjustment_factor.py",
            "--choice-universe-date",
            "2026-07-21",
            "--start-date",
            "2026-07-21",
            "--end-date",
            "2026-07-21",
            "--dry-run",
        ],
    )

    exit_code = module.main()

    assert exit_code == 0
    assert captured["choice_universe_date"] == "2026-07-21"
    assert captured["codes"] is None
    assert '"status": "dry_run"' in capsys.readouterr().out


def _create_choice_universe_factor_fixture(db_path) -> None:
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute("create table choice_stock_universe (as_of_date varchar, stock_code varchar)")
        conn.executemany(
            "insert into choice_stock_universe values (?, ?)",
            [
                ("2026-07-21", "000001.SZ"),
                ("2026-07-21", "000002.SZ"),
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
        conn.executemany(
            "insert into stock_adjustment_factor values (?, '2026-07-21', ?, 'sv_existing', 'run-existing')",
            [
                ("000001.SZ", 9.1),
                ("000002.SZ", 9.2),
            ],
        )
    finally:
        conn.close()


def _choice_factor_rows(db_path) -> list[tuple[object, ...]]:
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        return conn.execute(
            """
            select stock_code, trade_date, adj_factor, source_version, run_id
            from stock_adjustment_factor
            order by stock_code, trade_date, adj_factor
            """
        ).fetchall()
    finally:
        conn.close()


def test_stock_adjustment_factor_choice_universe_defaults_to_exact_single_date(tmp_path) -> None:
    db_path = tmp_path / "stock-adjustment-choice-default-date.duckdb"
    _create_choice_universe_factor_fixture(db_path)
    module = load_module(
        "scripts.backfill_stock_adjustment_factor_choice_default_date",
        "scripts/backfill_stock_adjustment_factor.py",
    )

    result = module.backfill_stock_adjustment_factor(
        duckdb_path=db_path,
        choice_universe_date="2026-07-21",
        dry_run=True,
    )

    assert result["start_date"] == "2026-07-21"
    assert result["end_date"] == "2026-07-21"
    assert result["date_count"] == 1
    assert result["selected_dates_preview"] == ["2026-07-21"]


@pytest.mark.parametrize(
    ("start_date", "end_date"),
    [
        ("2026-07-20", None),
        (None, "2026-07-22"),
        ("2026-07-21", "2026-07-22"),
    ],
)
def test_stock_adjustment_factor_choice_universe_rejects_nonmatching_date_scope(
    tmp_path,
    start_date,
    end_date,
) -> None:
    db_path = tmp_path / "stock-adjustment-choice-date-mismatch.duckdb"
    _create_choice_universe_factor_fixture(db_path)
    module = load_module(
        "scripts.backfill_stock_adjustment_factor_choice_date_mismatch",
        "scripts/backfill_stock_adjustment_factor.py",
    )

    with pytest.raises(ValueError, match="must match --choice-universe-date"):
        module.backfill_stock_adjustment_factor(
            duckdb_path=db_path,
            start_date=start_date,
            end_date=end_date,
            choice_universe_date="2026-07-21",
            dry_run=True,
        )


@pytest.mark.parametrize(
    "vendor_rows",
    [
        [
            {"ts_code": "000001.SZ", "trade_date": "20260721", "adj_factor": 1.1},
        ],
        [
            {"ts_code": "000001.SZ", "trade_date": "20260721", "adj_factor": 1.1},
            {"ts_code": "000002.SZ", "trade_date": "20260721", "adj_factor": 2.2},
            {"ts_code": "000002.SZ", "trade_date": "20260721", "adj_factor": 0.0},
        ],
        [
            {"ts_code": "000001.SZ", "trade_date": "20260721", "adj_factor": 1.1},
            {"ts_code": "000002.SZ", "trade_date": "20260721", "adj_factor": 2.2},
            {"ts_code": "000002.SZ", "trade_date": "20260720", "adj_factor": 2.2},
        ],
    ],
    ids=["missing-cell", "nonpositive-factor", "wrong-date"],
)
def test_stock_adjustment_factor_choice_universe_incomplete_payload_writes_nothing(
    tmp_path,
    vendor_rows,
) -> None:
    db_path = tmp_path / "stock-adjustment-choice-incomplete.duckdb"
    _create_choice_universe_factor_fixture(db_path)
    original_rows = _choice_factor_rows(db_path)
    module = load_module(
        "scripts.backfill_stock_adjustment_factor_choice_incomplete",
        "scripts/backfill_stock_adjustment_factor.py",
    )

    with pytest.raises(RuntimeError, match="incomplete Choice-universe adjustment factors"):
        module.backfill_stock_adjustment_factor(
            duckdb_path=db_path,
            choice_universe_date="2026-07-21",
            governance_lock=True,
            client=_AdjFactorClient({"20260721": vendor_rows}),
        )

    assert _choice_factor_rows(db_path) == original_rows


def test_stock_adjustment_factor_choice_universe_conflicting_duplicate_writes_nothing(
    tmp_path,
) -> None:
    db_path = tmp_path / "stock-adjustment-choice-conflict.duckdb"
    _create_choice_universe_factor_fixture(db_path)
    original_rows = _choice_factor_rows(db_path)
    module = load_module(
        "scripts.backfill_stock_adjustment_factor_choice_conflict",
        "scripts/backfill_stock_adjustment_factor.py",
    )

    with pytest.raises(RuntimeError, match="conflicting adj_factor values"):
        module.backfill_stock_adjustment_factor(
            duckdb_path=db_path,
            choice_universe_date="2026-07-21",
            governance_lock=True,
            client=_AdjFactorClient(
                {
                    "20260721": [
                        {"ts_code": "000001.SZ", "trade_date": "20260721", "adj_factor": 1.1},
                        {"ts_code": "000001.SZ", "trade_date": "20260721", "adj_factor": 1.2},
                        {"ts_code": "000002.SZ", "trade_date": "20260721", "adj_factor": 2.2},
                    ]
                }
            ),
        )

    assert _choice_factor_rows(db_path) == original_rows


def test_stock_adjustment_factor_choice_universe_strict_complete_payload_deduplicates_and_writes(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "stock-adjustment-choice-complete.duckdb"
    _create_choice_universe_factor_fixture(db_path)
    module = load_module(
        "scripts.backfill_stock_adjustment_factor_choice_complete",
        "scripts/backfill_stock_adjustment_factor.py",
    )
    maturity_module = __import__(
        "backend.app.tasks.livermore_candidate_outcome_maturity",
        fromlist=["mature_livermore_candidate_outcomes"],
    )
    monkeypatch.setattr(
        maturity_module,
        "mature_livermore_candidate_outcomes",
        lambda *_args, **_kwargs: {"status": "completed", "updated_row_count": 0},
    )
    client = _AdjFactorClient(
        {
            "20260721": [
                {"ts_code": "000001.SZ", "trade_date": "20260721", "adj_factor": 1.1},
                {"ts_code": "000001.SZ", "trade_date": "20260721", "adj_factor": 1.1},
                {"ts_code": "000002.SZ", "trade_date": "20260721", "adj_factor": 2.2},
            ]
        }
    )

    result = module.backfill_stock_adjustment_factor(
        duckdb_path=db_path,
        choice_universe_date="2026-07-21",
        governance_lock=True,
        client=client,
    )

    assert result["status"] == "completed"
    assert result["requested_cell_count"] == 2
    assert result["returned_cell_count"] == 2
    assert result["missing_vendor_cell_count"] == 0
    assert client.calls == [
        {
            "trade_date": "20260721",
            "fields": "ts_code,trade_date,adj_factor",
        }
    ]
    assert [
        (stock_code, trade_date, factor)
        for stock_code, trade_date, factor, _source_version, _run_id in _choice_factor_rows(db_path)
    ] == [
        ("000001.SZ", "2026-07-21", pytest.approx(1.1)),
        ("000002.SZ", "2026-07-21", pytest.approx(2.2)),
    ]
