from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb


TABLE_HIST = "livermore_candidate_history"
TABLE_DAILY = "choice_stock_daily_observation"
TABLE_FACTOR = "choice_stock_factor_snapshot"
TABLE_LIMIT = "choice_stock_limit_quality"
TABLE_MACRO = "fact_choice_macro_daily"
TABLE_MARKET = "choice_market_snapshot"
SIGNAL_KIND = "factor_screen"
DEFAULT_OUTPUT_DIR = "test_output/livermore_stock_selection"
DEFAULT_TOP_N = 10
DEFAULT_MIN_AMOUNT = 0.0
DEFAULT_MAX_SECTOR_WEIGHT = 0.30
DEFAULT_STALE_CALENDAR_DAYS = 5
_NORMAL_TRADE_STATUSES = {"1", "normal", "trade", "trading", "\u4ea4\u6613"}
_FALSE_FLAGS = {"", "0", "false", "n", "no", "\u5426"}
_TRUE_FLAGS = {"1", "true", "y", "yes", "\u662f", "\u6da8\u505c", "\u8dcc\u505c"}


def export_livermore_pretrade_check(
    *,
    duckdb_path: str | Path,
    as_of_date: str | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    top_n: int = DEFAULT_TOP_N,
    min_amount: float = DEFAULT_MIN_AMOUNT,
    max_sector_weight: float = DEFAULT_MAX_SECTOR_WEIGHT,
    stale_calendar_days: int = DEFAULT_STALE_CALENDAR_DAYS,
    rerun_selection: bool = False,
    stock_candidate_policy: str | None = None,
    today: str | None = None,
) -> dict[str, object]:
    resolved_path = _resolve_duckdb_path(duckdb_path)
    normalized_top_n = max(1, int(top_n))
    rerun_result: dict[str, object] | None = None
    if rerun_selection:
        from backend.app.tasks.livermore_candidate_history_materialize import (
            materialize_livermore_candidate_history,
        )

        rerun_result = materialize_livermore_candidate_history(
            str(resolved_path),
            as_of_date=_normalize_date(as_of_date) if as_of_date else None,
            stock_candidate_policy=stock_candidate_policy,
        )

    conn = duckdb.connect(str(resolved_path), read_only=True)
    try:
        tables = _table_names(conn)
        if TABLE_HIST not in tables:
            raise ValueError(f"{TABLE_HIST} table not found.")
        resolved_as_of = _resolve_as_of_date(conn, as_of_date=as_of_date)
        candidates = _load_candidates(conn, as_of_date=resolved_as_of)
        if not candidates:
            raise ValueError(f"No {SIGNAL_KIND} candidates found for {resolved_as_of}.")
        top_rows = candidates[:normalized_top_n]
        enriched_rows = _enrich_rows(
            conn,
            tables=tables,
            as_of_date=resolved_as_of,
            rows=top_rows,
            min_amount=float(min_amount),
        )
        freshness = _freshness_checks(
            conn,
            tables=tables,
            as_of_date=resolved_as_of,
            today=today,
            stale_calendar_days=int(stale_calendar_days),
        )
    finally:
        conn.close()

    sector_distribution = _sector_distribution(enriched_rows)
    portfolio_flags = _portfolio_flags(
        enriched_rows,
        max_sector_weight=float(max_sector_weight),
    )
    market_states = _distinct_values(candidates, "market_state")
    data_statuses = _distinct_values(candidates, "data_status")
    decision = _execution_decision(
        freshness=freshness,
        rows=enriched_rows,
        portfolio_flags=portfolio_flags,
        market_states=market_states,
        data_statuses=data_statuses,
    )
    output_paths = _write_outputs(
        output_dir=Path(output_dir),
        as_of_date=resolved_as_of,
        rows=enriched_rows,
        payload={
            "status": "completed",
            "duckdb_path": str(resolved_path),
            "as_of_date": resolved_as_of,
            "signal_kind": SIGNAL_KIND,
            "candidate_count": len(candidates),
            "top_n": normalized_top_n,
            "market_states": market_states,
            "data_statuses": data_statuses,
            "freshness": freshness,
            "sector_distribution": sector_distribution,
            "portfolio_flags": portfolio_flags,
            "decision": decision,
            "rerun_result": rerun_result,
            "rows": enriched_rows,
        },
    )
    return {
        "status": "completed",
        "duckdb_path": str(resolved_path),
        "as_of_date": resolved_as_of,
        "signal_kind": SIGNAL_KIND,
        "candidate_count": len(candidates),
        "top_n": normalized_top_n,
        "market_states": market_states,
        "data_statuses": data_statuses,
        "freshness": freshness,
        "sector_distribution": sector_distribution,
        "portfolio_flags": portfolio_flags,
        "decision": decision,
        "rerun_result": rerun_result,
        "output_paths": output_paths,
        "rows": enriched_rows,
    }


