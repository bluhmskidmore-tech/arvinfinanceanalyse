# Stock Analysis First-Screen Contract Gap

日期：2026-07-06

范围：只锁定现状并说明差异，不做行为变更。对比后端 `StockAnalysisWorkbenchPayload.first_screen` 与前端 `buildCandidateReviewQueue` 自建首屏队列。

## 结论

待 owner 裁决：前端消费 vs 后端移除。

当前后端 workbench envelope 已构建 `result.first_screen`，契约文档也写明页面应能从 workbench query 渲染首屏；但 `frontend/src/features/stock-analysis` 没有消费 `workbenchPayload.first_screen`。页面实际队列来自 `modules.main.result` 提取出的 Livermore payload，再由 `buildCandidateReviewQueue(payload)` 生成。

## 证据

- 后端构建点：`backend/app/services/stock_analysis_workbench_service.py` 的 `_first_screen()` 返回 `market_gate`、`review_queue`、`sector_snapshot`、`risk_exit_snapshot`、`data_gaps`、`diagnostics`、`supported_outputs`、`unsupported_outputs`。
- 后端队列构建点：`_candidate_queue()` 按固定模块顺序扫描 `stock_candidates`、`factor_screen_candidates`、`hybrid_fusion_candidates`、`uptrend_momentum_candidates`、`fresh_trend_watchlist`、`mean_reversion_candidates`、`theme_breakout`。
- 前端实际入口：`StockAnalysisPageImpl.extractWorkbenchStrategyPayload()` 从 `workbenchPayload.modules.main.result` 提取 `LivermoreStrategyPayload`，随后页面模型使用 `buildCandidateReviewQueue(payload)`。
- 前端无直接消费：在 `frontend/src/features/stock-analysis` 内没有 `first_screen` 读取；`review_queue` 字符串只出现在 UI 标签、详情来源或 `decision_summary.review_queue_count` 等路径。
- 契约文档：`docs/stock_analysis_workbench_api_contract.md` 的 `first_screen` 字段和 Frontend Consumption Rule 仍描述“首屏可由 workbench query 渲染”。
- MCP/GitNexus：当前 Codex tool surface 未暴露 `gitnexus_*` 或 `moss-*` 项目 MCP 工具；本报告使用本地代码、类型和契约文档证据，不裁决指标定义或 owner 审批状态。

## 差异表

| 维度 | 后端 `first_screen.review_queue` | 前端 `buildCandidateReviewQueue` |
| --- | --- | --- |
| 消费状态 | envelope 中存在，但 stock-analysis feature 不读取 | 页面实际首屏队列来源 |
| 字段命名 | 保留后端原始 snake_case 字段，并追加 `source_module` | 输出 UI camelCase 字段：`stockCode`、`reviewFocus`、`primaryEvidence`、`boundaryEvidence`、`invalidationFocus` 等 |
| 字段丰富度 | 透传候选原始字段，按来源补 `source_module` | 重组为展示模型，拆分主证据/辅助证据/边界证据/失效规则/原始字段 |
| 排序 | 按模块顺序和各容器原始顺序取数；不在 `_candidate_queue()` 内按 `rank` 重排 | `buildCandidateEvidenceCards()` 内按候选 `rank` 排序；如果 hybrid primary 有候选，直接优先使用 hybrid 队列 |
| 过滤 | 仅按 `top_k` 截断；同一 `source_module + stock_code` 去重，不跨模块去重 | 受 `module_states` 影响：`render_mode !== primary` 或 `excludes_from_primary` 会排除首屏队列 |
| 模块优先级 | 固定顺序：Livermore stock -> factor -> hybrid -> uptrend -> fresh trend -> mean reversion -> theme | 优先 hybrid primary；否则 stock primary；否则 fresh trend primary；未把 factor/mean/theme 直接混入主队列 |
| 风险/板块/缺口 | 同一 `first_screen` 同时带 `sector_snapshot`、`risk_exit_snapshot`、`data_gaps`、`diagnostics` | 候选队列只关心候选卡；板块、风险、边界由其他 page-model 函数分别构建 |
| 阻断语义 | `decision_summary.can_review_candidates` 和 `page_question.answer_state` 由后端基于 `first_screen.review_queue` 与 issues 计算 | 页面会消费后端 `decision_summary/page_question`，但候选列表本身仍来自前端队列 |

## 当前锁定

- 新增后端 pytest 锁定 `first_screen` 顶层字段、队列 `source_module`、板块快照、风险退出 bucket、缺口/诊断/输出字段。
- 新增前端 Vitest 锁定 `buildCandidateReviewQueue` 的关键字段、rank 排序、主/辅助证据切片、边界证据、失效焦点和 raw field keys。

## Owner 待裁决项

1. 前端消费：将首屏候选、板块、风险、缺口等首屏区域切到 `workbenchPayload.first_screen`，并保留 `modules.main.result` 作为详情/兼容来源。
2. 后端移除：若 owner 判定前端自建队列是长期方案，则后端 `first_screen` 应从 contract 中降级或移除，避免维护两套首屏事实。

回滚方式：revert 单 commit；本次范围应仅包含新增测试与新增审计文档，无行为变更。
