from __future__ import annotations

import duckdb
import pytest

import backend.app.core_finance.matched_baseline as matched_baseline_module
from backend.app.core_finance.matched_baseline import (
    LIQUIDITY_FALLBACK_CONTROL_GROUP,
    SAME_SECTOR_CONTROL_GROUP,
    generate_matched_baseline_rows,
    generate_matched_baseline_pit_proof_rows,
    write_matched_baseline_rows,
    matched_baseline_stats_from_rows,
    select_matched_controls,
    summarize_matched_baseline_pit_proof_rows,
)


def _row(
    code: str,
    *,
    sector_code: str = "S1",
    amount: float = 100.0,
    entry_executable: bool = True,
    stock_name: str = "Stock",
) -> dict[str, object]:
    return {
        "signal_date": "2026-06-12",
        "stock_code": code,
        "sector_code": sector_code,
        "amount": amount,
        "entry_executable": entry_executable,
        "stock_name": stock_name,
    }


def _candidate(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "signal_date": "2026-06-12",
        "stock_code": "000001.SZ",
        "sector_code": "S1",
        "amount": 100.0,
        "run_id": "run-test",
    }
    base.update(overrides)
    return base


def _seed_pit_proof_market(
    conn: duckdb.DuckDBPyConnection,
    *,
    include_exit_factor_5d: bool = True,
    include_entry_factor: bool = True,
    include_exit_factor_20d: bool = True,
    exit_day_5_limit_down: bool = False,
    exit_day_6_halted: bool = False,
    include_day_20: bool = True,
    missing_entry_open: bool = False,
    observation_source_version: str | None = "obs-sv",
    observation_run_id: str | None = "obs-run",
    factor_source_version: str | None = "factor-sv",
    factor_run_id: str | None = "factor-run",
) -> None:
    conn.execute(
        """
        create table choice_stock_universe (
          as_of_date varchar,
          stock_code varchar,
          stock_name varchar
        )
        """
    )
    conn.execute(
        """
        create table choice_stock_sector_membership (
          as_of_date varchar,
          stock_code varchar,
          sw2021 varchar,
          sw2021code varchar
        )
        """
    )
    conn.execute(
        """
        create table choice_stock_daily_observation (
          trade_date varchar,
          stock_code varchar,
          open_value double,
          close_value double,
          amount double,
          tradestatus varchar,
          highlimit double,
          lowlimit double,
          source_version varchar,
          vendor_version varchar,
          rule_version varchar,
          run_id varchar
        )
        """
    )
    conn.execute(
        """
        create table stock_adjustment_factor (
          stock_code varchar,
          trade_date varchar,
          adj_factor double,
          source_version varchar,
          vendor_version varchar,
          rule_version varchar,
          run_id varchar
        )
        """
    )
    stocks = ["000001.SZ", "000002.SZ", "000003.SZ"]
    conn.executemany(
        "insert into choice_stock_universe values ('2026-06-12', ?, ?)",
        [(stock, f"Name {stock}") for stock in stocks],
    )
    conn.executemany(
        "insert into choice_stock_sector_membership values ('2026-06-12', ?, 'Sector 1', 'S1')",
        [(stock,) for stock in stocks],
    )
    conn.executemany(
        "insert into choice_stock_daily_observation values ('2026-06-12', ?, 10, 10, ?, 'Trading', 20, 5, ?, 'obs-vv', 'obs-rv', ?)",
        [
            (stock, 100.0 + index, observation_source_version, observation_run_id)
            for index, stock in enumerate(stocks)
        ],
    )
    future_dates = [
        *[f"2026-06-{day:02d}" for day in range(13, 31)],
        "2026-07-01",
        "2026-07-02",
    ]
    obs_rows = []
    factor_rows = []
    for stock in stocks:
        if include_entry_factor:
            factor_rows.append(
                (
                    stock,
                    "2026-06-13",
                    1.0,
                    factor_source_version,
                    "factor-vv",
                    "factor-rv",
                    factor_run_id,
                )
            )
        for day_index, trade_date in enumerate(future_dates):
            tradestatus = "Trading"
            lowlimit = 5.0
            close_value = 11.0 + day_index
            open_value = None if missing_entry_open and day_index == 0 else 10.0
            if exit_day_5_limit_down and stock == "000002.SZ" and day_index == 4:
                close_value = 5.0
                lowlimit = 5.0
            if exit_day_6_halted and stock == "000002.SZ" and day_index == 5:
                tradestatus = "Suspended"
            obs_rows.append(
                (
                    trade_date,
                    stock,
                    open_value,
                    close_value,
                    100.0,
                    tradestatus,
                    20.0,
                    lowlimit,
                    observation_source_version,
                    "obs-vv",
                    "obs-rv",
                    observation_run_id,
                )
            )
            if day_index == 4 and include_exit_factor_5d:
                factor_rows.append(
                    (
                        stock,
                        trade_date,
                        1.0,
                        factor_source_version,
                        "factor-vv",
                        "factor-rv",
                        factor_run_id,
                    )
                )
            if day_index == 6 and exit_day_5_limit_down and exit_day_6_halted:
                factor_rows.append(
                    (
                        stock,
                        trade_date,
                        1.0,
                        factor_source_version,
                        "factor-vv",
                        "factor-rv",
                        factor_run_id,
                    )
                )
            if day_index == 19 and include_day_20 and include_exit_factor_20d:
                factor_rows.append(
                    (
                        stock,
                        trade_date,
                        1.0,
                        factor_source_version,
                        "factor-vv",
                        "factor-rv",
                        factor_run_id,
                    )
                )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            obs_rows,
        )
        obs_rows.clear()
    if factor_rows:
        conn.executemany(
            "insert into stock_adjustment_factor values (?, ?, ?, ?, ?, ?, ?)",
            factor_rows,
        )