def _resolve_duckdb_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {path}")
    return path


def _table_names(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {str(row[0]) for row in conn.execute("show tables").fetchall()}


def _resolve_as_of_date(conn: duckdb.DuckDBPyConnection, *, as_of_date: str | None) -> str:
    if as_of_date:
        return _normalize_date(as_of_date)
    row = conn.execute(
        f"""
        select max(snapshot_as_of_date)
        from {TABLE_HIST}
        where signal_kind = ?
        """,
        [SIGNAL_KIND],
    ).fetchone()
    resolved = str(row[0] or "").strip()[:10] if row else ""
    if not resolved:
        raise ValueError(f"No {SIGNAL_KIND} snapshot date found.")
    return resolved


def _load_candidates(conn: duckdb.DuckDBPyConnection, *, as_of_date: str) -> list[dict[str, object]]:
    rows = conn.execute(
        f"""
        select
          candidate_rank,
          stock_code,
          stock_name,
          sector_name,
          selection_close,
          market_state,
          data_status,
          closed_up_limit,
          source_version,
          vendor_version,
          run_id
        from {TABLE_HIST}
        where snapshot_as_of_date = ?
          and signal_kind = ?
        order by candidate_rank nulls last, stock_code
        """,
        [as_of_date, SIGNAL_KIND],
    ).fetchall()
    keys = [
        "rank",
        "stock_code",
        "stock_name",
        "sector_name",
        "selection_close",
        "market_state",
        "data_status",
        "closed_up_limit",
        "source_version",
        "vendor_version",
        "run_id",
    ]
    return [dict(zip(keys, row)) for row in rows]


def _enrich_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    as_of_date: str,
    rows: list[dict[str, object]],
    min_amount: float,
) -> list[dict[str, object]]:
    codes = [str(row["stock_code"]) for row in rows if row.get("stock_code")]
    daily_by_code = _load_daily_rows(conn, tables=tables, as_of_date=as_of_date, codes=codes)
    limit_by_code = _load_limit_rows(conn, tables=tables, as_of_date=as_of_date, codes=codes)
    enriched: list[dict[str, object]] = []
    for row in rows:
        stock_code = str(row.get("stock_code") or "")
        daily = daily_by_code.get(stock_code, {})
        limit = limit_by_code.get(stock_code, {})
        close_value = _optional_float(daily.get("close_value"))
        highlimit = _optional_float(daily.get("highlimit"))
        lowlimit = _optional_float(daily.get("lowlimit"))
        amount = _optional_float(daily.get("amount"))
        trade_status = str(daily.get("tradestatus") or "").strip()
        is_limit_up = _is_limit_up(
            closed_up_limit=row.get("closed_up_limit"),
            limit_flag=limit.get("issurgedlimit"),
            close_value=close_value,
            highlimit=highlimit,
        )
        is_limit_down = _is_limit_down(
            limit_flag=limit.get("isdeclinelimit"),
            close_value=close_value,
            lowlimit=lowlimit,
        )
        is_suspended = _is_suspended(trade_status)
        risk_flags = _row_risk_flags(
            has_daily=bool(daily),
            amount=amount,
            min_amount=min_amount,
            is_limit_up=is_limit_up,
            is_limit_down=is_limit_down,
            is_suspended=is_suspended,
        )
        enriched.append(
            {
                **row,
                "trade_status": trade_status or None,
                "close_value": close_value,
                "amount": amount,
                "turn": _optional_float(daily.get("turn")),
                "pctchange": _optional_float(daily.get("pctchange")),
                "highlimit": highlimit,
                "lowlimit": lowlimit,
                "hlimitedays": _optional_int(limit.get("hlimitedays")),
                "llimitedays": _optional_int(limit.get("llimitedays")),
                "is_limit_up": is_limit_up,
                "is_limit_down": is_limit_down,
                "is_suspended": is_suspended,
                "risk_flags": risk_flags,
                "row_action": "blocked" if _has_blocking_row_flag(risk_flags) else "review",
            }
        )
    return enriched


