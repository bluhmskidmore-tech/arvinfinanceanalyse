# B5 — BLE001（blind except）存量基线清单

- 生成日期：2026-08-12
- 扫描范围：`backend/`（ruff 配置：`backend/pyproject.toml`）
- 生成命令：
  - 总量：`python -m ruff check backend --select BLE001 --statistics`
  - 明细：`python -m ruff check backend --select BLE001 --output-format concise`
- 状态：**BLE001 未启用**（不在 `[tool.ruff.lint] select` 中）。本清单仅作为后续棘轮（ratchet）治理的冻结基线：新代码不得新增 BLE001，存量按文件逐步清偿，清偿后更新本表。

## 总量

| 规则 | 数量 |
| --- | ---: |
| BLE001 blind-except（冻结基线） | **179** |
| 批次 1 清偿后全库实测余额（2026-08-12，`py -m ruff check backend --select BLE001 --statistics`，含其他并行批次同步清偿） | **147** |

## 按文件计数（降序）

| 数量 | 文件 |
| ---: | --- |
| 11 | backend/app/api/routes/kpi.py |
| 0（原 11，批次 1 已清偿：1 处窄化 duckdb.Error + 10 处 noqa） | backend/scripts/bootstrap_data_pipeline.py |
| 0（原 9，批次 1 已清偿：9 处 noqa，终态落账/重试/spool 耐久性边界） | backend/app/tasks/ledger_import.py |
| 8 | backend/app/tasks/tushare_news_ingest.py |
| 0（原 6，批次 1 已清偿：6 处 noqa，多供应商回退链补 logger.warning） | backend/app/repositories/akshare_adapter.py |
| 6 | backend/app/services/campisi_attribution_service.py |
| 6 | backend/app/tasks/choice_stock_materialize.py |
| 5 | backend/app/services/research_calendar_upstream_fetch_service.py |
| 4 | backend/app/api/routes/ledger.py |
| 4 | backend/app/api/routes/macro_toolkit.py |
| 4 | backend/app/core_finance/macro/toolkit/scripts/garch_multi_asset.py |
| 4 | backend/app/services/executive_service.py |
| 4 | backend/app/services/hermes_agent_service.py |
| 4 | backend/app/tasks/materialize.py |
| 4 | backend/app/tasks/yield_curve_materialize.py |
| 3 | backend/app/agent/tools/analysis_view_tool.py |
| 3 | backend/app/core_finance/macro/toolkit/scripts/backtest_cn.py |
| 3 | backend/app/core_finance/macro/toolkit/scripts/risk_monitor.py |
| 3 | backend/app/services/knowledge_index_service.py |
| 3 | backend/app/tasks/choice_stock_theme_overlay_refresh.py |
| 3 | backend/app/tasks/fx_mid_materialize.py |
| 3 | backend/app/tasks/home_macro_release_refresh.py |
| 2 | backend/app/core_finance/macro/toolkit/scripts/credit_bond_data.py |
| 2 | backend/app/core_finance/macro/toolkit/scripts/cta_trend_cn.py |
| 2 | backend/app/core_finance/macro/toolkit/scripts/dcc_garch_cn.py |
| 2 | backend/app/core_finance/macro/toolkit/scripts/performance_metrics_cn.py |
| 2 | backend/app/core_finance/macro/toolkit/scripts/rebalance_cn.py |
| 2 | backend/app/core_finance/macro/toolkit/scripts/regime_switch_cn.py |
| 2 | backend/app/core_finance/macro/toolkit/scripts/risk_parity_cn.py |
| 2 | backend/app/services/advanced_attribution_service.py |
| 2 | backend/app/services/agent_run_service.py |
| 2 | backend/app/services/cffex_member_rank_service.py |
| 2 | backend/app/services/macro_etf_strategy_service.py |
| 2 | backend/app/services/macro_toolkit_service.py |
| 2 | backend/app/services/tushare_news_ingest_service.py |
| 2 | backend/app/tasks/choice_macro.py |
| 2 | backend/app/tasks/livermore_monitor_append.py |
| 2 | backend/app/tasks/source_preview_refresh.py |
| 2 | backend/app/tasks/tushare_stock_disclosure.py |
| 2 | backend/scripts/backfill_formal_balance.py |
| 2 | backend/scripts/batch_materialize_balance.py |
| 1 | backend/app/api/routes/adb_analysis.py |
| 1 | backend/app/config/choice_runtime.py |
| 1 | backend/app/core_finance/macro/toolkit/scripts/alphaear_news_fetch.py |
| 1 | backend/app/core_finance/macro/toolkit/scripts/evening_report.py |
| 1 | backend/app/repositories/postgres_repo.py |
| 1 | backend/app/repositories/source_preview_repo.py |
| 1 | backend/app/repositories/stock_analysis_theme_overlay_reader.py |
| 1 | backend/app/services/analytical_bridge_service.py |
| 1 | backend/app/services/bond_dashboard_service.py |
| 1 | backend/app/services/gitnexus_service.py |
| 1 | backend/app/services/kpi_service.py |
| 1 | backend/app/services/ledger_import_run_service.py |
| 1 | backend/app/services/livermore_gate_supplement_compute_service.py |
| 1 | backend/app/services/market_data_livermore_service.py |
| 1 | backend/app/services/pnl_attribution_service.py |
| 1 | backend/app/services/product_category_pnl_service.py |
| 1 | backend/app/services/qdb_gl_input_validation_service.py |
| 1 | backend/app/services/qdb_gl_monthly_analysis_service.py |
| 1 | backend/app/services/tushare_macro_ingest_service.py |
| 1 | backend/app/tasks/bond_analytics_materialize.py |
| 1 | backend/app/tasks/ledger_classification_backfill.py |
| 1 | backend/app/tasks/macro_backfill.py |
| 1 | backend/app/tasks/market_breadth_materialize.py |
| 1 | backend/app/tasks/nbs_gdp_release_ingest.py |
| 1 | backend/app/tasks/pnl_materialize.py |
| 1 | backend/app/tasks/stock_analysis_theme_overlay_archive.py |
| 1 | backend/scripts/backfill_crisis_score_inputs.py |
| 1 | backend/scripts/diagnose_adb_coverage.py |
| 1 | backend/scripts/diagnose_balance_calibration.py |
| 1 | backend/scripts/diagnose_balance_diff.py |