def _source_availability_receipt(
    *,
    observation_source_version: str | None = "obs-sv",
    observation_vendor_version: str | None = "obs-vv",
    observation_rule_version: str | None = "obs-rv",
    observation_run_id: str | None = "obs-run",
    observation_available_at: str | None = "2026-06-12",
    factor_source_version: str | None = "factor-sv",
    factor_vendor_version: str | None = "factor-vv",
    factor_rule_version: str | None = "factor-rv",
    factor_run_id: str | None = "factor-run",
    factor_available_at: str | None = "2026-06-13",
    extra_sources: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    sources: list[dict[str, object]] = []
    if observation_available_at is not None:
        sources.append(
            {
                "table": "choice_stock_daily_observation",
                "source_version": observation_source_version,
                "vendor_version": observation_vendor_version,
                "rule_version": observation_rule_version,
                "run_id": observation_run_id,
                "available_at": observation_available_at,
            }
        )
    if factor_available_at is not None:
        sources.append(
            {
                "table": "stock_adjustment_factor",
                "source_version": factor_source_version,
                "vendor_version": factor_vendor_version,
                "rule_version": factor_rule_version,
                "run_id": factor_run_id,
                "available_at": factor_available_at,
            }
        )
    sources.extend(extra_sources or [])
    return {
        "receipt_kind": "pit_source_availability_v1",
        "sources": sources,
    }


def test_matched_baseline_sampling_is_reproducible_with_fixed_seed() -> None:
    universe = [_row("000001.SZ"), *[_row(f"00000{i}.SZ", amount=100.0 + i) for i in range(2, 10)]]
    candidate = _candidate()

    first = select_matched_controls(candidate, universe, sample_size=3, min_same_sector=3)
    second = select_matched_controls(candidate, universe, sample_size=3, min_same_sector=3)
    third = select_matched_controls({**candidate, "run_id": "run-other"}, universe, sample_size=3, min_same_sector=3)

    assert [row["stock_code"] for row in first] == [row["stock_code"] for row in second]
    assert [row["control_group"] for row in first] == [SAME_SECTOR_CONTROL_GROUP] * 3
    assert [row["stock_code"] for row in first] != [row["stock_code"] for row in third]


def test_matched_baseline_falls_back_when_same_sector_pool_is_too_small_and_marks_group() -> None:
    universe = [
        _row("000001.SZ", sector_code="BANK", amount=100),
        _row("000002.SZ", sector_code="BANK", amount=101),
        _row("000003.SZ", sector_code="TECH", amount=99),
        _row("000004.SZ", sector_code="TECH", amount=102),
        _row("000005.SZ", sector_code="TECH", amount=98),
    ]

    controls = select_matched_controls(
        _candidate(sector_code="BANK", amount=100),
        universe,
        sample_size=3,
        min_same_sector=3,
    )

    assert controls
    assert any(row["sector_code"] != "BANK" for row in controls)
    assert {row["control_group"] for row in controls} == {LIQUIDITY_FALLBACK_CONTROL_GROUP}


def test_matched_baseline_excludes_non_buyable_and_st_controls() -> None:
    universe = [
        _row("000001.SZ"),
        _row("000002.SZ", entry_executable=False),
        _row("000003.SZ", stock_name="ST Risk"),
        _row("000004.SZ"),
        _row("000005.SZ"),
    ]

    controls = select_matched_controls(_candidate(), universe, sample_size=5, min_same_sector=2)

    assert {row["stock_code"] for row in controls} == {"000004.SZ", "000005.SZ"}
    assert all(row["entry_executable"] is True for row in controls)


def test_matched_baseline_bootstrap_ci_returns_expected_shape() -> None:
    candidate_rows = [
        {
            "signal_date": "2026-06-12",
            "stock_code": "000001.SZ",
            "signal_kind": "stock_candidate",
            "market_state": "HOT",
            "return_5d_net_adj": 0.08,
        },
        {
            "signal_date": "2026-06-13",
            "stock_code": "000002.SZ",
            "signal_kind": "stock_candidate",
            "market_state": "HOT",
            "return_5d_net_adj": -0.01,
        },
    ]
    control_rows = [
        {
            "signal_date": "2026-06-12",
            "candidate_stock_code": "000001.SZ",
            "signal_kind": "stock_candidate",
            "control_return_5d_net_adj": 0.02,
        },
        {
            "signal_date": "2026-06-12",
            "candidate_stock_code": "000001.SZ",
            "signal_kind": "stock_candidate",
            "control_return_5d_net_adj": 0.04,
        },
        {
            "signal_date": "2026-06-13",
            "candidate_stock_code": "000002.SZ",
            "signal_kind": "stock_candidate",
            "control_return_5d_net_adj": -0.02,
        },
    ]

    stats = matched_baseline_stats_from_rows(
        candidate_rows,
        control_rows,
        bootstrap_iterations=200,
        seed="test",
    )
    horizon = stats["stock_candidate"]["return_5d"]
    ci = horizon["bootstrap_ci_95"]

    assert horizon["n"] == 2
    assert horizon["paired_alpha_avg"] == 0.03
    assert ci["confidence"] == 0.95
    assert ci["iterations"] == 200
    assert isinstance(ci["low"], float)
    assert isinstance(ci["high"], float)
    assert ci["low"] <= ci["high"]


def test_matched_baseline_generates_control_returns_and_writes_rows(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "matched.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_execution_history (
              signal_date varchar,
              stock_code varchar,
              signal_kind varchar,
              market_state varchar,
              candidate_rank integer,
              entry_executable boolean,
              return_1d_net_adj double,
              return_5d_net_adj double,
              return_10d_net_adj double,
              return_20d_net_adj double,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            insert into livermore_candidate_execution_history values
            ('2026-06-12', '000001.SZ', 'stock_candidate', 'HOT', 1, true, 0.01, 0.10, null, null, 'run-cand')
            """
        )
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar,
              signal_kind varchar,
              sector_code varchar,
              sector_name varchar
            )
            """
        )
        conn.execute(
            """
            insert into livermore_candidate_history values
            ('2026-06-12', '000001.SZ', 'stock_candidate', 'S1', 'Sector 1')
            """
        )
        conn.execute(
            """
            create table choice_stock_universe (
              as_of_date varchar,
              stock_code varchar,
              stock_name varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_sector_membership (
              as_of_date varchar,
              stock_code varchar,
              sw2021 varchar,
              sw2021code varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              open_value double,
              close_value double,
              amount double,
              tradestatus varchar,
              highlimit double,
              lowlimit double
            )
            """
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
        stocks = ["000001.SZ", "000002.SZ", "000003.SZ", "000004.SZ"]
        conn.executemany(
            "insert into choice_stock_universe values ('2026-06-12', ?, ?)",
            [(stock, f"Name {stock}") for stock in stocks],
        )
        conn.executemany(
            "insert into choice_stock_sector_membership values ('2026-06-12', ?, 'Sector 1', 'S1')",
            [(stock,) for stock in stocks],
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values ('2026-06-12', ?, 10, 10, ?, 'Trading', 20, 5)",
            [(stock, 100.0 + index) for index, stock in enumerate(stocks)],
        )
        future_dates = ["2026-06-15", "2026-06-16", "2026-06-17", "2026-06-18", "2026-06-19"]
        obs_rows = []
        factor_rows = []
        for stock in stocks:
            factor_rows.append((stock, "2026-06-12", 1.0, "sv", "run"))
            for day_index, trade_date in enumerate(future_dates):
                highlimit = 10.0 if stock == "000004.SZ" and day_index == 0 else 20.0
                close_value = 11.0 + day_index
                obs_rows.append((trade_date, stock, 10.0, close_value, 100.0, "Trading", highlimit, 5.0))
                factor_rows.append((stock, trade_date, 1.0, "sv", "run"))
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?, ?, ?, ?, ?, ?, ?)",
            obs_rows,
        )
        conn.executemany(
            "insert into stock_adjustment_factor values (?, ?, ?, ?, ?)",
            factor_rows,
        )

        rows = generate_matched_baseline_rows(
            conn,
            start_date="2026-06-12",
            end_date="2026-06-12",
            sample_size=2,
            run_id="run-test",
        )
        monkeypatch.setattr(
            matched_baseline_module,
            "_load_control_universes_for_dates",
            lambda connection, signal_dates: {
                signal_date: matched_baseline_module._load_control_universe_for_date(connection, signal_date)
                for signal_date in signal_dates
            },
        )
        monkeypatch.setattr(
            matched_baseline_module,
            "_load_control_execution_returns_for_date",
            lambda connection, *, stock_codes, signal_date: {
                stock_code: matched_baseline_module._control_execution_returns(
                    connection,
                    stock_code=stock_code,
                    signal_date=signal_date,
                )
                for stock_code in stock_codes
            },
        )
        legacy_rows = generate_matched_baseline_rows(
            conn,
            start_date="2026-06-12",
            end_date="2026-06-12",
            sample_size=2,
            run_id="run-test",
        )
        inserted = write_matched_baseline_rows(
            conn,
            rows,
            start_date="2026-06-12",
            end_date="2026-06-12",
        )
        count = conn.execute("select count(*) from livermore_matched_baseline_history").fetchone()[0]
    finally:
        conn.close()

    assert inserted == 2
    assert count == 2
    assert rows == legacy_rows
    assert {row["control_stock_code"] for row in rows} == {"000002.SZ", "000003.SZ"}
    assert {row["control_group"] for row in rows} == {LIQUIDITY_FALLBACK_CONTROL_GROUP}
    # gross 0.50 netted multiplicatively: (1 + 0.5) * (1 - 0.0041) - 1 = 0.49385
    assert rows[0]["control_return_5d_net_adj"] == pytest.approx(0.49385)


