# 前端重构实施 Prompt 包 (v2 — 原子任务版)

> 生成自 Deep Interview Session 2026-04-14
> 策略: 增量重构 + 原子任务（每个任务只做一件事）

## 与 v1 的区别

| 维度 | v1 (旧) | v2 (原子任务) |
|------|---------|-------------|
| 事实准确性 | 部分事实错误（如声称 ConfigProvider 未挂载） | 基于逐行阅读校准 |
| 任务粒度 | 1 prompt = 15+ 件事 | 1 任务 = 1 个组件/区块 |
| 锚定方式 | "增强某页面" | "行 1601-1629 替换为..." |
| 禁止事项 | 泛泛 | 精确列出"已有的 X 不要动" |
| 验证频率 | 最后一次 | 每个任务后 typecheck |

## 执行顺序

```
Phase 0 (5 任务) → Phase 1 (8 任务) → Phase 2 (4 任务)
                                     → Phase 3 (6 任务) ← 可与 2 并行
                                     → Phase 4 (7 任务) ← 可与 2/3 并行
                  → Phase 5 (6 任务)
                  → Phase 6 (6 任务)
```

## 文件清单

| Phase | 文件 | 任务数 | 目标 |
|-------|------|--------|------|
| 0 | `phase-0-atomic.md` | 5 | 格式化工具 + 新共享组件 |
| 1 | `phase-1-atomic.md` | 8 | 资产负债分析（第一优先级） |
| 2 | `phase-2-atomic.md` | 4 | 驾驶舱 |
| 3 | `phase-3-atomic.md` | 6 | 债券分析 |
| 4 | `phase-4-atomic.md` | 7 | 市场数据 |
| 5 | `phase-5-atomic.md` | 6 | 经营分析 |
| 6 | `phase-6-atomic.md` | 6 | 跨资产驱动 |

总计: **42 个原子任务**

## 使用方式

每个 Phase 打开一个新 Cursor Agent 窗口:

1. 输入对应 `phase-X-atomic.md` 的**全文**
2. Agent 按序执行每个任务
3. 每个任务完成后 `npx tsc --noEmit` 验证
4. 全部任务完成后 `npm run lint && npm run build`

## 关键约束（每个 prompt 都已内置）

- ConfigProvider + workbenchTheme **已挂载**，不要重复
- KpiCard/SectionCard/FilterBar/StatusPill/AsyncSection **已存在于** `src/components/`
- BalanceAnalysis 的 basisBreakdown / advancedAttribution API **已接通**
- CrossAsset 已有 KPI/sparkline/驱动拆解/走势图
- BondAnalytics 已有 21 个子组件和模块注册表
- 不引入新 npm 依赖
- 不删除现有功能
- Mock 数据只标注来源，不伪造真实后端能力

## 旧版 prompt（已过时）

以下文件为 v1 版本，保留供参考但**不应使用**:
- `phase-0-global-infrastructure.md` (v1)
- `phase-1-asset-liability-analysis.md` (v1)
- `phase-2-dashboard.md` (v1)
- `phase-3-bond-analysis.md` (v1)
- `phase-4-market-data.md` (v1)
- `phase-5-business-analysis.md` (v1)
- `phase-6-cross-asset-drivers.md` (v1)
