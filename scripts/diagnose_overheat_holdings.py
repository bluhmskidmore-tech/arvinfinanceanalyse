from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections.abc import Mapping, Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.core_finance.gate_exposure_series import load_gate_exposure_by_date  # noqa: E402
from backend.app.core_finance.livermore_risk_exit import (  # noqa: E402
    FORMULA_VERSION as RISK_EXIT_FORMULA_VERSION,
)
from backend.app.core_finance.livermore_risk_exit import RiskExitSnapshot, compute_risk_exit  # noqa: E402
from backend.app.core_finance.strategy_policy import POLICY  # noqa: E402

DEFAULT_REPORT_PATH = Path("docs/pnl/2026-07-batch2-overheat-holdings-report.md")
TABLE_POSITION = "livermore_position_snapshot"
TABLE_OBS = "choice_stock_daily_observation"
TABLE_ADJ_FACTOR = "stock_adjustment_factor"
HORIZONS = (5, 10, 20)
BLINDSPOT_DRAWDOWN_THRESHOLD = 0.08
MAX_HISTORY_DAYS = 180
MAX_FUTURE_DAYS = 80


def analyze_overheat_holding_samples(
    samples: Sequence[Mapping[str, object]],
    *,
    blindspot_drawdown_threshold: float = BLINDSPOT_DRAWDOWN_THRESHOLD,
) -> dict[str, Any]:
    if not samples:
        return {"status": "blocked", "reason": "No holding samples were available."}

    by_state: dict[str, list[Mapping[str, object]]] = {}
    for sample in samples:
        state = _text(sample.get("market_state")) or "UNKNOWN"
        by_state.setdefault(state, []).append(sample)

    state_summary: dict[str, Any] = {}
    for state, rows in sorted(by_state.items()):
        state_summary[state] = {
            "sample_count": len(rows),
            "stock_count": len({_text(row.get("stock_code")) for row in rows if _text(row.get("stock_code"))}),
            "returns": {
                f"{horizon}d": _return_stats([_safe_float(row.get(f"return_{horizon}d_net")) for row in rows])
                for horizon in HORIZONS
            },
            "max_drawdown": {
                f"{horizon}d": _drawdown_stats([_safe_float(row.get(f"max_drawdown_{horizon}d")) for row in rows])
                for horizon in HORIZONS
            },
        }

    overheat_rows = [row for row in samples if _text(row.get("market_state")) == "OVERHEAT"]
    overheat_evaluable = [
        row
        for row in overheat_rows
        if bool(row.get("risk_exit_evaluable")) and _safe_float(row.get("max_drawdown_10d")) is not None
    ]
    blindspots = [
        row
        for row in overheat_evaluable
        if not bool(row.get("risk_exit_triggered"))
        and (_safe_float(row.get("max_drawdown_10d")) or 0.0) > blindspot_drawdown_threshold
    ]
    blindspot_ratio = len(blindspots) / len(overheat_evaluable) if overheat_evaluable else None
    conclusion = _overheat_conclusion(state_summary, blindspot_ratio=blindspot_ratio)
    return {
        "status": "ready",
        "sample_count": len(samples),
        "state_summary": state_summary,
        "overheat_blindspot": {
            "threshold": blindspot_drawdown_threshold,
            "sample_count": len(overheat_rows),
            "evaluable_sample_count": len(overheat_evaluable),
            "blindspot_count": len(blindspots),
            "blindspot_ratio": _round_optional(blindspot_ratio),
            "sample_reach_stock_count": len(
                {_text(row.get("stock_code")) for row in overheat_rows if _text(row.get("stock_code"))}
            ),
        },
        "conclusion": conclusion,
        "rule_candidates": _rule_candidates(conclusion, overheat_count=len(overheat_rows)),
    }


