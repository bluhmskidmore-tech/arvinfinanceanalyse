from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date
from pathlib import Path
from typing import Any, cast

import duckdb

from backend.app.repositories.choice_stock_adapter import choice_stock_readiness_missing
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text
from backend.app.services.market_data_livermore_service import load_livermore_strategy_payload

RULE_VERSION = "rv_livermore_candidate_history_v1"
FORMULA_VERSION = "fv_livermore_candidate_forward_close_unadjusted_v1"
TABLE_HIST = "livermore_candidate_history"
TABLE_OBS = "choice_stock_daily_observation"
_MAX_CALENDAR_GAP_DAYS_NORMAL = 5
_INSERT_COLUMNS = (
    "snapshot_as_of_date",
    "stock_code",
    "stock_name",
    "candidate_rank",
    "sector_code",
    "sector_name",
    "selection_close",
    "forward_trade_date_1d",
    "forward_trade_date_5d",
    "forward_trade_date_20d",
    "return_1d",
    "return_5d",
    "return_20d",
    "data_status",
    "formula_version",
    "source_version",
    "vendor_version",
    "rule_version",
    "run_id",
)


def ensure_livermore_candidate_history_schema(conn: duckdb.DuckDBPyConnection) -> None:
    text = (REGISTRY_DIR / "28_livermore_candidate_history.sql").read_text(encoding="utf-8")
    for statement in parse_registry_sql_text(text):
        conn.execute(statement)