合计（冻结基线）：179 处，72 个文件。批次 1 清偿 26 处（3 个文件清零）后，全库实测余额 147 处（2026-08-12，差额含其他并行批次同步清偿与代码演进）。

## 清偿记录

### 批次 1（2026-08-12）— 26 处，余额 179 → 147（实测）

| 文件 | 原计数 | 处置 |
| --- | ---: | --- |
| backend/scripts/bootstrap_data_pipeline.py | 11 | 1 处窄化为 `duckdb.Error`（汇总表行数读取，错误信息随行打印）；10 处 `noqa: BLE001`（顶层 CLI 步骤/单日期隔离，失败打印 traceback 或错误后继续，fail-visible） |
| backend/app/tasks/ledger_import.py | 9 | 9 处 `noqa: BLE001`（终态落账/重试入队/outbox spool 耐久性边界，任何异常必须走降级路径且每处已有 `logger.error` 含 error_type） |
| backend/app/repositories/akshare_adapter.py | 6 | 6 处 `noqa: BLE001`（AkShare/Choice/ChinaBond 多供应商回退链与 loader 探测循环，vendor SDK 异常面无界；错误聚合进最终 RuntimeError，5 处回退点补 `logger.warning` 使部分降级可见） |

验证：三个文件 `ruff --select BLE001` 清零；`py -m py_compile` 通过；配套测试 `test_bootstrap_data_pipeline_script.py`、`test_akshare_adapter_yield_curve.py`、`test_akshare_adapter_fx.py`、`test_ledger_import_flow.py`、`test_ledger_import_worker_e2e.py` 共 71 passed / 2 skipped（既有 skip registry）。

## 棘轮建议（后续任务用）

1. 新增代码零容忍：CI 中对差异文件运行 `ruff check <changed files> --select BLE001`，或待存量清偿后在 `backend/pyproject.toml` 直接启用 BLE001。
2. 清偿优先级：`api/routes`（面向用户的错误吞噬风险最高）→ `services`（业务口径静默降级）→ `tasks`（数据质量静默丢失）→ `scripts` / `core_finance/macro/toolkit/scripts`（研究/诊断脚本，风险最低）。
3. 与 S110/S112 相同的处置准则：日志化（fail-visible）优先；确属安全跳过的场景用 `# noqa: BLE001` 附一行原因注释。
