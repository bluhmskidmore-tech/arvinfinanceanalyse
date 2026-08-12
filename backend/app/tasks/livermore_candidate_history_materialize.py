from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date
from pathlib import Path
from typing import Any, cast

import duckdb
from backend.app.core_finance.adjusted_returns import (
    PRICE_ADJUSTMENT_MODE,
    STOCK_ADJUSTMENT_FACTOR_TABLE,
    adjusted_return,
    ensure_stock_adjustment_factor_schema,
    factors_changed,
    net_return_after_costs,
)
from backend.app.core_finance.field_normalization import is_tradestatus_halted
from backend.app.core_finance.portfolio_paths import (
    TABLE_LIMIT_PRICE,
    resolve_limit_prices,
)
from backend.app.core_finance.strategy_policy import POLICY
from backend.app.governance.locks import LockDefinition, acquire_lock
from backend.app.governance.settings import get_settings
from backend.app.repositories.choice_stock_adapter import ChoiceStockReadiness, load_choice_stock_readiness
from backend.app.schema_registry.duckdb_loader import REGISTRY_DIR, parse_registry_sql_text
from backend.app.services.market_data_livermore_service import (
    EXECUTION_STOCK_CANDIDATE_POLICY,
    load_livermore_strategy_payload,
)

LIVERMORE_CANDIDATE_HISTORY_LOCK = LockDefinition(
    key="lock:duckdb:livermore-candidate-history",
    ttl_seconds=600,
)
RULE_VERSION = "rv_livermore_candidate_history_v1"
FORMULA_VERSION = "fv_livermore_candidate_forward_close_dual_adjust_v2"
# v3: return_*_net_adj uses multiplicative cost netting ((1+r)*(1-c)-1).
# v4: return_*_net uses the same multiplicative helper (no longer additive r-c).
# v5: halted 判定统一到共享互补口径（is_tradestatus_halted）——"停牌一天"/
# "连续停牌"等非空非可交易值判停牌：entry 落停牌值日记 entry_halted，
# 卖出顺延到首个可卖 bar（旧完整匹配词表把这些日误判可交易）。
EXECUTION_FORMULA_VERSION = "fv_livermore_candidate_execution_dual_adjust_v5"
TABLE_HIST = "livermore_candidate_history"
TABLE_EXECUTION_HIST = "livermore_candidate_execution_history"
TABLE_STOCK_UNIVERSE = "livermore_stock_candidate_universe_history"
TABLE_OBS = "choice_stock_daily_observation"
_MAX_CALENDAR_GAP_DAYS_NORMAL = 5
_MIN_FORWARD_BARS_FOR_HALT_FALLBACK = 5
BUY_COST_RATE = POLICY.buy_cost_rate
SELL_COST_RATE = POLICY.sell_cost_rate
SLIPPAGE_RATE = POLICY.slippage_rate
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
    "forward_trade_date_10d",
    "forward_trade_date_20d",
    "return_1d",
    "return_5d",
    "return_10d",
    "return_20d",
    "return_1d_adj",
    "return_5d_adj",
    "return_10d_adj",
    "return_20d_adj",
    "ex_div_in_window",
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
    "market_state",
    "abnormal_turnover",
    "gap_norm",
    "breakout_extension_norm",
    "breakout_level",
    "ema10",
    "ma20",
    "ma60",
    "ma120",
    "strength_pctchange",
    "strength_turn",
    "strength_amplitude",
    "close_strength",
    "closed_up_limit",
    "signal_evidence_json",
)
_UNIVERSE_INSERT_COLUMNS = (
    "snapshot_as_of_date",
    "stock_code",
    "stock_name",
    "sector_code",
    "sector_name",
    "sector_rank",
    "selection_close",
    "close_strength",
    "gap_norm",
    "breakout_extension_norm",
    "abnormal_turnover",
    "breakout_level",
    "ema10",
    "ma20",
    "ma60",
    "ma120",
    "old_rank",
    "new_rank",
    "eligible_before_truncation",
    "selected_old_top6",
    "selected_new_top6",
    "forward_trade_date_1d",
    "forward_trade_date_5d",
    "forward_trade_date_10d",
    "forward_trade_date_20d",
    "return_1d",
    "return_5d",
    "return_10d",
    "return_20d",
    "return_1d_adj",
    "return_5d_adj",
    "return_10d_adj",
    "return_20d_adj",
    "ex_div_in_window",
    "market_state",
    "data_status",
    "formula_version",
    "source_version",
    "vendor_version",
    "rule_version",
    "run_id",
    "evidence_json",
)
_EXECUTION_INSERT_COLUMNS = (
    "signal_date",
    "stock_code",
    "stock_name",
    "signal_kind",
    "candidate_rank",
    "market_state",
    "signal_close",
    "entry_date",
    "entry_price",
    "entry_price_kind",
    "entry_executable",
    "entry_block_reason",
    "entry_ex_div",
    "exit_date_1d",
    "exit_price_1d",
    "return_1d_gross",
    "return_1d_net",
    "return_1d_gross_adj",
    "return_1d_net_adj",
    "exit_date_5d",
    "exit_price_5d",
    "return_5d_gross",
    "return_5d_net",
    "return_5d_gross_adj",
    "return_5d_net_adj",
    "exit_date_10d",
    "exit_price_10d",
    "return_10d_gross",
    "return_10d_net",
    "return_10d_gross_adj",
    "return_10d_net_adj",
    "exit_date_20d",
    "exit_price_20d",
    "return_20d_gross",
    "return_20d_net",
    "return_20d_gross_adj",
    "return_20d_net_adj",
    "buy_cost_bps",
    "sell_cost_bps",
    "slippage_bps",
    "price_adjustment_mode",
    "data_status",
    "formula_version",
    "run_id",
    "evidence_json",
)
_ADDED_COLUMN_SQL = (
    ("forward_trade_date_10d", "varchar"),
    ("return_10d", "double"),
    ("return_1d_adj", "double"),
    ("return_5d_adj", "double"),
    ("return_10d_adj", "double"),
    ("return_20d_adj", "double"),
    ("ex_div_in_window", "boolean"),
    ("signal_kind", "varchar"),
    ("theme_key", "varchar"),
    ("theme_name", "varchar"),
    ("theme_source_kind", "varchar"),
    ("theme_rank", "integer"),
    ("stock_rank_in_theme", "integer"),
    ("sector_rank", "integer"),
    ("market_state", "varchar"),
    ("abnormal_turnover", "double"),
    ("gap_norm", "double"),
    ("breakout_extension_norm", "double"),
    ("breakout_level", "double"),
    ("ema10", "double"),
    ("ma20", "double"),
    ("ma60", "double"),
    ("ma120", "double"),
    ("strength_pctchange", "double"),
    ("strength_turn", "double"),
    ("strength_amplitude", "double"),
    ("close_strength", "double"),
    ("closed_up_limit", "boolean"),
    ("signal_evidence_json", "varchar"),
)
_UNIVERSE_ADDED_COLUMN_SQL = (
    ("forward_trade_date_10d", "varchar"),
    ("return_10d", "double"),
    ("return_1d_adj", "double"),
    ("return_5d_adj", "double"),
    ("return_10d_adj", "double"),
    ("return_20d_adj", "double"),
    ("ex_div_in_window", "boolean"),
    ("old_rank", "integer"),
    ("new_rank", "integer"),
    ("eligible_before_truncation", "boolean"),
    ("selected_old_top6", "boolean"),
    ("selected_new_top6", "boolean"),
    ("evidence_json", "varchar"),
)
_EXECUTION_ADDED_COLUMN_SQL = (
    ("entry_ex_div", "boolean"),
    ("return_1d_gross_adj", "double"),
    ("return_1d_net_adj", "double"),
    ("return_5d_gross_adj", "double"),
    ("return_5d_net_adj", "double"),
    ("return_10d_gross_adj", "double"),
    ("return_10d_net_adj", "double"),
    ("return_20d_gross_adj", "double"),
    ("return_20d_net_adj", "double"),
)
_UNIVERSE_BASE_TABLE_SQL = f"""
create table if not exists {TABLE_STOCK_UNIVERSE} (
  snapshot_as_of_date varchar,
  stock_code varchar,
  stock_name varchar,
  sector_code varchar,
  sector_name varchar,
  sector_rank integer,
  selection_close double,
  close_strength double,
  gap_norm double,
  breakout_extension_norm double,
  abnormal_turnover double,
  breakout_level double,
  ema10 double,
  ma20 double,
  ma60 double,
  ma120 double,
  old_rank integer,
  new_rank integer,
  eligible_before_truncation boolean,
  selected_old_top6 boolean,
  selected_new_top6 boolean,
  forward_trade_date_1d varchar,
  forward_trade_date_5d varchar,
  forward_trade_date_20d varchar,
  return_1d double,
  return_5d double,
  return_20d double,
  return_1d_adj double,
  return_5d_adj double,
  return_10d_adj double,
  return_20d_adj double,
  ex_div_in_window boolean,
  market_state varchar,
  data_status varchar,
  formula_version varchar,
  source_version varchar,
  vendor_version varchar,
  rule_version varchar,
  run_id varchar,
  evidence_json varchar
)
"""
_EXECUTION_BASE_TABLE_SQL = f"""
create table if not exists {TABLE_EXECUTION_HIST} (
  signal_date varchar,
  stock_code varchar,
  stock_name varchar,
  signal_kind varchar,
  candidate_rank integer,
  market_state varchar,
  signal_close double,
  entry_date varchar,
  entry_price double,
  entry_price_kind varchar,
  entry_executable boolean,
  entry_block_reason varchar,
  entry_ex_div boolean,
  exit_date_1d varchar,
  exit_price_1d double,
  return_1d_gross double,
  return_1d_net double,
  return_1d_gross_adj double,
  return_1d_net_adj double,
  exit_date_5d varchar,
  exit_price_5d double,
  return_5d_gross double,
  return_5d_net double,
  return_5d_gross_adj double,
  return_5d_net_adj double,
  exit_date_10d varchar,
  exit_price_10d double,
  return_10d_gross double,
  return_10d_net double,
  return_10d_gross_adj double,
  return_10d_net_adj double,
  exit_date_20d varchar,
  exit_price_20d double,
  return_20d_gross double,
  return_20d_net double,
  return_20d_gross_adj double,
  return_20d_net_adj double,
  buy_cost_bps double,
  sell_cost_bps double,
  slippage_bps double,
  price_adjustment_mode varchar,
  data_status varchar,
  formula_version varchar,
  run_id varchar,
  evidence_json varchar
)
"""


