from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import date
from pathlib import Path
from typing import Callable, Literal

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb  # noqa: E402


DEFAULT_OUTPUT_DIR = "test_output/livermore_stock_selection"
DEFAULT_SAMPLE_STOCK_CODE = "600582.SH"
REQUIRED_MACRO_SERIES = ("CA.CSI300", "CA.CSI300_PCT_CHG", "CA.CSI300_PE")


def run_livermore_daily_pretrade_refresh(
    *,
    duckdb_path: str | Path,
    target_date: str | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    top_n: int = 10,
    lookback_days: int = 90,
    stock_candidate_policy: str | None = None,
    sample_stock_code: str = DEFAULT_SAMPLE_STOCK_CODE,
    dry_run: bool = False,
    skip_upstream_probe: bool = False,
    theme_overlay_mode: Literal["off", "dry_run", "archive"] = "off",
) -> dict[str, object]:
    if theme_overlay_mode not in {"off", "dry_run", "archive"}:
        raise ValueError("theme_overlay_mode must be one of: off, dry_run, archive")
    resolved_path = _resolve_duckdb_path(duckdb_path)
    resolved_date = _normalize_date(target_date or date.today().isoformat())
    initial = inspect_livermore_daily_refresh_state(
        duckdb_path=resolved_path,
        target_date=resolved_date,
    )

    if dry_run:
        would_run_steps = _missing_step_names(initial)
        if theme_overlay_mode != "off":
            choice_step_count = sum(
                step
                in {
                    "materialize_choice_stock_inputs",
                    "materialize_choice_stock_factor_snapshot",
                }
                for step in would_run_steps
            )
            would_run_steps.insert(choice_step_count, "refresh_choice_stock_theme_overlay")
        return {
            "status": "dry_run",
            "duckdb_path": str(resolved_path),
            "target_date": resolved_date,
            "theme_overlay_mode": theme_overlay_mode,
            "local_state": initial,
            "would_run_steps": [
                *would_run_steps,
                "mature_livermore_candidate_outcomes",
            ],
        }

    steps: list[dict[str, object]] = []
    if not initial["ready"] and not skip_upstream_probe:
        probe = probe_target_market_data_availability(
            target_date=resolved_date,
            sample_stock_code=sample_stock_code,
        )
        steps.append({"name": "upstream_probe", "result": probe})
        if probe["status"] != "ready":
            return {
                "status": "not_ready",
                "duckdb_path": str(resolved_path),
                "target_date": resolved_date,
                "reason": "target_market_data_not_landed",
                "local_state": initial,
                "steps": steps,
            }

    state = initial
    if not state["checks"]["choice_stock_inputs"]["ready"]:
        from backend.app.tasks.choice_stock_materialize import materialize_choice_stock_inputs

        payload = materialize_choice_stock_inputs(
            as_of_date=resolved_date,
            duckdb_path=str(resolved_path),
        )
        steps.append({"name": "choice_stock_inputs", "result": payload})
        state = inspect_livermore_daily_refresh_state(duckdb_path=resolved_path, target_date=resolved_date)

    if not state["checks"]["factor_snapshot"]["ready"]:
        from backend.app.tasks.choice_stock_materialize import materialize_choice_stock_factor_snapshot

        payload = materialize_choice_stock_factor_snapshot(
            as_of_date=resolved_date,
            duckdb_path=str(resolved_path),
        )
        steps.append({"name": "factor_snapshot", "result": payload})
        state = inspect_livermore_daily_refresh_state(duckdb_path=resolved_path, target_date=resolved_date)

    theme_overlay_result: dict[str, object] | None = None
    theme_overlay_failed = False
    if theme_overlay_mode != "off":
        try:
            from backend.app.governance.settings import get_settings
            from backend.app.tasks.choice_stock_observation_manifest import (
                resolve_latest_committed_choice_stock_observation,
            )
            from backend.app.tasks.choice_stock_theme_overlay_refresh import (
                refresh_choice_stock_theme_overlay,
            )

            observation = resolve_latest_committed_choice_stock_observation(
                duckdb_path=resolved_path,
                expected_report_date=resolved_date,
            )
            parent_run_id = observation.materialization_run_id
            digest = hashlib.sha256(f"{parent_run_id}|{resolved_date}".encode()).hexdigest()[:16]
            settings = get_settings()
            theme_overlay_result = refresh_choice_stock_theme_overlay(
                mode=theme_overlay_mode,
                duckdb_path=str(resolved_path),
                governance_dir=str(settings.governance_path),
                archive_root=str(settings.local_archive_path),
                expected_report_date=resolved_date,
                run_id=f"{parent_run_id}:theme-overlay",
                source_version=f"sv_choice_stock_theme_overlay_{digest}",
                vendor_version="vv_tushare_ths_current_overlay_v1",
            )
        except Exception as exc:
            theme_overlay_result = {
                "mode": theme_overlay_mode,
                "status": (
                    "archive_failed"
                    if theme_overlay_mode == "archive"
                    else "dry_run_failed"
                ),
                "overlay_status": (
                    "archive_failed"
                    if theme_overlay_mode == "archive"
                    else "dry_run_failed"
                ),
                "member_count": 0,
                "message": _summarize_error(exc),
            }
        theme_overlay_failed = str(theme_overlay_result.get("status") or "") not in {
            "completed",
            "dry_run",
        }
        steps.append({"name": "theme_overlay", "result": theme_overlay_result})

    if not state["checks"]["csi300_macro"]["ready"]:
        from backend.app.tasks.choice_macro import refresh_public_cross_asset_headlines

        payload = refresh_public_cross_asset_headlines(
            duckdb_path=str(resolved_path),
            lookback_days=lookback_days,
            report_date=resolved_date,
        )
        steps.append({"name": "public_cross_asset", "result": payload})
        state = inspect_livermore_daily_refresh_state(duckdb_path=resolved_path, target_date=resolved_date)
        if not state["checks"]["csi300_macro"]["ready"]:
            return {
                "status": "not_ready",
                "duckdb_path": str(resolved_path),
                "target_date": resolved_date,
                "reason": "csi300_macro_not_landed_after_refresh",
                "local_state": state,
                "steps": steps,
            }

    if not state["checks"]["gate_supplement"]["ready"]:
        from scripts.backfill_livermore_gate_supplement import backfill_livermore_gate_supplement

        payload = backfill_livermore_gate_supplement(
            duckdb_path=resolved_path,
            as_of_date=date.fromisoformat(resolved_date),
            lookback_days=lookback_days,
        )
        steps.append({"name": "gate_supplement", "result": payload})
        state = inspect_livermore_daily_refresh_state(duckdb_path=resolved_path, target_date=resolved_date)
        if str(payload.get("status") or "") != "completed" or not state["checks"][
            "gate_supplement"
        ]["ready"]:
            return {
                "status": "not_ready",
                "duckdb_path": str(resolved_path),
                "target_date": resolved_date,
                "reason": "gate_supplement_not_landed_after_refresh",
                "local_state": state,
                "steps": steps,
            }

    if not state["checks"]["position_snapshot"]["ready"]:
        from scripts.sync_livermore_position_snapshot import sync_livermore_position_snapshot

        payload = sync_livermore_position_snapshot(
            duckdb_path=resolved_path,
            target_as_of=resolved_date,
        )
        steps.append({"name": "position_snapshot", "result": payload})
        state = inspect_livermore_daily_refresh_state(duckdb_path=resolved_path, target_date=resolved_date)

    from backend.app.tasks.livermore_candidate_history_materialize import materialize_livermore_candidate_history

    candidate_payload = materialize_livermore_candidate_history(
        str(resolved_path),
        as_of_date=resolved_date,
        stock_candidate_policy=stock_candidate_policy,
    )
    steps.append({"name": "candidate_history", "result": candidate_payload})
    state = inspect_livermore_daily_refresh_state(duckdb_path=resolved_path, target_date=resolved_date)
    if not state["checks"]["candidate_history"]["ready"]:
        return {
            "status": "partial",
            "duckdb_path": str(resolved_path),
            "target_date": resolved_date,
            "reason": "candidate_history_not_landed_after_refresh",
            "local_state": state,
            "steps": steps,
        }

    try:
        from backend.app.tasks.livermore_candidate_outcome_maturity import (
            mature_livermore_candidate_outcomes,
        )

        maturity_payload = mature_livermore_candidate_outcomes(
            resolved_path,
            evaluation_as_of_date=resolved_date,
        )
        steps.append({"name": "candidate_outcome_maturity", "result": maturity_payload})
    except Exception as exc:
        steps.append(
            {
                "name": "candidate_outcome_maturity",
                "result": {
                    "status": "failed",
                    "evaluation_as_of_date": resolved_date,
                    "error": _summarize_error(exc),
                },
            }
        )
        return {
            "status": "partial",
            "duckdb_path": str(resolved_path),
            "target_date": resolved_date,
            "reason": "candidate_outcome_maturity_failed",
            "local_state": state,
            "steps": steps,
        }
    if maturity_payload.get("status") != "completed":
        return {
            "status": "partial",
            "duckdb_path": str(resolved_path),
            "target_date": resolved_date,
            "reason": "candidate_outcome_maturity_not_completed",
            "local_state": state,
            "steps": steps,
        }

    pre_export_state = inspect_livermore_daily_refresh_state(
        duckdb_path=resolved_path,
        target_date=resolved_date,
    )
    if not pre_export_state["ready"]:
        return {
            "status": "partial",
            "duckdb_path": str(resolved_path),
            "target_date": resolved_date,
            "reason": "refresh_state_incomplete_before_export",
            "local_state": pre_export_state,
            "steps": steps,
        }

    from scripts.export_livermore_pretrade_check import export_livermore_pretrade_check

    pretrade_payload = export_livermore_pretrade_check(
        duckdb_path=resolved_path,
        as_of_date=resolved_date,
        output_dir=output_dir,
        top_n=top_n,
        today=resolved_date,
    )
    steps.append({"name": "pretrade_export", "result": _compact_pretrade_result(pretrade_payload)})
    final_state = inspect_livermore_daily_refresh_state(duckdb_path=resolved_path, target_date=resolved_date)
    result = {
        "status": "partial" if theme_overlay_failed else "completed",
        "duckdb_path": str(resolved_path),
        "target_date": resolved_date,
        "theme_overlay_mode": theme_overlay_mode,
        "local_state": final_state,
        "steps": steps,
        "pretrade_output_paths": pretrade_payload.get("output_paths"),
        "pretrade_decision": pretrade_payload.get("decision"),
    }
    if theme_overlay_result is not None:
        result["theme_overlay"] = theme_overlay_result
    if theme_overlay_failed:
        result["reason"] = "theme_overlay_failed"
    return result