def run_overheat_holdings_diagnostic(
    *,
    db_path: str,
    report_path: str | Path = DEFAULT_REPORT_PATH,
) -> dict[str, Any]:
    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    db_file = Path(db_path)
    if not db_file.exists():
        payload = _blocked_payload(f"DuckDB file not found: {db_file}")
        _write_report(report, payload)
        return payload

    conn = duckdb.connect(str(db_file), read_only=True)
    try:
        tables = _table_names(conn)
        missing = [table for table in (TABLE_POSITION, TABLE_OBS) if table not in tables]
        if missing:
            payload = _blocked_payload(f"Missing required table(s): {', '.join(missing)}")
            _write_report(report, payload)
            return payload
        positions, position_issues = _load_position_rows(conn)
        if position_issues:
            payload = _blocked_payload("; ".join(position_issues))
            _write_report(report, payload)
            return payload
        if not positions:
            payload = _blocked_payload("No ACTIVE livermore_position_snapshot rows were available.")
            _write_report(report, payload)
            return payload
        price_rows_by_code, price_issues = _load_price_rows(conn, tables=tables, positions=positions)
        start_date = min(str(row["as_of_date"]) for row in positions)
        end_date = max(str(row["as_of_date"]) for row in positions)
        gate_points = load_gate_exposure_by_date(conn, start_date, end_date)
        samples, sample_issues = _build_samples(
            positions,
            price_rows_by_code=price_rows_by_code,
            gate_points=gate_points,
        )
    finally:
        conn.close()

    if not samples:
        payload = _blocked_payload("No holding samples could be joined to price history.")
        payload["issues"] = [*price_issues, *sample_issues]
        _write_report(report, payload)
        return payload

    payload = analyze_overheat_holding_samples(samples)
    payload.update(
        {
            "db_path": str(db_file),
            "report_path": str(report),
            "risk_exit_formula_version": RISK_EXIT_FORMULA_VERSION,
            "price_basis": _price_basis(samples),
            "adjustment_factor_missing_rows": sum(
                int(sample.get("adjustment_factor_missing_rows") or 0) for sample in samples
            ),
            "issues": [*price_issues, *sample_issues],
        }
    )
    _write_report(report, payload)
    return payload


def _load_position_rows(conn: duckdb.DuckDBPyConnection) -> tuple[list[dict[str, object]], list[str]]:
    columns = _columns(conn, TABLE_POSITION)
    required = {"as_of_date", "stock_code", "entry_cost", "bars_since_entry", "position_status"}
    missing = sorted(required - columns)
    if missing:
        return [], [f"{TABLE_POSITION} missing columns: {', '.join(missing)}"]
    stock_name_select = "stock_name" if "stock_name" in columns else "stock_code as stock_name"
    entry_date_select = "entry_date" if "entry_date" in columns else "cast(null as varchar) as entry_date"
    quantity_select = "position_quantity" if "position_quantity" in columns else "cast(null as double) as position_quantity"
    rows = conn.execute(
        f"""
        select
          as_of_date,
          stock_code,
          {stock_name_select},
          entry_cost,
          bars_since_entry,
          {entry_date_select},
          {quantity_select}
        from {TABLE_POSITION}
        where upper(coalesce(position_status, 'ACTIVE')) = 'ACTIVE'
          and as_of_date is not null
          and stock_code is not null
        order by cast(as_of_date as date), stock_code
        """
    ).fetchall()
    return [
        {
            "as_of_date": str(as_of_date)[:10],
            "stock_code": _text(stock_code),
            "stock_name": _text(stock_name) or _text(stock_code),
            "entry_cost": entry_cost,
            "bars_since_entry": bars_since_entry,
            "entry_date": _date_text(entry_date),
            "position_quantity": position_quantity,
        }
        for as_of_date, stock_code, stock_name, entry_cost, bars_since_entry, entry_date, position_quantity in rows
    ], []