def ensure_livermore_candidate_history_schema(conn: duckdb.DuckDBPyConnection) -> None:
    text = (REGISTRY_DIR / "28_livermore_candidate_history.sql").read_text(encoding="utf-8")
    for statement in parse_registry_sql_text(text):
        conn.execute(statement)
    ensure_stock_adjustment_factor_schema(conn)
    existing = {str(row[1]).lower() for row in conn.execute(f"pragma table_info('{TABLE_HIST}')").fetchall()}
    for column, definition in _ADDED_COLUMN_SQL:
        if column not in existing:
            conn.execute(f"alter table {TABLE_HIST} add column {column} {definition}")
    conn.execute(_UNIVERSE_BASE_TABLE_SQL)
    universe_existing = {
        str(row[1]).lower() for row in conn.execute(f"pragma table_info('{TABLE_STOCK_UNIVERSE}')").fetchall()
    }
    for column, definition in _UNIVERSE_ADDED_COLUMN_SQL:
        if column not in universe_existing:
            conn.execute(f"alter table {TABLE_STOCK_UNIVERSE} add column {column} {definition}")
    conn.execute(_EXECUTION_BASE_TABLE_SQL)
    execution_existing = {
        str(row[1]).lower() for row in conn.execute(f"pragma table_info('{TABLE_EXECUTION_HIST}')").fetchall()
    }
    for column, definition in _EXECUTION_ADDED_COLUMN_SQL:
        if column not in execution_existing:
            conn.execute(f"alter table {TABLE_EXECUTION_HIST} add column {column} {definition}")


def materialize_livermore_candidate_history(
    duckdb_path: str,
    *,
    as_of_date: str | None = None,
    stock_candidate_policy: str | None = None,
    _schema_ready: bool = False,
) -> dict[str, object]:
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
        stock_candidate_policy=stock_candidate_policy,
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
            "stock_candidate_policy": stock_candidate_policy or EXECUTION_STOCK_CANDIDATE_POLICY,
            "message": "Strategy payload has no resolved as_of_date; nothing written.",
        }

    items_sorted = _build_signal_rows(payload)
    universe_items = _build_stock_candidate_universe_rows(payload)

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
        if not _schema_ready:
            ensure_livermore_candidate_history_schema(conn)
        observation_table_ok = TABLE_OBS in {r[0] for r in conn.execute("show tables").fetchall()}

        computed_rows: list[dict[str, object]] = []
        computed_universe_rows: list[dict[str, object]] = []
        computed_execution_rows: list[dict[str, object]] = []
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
                    "market_state": _row_market_state(item),
                    "abnormal_turnover": _safe_float_or_none(item.get("abnormal_turnover")),
                    "gap_norm": _safe_float_or_none(item.get("gap_norm")),
                    "breakout_extension_norm": _safe_float_or_none(item.get("breakout_extension_norm")),
                    "breakout_level": _safe_float_or_none(item.get("breakout_level")),
                    "ema10": _safe_float_or_none(item.get("ema10")),
                    "ma20": _safe_float_or_none(item.get("ma20")),
                    "ma60": _safe_float_or_none(item.get("ma60")),
                    "ma120": _safe_float_or_none(item.get("ma120")),
                    "strength_pctchange": _safe_float_or_none(item.get("strength_pctchange")),
                    "strength_turn": _safe_float_or_none(item.get("strength_turn")),
                    "strength_amplitude": _safe_float_or_none(item.get("strength_amplitude")),
                    "close_strength": _safe_float_or_none(item.get("close_strength")),
                    "closed_up_limit": _safe_bool_or_none(item.get("closed_up_limit")),
                    "signal_evidence_json": _json_dump(
                        _evidence_with_adjustment(
                            item.get("signal_evidence"),
                            computed.get("adjustment_evidence"),
                        )
                    ),
                }
            )
            execution = _execution_returns_for_candidate(
                conn,
                stock_code=code,
                snapshot_as_of_date=snapshot_as_of,
            )
            if execution is not None:
                computed_execution_rows.append(
                    {
                        "signal_date": snapshot_as_of,
                        "stock_code": code,
                        "stock_name": name if name else None,
                        "signal_kind": _text(item.get("signal_kind")) or "stock_candidate",
                        "candidate_rank": rank,
                        "market_state": _row_market_state(item),
                        **execution,
                        "formula_version": EXECUTION_FORMULA_VERSION,
                        "run_id": run_id,
                    }
                )

        if universe_items and observation_table_ok:
            for item in universe_items:
                code = _text(item.get("stock_code")).upper()
                if not code:
                    skipped.append("universe:blank_stock_code")
                    continue
                computed = _forward_returns_for_candidate(
                    conn,
                    stock_code=code,
                    snapshot_as_of_date=snapshot_as_of,
                )
                if computed is None:
                    skipped.append(f"{code}:universe_missing_selection_bar")
                    continue
                computed_universe_rows.append(
                    {
                        "snapshot_as_of_date": snapshot_as_of,
                        "stock_code": code,
                        "stock_name": _optional_text(item.get("stock_name")),
                        "sector_code": _optional_text(item.get("sector_code")),
                        "sector_name": _optional_text(item.get("sector_name")),
                        "sector_rank": _safe_int_or_none(item.get("sector_rank")),
                        **computed,
                        "close_strength": _safe_float_or_none(item.get("close_strength")),
                        "gap_norm": _safe_float_or_none(item.get("gap_norm")),
                        "breakout_extension_norm": _safe_float_or_none(item.get("breakout_extension_norm")),
                        "abnormal_turnover": _safe_float_or_none(item.get("abnormal_turnover")),
                        "breakout_level": _safe_float_or_none(item.get("breakout_level")),
                        "ema10": _safe_float_or_none(item.get("ema10")),
                        "ma20": _safe_float_or_none(item.get("ma20")),
                        "ma60": _safe_float_or_none(item.get("ma60")),
                        "ma120": _safe_float_or_none(item.get("ma120")),
                        "old_rank": _safe_int_or_none(item.get("old_rank")),
                        "new_rank": _safe_int_or_none(item.get("new_rank")),
                        "eligible_before_truncation": _safe_bool(item.get("eligible_before_truncation"), default=True),
                        "selected_old_top6": _safe_bool(item.get("selected_old_top6"), default=False),
                        "selected_new_top6": _safe_bool(item.get("selected_new_top6"), default=False),
                        "market_state": _optional_text(item.get("market_state")) or _payload_market_state(payload),
                        "formula_version": FORMULA_VERSION,
                        "source_version": row_source_version,
                        "vendor_version": vendor_version,
                        "rule_version": RULE_VERSION,
                        "run_id": run_id,
                        "evidence_json": _json_dump(
                            _evidence_with_adjustment(
                                _stock_candidate_universe_evidence(item, payload=payload),
                                computed.get("adjustment_evidence"),
                            )
                        ),
                    }
                )
        elif universe_items:
            skipped.append("universe:missing_observation_table")

        computed_execution_rows = _deduplicate_execution_history_rows(computed_execution_rows)
        with acquire_lock(LIVERMORE_CANDIDATE_HISTORY_LOCK, base_dir=duckdb_file.parent):
            transaction_started = False
            try:
                conn.execute("begin transaction")
                transaction_started = True
                conn.execute(f"delete from {TABLE_HIST} where snapshot_as_of_date = ?", [snapshot_as_of])
                conn.execute(f"delete from {TABLE_STOCK_UNIVERSE} where snapshot_as_of_date = ?", [snapshot_as_of])
                conn.execute(f"delete from {TABLE_EXECUTION_HIST} where signal_date = ?", [snapshot_as_of])
                if computed_rows:
                    placeholders = ", ".join("?" for _ in _INSERT_COLUMNS)
                    conn.executemany(
                        f"""
                        insert into {TABLE_HIST} ({", ".join(_INSERT_COLUMNS)})
                        values ({placeholders})
                        """,
                        [tuple(cast(Any, row[col]) for col in _INSERT_COLUMNS) for row in computed_rows],
                    )
                if computed_universe_rows:
                    placeholders = ", ".join("?" for _ in _UNIVERSE_INSERT_COLUMNS)
                    conn.executemany(
                        f"""
                        insert into {TABLE_STOCK_UNIVERSE} ({", ".join(_UNIVERSE_INSERT_COLUMNS)})
                        values ({placeholders})
                        """,
                        [
                            tuple(cast(Any, row[col]) for col in _UNIVERSE_INSERT_COLUMNS)
                            for row in computed_universe_rows
                        ],
                    )
                _insert_execution_history_rows(conn, computed_execution_rows)
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
            "universe_row_count": len(computed_universe_rows),
            "execution_row_count": len(computed_execution_rows),
            "stock_candidate_policy": stock_candidate_policy or EXECUTION_STOCK_CANDIDATE_POLICY,
        }
    finally:
        conn.close()


