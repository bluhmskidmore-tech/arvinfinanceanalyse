from __future__ import annotations

import hashlib
import shutil
from contextlib import contextmanager
from pathlib import Path

import duckdb
import pytest

from backend.app.tasks import choice_stock_halt_status_repair as repair
from backend.app.tasks.livermore_candidate_outcome_maturity import _horizon_status

pytestmark = [pytest.mark.excluded_surface_acceptance, pytest.mark.surface_livermore]


@pytest.fixture
def inputs(tmp_path: Path) -> dict[str, object]:
    target = tmp_path / "halt.duckdb"
    with duckdb.connect(str(target)) as conn:
        columns = ",".join(f"{field} double" for field in repair.EMPTY_PRICE_COLUMNS)
        conn.execute(
            f"create table choice_stock_daily_observation (trade_date varchar, stock_code varchar, {columns}, "
            "tradestatus varchar,highlimit double,lowlimit double,field_keys_json varchar,"
            "source_version varchar,vendor_version varchar,rule_version varchar,run_id varchar)"
        )
        for day in repair.HALT_DATES:
            conn.execute(
                "insert into choice_stock_daily_observation values (?,?,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,120,80,?,?,?, ?,?)",
                [
                    day,
                    repair.STOCK_CODE,
                    '["daily_limit_flags"]',
                    "sv_original",
                    "vv_choice_stock_20260911_0123456789ab",
                    "rv_original",
                    "run_original",
                ],
            )
        conn.execute(
            "insert into choice_stock_daily_observation values ('2026-09-14','688432.SH',100,110,90,101,1000,101000,1,2,3,'Trading',120,80,'[]','sv_original','vv_choice_stock_20260914_0123456789ab','rv_original','run_original')"
        )
        conn.execute(
            "insert into choice_stock_daily_observation select trade_date,'002870.SZ',open_value,high_value,low_value,close_value,volume,amount,pctchange,turn,amplitude,tradestatus,highlimit,lowlimit,field_keys_json,source_version,vendor_version,rule_version,run_id from choice_stock_daily_observation where trade_date='2026-08-31'"
        )
    source = tmp_path / "announcement.html"
    source.write_text(
        "<p>" + "</p><p>".join(repair._ANNOUNCEMENT_FACTS) + "</p>", encoding="utf-8"
    )
    return {
        "duckdb_path": target,
        "announcement_path": source,
        "expected_announcement_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "receipt_path": tmp_path / "receipt.json",
    }


def rows(path: object) -> list[tuple[object, ...]]:
    with duckdb.connect(str(path), read_only=True) as conn:
        return conn.execute(
            "select * from choice_stock_daily_observation order by rowid"
        ).fetchall()


def apply(inputs: dict[str, object], tmp_path: Path) -> dict[str, object]:
    dry = repair.repair_choice_stock_halt_status(**inputs)
    backup = tmp_path / "backup.duckdb"
    shutil.copyfile(inputs["duckdb_path"], backup)
    return repair.repair_choice_stock_halt_status(
        **inputs,
        apply_changes=True,
        expected_plan_sha256=str(dry["plan_sha256"]),
        target_backup_path=backup,
    )


def test_dry_run_preserves_bytes_and_reports_exact_scope(inputs, tmp_path) -> None:
    before = Path(inputs["duckdb_path"]).read_bytes()
    result = repair.repair_choice_stock_halt_status(**inputs)
    assert result["status"] == "dry_run"
    assert result["status_update_count"] == 10
    assert result["duckdb_written"] is False
    assert Path(inputs["duckdb_path"]).read_bytes() == before
    assert result["source_evidence"]["choice_native_request_certified"] is False


def test_apply_changes_only_ten_statuses_and_retains_original_lineage(
    inputs, tmp_path
) -> None:
    before = rows(inputs["duckdb_path"])
    result = apply(inputs, tmp_path)
    after = rows(inputs["duckdb_path"])
    for index, (old, new) in enumerate(zip(before, after, strict=True)):
        expected = list(old)
        if index < 10:
            expected[11] = "Suspended"
        assert new == tuple(expected)
    assert result["status"] == "completed"
    assert result["price_fields_changed"] is False
    assert result["request_audit_created"] is False
    assert result["passes_replay_certification"] is False
    assert (
        _horizon_status(
            bar_count=20,
            stock_valid_bar_count=15,
            market_trade_date_count=25,
            raw_return=None,
            adjusted_return=None,
            target_trade_date=None,
            evaluation_as_of_date="2026-09-29",
            explicit_halt=True,
        )
        == "partial_halt"
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "price",
        "status",
        "empty_status",
        "space_status",
        "duplicate",
        "missing",
        "vendor",
    ],
)
def test_rejects_unsafe_target_scope_without_writing(inputs, mutation) -> None:
    with duckdb.connect(str(inputs["duckdb_path"])) as conn:
        if mutation == "price":
            conn.execute(
                "update choice_stock_daily_observation set close_value=100 where rowid=0"
            )
        elif mutation == "status":
            conn.execute(
                "update choice_stock_daily_observation set tradestatus='Trading' where rowid=0"
            )
        elif mutation == "empty_status":
            conn.execute(
                "update choice_stock_daily_observation set tradestatus='' where rowid=0"
            )
        elif mutation == "space_status":
            conn.execute(
                "update choice_stock_daily_observation set tradestatus='  ' where rowid=0"
            )
        elif mutation == "vendor":
            conn.execute(
                "update choice_stock_daily_observation set vendor_version='unknown' where rowid=0"
            )
        elif mutation == "duplicate":
            conn.execute(
                "insert into choice_stock_daily_observation select * from choice_stock_daily_observation where rowid=0"
            )
        else:
            conn.execute("delete from choice_stock_daily_observation where rowid=0")
    before = rows(inputs["duckdb_path"])
    with pytest.raises((RuntimeError, ValueError)):
        repair.repair_choice_stock_halt_status(**inputs)
    assert rows(inputs["duckdb_path"]) == before