def materialize_livermore_candidate_history(duckdb_path: str, *, as_of_date: str | None = None) -> dict[str, object]:
    """Persist Livermore candidate rows with forward closes from choice_stock_daily_observation (task write path)."""
    parsed_as_of: date | None = None
    if as_of_date is not None:
        text = as_of_date.strip()
        if not text:
            raise ValueError("as_of_date cannot be blank.")
        parsed_as_of = date.fromisoformat(text[:10])

    duckdb_file = Path(duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(duckdb_file), read_only=False)
    skipped: list[str] = []
    run_id = ""
    try:
        ensure_livermore_candidate_history_schema(conn)
        payload, meta = load_livermore_strategy_payload(
            duckdb_path=str(duckdb_file),
            as_of_date=parsed_as_of,
            stock_readiness=choice_stock_readiness_missing(""),
        )
        snapshot_as_of = cast(str | None, payload.get("as_of_date"))
        if not snapshot_as_of:
            return {
                "status": "partial",
                "row_count": 0,
                "run_id": f"livermore_candidate_history:none:{uuid.uuid4().hex[:12]}",
                "source_version": str(meta.get("source_version") or ""),
                "vendor_version": str(meta.get("vendor_version") or ""),
                "rule_version": RULE_VERSION,
                "formula_version": FORMULA_VERSION,
                "skipped": ["missing_resolved_as_of_date"],
                "message": "Strategy payload has no resolved as_of_date; nothing written.",
            }

        stock_candidates_raw = payload.get("stock_candidates")
        items: list[dict[str, object]] = []
        if isinstance(stock_candidates_raw, dict):
            raw_items = stock_candidates_raw.get("items")
            if isinstance(raw_items, list):
                items = [cast(dict[str, object], x) for x in raw_items if isinstance(x, dict)]

        items_sorted = sorted(
            items,
            key=lambda row: (_safe_int(row.get("rank"), default=9999), str(row.get("stock_code") or "")),
        )

        source_version_meta = cast(str, meta.get("source_version"))
        lineage_payload = _build_vendor_payload(payload=payload, items=items_sorted, snapshot_as_of=snapshot_as_of)
        vendor_version = _build_vendor_version(lineage_payload)
        lineage_hash_source = hashlib.sha256(
            json.dumps(lineage_payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:12]
        row_source_version = f"sv_livermore_candidate_hist_{lineage_hash_source}"
        run_id = f"livermore_candidate_history:{snapshot_as_of}:{uuid.uuid4().hex[:12]}"

        observation_table_ok = TABLE_OBS in {r[0] for r in conn.execute("show tables").fetchall()}

        computed_rows: list[dict[str, object]] = []
        for item in items_sorted:
            code = _text(item.get("stock_code")).upper()
            if not code:
                skipped.append("blank_stock_code")
                continue
            name = _text(item.get("stock_name"))
            sect_c = _text(item.get("sector_code")) or None
            sect_n = _text(item.get("sector_name")) or None
            rank = _safe_int(item.get("rank"), default=1)
            if not observation_table_ok:
                skipped.append(f"{code}:missing_observation_table")
                continue

            computed = _forward_returns_for_candidate(
                conn,
                stock_code=code,
                snapshot_as_of_date=snapshot_as_of,
            )
            if computed is None:
                skipped.append(f"{code}:missing_selection_bar")
                continue

            computed_rows.append(
                {
                    "snapshot_as_of_date": snapshot_as_of,
                    "stock_code": code,
                    "stock_name": name if name else None,
                    "candidate_rank": rank,
                    "sector_code": sect_c if sect_c else None,
                    "sector_name": sect_n if sect_n else None,
                    **computed,
                    "formula_version": FORMULA_VERSION,
                    "source_version": row_source_version,
                    "vendor_version": vendor_version,
                    "rule_version": RULE_VERSION,
                    "run_id": run_id,
                }
            )

        transaction_started = False
        try:
            conn.execute("begin transaction")
            transaction_started = True
            conn.execute(f"delete from {TABLE_HIST} where snapshot_as_of_date = ?", [snapshot_as_of])
            if computed_rows:
                placeholders = ", ".join("?" for _ in _INSERT_COLUMNS)
                conn.executemany(
                    f"""
                    insert into {TABLE_HIST} ({", ".join(_INSERT_COLUMNS)})
                    values ({placeholders})
                    """,
                    [tuple(cast(Any, row[col]) for col in _INSERT_COLUMNS) for row in computed_rows],
                )
            conn.execute("commit")
            transaction_started = False
        except Exception:
            if transaction_started:
                conn.execute("rollback")
            raise

        status = "ok"
        if skipped and computed_rows:
            status = "partial"
        elif not computed_rows:
            status = "partial"

        return {
            "status": status,
            "row_count": len(computed_rows),
            "run_id": run_id,
            "snapshot_as_of_date": snapshot_as_of,
            "source_version": row_source_version,
            "source_version_meta": source_version_meta,
            "vendor_version": vendor_version,
            "rule_version": RULE_VERSION,
            "formula_version": FORMULA_VERSION,
            "skipped": skipped,
            "skipped_count": len(skipped),
        }
    except Exception:
        try:
            conn.execute("rollback")
        except Exception:
            pass
        raise
    finally:
        conn.close()


def _build_vendor_payload(
    *,
    payload: dict[str, object],
    items: list[dict[str, object]],
    snapshot_as_of: str,
) -> dict[str, object]:
    return {
        "snapshot_as_of_date": snapshot_as_of,
        "strategy_as_of_requested": payload.get("requested_as_of_date"),
        "candidate_stock_codes": [_text(i.get("stock_code")).upper() for i in items if _text(i.get("stock_code"))],
        "market_gate_state": (_mapping(payload.get("market_gate")).get("state")),
    }


def _build_vendor_version(lineage_payload: dict[str, object]) -> str:
    digest = hashlib.sha256(
        json.dumps(lineage_payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:12]
    return f"vv_livermore_candidate_history_{digest}"


def _forward_returns_for_candidate(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str,
    snapshot_as_of_date: str,
) -> dict[str, object] | None:
    sel = conn.execute(
        f"""
        select close_value
        from {TABLE_OBS}
        where stock_code = ? and trade_date = ? and close_value is not null
        """,
        [stock_code, snapshot_as_of_date],
    ).fetchone()
    if sel is None or sel[0] is None:
        return None

    selection_close = float(sel[0])
    forward_bars = conn.execute(
        f"""
        select trade_date, close_value
        from {TABLE_OBS}
        where stock_code = ?
          and cast(trade_date as date) > cast(? as date)
          and close_value is not null
        order by trade_date
        """,
        [stock_code, snapshot_as_of_date],
    ).fetchall()

    series: list[tuple[str, float]] = []
    for trade_date_raw, close_raw in forward_bars:
        iso = _normalize_trade_date_iso(trade_date_raw)
        if iso is None or close_raw is None:
            continue
        series.append((iso, float(close_raw)))

    all_rows = conn.execute(
        f"""
        select trade_date from {TABLE_OBS}
        where stock_code = ? and trade_date >= ? and close_value is not null
        order by trade_date
        """,
        [stock_code, snapshot_as_of_date],
    ).fetchall()
    ordered_dates = [_normalize_trade_date_iso(r[0]) for r in all_rows]
    ordered_dates = [d for d in ordered_dates if d is not None]
    has_gap = False
    for a, b in zip(ordered_dates, ordered_dates[1:], strict=False):
        if _calendar_gap_days(a, b) > _MAX_CALENDAR_GAP_DAYS_NORMAL:
            has_gap = True
            break

    d1 = series[0] if len(series) >= 1 else None
    d5 = series[4] if len(series) >= 5 else None
    d20 = series[19] if len(series) >= 20 else None

    r1 = (d1[1] - selection_close) / selection_close if d1 else None
    r5 = (d5[1] - selection_close) / selection_close if d5 else None
    r20 = (d20[1] - selection_close) / selection_close if d20 else None

    has_all = r1 is not None and r5 is not None and r20 is not None
    if has_gap:
        data_status = "partial_halt"
    elif has_all:
        data_status = "complete"
    else:
        data_status = "pending"

    return {
        "selection_close": selection_close,
        "forward_trade_date_1d": d1[0] if d1 else None,
        "forward_trade_date_5d": d5[0] if d5 else None,
        "forward_trade_date_20d": d20[0] if d20 else None,
        "return_1d": r1,
        "return_5d": r5,
        "return_20d": r20,
        "data_status": data_status,
    }


def _calendar_gap_days(prev_iso: str, next_iso: str) -> int:
    return (date.fromisoformat(next_iso[:10]) - date.fromisoformat(prev_iso[:10])).days


def _normalize_trade_date_iso(value: object) -> str | None:
    text = _text(value)
    if len(text) >= 10:
        fragment = text[:10].replace("/", "-")
        try:
            return date.fromisoformat(fragment).isoformat()
        except ValueError:
            return None
    return None


def _mapping(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    return {}


def _text(value: object) -> str:
    return str(value or "").strip()


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default
