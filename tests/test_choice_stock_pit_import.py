from __future__ import annotations

import hashlib
import json
import shutil
from contextlib import contextmanager
from pathlib import Path

import duckdb
import pytest

from backend.app.tasks import choice_stock_pit_import as pit_import
from backend.app.tasks.choice_stock_materialize import ensure_choice_stock_schema


AS_OF_DATE = "2026-09-02"
SOURCE_VERSION = "sv_choice_stock_aaaaaaaaaaaa"
VENDOR_VERSION = "vv_choice_tushare_stock_20260902_aaaaaaaaaaaa"
RULE_VERSION = "rv_choice_stock_materialization_front_layer_v1"
RUN_ID = "choice_stock_materialize:2026-09-02:aaaaaaaaaaaa"
STOCK_CODES = ("000001.SZ", "600000.SH")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _open_choice_db(path: Path) -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(str(path), read_only=False)
    ensure_choice_stock_schema(conn)
    return conn


def _pit_audit_rows(
    *,
    run_id: str = RUN_ID,
    source_version: str = SOURCE_VERSION,
    vendor_version: str = VENDOR_VERSION,
) -> list[tuple[object, ...]]:
    codes = ",".join(STOCK_CODES)
    return [
        (
            run_id,
            AS_OF_DATE,
            "stock_universe",
            "a_share_universe_sector_001004",
            "sector",
            "001004",
            json.dumps(["001004", AS_OF_DATE]),
            "{}",
            "completed",
            len(STOCK_CODES),
            0,
            "",
            source_version,
            vendor_version,
            RULE_VERSION,
        ),
        (
            run_id,
            AS_OF_DATE,
            "sector_membership",
            "sw2021_industry_membership",
            "css",
            "SW2021,SW2021CODE",
            json.dumps([codes, "SW2021,SW2021CODE"]),
            json.dumps({"EndDate": AS_OF_DATE, "Classification": "1"}),
            "completed",
            len(STOCK_CODES),
            0,
            "",
            source_version,
            vendor_version,
            RULE_VERSION,
        ),
        (
            run_id,
            AS_OF_DATE,
            "limit_up_quality",
            "point_in_time_limit_streaks",
            "css",
            "ISSURGEDLIMIT,ISDECLINELIMIT,HLIMITEDAYS,LLIMITEDDAYS",
            json.dumps(
                [
                    codes,
                    "ISSURGEDLIMIT,ISDECLINELIMIT,HLIMITEDAYS,LLIMITEDDAYS",
                ]
            ),
            json.dumps({"TradeDate": AS_OF_DATE}),
            "completed",
            len(STOCK_CODES),
            0,
            "",
            source_version,
            vendor_version,
            RULE_VERSION,
        ),
    ]


def _daily_audit_rows() -> list[tuple[object, ...]]:
    rows = []
    for family, field_key, indicator in (
        ("sector_strength", "daily_return_turnover_amplitude", "PCTCHANGE,TURN,AMPLITUDE"),
        ("stock_ohlcv", "daily_ohlcv_amount", "OPEN,HIGH,LOW,CLOSE,VOLUME,AMOUNT"),
        ("stock_status", "daily_trade_status", "TRADESTATUS"),
        ("limit_up_quality", "daily_limit_flags", "HIGHLIMIT,LOWLIMIT"),
    ):
        rows.append(
            (
                "target-existing-daily-run",
                AS_OF_DATE,
                family,
                field_key,
                "csd",
                indicator,
                "[]",
                "{}",
                "completed_tushare_gap_repair",
                len(STOCK_CODES),
                0,
                "",
                "sv_existing_daily",
                "vv_choice_tushare_stock_20260902_bbbbbbbbbbbb",
                RULE_VERSION,
            )
        )
    return rows