def _load_price_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    positions: Sequence[Mapping[str, object]],
) -> tuple[dict[str, list[dict[str, object]]], list[str]]:
    obs_columns = _columns(conn, TABLE_OBS)
    required = {"trade_date", "stock_code", "close_value", "volume"}
    missing = sorted(required - obs_columns)
    if missing:
        return {}, [f"{TABLE_OBS} missing columns: {', '.join(missing)}"]
    has_adj = TABLE_ADJ_FACTOR in tables and {"stock_code", "trade_date", "adj_factor"}.issubset(
        _columns(conn, TABLE_ADJ_FACTOR)
    )
    codes = sorted({_text(row.get("stock_code")) for row in positions if _text(row.get("stock_code"))})
    if not codes:
        return {}, ["No stock codes were present in ACTIVE position rows."]
    min_date = min(_parse_date(row["as_of_date"]) for row in positions) - timedelta(days=MAX_HISTORY_DAYS)
    max_date = max(_parse_date(row["as_of_date"]) for row in positions) + timedelta(days=MAX_FUTURE_DAYS)
    placeholders = ", ".join("?" for _ in codes)
    adj_select = "af.adj_factor" if has_adj else "cast(null as double) as adj_factor"
    adj_join = (
        f"""
        left join {TABLE_ADJ_FACTOR} af
          on af.stock_code = d.stock_code
         and af.trade_date = d.trade_date
        """
        if has_adj
        else ""
    )
    rows = conn.execute(
        f"""
        select d.stock_code, d.trade_date, d.close_value, d.volume, {adj_select}
        from {TABLE_OBS} d
        {adj_join}
        where d.stock_code in ({placeholders})
          and cast(d.trade_date as date) >= cast(? as date)
          and cast(d.trade_date as date) <= cast(? as date)
          and d.close_value is not null
        order by d.stock_code, cast(d.trade_date as date)
        """,
        [*codes, min_date.isoformat(), max_date.isoformat()],
    ).fetchall()
    by_code: dict[str, list[dict[str, object]]] = {}
    for stock_code, trade_date, close_value, volume, adj_factor in rows:
        close = _safe_float(close_value)
        factor = _safe_float(adj_factor)
        if close is None:
            continue
        factor_missing = has_adj and factor is None
        mark_price = close * factor if factor is not None and factor > 0 else close
        by_code.setdefault(_text(stock_code), []).append(
            {
                "trade_date": str(trade_date)[:10],
                "close": close,
                "volume": _safe_float(volume),
                "adj_factor": factor,
                "adj_factor_missing": factor_missing,
                "mark_price": mark_price,
            }
        )
    return by_code, []


def _build_samples(
    positions: Sequence[Mapping[str, object]],
    *,
    price_rows_by_code: Mapping[str, Sequence[Mapping[str, object]]],
    gate_points: Mapping[str, Any],
) -> tuple[list[dict[str, object]], list[str]]:
    samples: list[dict[str, object]] = []
    issues: list[str] = []
    for position in positions:
        stock_code = _text(position.get("stock_code"))
        as_of_date = _date_text(position.get("as_of_date"))
        rows = list(price_rows_by_code.get(stock_code, ()))
        start_index = _start_index(rows, as_of_date)
        if start_index is None:
            issues.append(f"No price row on or before {as_of_date} for {stock_code}.")
            continue
        gate_point = gate_points.get(as_of_date)
        market_state = _text(getattr(gate_point, "state", "")) or "NO_DATA"
        exposure = _safe_float(getattr(gate_point, "exposure", None)) if gate_point is not None else 0.0
        sample = {
            "as_of_date": as_of_date,
            "price_as_of_date": rows[start_index]["trade_date"],
            "stock_code": stock_code,
            "stock_name": _text(position.get("stock_name")) or stock_code,
            "market_state": market_state,
            "market_gate_exposure": exposure,
            "market_gate_source": _text(getattr(gate_point, "source", "")) or "missing",
            "adjustment_factor_missing_rows": 0,
        }
        sample.update(_future_metrics(rows, start_index=start_index))
        sample.update(_risk_exit_metrics(position, rows=rows[: start_index + 1], as_of_date=as_of_date))
        samples.append(sample)
    return samples, issues


def _future_metrics(rows: Sequence[Mapping[str, object]], *, start_index: int) -> dict[str, object]:
    out: dict[str, object] = {}
    start_price = _safe_float(rows[start_index].get("mark_price"))
    if start_price is None or start_price <= 0:
        return out
    for horizon in HORIZONS:
        end_index = start_index + horizon
        if end_index >= len(rows):
            out[f"return_{horizon}d_net"] = None
            out[f"max_drawdown_{horizon}d"] = None
            continue
        path = list(rows[start_index : end_index + 1])
        end_price = _safe_float(path[-1].get("mark_price"))
        gross_return = end_price / start_price - 1.0 if end_price is not None and end_price > 0 else None
        net_return = (
            gross_return - POLICY.sell_cost_rate - POLICY.slippage_rate
            if gross_return is not None
            else None
        )
        prices = [_safe_float(row.get("mark_price")) for row in path]
        out[f"return_{horizon}d_net"] = _round_optional(net_return)
        out[f"max_drawdown_{horizon}d"] = _round_optional(
            _max_drawdown([price for price in prices if price is not None])
        )
        out["adjustment_factor_missing_rows"] = int(out.get("adjustment_factor_missing_rows") or 0) + sum(
            1 for row in path if bool(row.get("adj_factor_missing"))
        )
    return out