def test_candidate_execution_loader_deduplicates_logical_key(tmp_path) -> None:
    db_path = tmp_path / "matched-dedup.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            """
            create table livermore_candidate_execution_history (
              signal_date varchar,
              stock_code varchar,
              signal_kind varchar,
              market_state varchar,
              candidate_rank integer,
              entry_executable boolean,
              return_1d_net_adj double,
              return_5d_net_adj double,
              return_10d_net_adj double,
              return_20d_net_adj double,
              run_id varchar
            )
            """
        )
        conn.executemany(
            """
            insert into livermore_candidate_execution_history values
            ('2026-06-12', '000001.SZ', 'stock_candidate', 'HOT', 1, true, 0.01, 0.10, null, null, 'run-cand')
            """,
            [(), ()],
        )
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar,
              signal_kind varchar,
              sector_code varchar,
              sector_name varchar
            )
            """
        )
        conn.executemany(
            """
            insert into livermore_candidate_history values
            ('2026-06-12', '000001.SZ', 'stock_candidate', 'S1', 'Sector 1')
            """,
            [(), ()],
        )

        rows = matched_baseline_module._load_candidate_execution_rows(
            conn,
            start_date="2026-06-12",
            end_date="2026-06-12",
        )
    finally:
        conn.close()

    assert len(rows) == 1
    assert rows[0]["stock_code"] == "000001.SZ"
    assert rows[0]["sector_code"] == "S1"