def backfill_livermore_candidate_history(
    duckdb_path: str,
    *,
    start_date: str,
    end_date: str,
    stock_candidate_policy: str | None = None,
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
            "stock_candidate_policy": stock_candidate_policy or EXECUTION_STOCK_CANDIDATE_POLICY,
        }

    # Ensure schema once for the whole window instead of per trade date; the
    # per-date materialize calls then skip their redundant DDL/pragma pass.
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    schema_conn = duckdb.connect(str(duckdb_file), read_only=False)
    try:
        ensure_livermore_candidate_history_schema(schema_conn)
    finally:
        schema_conn.close()

    date_results: list[dict[str, object]] = []
    total_rows = 0
    total_skipped = 0
    partial_dates = 0
    for trade_date in trade_dates:
        result = materialize_livermore_candidate_history(
            str(duckdb_file),
            as_of_date=trade_date,
            stock_candidate_policy=stock_candidate_policy,
            _schema_ready=True,
        )
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

    result = {
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
        "stock_candidate_policy": stock_candidate_policy or EXECUTION_STOCK_CANDIDATE_POLICY,
    }
    if trade_dates:
        from backend.app.tasks.livermore_monitor_append import append_daily_monitor

        append_daily_monitor(duckdb_path=str(duckdb_file), as_of_date=trade_dates[-1])
    return result


def backfill_livermore_candidate_execution_history(
    duckdb_path: str,
    *,
    start_date: str,
    end_date: str,
) -> dict[str, object]:
    """Rebuild execution history rows from persisted candidate history without reloading live strategy payloads."""
    parsed_start = date.fromisoformat(start_date.strip()[:10])
    parsed_end = date.fromisoformat(end_date.strip()[:10])
    if parsed_start > parsed_end:
        raise ValueError("start_date must be on or before end_date.")

    normalized_start = parsed_start.isoformat()
    normalized_end = parsed_end.isoformat()
    duckdb_file = Path(duckdb_path)
    duckdb_file.parent.mkdir(parents=True, exist_ok=True)
    run_id = f"livermore_candidate_execution_history:{normalized_start}:{normalized_end}:{uuid.uuid4().hex[:12]}"

    conn = duckdb.connect(str(duckdb_file), read_only=False)
    try:
        ensure_livermore_candidate_history_schema(conn)
        tables = _table_names(conn)
        observation_table_ok = TABLE_OBS in tables
        requested_dates = (
            _available_observation_trade_dates_from_conn(
                conn,
                start_date=normalized_start,
                end_date=normalized_end,
            )
            if observation_table_ok
            else []
        )
        if not requested_dates:
            requested_dates = _calendar_dates_in_range(parsed_start, parsed_end)
        source_rows = conn.execute(
            f"""
            select snapshot_as_of_date, stock_code, stock_name, signal_kind, candidate_rank, market_state
            from {TABLE_HIST}
            where cast(snapshot_as_of_date as date) >= cast(? as date)
              and cast(snapshot_as_of_date as date) <= cast(? as date)
            order by snapshot_as_of_date, candidate_rank nulls last, stock_code
            """,
            [normalized_start, normalized_end],
        ).fetchall()

        date_results_by_date: dict[str, dict[str, object]] = {}
        skipped: list[str] = []
        execution_rows: list[dict[str, object]] = []
        source_dates: set[str] = set()

        for snapshot_as_of_date, stock_code_raw, stock_name_raw, signal_kind_raw, candidate_rank_raw, market_state_raw in source_rows:
            snapshot_as_of = _normalize_trade_date_iso(snapshot_as_of_date)
            if snapshot_as_of is None:
                skipped.append(f"{snapshot_as_of_date}:invalid_snapshot_as_of_date")
                continue
            source_dates.add(snapshot_as_of)

            date_result = date_results_by_date.setdefault(
                snapshot_as_of,
                {
                    "as_of_date": snapshot_as_of,
                    "status": "ok",
                    "source_candidate_row_count": 0,
                    "execution_row_count": 0,
                    "skipped_count": 0,
                    "skipped": [],
                },
            )
            date_result["source_candidate_row_count"] = _safe_int(date_result.get("source_candidate_row_count"), default=0) + 1

            stock_code = _text(stock_code_raw).upper()
            if not stock_code:
                skip_reason = "blank_stock_code"
            elif not observation_table_ok:
                skip_reason = "missing_observation_table"
            else:
                execution = _execution_returns_for_candidate(
                    conn,
                    stock_code=stock_code,
                    snapshot_as_of_date=snapshot_as_of,
                )
                if execution is None:
                    skip_reason = "missing_execution_payload"
                else:
                    execution_rows.append(
                        {
                            "signal_date": snapshot_as_of,
                            "stock_code": stock_code,
                            "stock_name": _optional_text(stock_name_raw),
                            "signal_kind": _text(signal_kind_raw) or "stock_candidate",
                            "candidate_rank": _safe_int_or_none(candidate_rank_raw),
                            "market_state": _optional_text(market_state_raw),
                            **execution,
                            "formula_version": EXECUTION_FORMULA_VERSION,
                            "run_id": run_id,
                        }
                    )
                    continue

            dated_skip_reason = f"{snapshot_as_of}:{stock_code or 'unknown'}:{skip_reason}"
            skipped.append(dated_skip_reason)
            cast(list[str], date_result["skipped"]).append(dated_skip_reason)
            date_result["skipped_count"] = _safe_int(date_result.get("skipped_count"), default=0) + 1
            date_result["status"] = "partial"

        execution_rows = _deduplicate_execution_history_rows(execution_rows)
        for execution_row in execution_rows:
            execution_date = _text(execution_row.get("signal_date"))
            date_result = date_results_by_date.get(execution_date)
            if date_result is not None:
                date_result["execution_row_count"] = (
                    _safe_int(date_result.get("execution_row_count"), default=0) + 1
                )

        missing_source_dates = [requested_date for requested_date in requested_dates if requested_date not in source_dates]
        for missing_source_date in missing_source_dates:
            missing_skip_reason = f"{missing_source_date}:missing_source_candidate_rows"
            skipped.append(missing_skip_reason)
            date_results_by_date[missing_source_date] = {
                "as_of_date": missing_source_date,
                "status": "partial",
                "source_candidate_row_count": 0,
                "execution_row_count": 0,
                "skipped_count": 1,
                "skipped": [missing_skip_reason],
            }

        rebuilt_dates = sorted(source_dates)
        if rebuilt_dates:
            with acquire_lock(LIVERMORE_CANDIDATE_HISTORY_LOCK, base_dir=duckdb_file.parent):
                transaction_started = False
                try:
                    conn.execute("begin transaction")
                    transaction_started = True
                    for rebuilt_date in rebuilt_dates:
                        conn.execute(
                            f"delete from {TABLE_EXECUTION_HIST} where signal_date = ?",
                            [rebuilt_date],
                        )
                    _insert_execution_history_rows(conn, execution_rows)
                    conn.execute("commit")
                    transaction_started = False
                except Exception:
                    if transaction_started:
                        conn.execute("rollback")
                    raise

        date_results = sorted(
            date_results_by_date.values(),
            key=lambda row: _text(row.get("as_of_date")),
        )
        partial_date_count = sum(1 for row in date_results if _text(row.get("status")) != "ok")
        if not source_rows:
            skipped.append("missing_source_candidate_rows")
        elif source_rows and not rebuilt_dates:
            skipped.append("missing_source_candidate_rows")

        return {
            "status": "ok" if date_results and partial_date_count == 0 else "partial",
            "start_date": normalized_start,
            "end_date": normalized_end,
            "processed_date_count": len(date_results),
            "source_candidate_row_count": len(source_rows),
            "execution_row_count": len(execution_rows),
            "skipped_count": len(skipped),
            "partial_date_count": partial_date_count,
            "dates": date_results,
            "formula_version": EXECUTION_FORMULA_VERSION,
            "run_id": run_id,
            "skipped": skipped,
        }
    finally:
        conn.close()