def _load_daily_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    as_of_date: str,
    codes: list[str],
) -> dict[str, dict[str, object]]:
    if TABLE_DAILY not in tables or not codes:
        return {}
    placeholders = ",".join("?" for _ in codes)
    rows = conn.execute(
        f"""
        select stock_code, close_value, amount, turn, tradestatus, highlimit, lowlimit, pctchange, volume
        from {TABLE_DAILY}
        where trade_date = ?
          and stock_code in ({placeholders})
        """,
        [as_of_date, *codes],
    ).fetchall()
    keys = [
        "stock_code",
        "close_value",
        "amount",
        "turn",
        "tradestatus",
        "highlimit",
        "lowlimit",
        "pctchange",
        "volume",
    ]
    return {str(row[0]): dict(zip(keys, row)) for row in rows}


def _load_limit_rows(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    as_of_date: str,
    codes: list[str],
) -> dict[str, dict[str, object]]:
    if TABLE_LIMIT not in tables or not codes:
        return {}
    placeholders = ",".join("?" for _ in codes)
    rows = conn.execute(
        f"""
        select stock_code, issurgedlimit, isdeclinelimit, hlimitedays, llimitedays
        from {TABLE_LIMIT}
        where as_of_date = ?
          and stock_code in ({placeholders})
        qualify row_number() over (
          partition by stock_code
          order by case when field_key = 'daily_limit_flags' then 0 else 1 end
        ) = 1
        """,
        [as_of_date, *codes],
    ).fetchall()
    keys = ["stock_code", "issurgedlimit", "isdeclinelimit", "hlimitedays", "llimitedays"]
    return {str(row[0]): dict(zip(keys, row)) for row in rows}


def _freshness_checks(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    as_of_date: str,
    today: str | None,
    stale_calendar_days: int,
) -> dict[str, object]:
    table_specs = {
        TABLE_DAILY: "trade_date",
        TABLE_FACTOR: "as_of_date",
        TABLE_HIST: "snapshot_as_of_date",
        TABLE_MACRO: "trade_date",
        TABLE_MARKET: "trade_date",
    }
    checks: dict[str, dict[str, object]] = {}
    warnings: list[str] = []
    blockers: list[str] = []
    for table_name, date_column in table_specs.items():
        if table_name not in tables:
            status = "missing" if table_name in {TABLE_DAILY, TABLE_FACTOR, TABLE_HIST} else "not_available"
            checks[table_name] = {"status": status, "max_date": None, "row_count": 0}
            if status == "missing":
                blockers.append(f"{table_name} missing")
            continue
        max_date, row_count = conn.execute(
            f"select max({date_column}), count(*) from {table_name}"
        ).fetchone()
        max_text = str(max_date or "").strip()[:10] or None
        status = "ok"
        if table_name in {TABLE_DAILY, TABLE_FACTOR}:
            if not max_text or max_text < as_of_date:
                status = "stale_input"
                blockers.append(f"{table_name} max date {max_text} before {as_of_date}")
            elif max_text > as_of_date:
                status = "selection_stale"
                warnings.append(f"{table_name} has fresher data {max_text} than selection {as_of_date}")
        checks[table_name] = {
            "status": status,
            "max_date": max_text,
            "row_count": int(row_count or 0),
        }

    today_text = _normalize_date(today) if today else date.today().isoformat()
    calendar_gap = _calendar_gap_days(today_text, as_of_date)
    calendar_status = "ok"
    if calendar_gap is not None and calendar_gap > stale_calendar_days:
        calendar_status = "stale_calendar"
        warnings.append(f"selection date is {calendar_gap} calendar days before {today_text}")
    checks["calendar"] = {
        "status": calendar_status,
        "today": today_text,
        "calendar_gap_days": calendar_gap,
        "stale_calendar_days": stale_calendar_days,
    }
    overall = "blocked" if blockers else ("warning" if warnings else "ok")
    return {"status": overall, "checks": checks, "warnings": warnings, "blockers": blockers}


