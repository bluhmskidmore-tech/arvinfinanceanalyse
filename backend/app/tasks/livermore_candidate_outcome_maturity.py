from __future__ import annotations

import hashlib
import json
import math
from bisect import bisect_right
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
from backend.app.core_finance.adjusted_returns import PRICE_ADJUSTMENT_MODE
from backend.app.core_finance.field_normalization import tradable_status_sql_condition
from backend.app.governance.locks import LockDefinition, acquire_lock

TABLE_HIST = "livermore_candidate_history"
TABLE_OBS = "choice_stock_daily_observation"
TABLE_ADJ_FACTOR = "stock_adjustment_factor"
OUTCOME_FORMULA_VERSION = "fv_livermore_candidate_outcome_maturity_v1"
OUTCOME_CONTRACT_VERSION = "rv_livermore_candidate_outcome_maturity_v1"
LIVERMORE_CANDIDATE_OUTCOME_LOCK = LockDefinition(
    key="lock:duckdb:livermore-candidate-history",
    ttl_seconds=600,
)

_HORIZONS = {"1d": 1, "5d": 5, "10d": 10, "20d": 20}
_LINEAGE_FIELDS = ("source_version", "vendor_version", "rule_version", "run_id")
_MATURITY_STATUSES = (
    "natural_pending",
    "complete",
    "matured_missing_bar",
    "raw_matured_adjustment_missing",
    "partial_halt",
)
_OUTCOME_COLUMNS = {
    *(f"forward_trade_date_{horizon}" for horizon in _HORIZONS),
    *(f"return_{horizon}" for horizon in _HORIZONS),
    *(f"return_{horizon}_adj" for horizon in _HORIZONS),
    "ex_div_in_window",
    "data_status",
    "signal_evidence_json",
}