def test_rejects_changed_source_hash(inputs) -> None:
    inputs["announcement_path"].write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="content hash"):
        repair.repair_choice_stock_halt_status(**inputs)


def test_rejects_other_security_or_interval_source(inputs) -> None:
    path = inputs["announcement_path"]
    path.write_text(
        path.read_text(encoding="utf-8").replace("688432", "002870"), encoding="utf-8"
    )
    inputs["expected_announcement_sha256"] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    with pytest.raises(ValueError, match="exact approved"):
        repair.repair_choice_stock_halt_status(**inputs)


@pytest.mark.parametrize("backup_mode", ["absent", "samefile", "different"])
def test_apply_requires_identical_separate_backup(
    inputs, tmp_path, backup_mode
) -> None:
    dry = repair.repair_choice_stock_halt_status(**inputs)
    backup = None
    if backup_mode == "samefile":
        backup = inputs["duckdb_path"]
    elif backup_mode == "different":
        backup = tmp_path / "wrong.duckdb"
        backup.write_bytes(b"wrong")
    before = rows(inputs["duckdb_path"])
    with pytest.raises(ValueError):
        repair.repair_choice_stock_halt_status(
            **inputs,
            apply_changes=True,
            expected_plan_sha256=dry["plan_sha256"],
            target_backup_path=backup,
        )
    assert rows(inputs["duckdb_path"]) == before


def test_apply_rejects_changed_plan_even_with_fresh_identical_backup(
    inputs, tmp_path
) -> None:
    dry = repair.repair_choice_stock_halt_status(**inputs)
    with duckdb.connect(str(inputs["duckdb_path"])) as conn:
        conn.execute(
            "update choice_stock_daily_observation set highlimit=130 where rowid=0"
        )
    backup = tmp_path / "backup.duckdb"
    shutil.copyfile(inputs["duckdb_path"], backup)
    before = rows(inputs["duckdb_path"])
    with pytest.raises(RuntimeError, match="plan changed"):
        repair.repair_choice_stock_halt_status(
            **inputs,
            apply_changes=True,
            expected_plan_sha256=dry["plan_sha256"],
            target_backup_path=backup,
        )
    assert rows(inputs["duckdb_path"]) == before


def test_transaction_rolls_back_when_scope_check_fails(
    inputs, tmp_path, monkeypatch
) -> None:
    before = rows(inputs["duckdb_path"])

    def fail(*args, **kwargs):
        raise RuntimeError("scope check failure")

    monkeypatch.setattr(repair, "_assert_scope_after", fail)
    with pytest.raises(RuntimeError, match="scope check failure"):
        apply(inputs, tmp_path)
    assert rows(inputs["duckdb_path"]) == before


def test_receipt_cannot_overwrite_target_or_source(inputs) -> None:
    inputs["receipt_path"] = inputs["announcement_path"]
    before = inputs["announcement_path"].read_bytes()
    with pytest.raises(ValueError, match="different files"):
        repair.repair_choice_stock_halt_status(**inputs)
    assert inputs["announcement_path"].read_bytes() == before


def test_receipt_cannot_replace_target_wal(inputs) -> None:
    inputs["receipt_path"] = Path(str(inputs["duckdb_path"]) + ".wal")
    with pytest.raises(ValueError, match="WAL file"):
        repair.repair_choice_stock_halt_status(**inputs)


@pytest.mark.parametrize("change", ["replace", "delete"])
def test_backup_changed_while_acquiring_lock_rejects_without_write(
    inputs, tmp_path, monkeypatch, change
) -> None:
    before = rows(inputs["duckdb_path"])
    backup = tmp_path / "backup.duckdb"

    @contextmanager
    def changed_backup_lock(*args, **kwargs):
        if change == "replace":
            backup.write_bytes(b"replaced while waiting for the writer lock")
        else:
            backup.unlink()
        yield

    monkeypatch.setattr(repair, "acquire_lock", changed_backup_lock)
    with pytest.raises((FileNotFoundError, ValueError)):
        apply(inputs, tmp_path)
    assert rows(inputs["duckdb_path"]) == before
