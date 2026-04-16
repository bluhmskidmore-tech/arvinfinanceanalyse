"""
V3 一键数据导入 Pipeline — 从 archive 中的 XLS 到完整的 DuckDB 物化。

使用方式：
  cd F:/MOSS-V3/backend
  python -m scripts.bootstrap_data_pipeline

执行顺序：
  1. snapshot_materialize — 解析 XLS → zqtz_bond_daily_snapshot + tyw_interbank_daily_snapshot
  2. source_preview_refresh — 生成 source preview 表（前端经营分析页依赖）
  3. bond_analytics_materialize — 计算久期/DV01/凸性 → fact_formal_bond_analytics_daily
  4. balance_analysis_materialize — 计算资产负债余额 → fact_formal_zqtz/tyw_balance_daily
  5. pnl_materialize — 物化 PnL（如果有 FI损益 XLS）
  6. product_category_pnl — 物化产品类别损益（如果有总账对账 Excel）
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# 确保 backend 在 sys.path 中
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

os.environ.setdefault("MOSS_OBJECT_STORE_MODE", "local")
os.environ.setdefault("MOSS_GOVERNANCE_BACKEND", "jsonl")


def _step(label: str):
    print(f"\n{'='*60}")
    print(f"  STEP: {label}")
    print(f"{'='*60}")


def _elapsed(start: float) -> str:
    return f"{time.time() - start:.1f}s"


def run_pipeline():
    from backend.app.governance.settings import get_settings

    settings = get_settings()
    duckdb_path = str(Path(settings.duckdb_path).resolve())
    governance_dir = str(Path(settings.governance_path).resolve())
    archive_dir = str(Path(settings.local_archive_path).resolve())

    print(f"DuckDB path:     {duckdb_path}")
    print(f"Governance dir:  {governance_dir}")
    print(f"Archive dir:     {archive_dir}")

    Path(duckdb_path).parent.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Snapshot Materialize ──────────────────────────────
    _step("1/6 Snapshot Materialize (XLS → DuckDB snapshot tables)")
    t0 = time.time()
    try:
        from backend.app.tasks.snapshot_materialize import _materialize_standard_snapshots
        result = _materialize_standard_snapshots(
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            source_families=["zqtz", "tyw"],
        )
        zqtz_rows = result.get("zqtz_rows", 0)
        tyw_rows = result.get("tyw_rows", 0)
        print(f"  ✓ zqtz_bond_daily_snapshot: {zqtz_rows} rows")
        print(f"  ✓ tyw_interbank_daily_snapshot: {tyw_rows} rows")
        print(f"  ({_elapsed(t0)})")
        if zqtz_rows == 0 and tyw_rows == 0:
            print("  ⚠ No rows materialized. Check source_manifest.jsonl and archive files.")
    except Exception as exc:
        print(f"  ✗ Failed: {exc}")
        import traceback
        traceback.print_exc()

    # ── Step 2: Source Preview Refresh ────────────────────────────
    _step("2/6 Source Preview Refresh")
    t0 = time.time()
    try:
        from backend.app.tasks.source_preview_refresh import _refresh_source_preview_cache
        result = _refresh_source_preview_cache(
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
        )
        status = result.get("status", "unknown")
        print(f"  ✓ Source preview: {status}")
        print(f"  ({_elapsed(t0)})")
    except Exception as exc:
        print(f"  ✗ Failed: {exc}")
        import traceback
        traceback.print_exc()

    # ── Step 3: Bond Analytics Materialize ────────────────────────
    _step("3/6 Bond Analytics Materialize (duration/DV01/convexity)")
    t0 = time.time()
    try:
        # 先获取可用的 report_dates
        import duckdb
        conn = duckdb.connect(duckdb_path, read_only=True)
        try:
            dates = conn.execute(
                "SELECT DISTINCT CAST(report_date AS VARCHAR) FROM zqtz_bond_daily_snapshot ORDER BY 1 DESC"
            ).fetchall()
        finally:
            conn.close()

        report_dates = [str(row[0]) for row in dates]
        if not report_dates:
            print("  ⚠ No report dates in zqtz_bond_daily_snapshot, skipping.")
        else:
            from backend.app.tasks.bond_analytics_materialize import materialize_bond_analytics_facts
            for rd in report_dates[:3]:  # 最近 3 个日期
                try:
                    result = materialize_bond_analytics_facts.fn(
                        report_date=rd,
                        duckdb_path=duckdb_path,
                        governance_dir=governance_dir,
                    )
                    status = result.get("status", "unknown") if isinstance(result, dict) else "done"
                    print(f"  ✓ {rd}: {status}")
                except Exception as exc:
                    print(f"  ✗ {rd}: {exc}")
            print(f"  ({_elapsed(t0)})")
    except Exception as exc:
        print(f"  ✗ Failed: {exc}")
        import traceback
        traceback.print_exc()

    # ── Step 4: Balance Analysis Materialize ──────────────────────
    _step("4/6 Balance Analysis Materialize (formal balance daily)")
    t0 = time.time()
    try:
        from backend.app.tasks.formal_balance_pipeline import run_formal_balance_pipeline
        result = run_formal_balance_pipeline.fn(
            duckdb_path=duckdb_path,
            governance_dir=governance_dir,
            archive_dir=archive_dir,
        )
        status = result.get("status", "unknown") if isinstance(result, dict) else "done"
        print(f"  ✓ Balance analysis: {status}")
        print(f"  ({_elapsed(t0)})")
    except ImportError:
        print("  ✗ Failed: formal_balance_pipeline task is unavailable.")
    except Exception as exc:
        print(f"  ✗ Failed: {exc}")
        import traceback
        traceback.print_exc()

    # ── Step 5: PnL Materialize ───────────────────────────────────
    _step("5/6 PnL Materialize")
    t0 = time.time()
    try:
        import duckdb
        conn = duckdb.connect(duckdb_path, read_only=True)
        try:
            dates = conn.execute(
                "SELECT DISTINCT CAST(report_date AS VARCHAR) FROM zqtz_bond_daily_snapshot ORDER BY 1 DESC"
            ).fetchall()
        finally:
            conn.close()

        report_dates = [str(row[0]) for row in dates]
        if not report_dates:
            print("  ⚠ No report dates, skipping PnL.")
        else:
            from backend.app.services.pnl_source_service import load_latest_pnl_refresh_input, resolve_pnl_data_input_root
            from backend.app.tasks.pnl_materialize import run_pnl_materialize_sync
            for rd in report_dates[:3]:
                try:
                    refresh_input = load_latest_pnl_refresh_input(
                        governance_dir=governance_dir,
                        data_root=resolve_pnl_data_input_root(),
                        report_date=rd,
                    )
                    result = run_pnl_materialize_sync(
                        report_date=refresh_input.report_date,
                        is_month_end=refresh_input.is_month_end,
                        fi_rows=refresh_input.fi_rows,
                        nonstd_rows_by_type=refresh_input.nonstd_rows_by_type,
                        duckdb_path=duckdb_path,
                        governance_dir=governance_dir,
                    )
                    status = result.get("status", "unknown") if isinstance(result, dict) else "done"
                    print(f"  ✓ {rd}: {status}")
                except Exception as exc:
                    print(f"  ✗ {rd}: {exc}")
            print(f"  ({_elapsed(t0)})")
    except Exception as exc:
        print(f"  ✗ Failed: {exc}")
        import traceback
        traceback.print_exc()

    # ── Step 6: Product Category PnL ──────────────────────────────
    _step("6/6 Product Category PnL Materialize")
    t0 = time.time()
    try:
        source_dir = str(Path(settings.product_category_source_dir).resolve())
        if not Path(source_dir).exists():
            print(f"  ⚠ Source dir not found: {source_dir}")
            print("  ⚠ Skipping product category PnL. Place 总账对账/日均 Excel files in this directory.")
        else:
            from backend.app.tasks.product_category_pnl import materialize_product_category_pnl
            result = materialize_product_category_pnl.fn(
                duckdb_path=duckdb_path,
                governance_dir=governance_dir,
            )
            status = result.get("status", "unknown") if isinstance(result, dict) else "done"
            print(f"  ✓ Product category PnL: {status}")
            print(f"  ({_elapsed(t0)})")
    except Exception as exc:
        print(f"  ✗ Failed: {exc}")
        import traceback
        traceback.print_exc()

    # ── Summary ───────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("  PIPELINE COMPLETE")
    print(f"{'='*60}")

    # 验证 DuckDB 表
    if Path(duckdb_path).exists():
        import duckdb
        conn = duckdb.connect(duckdb_path, read_only=True)
        try:
            tables = conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' ORDER BY table_name"
            ).fetchall()
            print(f"\n  DuckDB tables ({len(tables)}):")
            for (name,) in tables:
                try:
                    count = conn.execute(f"SELECT COUNT(*) FROM \"{name}\"").fetchone()[0]
                    print(f"    {name}: {count} rows")
                except Exception:
                    print(f"    {name}: (error reading)")
        finally:
            conn.close()
    else:
        print(f"\n  ⚠ DuckDB file not created: {duckdb_path}")


if __name__ == "__main__":
    run_pipeline()
