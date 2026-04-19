# Frontend Numeric Correctness Implementation Plan

> **For agentic workers:** 本 plan 由 Cursor Agent 主理审阅合并，由 composer-2 subagent 分任务执行。每个波次（wave）内部的 task 可并发，波次之间严格串行。每个 task 的详细 prompt 位于 `docs/superpowers/plans/composer/wave-<N>/<task-id>.md`。

**Goal:** 用 8-10 周把前端所有 governed 数字升级为端到端可审计的 typed Numeric，引入 adapter/selector/formatter 分层、统一状态组件族、authoritative snapshot，并完成全仓 string-as-number contract 升级。

**Architecture:** 后端 pydantic 引入通用 `Numeric` type（raw + unit + display + precision + sign_aware），前端通过 zod schema 做 runtime 对拍；每页建立独立 adapter/selector，formatter 和 tone 全局单一出口；`AsyncSection` 升级为 7 状态 `DataSection`；Dashboard 切到 `/ui/home/snapshot` 消除 mixed 日期。

**Tech Stack:** Python 3.14 + pydantic v2、TypeScript + React + vitest + playwright、zod（schema 对拍）、echarts（图表）、DuckDB/PostgreSQL（governance 读面）

**Spec:** `docs/superpowers/specs/2026-04-18-frontend-numeric-correctness-design.md`

---

## 波次索引（5 波 · 32 任务）

| Wave | 周数 | 任务数 | 目标 | 阻塞 |
|---|---|---|---|---|
| W1 · 基础设施 | 1 周 | 5 | 全局 Numeric type、format/tone 单一出口、DataSection 组件族、mock↔schema 对拍 | 无（起点） |
| W2 · Executive 升级 | 1-2 周 | 8 | executive 两页（Dashboard 端）typed + adapter + 颜色修复 + E2E | W1 |
| W3 · PnL Attribution 升级 | 1-2 周 | 6 | PnL 工作台 typed + adapter + 饼图修复 + E2E | W1 |
| W4 · Snapshot & 口径 | 1-2 周 | 5 | `/ui/home/snapshot` + source_surface 强制 + naming lint + fail-fast | W2 / W3 |
| W5 · 全仓扩展层 | 3-4 周 | 8 | bond-analytics / KRD / BondDashboard / PnL bridge / cashflow / liability 的 typed 升级 | W1（并可部分 W4 后并行） |

---

## 依赖图

```
W1 (基础设施 5 任务，全部并行)
 ├─→ W2 (Executive 8 任务，内部按 backend→adapter→component→mock→E2E 顺序部分串行)
 ├─→ W3 (PnL 6 任务，同上)
 ├─→ W5.1-5.6 (6 个独立域，可与 W2/W3 部分并行)
 │
 └─→ W4 (Snapshot 5 任务，须 W2+W3 合并后开始)
       └─→ W5.7-5.8 (组件改造 + 全仓回归测试，最后执行)
```

## 波次内 vs 波次间规则

- **波次内**：task 之间**可并发**启动 composer subagent，彼此不依赖
- **波次间**：**严格串行**，前一波全部 merge + CI 绿 + 打 tag 之后，才启动下一波
- **主理审阅**：每个 task 的 composer subagent 返回后，主理必审以下四项：
  1. diff 是否仅涉及 prompt 白名单路径
  2. 是否违反 `docs/superpowers/specs/2026-04-18-frontend-numeric-correctness-design.md` §2 分层约束
  3. 测试是否覆盖 design §10 的 5 场景 / 契约 / 一致性 / E2E
  4. composer 是否声明了越界操作（diff vs 自述）

---

## Wave 1 · 基础设施（5 任务，全并行）

