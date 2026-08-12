# ThemeGroupedView 装配交接说明

状态：**预制完成，未接线**。stock-analysis 域当前有并行会话的大量未提交改动，本次只新增文件，等域干净后按下述步骤接线。

## 本次新增文件（全部新文件，未改任何现有文件）

| 文件 | 说明 |
| --- | --- |
| `StockAnalysisThemeGroupedView.tsx` | 分组视图组件 + `buildStockThemeGroups` 分组/排序纯函数 + `POLICY_THEME_ORDER` 7 题材目录 |
| `StockAnalysisThemeGroupedView.css` | 组件样式，零新增色值，全部 `--dh-api-*` token |
| `StockAnalysisThemeGroupedView.test.tsx` | 8 个用例：分组/排序/筛选/空态/单题材回退/未知题材/证据复核区块 |
| `ThemeGroupedView.handoff.md` | 本文件 |

## 组件契约

props 与 `StockAnalysisThemeBreakoutPanel` **同名同形态**，可整体替换：

```tsx
type Props = {
  cards: StockThemeBreakoutCard[];        // 必传，题材信号行（pageModel buildThemeBreakoutCards 输出）
  emptyMessage: string;                   // 必传，7 题材全空时的空态文案
  evidenceRows?: StockThemeEvidenceStateRow[];   // 可选，缺省 []
  reviewItems?: StockThemeBreakoutReviewItem[];  // 可选，缺省 []
};
```

类型仅 type-import 自 `../lib/stockAnalysisPageModel`（该文件当前是干净的）；组件不 import 任何被占用文件（PageImpl、chartModel、页面 css、`src/pageModel/index.ts`、`tokens.css`、`tone.ts` 均未引用，CSS 变量走运行时全局作用域）。

## 装配步骤（预计 diff 约 6 行，均在 `pages/StockAnalysisPageImpl.tsx`）

行号以 2026-08-12 快照为准，接线时以锚点文本搜索为准（该文件正被并行会话修改）。

1. **lazy 声明**（锚点：搜 `LazyStockAnalysisThemeBreakoutPanel`，快照约 260-264 行），将 lazy 目标替换为新组件（4 行改动）：

```tsx
const LazyStockAnalysisThemeGroupedView = lazy(() =>
  import("../components/StockAnalysisThemeGroupedView").then((module) => ({
    default: module.StockAnalysisThemeGroupedView,
  })),
);
```

2. **渲染点**（锚点：搜 `sectionTestId="stock-analysis-theme-breakout"` 所在的 `LazyStrategyModuleCard id="theme-breakout"`，快照约 3913-3922 行），把标签名换掉，props 原样保留（2 行改动）：

```tsx
<LazyStockAnalysisThemeGroupedView
  cards={themeBreakoutCards}
  evidenceRows={themeEvidenceRows}
  reviewItems={themeBreakoutReviewItems}
  emptyMessage={/* 原有表达式不动 */}
/>
```

3. 若要灰度并存（旧平铺 + 新分组切换），保留原 lazy 声明再新增一条 + 条件渲染，diff 约 12 行；默认推荐直接替换。

替换完成后旧 `StockAnalysisThemeBreakoutPanel.tsx` 将无引用，是否删除由域主决定（建议先保留一个迭代）。

## 组件行为要点（已由测试锁定）

- **分组**：按 `card.themeKey` 分组；组头 = 题材中文名 + 状态点 + 「信号 N 行」徽章 + 代理代码（`proxy_code`，title 注明申万一级行业代理篮子）。
- **排序**：有信号的组在前按行数降序；行数相同按 policy 声明序；未知 `theme_key`（policy 之外）排在已知题材之后、名称取数据行里的 `themeName`。无信号题材按 policy 声明序进汇总条。
- **筛选 chips**：「全部（总行数）」+ 各有信号题材（行数徽章，点击过滤、再点还原）+ 无信号题材（0 徽章、禁用）。纯组件内 `useState`，cards 变化后失效选择自动回退「全部」。
- **空态**：7 题材全空 → 收缩消息框显示 `emptyMessage`，不渲染 chips 与汇总条；单题材有数据 → 只渲染该组 + 可折叠「无信号题材 N 个」汇总条（展开列出题材名 + 代理代码）。
- **行渲染**：内联实现了旧 ThemeBreakoutPanel 行逻辑的最小必要子集（rank/父行业/摘要/来源 pill、五个统计 chip、reason/最新事件/边界提示、龙头股列表），题材名不再在行内重复（组头已有，符合 DESIGN §6 去重）。
- **证据/复核区块**：与旧面板行为一致（`current_overlay` → 「题材证据受限」；复核项含未过门槛 pill 与龙头列表），props 不传则不渲染。
- **色点语义**：组头/汇总条圆点承载信号状态（有信号=`--dh-api-blue`，无信号=`--dh-api-muted`），非装饰点（DESIGN §6）。
- **7 题材目录**：`POLICY_THEME_ORDER` 硬编码镜像后端 `strategy_policy.POLICY.theme_proxies` 声明序（`rv_livermore_theme_breakout_multi_proxy_v6`）：半导体 S270000 → 算力AI S710000+S730000 → 机器人与智能装备 S640000 → 国防军工 S650000 → 新能源 S630000 → 医药 S370000 → 券商 S490000。后端题材池调整时需同步。

## 验证

- 已跑：`npm run test -- StockAnalysisThemeGroupedView` → 8/8 通过（2026-08-12）。
- 已跑：新文件 eslint 0 error（2 个 react-refresh 警告，见下）；`debt:audit`/视觉 token 审计的失败项均来自其他域被占用文件，本次新文件零 hex、未上榜。
- 接线后请补：`npm run test -- StockAnalysisTheme`（连同旧面板相关用例）、`npm run lint`、`npm run typecheck`、`npm run debt:audit`，并在 1440×900 下浏览器走查 `id="theme-breakout"` 卡片（深色主题、chips 交互、折叠条）。

## 遗留与后续建议（域干净后）

1. `buildStockThemeGroups` / `POLICY_THEME_ORDER` 下沉到 `lib/stockAnalysisPageModel.ts`（或独立 lib 模块），消除组件文件的 2 个 react-refresh 警告。
2. 题材目录改为由 payload 驱动（后端已返回 `theme_count`，可考虑让 API 直接披露 policy 题材清单），去掉前端硬编码镜像。
3. 视觉走查后如需与页面其他新组件（如 SectorStrengthCard）统一密度，可在 CSS 内微调 padding，不动 token。
