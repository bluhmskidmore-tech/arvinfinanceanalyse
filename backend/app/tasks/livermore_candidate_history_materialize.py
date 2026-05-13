from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date
from pathlib import Path
from typing import Any, cast

import duckdb

from backend.app.governance.settings import get_settings
from backend.app.repositories.choice_stock_adapter import ChoiceStockReadiness, load_choice_stock_readiness
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text
from backend.app.services.market_data_livermore_service import load_livermore_strategy_payload

RULE_VERSION = "rv_livermore_candidate_history_v1"
FORMULA_VERSION = "fv_livermore_candidate_forward_close_unadjusted_v1"
TABLE_HIST = "livermore_candidate_history"
TABLE_OBS = "choice_stock_daily_observation"
_MAX_CALENDAR_GAP_DAYS_NORMAL = 5
_MIN_FORWARD_BARS_FOR_HALT_FALLBACK = 5
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
    "signal_kind",
    "theme_key",
    "theme_name",
    "theme_source_kind",
    "theme_rank",
    "stock_rank_in_theme",
    "sector_rank",
    "strength_pctchange",
    "strength_turn",
    "strength_amplitude",
    "close_strength",
    "closed_up_limit",
    "signal_evidence_json",
)
_ADDED_COLUMN_SQL = (
    ("signal_kind", "varchar"),
    ("theme_key", "varchar"),
    ("theme_name", "varchar"),
    ("theme_source_kind", "varchar"),
    ("theme_rank", "integer"),
    ("stock_rank_in_theme", "integer"),
    ("sector_rank", "integer"),
    ("strength_pctchange", "double"),
    ("strength_turn", "double"),
    ("strength_amplitude", "double"),
    ("close_strength", "double"),
    ("closed_up_limit", "boolean"),
    ("signal_evidence_json", "varchar"),
)