def mature_livermore_candidate_outcomes(
    duckdb_path: str | Path,
    *,
    evaluation_as_of_date: str | None = None,
    arbitrate_conflicts: bool = True,
) -> dict[str, object]:
    """Fill only missing candidate outcomes using observations available by the evaluation date.

    ``arbitrate_conflicts``：stored target 与当前修订行情重算 target 不一致时，
    按 revision-current canonical 仲裁——以当前行情覆盖该 horizon 的日期/收益
    三元组，旧值完整写入 ``signal_evidence_json.outcome_maturity_audit`` 留痕；
    置 ``False`` 时保持旧保守行为（仅记录 issue、跳过该 horizon 回补）。
    """
    evaluation_date = _normalize_evaluation_date(evaluation_as_of_date)
    path = Path(duckdb_path)
    if not path.is_file():
        return _empty_result(status="not_ready", evaluation_as_of_date=evaluation_date, reason="duckdb_missing")

    run_id = f"livermore_candidate_outcome_maturity:{evaluation_date}:{OUTCOME_CONTRACT_VERSION}"
    with acquire_lock(LIVERMORE_CANDIDATE_OUTCOME_LOCK, base_dir=path.parent):
        conn = duckdb.connect(str(path), read_only=False)
        try:
            tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
            missing_tables = [table for table in (TABLE_HIST, TABLE_OBS) if table not in tables]
            if missing_tables:
                return _empty_result(
                    status="not_ready",
                    evaluation_as_of_date=evaluation_date,
                    reason=f"missing_tables:{','.join(missing_tables)}",
                )

            history_columns = _table_columns(conn, TABLE_HIST)
            required_columns = {
                "snapshot_as_of_date",
                "stock_code",
                "selection_close",
                *_OUTCOME_COLUMNS,
            }
            missing_columns = sorted(required_columns - history_columns)
            if missing_columns:
                return _empty_result(
                    status="not_ready",
                    evaluation_as_of_date=evaluation_date,
                    reason=f"missing_history_columns:{','.join(missing_columns)}",
                )

            observation_columns = _table_columns(conn, TABLE_OBS)
            if not {"trade_date", "stock_code", "close_value"}.issubset(observation_columns):
                return _empty_result(
                    status="not_ready",
                    evaluation_as_of_date=evaluation_date,
                    reason="missing_observation_columns",
                )

            conn.execute("begin transaction")
            candidates = _load_candidates(conn, evaluation_as_of_date=evaluation_date)
            if not candidates:
                conn.execute("commit")
                return _empty_result(status="completed", evaluation_as_of_date=evaluation_date)

            minimum_snapshot_date = min(str(row["snapshot_as_of_date"])[:10] for row in candidates)
            observation_windows, market_dates, loaded_observation_row_count = (
                _load_candidate_observation_windows(
                    conn,
                    candidates=candidates,
                    evaluation_as_of_date=evaluation_date,
                    minimum_snapshot_date=minimum_snapshot_date,
                    observation_columns=observation_columns,
                )
            )
            required_factor_keys = _required_factor_keys(
                candidates,
                observation_windows=observation_windows,
            )
            factors, loaded_factor_row_count = _load_adjustment_factors(
                conn,
                tables=tables,
                factor_keys=required_factor_keys,
            )
            table_present = [TABLE_HIST, TABLE_OBS]
            if TABLE_ADJ_FACTOR in tables:
                table_present.append(TABLE_ADJ_FACTOR)

            horizon_items = {horizon: [] for horizon in _HORIZONS}
            updated_rows = 0
            updated_fields = 0
            arbitrated_conflict_units = 0
            issues: list[str] = []
            blocked_rows: list[dict[str, object]] = []
            for candidate in candidates:
                updates, maturity, row_issues, blocked_issue, row_arbitrations = _candidate_outcome_updates(
                    candidate,
                    observation_window=observation_windows.get(
                        int(candidate["_rowid"]),
                        _empty_observation_window(),
                    ),
                    market_dates=market_dates,
                    factors=factors,
                    evaluation_as_of_date=evaluation_date,
                    run_id=run_id,
                    table_present=table_present,
                    arbitrate_conflicts=arbitrate_conflicts,
                )
                issues.extend(row_issues)
                arbitrated_conflict_units += row_arbitrations
                if blocked_issue:
                    blocked_rows.append(
                        {
                            "rowid": int(candidate["_rowid"]),
                            "issue": blocked_issue,
                        }
                    )
                for horizon, item in maturity.items():
                    horizon_items[horizon].append(item)
                if updates:
                    _update_candidate_outcomes(conn, row_id=int(candidate["_rowid"]), updates=updates)
                    updated_rows += 1
                    updated_fields += len(updates)
            conn.execute("commit")
        except Exception:
            try:
                conn.execute("rollback")
            except duckdb.Error:
                pass
            raise
        finally:
            conn.close()

    return {
        "status": "partial" if blocked_rows else "completed",
        "evaluation_as_of_date": evaluation_date,
        "candidate_row_count": len(candidates),
        "updated_row_count": updated_rows,
        "updated_field_count": updated_fields,
        "arbitrate_conflicts": arbitrate_conflicts,
        "arbitrated_conflict_count": arbitrated_conflict_units,
        "blocked_row_count": len(blocked_rows),
        "blocked_rows": blocked_rows,
        "loaded_observation_row_count": loaded_observation_row_count,
        "loaded_market_date_count": len(market_dates),
        "requested_factor_key_count": len(required_factor_keys),
        "loaded_factor_row_count": loaded_factor_row_count,
        "run_id": run_id,
        "formula_version": OUTCOME_FORMULA_VERSION,
        "contract_version": OUTCOME_CONTRACT_VERSION,
        "horizons": _horizon_summary(horizon_items),
        "issues": sorted(set(issues)),
        "observational_only": True,
        "formal_use_allowed": False,
    }


def _load_candidates(
    conn: duckdb.DuckDBPyConnection,
    *,
    evaluation_as_of_date: str,
) -> list[dict[str, Any]]:
    columns = [
        "snapshot_as_of_date",
        "stock_code",
        "selection_close",
        *(f"forward_trade_date_{horizon}" for horizon in _HORIZONS),
        *(f"return_{horizon}" for horizon in _HORIZONS),
        *(f"return_{horizon}_adj" for horizon in _HORIZONS),
        "ex_div_in_window",
        "data_status",
        "signal_evidence_json",
    ]
    rows = conn.execute(
        f"""
        select rowid, {", ".join(columns)}
        from {TABLE_HIST}
        where try_cast(snapshot_as_of_date as date) <= cast(? as date)
        order by snapshot_as_of_date, stock_code, rowid
        """,
        [evaluation_as_of_date],
    ).fetchall()
    return [dict(zip(["_rowid", *columns], row, strict=True)) for row in rows]