def repair_livermore_candidate_execution_gaps(
    duckdb_path: str,
    *,
    dry_run: bool = True,
    target_backup_path: str | None = None,
    signal_kind: str = "stock_candidate",
) -> dict[str, object]:
    """Preview or repair exact logical-key gaps in persisted execution history."""
    duckdb_file = Path(duckdb_path)
    if not duckdb_file.is_file():
        raise FileNotFoundError(f"DuckDB file not found: {duckdb_file}")

    normalized_signal_kind = signal_kind.strip()
    if not normalized_signal_kind:
        raise ValueError("signal_kind cannot be blank.")

    if normalized_signal_kind != "stock_candidate":
        raise ValueError("execution-gap repair only supports signal_kind='stock_candidate'.")
    if dry_run:
        conn = duckdb.connect(str(duckdb_file), read_only=True)
        try:
            targets = _livermore_candidate_execution_gap_targets(
                conn,
                signal_kind=normalized_signal_kind,
            )
        finally:
            conn.close()
        return _livermore_candidate_execution_gap_result(
            signal_kind=normalized_signal_kind,
            targets=targets,
            mode="dry_run",
            run_id=None,
            repaired_count=0,
            deleted_physical_row_count=0,
        )

    with acquire_lock(LIVERMORE_CANDIDATE_HISTORY_LOCK, base_dir=duckdb_file.parent):
        backup_evidence = _validate_livermore_execution_gap_backup(
            duckdb_file,
            target_backup_path=target_backup_path,
        )
        _validate_livermore_execution_gap_target_hash(
            duckdb_file,
            expected_backup_sha256=str(backup_evidence["backup_sha256"]),
        )
        run_id = f"livermore_candidate_execution_gap_repair:{uuid.uuid4()}"
        conn = duckdb.connect(str(duckdb_file), read_only=False)
        transaction_started = False
        try:
            conn.execute("begin transaction")
            transaction_started = True
            targets = _livermore_candidate_execution_gap_targets(
                conn,
                signal_kind=normalized_signal_kind,
            )
            repairable_targets = [target for target in targets if bool(target["repairable"])]
            repaired_rows = [
                _livermore_execution_gap_replacement_row(target, run_id=run_id)
                for target in repairable_targets
            ]
            for target in repairable_targets:
                key = cast(dict[str, object], target["key"])
                conn.execute(
                    f"""
                    delete from {TABLE_EXECUTION_HIST}
                    where signal_date = ? and stock_code = ? and signal_kind = ?
                    """,
                    [
                        key["signal_date"],
                        key["stock_code"],
                        key["signal_kind"],
                    ],
                )
            _insert_execution_history_rows(conn, repaired_rows)
            conn.execute("commit")
            transaction_started = False
        except Exception:
            if transaction_started:
                conn.execute("rollback")
            raise
        finally:
            conn.close()

    result = _livermore_candidate_execution_gap_result(
        signal_kind=normalized_signal_kind,
        targets=targets,
        mode="live",
        run_id=run_id,
        repaired_count=len(repairable_targets),
        deleted_physical_row_count=sum(
            _safe_int(target.get("physical_row_count"), default=1)
            for target in repairable_targets
        ),
    )
    result.update(backup_evidence)
    return result


def _livermore_candidate_execution_gap_targets(
    conn: duckdb.DuckDBPyConnection,
    *,
    signal_kind: str,
) -> list[dict[str, object]]:
    candidate_rows = conn.execute(
        f"""
        with scoped as (
          select signal_date,
                 stock_code,
                 stock_name,
                 signal_kind,
                 candidate_rank,
                 market_state,
                 entry_executable,
                 data_status,
                 formula_version,
                 run_id,
                 return_20d_net,
                 return_20d_net_adj,
                 max(
                   case
                     when entry_executable is true
                      and return_20d_net is not null
                      and return_20d_net_adj is null
                     then 1 else 0
                   end
                 ) over logical_key as has_raw_20d_gap,
                 max(
                   case when lower(coalesce(data_status, '')) = 'pending' then 1 else 0 end
                 ) over logical_key as has_pending,
                 max(
                   case when coalesce(formula_version, '') <> ? then 1 else 0 end
                 ) over logical_key as has_stale_formula,
                 count(*) over logical_key as physical_row_count,
                 row_number() over (
                   logical_key
                   order by case when formula_version = ? then 0 else 1 end,
                            run_id desc nulls last
                 ) as logical_row_number
          from {TABLE_EXECUTION_HIST}
          where signal_kind = ?
          window logical_key as (partition by signal_date, stock_code, signal_kind)
        )
        select signal_date,
               stock_code,
               stock_name,
               signal_kind,
               candidate_rank,
               market_state,
               entry_executable,
               data_status,
               formula_version,
               run_id,
               return_20d_net,
               return_20d_net_adj,
               has_raw_20d_gap,
               has_pending,
               has_stale_formula,
               physical_row_count
        from scoped
        where logical_row_number = 1
          and (has_raw_20d_gap = 1 or has_pending = 1 or has_stale_formula = 1)
        order by signal_date, stock_code, signal_kind
        """,
        [EXECUTION_FORMULA_VERSION, EXECUTION_FORMULA_VERSION, signal_kind],
    ).fetchall()

    targets: list[dict[str, object]] = []
    for row in candidate_rows:
        stored_signal_date = _text(row[0])
        signal_date = _normalize_trade_date_iso(row[0])
        stored_stock_code = _text(row[1])
        stock_code = stored_stock_code.upper()
        computed = (
            _execution_returns_for_candidate(
                conn,
                stock_code=stock_code,
                snapshot_as_of_date=signal_date,
            )
            if signal_date and stock_code
            else None
        )
        reasons: list[str] = []
        if bool(row[12]):
            reasons.append("raw_20d_without_adjusted_20d")
        if bool(row[13]) and computed is not None and computed.get("data_status") == "complete":
            reasons.append("pending_recomputes_complete")
        if bool(row[14]):
            reasons.append("formula_version_stale")
        if not reasons:
            continue

        preview: dict[str, object] = {
            "stock_name": _optional_text(row[2]),
            "candidate_rank": _safe_int_or_none(row[4]),
            "market_state": _optional_text(row[5]),
            **(computed or {}),
            "formula_version": EXECUTION_FORMULA_VERSION,
        }
        remaining_reasons: list[str] = []
        if computed is None:
            remaining_reasons.append("missing_execution_payload")
        elif (
            computed.get("entry_executable") is True
            and computed.get("return_20d_net") is not None
            and computed.get("return_20d_net_adj") is None
        ):
            remaining_reasons.append("raw_20d_without_adjusted_20d")
        targets.append(
            {
                "key": {
                    "signal_date": stored_signal_date,
                    "stock_code": stored_stock_code,
                    "signal_kind": signal_kind,
                },
                "reasons": reasons,
                "physical_row_count": _safe_int(row[15], default=1),
                "current": {
                    "data_status": _optional_text(row[7]),
                    "formula_version": _optional_text(row[8]),
                    "run_id": _optional_text(row[9]),
                    "return_20d_net": _safe_float_or_none(row[10]),
                    "return_20d_net_adj": _safe_float_or_none(row[11]),
                },
                "preview": preview,
                "repairable": computed is not None,
                "remaining_reasons": remaining_reasons,
            }
        )
    return targets


def _livermore_execution_gap_replacement_row(
    target: dict[str, object],
    *,
    run_id: str,
) -> dict[str, object]:
    key = cast(dict[str, object], target["key"])
    preview = cast(dict[str, object], target["preview"])
    return {
        "signal_date": key["signal_date"],
        "stock_code": key["stock_code"],
        "signal_kind": key["signal_kind"],
        **preview,
        "run_id": run_id,
    }


