"""按日期范围回填 stock_limit_price_daily（tushare stk_limit 数值涨跌停价）。

薄 CLI 骨架：仅调用 backend.app.tasks.stock_limit_price_ingest（任务层写路径，
含幂等 delete+insert、vendor 白名单守卫与写后 DQ），本脚本自身不直连 DuckDB 写。

默认 dry-run（只输出执行计划与现有覆盖，不调 Tushare、不写库）；传 --execute
才真实拉取写入。Tushare 网络恢复后按打印的四步顺序执行下游重建（本脚本不自动执行）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.repositories.duckdb_repo import read_only_connection  # noqa: E402
from backend.app.tasks.stock_limit_price_ingest import (  # noqa: E402
    ingest_stock_limit_prices,
)

# Fixer D 调查确定的回填后步骤顺序，已与各步骤的实际代码依赖对齐：
# 直接消费 stock_limit_price_daily 的是 portfolio_paths 价格路径与
# livermore_candidate_history_materialize 的 execution bars（execution_history
# 重建）；market_breadth 不直接消费新表（其涨停口径基于 Choice flag，stk_limit
# 仅是 opt-in 交叉核对 loader 且直连 API）；candidate_history 主表为固定
# forward-close 口径，不判跌停顺延，无需为本回填重建。仅打印指引，不自动执行。
# stdout 文案用英文：Windows 控制台（cp936）下打印中文会乱码（见
# tests/test_scripts_duckdb_guard_static.py 同类注记）。
_FOLLOW_UP_RUNBOOK = """\
== Follow-up runbook (Fixer D order; run manually, NOT auto-triggered) ==
[0/4] BEFORE any rebuild: snapshot the current baseline for later comparison.
      Whole-file backup:
        Copy-Item data/moss.duckdb backups/moss_pre_stk_limit_rebuild_$(Get-Date -Format yyyyMMdd).duckdb
      Export the execution_history baseline (metrics comparison input; read-only):
        .venv\\Scripts\\python.exe scripts/backfill_stock_limit_prices.py --export-execution-baseline backups/execution_history_baseline.parquet
[1/4] Backfill stock_limit_price_daily: this script with --execute (the step just run).
      Suggested batching: one month per invocation; verify status, dq.issues and
      empty_trade_date_count before moving to the next range.
[2/4] OPTIONAL cross-check only - market_breadth does NOT consume
      stock_limit_price_daily directly (its limit-up basis is the Choice flag;
      the stk_limit cross-check loader calls the vendor API, not this table).
      Rebuild only if you want the limit-price cross-check evidence refreshed:
      .venv\\Scripts\\python.exe -c "from backend.app.tasks.market_breadth_materialize import materialize_market_breadth_daily; import json; print(json.dumps(materialize_market_breadth_daily(duckdb_path='data/moss.duckdb', lookback_days=<backfilled-days>), ensure_ascii=False, default=str))"
[3/4] candidate_history main table: NO rebuild needed for this backfill. Its
      forward returns are fixed forward-close (no limit-down deferral); the
      limit-price consumers are the execution bars, covered by step 4.
[4/4] Rebuild execution_history (the actual downstream consumer; limit-down
      deferred exits recover on the 2026 era): entry point
      backend.app.tasks.livermore_candidate_history_materialize.backfill_livermore_candidate_execution_history.
      EXPECTATION: some 2026-era exit dates shift later, so return metrics
      (e.g. return_*_net_adj, backtest equity) will drift slightly DOWNWARD in
      a systematic way - this is the intended correction, not a regression.
      Compare rebuilt rows against the step-0 parquet baseline (exit dates and
      net returns per signal_date/stock_code) and archive the diff before
      re-running scripts/run_portfolio_backtest.py to re-baseline reports.
"""


def _export_execution_baseline(duckdb_path: str, parquet_path: str) -> int:
    """Runbook step 0: read-only parquet export of the execution_history baseline."""
    target = Path(parquet_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    escaped = str(target).replace("'", "''")
    with read_only_connection(duckdb_path) as conn:
        row_count = int(
            conn.execute("select count(*) from livermore_candidate_execution_history").fetchone()[0]
        )
        conn.execute(
            f"copy livermore_candidate_execution_history to '{escaped}' (format parquet)"
        )
    print(
        json.dumps(
            {
                "status": "baseline_exported",
                "table": "livermore_candidate_execution_history",
                "row_count": row_count,
                "parquet_path": str(target),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backfill tushare stk_limit numeric limit prices into stock_limit_price_daily.",
    )
    parser.add_argument("--db-path", "--duckdb-path", dest="duckdb_path", default="data/moss.duckdb")
    parser.add_argument("--start", "--start-date", dest="start_date", default=None, help="YYYY-MM-DD 或 YYYYMMDD")
    parser.add_argument("--end", "--end-date", dest="end_date", default=None, help="缺省时等于 --start")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="真实拉取 Tushare 并写库；缺省为 dry-run（只输出计划，不调 vendor、不写库）。",
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--retry-attempts", type=int, default=3)
    parser.add_argument("--retry-sleep-seconds", type=float, default=1.0)
    parser.add_argument(
        "--export-execution-baseline",
        default=None,
        metavar="PARQUET_PATH",
        help="只读导出 livermore_candidate_execution_history 基线到 parquet 后退出"
        "（runbook 第 0 步；不摄入、不写库）。",
    )
    args = parser.parse_args()

    if args.export_execution_baseline:
        return _export_execution_baseline(args.duckdb_path, args.export_execution_baseline)
    if not args.start_date:
        parser.error("--start is required unless --export-execution-baseline is used")

    dry_run = not args.execute
    try:
        result = ingest_stock_limit_prices(
            duckdb_path=args.duckdb_path,
            start_date=args.start_date,
            end_date=args.end_date,
            dry_run=dry_run,
            run_id=args.run_id,
            retry_attempts=args.retry_attempts,
            retry_sleep_seconds=args.retry_sleep_seconds,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    print()
    print(_FOLLOW_UP_RUNBOOK)
    if result.get("status") == "partial_completed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