def _insert_audits(conn: duckdb.DuckDBPyConnection, rows: list[tuple[object, ...]]) -> None:
    conn.executemany(
        "insert into choice_stock_request_audit values "
        "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def _seed_source(path: Path) -> None:
    conn = _open_choice_db(path)
    try:
        for index, stock_code in enumerate(STOCK_CODES):
            conn.execute(
                "insert into choice_stock_universe values (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    AS_OF_DATE,
                    stock_code,
                    f"Stock {index}",
                    "a_share_universe_sector_001004",
                    SOURCE_VERSION,
                    VENDOR_VERSION,
                    RULE_VERSION,
                    RUN_ID,
                ],
            )
            conn.execute(
                "insert into choice_stock_sector_membership values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    AS_OF_DATE,
                    stock_code,
                    "Bank",
                    "801780",
                    "sw2021_industry_membership",
                    SOURCE_VERSION,
                    VENDOR_VERSION,
                    RULE_VERSION,
                    RUN_ID,
                ],
            )
            conn.execute(
                "insert into choice_stock_limit_quality values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    AS_OF_DATE,
                    stock_code,
                    "0",
                    "0",
                    index,
                    0,
                    "point_in_time_limit_streaks",
                    SOURCE_VERSION,
                    VENDOR_VERSION,
                    RULE_VERSION,
                    RUN_ID,
                ],
            )
            conn.execute(
                "insert into choice_stock_daily_observation values "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    AS_OF_DATE,
                    stock_code,
                    10.0,
                    10.5,
                    9.5,
                    10.2,
                    1000.0,
                    10200.0,
                    2.0,
                    1.5,
                    10.0,
                    "Trading",
                    "11.0",
                    "9.0",
                    json.dumps(
                        [
                            "daily_return_turnover_amplitude",
                            "daily_ohlcv_amount",
                            "daily_trade_status",
                            "daily_limit_flags",
                        ]
                    ),
                    "sv_existing_daily",
                    "vv_choice_tushare_stock_20260902_bbbbbbbbbbbb",
                    RULE_VERSION,
                    "target-existing-daily-run",
                ],
            )
        _insert_audits(conn, _pit_audit_rows() + _daily_audit_rows())
    finally:
        conn.close()


def _seed_target(path: Path) -> None:
    conn = _open_choice_db(path)
    try:
        for index, stock_code in enumerate(STOCK_CODES):
            conn.execute(
                "insert into choice_stock_daily_observation values "
                "(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    AS_OF_DATE,
                    stock_code,
                    10.0,
                    10.5,
                    9.5,
                    10.2,
                    1000.0,
                    10200.0,
                    2.0,
                    1.5,
                    10.0,
                    "Trading",
                    "11.0",
                    "9.0",
                    '["daily_return_turnover_amplitude","daily_ohlcv_amount",'
                    '"daily_trade_status","daily_limit_flags"]',
                    "sv_existing_daily",
                    "vv_choice_tushare_stock_20260902_bbbbbbbbbbbb",
                    RULE_VERSION,
                    "target-existing-daily-run",
                ],
            )
        _insert_audits(conn, _daily_audit_rows())
        _insert_audits(
            conn,
            _pit_audit_rows(
                run_id="choice_stock_materialize:2026-09-02:failed000000",
                source_version="sv_choice_stock_cccccccccccc",
                vendor_version="vv_choice_stock_failed_20260902",
            ),
        )
        conn.execute(
            "insert into choice_stock_universe values "
            "('2026-09-01', '000001.SZ', 'Keep', 'a_share_universe_sector_001004', "
            "'sv_keep', 'vv_keep', 'rv_keep', 'run:keep')"
        )
        conn.execute(
            "insert into choice_stock_sector_membership values "
            "('2026-09-01', '000001.SZ', 'Keep', '801000', 'sw2021_industry_membership', "
            "'sv_keep', 'vv_keep', 'rv_keep', 'run:keep')"
        )
        conn.execute(
            "insert into choice_stock_limit_quality values "
            "('2026-09-01', '000001.SZ', '0', '0', 0, 0, 'point_in_time_limit_streaks', "
            "'sv_keep', 'vv_keep', 'rv_keep', 'run:keep')"
        )
    finally:
        conn.close()