| Task ID | Prompt 文件 | 目标 | 核心产出 |
|---|---|---|---|
| W1.1 | `composer/wave-1/1.1-backend-numeric-schema.md` | 后端 `Numeric` type + 单元测试 | `backend/app/schemas/common_numeric.py` + `tests/test_common_numeric.py` |
| W1.2 | `composer/wave-1/1.2-frontend-numeric-type.md` | 前端 `Numeric` type + zod schema + 代码生成脚本 | `frontend/src/api/contracts.ts`（新增 Numeric/NumericUnit）+ `frontend/src/api/generated/zod/numeric.ts` + 生成脚本 |
| W1.3 | `composer/wave-1/1.3-format-tone-modules.md` | 全局 `format.ts` + `tone.ts` 集中化 | `frontend/src/utils/format.ts` 扩展 + 新建 `frontend/src/utils/tone.ts` + 单测 |
| W1.4 | `composer/wave-1/1.4-data-section-component.md` | `DataSection` 7 状态组件 | `frontend/src/components/DataSection.tsx` + 单测 + storybook-style 示例页 |
| W1.5 | `composer/wave-1/1.5-mock-schema-contract.md` | mock↔schema 运行时对拍脚本 + CI 钩子 | `scripts/check_mock_contract.mjs` + CI job 配置 |

**Wave 1 DoD：**
- 所有 5 task 各自 CI 绿
- Numeric 在前后端 shape 一致（通过对拍脚本验证）
- DataSection 7 状态都有单元测试
- 打 tag：`numeric-correctness-w1-done`

---

## Wave 2 · Executive 升级（8 任务）

| Task ID | Prompt 文件 | 依赖 | 目标 |
|---|---|---|---|
| W2.1 | `composer/wave-2/2.1-executive-schema-numeric.md` | W1.1 | `schemas/executive_dashboard.py` 升级 Numeric |
| W2.2 | `composer/wave-2/2.2-executive-service-numeric.md` | W2.1 | `services/executive_service.py` 构造 Numeric |
| W2.3 | `composer/wave-2/2.3-dashboard-adapter.md` | W2.1 / W1.3 | `features/executive-dashboard/adapters/` + 5 场景单测 **+ `contracts.ts` 5 个类型升级 Numeric**（mid-execution plan fix，见 W2.3 subagent follow-up） |
| W2.4 | `composer/wave-2/2.4-dashboard-selectors.md` | W2.3 | `features/executive-dashboard/selectors/` + 跨组件一致性测试 |
| W2.5 | `composer/wave-2/2.5-overview-section-rewrite.md` | W2.3 / W2.4 / W1.4 | `OverviewSection` 只读 view-model，Math.* 清零 |
| W2.6 | `composer/wave-2/2.6-pnl-attribution-section-rewrite.md` | W2.3 / W2.4 / W1.3 | `PnlAttributionSection` 环形→bipolar waterfall、删除 chartToneColor |
| W2.7 | `composer/wave-2/2.7-dashboard-mock-update.md` | W2.1 / W1.5 | Dashboard mock payload 升级 + 对拍通过 |
| W2.8 | `composer/wave-2/2.8-dashboard-e2e.md` | W2.5 / W2.6 / W2.7 / W1.4 | Playwright E2E 7 状态 + 报告日切换 + mock/real 切换 |

**Wave 2 内部串行链：** `2.1 → 2.2 → 2.3 → 2.4 → (2.5 ∥ 2.6) → 2.8`；`2.7` 与 `2.3-2.6` 并行。

**Wave 2 DoD：**
- Dashboard 所有 governed 字段消费 Numeric 类型
- 跨组件一致性集成测试绿（card = chart raw）
- E2E 7 状态快照全绿
- `npm run typecheck` 归零（W2.3-W2.6 合并后，组件迁移完）
- tag：`numeric-correctness-w2-done`

**Wave 2 中间状态（已知）：** W2.3 合并后、W2.6 合并前，`npm run typecheck` 会有错误，因为 `OverviewSection` / `PnlAttributionSection` / `DashboardPage` 仍然消费旧 string shape；W2.5/W2.6/W4.3 修复。vitest 不受影响（用 esbuild 不依赖 tsc）。

---

## Wave 3 · PnL Attribution 升级（6 任务）

