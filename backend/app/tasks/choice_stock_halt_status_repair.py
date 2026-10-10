"""Restore only the ten disclosed 688432.SH halt statuses; never synthesize prices."""

from __future__ import annotations

import hashlib
import html
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
from backend.app.governance.locks import acquire_lock, resolve_duckdb_writer_lock
from backend.app.repositories.task_write_guard import repository_task_write_scope
from backend.app.tasks.choice_stock_materialize import (
    assert_known_choice_stock_daily_vendor_version,
)
from backend.app.tasks.choice_stock_matured_bar_repair import (
    EMPTY_PRICE_COLUMNS,
    _canonical_sha256,
    _normalize_sha256,
    _sha256_file,
    _verify_byte_identical_backup,
    _write_json_atomic,
)

SCHEMA = "choice_stock_halt_status_repair/v1"
STOCK_CODE = "688432.SH"
HALT_DATES = (
    "2026-08-31",
    "2026-09-01",
    "2026-09-02",
    "2026-09-03",
    "2026-09-04",
    "2026-09-07",
    "2026-09-08",
    "2026-09-09",
    "2026-09-10",
    "2026-09-11",
)
ANNOUNCEMENT_URL = "https://paper.cnstock.com/html/2026-09/12/content_2268083.htm"
_ANNOUNCEMENT_FACTS = (
    "证券代码：688432",
    "公告编号：2026-039",
    "自2026年8月31日开市起开始停牌",
    "自2026年9月7日开市起继续停牌",
    "将于2026年9月14日（星期一）开市起复牌",
)


def repair_choice_stock_halt_status(
    duckdb_path: str | Path,
    *,
    announcement_path: str | Path,
    expected_announcement_sha256: str,
    receipt_path: str | Path,
    apply_changes: bool = False,
    expected_plan_sha256: str | None = None,
    target_backup_path: str | Path | None = None,
) -> dict[str, object]:
    """Review a bounded plan before an explicitly requested, backed-up apply."""
    target = Path(duckdb_path).resolve(strict=True)
    source = Path(announcement_path).resolve(strict=True)
    receipt = Path(receipt_path).resolve()
    paths = [target, source, receipt]
    if target_backup_path is not None:
        paths.append(Path(target_backup_path).resolve(strict=True))
    if receipt == Path(str(target) + ".wal") or (
        target_backup_path is not None and receipt == Path(str(Path(target_backup_path).resolve()) + ".wal")
    ):
        raise ValueError("receipt must not replace a DuckDB WAL file")
    if len(set(paths)) != len(paths) or any(
        a.exists() and b.exists() and a.samefile(b) for i, a in enumerate(paths) for b in paths[i + 1 :]
    ):
        raise ValueError("target, source, backup, and receipt must be different files")
    source_hash = _normalize_sha256(expected_announcement_sha256, field_name="expected_announcement_sha256")
    source_bytes = source.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != source_hash:
        raise ValueError("announcement content hash mismatch")
    text = html.unescape(re.sub(r"<[^>]+>", "", source_bytes.decode("utf-8")))
    text = re.sub(r"\s+", "", text)
    if any(fact not in text for fact in _ANNOUNCEMENT_FACTS):
        raise ValueError("announcement does not prove the exact approved security and halt interval")
    provenance: dict[str, object] = {
        "kind": "issuer_announcement_status_evidence",
        "url": ANNOUNCEMENT_URL,
        "announcement_number": "2026-039",
        "published_date": "2026-09-12",
        "document_path": str(source),
        "document_sha256": source_hash,
        "captured_receipt_at": datetime.now(UTC).isoformat(),
        "choice_native_request_certified": False,
    }
    committed = False
    try:
        backup: dict[str, object] = {}
        if not apply_changes:
            with duckdb.connect(str(target), read_only=True) as conn:
                plan = _build_plan(conn, source_hash=source_hash)
        else:
            expected_plan = _normalize_sha256(expected_plan_sha256, field_name="expected_plan_sha256")
            lock = resolve_duckdb_writer_lock(target, ttl_seconds=900)
            with acquire_lock(lock, base_dir=target.parent, timeout_seconds=30):
                backup = _verify_byte_identical_backup(target, target_backup_path=target_backup_path)
                if _sha256_file(source) != source_hash:
                    raise RuntimeError("announcement changed after validation")
                with duckdb.connect(str(target), read_only=False) as conn:
                    plan = _build_plan(conn, source_hash=source_hash)
                    if plan["plan_sha256"] != expected_plan:
                        raise RuntimeError("halt repair plan changed; rerun and review dry-run")
                    with repository_task_write_scope(__name__):
                        conn.execute("begin transaction")
                        try:
                            for row in plan["updates"]:
                                conn.execute(
                                    "update choice_stock_daily_observation set tradestatus='Suspended' where rowid=?",
                                    [row["_rowid"]],
                                )
                            _assert_scope_after(conn, plan=plan)
                            conn.execute("commit")
                            committed = True
                        except Exception:
                            conn.execute("rollback")
                            raise
        result: dict[str, object] = {
            "schema": SCHEMA,
            "status": "completed" if committed else "dry_run",
            "duckdb_path": str(target),
            "duckdb_written": committed,
            "plan_sha256": plan["plan_sha256"],
            "status_update_count": len(plan["updates"]),
            "price_fields_changed": False,
            "candidate_outcomes_changed": False,
            "request_audit_created": False,
            "passes_replay_certification": False,
            "source_evidence": provenance,
            "changes": [{"before": row, "new_tradestatus": "Suspended"} for row in plan["updates"]],
            "next_step": "The existing outcome-maturity task can disclose partial_halt at the genuine evaluation date; stored pending status and the unavailable 20th valid bar/return may remain. This does not close replay certification.",
            **backup,
        }
        _write_json_atomic(receipt, result)
        return result
    except Exception as exc:
        _write_json_atomic(
            receipt,
            {
                "schema": SCHEMA,
                "status": "failed",
                "duckdb_path": str(target),
                "duckdb_written": committed,
                "no_changes_committed": not committed,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "source_evidence": provenance,
            },
        )
        raise