def test_pit_proof_respects_evaluation_cutoff_and_counts_unique_candidates(tmp_path) -> None:
    db_path = tmp_path / "matched-pit.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_pit_proof_market(conn)
        rows = generate_matched_baseline_pit_proof_rows(
            conn,
            candidate_rows=[_candidate()],
            evaluation_as_of_date="2026-06-18",
            source_availability_receipt=_source_availability_receipt(),
            sample_size=2,
        )
    finally:
        conn.close()

    assert len(rows) == 2
    assert all(row["control_entry_date"] == "2026-06-13" for row in rows)
    assert all(row["control_return_5d_usable"] is True for row in rows)
    assert all(row["control_return_20d_usable"] is False for row in rows)
    assert all(row["control_failure_reason_20d"] == "exit_horizon_unreached_by_evaluation" for row in rows)
    summary = summarize_matched_baseline_pit_proof_rows(rows)
    assert summary["unique_candidate_keys_with_any_usable_control_entry_count"] == 1
    assert summary["control_row_count"] == 2


def test_pit_proof_rejects_non_iso_or_future_signal_dates(tmp_path) -> None:
    db_path = tmp_path / "matched-pit-date-validation.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_pit_proof_market(conn)
        with pytest.raises(ValueError, match="evaluation_as_of_date must be strict ISO date"):
            generate_matched_baseline_pit_proof_rows(
                conn,
                candidate_rows=[_candidate()],
                evaluation_as_of_date="2026/06/18",
                source_availability_receipt=_source_availability_receipt(),
                sample_size=1,
            )
        with pytest.raises(ValueError, match="candidate.signal_date must be strict ISO date"):
            generate_matched_baseline_pit_proof_rows(
                conn,
                candidate_rows=[_candidate(signal_date="2026/06/12")],
                evaluation_as_of_date="2026-06-18",
                source_availability_receipt=_source_availability_receipt(),
                sample_size=1,
            )
        with pytest.raises(ValueError, match="candidate.signal_date must be on or before evaluation_as_of_date"):
            generate_matched_baseline_pit_proof_rows(
                conn,
                candidate_rows=[_candidate(signal_date="2026-06-20")],
                evaluation_as_of_date="2026-06-18",
                source_availability_receipt=_source_availability_receipt(),
                sample_size=1,
            )
    finally:
        conn.close()