def _build_fixture(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source.duckdb"
    target = tmp_path / "target.duckdb"
    _seed_source(source)
    _seed_target(target)
    return source, target


def _dry_run(tmp_path: Path, source: Path, target: Path) -> dict[str, object]:
    return pit_import.import_choice_stock_pit_snapshot(
        target,
        source_duckdb_path=source,
        as_of_date=AS_OF_DATE,
        expected_source_sha256=_sha256(source),
        receipt_path=tmp_path / "dry-run.json",
    )


def test_import_applies_exact_scope_and_is_idempotent(tmp_path: Path) -> None:
    source, target = _build_fixture(tmp_path)
    daily_before = _table_hash(target, "choice_stock_daily_observation")
    old_audits_before = _old_audit_hash(target)
    dry_run = _dry_run(tmp_path, source, target)
    assert dry_run["insert_counts"] == {
        "choice_stock_universe": 2,
        "choice_stock_sector_membership": 2,
        "choice_stock_limit_quality": 2,
    }
    assert dry_run["audit_insert_count"] == 3

    backup = tmp_path / "target-before.duckdb"
    shutil.copy2(target, backup)
    result = pit_import.import_choice_stock_pit_snapshot(
        target,
        source_duckdb_path=source,
        as_of_date=AS_OF_DATE,
        expected_source_sha256=_sha256(source),
        receipt_path=tmp_path / "apply.json",
        apply_changes=True,
        expected_plan_sha256=str(dry_run["plan_sha256"]),
        target_backup_path=backup,
    )

    assert result["status"] == "completed"
    assert result["inserted_total"] == 9
    assert result["post_write_validation"]["coverage_full"] is True
    assert _table_hash(target, "choice_stock_daily_observation") == daily_before
    assert _old_audit_hash(target) == old_audits_before
    conn = duckdb.connect(str(target), read_only=True)
    try:
        assert {
            table: conn.execute(
                f"select count(*) from {table} where as_of_date = ?",
                [AS_OF_DATE],
            ).fetchone()[0]
            for table in (
                "choice_stock_universe",
                "choice_stock_sector_membership",
                "choice_stock_limit_quality",
            )
        } == {
            "choice_stock_universe": 2,
            "choice_stock_sector_membership": 2,
            "choice_stock_limit_quality": 2,
        }
        assert conn.execute(
            "select count(*) from choice_stock_request_audit where as_of_date = ?",
            [AS_OF_DATE],
        ).fetchone()[0] == 10
        assert conn.execute("select count(*) from choice_stock_materialize_run").fetchone()[0] == 0
        assert conn.execute(
            "select count(*) from choice_stock_universe where as_of_date = '2026-09-01'"
        ).fetchone()[0] == 1
    finally:
        conn.close()

    noop = _dry_run(tmp_path, source, target)
    assert set(noop["insert_counts"].values()) == {0}
    assert set(noop["identical_counts"].values()) == {2}
    assert noop["audit_insert_count"] == 0
    assert noop["audit_identical_count"] == 3


def test_import_rejects_conflicting_nonempty_target_row(tmp_path: Path) -> None:
    source, target = _build_fixture(tmp_path)
    conn = duckdb.connect(str(target), read_only=False)
    try:
        conn.execute(
            "insert into choice_stock_universe values "
            "(?, '000001.SZ', 'Conflicting', 'a_share_universe_sector_001004', "
            "'sv_conflict', 'vv_conflict', 'rv_conflict', 'run:conflict')",
            [AS_OF_DATE],
        )
    finally:
        conn.close()

    with pytest.raises(RuntimeError, match="conflicting nonempty target PIT row"):
        _dry_run(tmp_path, source, target)
    assert json.loads((tmp_path / "dry-run.json").read_text(encoding="utf-8"))[
        "no_changes_committed"
    ] is True


def test_import_rejects_duplicate_source_key_and_mismatched_css_code_scope(tmp_path: Path) -> None:
    source, target = _build_fixture(tmp_path)
    conn = duckdb.connect(str(source), read_only=False)
    try:
        conn.execute(
            "insert into choice_stock_universe select * from choice_stock_universe limit 1"
        )
    finally:
        conn.close()
    with pytest.raises(RuntimeError, match="duplicate natural keys"):
        _dry_run(tmp_path, source, target)

    source.unlink()
    _seed_source(source)
    conn = duckdb.connect(str(source), read_only=False)
    try:
        conn.execute(
            "update choice_stock_request_audit set request_arguments_json = ? "
            "where input_family = 'sector_membership' "
            "and field_key = 'sw2021_industry_membership'",
            [json.dumps([STOCK_CODES[0], "SW2021,SW2021CODE"])],
        )
    finally:
        conn.close()
    with pytest.raises(RuntimeError, match="CSS request code scope differs"):
        _dry_run(tmp_path, source, target)


def test_import_rolls_back_all_tables_when_post_write_validation_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, target = _build_fixture(tmp_path)
    dry_run = _dry_run(tmp_path, source, target)
    backup = tmp_path / "target-before.duckdb"
    shutil.copy2(target, backup)
    before_sha256 = _sha256(target)
    monkeypatch.setattr(
        pit_import,
        "_post_write_validate",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("forced validation failure")),
    )

    with pytest.raises(RuntimeError, match="forced validation failure"):
        pit_import.import_choice_stock_pit_snapshot(
            target,
            source_duckdb_path=source,
            as_of_date=AS_OF_DATE,
            expected_source_sha256=_sha256(source),
            receipt_path=tmp_path / "apply.json",
            apply_changes=True,
            expected_plan_sha256=str(dry_run["plan_sha256"]),
            target_backup_path=backup,
        )

    assert _sha256(target) == before_sha256
    failure = json.loads((tmp_path / "apply.json").read_text(encoding="utf-8"))
    assert failure["duckdb_written"] is False
    assert failure["no_changes_committed"] is True