def monitor_livermore_daily_pretrade_refresh(
    *,
    duckdb_path: str | Path,
    target_date: str | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    top_n: int = 10,
    lookback_days: int = 90,
    stock_candidate_policy: str | None = None,
    sample_stock_code: str = DEFAULT_SAMPLE_STOCK_CODE,
    dry_run: bool = False,
    skip_upstream_probe: bool = False,
    theme_overlay_mode: Literal["off", "dry_run", "archive"] = "off",
    max_attempts: int = 12,
    poll_interval_seconds: float = 600,
    sleep_func: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    attempts: list[dict[str, object]] = []
    attempt_limit = max(1, int(max_attempts))
    interval = max(0.0, float(poll_interval_seconds))
    last_result: dict[str, object] | None = None
    for attempt in range(1, attempt_limit + 1):
        result = run_livermore_daily_pretrade_refresh(
            duckdb_path=duckdb_path,
            target_date=target_date,
            output_dir=output_dir,
            top_n=top_n,
            lookback_days=lookback_days,
            stock_candidate_policy=stock_candidate_policy,
            sample_stock_code=sample_stock_code,
            dry_run=dry_run,
            skip_upstream_probe=skip_upstream_probe,
            theme_overlay_mode=theme_overlay_mode,
        )
        last_result = result
        attempts.append(_compact_monitor_attempt(attempt, result))
        if result.get("status") != "not_ready":
            monitored = dict(result)
            monitored["attempt_count"] = attempt
            monitored["attempts"] = attempts
            return monitored
        if attempt < attempt_limit:
            sleep_func(interval)
    return {
        "status": "not_ready",
        "reason": "max_attempts_exhausted",
        "attempt_count": attempt_limit,
        "attempts": attempts,
        "last_result": last_result,
    }


def inspect_livermore_daily_refresh_state(
    *,
    duckdb_path: str | Path,
    target_date: str,
) -> dict[str, object]:
    resolved_path = _resolve_duckdb_path(duckdb_path)
    checks = {
        "choice_stock_inputs": {"ready": False, "row_count": 0},
        "factor_snapshot": {"ready": False, "row_count": 0},
        "csi300_macro": {"ready": False, "series": {}},
        "gate_supplement": {"ready": False, "row_count": 0},
        "position_snapshot": {"ready": False, "row_count": 0},
        "candidate_history": {"ready": False, "row_count": 0},
    }
    conn = duckdb.connect(str(resolved_path), read_only=True)
    try:
        tables = {str(row[0]) for row in conn.execute("show tables").fetchall()}
        checks["choice_stock_inputs"] = _choice_stock_input_check(conn, tables=tables, target_date=target_date)
        checks["factor_snapshot"] = _date_count_check(
            conn,
            tables=tables,
            table_name="choice_stock_factor_snapshot",
            date_column="as_of_date",
            target_date=target_date,
        )
        checks["csi300_macro"] = _macro_series_check(conn, tables=tables, target_date=target_date)
        checks["gate_supplement"] = _gate_supplement_check(
            conn,
            tables=tables,
            target_date=target_date,
        )
        checks["position_snapshot"] = _position_snapshot_check(conn, tables=tables, target_date=target_date)
        checks["candidate_history"] = _candidate_history_check(conn, tables=tables, target_date=target_date)
    finally:
        conn.close()
    missing = [name for name, check in checks.items() if not bool(check["ready"])]
    return {
        "target_date": target_date,
        "ready": not missing,
        "missing": missing,
        "checks": checks,
    }


def probe_target_market_data_availability(
    *,
    target_date: str,
    sample_stock_code: str = DEFAULT_SAMPLE_STOCK_CODE,
) -> dict[str, object]:
    compact = target_date.replace("-", "")
    try:
        from backend.app.governance.settings import get_settings
        from backend.app.repositories.tushare_adapter import (
            import_tushare_pro,
            resolve_tushare_token_with_settings_fallback,
        )

        token = resolve_tushare_token_with_settings_fallback(get_settings())
        if not token:
            return {"status": "not_ready", "reason": "missing_tushare_token"}
        ts = import_tushare_pro()
        pro = ts.pro_api(token)
        calendar = _records_from_frame(
            pro.trade_cal(exchange="SSE", start_date=compact, end_date=compact)
        )
        is_open = any(int(record.get("is_open") or 0) == 1 for record in calendar)
        if not is_open:
            return {"status": "not_ready", "reason": "target_date_not_open", "calendar": calendar}
        csi300_rows = _records_from_frame(
            pro.index_daily(ts_code="000300.SH", start_date=compact, end_date=compact)
        )
        if not csi300_rows:
            return {"status": "not_ready", "reason": "missing_csi300_daily", "calendar": calendar}
        stock_rows = _records_from_frame(
            pro.daily(ts_code=sample_stock_code, start_date=compact, end_date=compact)
        )
        if not stock_rows:
            return {
                "status": "not_ready",
                "reason": "missing_stock_daily_sample",
                "calendar": calendar,
                "sample_stock_code": sample_stock_code,
            }
        return {
            "status": "ready",
            "target_date": target_date,
            "calendar": calendar,
            "csi300_row_count": len(csi300_rows),
            "sample_stock_code": sample_stock_code,
            "sample_stock_row_count": len(stock_rows),
        }
    except Exception as exc:
        return {
            "status": "not_ready",
            "reason": "upstream_probe_failed",
            "error": _summarize_error(exc),
        }


def _choice_stock_input_check(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    target_date: str,
) -> dict[str, object]:
    table_specs = {
        "choice_stock_universe": "as_of_date",
        "choice_stock_sector_membership": "as_of_date",
        "choice_stock_daily_observation": "trade_date",
        "choice_stock_limit_quality": "as_of_date",
    }
    counts = {
        table_name: _count_rows_on_date(conn, tables, table_name, date_column, target_date)
        for table_name, date_column in table_specs.items()
    }
    return {
        "ready": all(count > 0 for count in counts.values()),
        "row_count": counts.get("choice_stock_daily_observation", 0),
        "counts": counts,
    }


def _date_count_check(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    table_name: str,
    date_column: str,
    target_date: str,
) -> dict[str, object]:
    count = _count_rows_on_date(conn, tables, table_name, date_column, target_date)
    return {"ready": count > 0, "row_count": count}


def _gate_supplement_check(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    target_date: str,
) -> dict[str, object]:
    table_name = "fact_livermore_gate_supplement_daily"
    row_count = _count_rows_on_date(conn, tables, table_name, "trade_date", target_date)
    if row_count <= 0:
        return {"ready": False, "row_count": 0, "usable_row_count": 0}
    try:
        row = conn.execute(
            f"""
            select count(*)::integer
            from {table_name}
            where trade_date = ?
              and breadth_5d is not null
              and limit_up_quality_ok is not null
            """,
            [target_date],
        ).fetchone()
    except duckdb.Error:
        return {"ready": False, "row_count": row_count, "usable_row_count": 0}
    usable_row_count = int(row[0] or 0) if row else 0
    return {
        "ready": usable_row_count > 0,
        "row_count": row_count,
        "usable_row_count": usable_row_count,
    }


def _position_snapshot_check(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    target_date: str,
) -> dict[str, object]:
    if "livermore_position_snapshot" not in tables:
        return {"ready": True, "row_count": 0, "status": "not_materialized"}
    row = conn.execute(
        """
        select count(*)::integer
        from livermore_position_snapshot
        where as_of_date = ?
          and upper(coalesce(position_status, 'ACTIVE')) = 'ACTIVE'
        """,
        [target_date],
    ).fetchone()
    count = int(row[0] or 0) if row else 0
    return {"ready": count > 0, "row_count": count}


def _candidate_history_check(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    target_date: str,
) -> dict[str, object]:
    if "livermore_candidate_history" not in tables:
        return {"ready": False, "row_count": 0}
    row = conn.execute(
        """
        select count(*)::integer
        from livermore_candidate_history
        where snapshot_as_of_date = ?
          and signal_kind = 'factor_screen'
        """,
        [target_date],
    ).fetchone()
    count = int(row[0] or 0) if row else 0
    return {"ready": count > 0, "row_count": count}


def _macro_series_check(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
    target_date: str,
) -> dict[str, object]:
    counts: dict[str, int] = {}
    if "fact_choice_macro_daily" in tables:
        rows = conn.execute(
            """
            select series_id, count(*)::integer
            from fact_choice_macro_daily
            where trade_date = ?
              and series_id in (?, ?, ?)
            group by series_id
            """,
            [target_date, *REQUIRED_MACRO_SERIES],
        ).fetchall()
        counts = {str(series_id): int(count or 0) for series_id, count in rows}
    series = {series_id: counts.get(series_id, 0) for series_id in REQUIRED_MACRO_SERIES}
    return {"ready": all(count > 0 for count in series.values()), "series": series}


def _count_rows_on_date(
    conn: duckdb.DuckDBPyConnection,
    tables: set[str],
    table_name: str,
    date_column: str,
    target_date: str,
) -> int:
    if table_name not in tables:
        return 0
    try:
        row = conn.execute(
            f"select count(*)::integer from {table_name} where {date_column} = ?",
            [target_date],
        ).fetchone()
    except duckdb.Error:
        return 0
    return int(row[0] or 0) if row else 0


def _missing_step_names(state: dict[str, object]) -> list[str]:
    mapping = {
        "choice_stock_inputs": "materialize_choice_stock_inputs",
        "factor_snapshot": "materialize_choice_stock_factor_snapshot",
        "csi300_macro": "refresh_public_cross_asset_headlines",
        "gate_supplement": "backfill_livermore_gate_supplement",
        "position_snapshot": "sync_livermore_position_snapshot",
        "candidate_history": "materialize_livermore_candidate_history",
    }
    return [mapping[name] for name in state.get("missing", []) if name in mapping]


def _compact_pretrade_result(payload: dict[str, object]) -> dict[str, object]:
    return {
        "status": payload.get("status"),
        "as_of_date": payload.get("as_of_date"),
        "candidate_count": payload.get("candidate_count"),
        "decision": payload.get("decision"),
        "output_paths": payload.get("output_paths"),
    }


def _compact_monitor_attempt(attempt: int, payload: dict[str, object]) -> dict[str, object]:
    compact: dict[str, object] = {
        "attempt": attempt,
        "status": payload.get("status"),
    }
    for key in ("target_date", "reason", "pretrade_output_paths", "pretrade_decision"):
        if key in payload:
            compact[key] = payload.get(key)
    return compact


def _resolve_duckdb_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {path}")
    return path


def _normalize_date(value: str) -> str:
    text = str(value or "").strip()[:10]
    if not text:
        raise ValueError("target_date cannot be blank.")
    date.fromisoformat(text)
    return text


def _records_from_frame(frame: object) -> list[dict[str, object]]:
    if frame is None:
        return []
    try:
        if len(frame) == 0:  # type: ignore[arg-type]
            return []
        return list(frame.to_dict(orient="records"))  # type: ignore[attr-defined]
    except (AttributeError, TypeError):
        return []


def _summarize_error(exc: Exception) -> str:
    text = str(exc).strip()
    return text.splitlines()[0] if text else exc.__class__.__name__


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the daily Livermore pretrade refresh pipeline.")
    parser.add_argument("--duckdb-path", default="data/moss.duckdb")
    parser.add_argument("--target-date", default="", help="YYYY-MM-DD, defaults to today.")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--lookback-days", type=int, default=90)
    parser.add_argument("--stock-candidate-policy")
    parser.add_argument("--sample-stock-code", default=DEFAULT_SAMPLE_STOCK_CODE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-upstream-probe", action="store_true")
    parser.add_argument(
        "--theme-overlay-mode",
        choices=("off", "dry_run", "archive"),
        default="off",
    )
    parser.add_argument("--monitor", action="store_true", help="Retry until data lands or max attempts is reached.")
    parser.add_argument("--max-attempts", type=int, default=12)
    parser.add_argument("--poll-interval-seconds", type=float, default=600)
    args = parser.parse_args()
    try:
        options = {
            "duckdb_path": args.duckdb_path,
            "target_date": args.target_date.strip() or None,
            "output_dir": args.output_dir,
            "top_n": args.top_n,
            "lookback_days": max(7, int(args.lookback_days)),
            "stock_candidate_policy": args.stock_candidate_policy,
            "sample_stock_code": args.sample_stock_code,
            "dry_run": args.dry_run,
            "skip_upstream_probe": args.skip_upstream_probe,
            "theme_overlay_mode": args.theme_overlay_mode,
        }
        if args.monitor:
            result = monitor_livermore_daily_pretrade_refresh(
                **options,
                max_attempts=args.max_attempts,
                poll_interval_seconds=args.poll_interval_seconds,
            )
        else:
            result = run_livermore_daily_pretrade_refresh(**options)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return 0 if result.get("status") in {"completed", "dry_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
