"""Static guard: freeze the inventory of bare ``duckdb.connect(`` call sites.

架构边界（backend/CLAUDE.md、backend/app/AGENTS.md）：
- API/services 对 DuckDB 必须只读；读连接应走
  ``backend.app.repositories.duckdb_repo.read_only_connection``。
- DuckDB 写入统一经 ``backend/app/tasks/``，仓储写函数受
  ``backend.app.repositories.task_write_guard.repository_task_write_scope`` 保护。

本测试对 ``scripts/``、``backend/scripts/``、``backend/app/services/`` 做静态扫描，
将裸 ``duckdb.connect(`` 的存量冻结为白名单（文件 -> 调用点数）：

- 新增文件或某文件计数上升 => 测试失败（新代码必须走上述封装）。
- 计数下降或文件消失 => 测试失败，提示同步削减白名单，保证台账始终准确。

白名单登记于 2026-08-12 全量重扫：
- scripts/            28 文件 / 41 调用点（含 dev-env.ps1 内嵌 Python 1 处）
- backend/scripts/     6 文件 / 14 调用点
- backend/app/services 19 文件 / 58 调用点（迁移属后续触碰式工作，先登记不动）

2026-08-12 首批迁移（C4）：10 个常驻只读脚本的裸 connect 已迁至
``duckdb_repo.read_only_connection``，对应条目已按棘轮规则移除。
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCAN_ROOTS = ("scripts", "backend/scripts", "backend/app/services")
_SCAN_SUFFIXES = {".py", ".ps1"}
_BARE_CONNECT = re.compile(r"duckdb\.connect\(")

# 人工写脚本标记：显式 read_only=False 的运维脚本必须在文件头部携带该标记。
_MANUAL_WRITE_MARKER = "MANUAL WRITE SCRIPT"

# 显式 read_only=False 的人工写脚本（2026-08-12 首批收口，共 3 处）。
# 均为 argparse 人工回填 CLI，裸 SQL 直写，不经 repository_task_write_scope；
# 已在各自文件头部添加 MANUAL WRITE SCRIPT 注释，仅限人工执行。
_MANUAL_WRITE_SCRIPTS = frozenset(
    {
        "scripts/backfill_adjusted_returns.py",
        "scripts/backfill_stock_adjustment_factor.py",
        "backend/scripts/backfill_cross_asset_macro_environment.py",
    }
)

# scripts/ 与 backend/scripts/ 存量白名单（文件 -> 裸 duckdb.connect( 调用点数）。
_SCRIPTS_ALLOWLIST: dict[str, int] = {
    "scripts/_run_diagnose_adb_other.py": 1,
    # MANUAL WRITE SCRIPT：read_only=False 直写 livermore 历史表（人工回填）。
    "scripts/backfill_adjusted_returns.py": 1,
    "scripts/backfill_csi300_benchmark_from_backup.py": 2,  # read_only=bool(dry_run) 写路径
    # MANUAL WRITE SCRIPT：read_only=False 直写 stock_adjustment_factor（自带备份守卫）。
    "scripts/backfill_stock_adjustment_factor.py": 2,
    "scripts/compare_formal_snapshot_adb_sources.py": 1,
    "scripts/copy_choice_stock_asof_from_duckdb.py": 1,  # read_only=bool(dry_run) 写路径
    "scripts/dev-env.ps1": 1,  # PowerShell 内嵌 Python 只读探活
    "scripts/dev_postgres_cluster.py": 1,
    "scripts/diagnose_entry_premium.py": 1,
    "scripts/diagnose_gate_state_flips.py": 1,
    "scripts/diagnose_macro_multiplier.py": 1,
    "scripts/diagnose_overheat_holdings.py": 1,
    "scripts/diff_zqtz_formal_vs_snapshot.py": 1,
    "scripts/mcp/moss_project_mcp.py": 2,
    "scripts/portfolio_home_full_closure_evidence.py": 1,
    "scripts/portfolio_home_krd_remap_review_queue.py": 1,
    "scripts/portfolio_home_matured_outstanding_queue.py": 1,
    "scripts/portfolio_home_maturity_remediation_queue.py": 1,
    "scripts/portfolio_home_risk_warning_consistency.py": 1,
    "scripts/refresh_tushare_news_backup.py": 1,
    "scripts/run_batch3_stock_strategy_research.py": 9,
    "scripts/run_decimal_precision_backfill.py": 3,
    "scripts/stock_strategy_health_diagnostic.py": 1,
    "scripts/supplement_livermore_after_close_inputs.py": 1,  # read_only=bool(dry_run) 写路径
    "scripts/validate_risk_exit_rules.py": 1,
    "scripts/verify_adb_source_coverage.py": 1,
    "scripts/verify_decimal_precision_backfill.py": 1,
    "scripts/walk_forward_threshold_scan.py": 1,
    # MANUAL WRITE SCRIPT：read_only=False 直写宏观环境表（persist_macro_environment_rows，
    # 亦被 backend/scripts/backfill_crisis_score_inputs.py 复用，均为人工执行）。
    "backend/scripts/backfill_cross_asset_macro_environment.py": 2,
    "backend/scripts/backfill_formal_balance.py": 3,
    "backend/scripts/batch_materialize_balance.py": 4,
    "backend/scripts/bootstrap_data_pipeline.py": 3,
    "backend/scripts/diagnose_adb_coverage.py": 1,
    "backend/scripts/diagnose_balance_diff.py": 1,
}

# backend/app/services/ 存量白名单：全部为 read_only=True 直连。
# 迁移到 duckdb_repo.read_only_connection 属后续"触碰式"工作：本清单只冻结存量。
_SERVICES_ALLOWLIST: dict[str, int] = {
    "backend/app/services/accounting_asset_movement_service.py": 1,
    "backend/app/services/adb_analysis_service.py": 1,
    "backend/app/services/campisi_attribution_service.py": 2,
    "backend/app/services/choice_news_service.py": 2,
    "backend/app/services/dexter_research_context_builder.py": 1,
    "backend/app/services/external_data_service.py": 2,
    "backend/app/services/livermore_candidate_history_service.py": 6,
    "backend/app/services/livermore_gate_supplement_compute_service.py": 2,
    "backend/app/services/livermore_readiness_probe.py": 2,
    "backend/app/services/livermore_sector_rank_series_service.py": 1,
    "backend/app/services/livermore_stock_detail_service.py": 1,
    "backend/app/services/macro_bond_linkage_service.py": 1,
    "backend/app/services/macro_toolkit_service.py": 10,
    "backend/app/services/macro_vendor_service.py": 8,
    "backend/app/services/market_data_livermore_service.py": 13,
    "backend/app/services/market_data_ncd_proxy_service.py": 2,
    "backend/app/services/pnl_attribution_service.py": 2,
    "backend/app/services/research_radar_service.py": 1,
    "backend/app/services/stock_kline_analysis_service.py": 1,
}

# 运行时断言消息使用英文：Windows 控制台（cp936）下 pytest 输出中文会乱码。
_GUIDANCE = (
    "Do not add bare duckdb.connect(: use backend.app.repositories.duckdb_repo."
    "read_only_connection for reads; route writes through backend/app/tasks/ guarded by "
    "repository_task_write_scope. For genuine manual ops write scripts, add a "
    "'MANUAL WRITE SCRIPT' header comment and register the file + count here with a reason."
)


def _scan_bare_connect_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for root in _SCAN_ROOTS:
        base = _REPO_ROOT / root
        assert base.is_dir(), f"scan root missing: {root}"
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in _SCAN_SUFFIXES:
                continue
            if "__pycache__" in path.parts:
                continue
            hits = len(_BARE_CONNECT.findall(path.read_text(encoding="utf-8", errors="ignore")))
            if hits:
                counts[path.relative_to(_REPO_ROOT).as_posix()] = hits
    return counts


def test_bare_duckdb_connect_inventory_is_frozen() -> None:
    actual = _scan_bare_connect_counts()
    expected = {**_SCRIPTS_ALLOWLIST, **_SERVICES_ALLOWLIST}

    new_files = sorted(set(actual) - set(expected))
    stale_entries = sorted(set(expected) - set(actual))
    increased = sorted(path for path in set(actual) & set(expected) if actual[path] > expected[path])
    decreased = sorted(path for path in set(actual) & set(expected) if actual[path] < expected[path])

    problems: list[str] = []
    if new_files:
        listing = "\n".join(f"  {path}: {actual[path]}" for path in new_files)
        problems.append(f"New files with bare duckdb.connect( (not allowlisted):\n{listing}\n{_GUIDANCE}")
    if increased:
        listing = "\n".join(f"  {path}: {expected[path]} -> {actual[path]}" for path in increased)
        problems.append(f"Bare duckdb.connect( count increased in allowlisted files:\n{listing}\n{_GUIDANCE}")
    if stale_entries:
        listing = "\n".join(f"  {path}: allowlisted {expected[path]}, actual 0" for path in stale_entries)
        problems.append(
            "Stale allowlist entries (file removed or no longer bare-connecting); "
            f"shrink the allowlist accordingly:\n{listing}"
        )
    if decreased:
        listing = "\n".join(f"  {path}: {expected[path]} -> {actual[path]}" for path in decreased)
        problems.append(
            "Bare connect count decreased (good); ratchet the allowlist down to keep it accurate:\n"
            f"{listing}"
        )

    assert not problems, "\n\n".join(problems)


def test_manual_write_scripts_declare_marker() -> None:
    for rel_path in sorted(_MANUAL_WRITE_SCRIPTS):
        assert rel_path in _SCRIPTS_ALLOWLIST, f"manual write script missing from allowlist: {rel_path}"
        path = _REPO_ROOT / rel_path
        assert path.is_file(), f"manual write script not found: {rel_path}"
        head = "\n".join(path.read_text(encoding="utf-8", errors="ignore").splitlines()[:12])
        assert _MANUAL_WRITE_MARKER in head, (
            f"{rel_path} lacks the '{_MANUAL_WRITE_MARKER}' header comment; explicit "
            "read_only=False manual scripts must declare that they bypass the task write "
            "scope and are for manual execution only."
        )