def _livermore_candidate_execution_gap_result(
    *,
    signal_kind: str,
    targets: list[dict[str, object]],
    mode: str,
    run_id: str | None,
    repaired_count: int,
    deleted_physical_row_count: int,
) -> dict[str, object]:
    unresolved_count = sum(
        1
        for target in targets
        if not bool(target["repairable"]) or bool(target["remaining_reasons"])
    )
    preview_limit = 50
    preview_targets = targets[:preview_limit]
    target_physical_row_count = sum(
        _safe_int(target.get("physical_row_count"), default=1) for target in targets
    )
    duplicate_physical_row_count = sum(
        max(_safe_int(target.get("physical_row_count"), default=1) - 1, 0)
        for target in targets
    )
    reason_counts: dict[str, int] = {}
    remaining_reason_counts: dict[str, int] = {}
    for target in targets:
        for reason in _string_list(target.get("reasons")):
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        for reason in _string_list(target.get("remaining_reasons")):
            remaining_reason_counts[reason] = remaining_reason_counts.get(reason, 0) + 1
    return {
        "status": "partial" if unresolved_count else "ok",
        "mode": mode,
        "signal_kind": signal_kind,
        "target_count": len(targets),
        "target_physical_row_count": target_physical_row_count,
        "duplicate_physical_row_count": duplicate_physical_row_count,
        "target_preview_count": len(preview_targets),
        "preview_limit": preview_limit,
        "targets_truncated": len(targets) > preview_limit,
        "reason_counts": reason_counts,
        "remaining_reason_counts": remaining_reason_counts,
        "target_keys": [target["key"] for target in preview_targets],
        "repaired_count": repaired_count,
        "deleted_physical_row_count": deleted_physical_row_count,
        "unresolved_count": unresolved_count,
        "formula_version": EXECUTION_FORMULA_VERSION,
        "run_id": run_id,
        "target_backup_path": None,
        "backup_verified": False,
        "target_sha256_before": None,
        "backup_sha256": None,
        "targets": preview_targets,
    }


def _validate_livermore_execution_gap_backup(
    duckdb_file: Path,
    *,
    target_backup_path: str | None,
) -> dict[str, object]:
    if target_backup_path is None or not target_backup_path.strip():
        raise ValueError("target_backup_path is required for live execution-gap repair.")

    target_resolved = duckdb_file.resolve(strict=True)
    backup_file = Path(target_backup_path)
    if not backup_file.is_file():
        raise FileNotFoundError(f"Backup file not found: {backup_file}")
    backup_resolved = backup_file.resolve(strict=True)
    if target_resolved == backup_resolved or target_resolved.samefile(backup_resolved):
        raise ValueError("Backup must be a different file from the target DuckDB.")

    target_sha256 = _sha256_file(target_resolved)
    backup_sha256 = _sha256_file(backup_resolved)
    if target_sha256 != backup_sha256:
        raise ValueError("Backup content hash does not match target DuckDB.")
    return {
        "target_backup_path": str(backup_resolved),
        "backup_verified": True,
        "target_sha256_before": target_sha256,
        "backup_sha256": backup_sha256,
    }


def _validate_livermore_execution_gap_target_hash(
    duckdb_file: Path,
    *,
    expected_backup_sha256: str,
) -> None:
    current_target_sha256 = _sha256_file(duckdb_file.resolve(strict=True))
    if current_target_sha256 != expected_backup_sha256:
        raise RuntimeError(
            "Target DuckDB changed after backup verification; aborting live execution-gap repair."
        )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _calendar_dates_in_range(start_date: date, end_date: date) -> list[str]:
    dates: list[str] = []
    current = start_date
    while current <= end_date:
        dates.append(current.isoformat())
        current = current.fromordinal(current.toordinal() + 1)
    return dates


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
        "stock_candidate_policy": _mapping(payload.get("stock_candidates")).get("selection_policy"),
        "stock_candidates_formula_version": _mapping(payload.get("stock_candidates")).get("formula_version"),
        "stock_candidates_fundamental_overlay": _mapping(payload.get("stock_candidates")).get("fundamental_overlay"),
        "factor_screen_formula_version": _mapping(payload.get("factor_screen_candidates")).get("formula_version"),
        "theme_breakout_formula_version": _mapping(payload.get("theme_breakout")).get("formula_version"),
        "mean_reversion_formula_version": _mapping(payload.get("mean_reversion_candidates")).get("formula_version"),
        "uptrend_momentum_formula_version": _mapping(payload.get("uptrend_momentum_candidates")).get(
            "formula_version"
        ),
        "hybrid_fusion_formula_version": _mapping(payload.get("hybrid_fusion_candidates")).get("formula_version"),
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
            _available_observation_trade_dates_sql(),
            [start_date, end_date],
        ).fetchall()
    finally:
        conn.close()
    return [iso for row in rows if (iso := _normalize_trade_date_iso(row[0])) is not None]


def _available_observation_trade_dates_from_conn(
    conn: duckdb.DuckDBPyConnection,
    *,
    start_date: str,
    end_date: str,
) -> list[str]:
    rows = conn.execute(
        _available_observation_trade_dates_sql(),
        [start_date, end_date],
    ).fetchall()
    return [iso for row in rows if (iso := _normalize_trade_date_iso(row[0])) is not None]


def _available_observation_trade_dates_sql() -> str:
    return f"""
        select distinct trade_date
        from {TABLE_OBS}
        where cast(trade_date as date) >= cast(? as date)
          and cast(trade_date as date) <= cast(? as date)
        order by trade_date
        """


def _load_configured_stock_readiness() -> ChoiceStockReadiness:
    settings = get_settings()
    return load_choice_stock_readiness(settings.choice_stock_catalog_file)


