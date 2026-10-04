# 市场数据页视觉原语收敛设计

**日期：** 2026-08-28

**状态：** 待用户审阅

**范围：** `/market-data`

## 目标

本轮只解决市场数据页在内容已经完整的前提下，因重复外框和两套分区标题并存而显得层级偏深的问题。完成后，页面继续保持现有深色机构终端风格、信息密度和业务流程，但同一视觉表面不再被连续边框包裹，分区标题与当前页面级设计原语一致。

业务口径不在本轮变化。接口、查询参数、日期、单位、精度、空值语义、来源状态、正式与分析数据边界、筛选行为、懒加载门槛、业务文案以及现有契约锚点全部保持不变。

## 设计决定

采用受控混合方案，不做整页组件重写。页面继续保留 `PageDecisionHero`、现有 KPI 带、专用图表与业务表格；只把能够无损承接的两处分区标题迁到 `SectionHead`，并用页面局部样式压平四类已确认的重复外框。

“01 正式利率”使用 `SectionHead`，保留“利率行情”、现有说明和“查看完整曲线”操作；“03 资金市场与存单”同样使用 `SectionHead`，保留“资金读数”和现有说明。两处都显式关闭自动编号，因为标题本身已经含有 `01` 和 `03`，其间也不存在可由共享组件推导的连续编号域。外层区块的 `id`、`data-testid`、链接目标和辅助语义不改名，并以标题 ID 建立 `aria-labelledby` 关联；“03”区当前的普通 `div` 改为语义化 `section`，使关联形成可访问区域。

KPI 带不迁到 `KpiStrip`。现有 KPI 脚注把可见内容和包含技术序列 ID 的 `title` 分开保存，而共享 `KpiStrip` 没有独立的脚注提示槽；直接迁移会丢信息或把技术 ID 暴露到正文，同时还会把单格高度从当前紧凑基线显著放大。保留现有 `KpiBand` 是当前组件契约下唯一无损的选择。

## 外框压平

压平只针对“外层和内层表达同一个视觉表面”的结构，不按边框数量机械删除。页面局部结构与样式将处理以下四处：Hero 内状态与结论区域的重复面板、扩展终端外层与内部折叠面板的双重框、Tushare 折叠内容外的重复包裹，以及序列浏览器根容器与其内部工作区的重复框。

Hero 采用结构性收敛，不用更高优先级样式覆盖共享 conclusion 面板。`DataStatusStrip` 从 `PageDecisionHero` 的 `conclusion` 槽移到 Hero 内容区的第一个直接子节点，仍在 KPI 带之前，并继续保留 `market-data-status-strip`、`role="region"` 和全部状态内容；页面局部类在这个单一状态容器上承接左侧 3 像素语义强调线。这样共享 `.moss-page-v2-decision-hero__conclusion` 不再生成，`DataStatusStrip` 本身仍然保留。

Hero 外框继续保留。扩展终端的折叠交互、标题和内容边界继续保留；序列浏览器的目录、详情和表格卡仍是不同工作区，也继续保留。正式利率面板与图表画布使用不同表面表达业务分区，不属于重复外框；资金市场区、控制项、活动态占位边框和其他专用卡片也不改。

样式修改只在市场数据页局部完成，不改共享 `workbenchShell` 或其他页面原语。现有宽泛选择器会收窄到真正需要外框的一级卡片，避免通过全局覆盖影响其他业务页面。

## 交互与业务边界

页面继续维持 mixed-source 语义：正式利率只覆盖 formal 片段，Choice 宏观、外汇分析、NCD proxy 和联动摘要仍是 analytical；`formal_use_allowed=false` 继续在首屏状态条和正式利率口径摘要中可见。

日期、曲线、来源与刷新控件，筛选只做本地过滤的行为，扩展终端和联动摘要的懒挂载门槛，新闻日历的自持查询，打印与 Ctrl+F 的强制物化，原生 `details` 的 DOM 行为，以及正式外汇明细首次展开才挂载的规则均不改变。所有现有 `market-data-*` 测试锚点和 ARIA 标签继续有效。

## 实施与验证

生产代码只修改：

- `frontend/src/features/market-data/pages/MarketDataPage.tsx`
- `frontend/src/features/market-data/pages/MarketDataPage.css`

验证代码修改 `frontend/src/test/MarketDataPage.test.tsx`，并新增独立的 `frontend/tests/playwright/market-data-layout-primitives.spec.mjs`；不改当前工作区中已有改动的市场数据 Playwright 文件。

先补会失败的契约测试，确认两处分区标题具备新的 `SectionHead` DOM 与无障碍关联，同时旧标题实现尚不能满足断言；再补一组在当前页面必然失败的 Playwright 结构与计算样式断言，最后才修改生产代码。红灯断言使用以下稳定节点：

- Hero：`[data-testid="market-data-hero"]` 不再包含 `.moss-page-v2-decision-hero__conclusion`，其直接子节点 `[data-testid="market-data-status-strip"]` 的左边框为 3 像素。
- 扩展终端：`[data-testid="market-data-extended-terminal-section"]` 的外框、背景、阴影和内边距归零，而 `[data-testid="market-data-extended-terminal-collapse"]` 仍有有效边界。
- Tushare：首次展开 `[data-testid="market-data-tushare-collapse"]` 后，其内部直接包裹 `.market-data-lower-deck-section` 的外框、背景、阴影和内边距归零，内部 `.market-data-tushare-panel` 边界仍存在。
- 序列浏览器：用 `?view=explorer` 打开后，`[data-testid="market-data-explorer-view"]` 的根外框、背景、阴影和内边距归零，内部 `.market-data-explorer__directory` 及详情工作区边界仍存在。

这些断言锁定 DOM 角色和计算样式，不锁源码字符串，也不把全页边框总数当成契约。

浏览器验证覆盖 1440 像素桌面视口以及 768、390 像素窄视口。首屏高度用 `[data-testid="market-data-hero"]` 顶部到 `[data-testid="market-data-formal-rates-board"]` 底部的距离量测；在第一轮红灯运行中记录固定 mock 数据下的改前基线，改后不得超过该基线 1 像素。横向溢出统一用 `document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1` 判断。验收时，四类已确认的同表面重复框应全部消失；正式利率面板、内部工作区和交互控件的有效边界必须仍然可辨。现有市场数据页单元测试、相关布局原语测试、类型检查和视觉债务审计都应通过。

## 风险与控制

主要风险不是组件替换本身，而是页面末尾大量高优先级样式误伤新标题，或宽泛选择器在窄屏下改变真实业务卡片的边界。实施时会先收窄选择器，再检查桌面与窄屏计算样式；不会整块删除包含其他专用头部的分组规则。

当前“查看完整曲线”链接已有一个与本轮无关的死锚点问题。本轮保持其现状，不借视觉收敛顺带改变交互目标；如需修复，应作为独立工作流核对。