| Task ID | Prompt 文件 | 依赖 | 目标 |
|---|---|---|---|
| W3.1 | `composer/wave-3/3.1-pnl-schema-numeric.md` | W1.1 | `schemas/pnl_attribution.py` 升级 Numeric（VolumeRate/TPL/Composition/Advanced/Campisi） |
| W3.2 | `composer/wave-3/3.2-pnl-service-numeric.md` | W3.1 | `services/pnl_attribution_service.py` 构造 Numeric |
| W3.3 | `composer/wave-3/3.3-pnl-adapter.md` | W3.1 / W1.3 | `features/pnl-attribution/adapters/` + 单测 |
| W3.4 | `composer/wave-3/3.4-pnl-charts-rewrite.md` | W3.3 | 5 图表组件改造：VolumeRate/TPLMarket/Composition/Advanced/Campisi |
| W3.5 | `composer/wave-3/3.5-composition-bipolar-waterfall.md` | W3.4 | `PnLCompositionChart` 饼图→bipolar waterfall 或加显式"绝对值占比"标题 |
| W3.6 | `composer/wave-3/3.6-pnl-mock-and-e2e.md` | W3.2 / W3.4 / W3.5 / W1.5 | mock 同步 + E2E 快照 |

**Wave 3 内部串行链：** `3.1 → 3.2 → 3.3 → (3.4 → 3.5) → 3.6`；与 Wave 2 可完全并行（不共享文件）。

**Wave 3 DoD：**
- PnL 工作台所有 governed 字段消费 Numeric
- 饼图（若保留）必须显式"绝对值占比"标注
- E2E 绿
- tag：`numeric-correctness-w3-done`

---

## Wave 4 · Snapshot & 口径（5 任务）

| Task ID | Prompt 文件 | 依赖 | 目标 |
|---|---|---|---|
| W4.1 | `composer/wave-4/4.1-home-snapshot-endpoint.md` | W2 合并 | 后端 `GET /ui/home/snapshot` 严格/宽松双模式 + 单测 |
| W4.2 | `composer/wave-4/4.2-source-surface-enforcement.md` | W2 / W3 合并 | `ResultMeta.source_surface` 字段 + 所有 envelope 强制填充 + 后端 lint |
| W4.3 | `composer/wave-4/4.3-dashboard-switch-to-snapshot.md` | W4.1 | `DashboardPage` 切到 snapshot 消费，删除 mixed |
| W4.4 | `composer/wave-4/4.4-naming-lint.md` | W4.2 | `scripts/check_surface_naming.mjs` + CI |
| W4.5 | `composer/wave-4/4.5-fail-fast-production-build.md` | W1 | `parseEnvMode` 生产模式 fail-fast |

**Wave 4 内部串行链：** `4.1 → 4.3`；`4.2 → 4.4`；`4.5` 独立。

**Wave 4 DoD：**
- Dashboard 默认严格日不再出现 `mixed` 标签
- 严格/宽松两种模式 E2E 都绿
- naming lint 在 CI 中拒绝违规
- 生产构建未设 `VITE_DATA_SOURCE=real` 时 fail-fast
- tag：`numeric-correctness-w4-done`

---

## Wave 5 · 全仓扩展层（8 任务）

| Task ID | Prompt 文件 | 依赖 | 目标 |
|---|---|---|---|
| W5.1 | `composer/wave-5/5.1-bond-analytics-typed.md` | W1 | bond-analytics schemas + 前端 contracts + adapter |
| W5.2 | `composer/wave-5/5.2-krd-cashflow-typed.md` | W1 | KRD + cashflow-projection schemas/contracts/adapter |
| W5.3 | `composer/wave-5/5.3-bond-dashboard-typed.md` | W1 | BondDashboard schemas/contracts/adapter |
| W5.4 | `composer/wave-5/5.4-pnl-bridge-typed.md` | W1 | PnL bridge schemas/contracts/adapter |
| W5.5 | `composer/wave-5/5.5-liability-typed.md` | W1 | Liability（risk/buckets, yield-metrics, counterparty, monthly, adb）schemas/contracts/adapter |
| W5.6 | `composer/wave-5/5.6-benchmark-action-audit.md` | W5.1 | Benchmark excess / Action attribution / Accounting audit |
| W5.7 | `composer/wave-5/5.7-extension-components-rewrite.md` | W5.1-5.6 | 对应组件改造 + mock 同步（依赖 W1.3/W1.4） |
| W5.8 | `composer/wave-5/5.8-contract-regression-baseline.md` | W5.1-5.7 | 全仓 contract runtime 对拍 + CI 回归基线 |