def test_pit_proof_selection_respects_evaluation_bounded_entry_state(tmp_path) -> None:
    db_path = tmp_path / "matched-pit-selection-cutoff.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_pit_proof_market(conn)
        rows = generate_matched_baseline_pit_proof_rows(
            conn,
            candidate_rows=[_candidate()],
            evaluation_as_of_date="2026-06-12",
            source_availability_receipt=_source_availability_receipt(),
            sample_size=2,
        )
    finally:
        conn.close()

    assert rows == []


def test_pit_proof_uses_first_sellable_exit_after_limit_down_and_halt(tmp_path) -> None:
    db_path = tmp_path / "matched-pit-exit.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_pit_proof_market(
            conn,
            exit_day_5_limit_down=True,
            exit_day_6_halted=True,
        )
        rows = generate_matched_baseline_pit_proof_rows(
            conn,
            candidate_rows=[_candidate()],
            evaluation_as_of_date="2026-07-02",
            source_availability_receipt=_source_availability_receipt(
                extra_sources=[
                    {
                        "table": "stock_adjustment_factor",
                        "source_version": "zz-source",
                        "vendor_version": "factor-vv",
                        "rule_version": "factor-rv",
                        "run_id": "zz-run",
                        "available_at": "2026-06-13",
                    }
                ],
            ),
            sample_size=2,
        )
    finally:
        conn.close()

    target = next(row for row in rows if row["control_stock_code"] == "000002.SZ")
    assert target["control_exit_date_5d"] == "2026-06-19"
    assert target["control_return_5d_usable"] is True