@pytest.mark.parametrize("backup_change", ["replaced", "deleted"])
def test_import_rejects_backup_changed_while_waiting_for_writer_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    backup_change: str,
) -> None:
    source, target = _build_fixture(tmp_path)
    dry_run = _dry_run(tmp_path, source, target)
    backup = tmp_path / "target-before.duckdb"
    shutil.copy2(target, backup)
    before_sha256 = _sha256(target)
    with duckdb.connect(str(target), read_only=True) as conn:
        before_tables = {
            str(table): conn.execute(f"select * from {table} order by all").fetchall()
            for (table,) in conn.execute("show tables").fetchall()
        }
    original_acquire_lock = pit_import.acquire_lock

    @contextmanager
    def acquire_with_backup_change(*args, **kwargs):
        with original_acquire_lock(*args, **kwargs) as acquired:
            if backup_change == "replaced":
                backup.write_bytes(b"backup replaced while waiting for writer lock")
            else:
                backup.unlink()
            yield acquired

    monkeypatch.setattr(pit_import, "acquire_lock", acquire_with_backup_change)
    expected_error = RuntimeError if backup_change == "replaced" else FileNotFoundError
    expected_message = "not byte-identical" if backup_change == "replaced" else "target-before.duckdb"
    with pytest.raises(expected_error, match=expected_message):
        pit_import.import_choice_stock_pit_snapshot(
            target,
            source_duckdb_path=source,
            as_of_date=AS_OF_DATE,
            expected_source_sha256=_sha256(source),
            receipt_path=tmp_path / "apply.json",
            apply_changes=True,
            expected_plan_sha256=str(dry_run["plan_sha256"]),
            target_backup_path=backup,
        )

    assert _sha256(target) == before_sha256
    with duckdb.connect(str(target), read_only=True) as conn:
        after_tables = {
            str(table): conn.execute(f"select * from {table} order by all").fetchall()
            for (table,) in conn.execute("show tables").fetchall()
        }
    assert after_tables == before_tables
    failure = json.loads((tmp_path / "apply.json").read_text(encoding="utf-8"))
    assert failure["status"] == "failed"
    assert failure["duckdb_written"] is False
    assert failure["no_changes_committed"] is True


def test_import_rejects_source_hardlinked_to_target(tmp_path: Path) -> None:
    target = tmp_path / "target.duckdb"
    _seed_source(target)
    source = tmp_path / "source-alias.duckdb"
    source.hardlink_to(target)
    before_sha256 = _sha256(target)

    with pytest.raises(ValueError, match="source and target DuckDB paths must be different"):
        _dry_run(tmp_path, source, target)

    assert _sha256(target) == before_sha256
    failure = json.loads((tmp_path / "dry-run.json").read_text(encoding="utf-8"))
    assert failure["duckdb_written"] is False
    assert failure["no_changes_committed"] is True


@pytest.mark.parametrize("backup_alias_of", ["target", "source"])
def test_import_rejects_hardlinked_backup(
    tmp_path: Path,
    backup_alias_of: str,
) -> None:
    source, target = _build_fixture(tmp_path)
    if backup_alias_of == "source":
        shutil.copyfile(source, target)
    dry_run = _dry_run(tmp_path, source, target)
    backup = tmp_path / "target-before.duckdb"
    backup.hardlink_to(target if backup_alias_of == "target" else source)
    before_sha256 = _sha256(target)
    with duckdb.connect(str(target), read_only=True) as conn:
        before_tables = {
            str(table): conn.execute(f"select * from {table} order by all").fetchall()
            for (table,) in conn.execute("show tables").fetchall()
        }

    with pytest.raises(ValueError, match="target backup must be a distinct file"):
        pit_import.import_choice_stock_pit_snapshot(
            target,
            source_duckdb_path=source,
            as_of_date=AS_OF_DATE,
            expected_source_sha256=_sha256(source),
            receipt_path=tmp_path / "apply.json",
            apply_changes=True,
            expected_plan_sha256=str(dry_run["plan_sha256"]),
            target_backup_path=backup,
        )

    assert _sha256(target) == before_sha256
    with duckdb.connect(str(target), read_only=True) as conn:
        after_tables = {
            str(table): conn.execute(f"select * from {table} order by all").fetchall()
            for (table,) in conn.execute("show tables").fetchall()
        }
    assert after_tables == before_tables
    failure = json.loads((tmp_path / "apply.json").read_text(encoding="utf-8"))
    assert failure["duckdb_written"] is False
    assert failure["no_changes_committed"] is True


def _table_hash(path: Path, table: str) -> str:
    conn = duckdb.connect(str(path), read_only=True)
    try:
        rows = conn.execute(f"select * from {table} order by all").fetchall()
    finally:
        conn.close()
    return pit_import._canonical_sha256(rows)


def _old_audit_hash(path: Path) -> str:
    conn = duckdb.connect(str(path), read_only=True)
    try:
        rows = conn.execute(
            "select * from choice_stock_request_audit where run_id <> ? order by all",
            [RUN_ID],
        ).fetchall()
    finally:
        conn.close()
    return pit_import._canonical_sha256(rows)