**Wave 5 内部结构：**
- `5.1, 5.2, 5.3, 5.4, 5.5` 可**全部并行**（每个独立业务域）
- `5.6` 依赖 `5.1`
- `5.7` 依赖所有 5.1-5.6
- `5.8` 依赖 5.7，作为最终把关

**Wave 5 DoD：**
- 所有 governed 页面 contract 无 string-as-number 残留
- 所有 mock 通过 zod parse
- tag：`numeric-correctness-w5-done`

---

## 每波启动 Checklist（主理执行）

### 波次启动前
- [ ] 前一波的 tag 已打，CI 绿
- [ ] 本波所有 task 的 composer prompt 文件存在且已被主理通读
- [ ] 依赖图内本波上游确实已 merge

### 波次内每个 task 启动
- [ ] 从 prompt 文件复制完整内容给 `composer-2` subagent
- [ ] 明确传递：本任务白名单路径、禁止路径、返回清单
- [ ] 启动（`run_in_background: true` 视任务长度决定）

### 波次内每个 task 返回后（主理审阅 4 项）
- [ ] 路径白名单：`git diff --name-only` 对比 prompt 白名单
- [ ] 分层约束：抽查组件是否 `Math.*` / `/100000000` 清零
- [ ] 测试覆盖：5 场景 / 契约 / 一致性 / E2E 按本波适用性勾选
- [ ] 越界自述：composer 返回 message 是否有 "warning: touched X outside whitelist"

### 波次合并后
- [ ] 本波所有 task 合并进主分支
- [ ] 跑 `npm run typecheck && npm run test && npm run build` 全绿
- [ ] 跑 `python -m pytest -q` 全绿
- [ ] 打 tag `numeric-correctness-w<N>-done`
- [ ] 在 `CHANGELOG.md` 记录本波摘要

---

## 风险回滚

每个 tag 都是回滚点。紧急回滚命令（主理执行，**非 composer subagent 执行**）：

```bash
git reset --hard numeric-correctness-w<N-1>-done
git push origin HEAD:refs/heads/<current-branch> --force-with-lease
```

使用 `--force-with-lease` 而非 `--force`，避免覆盖他人提交。

---

## Composer Subagent 协作协议

所有 composer-2 subagent prompt **必须**以下列约束开头（在每份 prompt 文件里重复列出）：

```
你是一个专注执行本单一 task 的 composer-2 subagent。
- 仅允许修改"允许修改的路径"白名单中的文件
- 遇到白名单外问题，在返回 message 中以 "BLOCKER:" 前缀报告，不要擅自修改
- 不要运行 git push / git reset --hard / git commit --amend
- 不要修改 package.json / requirements.txt 的依赖版本（除非 prompt 明确要求）
- 不要修改 .cursor / .gstack / CLAUDE.md / AGENTS.md 等配置
- 完成后以下列结构返回：
  1. 修改文件列表
  2. 测试命令输出摘要
  3. 越界/告警（如有）
  4. 是否需要主理决策的遗留问题
```

每份 prompt 的"允许修改的路径"白名单必须具体、可验证，**禁止**使用 "相关文件" / "如有需要" 这类模糊措辞。

---

## Execution Handoff

本 plan 保存在 `docs/superpowers/plans/2026-04-18-frontend-numeric-correctness-plan.md`。

**执行方式：Subagent-Driven**
- 波次内并行启动 composer-2 subagent
- 每个 task 对应一份独立 prompt 文件
- 主理在每个 task 返回后审阅合并
- 波次间严格串行

启动第一个波次前，主理必须先通读 W1 的 5 份 prompt 文件，确认样品质量。确认后再进入批量执行。