def test_pit_proof_fails_closed_when_adjustment_factor_is_missing(tmp_path) -> None:
    db_path = tmp_path / "matched-pit-missing-factor.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_pit_proof_market(
            conn,
            include_entry_factor=False,
            include_exit_factor_5d=False,
            include_exit_factor_20d=False,
        )
        rows = generate_matched_baseline_pit_proof_rows(
            conn,
            candidate_rows=[_candidate()],
            evaluation_as_of_date="2026-07-02",
            source_availability_receipt=_source_availability_receipt(),
            sample_size=1,
        )
    finally:
        conn.close()

    row = rows[0]
    assert row["control_entry_usable"] is False
    assert row["control_entry_failure_reason"] == "missing_entry_adjustment_factor"
    assert row["control_return_5d_net_adj"] is None
    assert row["control_return_5d_usable"] is False
    assert row["control_return_20d_net_adj"] is None
    assert row["control_failure_reason"] == "missing_entry_adjustment_factor"


def test_pit_proof_fails_closed_without_next_open_price(tmp_path) -> None:
    db_path = tmp_path / "matched-pit-open-only.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_pit_proof_market(
            conn,
            missing_entry_open=True,
        )
        proof = matched_baseline_module._control_execution_pit_proof(
            conn,
            stock_code="000002.SZ",
            signal_date="2026-06-12",
            evaluation_as_of_date="2026-07-02",
            source_availability_index=matched_baseline_module._normalize_source_availability_receipt(
                _source_availability_receipt()
            ),
        )
    finally:
        conn.close()

    assert proof["entry"]["executable"] is False
    assert proof["entry"]["usable"] is False
    assert proof["entry"]["price"] is None
    assert proof["entry"]["price_kind"] is None
    assert proof["entry"]["failure_reason"] == "missing_entry_price"


def test_pit_proof_fails_closed_when_observation_source_metadata_is_missing(tmp_path) -> None:
    db_path = tmp_path / "matched-pit-missing-observation-source.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_pit_proof_market(
            conn,
            observation_source_version=None,
            observation_run_id=None,
        )
        rows = generate_matched_baseline_pit_proof_rows(
            conn,
            candidate_rows=[_candidate()],
            evaluation_as_of_date="2026-07-02",
            source_availability_receipt=_source_availability_receipt(),
            sample_size=1,
        )
    finally:
        conn.close()

    row = rows[0]
    assert row["control_entry_executable"] is True
    assert row["control_entry_usable"] is False
    assert row["control_entry_failure_reason"] == "missing_entry_observation_source_metadata"
    assert row["source_evidence"]["observation"]["entry"]["source_version"] is None
    assert row["source_evidence"]["observation"]["entry"]["run_id"] is None


def test_pit_proof_fails_closed_when_factor_source_metadata_is_missing(tmp_path) -> None:
    db_path = tmp_path / "matched-pit-missing-factor-source.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_pit_proof_market(
            conn,
            factor_source_version=None,
            factor_run_id=None,
        )
        rows = generate_matched_baseline_pit_proof_rows(
            conn,
            candidate_rows=[_candidate()],
            evaluation_as_of_date="2026-07-02",
            source_availability_receipt=_source_availability_receipt(),
            sample_size=1,
        )
    finally:
        conn.close()

    row = rows[0]
    assert row["control_entry_executable"] is True
    assert row["control_entry_usable"] is False
    assert row["control_entry_failure_reason"] == "missing_entry_adjustment_factor_source_metadata"
    assert row["source_evidence"]["adjustment_factor"]["entry"]["source_version"] is None
    assert row["source_evidence"]["adjustment_factor"]["entry"]["run_id"] is None