def _load_candidate_observation_windows(
    conn: duckdb.DuckDBPyConnection,
    *,
    candidates: list[dict[str, Any]],
    evaluation_as_of_date: str,
    minimum_snapshot_date: str,
    observation_columns: set[str],
) -> tuple[dict[int, dict[str, Any]], list[str], int]:
    conn.execute(
        """
        create temp table maturity_candidate_scope (
          candidate_rowid bigint,
          stock_code varchar,
          snapshot_date date
        )
        """
    )
    scope_rows = [
        (int(candidate["_rowid"]), stock_code, snapshot_date)
        for candidate in candidates
        if (stock_code := str(candidate.get("stock_code") or "").strip().upper())
        and (snapshot_date := _normalize_date_value(candidate.get("snapshot_as_of_date")))
    ]
    if scope_rows:
        conn.executemany(
            "insert into maturity_candidate_scope values (?, ?, cast(? as date))",
            scope_rows,
        )

    has_trade_status = "tradestatus" in observation_columns
    status_expr = "cast(tradestatus as varchar)" if has_trade_status else "cast(null as varchar)"
    valid_status_sql = tradable_status_sql_condition("trade_status") if has_trade_status else "true"
    lineage_select = ", ".join(
        f"cast({field} as varchar) as {field}"
        if field in observation_columns
        else f"cast(null as varchar) as {field}"
        for field in _LINEAGE_FIELDS
    )
    rows = conn.execute(
        f"""
        with normalized_observations as materialized (
          select
            rowid as observation_rowid,
            try_cast(trade_date as date) as trade_date,
            upper(trim(cast(stock_code as varchar))) as stock_code,
            try_cast(close_value as double) as close_value,
            {status_expr} as trade_status,
            {lineage_select},
            row_number() over (
              partition by upper(trim(cast(stock_code as varchar))), try_cast(trade_date as date)
              order by rowid desc
            ) as dedupe_rank
          from {TABLE_OBS}
          where try_cast(trade_date as date) > cast(? as date)
            and try_cast(trade_date as date) <= cast(? as date)
        ),
        candidate_observations as materialized (
          select
            scope.candidate_rowid,
            obs.*,
            (
              obs.close_value > 0
              and isfinite(obs.close_value)
              and {valid_status_sql}
            ) as valid_close,
            (
              trim(coalesce(obs.trade_status, '')) <> ''
              and not ({valid_status_sql})
            ) as explicit_halt
          from maturity_candidate_scope scope
          join normalized_observations obs
            on obs.stock_code = scope.stock_code
           and obs.trade_date > scope.snapshot_date
          where obs.dedupe_rank = 1
        ),
        candidate_flags as (
          select
            candidate_rowid,
            count(*) filter (where valid_close) as stock_valid_bar_count,
            coalesce(bool_or(explicit_halt), false) as explicit_halt
          from candidate_observations
          group by candidate_rowid
        ),
        ranked_valid_bars as (
          select
            *,
            row_number() over (
              partition by candidate_rowid
              order by trade_date, observation_rowid
            ) as valid_rank
          from candidate_observations
          where valid_close
        )
        select
          flags.candidate_rowid,
          flags.stock_valid_bar_count,
          flags.explicit_halt,
          bars.trade_date,
          bars.close_value,
          {", ".join(f"bars.{field}" for field in _LINEAGE_FIELDS)}
        from candidate_flags flags
        left join ranked_valid_bars bars
          on bars.candidate_rowid = flags.candidate_rowid
         and bars.valid_rank <= 20
        order by flags.candidate_rowid, bars.valid_rank
        """,
        [minimum_snapshot_date, evaluation_as_of_date],
    ).fetchall()

    windows: dict[int, dict[str, Any]] = {}
    loaded_observation_row_count = 0
    for row in rows:
        candidate_rowid = int(row[0])
        window = windows.setdefault(
            candidate_rowid,
            {
                "valid_bars": [],
                "stock_valid_bar_count": int(row[1] or 0),
                "explicit_halt": bool(row[2]),
            },
        )
        trade_date = _normalize_date_value(row[3])
        close_value = _finite_positive_float(row[4])
        if trade_date and close_value is not None:
            window["valid_bars"].append(
                {
                    "trade_date": trade_date,
                    "close": close_value,
                    "lineage": _compact_lineage(dict(zip(_LINEAGE_FIELDS, row[5:], strict=True))),
                }
            )
            loaded_observation_row_count += 1

    market_dates = _load_market_dates(
        conn,
        evaluation_as_of_date=evaluation_as_of_date,
        minimum_snapshot_date=minimum_snapshot_date,
        has_trade_status=has_trade_status,
    )
    return windows, market_dates, loaded_observation_row_count


