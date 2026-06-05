#!/usr/bin/env python3
"""
只读核查：Livermore 宽基历史在 DuckDB 中的可用性与 Choice 股票目录就绪态。

与页面 /api 使用同一套设置与加载逻辑，便于对照截图中的诊断。

用法（仓库根目录）:
  python scripts/check_livermore_readiness.py
  python scripts/check_livermore_readiness.py --as-of 2026-05-03

环境变量 MOSS_* 与 config/.env、.env 由 Settings 解析；可覆盖 MOSS_DUCKDB_PATH、MOSS_CHOICE_STOCK_CATALOG_FILE。
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _parse_date(s: str) -> date:
    return date.fromisoformat(s.strip())


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass

    parser = argparse.ArgumentParser(description="只读检查 Livermore DuckDB 与 Choice stock catalog 状态。")
    parser.add_argument(
        "--as-of",
        type=str,
        default=None,
        help="可选 YYYY-MM-DD，与 API as_of_date 对齐（宽基历史取该日及以前最后可用点）。",
    )
    args = parser.parse_args()

    from backend.app.governance.settings import get_settings
    from backend.app.services.livermore_readiness_probe import probe_livermore_readiness

    settings = get_settings()
    as_of = _parse_date(args.as_of) if args.as_of else None
    report = probe_livermore_readiness(
        duckdb_path=settings.duckdb_path,
        catalog_path=settings.choice_stock_catalog_file,
        as_of_date=as_of,
    )

    print(f"duckdb_path: {report.duckdb_path}")
    if not report.duckdb_exists:
        print("  (文件不存在：无法查询宽基历史)")
    else:
        print(f"tables_used: {list(report.tables_used) or '(none)'}")
        if report.history_count == 0:
            print("broad_index_history: 无可用行 (CA.CSI300)")
        else:
            print(
                f"broad_index_history: {report.history_count} 点, "
                f"最早 {report.first_trade_date}, 最近 {report.last_trade_date}"
            )
            if report.resolved_differs_from_as_of:
                print(
                    f"  提示: 请求 as_of={report.requested_as_of}，解析到的最近交易日为 {report.last_trade_date} "
                    f"（与 LIVERMORE_REQUESTED_DATE_RESOLVED_TO_AVAILABLE 一致时属预期）。"
                )

    print(f"choice_stock_catalog_file: {report.catalog_path}")
    print(f"choice_stock_readiness: ready={report.stock_ready} status={report.stock_status}")
    print(f"  message: {report.stock_message}")
    if report.stock_missing_families:
        print(f"  missing_input_families: {', '.join(report.stock_missing_families)}")

    if report.duckdb_exists and report.last_trade_date:
        print()
        print(f"gate_supplement (fact_livermore_gate_supplement_daily): max={report.gate_supplement_max_date or '(none)'}")
        print(
            f"  landed_for_last_trade ({report.last_trade_date}): "
            f"{report.gate_supplement_landed_for_last_trade}"
        )
        if not report.gate_supplement_landed_for_last_trade:
            print(
                "  fix: python scripts/backfill_livermore_gate_supplement.py "
                f"--as-of {report.last_trade_date}"
            )
            print(
                "  or API: POST /ui/market-data/livermore/refresh-gate-supplement"
                f"?as_of_date={report.last_trade_date}"
            )

        print()
        print(f"position_snapshot (livermore_position_snapshot ACTIVE): max={report.position_active_max_date or '(none)'}")
        print(
            f"  landed_for_last_trade ({report.last_trade_date}): "
            f"{report.position_landed_for_last_trade}"
        )
        if report.risk_exit_block_reason:
            print(f"  risk_exit_block_reason: {report.risk_exit_block_reason}")
        if not report.position_landed_for_last_trade and report.position_active_max_date:
            print(
                "  fix: python scripts/sync_livermore_position_snapshot.py "
                f"--target-as-of {report.last_trade_date}"
            )
            print(
                "  or import CSV: python -m backend.app.tasks.livermore_position_snapshot_run "
                f"--as-of-date {report.last_trade_date} --csv-path <holdings.csv>"
            )
        elif not report.position_active_max_date:
            print(
                "  fix: load holdings via POST /ui/market-data/livermore/position-snapshot/manual "
                "or livermore_position_snapshot_run with a CSV."
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