def test_pit_proof_uses_deterministic_factor_source_ordering(tmp_path) -> None:
    db_path = tmp_path / "matched-pit-factor-order.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_pit_proof_market(conn)
        conn.executemany(
            "insert into stock_adjustment_factor values (?, ?, ?, ?, ?, ?, ?)",
            [
                ("000002.SZ", "2026-06-13", 1.2, "zz-source", "factor-vv", "factor-rv", "zz-run"),
                ("000002.SZ", "2026-06-17", 1.3, "zz-source", "factor-vv", "factor-rv", "zz-run"),
            ],
        )
        rows = generate_matched_baseline_pit_proof_rows(
            conn,
            candidate_rows=[_candidate()],
            evaluation_as_of_date="2026-07-02",
            source_availability_receipt=_source_availability_receipt(
                extra_sources=[
                    {
                        "table": "stock_adjustment_factor",
                        "source_version": "zz-source",
                        "vendor_version": "factor-vv",
                        "rule_version": "factor-rv",
                        "run_id": "zz-run",
                        "available_at": "2026-06-13",
                    }
                ],
            ),
            sample_size=2,
        )
    finally:
        conn.close()

    target = next(row for row in rows if row["control_stock_code"] == "000002.SZ")
    assert target["source_evidence"]["adjustment_factor"]["entry"]["source_version"] == "zz-source"
    assert target["source_evidence"]["adjustment_factor"]["entry"]["run_id"] == "zz-run"
    assert target["source_evidence"]["adjustment_factor"]["exit_5d"]["source_version"] == "zz-source"
    assert target["source_evidence"]["adjustment_factor"]["exit_5d"]["run_id"] == "zz-run"


def test_pit_proof_fails_closed_without_source_availability_receipt(tmp_path) -> None:
    db_path = tmp_path / "matched-pit-missing-availability-receipt.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_pit_proof_market(conn)
        rows = generate_matched_baseline_pit_proof_rows(
            conn,
            candidate_rows=[_candidate()],
            evaluation_as_of_date="2026-07-02",
            sample_size=1,
        )
    finally:
        conn.close()

    row = rows[0]
    assert row["control_entry_executable"] is True
    assert row["control_entry_usable"] is False
    assert row["control_entry_failure_reason"] == "entry_observation_source_availability_unproven"
    assert row["source_evidence"]["observation"]["entry"]["availability_status"] == "availability_unproven"
    assert row["source_evidence"]["adjustment_factor"]["entry"]["availability_status"] == "availability_unproven"


def test_pit_proof_fails_closed_when_observation_source_is_available_after_evaluation(tmp_path) -> None:
    db_path = tmp_path / "matched-pit-observation-future.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_pit_proof_market(conn)
        rows = generate_matched_baseline_pit_proof_rows(
            conn,
            candidate_rows=[_candidate()],
            evaluation_as_of_date="2026-07-02",
            source_availability_receipt=_source_availability_receipt(
                observation_available_at="2026-07-03",
            ),
            sample_size=1,
        )
    finally:
        conn.close()

    row = rows[0]
    assert row["control_entry_usable"] is False
    assert row["control_entry_failure_reason"] == "entry_observation_source_available_after_evaluation"
    assert row["source_evidence"]["observation"]["entry"]["availability_status"] == "available_after_evaluation"