def _risk_exit_metrics(
    position: Mapping[str, object],
    *,
    rows: Sequence[Mapping[str, object]],
    as_of_date: str,
) -> dict[str, object]:
    history = list(rows[-65:])
    snapshot = RiskExitSnapshot(
        stock_code=_text(position.get("stock_code")),
        stock_name=_text(position.get("stock_name")),
        entry_cost=position.get("entry_cost"),
        bars_since_entry=position.get("bars_since_entry"),
        close_history=[row.get("close") for row in history],
        volume_history=[row.get("volume") for row in history],
    )
    payload = compute_risk_exit(as_of_date=as_of_date, snapshots=[snapshot]).payload
    return {
        "risk_exit_evaluable": bool(payload.get("watch_items")),
        "risk_exit_triggered": int(payload.get("signal_count") or 0) > 0,
        "risk_exit_insufficient_history": int(payload.get("insufficient_history_count") or 0) > 0,
    }


def _write_report(path: Path, payload: Mapping[str, Any]) -> None:
    if payload.get("status") != "ready":
        lines = [
            "# 2026-07 Batch 2 OVERHEAT Holdings Diagnostic",
            "",
            f"- status: {payload.get('status', 'blocked')}",
            f"- reason: {payload.get('reason', 'No diagnostic was generated.')}",
        ]
        for issue in payload.get("issues") or []:
            lines.append(f"- issue: {issue}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    overheat = payload["overheat_blindspot"]
    lines = [
        "# 2026-07 Batch 2 OVERHEAT Holdings Diagnostic",
        "",
        "- status: ready",
        f"- db_path: {payload.get('db_path')}",
        f"- conclusion: {payload.get('conclusion')}",
        f"- sample_count: {payload.get('sample_count')}",
        f"- price_basis: {payload.get('price_basis')}",
        f"- adjustment_factor_missing_rows: {payload.get('adjustment_factor_missing_rows')}",
        f"- risk_exit_formula_version: {payload.get('risk_exit_formula_version')}",
        f"- overheat_sample_count: {overheat['sample_count']}",
        f"- overheat_blindspot_ratio: {_fmt(overheat.get('blindspot_ratio'))}",
        "",
        "## State Summary",
        "",
        "| state | samples | stocks | horizon | avg_net_return | win_rate | avg_max_drawdown |",
        "|---|---:|---:|---|---:|---:|---:|",
    ]
    for state, summary in payload["state_summary"].items():
        for horizon in (f"{item}d" for item in HORIZONS):
            returns = summary["returns"][horizon]
            drawdown = summary["max_drawdown"][horizon]
            lines.append(
                "| {state} | {samples} | {stocks} | {horizon} | {avg} | {win} | {dd} |".format(
                    state=state,
                    samples=summary["sample_count"],
                    stocks=summary["stock_count"],
                    horizon=horizon,
                    avg=_fmt(returns.get("avg_net_return")),
                    win=_fmt(returns.get("win_rate")),
                    dd=_fmt(drawdown.get("avg_max_drawdown")),
                )
            )
    lines.extend(["", "## Rule Candidates", ""])
    for candidate in payload.get("rule_candidates") or []:
        lines.append(f"- {candidate}")
    for issue in payload.get("issues") or []:
        lines.append(f"- issue: {issue}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _return_stats(values: Sequence[float | None]) -> dict[str, object]:
    valid = [float(value) for value in values if value is not None and math.isfinite(value)]
    if not valid:
        return {"count": 0, "avg_net_return": None, "win_rate": None, "p10_net_return": None}
    return {
        "count": len(valid),
        "avg_net_return": _round_optional(statistics.fmean(valid)),
        "win_rate": _round_optional(sum(1 for value in valid if value > 0) / len(valid)),
        "p10_net_return": _round_optional(_quantile(valid, 0.10)),
    }


def _drawdown_stats(values: Sequence[float | None]) -> dict[str, object]:
    valid = [float(value) for value in values if value is not None and math.isfinite(value)]
    if not valid:
        return {"count": 0, "avg_max_drawdown": None, "p90_max_drawdown": None}
    return {
        "count": len(valid),
        "avg_max_drawdown": _round_optional(statistics.fmean(valid)),
        "p90_max_drawdown": _round_optional(_quantile(valid, 0.90)),
    }


def _overheat_conclusion(state_summary: Mapping[str, Any], *, blindspot_ratio: float | None) -> str:
    overheat = state_summary.get("OVERHEAT")
    if not overheat:
        return "overheat_holding_samples_unavailable"
    overheat_20d = overheat["returns"]["20d"].get("avg_net_return")
    if blindspot_ratio is not None and blindspot_ratio >= 0.2:
        return "overheat_holding_blindspot_needs_rule_research"
    if overheat_20d is not None and overheat_20d < 0:
        return "overheat_holding_drag_observed"
    return "overheat_holding_rule_change_low_priority"


def _rule_candidates(conclusion: str, *, overheat_count: int) -> list[str]:
    if overheat_count <= 0:
        return ["Collect OVERHEAT holding samples before changing any holding rule."]
    if conclusion == "overheat_holding_blindspot_needs_rule_research":
        return [
            f"Evaluate OVERHEAT exposure downgrade for existing holdings; estimated sample reach {overheat_count} holding-days.",
            f"Evaluate tighter trailing exit under OVERHEAT when current risk_exit is not triggered; estimated sample reach {overheat_count} holding-days.",
        ]
    if conclusion == "overheat_holding_drag_observed":
        return [
            f"Evaluate OVERHEAT exposure downgrade before adding complex exits; estimated sample reach {overheat_count} holding-days."
        ]
    return [f"Keep rules unchanged until a larger OVERHEAT sample appears; current reach {overheat_count} holding-days."]


def _price_basis(samples: Sequence[Mapping[str, object]]) -> str:
    missing = sum(int(sample.get("adjustment_factor_missing_rows") or 0) for sample in samples)
    return "raw_close_missing_adjustment_factor" if missing else "adjusted_close_or_raw_when_no_factor_table"


def _start_index(rows: Sequence[Mapping[str, object]], as_of_date: str) -> int | None:
    candidates = [index for index, row in enumerate(rows) if _date_text(row.get("trade_date")) <= as_of_date]
    return max(candidates) if candidates else None


def _max_drawdown(values: Sequence[float]) -> float | None:
    if not values:
        return None
    peak = values[0]
    max_drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            max_drawdown = max(max_drawdown, 1.0 - value / peak)
    return max_drawdown


def _quantile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(max(int(math.ceil(q * len(ordered))) - 1, 0), len(ordered) - 1)
    return ordered[index]


def _blocked_payload(reason: str) -> dict[str, Any]:
    return {"status": "blocked", "reason": reason}


def _table_names(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {str(row[0]) for row in conn.execute("show tables").fetchall()}


def _columns(conn: duckdb.DuckDBPyConnection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f"pragma table_info('{table}')").fetchall()}


def _safe_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _round_optional(value: float | None) -> float | None:
    return round(value, 6) if value is not None and math.isfinite(value) else None


def _parse_date(value: object) -> date:
    return date.fromisoformat(_date_text(value))


def _date_text(value: object) -> str:
    return "" if value is None else str(value).strip()[:10]


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _fmt(value: object) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose OVERHEAT holding risk without changing live rules.")
    parser.add_argument("--db-path", default="data/moss.duckdb", help="DuckDB database path.")
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH), help="Markdown report path.")
    args = parser.parse_args()
    payload = run_overheat_holdings_diagnostic(db_path=args.db_path, report_path=args.report_path)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))


if __name__ == "__main__":
    main()