def _load_market_dates(
    conn: duckdb.DuckDBPyConnection,
    *,
    evaluation_as_of_date: str,
    minimum_snapshot_date: str,
    has_trade_status: bool,
) -> list[str]:
    status_select = "cast(tradestatus as varchar)" if has_trade_status else "cast(null as varchar)"
    valid_status_sql = tradable_status_sql_condition("trade_status") if has_trade_status else "true"
    rows = conn.execute(
        f"""
        with normalized as (
          select
            rowid as observation_rowid,
            try_cast(trade_date as date) as trade_date,
            upper(trim(cast(stock_code as varchar))) as stock_code,
            try_cast(close_value as double) as close_value,
            {status_select} as trade_status,
            row_number() over (
              partition by upper(trim(cast(stock_code as varchar))), try_cast(trade_date as date)
              order by rowid desc
            ) as dedupe_rank
          from {TABLE_OBS}
          where try_cast(trade_date as date) > cast(? as date)
            and try_cast(trade_date as date) <= cast(? as date)
        )
        select distinct trade_date
        from normalized
        where dedupe_rank = 1
          and close_value > 0
          and isfinite(close_value)
          and {valid_status_sql}
        order by trade_date
        """,
        [minimum_snapshot_date, evaluation_as_of_date],
    ).fetchall()
    return [normalized for row in rows if (normalized := _normalize_date_value(row[0]))]


def _required_factor_keys(
    candidates: list[dict[str, Any]],
    *,
    observation_windows: dict[int, dict[str, Any]],
) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for candidate in candidates:
        stock_code = str(candidate.get("stock_code") or "").strip().upper()
        snapshot_date = _normalize_date_value(candidate.get("snapshot_as_of_date"))
        if not stock_code or not snapshot_date:
            continue
        keys.add((stock_code, snapshot_date))
        valid_bars = observation_windows.get(int(candidate["_rowid"]), {}).get("valid_bars", [])
        for _horizon, bar_count in _HORIZONS.items():
            if len(valid_bars) < bar_count:
                continue
            # stored 与 computed 冲突时仲裁分支同样需要新目标日因子，
            # 因此无条件收集 computed 目标日的因子键。
            computed_target_date = str(valid_bars[bar_count - 1]["trade_date"])
            keys.add((stock_code, computed_target_date))
    return keys


def _load_adjustment_factors(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    factor_keys: set[tuple[str, str]],
) -> tuple[dict[tuple[str, str], dict[str, Any]], int]:
    if TABLE_ADJ_FACTOR not in tables or not factor_keys:
        return {}, 0
    columns = _table_columns(conn, TABLE_ADJ_FACTOR)
    if not {"stock_code", "trade_date", "adj_factor"}.issubset(columns):
        return {}, 0
    conn.execute(
        """
        create temp table maturity_factor_keys (
          stock_code varchar,
          trade_date date
        )
        """
    )
    conn.executemany(
        "insert into maturity_factor_keys values (?, cast(? as date))",
        sorted(factor_keys),
    )
    lineage_select = ", ".join(
        f"cast(factor.{field} as varchar) as {field}"
        if field in columns
        else f"cast(null as varchar) as {field}"
        for field in _LINEAGE_FIELDS
    )
    rows = conn.execute(
        f"""
        with factor_ranked as (
          select
            upper(trim(cast(factor.stock_code as varchar))) as stock_code,
            try_cast(factor.trade_date as date) as trade_date,
            try_cast(factor.adj_factor as double) as adj_factor,
            {lineage_select},
            row_number() over (
              partition by
                upper(trim(cast(factor.stock_code as varchar))),
                try_cast(factor.trade_date as date)
              order by factor.rowid desc
            ) as factor_rank
          from {TABLE_ADJ_FACTOR} factor
          where exists (
            select 1
            from maturity_factor_keys keys
            where keys.stock_code = upper(trim(cast(factor.stock_code as varchar)))
              and keys.trade_date = try_cast(factor.trade_date as date)
          )
        )
        select stock_code, trade_date, adj_factor, {", ".join(_LINEAGE_FIELDS)}
        from factor_ranked
        where factor_rank = 1
        order by stock_code, trade_date
        """
    ).fetchall()
    factors: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        stock_code = str(row[0] or "").strip().upper()
        trade_date = _normalize_date_value(row[1])
        if not stock_code or not trade_date:
            continue
        factors[(stock_code, trade_date)] = {
            "value": _finite_positive_float(row[2]),
            "lineage": _compact_lineage(dict(zip(_LINEAGE_FIELDS, row[3:], strict=True))),
        }
    return factors, len(rows)