def test_pit_proof_excludes_future_factor_rewrite_when_older_proven_source_exists(tmp_path) -> None:
    db_path = tmp_path / "matched-pit-factor-future-rewrite.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_pit_proof_market(conn)
        conn.executemany(
            "insert into stock_adjustment_factor values (?, ?, ?, ?, ?, ?, ?)",
            [
                ("000002.SZ", "2026-06-13", 9.9, "future-factor-sv", "factor-vv", "factor-rv", "future-factor-run"),
                ("000002.SZ", "2026-06-17", 9.8, "future-factor-sv", "factor-vv", "factor-rv", "future-factor-run"),
            ],
        )
        rows = generate_matched_baseline_pit_proof_rows(
            conn,
            candidate_rows=[_candidate()],
            evaluation_as_of_date="2026-07-02",
            source_availability_receipt=_source_availability_receipt(
                extra_sources=[
                    {
                        "table": "stock_adjustment_factor",
                        "source_version": "future-factor-sv",
                        "vendor_version": "factor-vv",
                        "rule_version": "factor-rv",
                        "run_id": "future-factor-run",
                        "available_at": "2026-07-03",
                    }
                ],
            ),
            sample_size=2,
        )
    finally:
        conn.close()

    target = next(row for row in rows if row["control_stock_code"] == "000002.SZ")
    assert target["control_entry_usable"] is True
    assert target["control_return_5d_usable"] is True
    assert target["source_evidence"]["adjustment_factor"]["entry"]["source_version"] == "factor-sv"
    assert target["source_evidence"]["adjustment_factor"]["entry"]["run_id"] == "factor-run"
    assert target["source_evidence"]["adjustment_factor"]["entry"]["availability_status"] == "available"


def test_pit_proof_fails_closed_on_duplicate_control_universe_logical_key(tmp_path) -> None:
    db_path = tmp_path / "matched-pit-duplicate-control-key.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_pit_proof_market(conn)
        conn.execute(
            """
            insert into choice_stock_daily_observation values
            ('2026-06-12', '000002.SZ', 10, 10, 101, 'Trading', 20, 5, 'dup-obs-sv', 'obs-vv', 'obs-rv', 'dup-obs-run')
            """
        )
        with pytest.raises(ValueError, match="duplicate logical keys"):
            generate_matched_baseline_pit_proof_rows(
                conn,
                candidate_rows=[_candidate()],
                evaluation_as_of_date="2026-07-02",
                source_availability_receipt=_source_availability_receipt(
                    extra_sources=[
                        {
                            "table": "choice_stock_daily_observation",
                            "source_version": "dup-obs-sv",
                            "vendor_version": "obs-vv",
                            "rule_version": "obs-rv",
                            "run_id": "dup-obs-run",
                            "available_at": "2026-06-12",
                        }
                    ],
                ),
                sample_size=2,
            )
    finally:
        conn.close()


def test_legacy_generate_rows_remain_unchanged_after_pit_proof_path(tmp_path) -> None:
    db_path = tmp_path / "matched-pit-legacy.duckdb"
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_pit_proof_market(conn)
        conn.execute(
            """
            create table livermore_candidate_execution_history (
              signal_date varchar,
              stock_code varchar,
              signal_kind varchar,
              market_state varchar,
              candidate_rank integer,
              entry_executable boolean,
              return_1d_net_adj double,
              return_5d_net_adj double,
              return_10d_net_adj double,
              return_20d_net_adj double,
              run_id varchar
            )
            """
        )
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar,
              signal_kind varchar,
              sector_code varchar,
              sector_name varchar
            )
            """
        )
        conn.execute(
            """
            insert into livermore_candidate_execution_history values
            ('2026-06-12', '000001.SZ', 'stock_candidate', 'HOT', 1, true, 0.01, 0.10, 0.15, 0.20, 'run-cand')
            """
        )
        conn.execute(
            """
            insert into livermore_candidate_history values
            ('2026-06-12', '000001.SZ', 'stock_candidate', 'S1', 'Sector 1')
            """
        )
        before_rows = generate_matched_baseline_rows(
            conn,
            start_date="2026-06-12",
            end_date="2026-06-12",
            sample_size=2,
            run_id="run-test",
        )
        generate_matched_baseline_pit_proof_rows(
            conn,
            candidate_rows=[_candidate()],
            evaluation_as_of_date="2026-07-02",
            source_availability_receipt=_source_availability_receipt(),
            sample_size=2,
        )
        after_rows = generate_matched_baseline_rows(
            conn,
            start_date="2026-06-12",
            end_date="2026-06-12",
            sample_size=2,
            run_id="run-test",
        )
    finally:
        conn.close()

    assert before_rows
    assert after_rows == before_rows
