# 跨资产驱动页（`/cross-asset`）UI 落地计划

## 目标

在**不改变数据契约、不改 API 与 model 计算**的前提下，把 `CrossAssetDriversPage` 的版式与视觉对齐近期静态参考稿的意图：

- 暖色纸面背景、主内容区**横向占满**可用宽度（避免「主栏过窄、右侧空」的观感）。
- 标题区文案层级：**市场工作台** eyebrow、清晰的数据日与跳转市场数据说明。
- **KPI 带**：在桌面端使用 **4 列栅格**（8 个槽位为 4×2），与参考稿一致。
- **信息结构**：`市场判断` 与 `宏观-债市相关性` 并排；`驱动拆解` 单独满宽，与现网 static 参考顺序一致，避免传导/跨资产结论文案被压到窄栏。
- 原右侧 **sticky 侧栏**（数据状态 + 热力表）并入主列：数据状态**紧随页头**（仍保留全部 provenance 字段与 test id）。

## 非目标（本轮不做）

- 不新增端点、不修改 `crossAssetDriversPageModel` / `crossAssetKpiModel` 的数值逻辑。
- 不全局改 `designSystem.ts` 或 Workbench 壳层（仅本页加 scoped class 与 `index.html` 字体链）。
- 不删除「传导主线」「跨资产结论文案」「NCD 代理」等现网能力模块。

## 实现要点

| 项 | 做法 |
|----|------|
| 字体 | `index.html` 增加 Google Fonts：`Plus Jakarta Sans`、`Noto Sans SC`、`IBM Plex Mono`；本页根节点 `font-family` 覆盖，等宽数字区保留 `tabularNumsStyle`。 |
| 样式 | 扩展 `CrossAssetDriversPage.css`：根 `.cross-asset-drivers-page` 定义纸色/CSS 变量；`.cross-asset-drivers-page__panel` 替代大量重复的 `detailPanelStyle` 卡片表面；KPI/双列栅格用 BEM 类。 |
| 结构 | 去掉最外层 `1fr + 360px` 栅格与 `<aside>`；主列内用 `__row-two` 放「市场判断 \| 相关性表」；`__drivers` 满宽。 |
| 回归 | `CrossAssetPage.test.tsx` 仍以 `data-testid` 断言；`npm run debt:audit` 不放宽基线。 |

## 风险与回滚

- 风险：E2E/截图若有依赖「侧栏在右侧」的假设，需以 testid 更新为准。
- 回滚：单页 CSS + 单文件 TSX 布局，可用 git 还原 `CrossAssetDriversPage.tsx` 与 `CrossAssetDriversPage.css`（及可选 `index.html` 字体链）。

## 完成定义

- 本地 `npm test -- CrossAssetPage` 通过；`npm run debt:audit` 通过或仅预期内提示。