def _load_security_scope(conn: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    cursor = conn.execute(
        "select rowid as _rowid, * from choice_stock_daily_observation "
        "where upper(trim(cast(stock_code as varchar)))=? order by rowid",
        [STOCK_CODE],
    )
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _build_plan(conn: duckdb.DuckDBPyConnection, *, source_hash: str) -> dict[str, Any]:
    before = _load_security_scope(conn)
    updates = [row for row in before if str(row["trade_date"]) in HALT_DATES]
    if len(updates) != 10 or {str(row["trade_date"]) for row in updates} != set(HALT_DATES):
        raise RuntimeError("halt repair requires exactly ten existing natural-key rows")
    required = {*EMPTY_PRICE_COLUMNS, "tradestatus", "vendor_version", "source_version", "rule_version", "run_id"}
    for row in updates:
        if not required.issubset(row):
            raise RuntimeError("observation schema lacks price or lineage fields")
        if any(row[field] is not None for field in EMPTY_PRICE_COLUMNS):
            raise RuntimeError("halt repair refuses rows with nonempty price or turnover fields")
        if row["tradestatus"] is not None:
            raise RuntimeError("halt repair refuses an existing trade status")
        assert_known_choice_stock_daily_vendor_version(str(row["vendor_version"] or ""))
    plan = {"schema": SCHEMA, "document_sha256": source_hash, "scope_before": before, "updates": updates}
    plan["plan_sha256"] = _canonical_sha256(plan)
    return plan


def _assert_scope_after(conn: duckdb.DuckDBPyConnection, *, plan: dict[str, Any]) -> None:
    changed_ids = {row["_rowid"] for row in plan["updates"]}
    expected = [dict(row) for row in plan["scope_before"]]
    for row in expected:
        if row["_rowid"] in changed_ids:
            row["tradestatus"] = "Suspended"
    if _canonical_sha256(_load_security_scope(conn)) != _canonical_sha256(expected):
        raise RuntimeError("halt repair changed fields or security dates outside the approved status scope")