def _empty_observation_window() -> dict[str, Any]:
    return {
        "valid_bars": [],
        "stock_valid_bar_count": 0,
        "explicit_halt": False,
    }


def _factor_value(record: dict[str, Any] | None) -> float | None:
    return _finite_positive_float(record.get("value")) if record is not None else None


def _compact_lineage(values: dict[str, Any]) -> dict[str, str]:
    return {
        field: text
        for field in _LINEAGE_FIELDS
        if (text := str(values.get(field) or "").strip())
    }


def _build_actual_lineage(
    *,
    target_observation_lineage: dict[str, dict[str, str]],
    signal_factor_record: dict[str, Any] | None,
    target_factor_records: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    actual_used: dict[str, Any] = {}
    lineage_documents: list[dict[str, str]] = []
    if target_observation_lineage:
        target_observations = {
            horizon: dict(target_observation_lineage[horizon])
            for horizon in _HORIZONS
            if horizon in target_observation_lineage
        }
        actual_used["target_observations"] = target_observations
        lineage_documents.extend(target_observations.values())

    adjustment_factors: dict[str, Any] = {}
    if signal_factor_record is not None:
        signal_lineage = dict(signal_factor_record.get("lineage") or {})
        adjustment_factors["signal"] = signal_lineage
        lineage_documents.append(signal_lineage)
    if target_factor_records:
        target_lineages = {
            horizon: dict(target_factor_records[horizon].get("lineage") or {})
            for horizon in _HORIZONS
            if horizon in target_factor_records
        }
        adjustment_factors["targets"] = target_lineages
        lineage_documents.extend(target_lineages.values())
    if adjustment_factors:
        actual_used["adjustment_factors"] = adjustment_factors

    version_sets = {
        field: sorted(
            {
                value
                for document in lineage_documents
                if (value := str(document.get(field) or "").strip())
            }
        )
        for field in _LINEAGE_FIELDS
    }
    version_sets = {field: values for field, values in version_sets.items() if values}
    canonical_actual_used = json.dumps(
        actual_used,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return {
        "actual_used": actual_used,
        "version_sets": version_sets,
        "lineage_hash": hashlib.sha256(canonical_actual_used.encode("utf-8")).hexdigest(),
    }


def _candidate_outcome_updates(
    candidate: dict[str, Any],
    *,
    observation_window: dict[str, Any],
    market_dates: list[str],
    factors: dict[tuple[str, str], dict[str, Any]],
    evaluation_as_of_date: str,
    run_id: str,
    table_present: list[str],
    arbitrate_conflicts: bool,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[str], str | None, int]:
    snapshot_date = _normalize_date_value(candidate.get("snapshot_as_of_date"))
    stock_code = str(candidate.get("stock_code") or "").strip().upper()
    selection_close = _finite_positive_float(candidate.get("selection_close"))
    if snapshot_date is None or not stock_code or selection_close is None:
        return (
            {},
            _invalid_candidate_maturity(snapshot_date),
            [f"{snapshot_date or '?'}:{stock_code or '?'}:invalid_candidate"],
            None,
            0,
        )

    valid_bars = list(observation_window.get("valid_bars", []))
    stock_valid_bar_count = int(observation_window.get("stock_valid_bar_count") or 0)
    market_trade_date_count = len(market_dates) - bisect_right(market_dates, snapshot_date)
    explicit_halt = bool(observation_window.get("explicit_halt"))
    signal_factor_record = factors.get((stock_code, snapshot_date))
    signal_factor = _factor_value(signal_factor_record)
    updates: dict[str, Any] = {}
    maturity: dict[str, dict[str, Any]] = {}
    target_factors: dict[str, float | None] = {}
    target_factor_records: dict[str, dict[str, Any]] = {}
    target_observation_lineage: dict[str, dict[str, str]] = {}
    row_issues: list[str] = []
    arbitrations: list[dict[str, Any]] = []

    for horizon, bar_count in _HORIZONS.items():
        date_column = f"forward_trade_date_{horizon}"
        raw_column = f"return_{horizon}"
        adjusted_column = f"return_{horizon}_adj"
        computed_target = valid_bars[bar_count - 1] if len(valid_bars) >= bar_count else None
        stored_target_date = _normalize_date_value(candidate.get(date_column))
        target_date: str | None = None
        target_close: float | None = None
        arbitration: dict[str, Any] | None = None
        if (
            stored_target_date
            and computed_target is not None
            and stored_target_date == computed_target["trade_date"]
        ):
            target_date = str(computed_target["trade_date"])
            target_close = float(computed_target["close"])
        elif stored_target_date and computed_target is not None:
            if arbitrate_conflicts:
                # revision-current canonical：当前修订行情的第 N 个有效 bar 覆盖
                # stored 三元组；旧值随本事件完整写入 audit（conflict_arbitrations）。
                target_date = str(computed_target["trade_date"])
                target_close = float(computed_target["close"])
                updates[date_column] = target_date
                arbitration = {
                    "type": "stored_target_conflict",
                    "horizon": horizon,
                    "decision": "current_revision_wins",
                    "reason": "current_revision_calendar_mismatch",
                    "stored": {
                        "date": stored_target_date,
                        "raw": _finite_float(candidate.get(raw_column)),
                        "adj": _finite_float(candidate.get(adjusted_column)),
                    },
                }
                row_issues.append(
                    f"{snapshot_date}:{stock_code}:{horizon}:stored_target_conflict_arbitrated"
                )
            else:
                row_issues.append(f"{snapshot_date}:{stock_code}:{horizon}:stored_target_conflict")
        elif candidate.get(date_column) is None and computed_target is not None:
            target_date = str(computed_target["trade_date"])
            target_close = float(computed_target["close"])
            updates[date_column] = target_date

        if target_date and computed_target is not None:
            target_observation_lineage[horizon] = dict(computed_target.get("lineage") or {})

        raw_return = _finite_float(candidate.get(raw_column))
        if (candidate.get(raw_column) is None or arbitration is not None) and target_close is not None:
            raw_return = _finite_float(target_close / selection_close - 1.0)
            if raw_return is not None:
                updates[raw_column] = raw_return

        target_factor_record = factors.get((stock_code, target_date)) if target_date else None
        target_factor = _factor_value(target_factor_record)
        target_factors[horizon] = target_factor
        if target_factor_record is not None:
            target_factor_records[horizon] = target_factor_record
        adjusted_return = _finite_float(candidate.get(adjusted_column))
        if arbitration is not None and target_close is not None:
            # 目标日已变：adjusted return 必须按新日期原子重算；新目标日因子
            # 缺失时置空，禁止沿用旧日期口径的 adjusted return。
            adjusted_return = _adjusted_return(
                start_price=selection_close,
                start_factor=signal_factor,
                end_price=target_close,
                end_factor=target_factor,
            )
            updates[adjusted_column] = adjusted_return
            arbitration["computed"] = {
                "date": target_date,
                "close": target_close,
                "raw": raw_return,
                "adj": adjusted_return,
            }
            arbitrations.append(arbitration)
        elif candidate.get(adjusted_column) is None and target_close is not None:
            adjusted_return = _adjusted_return(
                start_price=selection_close,
                start_factor=signal_factor,
                end_price=target_close,
                end_factor=target_factor,
            )
            if adjusted_return is not None:
                updates[adjusted_column] = adjusted_return

        status = _horizon_status(
            bar_count=bar_count,
            stock_valid_bar_count=stock_valid_bar_count,
            market_trade_date_count=market_trade_date_count,
            raw_return=raw_return,
            adjusted_return=adjusted_return,
            target_trade_date=target_date,
            evaluation_as_of_date=evaluation_as_of_date,
            explicit_halt=explicit_halt,
        )
        maturity[horizon] = {
            "status": status,
            "horizon_bars": bar_count,
            "target_trade_date": target_date if target_date and target_date <= evaluation_as_of_date else None,
            "stock_valid_bar_count": stock_valid_bar_count,
            "market_trade_date_count": market_trade_date_count,
            "snapshot_as_of_date": snapshot_date,
        }

    # 仲裁改变目标日后，ex_div 结论基于旧日期不再可信，可判定时强制重算覆盖。
    if (candidate.get("ex_div_in_window") is None or arbitrations) and signal_factor is not None:
        comparable_factors = [factor for factor in target_factors.values() if factor is not None]
        if any(abs(factor - signal_factor) > 1e-12 for factor in comparable_factors):
            updates["ex_div_in_window"] = True
        elif target_factors.get("20d") is not None:
            updates["ex_div_in_window"] = False

    aggregate_status = _aggregate_data_status(maturity)
    stored_data_status = str(candidate.get("data_status") or "").strip()
    if (
        candidate.get("data_status") is None
        or (stored_data_status == "pending" and aggregate_status == "complete")
        or (arbitrations and stored_data_status != aggregate_status)
    ):
        updates["data_status"] = aggregate_status

    outcome_fields_changed = sorted(updates)
    evidence = _parse_evidence(candidate.get("signal_evidence_json"))
    if evidence is None:
        issue = f"{snapshot_date}:{stock_code}:invalid_signal_evidence_json"
        row_issues.append(issue)
        if outcome_fields_changed:
            return {}, maturity, row_issues, issue, 0
    elif outcome_fields_changed:
        raw_audit = evidence.get("outcome_maturity_audit")
        if raw_audit is None:
            audit: list[dict[str, Any]] = []
        elif isinstance(raw_audit, list) and all(isinstance(item, dict) for item in raw_audit):
            audit = [dict(item) for item in raw_audit]
        else:
            issue = f"{snapshot_date}:{stock_code}:invalid_outcome_maturity_audit"
            row_issues.append(issue)
            return {}, maturity, row_issues, issue, 0
        effective_ex_div = (
            candidate.get("ex_div_in_window")
            if candidate.get("ex_div_in_window") is not None
            else updates.get("ex_div_in_window")
        )
        current_adjustment_state = {
            "price_adjustment_mode": PRICE_ADJUSTMENT_MODE,
            "signal_adj_factor": signal_factor,
            "forward_adj_factors": {
                horizon: factor
                for horizon, factor in target_factors.items()
                if maturity[horizon]["target_trade_date"] is not None
            },
            "missing_horizons": [
                horizon
                for horizon, item in maturity.items()
                if item["status"] == "raw_matured_adjustment_missing"
            ],
            "adjusted_return_complete_horizons": [
                horizon
                for horizon in _HORIZONS
                if _finite_float(
                    updates.get(
                        f"return_{horizon}_adj",
                        candidate.get(f"return_{horizon}_adj"),
                    )
                )
                is not None
            ],
            "ex_div_complete": effective_ex_div is not None,
            "ex_div_in_window": effective_ex_div,
        }
        lineage = _build_actual_lineage(
            target_observation_lineage=target_observation_lineage,
            signal_factor_record=signal_factor_record,
            target_factor_records=target_factor_records,
        )
        actual_table_set = {TABLE_HIST}
        if target_observation_lineage:
            actual_table_set.add(TABLE_OBS)
        if signal_factor_record is not None or target_factor_records:
            actual_table_set.add(TABLE_ADJ_FACTOR)
        audit_event = {
            "contract_version": OUTCOME_CONTRACT_VERSION,
            "formula_version": OUTCOME_FORMULA_VERSION,
            "evaluation_as_of_date": evaluation_as_of_date,
            "run_id": run_id,
            "updated_fields": outcome_fields_changed,
            "horizons": maturity,
            "current_adjustment_state": current_adjustment_state,
            "source_tables": {
                "actual_used": [table for table in table_present if table in actual_table_set],
                "table_present": list(table_present),
            },
            "lineage": lineage,
            "observational_only": True,
            "formal_use_allowed": False,
        }
        if arbitrations:
            audit_event["conflict_arbitrations"] = arbitrations
        if audit_event not in audit:
            audit.append(audit_event)
        evidence["outcome_maturity_audit"] = audit
        serialized = json.dumps(evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if serialized != str(candidate.get("signal_evidence_json") or ""):
            updates["signal_evidence_json"] = serialized

    return updates, maturity, row_issues, None, len(arbitrations)


def _horizon_status(
    *,
    bar_count: int,
    stock_valid_bar_count: int,
    market_trade_date_count: int,
    raw_return: float | None,
    adjusted_return: float | None,
    target_trade_date: str | None,
    evaluation_as_of_date: str,
    explicit_halt: bool,
) -> str:
    target_is_usable = bool(target_trade_date and target_trade_date <= evaluation_as_of_date)
    if target_is_usable and raw_return is not None:
        return "complete" if adjusted_return is not None else "raw_matured_adjustment_missing"
    if market_trade_date_count < bar_count:
        return "natural_pending"
    if explicit_halt and stock_valid_bar_count < bar_count:
        return "partial_halt"
    return "matured_missing_bar"


def _update_candidate_outcomes(
    conn: duckdb.DuckDBPyConnection,
    *,
    row_id: int,
    updates: dict[str, Any],
) -> None:
    unexpected = set(updates) - _OUTCOME_COLUMNS
    if unexpected:
        raise ValueError(f"Non-outcome columns cannot be updated: {sorted(unexpected)}")
    assignments = ", ".join(f"{column} = ?" for column in updates)
    conn.execute(
        f"update {TABLE_HIST} set {assignments} where rowid = ?",
        [*updates.values(), row_id],
    )


def _horizon_summary(items_by_horizon: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for horizon, items in items_by_horizon.items():
        counts = {status: 0 for status in _MATURITY_STATUSES}
        mature_dates: list[str] = []
        pending_dates: list[str] = []
        for item in items:
            status = str(item["status"])
            counts[status] += 1
            snapshot_date = str(item.get("snapshot_as_of_date") or "")
            if status == "natural_pending":
                pending_dates.append(snapshot_date)
            else:
                mature_dates.append(snapshot_date)
        summary[horizon] = {
            "horizon_bars": _HORIZONS[horizon],
            "row_count": len(items),
            "counts": counts,
            "latest_mature_snapshot_date": max(mature_dates) if mature_dates else None,
            "latest_pending_snapshot_date": max(pending_dates) if pending_dates else None,
        }
    return summary


def _empty_result(
    *,
    status: str,
    evaluation_as_of_date: str,
    reason: str | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "status": status,
        "evaluation_as_of_date": evaluation_as_of_date,
        "candidate_row_count": 0,
        "updated_row_count": 0,
        "updated_field_count": 0,
        "arbitrate_conflicts": True,
        "arbitrated_conflict_count": 0,
        "blocked_row_count": 0,
        "blocked_rows": [],
        "loaded_observation_row_count": 0,
        "loaded_market_date_count": 0,
        "requested_factor_key_count": 0,
        "loaded_factor_row_count": 0,
        "formula_version": OUTCOME_FORMULA_VERSION,
        "contract_version": OUTCOME_CONTRACT_VERSION,
        "horizons": _horizon_summary({horizon: [] for horizon in _HORIZONS}),
        "issues": [],
        "observational_only": True,
        "formal_use_allowed": False,
    }
    if reason:
        result["reason"] = reason
    return result


def _invalid_candidate_maturity(snapshot_date: str | None) -> dict[str, dict[str, Any]]:
    return {
        horizon: {
            "status": "matured_missing_bar",
            "horizon_bars": bar_count,
            "target_trade_date": None,
            "stock_valid_bar_count": 0,
            "market_trade_date_count": 0,
            "snapshot_as_of_date": snapshot_date,
        }
        for horizon, bar_count in _HORIZONS.items()
    }


def _aggregate_data_status(maturity: dict[str, dict[str, Any]]) -> str:
    statuses = {str(item["status"]) for item in maturity.values()}
    if statuses == {"complete"}:
        return "complete"
    if "partial_halt" in statuses:
        return "partial_halt"
    return "pending"


def _normalize_evaluation_date(value: str | None) -> str:
    text = str(value or date.today().isoformat()).strip()
    if not text:
        raise ValueError("evaluation_as_of_date cannot be blank")
    return date.fromisoformat(text[:10]).isoformat()


def _normalize_date_value(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def _finite_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _finite_positive_float(value: Any) -> float | None:
    number = _finite_float(value)
    return number if number is not None and number > 0 else None


def _adjusted_return(
    *,
    start_price: float,
    start_factor: float | None,
    end_price: float,
    end_factor: float | None,
) -> float | None:
    if start_factor is None or end_factor is None:
        return None
    return _finite_float((end_price * end_factor) / (start_price * start_factor) - 1.0)


def _parse_evidence(value: Any) -> dict[str, Any] | None:
    if value is None or not str(value).strip():
        return {}
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return dict(parsed) if isinstance(parsed, dict) else None


def _table_columns(conn: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    return {str(row[1]).lower() for row in conn.execute(f"pragma table_info('{table_name}')").fetchall()}
