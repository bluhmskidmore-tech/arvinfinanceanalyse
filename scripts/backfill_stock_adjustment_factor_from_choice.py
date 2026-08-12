# =============================================================================
# MANUAL WRITE SCRIPT: 绕过任务写作用域，仅限人工执行。
# 本脚本以 read_only=False 直连 DuckDB 写入 stock_adjustment_factor（写前需
# --target-backup-path 或 --governance-lock），未经 repository_task_write_scope /
# backend.app.tasks 写路径；禁止被 API/services 运行时导入执行。
# 已登记于 tests/test_scripts_duckdb_guard_static.py 白名单。
#
# 数据来源：Choice csd CLOSE（AdjustFlag=1 不复权 / AdjustFlag=2 后复权），
# rel = 后复权/不复权，经重叠段锚定到既有 tushare adj_factor 尺度后落表。
# 默认 dry-run（plan 模式，不调 Choice、不写库）；--verify-only 调 Choice 出
# 一致性报告但不写库；--execute 才真正写入。
# =============================================================================
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import duckdb  # noqa: E402

from backend.app.core_finance.adjusted_returns import (  # noqa: E402
    STOCK_ADJUSTMENT_FACTOR_TABLE,
    ensure_stock_adjustment_factor_schema,
    normalize_duckdb_path,
)
from backend.app.core_finance.choice_adjustment_factors import (  # noqa: E402
    DEFAULT_CONSISTENCY_TOLERANCE,
    STATUS_ANCHORED,
    STATUS_UNANCHORED,
    ChoiceFactorDerivation,
    derive_choice_adjustment_factors,
)

CHOICE_NATIVE_ERA_START_DATE = "2026-01-05"
_HORIZONS = ("1d", "5d", "10d", "20d")
_CSD_OPTIONS_TEMPLATE = "Period=1,AdjustFlag={adjust_flag},RowIndex=1,Ispandas=0"
SOURCE_VERSION_PREFIX = "sv_choice_adj_factor_"