def ensure_livermore_candidate_history_schema(conn: duckdb.DuckDBPyConnection) -> None:
    text = (REGISTRY_DIR / "28_livermore_candidate_history.sql").read_text(encoding="utf-8")
    for statement in parse_registry_sql_text(text):
        conn.execute(statement)
    existing = {str(row[1]).lower() for row in conn.execute(f"pragma table_info('{TABLE_HIST}')").fetchall()}
    for column, definition in _ADDED_COLUMN_SQL:
        if column not in existing:
            conn.execute(f"alter table {TABLE_HIST} add column {column} {definition}")


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
    skipped: list[str] = []

    payload, meta = load_livermore_strategy_payload(
        duckdb_path=str(duckdb_file),
        as_of_date=parsed_as_of,
        stock_readiness=_load_configured_stock_readiness(),
        backfill_mode=True,
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

    items_sorted = _build_signal_rows(payload)

    source_version_meta = cast(str, meta.get("source_version"))
    lineage_payload = _build_vendor_payload(payload=payload, items=items_sorted, snapshot_as_of=snapshot_as_of)
    vendor_version = _build_vendor_version(lineage_payload)
    lineage_hash_source = hashlib.sha256(
        json.dumps(lineage_payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:12]
    row_source_version = f"sv_livermore_candidate_hist_{lineage_hash_source}"
    run_id = f"livermore_candidate_history:{snapshot_as_of}:{uuid.uuid4().hex[:12]}"

    conn = duckdb.connect(str(duckdb_file), read_only=False)
    try:
        ensure_livermore_candidate_history_schema(conn)
        observation_table_ok = TABLE_OBS in {r[0] for r in conn.execute("show tables").fetchall()}

        computed_rows: list[dict[str, object]] = []
        if not items_sorted:
            skipped.append("no_strategy_signals")
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
                    "signal_kind": _text(item.get("signal_kind")) or "stock_candidate",
                    "theme_key": _optional_text(item.get("theme_key")),
                    "theme_name": _optional_text(item.get("theme_name")),
                    "theme_source_kind": _optional_text(item.get("theme_source_kind")),
                    "theme_rank": _safe_int_or_none(item.get("theme_rank")),
                    "stock_rank_in_theme": _safe_int_or_none(item.get("stock_rank_in_theme")),
                    "sector_rank": _safe_int_or_none(item.get("sector_rank")),
                    "strength_pctchange": _safe_float_or_none(item.get("strength_pctchange")),
                    "strength_turn": _safe_float_or_none(item.get("strength_turn")),
                    "strength_amplitude": _safe_float_or_none(item.get("strength_amplitude")),
                    "close_strength": _safe_float_or_none(item.get("close_strength")),
                    "closed_up_limit": _safe_bool_or_none(item.get("closed_up_limit")),
                    "signal_evidence_json": _json_dump(item.get("signal_evidence")),
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
    finally:
        conn.close()


def backfill_livermore_candidate_history(
    duckdb_path: str,
    *,
    start_date: str,
    end_date: str,
) -> dict[str, object]:
    """Materialize candidate history for every observed trade date in a bounded date range."""
    parsed_start = date.fromisoformat(start_date.strip()[:10])
    parsed_end = date.fromisoformat(end_date.strip()[:10])
    if parsed_start > parsed_end:
        raise ValueError("start_date must be on or before end_date.")

    duckdb_file = Path(duckdb_path)
    trade_dates = _available_observation_trade_dates(
        duckdb_file,
        start_date=parsed_start.isoformat(),
        end_date=parsed_end.isoformat(),
    )
    if not trade_dates:
        return {
            "status": "partial",
            "start_date": parsed_start.isoformat(),
            "end_date": parsed_end.isoformat(),
            "processed_date_count": 0,
            "row_count": 0,
            "skipped_count": 1,
            "dates": [],
            "skipped": ["missing_observation_trade_dates"],
            "rule_version": RULE_VERSION,
            "formula_version": FORMULA_VERSION,
        }

    date_results: list[dict[str, object]] = []
    total_rows = 0
    total_skipped = 0
    partial_dates = 0
    for trade_date in trade_dates:
        result = materialize_livermore_candidate_history(str(duckdb_file), as_of_date=trade_date)
        row_count = _safe_int(result.get("row_count"), default=0)
        skipped_count = _safe_int(result.get("skipped_count"), default=0)
        status = _text(result.get("status")) or "partial"
        total_rows += row_count
        total_skipped += skipped_count
        if status != "ok":
            partial_dates += 1
        date_results.append(
            {
                "as_of_date": trade_date,
                "status": status,
                "row_count": row_count,
                "skipped_count": skipped_count,
                "skipped": _string_list(result.get("skipped")),
            }
        )

    return {
        "status": "ok" if partial_dates == 0 else "partial",
        "start_date": parsed_start.isoformat(),
        "end_date": parsed_end.isoformat(),
        "processed_date_count": len(date_results),
        "row_count": total_rows,
        "skipped_count": total_skipped,
        "partial_date_count": partial_dates,
        "dates": date_results,
        "rule_version": RULE_VERSION,
        "formula_version": FORMULA_VERSION,
    }


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
        "signal_kinds": sorted({_text(i.get("signal_kind")) or "stock_candidate" for i in items}),
        "market_gate_state": (_mapping(payload.get("market_gate")).get("state")),
    }


def _available_observation_trade_dates(
    duckdb_file: Path,
    *,
    start_date: str,
    end_date: str,
) -> list[str]:
    if not duckdb_file.exists():
        return []
    conn = duckdb.connect(str(duckdb_file), read_only=True)
    try:
        tables = {r[0] for r in conn.execute("show tables").fetchall()}
        if TABLE_OBS not in tables:
            return []
        rows = conn.execute(
            f"""
            select distinct trade_date
            from {TABLE_OBS}
            where cast(trade_date as date) >= cast(? as date)
              and cast(trade_date as date) <= cast(? as date)
            order by trade_date
            """,
            [start_date, end_date],
        ).fetchall()
    finally:
        conn.close()
    return [iso for row in rows if (iso := _normalize_trade_date_iso(row[0])) is not None]


def _load_configured_stock_readiness() -> ChoiceStockReadiness:
    settings = get_settings()
    return load_choice_stock_readiness(settings.choice_stock_catalog_file)


def _build_signal_rows(payload: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    market_state = _optional_text(_mapping(payload.get("market_gate")).get("state"))
    stock_candidates_raw = payload.get("stock_candidates")
    if isinstance(stock_candidates_raw, dict):
        raw_items = stock_candidates_raw.get("items")
        if isinstance(raw_items, list):
            for raw in raw_items:
                if not isinstance(raw, dict):
                    continue
                item = cast(dict[str, object], raw)
                rank = _safe_int(item.get("rank"), default=1)
                rows.append(
                    {
                        "signal_kind": "stock_candidate",
                        "rank": rank,
                        "stock_code": item.get("stock_code"),
                        "stock_name": item.get("stock_name"),
                        "sector_code": item.get("sector_code"),
                        "sector_name": item.get("sector_name"),
                        "sector_rank": item.get("sector_rank"),
                        "strength_pctchange": item.get("pctchange"),
                        "strength_turn": item.get("turn"),
                        "strength_amplitude": item.get("amplitude"),
                        "close_strength": item.get("close_strength"),
                        "closed_up_limit": item.get("closed_up_limit"),
                        "signal_evidence": {
                            "signal_kind": "stock_candidate",
                            "market_state": market_state,
                            "rank": rank,
                            "stock_code": item.get("stock_code"),
                            "sector_code": item.get("sector_code"),
                        },
                    }
                )

    theme_breakout_raw = payload.get("theme_breakout")
    if isinstance(theme_breakout_raw, dict):
        raw_themes = theme_breakout_raw.get("items")
        if isinstance(raw_themes, list):
            for raw_theme in raw_themes:
                if not isinstance(raw_theme, dict):
                    continue
                theme = cast(dict[str, object], raw_theme)
                theme_rank = _safe_int(theme.get("rank"), default=9999)
                raw_stocks = theme.get("items")
                if not isinstance(raw_stocks, list):
                    continue
                for index, raw_stock in enumerate(raw_stocks, start=1):
                    if not isinstance(raw_stock, dict):
                        continue
                    stock = cast(dict[str, object], raw_stock)
                    stock_rank = index
                    rows.append(
                        {
                            "signal_kind": "theme_breakout",
                            "rank": stock_rank,
                            "stock_code": stock.get("stock_code"),
                            "stock_name": stock.get("stock_name"),
                            "sector_code": stock.get("sector_code"),
                            "sector_name": stock.get("sector_name"),
                            "theme_key": theme.get("theme_key"),
                            "theme_name": theme.get("theme_name"),
                            "theme_source_kind": theme.get("source_kind"),
                            "theme_rank": theme_rank,
                            "stock_rank_in_theme": stock_rank,
                            "sector_rank": stock.get("sector_rank", theme.get("parent_sector_rank")),
                            "strength_pctchange": stock.get("pctchange"),
                            "strength_turn": stock.get("turn"),
                            "strength_amplitude": stock.get("amplitude"),
                            "close_strength": stock.get("close_strength"),
                            "closed_up_limit": stock.get("closed_up_limit"),
                            "signal_evidence": {
                                "signal_kind": "theme_breakout",
                                "market_state": market_state,
                                "theme_key": theme.get("theme_key"),
                                "theme_name": theme.get("theme_name"),
                                "theme_source_kind": theme.get("source_kind"),
                                "theme_rank": theme_rank,
                                "strong_stock_count": theme.get("strong_stock_count"),
                                "limit_stock_count": theme.get("limit_stock_count"),
                                "avg_pctchange": theme.get("avg_pctchange"),
                                "avg_turn": theme.get("avg_turn"),
                                "stock_rank_in_theme": stock_rank,
                                "stock_code": stock.get("stock_code"),
                            },
                        }
                    )

    factor_screen_raw = payload.get("factor_screen_candidates")
    if isinstance(factor_screen_raw, dict):
        raw_items = factor_screen_raw.get("items")
        if isinstance(raw_items, list):
            for raw in raw_items:
                if not isinstance(raw, dict):
                    continue
                item = cast(dict[str, object], raw)
                rank = _safe_int(item.get("rank"), default=1)
                rows.append(
                    {
                        "signal_kind": "factor_screen",
                        "rank": rank,
                        "stock_code": item.get("stock_code"),
                        "stock_name": item.get("stock_name"),
                        "sector_code": item.get("sector_code"),
                        "sector_name": item.get("sector_name"),
                        "sector_rank": None,
                        "signal_evidence": {
                            "signal_kind": "factor_screen",
                            "market_state": market_state,
                            "rank": rank,
                            "stock_code": item.get("stock_code"),
                            "sector_code": item.get("sector_code"),
                            "industry": item.get("industry"),
                            "score": item.get("score"),
                            "pe": item.get("pe"),
                            "pb": item.get("pb"),
                            "roe": item.get("roe"),
                            "gross_margin": item.get("gross_margin"),
                            "three_month_return": item.get("three_month_return"),
                            "twelve_month_return": item.get("twelve_month_return"),
                            "dividend_yield": item.get("dividend_yield"),
                        },
                    }
                )

    mean_reversion_raw = payload.get("mean_reversion_candidates")
    if isinstance(mean_reversion_raw, dict):
        raw_items = mean_reversion_raw.get("items")
        if isinstance(raw_items, list):
            for raw in raw_items:
                if not isinstance(raw, dict):
                    continue
                item = cast(dict[str, object], raw)
                rank = _safe_int(item.get("rank"), default=1)
                rows.append(
                    {
                        "signal_kind": "mean_reversion",
                        "rank": rank,
                        "stock_code": item.get("stock_code"),
                        "stock_name": item.get("stock_name"),
                        "sector_code": item.get("sector_code"),
                        "sector_name": item.get("sector_name"),
                        "strength_pctchange": item.get("drawdown_20d"),
                        "strength_turn": item.get("vol_ratio"),
                        "close_strength": item.get("close_strength"),
                        "signal_evidence": {
                            "signal_kind": "mean_reversion",
                            "market_state": market_state,
                            "rank": rank,
                            "stock_code": item.get("stock_code"),
                            "sector_code": item.get("sector_code"),
                            "drawdown_20d": item.get("drawdown_20d"),
                            "drawdown_60d": item.get("drawdown_60d"),
                            "ma5": item.get("ma5"),
                            "ma10": item.get("ma10"),
                            "vol_ratio": item.get("vol_ratio"),
                            "score": item.get("score"),
                        },
                    }
                )

    signal_order = {
        "stock_candidate": 0,
        "theme_breakout": 1,
        "factor_screen": 2,
        "mean_reversion": 3,
    }
    return sorted(
        rows,
        key=lambda row: (
            signal_order.get(_text(row.get("signal_kind")), 99),
            _safe_int(row.get("theme_rank"), default=9999),
            _safe_int(row.get("rank"), default=9999),
            str(row.get("stock_code") or ""),
        ),
    )


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
    has_stock_gap = False
    has_leading_sparse_gap_without_market_context = False
    for a, b in zip(ordered_dates, ordered_dates[1:], strict=False):
        if _calendar_gap_days(a, b) > _MAX_CALENDAR_GAP_DAYS_NORMAL:
            if _has_market_dates_between(conn, start_date=a, end_date=b):
                has_stock_gap = True
                break
            if a == snapshot_as_of_date:
                has_leading_sparse_gap_without_market_context = True

    d1 = series[0] if len(series) >= 1 else None
    d5 = series[4] if len(series) >= 5 else None
    d20 = series[19] if len(series) >= 20 else None

    r1 = (d1[1] - selection_close) / selection_close if d1 else None
    r5 = (d5[1] - selection_close) / selection_close if d5 else None
    r20 = (d20[1] - selection_close) / selection_close if d20 else None

    has_all = r1 is not None and r5 is not None and r20 is not None
    if has_stock_gap:
        data_status = "partial_halt"
    elif has_all:
        data_status = "complete"
    elif has_leading_sparse_gap_without_market_context and len(series) >= _MIN_FORWARD_BARS_FOR_HALT_FALLBACK:
        data_status = "partial_halt"
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


def _has_market_dates_between(
    conn: duckdb.DuckDBPyConnection,
    *,
    start_date: str,
    end_date: str,
) -> bool:
    row = conn.execute(
        f"""
        select 1
        from {TABLE_OBS}
        where cast(trade_date as date) > cast(? as date)
          and cast(trade_date as date) < cast(? as date)
          and close_value is not null
        limit 1
        """,
        [start_date, end_date],
    ).fetchone()
    return row is not None


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


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := _text(item))]


def _optional_text(value: object) -> str | None:
    text = _text(value)
    return text or None


def _text(value: object) -> str:
    return str(value or "").strip()


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default


def _safe_int_or_none(value: object) -> int | None:
    text = _text(value)
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _safe_float_or_none(value: object) -> float | None:
    text = _text(value)
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _safe_bool_or_none(value: object) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    text = _text(value).lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return None


def _json_dump(value: object) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True, default=str)