def _sector_distribution(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    counts: dict[str, int] = {}
    for row in rows:
        sector = str(row.get("sector_name") or "unknown")
        counts[sector] = counts.get(sector, 0) + 1
    total = len(rows)
    return [
        {"sector_name": sector, "count": count, "weight": round(count / total, 6) if total else None}
        for sector, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _portfolio_flags(rows: list[dict[str, object]], *, max_sector_weight: float) -> list[dict[str, object]]:
    flags: list[dict[str, object]] = []
    for sector in _sector_distribution(rows):
        weight = sector.get("weight")
        if isinstance(weight, float) and weight > max_sector_weight:
            flags.append(
                {
                    "kind": "sector_concentration",
                    "severity": "review",
                    "sector_name": sector["sector_name"],
                    "weight": weight,
                    "threshold": max_sector_weight,
                }
            )
    blocked_rows = [
        row
        for row in rows
        if any(str(flag.get("severity") or "") == "block" for flag in row.get("risk_flags", []))
    ]
    if blocked_rows:
        flags.append(
            {
                "kind": "blocked_rows_present",
                "severity": "block",
                "count": len(blocked_rows),
            }
        )
    return flags


def _execution_decision(
    *,
    freshness: dict[str, object],
    rows: list[dict[str, object]],
    portfolio_flags: list[dict[str, object]],
    market_states: list[str],
    data_statuses: list[str],
) -> dict[str, object]:
    reasons: list[str] = []
    if freshness.get("status") == "blocked":
        reasons.extend(str(reason) for reason in freshness.get("blockers", []))
    if any(str(flag.get("severity") or "") == "block" for flag in portfolio_flags):
        reasons.append("blocked row-level checks present")
    if any(row.get("row_action") == "blocked" for row in rows):
        reasons.append("one or more top candidates are blocked")
    if reasons:
        return {"action": "blocked", "reasons": reasons}

    if any(str(flag.get("severity") or "") == "review" for flag in portfolio_flags):
        reasons.append("portfolio review checks present")
    if any(row.get("risk_flags") for row in rows):
        reasons.append("row-level review checks present")
    if "OVERHEAT" in market_states:
        reasons.append("market_state OVERHEAT; use review-only output")
    if any(str(status or "").lower() == "pending" for status in data_statuses):
        reasons.append("forward return windows are pending")
    if freshness.get("status") == "warning":
        reasons.extend(str(reason) for reason in freshness.get("warnings", []))
    if reasons:
        return {"action": "review_only", "reasons": reasons}
    return {"action": "ready_for_review", "reasons": ["pretrade checks passed for review export"]}


def _write_outputs(
    *,
    output_dir: Path,
    as_of_date: str,
    rows: list[dict[str, object]],
    payload: dict[str, object],
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    base = f"livermore_pretrade_{as_of_date}"
    csv_path = output_dir / f"{base}.csv"
    json_path = output_dir / f"{base}.json"
    md_path = output_dir / f"{base}.md"
    csv_fields = [
        "rank",
        "stock_code",
        "stock_name",
        "sector_name",
        "selection_close",
        "market_state",
        "data_status",
        "trade_status",
        "amount",
        "turn",
        "is_limit_up",
        "is_limit_down",
        "is_suspended",
        "row_action",
        "risk_flags",
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields)
        writer.writeheader()
        for row in rows:
            record = {field: row.get(field) for field in csv_fields}
            record["risk_flags"] = ";".join(str(flag["kind"]) for flag in row.get("risk_flags", []))
            writer.writerow(record)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown_summary(payload), encoding="utf-8")
    return {"csv": str(csv_path), "json": str(json_path), "summary": str(md_path)}


def _markdown_summary(payload: dict[str, object]) -> str:
    lines = [
        f"# Livermore pretrade check - {payload['as_of_date']}",
        "",
        f"- Signal kind: {payload['signal_kind']}",
        f"- Candidate count: {payload['candidate_count']}",
        f"- Exported top N: {payload['top_n']}",
        f"- Market states: {', '.join(payload['market_states'])}",
        f"- Data statuses: {', '.join(payload['data_statuses'])}",
        f"- Decision: {payload['decision']['action']}",
        "",
        "## Decision Reasons",
    ]
    for reason in payload["decision"].get("reasons", []):
        lines.append(f"- {reason}")
    lines.extend(["", "## Top Candidates", "| Rank | Code | Name | Sector | Action | Flags |", "|---:|---|---|---|---|---|"])
    for row in payload["rows"]:
        flags = ", ".join(str(flag["kind"]) for flag in row.get("risk_flags", []))
        lines.append(
            f"| {row.get('rank')} | {row.get('stock_code')} | {row.get('stock_name')} | "
            f"{row.get('sector_name') or ''} | {row.get('row_action')} | {flags} |"
        )
    lines.append("")
    return "\n".join(lines)


def _row_risk_flags(
    *,
    has_daily: bool,
    amount: float | None,
    min_amount: float,
    is_limit_up: bool,
    is_limit_down: bool,
    is_suspended: bool,
) -> list[dict[str, object]]:
    flags: list[dict[str, object]] = []
    if not has_daily:
        flags.append({"kind": "missing_daily_observation", "severity": "block"})
    if is_suspended:
        flags.append({"kind": "suspended", "severity": "block"})
    if is_limit_down:
        flags.append({"kind": "limit_down", "severity": "block"})
    if amount is None:
        flags.append({"kind": "missing_amount", "severity": "block"})
    elif amount <= 0:
        flags.append({"kind": "non_positive_amount", "severity": "block", "amount": amount})
    elif min_amount > 0 and amount < min_amount:
        flags.append(
            {
                "kind": "low_liquidity",
                "severity": "review",
                "amount": amount,
                "threshold": min_amount,
            }
        )
    if is_limit_up:
        flags.append({"kind": "limit_up", "severity": "review"})
    return flags


def _has_blocking_row_flag(flags: list[dict[str, object]]) -> bool:
    return any(str(flag.get("severity") or "") == "block" for flag in flags)


def _is_limit_up(
    *,
    closed_up_limit: object,
    limit_flag: object,
    close_value: float | None,
    highlimit: float | None,
) -> bool:
    if _truthy_flag(closed_up_limit) or _truthy_flag(limit_flag):
        return True
    return bool(close_value is not None and highlimit is not None and close_value >= highlimit * 0.999)


def _is_limit_down(
    *,
    limit_flag: object,
    close_value: float | None,
    lowlimit: float | None,
) -> bool:
    if _truthy_flag(limit_flag):
        return True
    return bool(close_value is not None and lowlimit is not None and close_value <= lowlimit * 1.001)


def _truthy_flag(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _FALSE_FLAGS:
        return False
    return text in _TRUE_FLAGS


def _is_suspended(trade_status: str) -> bool:
    text = str(trade_status or "").strip().lower()
    if not text or text in _NORMAL_TRADE_STATUSES:
        return False
    return "\u505c" in text or "suspend" in text or "halt" in text or text == "0"


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _distinct_values(rows: list[dict[str, object]], key: str) -> list[str]:
    return sorted({str(row.get(key) or "unknown") for row in rows})


def _normalize_date(value: str | None) -> str:
    text = str(value or "").strip()[:10]
    if not text:
        raise ValueError("date value cannot be blank.")
    date.fromisoformat(text)
    return text


def _calendar_gap_days(today_text: str, as_of_text: str) -> int | None:
    try:
        return (date.fromisoformat(today_text) - date.fromisoformat(as_of_text)).days
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Livermore pretrade review checks.")
    parser.add_argument("--duckdb-path", default="data/moss.duckdb")
    parser.add_argument("--as-of-date")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    parser.add_argument("--min-amount", type=float, default=DEFAULT_MIN_AMOUNT)
    parser.add_argument("--max-sector-weight", type=float, default=DEFAULT_MAX_SECTOR_WEIGHT)
    parser.add_argument("--stale-calendar-days", type=int, default=DEFAULT_STALE_CALENDAR_DAYS)
    parser.add_argument("--rerun-selection", action="store_true")
    parser.add_argument("--stock-candidate-policy")
    parser.add_argument("--today")
    args = parser.parse_args()
    try:
        result = export_livermore_pretrade_check(
            duckdb_path=args.duckdb_path,
            as_of_date=args.as_of_date,
            output_dir=args.output_dir,
            top_n=args.top_n,
            min_amount=args.min_amount,
            max_sector_weight=args.max_sector_weight,
            stale_calendar_days=args.stale_calendar_days,
            rerun_selection=args.rerun_selection,
            stock_candidate_policy=args.stock_candidate_policy,
            today=args.today,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return 1 if result.get("decision", {}).get("action") == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