def backfill_stock_adjustment_factor_from_choice(
    *,
    duckdb_path: str | Path,
    codes: list[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    verify_only: bool = False,
    execute: bool = False,
    client: object | None = None,
    target_backup_path: str | Path | None = None,
    governance_lock: bool = False,
    consistency_tolerance: float = DEFAULT_CONSISTENCY_TOLERANCE,
    anchor_overlap_days: int = 10,
    chunk_size: int = 100,
    allow_unanchored: bool = False,
    skip_outcome_maturity: bool = False,
) -> dict[str, object]:
    if verify_only and execute:
        raise ValueError("--verify-only and --execute are mutually exclusive")
    resolved_path = normalize_duckdb_path(duckdb_path)
    if not resolved_path.exists():
        raise FileNotFoundError(f"DuckDB file not found: {resolved_path}")

    plan = _load_plan(
        resolved_path,
        codes=codes,
        start_date=_normalize_date_text(start_date) or None,
        end_date=_normalize_date_text(end_date) or None,
        anchor_overlap_days=anchor_overlap_days,
    )
    base_result: dict[str, object] = {
        "duckdb_path": str(resolved_path),
        "missing_cell_count": len(plan.missing_cells),
        "code_count": len(plan.codes),
        "era_split": plan.era_split,
        "codes_without_anchor": sorted(plan.codes_without_anchor),
    }

    if not verify_only and not execute:
        return {
            "status": "dry_run",
            **base_result,
            "mode": "plan",
            "missing_cells_preview": [
                {"stock_code": code, "trade_date": trade_date}
                for code, trade_date in sorted(plan.missing_cells)[:10]
            ],
            "would_call_choice": bool(plan.missing_cells),
        }

    if not plan.missing_cells:
        return {"status": "noop", **base_result, "inserted_count": 0}

    resolved_client = client or _DefaultChoiceCsdClient()
    derivations, fetch_stats = _derive_all(
        plan,
        client=resolved_client,
        chunk_size=chunk_size,
        consistency_tolerance=consistency_tolerance,
        allow_unanchored=allow_unanchored,
    )
    verification = _verification_report(derivations, tolerance=consistency_tolerance)

    if verify_only:
        status = "verified" if not verification["failed_codes"] else "verified_with_issues"
        return {
            "status": status,
            **base_result,
            "mode": "verify_only",
            "fetch_stats": fetch_stats,
            "verification": verification,
        }

    write_safety = _write_safety_guard(
        target_backup_path=target_backup_path,
        governance_lock=governance_lock,
    )
    rows = _rows_to_write(plan, derivations)
    inserted_count, skipped_existing_count, run_id, source_version = _write_rows(
        resolved_path,
        rows=rows,
    )

    unresolved_cells = len(plan.missing_cells) - inserted_count - skipped_existing_count
    result: dict[str, object] = {
        "status": "completed" if unresolved_cells == 0 and not verification["failed_codes"] else "partial_completed",
        "factor_write_status": "completed",
        **base_result,
        "mode": "execute",
        "fetch_stats": fetch_stats,
        "verification": verification,
        "inserted_count": inserted_count,
        "skipped_existing_cell_count": skipped_existing_count,
        "unresolved_cell_count": unresolved_cells,
        "source_version": source_version,
        "run_id": run_id,
        "write_safety": write_safety,
    }
    if rows and not skip_outcome_maturity:
        from backend.app.tasks.livermore_candidate_outcome_maturity import (
            mature_livermore_candidate_outcomes,
        )

        maturity_evaluation_date = max(row["trade_date"] for row in rows)
        try:
            maturity_payload = mature_livermore_candidate_outcomes(
                resolved_path,
                evaluation_as_of_date=str(maturity_evaluation_date),
            )
        except Exception as exc:
            maturity_payload = {"status": "failed", "error": str(exc)}
        if maturity_payload.get("status") != "completed":
            result["status"] = "partial_completed"
        result["outcome_maturity"] = maturity_payload
    return result


class _Plan:
    def __init__(self) -> None:
        self.missing_cells: set[tuple[str, str]] = set()
        self.reference_factors: dict[str, dict[str, float]] = {}
        self.fetch_windows: dict[str, tuple[str, str]] = {}
        self.codes_without_anchor: set[str] = set()
        self.era_split: dict[str, int] = {}

    @property
    def codes(self) -> list[str]:
        return sorted({code for code, _ in self.missing_cells})


def _load_plan(
    resolved_path: Path,
    *,
    codes: list[str] | None,
    start_date: str | None,
    end_date: str | None,
    anchor_overlap_days: int,
) -> _Plan:
    plan = _Plan()
    conn = duckdb.connect(str(resolved_path), read_only=True)
    try:
        tables = _table_names(conn)
        needed = _collect_needed_cells(conn, tables=tables)
        explicit_codes = {code.strip().upper() for code in codes or [] if code.strip()}
        for stock_code, trade_date in needed:
            if explicit_codes and stock_code not in explicit_codes:
                continue
            if start_date and trade_date < start_date:
                continue
            if end_date and trade_date > end_date:
                continue
            plan.missing_cells.add((stock_code, trade_date))
        plan.missing_cells = _drop_cells_with_existing_factor(conn, plan.missing_cells)
        for era, count in _era_split(plan.missing_cells).items():
            plan.era_split[era] = count
        _resolve_fetch_windows(
            conn,
            plan=plan,
            anchor_overlap_days=anchor_overlap_days,
        )
    finally:
        conn.close()
    return plan


def _collect_needed_cells(
    conn: duckdb.DuckDBPyConnection,
    *,
    tables: set[str],
) -> set[tuple[str, str]]:
    """收集成熟链路仍缺复权调整的行所需的 (stock_code, trade_date) 因子键。

    - livermore_candidate_history：raw return 已成熟但 *_adj 为空的行，
      需要 signal 日与对应 forward 日因子（与 outcome maturity 的
      _required_factor_keys 口径一致）。
    - livermore_candidate_execution_history：gross 已成熟但 gross_adj 为空的行，
      需要 signal/entry/exit 日因子（与执行历史物化的取因子口径一致）。
    """
    cells: set[tuple[str, str]] = set()
    if "livermore_candidate_history" in tables:
        history_columns = _table_columns(conn, "livermore_candidate_history")
        for horizon in _HORIZONS:
            required = {
                "stock_code",
                "snapshot_as_of_date",
                f"return_{horizon}",
                f"return_{horizon}_adj",
                f"forward_trade_date_{horizon}",
            }
            if not required.issubset(history_columns):
                continue
            rows = conn.execute(
                f"""
                select upper(trim(stock_code)),
                       substr(cast(snapshot_as_of_date as varchar), 1, 10),
                       substr(cast(forward_trade_date_{horizon} as varchar), 1, 10)
                from livermore_candidate_history
                where return_{horizon} is not null
                  and return_{horizon}_adj is null
                  and stock_code is not null
                """
            ).fetchall()
            for stock_code, snapshot_date, forward_date in rows:
                if not stock_code:
                    continue
                if snapshot_date:
                    cells.add((str(stock_code), str(snapshot_date)))
                if forward_date:
                    cells.add((str(stock_code), str(forward_date)))
    if "livermore_candidate_execution_history" in tables:
        execution_columns = _table_columns(conn, "livermore_candidate_execution_history")
        for horizon in _HORIZONS:
            required = {
                "stock_code",
                "signal_date",
                "entry_date",
                f"exit_date_{horizon}",
                f"return_{horizon}_gross",
                f"return_{horizon}_gross_adj",
            }
            if not required.issubset(execution_columns):
                continue
            rows = conn.execute(
                f"""
                select upper(trim(stock_code)),
                       substr(cast(signal_date as varchar), 1, 10),
                       substr(cast(entry_date as varchar), 1, 10),
                       substr(cast(exit_date_{horizon} as varchar), 1, 10)
                from livermore_candidate_execution_history
                where return_{horizon}_gross is not null
                  and return_{horizon}_gross_adj is null
                  and stock_code is not null
                """
            ).fetchall()
            for stock_code, signal_date, entry_date, exit_date in rows:
                if not stock_code:
                    continue
                for trade_date in (signal_date, entry_date, exit_date):
                    if trade_date:
                        cells.add((str(stock_code), str(trade_date)))
    return cells


def _drop_cells_with_existing_factor(
    conn: duckdb.DuckDBPyConnection,
    cells: set[tuple[str, str]],
) -> set[tuple[str, str]]:
    if not cells:
        return set()
    conn.execute(
        "create temp table if not exists choice_adj_needed_cells (stock_code varchar, trade_date varchar)"
    )
    conn.execute("delete from choice_adj_needed_cells")
    conn.executemany("insert into choice_adj_needed_cells values (?, ?)", sorted(cells))
    rows = conn.execute(
        f"""
        select n.stock_code, n.trade_date
        from choice_adj_needed_cells n
        left join {STOCK_ADJUSTMENT_FACTOR_TABLE} f
          on upper(trim(f.stock_code)) = n.stock_code
         and substr(cast(f.trade_date as varchar), 1, 10) = n.trade_date
         and f.adj_factor is not null
        where f.stock_code is null
        """
    ).fetchall()
    return {(str(code), str(trade_date)) for code, trade_date in rows}


def _resolve_fetch_windows(
    conn: duckdb.DuckDBPyConnection,
    *,
    plan: _Plan,
    anchor_overlap_days: int,
) -> None:
    for stock_code in plan.codes:
        needed_dates = sorted(d for c, d in plan.missing_cells if c == stock_code)
        max_needed = needed_dates[-1]
        factor_rows = conn.execute(
            f"""
            select substr(cast(trade_date as varchar), 1, 10) as trade_date,
                   cast(adj_factor as double) as adj_factor
            from {STOCK_ADJUSTMENT_FACTOR_TABLE}
            where upper(trim(stock_code)) = ? and adj_factor is not null
            order by 1
            """,
            [stock_code],
        ).fetchall()
        anchors_before = [str(r[0]) for r in factor_rows if str(r[0]) <= max_needed]
        anchors_after = [str(r[0]) for r in factor_rows if str(r[0]) > max_needed]
        chosen_anchor_dates = (
            anchors_before[-anchor_overlap_days:]
            if anchors_before
            else anchors_after[:anchor_overlap_days]
        )
        if not chosen_anchor_dates:
            plan.codes_without_anchor.add(stock_code)
        window_dates = needed_dates + chosen_anchor_dates
        window_start, window_end = min(window_dates), max(window_dates)
        plan.fetch_windows[stock_code] = (window_start, window_end)
        plan.reference_factors[stock_code] = {
            str(trade_date): float(adj_factor)
            for trade_date, adj_factor in factor_rows
            if window_start <= str(trade_date) <= window_end
        }


def _era_split(cells: set[tuple[str, str]]) -> dict[str, int]:
    split = {"native_era": 0, "tushare_era": 0}
    for _, trade_date in cells:
        if trade_date >= CHOICE_NATIVE_ERA_START_DATE:
            split["native_era"] += 1
        else:
            split["tushare_era"] += 1
    return split


class _DefaultChoiceCsdClient:
    def __init__(self) -> None:
        from backend.app.repositories.choice_client import ChoiceClient

        self._client = ChoiceClient()

    def csd(self, codes: str, indicators: str, start_date: str, end_date: str, *, options: str) -> object:
        return self._client.csd(codes, indicators, start_date, end_date, options=options)


def _derive_all(
    plan: _Plan,
    *,
    client: object,
    chunk_size: int,
    consistency_tolerance: float,
    allow_unanchored: bool,
) -> tuple[dict[str, ChoiceFactorDerivation], dict[str, object]]:
    codes = plan.codes
    call_count = 0
    derivations: dict[str, ChoiceFactorDerivation] = {}
    for chunk in _chunks(codes, max(1, chunk_size)):
        window_start = min(plan.fetch_windows[code][0] for code in chunk)
        window_end = max(plan.fetch_windows[code][1] for code in chunk)
        codes_arg = ",".join(chunk)
        raw_closes = _closes_by_code(
            client,
            codes=codes_arg,
            start_date=window_start,
            end_date=window_end,
            adjust_flag=1,
        )
        hfq_closes = _closes_by_code(
            client,
            codes=codes_arg,
            start_date=window_start,
            end_date=window_end,
            adjust_flag=2,
        )
        call_count += 2
        for stock_code in chunk:
            requested = sorted(d for c, d in plan.missing_cells if c == stock_code)
            derivations[stock_code] = derive_choice_adjustment_factors(
                stock_code=stock_code,
                raw_close_by_date=raw_closes.get(stock_code, {}),
                adjusted_close_by_date=hfq_closes.get(stock_code, {}),
                reference_factors_by_date=plan.reference_factors.get(stock_code, {}),
                requested_dates=requested,
                consistency_tolerance=consistency_tolerance,
                allow_unanchored=allow_unanchored,
            )
    fetch_stats = {
        "choice_csd_call_count": call_count,
        "chunk_size": chunk_size,
        "adjust_flags": [1, 2],
    }
    return derivations, fetch_stats


def _closes_by_code(
    client: object,
    *,
    codes: str,
    start_date: str,
    end_date: str,
    adjust_flag: int,
) -> dict[str, dict[str, float | None]]:
    result = client.csd(  # type: ignore[attr-defined]
        codes,
        "CLOSE",
        start_date,
        end_date,
        options=_CSD_OPTIONS_TEMPLATE.format(adjust_flag=adjust_flag),
    )
    error_code = getattr(result, "ErrorCode", 0) or 0
    if error_code != 0:
        raise RuntimeError(
            f"Choice csd failed (AdjustFlag={adjust_flag}, ErrorCode={error_code}): "
            f"{getattr(result, 'ErrorMsg', 'unknown error')}"
        )
    dates = [_normalize_date_text(item) for item in (getattr(result, "Dates", None) or [])]
    data = getattr(result, "Data", {}) or {}
    if not isinstance(data, dict):
        raise RuntimeError(f"unexpected Choice csd payload type: {type(data).__name__}")
    closes: dict[str, dict[str, float | None]] = {}
    for code, payload in data.items():
        series = _close_series_from_payload(payload, date_count=len(dates))
        by_date: dict[str, float | None] = {}
        for trade_date, value in zip(dates, series, strict=False):
            if trade_date:
                by_date[trade_date] = _float_or_none(value)
        closes[str(code).strip().upper()] = by_date
    return closes


def _close_series_from_payload(payload: object, *, date_count: int) -> list[object]:
    """csd Ispandas=0 的 Data[code] 载荷：单指标 CLOSE 时为 [[v1, v2, ...]] 或扁平 [v1, v2, ...]。"""
    if isinstance(payload, list):
        if len(payload) == 1 and isinstance(payload[0], list):
            return list(payload[0])
        if payload and all(isinstance(item, list) for item in payload):
            raise RuntimeError("unexpected multi-indicator csd payload for single CLOSE request")
        if len(payload) == date_count:
            return list(payload)
        if date_count == 1 and len(payload) == 1:
            return list(payload)
    raise RuntimeError(f"unexpected Choice csd payload shape: {type(payload).__name__}")


def _verification_report(
    derivations: dict[str, ChoiceFactorDerivation],
    *,
    tolerance: float,
) -> dict[str, object]:
    status_counts: dict[str, int] = {}
    failed_codes: list[dict[str, object]] = []
    unanchored_codes: list[str] = []
    max_scale_deviation = 0.0
    max_return_diff = 0.0
    event_pairs = 0
    event_matched = 0
    for stock_code in sorted(derivations):
        derivation = derivations[stock_code]
        status_counts[derivation.status] = status_counts.get(derivation.status, 0) + 1
        if derivation.scale_max_rel_deviation is not None:
            max_scale_deviation = max(max_scale_deviation, derivation.scale_max_rel_deviation)
        if derivation.return_consistency_max_rel_diff is not None:
            max_return_diff = max(max_return_diff, derivation.return_consistency_max_rel_diff)
        event_pairs += derivation.overlap_event_pair_count
        event_matched += derivation.overlap_event_matched_count
        if derivation.status == STATUS_UNANCHORED:
            unanchored_codes.append(stock_code)
        if derivation.status not in (STATUS_ANCHORED, STATUS_UNANCHORED):
            failed_codes.append(
                {
                    "stock_code": stock_code,
                    "status": derivation.status,
                    "scale_max_rel_deviation": derivation.scale_max_rel_deviation,
                    "return_consistency_max_rel_diff": derivation.return_consistency_max_rel_diff,
                    "return_consistency_breach_count": derivation.return_consistency_breach_count,
                    "return_consistency_pair_count": derivation.return_consistency_pair_count,
                }
            )
    missing_vendor_cells = sorted(
        (derivation.stock_code, missing_date)
        for derivation in derivations.values()
        for missing_date in derivation.missing_requested_dates
    )
    return {
        "consistency_tolerance": tolerance,
        "status_counts": status_counts,
        "failed_codes": failed_codes,
        "unanchored_codes": unanchored_codes,
        "max_scale_rel_deviation": max_scale_deviation,
        "max_return_consistency_rel_diff": max_return_diff,
        "overlap_event_pair_count": event_pairs,
        "overlap_event_matched_count": event_matched,
        "missing_vendor_cell_count": len(missing_vendor_cells),
        "missing_vendor_cells_preview": [
            {"stock_code": code, "trade_date": trade_date}
            for code, trade_date in missing_vendor_cells[:10]
        ],
    }


def _rows_to_write(
    plan: _Plan,
    derivations: dict[str, ChoiceFactorDerivation],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for stock_code, trade_date in sorted(plan.missing_cells):
        derivation = derivations.get(stock_code)
        if derivation is None:
            continue
        factor = derivation.factors.get(trade_date)
        if factor is None or not math.isfinite(factor) or factor <= 0:
            continue
        rows.append(
            {
                "stock_code": stock_code,
                "trade_date": trade_date,
                "adj_factor": float(factor),
                "derivation_status": derivation.status,
            }
        )
    return rows


def _write_rows(
    resolved_path: Path,
    *,
    rows: list[dict[str, object]],
) -> tuple[int, int, str, str]:
    source_version = _source_version(rows)
    dates = sorted({str(row["trade_date"]) for row in rows})
    run_id = (
        "stock_adjustment_factor_choice:"
        f"{dates[0] if dates else 'na'}:{dates[-1] if dates else 'na'}:{uuid.uuid4().hex[:12]}"
    )
    inserted = 0
    skipped_existing = 0
    conn = duckdb.connect(str(resolved_path), read_only=False)
    try:
        ensure_stock_adjustment_factor_schema(conn)
        conn.execute("begin transaction")
        for row in rows:
            existing = conn.execute(
                f"""
                select 1 from {STOCK_ADJUSTMENT_FACTOR_TABLE}
                where upper(trim(stock_code)) = ?
                  and substr(cast(trade_date as varchar), 1, 10) = ?
                  and adj_factor is not null
                limit 1
                """,
                [row["stock_code"], row["trade_date"]],
            ).fetchone()
            if existing is not None:
                # 只补缺失 cell：任何既有行（含 tushare 行）一律不覆盖。
                skipped_existing += 1
                continue
            conn.execute(
                f"""
                insert into {STOCK_ADJUSTMENT_FACTOR_TABLE}
                (stock_code, trade_date, adj_factor, source_version, run_id)
                values (?, ?, ?, ?, ?)
                """,
                [row["stock_code"], row["trade_date"], row["adj_factor"], source_version, run_id],
            )
            inserted += 1
        conn.execute("commit")
    except Exception:
        conn.execute("rollback")
        raise
    finally:
        conn.close()
    return inserted, skipped_existing, run_id, source_version


def _write_safety_guard(
    *,
    target_backup_path: str | Path | None,
    governance_lock: bool,
) -> dict[str, object]:
    if governance_lock:
        return {"status": "governance_lock_acknowledged", "governance_lock": True, "target_backup_path": None}
    if target_backup_path is None:
        raise RuntimeError("stock_adjustment_factor write requires --target-backup-path or --governance-lock")
    backup = Path(target_backup_path)
    if not backup.exists():
        raise FileNotFoundError(f"target backup path does not exist: {backup}")
    return {
        "status": "target_backup_verified",
        "governance_lock": False,
        "target_backup_path": str(backup),
        "target_backup_sha256": _file_sha256(backup) if backup.is_file() else None,
    }


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_version(rows: list[dict[str, object]]) -> str:
    payload = [
        {key: row[key] for key in ("stock_code", "trade_date", "adj_factor")}
        for row in rows
    ]
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode()
    ).hexdigest()[:12]
    return f"{SOURCE_VERSION_PREFIX}{digest}"


def _chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _normalize_date_text(value: object) -> str:
    text = str(value or "").strip().replace("/", "-")
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text[:10] if len(text) >= 10 else ""


def _float_or_none(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _table_names(conn: duckdb.DuckDBPyConnection) -> set[str]:
    return {str(row[0]) for row in conn.execute("show tables").fetchall()}


def _table_columns(conn: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    return {str(row[1]).lower() for row in conn.execute(f"pragma table_info('{table_name}')").fetchall()}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill stock_adjustment_factor from Choice csd CLOSE "
            "(AdjustFlag=2 后复权 / AdjustFlag=1 不复权 推导，锚定到既有 tushare 尺度)。"
            "默认 plan 模式（不调 Choice、不写库）。"
        )
    )
    parser.add_argument("--db-path", "--duckdb-path", dest="duckdb_path", default="data/moss.duckdb")
    parser.add_argument("--codes", default="", help="Comma-separated stock codes filter; defaults to all gap codes.")
    parser.add_argument("--start", "--start-date", dest="start_date", default=None, help="Min factor trade_date (e.g. 2026-01-05 native era).")
    parser.add_argument("--end", "--end-date", dest="end_date", default=None)
    parser.add_argument("--verify-only", action="store_true", help="Call Choice and report overlap consistency; no writes.")
    parser.add_argument("--execute", action="store_true", help="Write to stock_adjustment_factor (requires backup/lock).")
    parser.add_argument("--target-backup-path", default=None, help="Existing backup artifact required before writes.")
    parser.add_argument("--governance-lock", action="store_true", help="Acknowledge external backup/governance lock for writes.")
    parser.add_argument("--consistency-tolerance", type=float, default=DEFAULT_CONSISTENCY_TOLERANCE)
    parser.add_argument("--anchor-overlap-days", type=int, default=10)
    parser.add_argument("--chunk-size", type=int, default=100)
    parser.add_argument("--allow-unanchored", action="store_true", help="Write scale=1 relative factors for codes without any existing factor row (NOT recommended).")
    parser.add_argument("--skip-outcome-maturity", action="store_true")
    args = parser.parse_args()

    codes = [item.strip() for item in args.codes.split(",") if item.strip()]
    try:
        result = backfill_stock_adjustment_factor_from_choice(
            duckdb_path=args.duckdb_path,
            codes=codes or None,
            start_date=args.start_date,
            end_date=args.end_date,
            verify_only=args.verify_only,
            execute=args.execute,
            target_backup_path=args.target_backup_path,
            governance_lock=args.governance_lock,
            consistency_tolerance=args.consistency_tolerance,
            anchor_overlap_days=args.anchor_overlap_days,
            chunk_size=args.chunk_size,
            allow_unanchored=args.allow_unanchored,
            skip_outcome_maturity=args.skip_outcome_maturity,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if result.get("status") in {"partial_completed", "verified_with_issues"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