def _build_signal_rows(payload: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    market_state = _payload_market_state(payload)
    market_gate_exposure = _payload_market_exposure(payload)
    hybrid_fusion_raw = payload.get("hybrid_fusion_candidates")
    if isinstance(hybrid_fusion_raw, dict):
        raw_items = hybrid_fusion_raw.get("items")
        if isinstance(raw_items, list):
            for raw in raw_items:
                if not isinstance(raw, dict):
                    continue
                item = cast(dict[str, object], raw)
                rank = _safe_int(item.get("rank"), default=1)
                rows.append(
                    {
                        "signal_kind": "hybrid_fusion",
                        "rank": rank,
                        "stock_code": item.get("stock_code"),
                        "stock_name": item.get("stock_name"),
                        "sector_code": item.get("sector_code"),
                        "sector_name": item.get("sector_name"),
                        "close_strength": item.get("price_confirm_score"),
                        "market_state": market_state,
                        "signal_evidence": _hybrid_fusion_signal_evidence(
                            item,
                            market_state=market_state,
                            rank=rank,
                            hybrid_fusion_payload=hybrid_fusion_raw,
                        ),
                    }
                )

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
                        "strength_turn": item.get("abnormal_turnover", item.get("turn")),
                        "strength_amplitude": item.get("amplitude"),
                        "close_strength": item.get("close_strength"),
                        "closed_up_limit": item.get("closed_up_limit"),
                        "market_state": market_state,
                        "abnormal_turnover": item.get("abnormal_turnover"),
                        "gap_norm": item.get("gap_norm"),
                        "breakout_extension_norm": item.get("breakout_extension_norm"),
                        "breakout_level": item.get("breakout_level"),
                        "ema10": item.get("ema10"),
                        "ma20": item.get("ma20"),
                        "ma60": item.get("ma60"),
                        "ma120": item.get("ma120"),
                        "selection_policy": item.get("selection_policy"),
                        "signal_evidence": _stock_candidate_signal_evidence(
                            item,
                            market_state=market_state,
                            market_gate_exposure=market_gate_exposure,
                            rank=rank,
                            stock_candidates_payload=stock_candidates_raw,
                        ),
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
                                "source_kind": theme.get("source_kind"),
                                "theme_source_kind": theme.get("source_kind"),
                                "theme_rank": theme_rank,
                                "strong_stock_count": theme.get("strong_stock_count"),
                                "limit_stock_count": theme.get("limit_stock_count"),
                                "avg_pctchange": theme.get("avg_pctchange"),
                                "avg_turn": theme.get("avg_turn"),
                                "movement_event_count": theme.get("movement_event_count"),
                                "latest_event_title": theme.get("latest_event_title"),
                                "latest_event_time": theme.get("latest_event_time"),
                                "stock_rank_in_theme": stock_rank,
                                "stock_code": stock.get("stock_code"),
                                "stock_movement_event_count": stock.get("movement_event_count"),
                                "stock_latest_event_title": stock.get("latest_event_title"),
                                "stock_latest_event_time": stock.get("latest_event_time"),
                                "evidence_state": _mapping(theme_breakout_raw.get("evidence_state")),
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
                            # 治理字段：选股公式版本补记(键名与 hybrid_fusion/momentum 族
                            # 一致为 formula_version)；item 级缺失时回退 payload 级,
                            # 兼容 v2 历史 payload 重放。
                            "formula_version": item.get("formula_version")
                            or factor_screen_raw.get("formula_version"),
                            # v3 流动性地板证据(元),供滚动 pass 率审计回溯。
                            "avg_amount_20d": item.get("avg_amount_20d"),
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

    uptrend_raw = payload.get("uptrend_momentum_candidates")
    if isinstance(uptrend_raw, dict):
        raw_items = uptrend_raw.get("items")
        if isinstance(raw_items, list):
            for raw in raw_items:
                if not isinstance(raw, dict):
                    continue
                item = cast(dict[str, object], raw)
                rank = _safe_int(item.get("rank"), default=1)
                rows.append(
                    {
                        "signal_kind": "uptrend_momentum",
                        "rank": rank,
                        "stock_code": item.get("stock_code"),
                        "stock_name": item.get("stock_name"),
                        "sector_code": item.get("sector_code"),
                        "sector_name": item.get("sector_name"),
                        "strength_pctchange": item.get("pctchange"),
                        "strength_turn": item.get("amount_ratio", item.get("turn")),
                        "strength_amplitude": item.get("amplitude"),
                        "ma20": item.get("ma20"),
                        "ma60": item.get("ma60"),
                        "ma120": item.get("ma120"),
                        "market_state": market_state,
                        "signal_evidence": {
                            "signal_kind": "uptrend_momentum",
                            "market_state": market_state,
                            "rank": rank,
                            "stock_code": item.get("stock_code"),
                            "sector_code": item.get("sector_code"),
                            "score": item.get("score"),
                            "close": item.get("close"),
                            "return_20d": item.get("return_20d"),
                            "return_60d": item.get("return_60d"),
                            "return_120d": item.get("return_120d"),
                            "ma20": item.get("ma20"),
                            "ma60": item.get("ma60"),
                            "ma120": item.get("ma120"),
                            "amount_ratio": item.get("amount_ratio"),
                            "close_to_ma20": item.get("close_to_ma20"),
                            "pctchange": item.get("pctchange"),
                            "turn": item.get("turn"),
                            "amplitude": item.get("amplitude"),
                            # 治理字段:评分公式版本补记(键名与 factor_screen/
                            # hybrid_fusion 一致);item 级缺失回退 payload 级,
                            # 兼容 v1 历史 payload 重放。历史按版本断代不回改。
                            "formula_version": item.get("formula_version")
                            or uptrend_raw.get("formula_version"),
                        },
                    }
                )

    fresh_trend_raw = payload.get("fresh_trend_watchlist")
    if isinstance(fresh_trend_raw, dict):
        raw_items = fresh_trend_raw.get("items")
        if isinstance(raw_items, list):
            for raw in raw_items:
                if not isinstance(raw, dict):
                    continue
                item = cast(dict[str, object], raw)
                rank = _safe_int(item.get("rank"), default=1)
                rows.append(
                    {
                        "signal_kind": "fresh_trend_watchlist",
                        "rank": rank,
                        "stock_code": item.get("stock_code"),
                        "stock_name": item.get("stock_name"),
                        "sector_code": item.get("sector_code"),
                        "sector_name": item.get("sector_name"),
                        "strength_pctchange": item.get("pctchange"),
                        "strength_turn": item.get("amount_ratio", item.get("turn")),
                        "strength_amplitude": item.get("amplitude"),
                        "ma20": item.get("ma20"),
                        "ma60": item.get("ma60"),
                        "ma120": item.get("ma120"),
                        "market_state": market_state,
                        "signal_evidence": {
                            "signal_kind": "fresh_trend_watchlist",
                            "market_state": market_state,
                            "rank": rank,
                            "stock_code": item.get("stock_code"),
                            "sector_code": item.get("sector_code"),
                            "concepts": item.get("concepts"),
                            "score": item.get("score"),
                            "close": item.get("close"),
                            "return_20d": item.get("return_20d"),
                            "return_60d": item.get("return_60d"),
                            "return_120d": item.get("return_120d"),
                            "ma20": item.get("ma20"),
                            "ma60": item.get("ma60"),
                            "ma120": item.get("ma120"),
                            "amount_ratio": item.get("amount_ratio"),
                            "close_to_ma20": item.get("close_to_ma20"),
                            "pctchange": item.get("pctchange"),
                            "turn": item.get("turn"),
                            "amplitude": item.get("amplitude"),
                            "hlimitedays": item.get("hlimitedays"),
                            # 治理字段:评分公式版本补记(同 uptrend 分支)。
                            "formula_version": item.get("formula_version")
                            or fresh_trend_raw.get("formula_version"),
                        },
                    }
                )

    signal_order = {
        "hybrid_fusion": 0,
        "stock_candidate": 1,
        "uptrend_momentum": 2,
        "fresh_trend_watchlist": 3,
        "theme_breakout": 4,
        "factor_screen": 5,
        "mean_reversion": 6,
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


def _build_stock_candidate_universe_rows(payload: dict[str, object]) -> list[dict[str, object]]:
    stock_candidates_raw = payload.get("stock_candidates")
    if not isinstance(stock_candidates_raw, dict):
        return []
    raw_items = stock_candidates_raw.get("universe_items")
    if not isinstance(raw_items, list):
        return []
    market_state = _payload_market_state(payload)
    rows: list[dict[str, object]] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        item = dict(cast(dict[str, object], raw))
        item["market_state"] = _optional_text(item.get("market_state")) or market_state
        rows.append(item)
    return rows


def _payload_market_state(payload: dict[str, object]) -> str | None:
    return _optional_text(_mapping(payload.get("market_gate")).get("state"))


def _payload_market_exposure(payload: dict[str, object]) -> float | None:
    return _safe_float_or_none(_mapping(payload.get("market_gate")).get("exposure"))


def _row_market_state(item: dict[str, object]) -> str | None:
    direct = _optional_text(item.get("market_state"))
    if direct:
        return direct
    evidence = _mapping(item.get("signal_evidence"))
    return _optional_text(evidence.get("market_state"))


def _stock_candidate_signal_evidence(
    item: dict[str, object],
    *,
    market_state: str | None,
    market_gate_exposure: float | None = None,
    rank: int,
    stock_candidates_payload: object | None = None,
) -> dict[str, object]:
    evidence = {
        "signal_kind": "stock_candidate",
        "market_state": market_state,
        "market_gate_exposure": market_gate_exposure,
        "rank": rank,
        "stock_code": item.get("stock_code"),
        "sector_code": item.get("sector_code"),
        "sector_rank": item.get("sector_rank"),
        "close_strength": item.get("close_strength"),
        "abnormal_turnover": item.get("abnormal_turnover"),
        "gap_norm": item.get("gap_norm"),
        "breakout_extension_norm": item.get("breakout_extension_norm"),
        "breakout_level": item.get("breakout_level"),
        "ema10": item.get("ema10"),
        "ma20": item.get("ma20"),
        "ma60": item.get("ma60"),
        "ma120": item.get("ma120"),
    }
    stock_candidates = _mapping(stock_candidates_payload)
    selection_formula_version = _optional_text(stock_candidates.get("formula_version"))
    if selection_formula_version:
        evidence["selection_formula_version"] = selection_formula_version
    overlay_status = _optional_text(_mapping(stock_candidates.get("fundamental_overlay")).get("status"))
    if overlay_status:
        evidence["fundamental_overlay_status"] = overlay_status
    for key in (
        "pe",
        "pb",
        "ps",
        "roe",
        "gross_margin",
        "three_month_return",
        "twelve_month_return",
        "volatility",
        "dividend_yield",
        "factor_score",
        "factor_overlay_rank",
    ):
        value = item.get(key)
        if value is not None and _text(value):
            evidence[key] = value
    selection_policy = _optional_text(item.get("selection_policy"))
    if selection_policy:
        evidence["selection_policy"] = selection_policy
    return evidence


def _hybrid_fusion_signal_evidence(
    item: dict[str, object],
    *,
    market_state: str | None,
    rank: int,
    hybrid_fusion_payload: object | None = None,
) -> dict[str, object]:
    nested = _mapping(item.get("evidence"))
    payload = _mapping(hybrid_fusion_payload)
    evidence: dict[str, object] = {
        **nested,
        "signal_kind": "hybrid_fusion",
        "market_state": market_state,
        "rank": rank,
        "stock_code": item.get("stock_code"),
        "sector_code": item.get("sector_code"),
        "formula_version": payload.get("formula_version") or nested.get("formula_version"),
        "observation_only": payload.get("observation_only", True),
        "fusion_score": item.get("fusion_score"),
        "cycle_score": item.get("cycle_score"),
        "lifecourt_proxy_score": item.get("lifecourt_proxy_score"),
        "attention_score": item.get("attention_score"),
        "price_confirm_score": item.get("price_confirm_score"),
        "crowding_penalty": item.get("crowding_penalty"),
        "confidence": item.get("confidence"),
        "reason": item.get("reason"),
    }
    source_kinds = nested.get("source_kinds")
    if source_kinds is not None:
        evidence["source_kinds"] = source_kinds
    return evidence


def _stock_candidate_universe_evidence(
    item: dict[str, object],
    *,
    payload: dict[str, object],
) -> dict[str, object]:
    return {
        **_stock_candidate_signal_evidence(
            item,
            market_state=_optional_text(item.get("market_state")) or _payload_market_state(payload),
            market_gate_exposure=_payload_market_exposure(payload),
            rank=_safe_int(item.get("new_rank"), default=1),
            stock_candidates_payload=_mapping(payload.get("stock_candidates")),
        ),
        "old_rank": item.get("old_rank"),
        "new_rank": item.get("new_rank"),
        "eligible_before_truncation": item.get("eligible_before_truncation"),
        "selected_old_top6": item.get("selected_old_top6"),
        "selected_new_top6": item.get("selected_new_top6"),
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
    d10 = series[9] if len(series) >= 10 else None
    d20 = series[19] if len(series) >= 20 else None

    r1 = (d1[1] - selection_close) / selection_close if d1 else None
    r5 = (d5[1] - selection_close) / selection_close if d5 else None
    r10 = (d10[1] - selection_close) / selection_close if d10 else None
    r20 = (d20[1] - selection_close) / selection_close if d20 else None
    signal_adj_factor = _adjustment_factor(conn, stock_code=stock_code, trade_date=snapshot_as_of_date)
    adj_returns: dict[str, float | None] = {}
    forward_factor_by_horizon: dict[str, float | None] = {}
    missing_adj_horizons: list[str] = []
    factor_values = [signal_adj_factor]
    for horizon, target in (("1d", d1), ("5d", d5), ("10d", d10), ("20d", d20)):
        if target is None:
            adj_returns[horizon] = None
            forward_factor_by_horizon[horizon] = None
            continue
        target_adj_factor = _adjustment_factor(conn, stock_code=stock_code, trade_date=target[0])
        forward_factor_by_horizon[horizon] = target_adj_factor
        factor_values.append(target_adj_factor)
        adj_returns[horizon] = adjusted_return(
            start_price=selection_close,
            start_adj_factor=signal_adj_factor,
            end_price=target[1],
            end_adj_factor=target_adj_factor,
        )
        if adj_returns[horizon] is None:
            missing_adj_horizons.append(horizon)
    ex_div_in_window = factors_changed(factor_values)

    has_all = r1 is not None and r5 is not None and r10 is not None and r20 is not None
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
        "forward_trade_date_10d": d10[0] if d10 else None,
        "forward_trade_date_20d": d20[0] if d20 else None,
        "return_1d": r1,
        "return_5d": r5,
        "return_10d": r10,
        "return_20d": r20,
        "return_1d_adj": adj_returns["1d"],
        "return_5d_adj": adj_returns["5d"],
        "return_10d_adj": adj_returns["10d"],
        "return_20d_adj": adj_returns["20d"],
        "ex_div_in_window": ex_div_in_window,
        "data_status": data_status,
        "adjustment_evidence": _forward_adjustment_evidence(
            signal_adj_factor=signal_adj_factor,
            forward_factor_by_horizon=forward_factor_by_horizon,
            missing_adj_horizons=missing_adj_horizons,
            ex_div_in_window=ex_div_in_window,
        ),
    }


def _forward_adjustment_evidence(
    *,
    signal_adj_factor: float | None,
    forward_factor_by_horizon: dict[str, float | None],
    missing_adj_horizons: list[str],
    ex_div_in_window: bool,
) -> dict[str, object]:
    return {
        "price_adjustment_mode": PRICE_ADJUSTMENT_MODE,
        "signal_adj_factor": signal_adj_factor,
        "forward_adj_factors": forward_factor_by_horizon,
        "adj_factor_missing": bool(missing_adj_horizons),
        "adj_factor_missing_horizons": missing_adj_horizons,
        "adjusted_returns_status": "partial_missing_adj_factor"
        if missing_adj_horizons
        else "complete",
        "ex_div_in_window": ex_div_in_window,
    }


def _evidence_with_adjustment(base: object, adjustment_evidence: object) -> dict[str, object]:
    evidence = dict(_mapping(base))
    if isinstance(adjustment_evidence, dict):
        evidence["adjustment_evidence"] = adjustment_evidence
    return evidence


def _adjustment_factor(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str,
    trade_date: str,
) -> float | None:
    if STOCK_ADJUSTMENT_FACTOR_TABLE not in _table_names(conn):
        return None
    row = conn.execute(
        f"""
        select adj_factor
        from {STOCK_ADJUSTMENT_FACTOR_TABLE}
        where stock_code = ? and trade_date = ? and adj_factor is not null
        order by run_id desc, source_version desc
        limit 1
        """,
        [stock_code, trade_date],
    ).fetchone()
    if row is None:
        return None
    return _safe_positive_float(row[0])


def _insert_execution_history_rows(
    conn: duckdb.DuckDBPyConnection,
    rows: list[dict[str, object]],
) -> None:
    deduplicated_rows = _deduplicate_execution_history_rows(rows)
    if not deduplicated_rows:
        return
    # Keep this enforcement in the shared task writer rather than adding a
    # table-level PK/unique index: constraining every legacy DuckDB snapshot is
    # a much wider schema migration, while all governed writes already converge
    # here and can enforce the execution grain before insertion.
    placeholders = ", ".join("?" for _ in _EXECUTION_INSERT_COLUMNS)
    conn.executemany(
        f"""
        insert into {TABLE_EXECUTION_HIST} ({", ".join(_EXECUTION_INSERT_COLUMNS)})
        values ({placeholders})
        """,
        [
            tuple(cast(Any, row[col]) for col in _EXECUTION_INSERT_COLUMNS)
            for row in deduplicated_rows
        ],
    )


def _deduplicate_execution_history_rows(
    rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    deduplicated: dict[tuple[str, str, str], dict[str, object]] = {}
    for row in rows:
        key = (
            _text(row.get("signal_date")),
            _text(row.get("stock_code")).upper(),
            _text(row.get("signal_kind")) or "stock_candidate",
        )
        current = deduplicated.get(key)
        if current is None or _execution_history_row_priority(row) > _execution_history_row_priority(current):
            deduplicated[key] = row
    return list(deduplicated.values())


def _execution_history_row_priority(row: dict[str, object]) -> tuple[int, int, str]:
    populated_adjusted_returns = sum(
        row.get(field) is not None
        for field in (
            "return_1d_net_adj",
            "return_5d_net_adj",
            "return_10d_net_adj",
            "return_20d_net_adj",
        )
    )
    candidate_rank = _safe_int(row.get("candidate_rank"), default=999_999)
    return populated_adjusted_returns, -candidate_rank, _text(row.get("run_id"))


def _execution_returns_for_candidate(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str,
    snapshot_as_of_date: str,
) -> dict[str, object] | None:
    signal_row = conn.execute(
        f"""
        select close_value
        from {TABLE_OBS}
        where stock_code = ? and trade_date = ? and close_value is not null
        """,
        [stock_code, snapshot_as_of_date],
    ).fetchone()
    if signal_row is None or signal_row[0] is None:
        return None

    signal_close = float(signal_row[0])
    signal_adj_factor = _adjustment_factor(conn, stock_code=stock_code, trade_date=snapshot_as_of_date)
    bars = _execution_bars_for_candidate(conn, stock_code=stock_code, snapshot_as_of_date=snapshot_as_of_date)
    if not bars:
        return _execution_payload(
            signal_close=signal_close,
            signal_adj_factor=signal_adj_factor,
            entry_bar=None,
            entry_price=None,
            entry_adj_factor=None,
            entry_ex_div=False,
            entry_price_kind="next_open",
            entry_block_reason="missing_entry_bar",
            exits={},
            data_status="pending",
        )

    entry_bar = bars[0]
    entry_price, entry_price_kind = _entry_price(entry_bar)
    entry_adj_factor = _adjustment_factor(conn, stock_code=stock_code, trade_date=cast(str, entry_bar["trade_date"]))
    entry_ex_div = factors_changed([signal_adj_factor, entry_adj_factor])
    entry_block_reason = _entry_block_reason(entry_bar, entry_price=entry_price)
    if entry_block_reason:
        return _execution_payload(
            signal_close=signal_close,
            signal_adj_factor=signal_adj_factor,
            entry_bar=entry_bar,
            entry_price=entry_price,
            entry_adj_factor=entry_adj_factor,
            entry_ex_div=entry_ex_div,
            entry_price_kind=entry_price_kind,
            entry_block_reason=entry_block_reason,
            exits={},
            data_status="entry_blocked",
        )

    exits: dict[str, dict[str, object]] = {}
    for horizon, index in (("1d", 0), ("5d", 4), ("10d", 9), ("20d", 19)):
        exit_bar = _first_sellable_bar_at_or_after(bars, index)
        if exit_bar is None:
            continue
        exit_price = _safe_positive_float(exit_bar.get("close_value"))
        if exit_price is None:
            continue
        exit_adj_factor = _adjustment_factor(conn, stock_code=stock_code, trade_date=cast(str, exit_bar["trade_date"]))
        gross = (exit_price / cast(float, entry_price)) - 1.0
        gross_adj = adjusted_return(
            start_price=cast(float, entry_price),
            start_adj_factor=entry_adj_factor,
            end_price=exit_price,
            end_adj_factor=exit_adj_factor,
        )
        exits[horizon] = {
            "date": exit_bar["trade_date"],
            "price": exit_price,
            "gross": gross,
            "net": _net_return(exit_price=exit_price, entry_price=cast(float, entry_price)),
            "gross_adj": gross_adj,
            "net_adj": net_return_after_costs(
                gross_adj,
                buy_cost_rate=BUY_COST_RATE,
                sell_cost_rate=SELL_COST_RATE,
                slippage_rate=SLIPPAGE_RATE,
            ),
            "exit_adj_factor": exit_adj_factor,
        }

    data_status = "complete" if all(key in exits for key in ("1d", "5d", "10d", "20d")) else "pending"
    return _execution_payload(
        signal_close=signal_close,
        signal_adj_factor=signal_adj_factor,
        entry_bar=entry_bar,
        entry_price=entry_price,
        entry_adj_factor=entry_adj_factor,
        entry_ex_div=entry_ex_div,
        entry_price_kind=entry_price_kind,
        entry_block_reason="",
        exits=exits,
        data_status=data_status,
    )


def _execution_bars_for_candidate(
    conn: duckdb.DuckDBPyConnection,
    *,
    stock_code: str,
    snapshot_as_of_date: str,
) -> list[dict[str, object]]:
    columns = _table_columns(conn, TABLE_OBS)
    open_expr = "d.open_value" if "open_value" in columns else "d.close_value"
    highlimit_expr = "d.highlimit" if "highlimit" in columns else "null"
    lowlimit_expr = "d.lowlimit" if "lowlimit" in columns else "null"
    tradestatus_expr = "d.tradestatus" if "tradestatus" in columns else "null"
    # 涨跌停数值价三态（契约 docs/data_contracts.md §4.10 覆盖缺口）：优先
    # stock_limit_price_daily 数值价，回退 observation 列 try_cast，皆无维持
    # fail-open；解析逻辑与 portfolio_paths 共享 resolve_limit_prices，口径一致。
    has_limit_price = TABLE_LIMIT_PRICE in _table_names(conn) and {
        "stock_code",
        "trade_date",
        "up_limit",
        "down_limit",
    } <= _table_columns(conn, TABLE_LIMIT_PRICE)
    limit_select = (
        "lp.up_limit, lp.down_limit"
        if has_limit_price
        else "cast(null as double) as up_limit, cast(null as double) as down_limit"
    )
    limit_join = (
        f"""
        left join {TABLE_LIMIT_PRICE} lp
          on lp.stock_code = d.stock_code
         and cast(lp.trade_date as varchar) = cast(d.trade_date as varchar)
        """
        if has_limit_price
        else ""
    )
    rows = conn.execute(
        f"""
        select d.trade_date,
               {open_expr} as open_value,
               d.close_value,
               {highlimit_expr} as highlimit,
               {lowlimit_expr} as lowlimit,
               {tradestatus_expr} as tradestatus,
               {limit_select}
        from {TABLE_OBS} d
        {limit_join}
        where d.stock_code = ?
          and cast(d.trade_date as date) > cast(? as date)
          and d.close_value is not null
        order by d.trade_date
        """,
        [stock_code, snapshot_as_of_date],
    ).fetchall()
    bars: list[dict[str, object]] = []
    has_open = "open_value" in columns
    for (
        trade_date_raw,
        open_raw,
        close_raw,
        highlimit_raw,
        lowlimit_raw,
        tradestatus_raw,
        table_up_raw,
        table_down_raw,
    ) in rows:
        trade_date = _normalize_trade_date_iso(trade_date_raw)
        if trade_date is None:
            continue
        resolved_highlimit, resolved_lowlimit, limit_price_source = resolve_limit_prices(
            observation_highlimit=highlimit_raw,
            observation_lowlimit=lowlimit_raw,
            table_up_limit=table_up_raw,
            table_down_limit=table_down_raw,
        )
        bars.append(
            {
                "trade_date": trade_date,
                "open_value": _safe_float_or_none(open_raw),
                "close_value": _safe_float_or_none(close_raw),
                "highlimit": resolved_highlimit,
                "lowlimit": resolved_lowlimit,
                "limit_price_source": limit_price_source,
                "tradestatus": _optional_text(tradestatus_raw),
                "has_open_value": has_open,
            }
        )
    return bars


def _execution_payload(
    *,
    signal_close: float,
    signal_adj_factor: float | None,
    entry_bar: dict[str, object] | None,
    entry_price: float | None,
    entry_adj_factor: float | None,
    entry_ex_div: bool,
    entry_price_kind: str,
    entry_block_reason: str,
    exits: dict[str, dict[str, object]],
    data_status: str,
) -> dict[str, object]:
    missing_adj_horizons = [
        horizon
        for horizon in ("1d", "5d", "10d", "20d")
        if horizon in exits and exits[horizon].get("gross_adj") is None
    ]
    entry_adj_factor_ratio = None
    if signal_adj_factor is not None and signal_adj_factor > 0 and entry_adj_factor is not None:
        entry_adj_factor_ratio = entry_adj_factor / signal_adj_factor
    evidence = {
        "entry_price_kind": entry_price_kind,
        "exit_price_kind": "close",
        "entry_block_reason": entry_block_reason or None,
        "price_adjustment_mode": PRICE_ADJUSTMENT_MODE,
        "adj_factor_missing": bool(missing_adj_horizons or (entry_bar is not None and entry_adj_factor is None)),
        "adj_factor_missing_horizons": missing_adj_horizons,
        "entry_ex_div": entry_ex_div,
        "entry_adj_factor_signal": signal_adj_factor,
        "entry_adj_factor": entry_adj_factor,
        "entry_adj_factor_ratio": entry_adj_factor_ratio,
        "costs": {
            "buy_cost_rate": BUY_COST_RATE,
            "sell_cost_rate": SELL_COST_RATE,
            "slippage_rate": SLIPPAGE_RATE,
        },
    }
    payload: dict[str, object] = {
        "signal_close": signal_close,
        "entry_date": entry_bar.get("trade_date") if entry_bar else None,
        "entry_price": entry_price,
        "entry_price_kind": entry_price_kind,
        "entry_executable": not bool(entry_block_reason),
        "entry_block_reason": entry_block_reason or None,
        "entry_ex_div": entry_ex_div,
        "buy_cost_bps": BUY_COST_RATE * 10000,
        "sell_cost_bps": SELL_COST_RATE * 10000,
        "slippage_bps": SLIPPAGE_RATE * 10000,
        "price_adjustment_mode": PRICE_ADJUSTMENT_MODE,
        "data_status": data_status,
        "evidence_json": _json_dump(evidence),
    }
    for horizon in ("1d", "5d", "10d", "20d"):
        exit_row = exits.get(horizon, {})
        payload[f"exit_date_{horizon}"] = exit_row.get("date")
        payload[f"exit_price_{horizon}"] = exit_row.get("price")
        payload[f"return_{horizon}_gross"] = exit_row.get("gross")
        payload[f"return_{horizon}_net"] = exit_row.get("net")
        payload[f"return_{horizon}_gross_adj"] = exit_row.get("gross_adj")
        payload[f"return_{horizon}_net_adj"] = exit_row.get("net_adj")
    return payload


def _entry_price(entry_bar: dict[str, object]) -> tuple[float | None, str]:
    open_price = _safe_positive_float(entry_bar.get("open_value"))
    if open_price is not None and entry_bar.get("has_open_value"):
        return open_price, "next_open"
    close_price = _safe_positive_float(entry_bar.get("close_value"))
    return close_price, "next_close_fallback"


def _entry_block_reason(entry_bar: dict[str, object], *, entry_price: float | None) -> str:
    if entry_price is None:
        return "missing_entry_price"
    if _is_halted(entry_bar):
        return "entry_halted"
    highlimit = _safe_positive_float(entry_bar.get("highlimit"))
    if highlimit is not None and entry_price >= highlimit * 0.999:
        return "entry_limit_up_or_one_line"
    return ""


def _first_sellable_bar_at_or_after(
    bars: list[dict[str, object]],
    start_index: int,
) -> dict[str, object] | None:
    for bar in bars[start_index:]:
        if _is_halted(bar) or _is_limit_down(bar):
            continue
        if _safe_positive_float(bar.get("close_value")) is None:
            continue
        return bar
    return None


def _is_halted(bar: dict[str, object]) -> bool:
    return is_tradestatus_halted(bar.get("tradestatus"))


def _is_limit_down(bar: dict[str, object]) -> bool:
    lowlimit = _safe_positive_float(bar.get("lowlimit"))
    close_value = _safe_positive_float(bar.get("close_value"))
    if lowlimit is None or close_value is None:
        return False
    return close_value <= lowlimit * 1.001


def _net_return(*, exit_price: float, entry_price: float) -> float:
    gross = exit_price / entry_price - 1.0
    netted = net_return_after_costs(
        gross,
        buy_cost_rate=BUY_COST_RATE,
        sell_cost_rate=SELL_COST_RATE,
        slippage_rate=SLIPPAGE_RATE,
    )
    assert netted is not None
    return netted


def _safe_positive_float(value: object) -> float | None:
    number = _safe_float_or_none(value)
    if number is None or number <= 0:
        return None
    return number


def _table_columns(conn: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    return {str(row[1]).lower() for row in conn.execute(f"pragma table_info('{table_name}')").fetchall()}


def _table_names(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {str(row[0]) for row in conn.execute("show tables").fetchall()}


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


def _safe_bool(value: object, *, default: bool) -> bool:
    parsed = _safe_bool_or_none(value)
    return default if parsed is None else parsed


def _json_dump(value: object) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True, default=str)
