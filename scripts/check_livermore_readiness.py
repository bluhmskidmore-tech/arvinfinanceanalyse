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

    print()
    print(
        "代码层说明: 5日广度与涨停质量在 livermore_strategy.py 仍为 Phase 1 占位 (missing)；"
        "修复需落库 + core_finance/服务层读表，而非仅刷新宏观。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
